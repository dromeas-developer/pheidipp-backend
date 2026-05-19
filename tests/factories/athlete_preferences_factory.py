"""Factory functions for AthletePreferences model."""

import uuid
from datetime import datetime

from app.models.athlete_preferences import AthletePreferences
from app.models.enums import (
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
)


def make_athlete_preferences(athlete_id: uuid.UUID | None = None, **overrides) -> AthletePreferences:
    """Create a minimal valid AthletePreferences instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    return AthletePreferences(
        athlete_id=athlete_id,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_preferences_full(athlete_id: uuid.UUID | None = None, **overrides) -> AthletePreferences:
    """Create an AthletePreferences instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    # Create a valid weekly_schedule dict
    weekly_schedule = {
        "days": {
            "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
            "tue": {"available": False, "max_hours": 0, "long_workout": False},
            "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
            "thu": {"available": False, "max_hours": 0, "long_workout": False},
            "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
            "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
            "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
        },
        "available_days_count": 5,
    }

    # Extract known fields from overrides to avoid conflicts
    known_fields = {
        "id", "athlete_id", "sport_background", "years_structured_training",
        "training_time_of_day", "weekly_schedule", "gps_source", "hr_source",
        "power_source", "primary_training_platform", "created_at", "updated_at"
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return AthletePreferences(
        id=overrides.get("id", uuid.uuid4()),
        athlete_id=athlete_id,
        sport_background=overrides.get("sport_background", SportBackground.RUNNING_PRIMARY),
        years_structured_training=overrides.get("years_structured_training", 5.0),
        training_time_of_day=overrides.get("training_time_of_day", TrainingTimeOfDay.MORNING),
        weekly_schedule=overrides.get("weekly_schedule", weekly_schedule),
        gps_source=overrides.get("gps_source", GpsSource.WATCH),
        hr_source=overrides.get("hr_source", HrSource.CHEST_STRAP),
        power_source=overrides.get("power_source", PowerSource.RUNNING_POWER),
        primary_training_platform=overrides.get("primary_training_platform", PrimaryTrainingPlatform.GARMIN_CONNECT),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        updated_at=overrides.get("updated_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_athlete_preferences_batch(
    n: int, athlete_id: uuid.UUID | None = None, **overrides
) -> list[AthletePreferences]:
    """Create a list of n AthletePreferences instances."""
    return [make_athlete_preferences(athlete_id, **overrides) for _ in range(n)]