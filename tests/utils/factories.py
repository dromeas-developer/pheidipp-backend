import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_profile import AthleteProfile
from app.models.athlete_preferences import AthletePreferences
from app.models.enums import (
    ActivitySource,
    DataTier,
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    Sex,
    SportBackground,
    SportType,
    TrainingGoalStatus,
    TrainingTimeOfDay,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState

_UNSET: Any = object()


async def make_athlete(
    db_session: AsyncSession, *, email: str | None = None
) -> Athlete:
    athlete = Athlete(email=email or f"test-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete


async def make_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    duration_seconds: int = 3600,
    has_power: bool = True,
    has_hr: bool = True,
    has_gps: bool = True,
) -> Activity:
    activity = Activity(
        athlete_id=athlete_id,
        source=source,
        external_id=None,
        activity_date=date(2026, 1, 1),
        start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
        duration_seconds=duration_seconds,
        sport_type=SportType.RUNNING,
        has_hr=has_hr,
        has_power=has_power,
        has_gps=has_gps,
        quality_flags={},
        fit_file_key="athlete/2026-01-01/test.fit",
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return activity


async def make_athlete_with_profile(
    db_session: AsyncSession,
    *,
    email: str | None = None,
    date_of_birth: date | None = None,
    sex: Sex | None = None,
) -> tuple[Athlete, AthleteProfile]:
    athlete = Athlete(email=email or f"test-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()
    profile = AthleteProfile(
        athlete_id=athlete.id,
        date_of_birth=date_of_birth or date(1990, 1, 15),
        sex=sex or Sex.MALE,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(athlete)
    await db_session.refresh(profile)
    return athlete, profile


async def make_training_goal(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    goal_type: GoalType = GoalType.RACE_EVENT,
    goal_event_type: GoalEventType | None = GoalEventType.MARATHON,
    goal_event_date: Any = _UNSET,
    target_distance_km: float | None = None,
    target_time_minutes: int | None = None,
    fitness_level: int = 3,
    status: TrainingGoalStatus = TrainingGoalStatus.ACTIVE,
) -> TrainingGoal:
    resolved_goal_event_date: date | None
    if goal_event_date is _UNSET:
        resolved_goal_event_date = date(2026, 12, 6)
    else:
        resolved_goal_event_date = goal_event_date
    goal = TrainingGoal(
        athlete_id=athlete_id,
        goal_type=goal_type,
        goal_event_type=goal_event_type,
        goal_event_date=resolved_goal_event_date,
        target_distance_km=target_distance_km,
        target_time_minutes=target_time_minutes,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=fitness_level,
        status=status,
    )
    db_session.add(goal)
    await db_session.commit()
    await db_session.refresh(goal)
    return goal


async def make_twin_state(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    training_goal_id: uuid.UUID,
    data_tier: DataTier = DataTier.TIER_3,
    confidence_level: TwinConfidenceLevel = TwinConfidenceLevel.LOW,
    trigger: TwinTrigger = TwinTrigger.QUESTIONNAIRE,
    metric_confidence: dict[str, str | None] | None = None,
) -> TwinState:
    twin = TwinState(
        athlete_id=athlete_id,
        training_goal_id=training_goal_id,
        data_tier=data_tier,
        confidence_level=confidence_level,
        trigger=trigger,
        model_version="v1-questionnaire-bootstrap",
        fitness=0.0,
        fatigue=0.0,
        form=0.0,
        readiness_level=RecoveryModifierLevel.GREEN,
        metric_confidence=metric_confidence or {},
    )
    db_session.add(twin)
    await db_session.commit()
    await db_session.refresh(twin)
    return twin


WEEKLY_SCHEDULE_TEMPLATE: dict[str, dict[str, object]] = {
    "monday": {"available": True, "max_hours": 1.5, "long_workout": False, "doubles_eligible": False},
    "tuesday": {"available": True, "max_hours": 1.5, "long_workout": False, "doubles_eligible": False},
    "wednesday": {"available": True, "max_hours": 1.5, "long_workout": False, "doubles_eligible": False},
    "thursday": {"available": True, "max_hours": 1.5, "long_workout": False, "doubles_eligible": False},
    "friday": {"available": True, "max_hours": 1.0, "long_workout": False, "doubles_eligible": False},
    "saturday": {"available": True, "max_hours": 2.5, "long_workout": True, "doubles_eligible": False},
    "sunday": {"available": True, "max_hours": 2.0, "long_workout": False, "doubles_eligible": False},
}


async def make_athlete_preferences(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    years_structured_training: int = 3,
    sport_background: SportBackground = SportBackground.RUNNING_PRIMARY,
    weekly_schedule: dict[str, dict[str, object]] | None = None,
) -> AthletePreferences:
    prefs = AthletePreferences(
        athlete_id=athlete_id,
        sport_background=sport_background,
        years_structured_training=years_structured_training,
        training_time_of_day=TrainingTimeOfDay.MORNING,
        weekly_schedule=weekly_schedule or WEEKLY_SCHEDULE_TEMPLATE,
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.RUNNING_POWER_METER,
        primary_training_platform=PrimaryTrainingPlatform.INTERVALS_ICU,
    )
    db_session.add(prefs)
    await db_session.commit()
    await db_session.refresh(prefs)
    return prefs


async def make_athlete_fitness(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    aggregate: dict[str, float] | None = None,
    time_constants: dict[str, object] | None = None,
    last_activity_id: uuid.UUID | None = None,
) -> AthleteFitness:
    resolved_aggregate = aggregate if aggregate is not None else {
        "fitness": 0.0,
        "fatigue": 0.0,
        "form": 0.0,
    }
    resolved_time_constants = time_constants if time_constants is not None else {
        "fitness_tau_days": 42,
        "fatigue_tau_days": 7,
        "source": "population_default",
    }
    fitness = AthleteFitness(
        athlete_id=athlete_id,
        aggregate=resolved_aggregate,
        time_constants=resolved_time_constants,
        last_activity_id=last_activity_id,
    )
    db_session.add(fitness)
    await db_session.commit()
    await db_session.refresh(fitness)
    return fitness


async def make_athlete_physiology(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    max_hr: int = 184,
    lt1: dict[str, object] | None = None,
    lt2: dict[str, object] | None = None,
    cp: int | None = None,
    vo2max: float | None = None,
) -> AthletePhysiology:
    resolved_lt1 = lt1 if lt1 is not None else {"hr": {"value": 145.0, "prior_weight": 0.5}}
    resolved_lt2 = lt2 if lt2 is not None else {"hr": {"value": 165.0, "prior_weight": 0.5}}
    physiology = AthletePhysiology(
        athlete_id=athlete_id,
        max_hr=max_hr,
        lt1=resolved_lt1,
        lt2=resolved_lt2,
        cp=cp,
        vo2max=vo2max,
    )
    db_session.add(physiology)
    await db_session.commit()
    await db_session.refresh(physiology)
    return physiology
