"""Unit tests for TrainingBlock schemas."""

import uuid
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.schemas.training_block import (
    TrainingBlockCreate,
    TrainingBlockUpdate,
    TrainingBlockResponse,
)
from app.models.enums import (
    GoalType,
    GoalEventType,
    GoalStatus,
)


# ============================================================================
# TrainingBlockCreate Tests
# ============================================================================


def test_training_block_create_valid():
    """Test TrainingBlockCreate with all fields."""
    data = {
        "goal_type": "race",
        "goal_event_type": "marathon",
        "goal_event_name": "Boston Marathon 2024",
        "goal_event_date": "2024-04-15",
        "goal_description": "Prepare for Boston Marathon",
        "custom_distance_km": 42.195,
        "weekly_volume_hours": 10.0,
        "weekly_volume_km": 80.0,
        "fitness_level": 3,
        "recent_injury": False,
    }
    block = TrainingBlockCreate.model_validate(data)
    assert block.goal_type == GoalType.RACE
    assert block.goal_event_type == GoalEventType.MARATHON
    assert block.custom_distance_km == 42.195
    assert block.fitness_level == 3


def test_training_block_create_custom_distance_negative():
    """Test TrainingBlockCreate rejects custom_distance_km <= 0."""
    data = {"custom_distance_km": 0}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_custom_distance_below_zero():
    """Test TrainingBlockCreate rejects negative custom_distance_km."""
    data = {"custom_distance_km": -1.0}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_weekly_volume_hours_negative():
    """Test TrainingBlockCreate rejects negative weekly_volume_hours."""
    data = {"weekly_volume_hours": -1.0}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_weekly_volume_km_negative():
    """Test TrainingBlockCreate rejects negative weekly_volume_km."""
    data = {"weekly_volume_km": -1.0}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_fitness_level_below_range():
    """Test TrainingBlockCreate rejects fitness_level below 1."""
    data = {"fitness_level": 0}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_fitness_level_above_range():
    """Test TrainingBlockCreate rejects fitness_level above 5."""
    data = {"fitness_level": 6}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_goal_event_name_too_long():
    """Test TrainingBlockCreate rejects goal_event_name > 200 characters."""
    data = {"goal_event_name": "x" * 201}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


def test_training_block_create_goal_description_too_long():
    """Test TrainingBlockCreate rejects goal_description > 500 characters."""
    data = {"goal_description": "x" * 501}
    with pytest.raises(ValidationError):
        TrainingBlockCreate.model_validate(data)


# ============================================================================
# TrainingBlockUpdate Tests
# ============================================================================


def test_training_block_update_status_only():
    """Test TrainingBlockUpdate with only status field."""
    data = {"status": "completed"}
    update = TrainingBlockUpdate.model_validate(data)
    assert update.status == GoalStatus.COMPLETED
    assert update.goal_event_date is None
    assert update.goal_description is None


def test_training_block_update_goal_event_date_only():
    """Test TrainingBlockUpdate with only goal_event_date field."""
    data = {"goal_event_date": "2024-06-01"}
    update = TrainingBlockUpdate.model_validate(data)
    assert update.goal_event_date == date(2024, 6, 1)
    assert update.status is None


def test_training_block_update_goal_description_only():
    """Test TrainingBlockUpdate with only goal_description field."""
    data = {"goal_description": "Updated description"}
    update = TrainingBlockUpdate.model_validate(data)
    assert update.goal_description == "Updated description"
    assert update.status is None


def test_training_block_update_immutable_fields_not_allowed():
    """Test that immutable fields are not in TrainingBlockUpdate schema."""
    # These fields should NOT be in TrainingBlockUpdate
    update_schema_fields = set(TrainingBlockUpdate.model_fields.keys())
    assert "goal_type" not in update_schema_fields
    assert "goal_event_type" not in update_schema_fields
    assert "custom_distance_km" not in update_schema_fields
    assert "weekly_volume_hours" not in update_schema_fields
    assert "weekly_volume_km" not in update_schema_fields
    assert "fitness_level" not in update_schema_fields
    assert "recent_injury" not in update_schema_fields


# ============================================================================
# TrainingBlockResponse Tests
# ============================================================================


def test_training_block_response_valid():
    """Test TrainingBlockResponse with all required fields."""
    data = {
        "id": str(uuid.uuid4()),
        "athlete_id": str(uuid.uuid4()),
        "goal_type": "race",
        "goal_event_type": "marathon",
        "goal_event_name": "Boston Marathon 2024",
        "goal_event_date": "2024-04-15",
        "goal_description": "Prepare for Boston Marathon",
        "custom_distance_km": 42.195,
        "weekly_volume_hours": 10.0,
        "weekly_volume_km": 80.0,
        "fitness_level": 3,
        "recent_injury": False,
        "status": "active",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    response = TrainingBlockResponse.model_validate(data)
    assert response.id == uuid.UUID(data["id"])
    assert response.status == GoalStatus.ACTIVE


def test_training_block_response_status_required():
    """Test TrainingBlockResponse requires status field."""
    data = {
        "id": str(uuid.uuid4()),
        "athlete_id": str(uuid.uuid4()),
        "status": "active",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    response = TrainingBlockResponse.model_validate(data)
    assert response.status == GoalStatus.ACTIVE


def test_training_block_response_from_attributes():
    """Test TrainingBlockResponse.from_attributes with ORM instance."""
    from tests.factories.training_block_factory import make_training_block_full

    # Create a model instance
    block = make_training_block_full()

    # Validate using from_attributes
    response = TrainingBlockResponse.model_validate(block)
    assert response.id == block.id
    assert response.athlete_id == block.athlete_id
    assert response.status == block.status