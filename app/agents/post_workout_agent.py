"""PostWorkoutAgent — generate the post-workout coach message (Phase-1.6 contract)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

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
from app.core.prompt_registry import PromptNotFoundError, PromptRegistry
from app.models.activity import Activity
from app.models.coaching_message import CoachingMessage
from app.models.enums import MessageType
from app.models.generation_event import GenerationEvent
from app.models.planned_session import PlannedSession
from app.models.twin_state import TwinState
from app.repositories.activity_repository import ActivityRepository
from app.repositories.coaching_message_repository import (
    CoachingMessageRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.planned_session_repository import PlannedSessionRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.compliance_service import (
    ComplianceFindings,
    ComplianceService,
)
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.services.event_publisher import EventPublisher


class PostWorkoutAgentError(Exception):
    """Base class for ``PostWorkoutAgent`` domain failures."""


class ActivityNotFoundError(PostWorkoutAgentError):
    """The ``activity_id`` does not exist (404 at the API layer)."""

    def __init__(self, activity_id: uuid.UUID) -> None:
        super().__init__(f"activity {activity_id} not found")
        self.activity_id = activity_id

class PostWorkoutLLMUnavailableError(PostWorkoutAgentError):
    """The LLM call failed (proxy / timeout / status / parse); mapped to HTTP 503."""

class PostWorkoutContractError(PostWorkoutAgentError):
    """The LLM output violated the three-paragraph structural rule."""

@dataclass
class PostWorkoutContext:
    """Structured payload serialised to JSON and sent to the LLM (Phase-1.6 shape — execution, comparable_session, objective_updates all null/empty)."""

    prescribed: Optional[Dict[str, Any]] = None
    compliance: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    comparable_session: Optional[Dict[str, Any]] = None
    objective_updates: list[dict[str, Any]] = field(
        default_factory=list[dict[str, Any]]
    )
    readiness: Optional[Dict[str, Any]] = None
    load_scores: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prescribed": self.prescribed,
            "compliance": self.compliance,
            "execution": self.execution,
            "comparable_session": self.comparable_session,
            "objective_updates": self.objective_updates,
            "readiness": self.readiness,
            "load_scores": self.load_scores,
        }

def describe_load(aerobic_load: Optional[float]) -> str:
    """Render a plain-language descriptor for the heuristic aerobic load (Phase-1.6 population-based thresholds)."""
    if aerobic_load is None:
        return "no load recorded"
    if aerobic_load < 30:
        return "light aerobic load"
    if aerobic_load < 60:
        return "moderate aerobic load"
    if aerobic_load < 100:
        return "steady aerobic load"
    return "heavy aerobic load"

def format_phase_position(
    planned_session: Optional[PlannedSession],
    twin_state: TwinState,
) -> str:
    """Render the plan-position phrase for paragraph 3 (e.g. "week 3 of the threshold build phase")."""
    if planned_session is None:
        return "early in the current training block"
    return (
        f"week {planned_session.week_number} of the "
        f"{planned_session.phase_label.value.replace('_', ' ')} phase"
    )

class PostWorkoutAgent:
    """Generate the post-workout coach message. Idempotent — returns existing message when present. The caller owns the commit boundary."""

    PROMPT_NAME = "post_workout"
    PROMPT_VERSION = "v1"
    AGENT_NAME = "PostWorkoutAgent"

    def __init__(
        self,
        session: AsyncSession,
        coaching_messages: CoachingMessageRepository,
        generation_events: GenerationEventRepository,
        activities: ActivityRepository,
        planned_sessions: PlannedSessionRepository,
        twin_states: TwinStateRepository,
        prompt_registry: PromptRegistry,
        compliance_service: Optional[ComplianceService] = None,
        events: Optional["EventPublisher"] = None,
    ) -> None:
        self._session: AsyncSession = session
        self._coaching_messages: CoachingMessageRepository = coaching_messages
        self._generation_events: GenerationEventRepository = generation_events
        self._activities: ActivityRepository = activities
        self._planned_sessions: PlannedSessionRepository = planned_sessions
        self._twin_states: TwinStateRepository = twin_states
        self._prompt_registry: PromptRegistry = prompt_registry
        self._compliance_service: ComplianceService = compliance_service or ComplianceService()
        if events is None:
            self._events = _build_default_publisher(session)
        else:
            self._events = events

    async def generate(
        self, athlete_id: uuid.UUID, activity_id: uuid.UUID
    ) -> CoachingMessage:
        """Generate or return the post-workout message. Idempotent — returns existing when present; raises ActivityNotFoundError on missing activity (404 at API)."""
        activity = await self._activities.get_by_id(activity_id)
        if activity is None or activity.athlete_id != athlete_id:
            raise ActivityNotFoundError(activity_id)

        existing = await self._coaching_messages.get_by_activity_and_type(
            athlete_id=athlete_id,
            activity_id=activity_id,
            message_type=MessageType.POST_WORKOUT,
        )
        if existing is not None:
            return existing

        twin_state = await self._twin_states.get_latest(athlete_id)
        if twin_state is None:
            raise PostWorkoutLLMUnavailableError(
                "twin state not available; athlete must complete onboarding "
                "before post-workout message generation"
            )

        planned_session: Optional[PlannedSession] = None
        if activity.planned_session_id is not None:
            planned_session = await self._planned_sessions.get_by_id(
                activity.planned_session_id
            )
        compliance: ComplianceFindings = self._compliance_service.evaluate(
            activity=activity,
            planned_session=planned_session,
        )

        context = self._build_context(
            activity=activity,
            planned_session=planned_session,
            compliance=compliance,
            twin_state=twin_state,
        )
        context_dict = context.to_dict()

        try:
            prompt = self._prompt_registry.get_prompt(
                self.PROMPT_NAME, self.PROMPT_VERSION
            )
        except PromptNotFoundError as exc:
            await self._write_failure_event(
                athlete_id=athlete_id,
                input_tokens=0,
                latency_ms=0,
                failure_reason="prompt_not_found",
            )
            raise PostWorkoutLLMUnavailableError(
                "post-workout prompt not deployed"
            ) from exc

        llm_client = AsyncOpenAI(
            base_url=settings.LITELLM_BASE_URL,
            api_key=settings.LITELLM_API_KEY,
        )
        start_time = datetime.now(timezone.utc)
        messages: List[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=prompt),
            ChatCompletionUserMessageParam(
                role="user", content=json.dumps(context_dict)
            ),
        ]
        input_tokens = self._estimate_tokens(messages)

        try:
            response = await llm_client.chat.completions.create(
                model=settings.LLM_MODEL or "cohere/command-a-plus",
                messages=messages,
                max_tokens=900,
            )
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            usage = response.usage
            output_tokens = usage.total_tokens or 0 if usage else 0
            content = (response.choices[0].message.content or "").strip()
            self._validate_three_paragraphs(content)

            await self._generation_events.insert(
                GenerationEvent(
                    athlete_id=athlete_id,
                    agent_name=self.AGENT_NAME,
                    prompt_version=self.PROMPT_VERSION,
                    trigger_context=f"activity_id:{activity_id}",
                    input_token_count=input_tokens,
                    output_token_count=output_tokens,
                    latency_ms=latency_ms,
                    success=True,
                    failure_reason=None,
                )
            )

            coaching_message = CoachingMessage(
                athlete_id=athlete_id,
                twin_state_id=twin_state.id,
                activity_id=activity_id,
                message_type=MessageType.POST_WORKOUT,
                content=content,
                prompt_version=self.PROMPT_VERSION,
            )
            await self._coaching_messages.insert(coaching_message)

            await self._events.publish(
                event_type="coaching_message_generated",
                athlete_id=athlete_id,
                payload={
                    "message_id": str(coaching_message.id),
                    "message_type": "post_workout",
                    "activity_id": str(activity_id),
                    "prompt_version": self.PROMPT_VERSION,
                },
            )

            log_event(
                event="coaching_message.generated",
                athlete_id=str(athlete_id),
                message_type="post_workout",
                prompt_version=self.PROMPT_VERSION,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                outcome="success",
            )

            return coaching_message

        except (APITimeoutError, APIConnectionError) as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            failure_reason = (
                "timeout" if isinstance(exc, APITimeoutError) else "proxy_unavailable"
            )
            await self._write_failure_event(
                athlete_id=athlete_id,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason=failure_reason,
            )
            raise PostWorkoutLLMUnavailableError(
                f"LLM call failed: {failure_reason}"
            ) from exc

        except APIStatusError as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            failure_reason = "rate_limit" if exc.status_code == 429 else "api_error"
            await self._write_failure_event(
                athlete_id=athlete_id,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason=failure_reason,
            )
            raise PostWorkoutLLMUnavailableError(
                f"LLM API error: {exc.message or 'unknown'}"
            ) from exc

        except PostWorkoutContractError:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            await self._write_failure_event(
                athlete_id=athlete_id,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason="invalid_output_format",
            )
            raise PostWorkoutLLMUnavailableError(
                "post-workout response format invalid"
            )

    def _build_context(
        self,
        *,
        activity: Activity,
        planned_session: Optional[PlannedSession],
        compliance: ComplianceFindings,
        twin_state: TwinState,
    ) -> PostWorkoutContext:
        prescribed: Optional[Dict[str, Any]] = None
        if planned_session is not None:
            prescribed = {
                "session_type": planned_session.session_type.value,
                "phase_label": planned_session.phase_label.value,
                "week_number": planned_session.week_number,
                "intent_description": planned_session.intent_description,
                "approximate_duration_minutes": (
                    planned_session.approximate_duration_minutes
                ),
            }

        readiness = {
            "recovery_modifier_level": twin_state.readiness_level.value,
            "recovery_modifier_reason": None,
            "confidence_level": twin_state.confidence_level.value,
            "readiness_descriptor": (
                "ready for full training load"
                if twin_state.readiness_level.value == "green"
                else "navigating a partially recovered state"
                if twin_state.readiness_level.value == "amber"
                else "in a recovery window"
            ),
            "phase_position": format_phase_position(planned_session, twin_state),
        }

        load_scores = {
            "aerobic_load": activity.aerobic_load,
            "neuromuscular_load": activity.neuromuscular_load,
            "structural_load": activity.structural_load,
            "load_descriptor": describe_load(activity.aerobic_load),
        }

        return PostWorkoutContext(
            prescribed=prescribed,
            compliance=compliance.to_dict(),
            execution=None,
            comparable_session=None,
            objective_updates=[],
            readiness=readiness,
            load_scores=load_scores,
        )

    async def _write_failure_event(
        self,
        *,
        athlete_id: uuid.UUID,
        input_tokens: int,
        latency_ms: int,
        failure_reason: str,
    ) -> None:
        await self._generation_events.insert(
            GenerationEvent(
                athlete_id=athlete_id,
                agent_name=self.AGENT_NAME,
                prompt_version=self.PROMPT_VERSION,
                trigger_context="post_workout_generate",
                input_token_count=input_tokens,
                output_token_count=0,
                latency_ms=latency_ms,
                success=False,
                failure_reason=failure_reason,
            )
        )
        log_event(
            event="coaching_message.generation.failed",
            athlete_id=str(athlete_id),
            message_type="post_workout",
            prompt_version=self.PROMPT_VERSION,
            failure_reason=failure_reason,
            outcome="failed",
        )

    @staticmethod
    def _validate_three_paragraphs(content: str) -> None:
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) != 3:
            raise PostWorkoutContractError(
                f"expected 3 paragraphs, got {len(paragraphs)}"
            )

    @staticmethod
    def _estimate_tokens(messages: List[ChatCompletionMessageParam]) -> int:
        joined = json.dumps(messages, default=str)
        return (len(joined) + 3) // 4

def _build_default_publisher(session: AsyncSession) -> EventPublisher:
    from app.repositories.system_event_outbox_repository import (
        SystemEventOutboxRepository,
    )
    from app.repositories.system_event_repository import SystemEventRepository
    from app.services.event_publisher import EventPublisher

    return EventPublisher(
        SystemEventRepository(session),
        SystemEventOutboxRepository(session),
    )
