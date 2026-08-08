"""Integration tests for WorkoutGenerationAgent — real DB, mocked LLM proxy.

Covers the agent's interaction with the real PostgreSQL test database
while stubbing the external LLM proxy at the AsyncOpenAI chat.completions
boundary. The agent's internal orchestration, repository calls, and
GenerationEvent writing run real per the mocking-contract rule that
only the external boundary is mocked.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.workout_generation_agent import WorkoutGenerationAgent
from app.core.prompt_registry import PromptRegistry
from app.models.enums import (
    DataTier,
    GoalEventType,
    GoalType,
    PhaseLabel,
    PlannedSessionStatus,
    RecoveryModifierLevel,
    SessionPriority,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
    WeeklyPlanStatus,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.generation_event import GenerationEvent
from app.models.planned_session import PlannedSession
from app.models.system_event import SystemEvent
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from app.models.workout_step import WorkoutStep
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_profile_repository import (
    AthleteProfileRepository,
)
from app.repositories.generated_workout_repository import (
    GeneratedWorkoutRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.planned_session_repository import (
    PlannedSessionRepository,
)
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.workout_step_repository import WorkoutStepRepository
from app.services.context_budget_service import ContextBudgetService
from app.services.workout_generation_errors import (
    LLMServiceUnavailableError,
    PlannedSessionNotFoundError,
    WorkoutAlreadyGeneratedError,
)


def _build_threshold_payload(
    *,
    target_type: str = "gap",
    power: dict[str, int] | None = None,
    gap: dict[str, int] | None = None,
) -> str:
    """Return a 3-step threshold workout JSON payload for the LLM stub."""
    if target_type == "power":
        primary = power or {"min": 280, "max": 320}
        power_field: dict[str, int] | None = primary
        gap_field: dict[str, int] | None = None
    elif target_type == "gap":
        primary = gap or {"min": 240, "max": 250}
        power_field = None
        gap_field = primary
    else:
        power_field = None
        gap_field = None

    steps: list[dict[str, Any]] = [
        {
            "step_order": 1,
            "step_type": "warmup",
            "physiological_intent": "recovery",
            "target_duration_seconds": 600,
            "target_hr_zone": None,
            "target_power_watts": None,
            "target_gap_sec_per_km": None,
            "description": "Easy warmup",
        },
        {
            "step_order": 2,
            "step_type": "work",
            "physiological_intent": "threshold",
            "target_duration_seconds": 300,
            "target_hr_zone": None,
            "target_power_watts": power_field,
            "target_gap_sec_per_km": gap_field,
            "description": "Threshold rep",
        },
        {
            "step_order": 3,
            "step_type": "cooldown",
            "physiological_intent": "recovery",
            "target_duration_seconds": 600,
            "target_hr_zone": None,
            "target_power_watts": None,
            "target_gap_sec_per_km": None,
            "description": "Easy cooldown",
        },
    ]
    return json.dumps({"steps": steps})


def _build_long_run_payload() -> str:
    """Easy-run / long-run style payload with only description targets."""
    steps = [
        {
            "step_order": 1,
            "step_type": "warmup",
            "physiological_intent": "recovery",
            "target_duration_seconds": 600,
            "target_hr_zone": None,
            "target_power_watts": None,
            "target_gap_sec_per_km": None,
            "description": "Easy warmup",
        },
        {
            "step_order": 2,
            "step_type": "work",
            "physiological_intent": "high_aerobic",
            "target_duration_seconds": 1800,
            "target_hr_zone": None,
            "target_power_watts": None,
            "target_gap_sec_per_km": None,
            "description": "Steady aerobic effort",
        },
        {
            "step_order": 3,
            "step_type": "cooldown",
            "physiological_intent": "recovery",
            "target_duration_seconds": 600,
            "target_hr_zone": None,
            "target_power_watts": None,
            "target_gap_sec_per_km": None,
            "description": "Easy cooldown",
        },
    ]
    return json.dumps({"steps": steps})


def _llm_client_returning(content: str) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.total_tokens = 150
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def _llm_client_raising(exc: BaseException) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=exc)
    return client


async def _build_setup_with_planned_session(
    db_session: AsyncSession,
    *,
    session_type: SessionType = SessionType.THRESHOLD,
    data_tier: DataTier = DataTier.TIER_3,
    target_date: date | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create an athlete + goal + plan + twin + planned session.

    Returns (athlete_id, planned_session_id, twin_state_id, workout_id).
    workout_id is None placeholder; populated after generation.
    """
    from app.models.athlete import Athlete

    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email=f"workout-{athlete_id}@example.com",
        onboarding_complete=True,
    )
    db_session.add(athlete)

    goal = TrainingGoal(
        athlete_id=athlete_id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=GoalEventType.MARATHON,
        goal_event_date=date.today() + timedelta(weeks=20),
        goal_event_name="Berlin Marathon",
        weekly_volume_hours=8.0,
        weekly_volume_km=50.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    twin = TwinState(
        athlete_id=athlete_id,
        training_goal_id=goal.id,
        data_tier=data_tier,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1-questionnaire-bootstrap",
        fitness=0.0,
        fatigue=0.0,
        form=0.0,
        readiness_level=RecoveryModifierLevel.GREEN,
    )
    db_session.add(twin)
    await db_session.flush()

    plan = TrainingPlan(
        training_goal_id=goal.id,
        status=TrainingPlanStatus.ACTIVE,
        twin_state_id=twin.id,
    )
    db_session.add(plan)
    await db_session.flush()

    session_date = target_date or date.today()
    wp = WeeklyPlan(
        training_plan_id=plan.id,
        week_number=1,
        adjusted_intent={},
        status=WeeklyPlanStatus.ACTIVE,
        week_starts_at=session_date,
        week_ends_at=session_date,
    )
    db_session.add(wp)
    await db_session.flush()

    planned_session = PlannedSession(
        weekly_plan_id=wp.id,
        training_plan_id=plan.id,
        target_date=session_date,
        week_number=1,
        phase_label=PhaseLabel.THRESHOLD_BUILD,
        session_type=session_type,
        intent_description="Threshold work",
        approximate_duration_minutes=60,
        status=PlannedSessionStatus.SCHEDULED,
        session_priority=SessionPriority.PRIMARY,
    )
    db_session.add(planned_session)
    await db_session.commit()

    return athlete_id, planned_session.id, twin.id, planned_session.id


from datetime import timedelta  # noqa: E402


async def _build_workout_agent(db_session: AsyncSession) -> WorkoutGenerationAgent:
    twin_states = TwinStateRepository(db_session)
    planned_sessions = PlannedSessionRepository(db_session)
    return WorkoutGenerationAgent(
        session=db_session,
        generated_workouts=GeneratedWorkoutRepository(db_session),
        workout_steps=WorkoutStepRepository(db_session),
        generation_events=GenerationEventRepository(db_session),
        planned_sessions=planned_sessions,
        twin_states=twin_states,
        context_budget=ContextBudgetService(
            twin_states=twin_states,
            training_goals=TrainingGoalRepository(db_session),
            plans=TrainingPlanRepository(db_session),
            profiles=AthleteProfileRepository(db_session),
            preferences=AthletePreferencesRepository(db_session),
            planned_sessions=planned_sessions,
        ),
        prompt_registry=PromptRegistry(),
    )


class TestWorkoutGenerationSuccess:
    async def test_workout_generated_successfully(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        result = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        assert result.theoretical_targets is not None
        assert result.adjusted_targets is not None
        assert result.recovery_modifier_level == RecoveryModifierLevel.GREEN
        assert result.recovery_modifier_reason is None

    async def test_workout_step_records_persisted_with_physiological_intent(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        steps = await agent.load_steps(workout.id)
        assert len(steps) == 3
        assert all(s.physiological_intent is not None for s in steps)
        assert steps[0].step_order == 1
        assert steps[1].step_order == 2
        assert steps[2].step_order == 3

    async def test_step_orders_one_indexed_and_unique(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.LONG_RUN,
            data_tier=DataTier.TIER_5,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_long_run_payload()),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        steps = await agent.load_steps(workout.id)
        assert [s.step_order for s in steps] == [1, 2, 3]

    async def test_workout_description_always_non_empty(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        steps = await agent.load_steps(workout.id)
        for s in steps:
            assert isinstance(s.description, str)
            assert len(s.description.strip()) > 0

    async def test_workout_generated_event_in_outbox(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        stmt = select(SystemEvent).where(
            SystemEvent.event_type == "workout_generated",
            SystemEvent.athlete_id == athlete_id,
        )
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].payload["planned_session_id"] == str(planned_session_id)
        assert "generated_workout_id" in events[0].payload

    async def test_generation_event_records_success_with_agent_name(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is True
        assert events[0].agent_name == "WorkoutGenerationAgent"
        assert events[0].failure_reason is None


class TestWorkoutIdempotency:
    async def test_second_generation_returns_existing_when_allow_existing_true(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        client = _llm_client_returning(_build_threshold_payload(target_type="gap"))
        monkeypatch.setattr(agent, "_build_llm_client", lambda: client)

        first = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
            allow_existing=True,
        )
        call_count_after_first = client.chat.completions.create.call_count

        second = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
            allow_existing=True,
        )

        assert first.id == second.id
        assert client.chat.completions.create.call_count == call_count_after_first

    async def test_second_generation_raises_409_when_allow_existing_false(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
            allow_existing=False,
        )

        with pytest.raises(WorkoutAlreadyGeneratedError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=date.today(),
                allow_existing=False,
            )

    async def test_get_by_session_and_date_returns_existing(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        existing = await agent._generated_workouts.get_by_session_and_date(
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        assert existing is not None
        assert existing.id == workout.id

    async def test_second_generation_does_not_create_new_generation_event(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
            allow_existing=True,
        )

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1


class TestWorkoutTargetTypeByDataTier:
    async def test_tier_1_uses_power_target_type(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_1,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="power")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        steps = await agent.load_steps(workout.id)
        work_steps = [s for s in steps if s.step_type.value == "work"]
        assert len(work_steps) == 1
        assert work_steps[0].target["signal_type"] == "power"
        assert work_steps[0].target["primary"] == {"min": 280, "max": 320, "unit": "watts"}

    async def test_tier_3_uses_gap_target_type(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        steps = await agent.load_steps(workout.id)
        work_steps = [s for s in steps if s.step_type.value == "work"]
        assert len(work_steps) == 1
        assert work_steps[0].target["signal_type"] == "gap"
        assert work_steps[0].target["primary"] == {"min": 240, "max": 250, "unit": "sec_per_km"}
        assert work_steps[0].target["primary"]["unit"] == "sec_per_km"

    async def test_tier_5_uses_description_only_target(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.LONG_RUN,
            data_tier=DataTier.TIER_5,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_long_run_payload()),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        steps = await agent.load_steps(workout.id)
        work_steps = [s for s in steps if s.step_type.value == "work"]
        assert len(work_steps) == 1
        assert work_steps[0].target["signal_type"] == "description"
        assert work_steps[0].target["primary"] is None


class TestWorkoutTwoColumnTargetStructure:
    async def test_theoretical_and_adjusted_targets_both_written(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        assert workout.theoretical_targets is not None
        assert workout.adjusted_targets is not None
        assert workout.theoretical_targets == workout.adjusted_targets

    async def test_recovery_modifier_defaults_to_green(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        assert workout.recovery_modifier_level == RecoveryModifierLevel.GREEN
        assert workout.recovery_modifier_reason is None

    async def test_twin_state_id_records_generation_version(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, twin_id, _ = (
            await _build_setup_with_planned_session(
                db_session,
                session_type=SessionType.THRESHOLD,
                data_tier=DataTier.TIER_3,
            )
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )
        assert workout.twin_state_id == twin_id


class TestWorkoutLLMFailure:
    async def test_timeout_writes_generation_event_with_failure_reason(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_raising(APITimeoutError(request=MagicMock())),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=date.today(),
            )

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "timeout"
        assert events[0].agent_name == "WorkoutGenerationAgent"

    async def test_api_connection_error_writes_failure_reason_proxy_unavailable(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_raising(APIConnectionError(request=MagicMock())),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=date.today(),
            )

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].failure_reason == "proxy_unavailable"

    async def test_invalid_json_writes_failure_reason_invalid_output(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning("not-json-at-all"),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=planned_session_id,
                generation_date=date.today(),
            )

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert events[0].failure_reason == "invalid_output_format"

        stmt_w = select(GeneratedWorkout).where(
            GeneratedWorkout.planned_session_id == planned_session_id,
        )
        workouts = list((await db_session.execute(stmt_w)).scalars().all())
        assert len(workouts) == 0

        stmt_s = select(WorkoutStep).where(
            WorkoutStep.generated_workout_id.in_(
                select(GeneratedWorkout.id).where(
                    GeneratedWorkout.planned_session_id == planned_session_id,
                )
            )
        )
        assert len(list((await db_session.execute(stmt_s)).scalars().all())) == 0


class TestWorkoutPreconditionGates:
    async def test_unknown_planned_session_raises_not_found(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        with pytest.raises(PlannedSessionNotFoundError):
            await agent.generate(
                athlete_id=athlete_id,
                planned_session_id=uuid.uuid4(),
                generation_date=date.today(),
            )


class TestWorkoutGenerationAgentName:
    async def test_agent_name_is_workout_generation_agent_on_all_paths(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, planned_session_id, _, _ = await _build_setup_with_planned_session(
            db_session,
            session_type=SessionType.THRESHOLD,
            data_tier=DataTier.TIER_3,
        )
        agent = await _build_workout_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(_build_threshold_payload(target_type="gap")),
        )

        await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            generation_date=date.today(),
        )

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert events[0].agent_name == "WorkoutGenerationAgent"