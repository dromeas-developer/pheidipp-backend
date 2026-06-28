"""Unit tests for ``FirstMessageAgent``.

Tests the core agent logic without database or LLM calls:
- Pre-condition check (no existing first message)
- Idempotency (second call raises FirstMessageAlreadyExistsError)
- Success path (writes GenerationEvent + CoachingMessage)
- Failure path (writes GenerationEvent with success=false, no CoachingMessage)
- Paragraph validation (exactly 4 paragraphs)
- Token count capture on both success and failure

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    DataTier,
    GoalType,
    MessageType,
    RecoveryModifierLevel,
    SportBackground,
    TwinConfidenceLevel,
)
from app.models.generation_event import GenerationEvent
from app.models.twin_state import TwinState
from app.repositories.coaching_message_repository import CoachingMessageRepository
from app.repositories.generation_event_repository import GenerationEventRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.context_budget_service import (
    ContextBudgetService,
    FirstMessageContext,
    GoalSummary,
    PlanOverview,
    ProfileSummary,
)
from app.services.first_message_agent import (
    FirstMessageAgent,
    FirstMessageAlreadyExistsError,
    LLMServiceUnavailableError,
    ParagraphCountViolationError,
)
from app.core.prompt_registry import PromptRegistry


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_coaching_messages_repo() -> AsyncMock:
    return AsyncMock(spec=CoachingMessageRepository)


@pytest.fixture
def mock_generation_events_repo() -> AsyncMock:
    return AsyncMock(spec=GenerationEventRepository)


@pytest.fixture
def mock_context_budget() -> AsyncMock:
    return AsyncMock(spec=ContextBudgetService)


@pytest.fixture
def mock_prompt_registry() -> AsyncMock:
    return AsyncMock(spec=PromptRegistry)


@pytest.fixture
def mock_events_publisher() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_training_goals_repo() -> AsyncMock:
    return AsyncMock(spec=TrainingGoalRepository)


@pytest.fixture
def mock_plans_repo() -> AsyncMock:
    return AsyncMock(spec=TrainingPlanRepository)


@pytest.fixture
def mock_twin_states_repo() -> AsyncMock:
    return AsyncMock(spec=TwinStateRepository)


@pytest.fixture
def athlete_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def twin_state_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_twin_state(twin_state_id: uuid.UUID) -> MagicMock:
    ts = MagicMock(spec=TwinState)
    ts.id = twin_state_id
    ts.readiness_level = RecoveryModifierLevel.GREEN
    ts.confidence_level = TwinConfidenceLevel.LOW
    ts.form = 0.0
    ts.data_tier = DataTier.TIER_5
    return ts


@pytest.fixture
def first_message_context() -> FirstMessageContext:
    return FirstMessageContext(
        profile_summary=ProfileSummary(
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=3,
            fitness_level=3,
            recent_injury=None,
        ),
        goal_summary=GoalSummary(
            goal_type=GoalType.RACE_EVENT,
            goal_event_type="5K",
            goal_event_date="2026-09-01",
            weeks_to_event=10,
            goal_description="Run a 5K race",
        ),
        readiness_level="green",
        confidence_level="low",
        fitness_form_descriptor="ready to build",
        data_tier=5,
        computed_observations={
            "aerobic_base_assessment": "limited running history",
            "structural_risk_flag": False,
            "structural_risk_reason": None,
            "training_consistency_signal": "3 year(s) of structured training on record",
        },
        plan_overview=PlanOverview(
            phases=[
                {"label": "Base", "weeks": 4, "primary_focus": "aerobic base"},
                {"label": "Build", "weeks": 4, "primary_focus": "threshold work"},
            ],
            total_weeks=8,
        ),
        first_block_preview=MagicMock(
            session_types_in_week_1=["easy run", "long run"],
            session_types_in_week_2=["interval", "easy run"],
            primary_focus="building aerobic base",
        ),
    )


def _agent(
    mock_session: MagicMock,
    mock_coaching_messages_repo: AsyncMock,
    mock_generation_events_repo: AsyncMock,
    mock_context_budget: AsyncMock,
    mock_prompt_registry: AsyncMock,
    mock_training_goals_repo: AsyncMock,
    mock_plans_repo: AsyncMock,
    mock_twin_states_repo: AsyncMock,
    mock_events_publisher: AsyncMock | None = None,
) -> FirstMessageAgent:
    return FirstMessageAgent(
        session=mock_session,
        coaching_messages=mock_coaching_messages_repo,
        generation_events=mock_generation_events_repo,
        context_budget=mock_context_budget,
        prompt_registry=mock_prompt_registry,
        training_goals=mock_training_goals_repo,
        plans=mock_plans_repo,
        twin_states=mock_twin_states_repo,
        events=mock_events_publisher,
    )


# ---------------------------------------------------------------------------
# Pre-condition: existing first message.
# ---------------------------------------------------------------------------


class TestFirstMessageAgentPrecondition:
    """The agent must check for an existing first_message before
    calling the LLM. Duplicate calls raise FirstMessageAlreadyExistsError."""

    @pytest.mark.asyncio
    async def test_raises_when_first_message_already_exists(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        existing_id = uuid.uuid4()
        mock_coaching_messages_repo.get_existing_first_message.return_value = (
            MagicMock(id=existing_id)
        )

        agent = _agent(
            mock_session,
            mock_coaching_messages_repo,
            mock_generation_events_repo,
            mock_context_budget,
            mock_prompt_registry,
            mock_training_goals_repo,
            mock_plans_repo,
            mock_events_publisher,
        )

        with pytest.raises(FirstMessageAlreadyExistsError) as exc_info:
            await agent.generate(athlete_id)

        assert exc_info.value.existing_message_id == existing_id
        mock_context_budget.build_first_message_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_when_no_existing_first_message(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )

        # Configure insert to return the argument passed so model_validate()
        # receives a real object with valid attribute values.
        async def _return_insert_arg(msg, /):
            msg.id = uuid.uuid4()
            msg.generated_at = datetime.now(timezone.utc)
            msg.twin_state_id = uuid.uuid4()
            return msg
        mock_coaching_messages_repo.insert.side_effect = _return_insert_arg

        # Mock LLM call
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=100)
        mock_llm_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="Para one.\n\nPara two.\n\nPara three.\n\nPara four."
                )
            )
        ]

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            # Patch TwinState fetch
            mock_context_budget._twin_states = AsyncMock()
            mock_context_budget._twin_states.get_latest.return_value = MagicMock(
                id=uuid.uuid4()
            )

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            await agent.generate(athlete_id)

        mock_context_budget.build_first_message_context.assert_called_once_with(
            athlete_id
        )


# ---------------------------------------------------------------------------
# Paragraph validation.
# ---------------------------------------------------------------------------


class TestParagraphValidation:
    """The generated message must contain exactly four paragraphs."""

    def test_raises_on_fewer_than_four_paragraphs(self) -> None:
        content = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        with pytest.raises(ParagraphCountViolationError):
            FirstMessageAgent._validate_paragraph_count(content)

    def test_raises_on_more_than_four_paragraphs(self) -> None:
        content = (
            "Paragraph one.\n\n"
            "Paragraph two.\n\n"
            "Paragraph three.\n\n"
            "Paragraph four.\n\n"
            "Paragraph five."
        )
        with pytest.raises(ParagraphCountViolationError):
            FirstMessageAgent._validate_paragraph_count(content)

    def test_passes_on_exactly_four_paragraphs(self) -> None:
        content = (
            "Paragraph one.\n\n"
            "Paragraph two.\n\n"
            "Paragraph three.\n\n"
            "Paragraph four."
        )
        # Should NOT raise.
        FirstMessageAgent._validate_paragraph_count(content)

    def test_strips_empty_paragraphs(self) -> None:
        content = "Para one.\n\n\n\nPara two.\n\n   \n\nPara three.\n\nPara four."
        # Should NOT raise — empty/whitespace-only paragraphs are ignored.
        FirstMessageAgent._validate_paragraph_count(content)


# ---------------------------------------------------------------------------
# Success path — writes GenerationEvent and CoachingMessage.
# ---------------------------------------------------------------------------


class TestFirstMessageAgentSuccessPath:
    @pytest.mark.asyncio
    async def test_writes_generation_event_on_success(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        twin_state_id = uuid.uuid4()
        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=twin_state_id
        )

        # Configure insert to return the CoachingMessage argument that was passed
        # to it. This ensures model_validate() receives a real object with valid
        # attribute values (id, generated_at, twin_state_id) rather than a mock.
        async def _return_insert_arg(msg, /):
            msg.id = uuid.uuid4()
            msg.generated_at = datetime.now(timezone.utc)
            msg.twin_state_id = uuid.uuid4()
            return msg
        mock_coaching_messages_repo.insert.side_effect = _return_insert_arg

        four_para_content = (
            "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        )
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=150)
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content=four_para_content))
        ]

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            result = await agent.generate(athlete_id)

        assert result.message_type == "first_message"
        mock_generation_events_repo.insert.assert_called_once()
        call_args = mock_generation_events_repo.insert.call_args
        gen_event: GenerationEvent = call_args[0][0]
        assert gen_event.success is True
        assert gen_event.failure_reason is None
        assert gen_event.athlete_id == athlete_id
        assert gen_event.agent_name == "FirstMessageAgent"

    @pytest.mark.asyncio
    async def test_writes_coaching_message_on_success(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        twin_state_id = uuid.uuid4()
        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=twin_state_id
        )

        # Configure insert to return the CoachingMessage argument that was passed
        # to it. This ensures model_validate() receives a real object with valid
        # attribute values (id, generated_at, twin_state_id) rather than a mock.
        async def _return_insert_arg(msg, /):
            msg.id = uuid.uuid4()
            msg.generated_at = datetime.now(timezone.utc)
            msg.twin_state_id = uuid.uuid4()
            return msg
        mock_coaching_messages_repo.insert.side_effect = _return_insert_arg

        four_para_content = (
            "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        )
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=150)
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content=four_para_content))
        ]

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            await agent.generate(athlete_id)

        mock_coaching_messages_repo.insert.assert_called_once()
        call_args = mock_coaching_messages_repo.insert.call_args
        msg: CoachingMessage = call_args[0][0]
        assert msg.message_type == MessageType.FIRST_MESSAGE

    @pytest.mark.asyncio
    async def test_publishes_event_on_success(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        twin_state_id = uuid.uuid4()
        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=twin_state_id
        )

        # Configure insert to return the CoachingMessage argument that was passed
        # to it. This ensures model_validate() receives a real object with valid
        # attribute values (id, generated_at, twin_state_id) rather than a mock.
        async def _return_insert_arg(msg, /):
            msg.id = uuid.uuid4()
            msg.generated_at = datetime.now(timezone.utc)
            msg.twin_state_id = uuid.uuid4()
            return msg
        mock_coaching_messages_repo.insert.side_effect = _return_insert_arg

        four_para_content = (
            "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        )
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=150)
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content=four_para_content))
        ]

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            await agent.generate(athlete_id)

        mock_events_publisher.publish.assert_called_once()
        call_kwargs = mock_events_publisher.publish.call_args
        assert call_kwargs[1]["event_type"] == "coaching_message_generated"


# ---------------------------------------------------------------------------
# Failure path — writes GenerationEvent with success=false.
# ---------------------------------------------------------------------------


class TestFirstMessageAgentFailurePath:
    @pytest.mark.asyncio
    async def test_writes_generation_event_on_llm_timeout(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        from openai import APITimeoutError

        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=uuid.uuid4()
        )

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError("timeout")
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            with pytest.raises(LLMServiceUnavailableError):
                await agent.generate(athlete_id)

        # GenerationEvent written with success=False
        mock_generation_events_repo.insert.assert_called_once()
        gen_event: GenerationEvent = (
            mock_generation_events_repo.insert.call_args[0][0]
        )
        assert gen_event.success is False
        assert gen_event.failure_reason == "timeout"
        # No CoachingMessage created
        mock_coaching_messages_repo.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_writes_generation_event_on_proxy_unavailable(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        from openai import APIConnectionError

        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=uuid.uuid4()
        )

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIConnectionError(message="connection failed", request=MagicMock())
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            with pytest.raises(LLMServiceUnavailableError):
                await agent.generate(athlete_id)

        gen_event: GenerationEvent = (
            mock_generation_events_repo.insert.call_args[0][0]
        )
        assert gen_event.success is False
        assert gen_event.failure_reason == "proxy_unavailable"

    @pytest.mark.asyncio
    async def test_writes_generation_event_on_rate_limit(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        from openai import APIStatusError

        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=uuid.uuid4()
        )

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APIStatusError(
                    "rate limited", response=MagicMock(status_code=429), body=None
                )
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            with pytest.raises(LLMServiceUnavailableError):
                await agent.generate(athlete_id)

        gen_event: GenerationEvent = (
            mock_generation_events_repo.insert.call_args[0][0]
        )
        assert gen_event.success is False
        assert gen_event.failure_reason == "rate_limit"

    @pytest.mark.asyncio
    async def test_writes_generation_event_on_paragraph_violation(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=uuid.uuid4()
        )

        # Return only 3 paragraphs — should trigger ParagraphCountViolationError
        three_para_content = "Para one.\n\nPara two.\n\nPara three."
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=100)
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content=three_para_content))
        ]

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            with pytest.raises(LLMServiceUnavailableError):
                await agent.generate(athlete_id)

        gen_event: GenerationEvent = (
            mock_generation_events_repo.insert.call_args[0][0]
        )
        assert gen_event.success is False
        assert gen_event.failure_reason == "invalid_output_format"


# ---------------------------------------------------------------------------
# Token count capture.
# ---------------------------------------------------------------------------


class TestFirstMessageAgentTokenCapture:
    @pytest.mark.asyncio
    async def test_captures_input_and_output_tokens_on_success(
        self,
        athlete_id: uuid.UUID,
        mock_session: MagicMock,
        mock_coaching_messages_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_training_goals_repo: AsyncMock,
        mock_plans_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
    ) -> None:
        mock_coaching_messages_repo.get_existing_first_message.return_value = None
        mock_training_goals_repo.get_active.return_value = MagicMock()
        mock_plans_repo.get_active_for_athlete.return_value = MagicMock()
        mock_context_budget.build_first_message_context.return_value = MagicMock(
            to_dict=MagicMock(return_value={})
        )
        mock_prompt_registry.get_prompt.return_value = "You are the coach."
        mock_context_budget.estimate_tokens.return_value = 500

        twin_state_id = uuid.uuid4()
        mock_context_budget._twin_states = AsyncMock()
        mock_context_budget._twin_states.get_latest.return_value = MagicMock(
            id=twin_state_id
        )

        # Configure insert to return the CoachingMessage argument that was passed
        # to it. This ensures model_validate() receives a real object with valid
        # attribute values (id, generated_at, twin_state_id) rather than a mock.
        async def _return_insert_arg(msg, /):
            msg.id = uuid.uuid4()
            msg.generated_at = datetime.now(timezone.utc)
            msg.twin_state_id = uuid.uuid4()
            return msg
        mock_coaching_messages_repo.insert.side_effect = _return_insert_arg

        four_para_content = (
            "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        )
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=250)
        mock_llm_response.choices = [
            MagicMock(message=MagicMock(content=four_para_content))
        ]

        with patch.object(FirstMessageAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_coaching_messages_repo,
                mock_generation_events_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_training_goals_repo,
                mock_plans_repo,
                mock_twin_states_repo,
                mock_events_publisher,
            )

            await agent.generate(athlete_id)

        gen_event: GenerationEvent = (
            mock_generation_events_repo.insert.call_args[0][0]
        )
        assert gen_event.input_token_count == 500
        assert gen_event.output_token_count == 250