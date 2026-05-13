"""Unit tests for TrainingPreferences schemas."""

import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.models.enums import GoalType, GoalEventType, SportBackground
from app.schemas.training_preferences import (
    TrainingPreferencesBase,
    TrainingPreferencesCreate,
    TrainingPreferencesUpdate,
    TrainingPreferencesResponse,
)


# ============================================================================
# TrainingPreferencesBase Tests
# ============================================================================


def test_training_preferences_base_valid():
    """Test TrainingPreferencesBase with valid data."""
    data = {
        "goal_type": "race",
        "goal_event_type": "marathon",
        "custom_distance_km": 42.195,
        "goal_event_date": "2024-06-15",
        "goal_description": "Run a marathon",
        "weekly_volume_hours": 10.0,
        "weekly_volume_km": 80.0,
        "years_structured_training": 3.0,
        "sport_background": "running_primary",
        "recent_injury": False,
        "fitness_level": 5,
    }

    prefs = TrainingPreferencesBase.model_validate(data)
    assert prefs.goal_type == GoalType.RACE
    assert prefs.goal_event_type == GoalEventType.MARATHON
    assert prefs.weekly_volume_hours == 10.0
    assert prefs.fitness_level == 5


def test_training_preferences_base_partial():
    """Test TrainingPreferencesBase with partial data."""
    data = {
        "goal_type": "fitness_improvement",
        "weekly_volume_hours": 5.0,
    }

    prefs = TrainingPreferencesBase.model_validate(data)
    assert prefs.goal_type == GoalType.FITNESS_IMPROVEMENT
    assert prefs.weekly_volume_hours == 5.0
    assert prefs.goal_event_type is None


# ============================================================================
# TrainingPreferencesCreate Tests
# ============================================================================


def test_training_preferences_create_valid():
    """Test TrainingPreferencesCreate with valid data."""
    data = {
        "athlete_id": str(uuid.uuid4()),
        "goal_type": "maintenance",
        "weekly_volume_hours": 8.0,
        "weekly_volume_km": 60.0,
        "fitness_level": 3,
    }

    prefs = TrainingPreferencesCreate.model_validate(data)
    assert prefs.goal_type == GoalType.MAINTENANCE
    assert prefs.weekly_volume_hours == 8.0
    assert prefs.fitness_level == 3


# ============================================================================
# TrainingPreferencesUpdate Tests
# ============================================================================


def test_training_preferences_update_valid():
    """Test TrainingPreferencesUpdate with valid data."""
    data = {
        "goal_type": "recovery",
        "weekly_volume_hours": 3.0,
    }

    prefs = TrainingPreferencesUpdate.model_validate(data)
    assert prefs.goal_type == GoalType.RECOVERY
    assert prefs.weekly_volume_hours == 3.0


# ============================================================================
# TrainingPreferencesResponse Tests
# ============================================================================


def test_training_preferences_response_valid():
    """Test TrainingPreferencesResponse with valid data."""
    from datetime import datetime

    data = {
        "id": uuid.uuid4(),
        "athlete_id": uuid.uuid4(),
        "goal_type": "race",
        "weekly_volume_hours": 12.0,
        "weekly_volume_km": 100.0,
        "fitness_level": 7,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }

    prefs = TrainingPreferencesResponse.model_validate(data)
    assert prefs.id == data["id"]
    assert prefs.athlete_id == data["athlete_id"]
    assert prefs.fitness_level == 7


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_training_preferences_rejects_invalid_fitness_level():
    """Verify values outside allowed range fail validation."""
    # Fitness level should be between 1 and 10
    # Test with value above maximum
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "fitness_level": 11,
        })
    assert "fitness_level" in str(exc_info.value)

    # Test with value below minimum
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "fitness_level": 0,
        })
    assert "fitness_level" in str(exc_info.value)


def test_training_preferences_rejects_negative_weekly_volume():
    """Verify negative training volume is rejected."""
    # Test negative weekly_volume_hours
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "weekly_volume_hours": -5.0,
        })
    assert "weekly_volume_hours" in str(exc_info.value)

    # Test negative weekly_volume_km
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "weekly_volume_km": -10.0,
        })
    assert "weekly_volume_km" in str(exc_info.value)


def test_training_preferences_rejects_invalid_goal_type():
    """Verify invalid enums fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "goal_type": "invalid_goal_type",
        })
    assert "goal_type" in str(exc_info.value)


def test_training_preferences_rejects_invalid_sport_background():
    """Verify invalid sport_background enum fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "sport_background": "invalid_sport",
        })
    assert "sport_background" in str(exc_info.value)


def test_training_preferences_rejects_invalid_goal_event_type():
    """Verify invalid goal_event_type enum fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        TrainingPreferencesBase.model_validate({
            "goal_event_type": "invalid_event",
        })
    assert "goal_event_type" in str(exc_info.value)