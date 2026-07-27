from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    ActivitySource,
    DataTier,
    GoalType,
    MessageType,
    PhaseLabel,
    PhysiologicalIntent,
    PlannedSessionStatus,
    RecoveryModifierLevel,
    SessionPriority,
    SessionType,
    StepType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
    WeeklyPlanStatus,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from app.models.workout_step import WorkoutStep
from tests.utils.factories import make_athlete


class TestCoachingMessageFirstMessageSingleton:
    async def test_duplicate_first_message_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
        await db_session.commit()

        msg = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Welcome to your training journey",
            prompt_version="v1",
        )
        db_session.add(msg)
        await db_session.commit()

        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Another first message attempt",
            prompt_version="v1",
        )
        db_session.add(msg2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestCoachingMessagePostWorkoutSingleton:
    async def test_duplicate_post_workout_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
        await db_session.commit()

        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            external_id=None,
            activity_date=date(2025, 6, 1),
            start_time=date(2025, 6, 1),
            duration_seconds=3600,
        )
        db_session.add(activity)
        await db_session.commit()

        msg = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            activity_id=activity.id,
            message_type=MessageType.POST_WORKOUT,
            content="Great run today",
            prompt_version="v1",
        )
        db_session.add(msg)
        await db_session.commit()

        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            activity_id=activity.id,
            message_type=MessageType.POST_WORKOUT,
            content="Another post-workout attempt",
            prompt_version="v1",
        )
        db_session.add(msg2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestCoachingMessagePostWorkoutNullActivity:
    async def test_duplicate_post_workout_null_activity_succeeds(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
        await db_session.commit()

        msg = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            activity_id=None,
            message_type=MessageType.POST_WORKOUT,
            content="Post-workout message one",
            prompt_version="v1",
        )
        db_session.add(msg)
        await db_session.commit()

        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            activity_id=None,
            message_type=MessageType.POST_WORKOUT,
            content="Post-workout message two",
            prompt_version="v1",
        )
        db_session.add(msg2)
        await db_session.commit()


class TestCoachingMessageContentCheck:
    async def test_empty_content_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
        await db_session.commit()

        msg = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="",
            prompt_version="v1",
        )
        db_session.add(msg)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestGeneratedWorkoutUniquePlanDate:
    async def test_duplicate_plan_date_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gen_date = date(2025, 6, 15)
        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=gen_date,
        )
        db_session.add(gw)
        await db_session.commit()

        gw2 = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=gen_date,
        )
        db_session.add(gw2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestGeneratedWorkoutTargetsCheck:
    async def test_theoretical_targets_not_object_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets="not-an-object",
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_adjusted_targets_null_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets=None,
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestGeneratedWorkoutRecoveryModifierCheck:
    async def test_invalid_recovery_modifier_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            recovery_modifier_level="purple",
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestWorkoutStepUniqueWorkoutOrder:
    async def test_duplicate_step_order_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        await db_session.commit()

        step = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=PhysiologicalIntent.THRESHOLD,
            target={},
            description="Tempo run",
        )
        db_session.add(step)
        await db_session.commit()

        step2 = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=1,
            step_type=StepType.RECOVERY,
            session_type=SessionType.RECOVERY_RUN,
            physiological_intent=PhysiologicalIntent.RECOVERY,
            target={},
            description="Recovery",
        )
        db_session.add(step2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestWorkoutStepPhysiologicalIntentNotNull:
    async def test_null_physiological_intent_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        await db_session.commit()

        step = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=None,
            target={},
            description="Tempo run",
        )
        db_session.add(step)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestWorkoutStepStepOrderCheck:
    async def test_step_order_zero_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        await db_session.commit()

        step = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=0,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=PhysiologicalIntent.THRESHOLD,
            target={},
            description="Tempo run",
        )
        db_session.add(step)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestWorkoutStepDescriptionCheck:
    async def test_empty_description_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        await db_session.commit()

        step = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=PhysiologicalIntent.THRESHOLD,
            target={},
            description="",
        )
        db_session.add(step)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestWorkoutStepDurationSecondsCheck:
    async def test_negative_duration_raises_integrity_error(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        await db_session.commit()

        step = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=PhysiologicalIntent.THRESHOLD,
            target={},
            description="Tempo run",
            duration_seconds=-10,
        )
        db_session.add(step)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_null_duration_succeeds(self, db_session: AsyncSession):
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

        twin = TwinState(
            athlete_id=athlete.id,
            training_goal_id=goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.ACTIVITY_SYNC,
            model_version="1.0.0",
            fitness=100.0,
            fatigue=40.0,
            form=60.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin)
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

        gw = GeneratedWorkout(
            planned_session_id=session.id,
            twin_state_id=twin.id,
            theoretical_targets={},
            adjusted_targets={},
            generation_date=date(2025, 6, 15),
        )
        db_session.add(gw)
        await db_session.commit()

        step = WorkoutStep(
            generated_workout_id=gw.id,
            step_order=1,
            step_type=StepType.WORK,
            session_type=SessionType.TEMPO,
            physiological_intent=PhysiologicalIntent.THRESHOLD,
            target={},
            description="Tempo run",
            duration_seconds=None,
        )
        db_session.add(step)
        await db_session.commit()
