"""Generate the first coach message for an athlete."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from app.config import settings
from app.core.logging_utils import log_event
from app.models.coaching_message import CoachingMessage
from app.models.enums import MessageType
from app.models.generation_event import GenerationEvent
from app.repositories.coaching_message_repository import CoachingMessageRepository
from app.repositories.generation_event_repository import GenerationEventRepository
from app.schemas.coaching import CoachingMessageResponse
from app.services.context_budget_service import ContextBudgetService
from app.services.event_publisher import EventPublisher
from app.core.prompt_registry import PromptNotFoundError, PromptRegistry

if TYPE_CHECKING:
    from app.repositories.training_goal_repository import TrainingGoalRepository
    from app.repositories.training_plan_repository import TrainingPlanRepository
    from app.repositories.twin_state_repository import TwinStateRepository


class FirstMessageAlreadyExistsError(Exception):
    """First message already exists for this athlete (HTTP 409)."""

    def __init__(self, existing_message_id: uuid.UUID) -> None:
        super().__init__("first message already exists")
        self.existing_message_id = existing_message_id


class LLMServiceUnavailableError(Exception):
    """LLM call failed (HTTP 503)."""


class FirstMessageAgent:
    """Generate the first coach message for an athlete."""

    PROMPT_VERSION = "v1"

    def __init__(
        self,
        session: AsyncSession,
        coaching_messages: CoachingMessageRepository,
        generation_events: GenerationEventRepository,
        context_budget: ContextBudgetService,
        prompt_registry: PromptRegistry,
        training_goals: "TrainingGoalRepository",
        plans: "TrainingPlanRepository",
        twin_states: "TwinStateRepository",
        events: Optional[EventPublisher] = None,
    ) -> None:
        self._session = session
        self._coaching_messages = coaching_messages
        self._generation_events = generation_events
        self._context_budget = context_budget
        self._prompt_registry = prompt_registry
        self._training_goals = training_goals
        self._plans = plans
        self._twin_states = twin_states
        # Build a real publisher on demand if caller did not inject one.
        if events is None:
            from app.repositories.system_event_outbox_repository import (
                SystemEventOutboxRepository,
            )
            from app.repositories.system_event_repository import (
                SystemEventRepository,
            )

            self._events = EventPublisher(
                SystemEventRepository(session),
                SystemEventOutboxRepository(session),
            )
        else:
            self._events = events

    def _build_llm_client(self) -> AsyncOpenAI:
        """Build the OpenAI-compatible client for LiteLLM proxy."""
        return AsyncOpenAI(
            base_url=settings.LITELLM_BASE_URL,
            api_key=settings.LITELLM_API_KEY,
        )

    @staticmethod
    def validate_paragraph_count(content: str) -> None:
        """Ensure the message has exactly four paragraphs."""
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) != 4:
            raise ParagraphCountViolationError(
                f"expected 4 paragraphs, got {len(paragraphs)}"
            )

    async def generate(
        self, athlete_id: uuid.UUID
    ) -> CoachingMessageResponse:
        """Generate the first coach message for ``athlete_id``.

        Raises:
            FirstMessageAlreadyExistsError: if a ``first_message`` record
                already exists.
            LLMServiceUnavailableError: if the LLM call fails.
        """
        # -----------------------------------------------------------------
        # Pre-condition: no existing first message.
        # -----------------------------------------------------------------
        existing = await self._coaching_messages.get_existing_first_message(
            athlete_id
        )
        if existing:
            raise FirstMessageAlreadyExistsError(existing.id)

        # -----------------------------------------------------------------
        # Pre-condition: TwinState must exist (athlete completed onboarding).
        # Plan pseudocode requires this gate before context assembly so the
        # caller fails fast with a clear 503 message instead of a cryptic
        # downstream error from ContextBudgetService.
        # -----------------------------------------------------------------
        twin_state = await self._twin_states.get_latest(athlete_id)
        if twin_state is None:
            raise LLMServiceUnavailableError(
                "twin state not available; athlete must complete onboarding "
                "before coach message generation"
            )

        # -----------------------------------------------------------------
        # Pre-condition: an active TrainingGoal must exist.
        # -----------------------------------------------------------------
        active_goal = await self._training_goals.get_active(athlete_id)
        if active_goal is None:
            raise LLMServiceUnavailableError(
                "active training goal not available; athlete must set a "
                "goal before coach message generation"
            )

        # -----------------------------------------------------------------
        # Pre-condition: an active TrainingPlan must exist.
        # -----------------------------------------------------------------
        active_plan = await self._plans.get_active_for_athlete(athlete_id)
        if active_plan is None:
            raise LLMServiceUnavailableError(
                "active training plan not available; athlete plan must be "
                "generated before coach message generation"
            )

        # -----------------------------------------------------------------
        # Assemble context.
        # -----------------------------------------------------------------
        context = await self._context_budget.build_first_message_context(
            athlete_id
        )
        context_dict = context.to_dict()

        # -----------------------------------------------------------------
        # Load prompt.
        # -----------------------------------------------------------------
        prompt_version = self.PROMPT_VERSION
        try:
            prompt = self._prompt_registry.get_prompt("first_message", prompt_version)
        except PromptNotFoundError as exc:
            # Missing prompt file is a deploy bug; treat as service
            # unavailable (503) so the coach can retry.
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=self._context_budget.estimate_tokens(
                    {"messages": [{"role": "user", "content": ""}]}
                ),
                latency_ms=0,
                failure_reason="prompt_not_found",
            )
            raise LLMServiceUnavailableError(
                "coach configuration unavailable"
            ) from exc

        # -----------------------------------------------------------------
        # Call LLM via proxy.
        # -----------------------------------------------------------------
        llm_client = self._build_llm_client()
        start_time = datetime.now(timezone.utc)

        # Build OpenAI-compatible messages payload.
        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=prompt),
            ChatCompletionUserMessageParam(
                role="user", content=json.dumps(context_dict)
            ),
        ]

        input_tokens = self._context_budget.estimate_tokens(
            {"messages": messages}
        )

        try:
            response = await llm_client.chat.completions.create(
                model=settings.LLM_MODEL or "cohere/command-a-plus",
                messages=messages,
                max_tokens=1000,
            )
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )

            # Extract token counts from proxy response.
            usage = response.usage
            if usage:
                output_tokens = usage.total_tokens or 0
            else:
                output_tokens = self._context_budget.estimate_tokens(
                    {"content": response.choices[0].message.content or ""}
                )

            generated_content = response.choices[0].message.content or ""

            # Validate paragraph count.
            self.validate_paragraph_count(generated_content)

            # -----------------------------------------------------------------
            # Success path.
            # -----------------------------------------------------------------
            generation_event = GenerationEvent(
                athlete_id=athlete_id,
                agent_name="FirstMessageAgent",
                prompt_version=prompt_version,
                trigger_context="manual_api_call",
                input_token_count=input_tokens,
                output_token_count=output_tokens,
                latency_ms=latency_ms,
                success=True,
                failure_reason=None,
            )
            await self._generation_events.insert(generation_event)

            # Fetch twin_state_id for FK.
            twin_state = await self._twin_states.get_latest(athlete_id)
            if twin_state is None:
                raise LLMServiceUnavailableError(
                    "twin state not found; cannot create message"
                )

            coaching_message = CoachingMessage(
                athlete_id=athlete_id,
                twin_state_id=twin_state.id,
                message_type=MessageType.FIRST_MESSAGE,
                content=generated_content,
                prompt_version=prompt_version,
            )
            await self._coaching_messages.insert(coaching_message)

            # Publish coaching_message_generated event via outbox.
            await self._events.publish(
                event_type="coaching_message_generated",
                athlete_id=athlete_id,
                payload={
                    "message_id": str(coaching_message.id),
                    "message_type": "first_message",
                    "generation_event_id": str(generation_event.id),
                    "prompt_version": prompt_version,
                },
            )

            log_event(
                event="coaching_message.generated",
                athlete_id=str(athlete_id),
                message_type="first_message",
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                outcome="success",
            )

            return CoachingMessageResponse.model_validate(coaching_message)

        except (APITimeoutError, APIConnectionError) as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            failure_reason = "timeout" if isinstance(exc, APITimeoutError) else "proxy_unavailable"
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason=failure_reason,
            )
            raise LLMServiceUnavailableError(
                f"LLM call failed: {failure_reason}"
            ) from exc

        except APIStatusError as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            failure_reason = "rate_limit" if exc.status_code == 429 else "api_error"
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason=failure_reason,
            )
            raise LLMServiceUnavailableError(
                f"LLM API error: {exc.message or 'unknown'}"
            ) from exc

        except ParagraphCountViolationError:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason="invalid_output_format",
            )
            raise LLMServiceUnavailableError(
                "coach response format invalid"
            )

    async def _write_generation_event_failure(
        self,
        *,
        athlete_id: uuid.UUID,
        prompt_version: str,
        input_tokens: int,
        latency_ms: int,
        failure_reason: str,
    ) -> None:
        """Write a GenerationEvent with success=False for any LLM failure."""
        generation_event = GenerationEvent(
            athlete_id=athlete_id,
            agent_name="FirstMessageAgent",
            prompt_version=prompt_version,
            trigger_context="manual_api_call",
            input_token_count=input_tokens,
            output_token_count=0,
            latency_ms=latency_ms,
            success=False,
            failure_reason=failure_reason,
        )
        await self._generation_events.insert(generation_event)
        log_event(
            event="coaching_message.generation.failed",
            athlete_id=str(athlete_id),
            message_type="first_message",
            prompt_version=prompt_version,
            failure_reason=failure_reason,
            outcome="failed",
        )


class ParagraphCountViolationError(Exception):
    """The generated message does not contain exactly four paragraphs."""