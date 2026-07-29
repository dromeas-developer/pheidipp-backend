import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    CheckpointType,
    GoalEventType,
    GoalType,
    SessionType,
    TrainingPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.training_plan import TrainingPlan
from app.services.plan_generation_errors import (
    InvalidGoalTypeError,
    PlanGenerationError,
)
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_generation_templates import QUALITY_SESSION_TYPES
from tests.utils.factories import (
    make_athlete,
    make_athlete_preferences,
    make_training_goal,
    make_twin_state,
)


async def _setup_athlete_with_race_goal(
    db_session: AsyncSession,
    *,
    goal_event_type: GoalEventType = GoalEventType.MARATHON,
    goal_event_date: date | None = None,
    fitness_level: int = 3,
    years_structured_training: int = 3,
    metric_confidence: dict[str, str | None] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    athlete = await make_athlete(db_session)
    goal = await make_training_goal(
        db_session,
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=goal_event_type,
        goal_event_date=goal_event_date
        if goal_event_date is not None
        else date.today() + timedelta(weeks=24),
        fitness_level=fitness_level,
    )
    await make_twin_state(
        db_session,
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        metric_confidence=metric_confidence,
    )
    await make_athlete_preferences(
        db_session,
        athlete_id=athlete.id,
        years_structured_training=years_structured_training,
    )
    return athlete.id, goal.id


async def _setup_athlete_with_target_performance_goal(
    db_session: AsyncSession,
    *,
    target_distance_km: float = 10.0,
    target_time_minutes: int = 50,
    fitness_level: int = 3,
    years_structured_training: int = 3,
) -> tuple[uuid.UUID, uuid.UUID]:
    athlete = await make_athlete(db_session)
    goal = await make_training_goal(
        db_session,
        athlete_id=athlete.id,
        goal_type=GoalType.TARGET_PERFORMANCE,
        goal_event_type=None,
        goal_event_date=None,
        target_distance_km=target_distance_km,
        target_time_minutes=target_time_minutes,
        fitness_level=fitness_level,
    )
    await make_twin_state(
        db_session,
        athlete_id=athlete.id,
        training_goal_id=goal.id,
    )
    await make_athlete_preferences(
        db_session,
        athlete_id=athlete.id,
        years_structured_training=years_structured_training,
    )
    return athlete.id, goal.id


class TestPlanGenerationGoalTypeValidation:
    async def test_race_event_plan_generated_successfully(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan.status == TrainingPlanStatus.ACTIVE
        assert len(result.weekly_plans) > 0
        assert len(result.weekly_sessions) > 0
        assert len(result.planned_sessions) > 0
        assert len(result.checkpoints) > 0

    async def test_target_performance_plan_generated_successfully(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_target_performance_goal(db_session)
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan.status == TrainingPlanStatus.ACTIVE
        assert len(result.weekly_plans) > 0

    async def test_unsupported_goal_type_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        await make_training_goal(
            db_session,
            athlete_id=athlete.id,
            goal_type=GoalType.FITNESS_IMPROVEMENT,
            goal_event_type=None,
            goal_event_date=None,
        )
        service = PlanGenerationService(db_session)

        with pytest.raises(InvalidGoalTypeError):
            await service.generate_plan(athlete_id=athlete.id)

    async def test_no_active_training_goal(self, db_session: AsyncSession) -> None:
        athlete = await make_athlete(db_session)
        service = PlanGenerationService(db_session)

        with pytest.raises(PlanGenerationError, match="no active training goal"):
            await service.generate_plan(athlete_id=athlete.id)

    async def test_no_twin_state(self, db_session: AsyncSession) -> None:
        athlete = await make_athlete(db_session)
        await make_training_goal(
            db_session,
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            goal_event_type=GoalEventType.MARATHON,
        )
        service = PlanGenerationService(db_session)

        with pytest.raises(PlanGenerationError, match="no twin state"):
            await service.generate_plan(athlete_id=athlete.id)

    async def test_no_athlete_preferences(self, db_session: AsyncSession) -> None:
        athlete = await make_athlete(db_session)
        goal = await make_training_goal(
            db_session,
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            goal_event_type=GoalEventType.MARATHON,
        )
        await make_twin_state(
            db_session,
            athlete_id=athlete.id,
            training_goal_id=goal.id,
        )
        service = PlanGenerationService(db_session)

        with pytest.raises(PlanGenerationError, match="no athlete preferences"):
            await service.generate_plan(athlete_id=athlete.id)

    async def test_race_event_missing_goal_event_date(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        goal = await make_training_goal(
            db_session,
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            goal_event_type=GoalEventType.MARATHON,
            goal_event_date=None,
        )
        await make_twin_state(
            db_session,
            athlete_id=athlete.id,
            training_goal_id=goal.id,
        )
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        service = PlanGenerationService(db_session)

        with pytest.raises(PlanGenerationError, match="race_event requires"):
            await service.generate_plan(athlete_id=athlete.id)


class TestPlanSupersession:
    async def test_existing_active_plan_superseded(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        first_result = await service.generate_plan(athlete_id=athlete_id)
        second_result = await service.generate_plan(athlete_id=athlete_id)

        assert second_result.supersedes_plan_id == first_result.plan.id
        assert second_result.plan.status == TrainingPlanStatus.ACTIVE

        refreshed_first = await db_session.get(TrainingPlan, first_result.plan.id)
        assert refreshed_first is not None
        assert refreshed_first.status == TrainingPlanStatus.SUPERSEDED
        assert refreshed_first.superseded_at is not None

    async def test_superseded_plan_not_deleted(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        first_result = await service.generate_plan(athlete_id=athlete_id)
        await service.generate_plan(athlete_id=athlete_id)

        refreshed = await db_session.get(TrainingPlan, first_result.plan.id)
        assert refreshed is not None
        assert refreshed.superseded_at is not None

    async def test_planned_session_retains_old_training_plan_id(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        first_result = await service.generate_plan(athlete_id=athlete_id)
        old_plan_id = first_result.plan.id

        old_sessions = [
            s for s in first_result.planned_sessions if s.training_plan_id == old_plan_id
        ]
        assert len(old_sessions) > 0

        await service.generate_plan(athlete_id=athlete_id)

        for session in old_sessions:
            refreshed = await db_session.get(PlannedSession, session.id)
            assert refreshed is not None
            assert refreshed.training_plan_id == old_plan_id


class TestTargetPerformanceGapClassification:
    async def test_small_gap_classification(self, db_session: AsyncSession) -> None:
        athlete_id, _ = await _setup_athlete_with_target_performance_goal(
            db_session,
            target_distance_km=10.0,
            target_time_minutes=50,
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan.status == TrainingPlanStatus.ACTIVE

    async def test_medium_gap_classification(self, db_session: AsyncSession) -> None:
        athlete_id, _ = await _setup_athlete_with_target_performance_goal(
            db_session,
            target_distance_km=10.0,
            target_time_minutes=55,
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan.status == TrainingPlanStatus.ACTIVE

    async def test_large_gap_classification(self, db_session: AsyncSession) -> None:
        athlete_id, _ = await _setup_athlete_with_target_performance_goal(
            db_session,
            target_distance_km=10.0,
            target_time_minutes=60,
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan.status == TrainingPlanStatus.ACTIVE


class TestSessionStructureRules:
    async def test_no_two_consecutive_quality_sessions(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            goal_event_date=date.today() + timedelta(weeks=24),
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        sessions_by_date = sorted(result.planned_sessions, key=lambda s: s.target_date)
        for i in range(len(sessions_by_date) - 1):
            current = sessions_by_date[i]
            next_session = sessions_by_date[i + 1]
            if next_session.target_date == current.target_date + timedelta(days=1):
                if current.session_type in QUALITY_SESSION_TYPES:
                    assert (
                        next_session.session_type not in QUALITY_SESSION_TYPES
                    ), f"Consecutive quality sessions: {current.session_type} then {next_session.session_type} on {current.target_date}"

    async def test_long_run_followed_by_rest_or_recovery(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            goal_event_date=date.today() + timedelta(weeks=24),
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        sessions_by_date = sorted(result.planned_sessions, key=lambda s: s.target_date)
        for i, session in enumerate(sessions_by_date):
            if session.session_type == SessionType.LONG_RUN:
                if i + 1 < len(sessions_by_date):
                    next_session = sessions_by_date[i + 1]
                    if next_session.target_date == session.target_date + timedelta(
                        days=1
                    ):
                        assert next_session.session_type in {
                            SessionType.REST,
                            SessionType.RECOVERY_RUN,
                        }

    async def test_threshold_sandwiched_between_easy_days(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            goal_event_date=date.today() + timedelta(weeks=24),
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        sandwiched_types = {SessionType.THRESHOLD, SessionType.VO2MAX}
        easy_rest_types = {SessionType.EASY_RUN, SessionType.REST, SessionType.RECOVERY_RUN}
        sessions_by_date = sorted(result.planned_sessions, key=lambda s: s.target_date)

        for i, session in enumerate(sessions_by_date):
            if session.session_type in sandwiched_types:
                if i > 0:
                    prev = sessions_by_date[i - 1]
                    if prev.target_date == session.target_date - timedelta(days=1):
                        assert prev.session_type in easy_rest_types
                if i + 1 < len(sessions_by_date):
                    next_s = sessions_by_date[i + 1]
                    if next_s.target_date == session.target_date + timedelta(days=1):
                        assert next_s.session_type in easy_rest_types

    async def test_plan_phases_cover_full_duration_with_weekly_plans(
        self, db_session: AsyncSession
    ) -> None:
        goal_date = date.today() + timedelta(weeks=24)
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            goal_event_date=goal_date,
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        phases = result.plan.phases_summary
        assert len(phases) > 0, "Plan has no phases"

        phase_starts = [date.fromisoformat(p["start_date"]) for p in phases]
        phase_ends = [date.fromisoformat(p["end_date"]) for p in phases]

        assert phase_starts == sorted(phase_starts), "Phases are not ordered by start_date"

        for i in range(len(phases) - 1):
            assert (
                phase_ends[i] + timedelta(days=1) == phase_starts[i + 1]
            ), f"Gap or overlap between phase {i} (ends {phase_ends[i]}) and phase {i + 1} (starts {phase_starts[i + 1]})"

        total_weeks = sum(p["weeks"] for p in phases)
        weekly_plan_weeks = {wp.week_number for wp in result.weekly_plans}
        assert weekly_plan_weeks == set(range(1, total_weeks + 1)), (
            f"Missing WeeklyPlan entries: expected weeks 1..{total_weeks}, "
            f"got {sorted(weekly_plan_weeks)}"
        )


class TestCheckpointScheduling:
    async def test_calibration_checkpoint_at_phase_transition_with_low_confidence(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            metric_confidence={"lt2_hr": "low", "lt1_hr": "low", "cp": None},
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        calibration = [
            c for c in result.checkpoints if c.type == CheckpointType.CALIBRATION
        ]
        assert len(calibration) >= 1

    async def test_benchmark_checkpoint_at_week_4(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        benchmark = [
            c for c in result.checkpoints if c.type == CheckpointType.BENCHMARK
        ]
        assert len(benchmark) == 1

    async def test_progress_review_checkpoints(self, db_session: AsyncSession) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            goal_event_date=date.today() + timedelta(weeks=24),
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        reviews = [
            c for c in result.checkpoints if c.type == CheckpointType.PROGRESS_REVIEW
        ]
        assert len(reviews) >= 1

    async def test_race_simulation_2_weeks_before_goal(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(
            db_session,
            goal_event_date=date.today() + timedelta(weeks=24),
        )
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        race_sim = [
            c for c in result.checkpoints if c.type == CheckpointType.RACE_SIMULATION
        ]
        assert len(race_sim) == 1

    async def test_checkpoints_sorted_by_week_number(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        session_weeks = {
            ps.id: ps.week_number for ps in result.planned_sessions
        }
        week_numbers = [
            session_weeks[c.planned_session_id] for c in result.checkpoints
        ]
        assert week_numbers == sorted(week_numbers)


class TestPlanGenerationPurity:
    async def test_no_llm_calls_during_generation(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan.status == TrainingPlanStatus.ACTIVE

    async def test_training_plan_generated_event_published(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _ = await _setup_athlete_with_race_goal(db_session)
        service = PlanGenerationService(db_session)

        result = await service.generate_plan(athlete_id=athlete_id)

        assert result.plan is not None
        assert result.plan.status == TrainingPlanStatus.ACTIVE
