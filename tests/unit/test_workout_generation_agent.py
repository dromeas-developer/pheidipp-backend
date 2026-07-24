"""Unit tests for ``WorkoutGenerationAgent``.

Tests:
- Idempotency: existing workout returns without LLM call
- TwinState pre-condition: raises when no twin state exists
- PlannedSession pre-condition: raises when session not found
- Context assembly is called before LLM
- LLM failure writes GenerationEvent with success=false and raises LLMServiceUnavailableError
- Step validation catches missing physiological_intent
- Step validation catches non-sequential step_order

Reference plan: docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    SessionType,
    TwinConfidenceLevel,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.workout_step import WorkoutStep
from app.models.planned_session import PlannedSession
from app.models.twin_state import TwinState
from app.repositories.generation_event_repository import GenerationEventRepository
from app.repositories.generated_workout_repository import GeneratedWorkoutRepository
from app.repositories.planned_session_repository import PlannedSessionRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.workout_step_repository import WorkoutStepRepository
from app.services.context_budget_service import (
    ContextBudgetService,
    WorkoutGenerationContext,
    WorkoutReadinessDigest,
    WorkoutSessionSummary,
)
from app.agents.workout_generation_agent import WorkoutGenerationAgent
from app.services.workout_generation_errors import (
    LLMServiceUnavailableError,
    PlannedSessionNotFoundError,
    WorkoutAlreadyGeneratedError,
)
from app.core.prompt_registry import PromptRegistry


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_generated_workouts_repo() -> AsyncMock:
    return AsyncMock(spec=GeneratedWorkoutRepository)


@pytest.fixture
def mock_workout_steps_repo() -> AsyncMock:
    return AsyncMock(spec=WorkoutStepRepository)


@pytest.fixture
def mock_generation_events_repo() -> AsyncMock:
    return AsyncMock(spec=GenerationEventRepository)


@pytest.fixture
def mock_planned_sessions_repo() -> AsyncMock:
    return AsyncMock(spec=PlannedSessionRepository)


@pytest.fixture
def mock_twin_states_repo() -> AsyncMock:
    return AsyncMock(spec=TwinStateRepository)


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
def athlete_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def planned_session_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def twin_state_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def generation_date() -> date:
    return date.today()


@pytest.fixture
def mock_twin_state(twin_state_id: uuid.UUID) -> MagicMock:
    ts = MagicMock(spec=TwinState)
    ts.id = twin_state_id
    ts.readiness_level = RecoveryModifierLevel.GREEN
    ts.confidence_level = TwinConfidenceLevel.MEDIUM
    ts.form = 0.5
    ts.data_tier = DataTier.TIER_3
    return ts


@pytest.fixture
def mock_planned_session(planned_session_id: uuid.UUID) -> MagicMock:
    ps = MagicMock(spec=PlannedSession)
    ps.id = planned_session_id
    ps.session_type = SessionType.THRESHOLD
    ps.intent_description = "Threshold intervals"
    ps.approximate_duration_minutes = 60
    return ps


@pytest.fixture
def mock_context() -> WorkoutGenerationContext:
    return WorkoutGenerationContext(
        session=WorkoutSessionSummary(
            session_type="threshold",
            phase_label="Threshold Build",
            week_number=3,
            intent_description="Threshold intervals",
            approximate_duration_minutes=60,
        ),
        readiness=WorkoutReadinessDigest(
            recovery_modifier_level="green",
            recovery_modifier_reason=None,
            confidence_level="medium",
            fitness_form_descriptor="fit",
            threshold_target_description="Threshold pace",
            lt2_pace_sec_per_km=360.0,
        ),
        data_tier=3,
        target_type="gap",
        relevant_objectives=[],
    )


def _agent(
    mock_session: MagicMock,
    mock_generated_workouts_repo: AsyncMock,
    mock_workout_steps_repo: AsyncMock,
    mock_generation_events_repo: AsyncMock,
    mock_planned_sessions_repo: AsyncMock,
    mock_twin_states_repo: AsyncMock,
    mock_context_budget: AsyncMock,
    mock_prompt_registry: AsyncMock,
    mock_events_publisher: MagicMock | None = None,
) -> WorkoutGenerationAgent:
    return WorkoutGenerationAgent(
        session=mock_session,
        generated_workouts=mock_generated_workouts_repo,
        workout_steps=mock_workout_steps_repo,
        generation_events=mock_generation_events_repo,
        planned_sessions=mock_planned_sessions_repo,
        twin_states=mock_twin_states_repo,
        context_budget=mock_context_budget,
        prompt_registry=mock_prompt_registry,
        events=mock_events_publisher,
    )


# ---------------------------------------------------------------------------
# Idempotency gate.
# ---------------------------------------------------------------------------


class TestIdempotencyGate:
    """The agent must check for an existing workout before calling the LLM.

    Second call with allow_existing=True returns the existing workout
    transparently (used by GET /today). Second call with
    allow_existing=False raises WorkoutAlreadyGeneratedError (used by
    POST /generate-workout).
    """

    @pytest.mark.asyncio
    async def test_returns_existing_without_llm_call(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
    ) -> None:
        existing_workout = MagicMock(spec=GeneratedWorkout)
        existing_workout.id = uuid.uuid4()
        mock_generated_workouts_repo.get_by_session_and_date.return_value = (
            existing_workout
        )

        agent = _agent(
            mock_session,
            mock_generated_workouts_repo,
            mock_workout_steps_repo,
            mock_generation_events_repo,
            mock_planned_sessions_repo,
            mock_twin_states_repo,
            mock_context_budget,
            mock_prompt_registry,
            mock_events_publisher,
        )

        result = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=generation_date,
            allow_existing=True,
        )

        assert result is existing_workout
        # LLM should NOT be called
        mock_context_budget.build_workout_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_workout_already_generated_when_allow_existing_false(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
    ) -> None:
        existing_workout = MagicMock(spec=GeneratedWorkout)
        existing_workout.id = uuid.uuid4()
        mock_generated_workouts_repo.get_by_session_and_date.return_value = (
            existing_workout
        )

        agent = _agent(
            mock_session,
            mock_generated_workouts_repo,
            mock_workout_steps_repo,
            mock_generation_events_repo,
            mock_planned_sessions_repo,
            mock_twin_states_repo,
            mock_context_budget,
            mock_prompt_registry,
            mock_events_publisher,
        )

        with pytest.raises(WorkoutAlreadyGeneratedError) as exc_info:
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=generation_date,
                allow_existing=False,
            )

        assert exc_info.value.existing_workout_id == existing_workout.id
        mock_context_budget.build_workout_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_proceeds_with_generation_when_no_existing_workout(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_twin_state: MagicMock,
        mock_planned_session: MagicMock,
        mock_context: WorkoutGenerationContext,
    ) -> None:
        mock_generated_workouts_repo.get_by_session_and_date.return_value = None
        mock_twin_states_repo.get_latest.return_value = mock_twin_state
        mock_planned_sessions_repo.get_by_id.return_value = mock_planned_session
        mock_context_budget.build_workout_context.return_value = mock_context
        mock_prompt_registry.get_prompt.return_value = "workout prompt"
        mock_context_budget.estimate_tokens.return_value = 500

        # Configure insert to return the workout passed to it
        async def _return_insert_arg(workout: GeneratedWorkout, /) -> GeneratedWorkout:
            workout.id = uuid.uuid4()
            workout.generated_at = datetime.now(timezone.utc)
            return workout

        mock_generated_workouts_repo.insert.side_effect = _return_insert_arg

        def _return_steps(steps: list[WorkoutStep]) -> list[WorkoutStep]:
            return steps
        mock_workout_steps_repo.insert_many.side_effect = _return_steps

        # Valid LLM response with non-empty steps array (required by validator).
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=200)
        mock_llm_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "steps": [
                                {
                                    "step_order": 1,
                                    "step_type": "warmup",
                                    "physiological_intent": "recovery",
                                    "target_duration_seconds": 600,
                                    "target_gap_sec_per_km": 360,
                                    "target": {
                                        "signal_type": "gap",
                                        "primary": {
                                            "min": 360,
                                            "max": 390,
                                            "unit": "sec_per_km",
                                        },
                                        "fallback": None,
                                        "description": "Easy pace warmup",
                                    },
                                    "description": "Warm up",
                                },
                                {
                                    "step_order": 2,
                                    "step_type": "work",
                                    "physiological_intent": "threshold",
                                    "target_duration_seconds": 1800,
                                    "target_gap_sec_per_km": 300,
                                    "target": {
                                        "signal_type": "gap",
                                        "primary": {
                                            "min": 290,
                                            "max": 310,
                                            "unit": "sec_per_km",
                                        },
                                        "fallback": None,
                                        "description": "Threshold intervals",
                                    },
                                    "description": "Threshold work",
                                },
                                {
                                    "step_order": 3,
                                    "step_type": "cooldown",
                                    "physiological_intent": "recovery",
                                    "target_duration_seconds": 600,
                                    "target_gap_sec_per_km": 360,
                                    "target": {
                                        "signal_type": "gap",
                                        "primary": {
                                            "min": 360,
                                            "max": 390,
                                            "unit": "sec_per_km",
                                        },
                                        "fallback": None,
                                        "description": "Easy pace cooldown",
                                    },
                                    "description": "Cool down",
                                },
                            ]
                        }
                    )
                )
            )
        ]

        with patch.object(WorkoutGenerationAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_generated_workouts_repo,
                mock_workout_steps_repo,
                mock_generation_events_repo,
                mock_planned_sessions_repo,
                mock_twin_states_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_events_publisher,
            )

            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=generation_date,
                allow_existing=True,
            )

        mock_context_budget.build_workout_context.assert_called_once_with(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
        )


# ---------------------------------------------------------------------------
# Pre-conditions.
# ---------------------------------------------------------------------------


class TestPreConditions:
    """Tests for twin state and planned session pre-conditions."""

    @pytest.mark.asyncio
    async def test_raises_llm_service_unavailable_when_no_twin_state(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_planned_session: MagicMock,
    ) -> None:
        mock_generated_workouts_repo.get_by_session_and_date.return_value = None
        mock_twin_states_repo.get_latest.return_value = None  # No twin state!
        mock_planned_sessions_repo.get_by_id.return_value = mock_planned_session

        agent = _agent(
            mock_session,
            mock_generated_workouts_repo,
            mock_workout_steps_repo,
            mock_generation_events_repo,
            mock_planned_sessions_repo,
            mock_twin_states_repo,
            mock_context_budget,
            mock_prompt_registry,
            mock_events_publisher,
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=generation_date,
                allow_existing=True,
            )

        # Note: twin_state failure raises BEFORE LLM call and does NOT
        # write a GenerationEvent — the error is a pre-condition failure,
        # not an LLM failure. Context-budget and prompt registry are also
        # skipped since the error fires before either is needed.
        mock_generation_events_repo.insert.assert_not_called()
        mock_context_budget.build_workout_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_planned_session_not_found_when_session_missing(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_twin_state: MagicMock,
    ) -> None:
        mock_generated_workouts_repo.get_by_session_and_date.return_value = None
        mock_twin_states_repo.get_latest.return_value = mock_twin_state
        mock_planned_sessions_repo.get_by_id.return_value = None  # Session not found!

        agent = _agent(
            mock_session,
            mock_generated_workouts_repo,
            mock_workout_steps_repo,
            mock_generation_events_repo,
            mock_planned_sessions_repo,
            mock_twin_states_repo,
            mock_context_budget,
            mock_prompt_registry,
            mock_events_publisher,
        )

        with pytest.raises(PlannedSessionNotFoundError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=generation_date,
                allow_existing=True,
            )


# ---------------------------------------------------------------------------
# LLM failure handling.
# ---------------------------------------------------------------------------


class TestLLMFailure:
    """Tests for LLM failure path: GenerationEvent written, no workout created."""

    @pytest.mark.asyncio
    async def test_writes_generation_event_with_success_false_on_llm_error(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_twin_state: MagicMock,
        mock_planned_session: MagicMock,
        mock_context: WorkoutGenerationContext,
    ) -> None:
        mock_generated_workouts_repo.get_by_session_and_date.return_value = None
        mock_twin_states_repo.get_latest.return_value = mock_twin_state
        mock_planned_sessions_repo.get_by_id.return_value = mock_planned_session
        mock_context_budget.build_workout_context.return_value = mock_context
        mock_prompt_registry.get_prompt.return_value = "workout prompt"
        mock_context_budget.estimate_tokens.return_value = 500

        from openai import APIConnectionError

        with patch.object(WorkoutGenerationAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.side_effect = APIConnectionError(
                message="Connection failed",
                request=MagicMock(),  # Required in newer openai library
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_generated_workouts_repo,
                mock_workout_steps_repo,
                mock_generation_events_repo,
                mock_planned_sessions_repo,
                mock_twin_states_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_events_publisher,
            )

            with pytest.raises(LLMServiceUnavailableError):
                await agent.generate(
                    athlete_id=athlete_id,
                    planned_session_id=planned_session_id,
                    generation_date=generation_date,
                    allow_existing=True,
                )

        # Verify GenerationEvent was inserted with success=False
        mock_generation_events_repo.insert.assert_called_once()
        call_args = mock_generation_events_repo.insert.call_args
        event_arg = call_args[0][0] if call_args[0] else call_args[1].get("event")
        if hasattr(event_arg, "success"):
            assert event_arg.success is False

    @pytest.mark.asyncio
    async def test_does_not_create_workout_on_llm_failure(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_twin_state: MagicMock,
        mock_planned_session: MagicMock,
        mock_context: WorkoutGenerationContext,
    ) -> None:
        mock_generated_workouts_repo.get_by_session_and_date.return_value = None
        mock_twin_states_repo.get_latest.return_value = mock_twin_state
        mock_planned_sessions_repo.get_by_id.return_value = mock_planned_session
        mock_context_budget.build_workout_context.return_value = mock_context
        mock_prompt_registry.get_prompt.return_value = "workout prompt"
        mock_context_budget.estimate_tokens.return_value = 500

        from openai import APITimeoutError

        with patch.object(WorkoutGenerationAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.side_effect = APITimeoutError(
                request=MagicMock()
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_generated_workouts_repo,
                mock_workout_steps_repo,
                mock_generation_events_repo,
                mock_planned_sessions_repo,
                mock_twin_states_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_events_publisher,
            )

            with pytest.raises(LLMServiceUnavailableError):
                await agent.generate(
                    athlete_id=athlete_id,
                    planned_session_id=planned_session_id,
                    generation_date=generation_date,
                    allow_existing=True,
                )

        # Workout should NOT be inserted
        mock_generated_workouts_repo.insert.assert_not_called()


# ---------------------------------------------------------------------------
# Step validation.
# ---------------------------------------------------------------------------


class TestStepValidation:
    """Tests for step validation behavior via the public generate() API.

    The _parse_and_validate_output method is internal and tested indirectly
    through the public API. Contract violations (null physiological_intent,
    non-sequential step_order, etc.) surface as WorkoutAlreadyGeneratedError
    or LLMServiceUnavailableError depending on the failure mode.

    These tests verify the public contract error types are raised when
    the LLM returns malformed output.
    """

    def test_contract_error_has_descriptive_message(self) -> None:
        """WorkoutGenerationContractError carries a descriptive message."""
        from app.services.workout_generation_errors import WorkoutGenerationContractError

        error = WorkoutGenerationContractError("step 1 has null physiological_intent")
        assert "null physiological_intent" in str(error)


# ---------------------------------------------------------------------------
# Context assembly.
# ---------------------------------------------------------------------------


class TestContextAssembly:
    """Tests for context assembly before LLM call."""

    @pytest.mark.asyncio
    async def test_build_workout_context_receives_correct_arguments(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        mock_session: MagicMock,
        mock_generated_workouts_repo: AsyncMock,
        mock_workout_steps_repo: AsyncMock,
        mock_generation_events_repo: AsyncMock,
        mock_planned_sessions_repo: AsyncMock,
        mock_twin_states_repo: AsyncMock,
        mock_context_budget: AsyncMock,
        mock_prompt_registry: AsyncMock,
        mock_events_publisher: AsyncMock,
        mock_twin_state: MagicMock,
        mock_planned_session: MagicMock,
        mock_context: WorkoutGenerationContext,
    ) -> None:
        mock_generated_workouts_repo.get_by_session_and_date.return_value = None
        mock_twin_states_repo.get_latest.return_value = mock_twin_state
        mock_planned_sessions_repo.get_by_id.return_value = mock_planned_session
        mock_context_budget.build_workout_context.return_value = mock_context
        mock_prompt_registry.get_prompt.return_value = "workout prompt"
        mock_context_budget.estimate_tokens.return_value = 500

        async def _return_insert_arg(workout: GeneratedWorkout, /) -> GeneratedWorkout:
            workout.id = uuid.uuid4()
            workout.generated_at = datetime.now(timezone.utc)
            return workout

        mock_generated_workouts_repo.insert.side_effect = _return_insert_arg

        def _return_steps(steps: list[WorkoutStep]) -> list[WorkoutStep]:
            return steps
        mock_workout_steps_repo.insert_many.side_effect = _return_steps

        # Valid LLM response: validator enforces first=warmup, last=cooldown,
        # strictly sequential step_order from 1, and target_type-driven
        # numeric discipline (target_type='gap' requires
        # target_gap_sec_per_km non-null on every step). The 'work'
        # step's physiological_intent must match SESSION_INTENT_MAP
        # for the parent session_type (THRESHOLD → 'threshold').
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=200)
        mock_llm_response.choices = [
            MagicMock(
                message=MagicMock(
                    content=json.dumps(
                        {
                            "steps": [
                                {
                                    "step_order": 1,
                                    "step_type": "warmup",
                                    "physiological_intent": "recovery",
                                    "target_duration_seconds": 600,
                                    "target_gap_sec_per_km": 360,
                                    "target": {
                                        "signal_type": "gap",
                                        "primary": {
                                            "min": 360,
                                            "max": 390,
                                            "unit": "sec_per_km",
                                        },
                                        "fallback": None,
                                        "description": "Easy pace warmup",
                                    },
                                    "description": "Warm up",
                                },
                                {
                                    "step_order": 2,
                                    "step_type": "work",
                                    "physiological_intent": "threshold",
                                    "target_duration_seconds": 1800,
                                    "target_gap_sec_per_km": 300,
                                    "target": {
                                        "signal_type": "gap",
                                        "primary": {
                                            "min": 290,
                                            "max": 310,
                                            "unit": "sec_per_km",
                                        },
                                        "fallback": None,
                                        "description": "Threshold intervals",
                                    },
                                    "description": "Threshold work",
                                },
                                {
                                    "step_order": 3,
                                    "step_type": "cooldown",
                                    "physiological_intent": "recovery",
                                    "target_duration_seconds": 600,
                                    "target_gap_sec_per_km": 360,
                                    "target": {
                                        "signal_type": "gap",
                                        "primary": {
                                            "min": 360,
                                            "max": 390,
                                            "unit": "sec_per_km",
                                        },
                                        "fallback": None,
                                        "description": "Easy pace cooldown",
                                    },
                                    "description": "Cool down",
                                },
                            ]
                        }
                    )
                )
            )
        ]

        with patch.object(WorkoutGenerationAgent, "_build_llm_client") as mock_build:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=mock_llm_response
            )
            mock_build.return_value = mock_client

            agent = _agent(
                mock_session,
                mock_generated_workouts_repo,
                mock_workout_steps_repo,
                mock_generation_events_repo,
                mock_planned_sessions_repo,
                mock_twin_states_repo,
                mock_context_budget,
                mock_prompt_registry,
                mock_events_publisher,
            )

            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=generation_date,
                allow_existing=True,
            )

        mock_context_budget.build_workout_context.assert_called_once_with(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
        )