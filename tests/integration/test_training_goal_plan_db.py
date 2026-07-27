from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkpoint import Checkpoint
from app.models.enums import (
    CheckpointStatus,
    CheckpointType,
    GoalType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    WeeklyPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan
from tests.utils.factories import make_athlete


class TestTrainingGoalActiveUnique:
    async def test_duplicate_active_goal_raises_integrity_error(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=40.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        await db_session.commit()

        goal2 = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            weekly_volume_hours=10.0,
            weekly_volume_km=50.0,
            fitness_level=4,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestTrainingGoalInactiveMultiple:
    async def test_multiple_inactive_goals_succeed(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=40.0,
            fitness_level=3,
            status=TrainingGoalStatus.COMPLETED,
        )
        db_session.add(goal)
        await db_session.commit()

        goal2 = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            weekly_volume_hours=10.0,
            weekly_volume_km=50.0,
            fitness_level=4,
            status=TrainingGoalStatus.ABANDONED,
        )
        db_session.add(goal2)
        await db_session.commit()


class TestTrainingGoalFitnessLevelRange:
    async def test_fitness_level_6_raises_integrity_error(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=40.0,
            fitness_level=6,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestTrainingGoalWeeklyVolumeHoursCheck:
    async def test_negative_weekly_volume_hours_raises_integrity_error(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=-5.0,
            weekly_volume_km=40.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestTrainingGoalWeeklyVolumeKmCheck:
    async def test_negative_weekly_volume_km_raises_integrity_error(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=-10.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestWeeklyPlanUniquePlanWeek:
    async def test_duplicate_plan_week_raises_integrity_error(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=40.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        await db_session.commit()

        plan = TrainingPlan(
            training_goal_id=goal.id,
            status=TrainingPlanStatus.ACTIVE,
        )
        db_session.add(plan)
        await db_session.commit()

        wp = WeeklyPlan(
            training_plan_id=plan.id,
            week_number=1,
            adjusted_intent={},
            status=WeeklyPlanStatus.ACTIVE,
            week_starts_at=date(2025, 6, 1),
            week_ends_at=date(2025, 6, 7),
        )
        db_session.add(wp)
        await db_session.commit()

        wp2 = WeeklyPlan(
            training_plan_id=plan.id,
            week_number=1,
            adjusted_intent={},
            status=WeeklyPlanStatus.ACTIVE,
            week_starts_at=date(2025, 6, 1),
            week_ends_at=date(2025, 6, 7),
        )
        db_session.add(wp2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestCheckpointUniquePlannedSession:
    async def test_duplicate_planned_session_id_raises_integrity_error(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=40.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        await db_session.commit()

        plan = TrainingPlan(
            training_goal_id=goal.id,
            status=TrainingPlanStatus.ACTIVE,
        )
        db_session.add(plan)
        await db_session.commit()

        wp = WeeklyPlan(
            training_plan_id=plan.id,
            week_number=1,
            adjusted_intent={},
            status=WeeklyPlanStatus.ACTIVE,
            week_starts_at=date(2025, 6, 1),
            week_ends_at=date(2025, 6, 7),
        )
        db_session.add(wp)
        await db_session.commit()

        session = PlannedSession(
            weekly_plan_id=wp.id,
            training_plan_id=plan.id,
            target_date=date(2025, 6, 1),
            week_number=1,
            phase_label=PhaseLabel.AEROBIC_BASE,
            session_type=SessionType.EASY_RUN,
            intent_description="Build aerobic base",
            approximate_duration_minutes=60,
            status=PlannedSessionStatus.SCHEDULED,
            session_priority=SessionPriority.PRIMARY,
        )
        db_session.add(session)
        await db_session.commit()

        cp = Checkpoint(
            planned_session_id=session.id,
            type=CheckpointType.BENCHMARK,
            target_metric="pace",
            status=CheckpointStatus.SCHEDULED,
        )
        db_session.add(cp)
        await db_session.commit()

        cp2 = Checkpoint(
            planned_session_id=session.id,
            type=CheckpointType.CALIBRATION,
            target_metric="heart_rate",
            status=CheckpointStatus.SCHEDULED,
        )
        db_session.add(cp2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
