"""Factory functions for TrainingPreferences model."""

import uuid
from datetime import date, datetime

from app.models.training_preferences import TrainingPreferences
from app.models.enums import (
    GoalType,
    GoalEventType,
    SportBackground,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
)


def make_training_preferences(athlete_id: uuid.UUID | None = None, **overrides) -> TrainingPreferences:
    """Create a minimal valid TrainingPreferences instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    # Extract overrides to avoid duplicate keyword arguments
    goal_type = overrides.pop('goal_type', None)
    goal_event_type = overrides.pop('goal_event_type', None)
    custom_distance_km = overrides.pop('custom_distance_km', None)
    goal_event_date = overrides.pop('goal_event_date', None)
    goal_description = overrides.pop('goal_description', None)
    weekly_volume_hours = overrides.pop('weekly_volume_hours', None)
    weekly_volume_km = overrides.pop('weekly_volume_km', None)
    years_structured_training = overrides.pop('years_structured_training', None)
    sport_background = overrides.pop('sport_background', None)
    recent_injury = overrides.pop('recent_injury', None)
    weekly_schedule = overrides.pop('weekly_schedule', None)
    gps_source = overrides.pop('gps_source', None)
    hr_source = overrides.pop('hr_source', None)
    power_source = overrides.pop('power_source', None)
    primary_training_platform = overrides.pop('primary_training_platform', None)
    fitness_level = overrides.pop('fitness_level', None)
    created_at = overrides.pop('created_at', datetime(2024, 1, 1, 0, 0, 0))
    updated_at = overrides.pop('updated_at', datetime(2024, 1, 1, 0, 0, 0))

    return TrainingPreferences(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        goal_type=goal_type,
        goal_event_type=goal_event_type,
        custom_distance_km=custom_distance_km,
        goal_event_date=goal_event_date,
        goal_description=goal_description,
        weekly_volume_hours=weekly_volume_hours,
        weekly_volume_km=weekly_volume_km,
        years_structured_training=years_structured_training,
        sport_background=sport_background,
        recent_injury=recent_injury,
        weekly_schedule=weekly_schedule,
        gps_source=gps_source,
        hr_source=hr_source,
        power_source=power_source,
        primary_training_platform=primary_training_platform,
        fitness_level=fitness_level,
        created_at=created_at,
        updated_at=updated_at,
        **overrides,
    )


def make_training_preferences_full(athlete_id: uuid.UUID | None = None, **overrides) -> TrainingPreferences:
    """Create a TrainingPreferences instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    return TrainingPreferences(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.HALF_MARATHON,
        custom_distance_km=21.1,
        goal_event_date=date(2025, 6, 15),
        goal_description="Complete my first half marathon",
        weekly_volume_hours=10.0,
        weekly_volume_km=50.0,
        years_structured_training=2.0,
        sport_background=SportBackground.RUNNING_PRIMARY,
        recent_injury=False,
        weekly_schedule={"monday": "rest", "tuesday": "run", "wednesday": "strength"},
        gps_source=GpsSource.WATCH,
        hr_source=HrSource.CHEST_STRAP,
        power_source=PowerSource.NONE,
        primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
        fitness_level=5,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_training_preferences_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[TrainingPreferences]:
    """Create a list of n TrainingPreferences instances."""
    return [make_training_preferences(athlete_id, **overrides) for _ in range(n)]