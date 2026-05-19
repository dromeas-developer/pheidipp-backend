"""Unit tests for AthletePreferences schemas."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.athlete_preferences import (
    DaySchedule,
    WeeklySchedule,
    AthletePreferencesCreate,
    AthletePreferencesUpdate,
    AthletePreferencesResponse,
)
from app.models.enums import (
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
)


# ============================================================================
# DaySchedule Tests
# ============================================================================


def test_day_schedule_valid():
    """Test DaySchedule with valid data."""
    data = {"available": True, "max_hours": 1.0, "long_workout": False}
    schedule = DaySchedule.model_validate(data)
    assert schedule.available is True
    assert schedule.max_hours == 1.0
    assert schedule.long_workout is False


def test_day_schedule_max_hours_negative():
    """Test DaySchedule rejects negative max_hours."""
    data = {"available": True, "max_hours": -1.0, "long_workout": False}
    with pytest.raises(ValidationError):
        DaySchedule.model_validate(data)


# ============================================================================
# WeeklySchedule Tests
# ============================================================================


def test_weekly_schedule_valid():
    """Test WeeklySchedule with all 7 days present."""
    data = {
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
    schedule = WeeklySchedule.model_validate(data)
    assert schedule.available_days_count == 5


def test_weekly_schedule_invalid_day_key():
    """Test WeeklySchedule rejects invalid day keys."""
    data = {
        "days": {
            "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
            "xyz": {"available": True, "max_hours": 1.0, "long_workout": False},
        },
        "available_days_count": 2,
    }
    with pytest.raises(ValidationError):
        WeeklySchedule.model_validate(data)


def test_weekly_schedule_missing_days():
    """Test WeeklySchedule rejects missing day entries."""
    data = {
        "days": {
            "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
        },
        "available_days_count": 1,
    }
    with pytest.raises(ValidationError):
        WeeklySchedule.model_validate(data)


def test_weekly_schedule_available_days_count_mismatch():
    """Test WeeklySchedule rejects mismatched available_days_count."""
    data = {
        "days": {
            "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
            "tue": {"available": False, "max_hours": 0, "long_workout": False},
            "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
            "thu": {"available": False, "max_hours": 0, "long_workout": False},
            "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
            "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
            "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
        },
        "available_days_count": 3,  # Should be 5
    }
    with pytest.raises(ValidationError):
        WeeklySchedule.model_validate(data)


def test_weekly_schedule_long_workout_on_unavailable_day():
    """Test WeeklySchedule rejects long_workout=True on unavailable day."""
    data = {
        "days": {
            "mon": {"available": False, "max_hours": 0, "long_workout": True},
            "tue": {"available": False, "max_hours": 0, "long_workout": False},
            "wed": {"available": False, "max_hours": 0, "long_workout": False},
            "thu": {"available": False, "max_hours": 0, "long_workout": False},
            "fri": {"available": False, "max_hours": 0, "long_workout": False},
            "sat": {"available": False, "max_hours": 0, "long_workout": False},
            "sun": {"available": False, "max_hours": 0, "long_workout": False},
        },
        "available_days_count": 0,
    }
    with pytest.raises(ValidationError):
        WeeklySchedule.model_validate(data)


# ============================================================================
# AthletePreferencesCreate Tests
# ============================================================================


def test_athlete_preferences_create_valid():
    """Test AthletePreferencesCreate with all fields."""
    data = {
        "sport_background": "running_primary",
        "years_structured_training": 5.0,
        "training_time_of_day": "morning",
        "weekly_schedule": {
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
        },
        "gps_source": "watch",
        "hr_source": "chest_strap",
        "power_source": "running_power",
        "primary_training_platform": "garmin_connect",
    }
    prefs = AthletePreferencesCreate.model_validate(data)
    assert prefs.sport_background == SportBackground.RUNNING_PRIMARY
    assert prefs.years_structured_training == 5.0


def test_athlete_preferences_create_minimal():
    """Test AthletePreferencesCreate with minimal fields (empty object)."""
    data = {}
    prefs = AthletePreferencesCreate.model_validate(data)
    assert prefs.sport_background is None
    assert prefs.years_structured_training is None


def test_athlete_preferences_create_years_negative():
    """Test AthletePreferencesCreate rejects negative years_structured_training."""
    data = {"years_structured_training": -1.0}
    with pytest.raises(ValidationError):
        AthletePreferencesCreate.model_validate(data)


# ============================================================================
# AthletePreferencesUpdate Tests
# ============================================================================


def test_athlete_preferences_update_partial():
    """Test AthletePreferencesUpdate with partial data (only sport_background)."""
    data = {"sport_background": "cycling_crossover"}
    update = AthletePreferencesUpdate.model_validate(data)
    assert update.sport_background == SportBackground.CYCLING_CROSSOVER
    assert update.years_structured_training is None


def test_athlete_preferences_update_all_optional():
    """Test AthletePreferencesUpdate with all fields optional."""
    data = {}
    update = AthletePreferencesUpdate.model_validate(data)
    assert update.sport_background is None
    assert update.training_time_of_day is None


# ============================================================================
# AthletePreferencesResponse Tests
# ============================================================================


def test_athlete_preferences_response_valid():
    """Test AthletePreferencesResponse with valid data."""
    data = {
        "id": str(uuid.uuid4()),
        "athlete_id": str(uuid.uuid4()),
        "sport_background": "running_primary",
        "years_structured_training": 5.0,
        "training_time_of_day": "morning",
        "weekly_schedule": {
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
        },
        "gps_source": "watch",
        "hr_source": "chest_strap",
        "power_source": "running_power",
        "primary_training_platform": "garmin_connect",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    response = AthletePreferencesResponse.model_validate(data)
    assert response.id == uuid.UUID(data["id"])
    assert response.athlete_id == uuid.UUID(data["athlete_id"])
    assert response.sport_background == SportBackground.RUNNING_PRIMARY


def test_athlete_preferences_response_from_attributes():
    """Test AthletePreferencesResponse.from_attributes with ORM instance."""
    from tests.factories.athlete_preferences_factory import make_athlete_preferences_full

    # Create a model instance
    prefs = make_athlete_preferences_full()

    # Validate using from_attributes
    response = AthletePreferencesResponse.model_validate(prefs)
    assert response.id == prefs.id
    assert response.athlete_id == prefs.athlete_id
    assert response.sport_background == prefs.sport_background