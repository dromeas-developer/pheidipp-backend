"""Unit tests for Activity schemas."""

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.enums import ActivityType, PerceivedEffort
from app.schemas.activity import (
    ActivityBase,
    ActivityCreate,
    ActivityUpdate,
    ActivityResponse,
    ActivityListParams,
    ActivityListResponse,
)


# ============================================================================
# ActivityBase Tests
# ============================================================================


def test_activity_base_valid():
    """Test ActivityBase with valid data."""
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)
    
    data = {
        "activity_type": "running",
        "title": "Morning Run",
        "description": "A nice morning run",
        "started_at": started_at,
        "finished_at": finished_at,
        "perceived_effort": "moderate",
        "avg_heart_rate": 145,
        "max_heart_rate": 175,
        "avg_speed_m_per_s": 3.5,
        "max_speed_m_per_s": 5.0,
        "avg_power": 200,
        "max_power": 400,
        "distance_meters": 10000.0,
        "elevation_gain_meters": 100.0,
        "elevation_loss_meters": 50.0,
        "calories": 500,
        "source": "garmin",
    }
    
    activity = ActivityBase.model_validate(data)
    assert activity.activity_type == ActivityType.RUNNING
    assert activity.title == "Morning Run"
    assert activity.perceived_effort == PerceivedEffort.MODERATE
    assert activity.avg_heart_rate == 145


def test_activity_base_partial():
    """Test ActivityBase with partial data."""
    data = {
        "activity_type": "cycling",
        "title": "Afternoon Ride",
    }
    
    activity = ActivityBase.model_validate(data)
    assert activity.activity_type == ActivityType.CYCLING
    assert activity.title == "Afternoon Ride"
    assert activity.description is None
    assert activity.perceived_effort is None


def test_activity_base_invalid_enum():
    """Test ActivityBase with invalid enum values."""
    with pytest.raises(ValidationError):
        ActivityBase.model_validate({
            "activity_type": "invalid_activity",
            "perceived_effort": "invalid_effort",
        })


# ============================================================================
# ActivityCreate Tests
# ============================================================================


def test_activity_create_valid():
    """Test ActivityCreate with valid data."""
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)
    
    data = {
        "athlete_id": uuid.uuid4(),
        "activity_type": "running",
        "title": "Morning Run",
        "started_at": started_at,
        "finished_at": finished_at,
        "distance_meters": 10000.0,
    }
    
    activity = ActivityCreate.model_validate(data)
    assert activity.athlete_id == data["athlete_id"]
    assert activity.activity_type == ActivityType.RUNNING
    assert activity.title == "Morning Run"


def test_activity_create_missing_required():
    """Test ActivityCreate with missing required fields."""
    with pytest.raises(ValidationError):
        ActivityCreate.model_validate({
            "activity_type": "running",
            "title": "Morning Run",
        })


# ============================================================================
# ActivityUpdate Tests
# ============================================================================


def test_activity_update_valid():
    """Test ActivityUpdate with valid data."""
    data = {
        "title": "Updated Run",
        "description": "Updated description",
        "perceived_effort": "hard",
    }
    
    update = ActivityUpdate.model_validate(data)
    assert update.title == "Updated Run"
    assert update.perceived_effort == PerceivedEffort.HARD


def test_activity_update_partial():
    """Test ActivityUpdate with partial data."""
    data = {"title": "Updated Run"}
    update = ActivityUpdate.model_validate(data)
    assert update.title == "Updated Run"
    assert update.description is None


# ============================================================================
# ActivityResponse Tests
# ============================================================================


def test_activity_response_valid():
    """Test ActivityResponse with valid data."""
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)
    
    data = {
        "id": uuid.uuid4(),
        "athlete_id": uuid.uuid4(),
        "activity_type": "running",
        "title": "Morning Run",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": 3600,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    
    response = ActivityResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.activity_type == ActivityType.RUNNING
    assert response.duration_seconds == 3600


def test_activity_response_from_attributes():
    """Test ActivityResponse.from_attributes with model instance."""
    from app.models.activity import Activity
    
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)
    
    activity = Activity(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        activity_type=ActivityType.RUNNING,
        title="Morning Run",
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=3600,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    response = ActivityResponse.model_validate(activity)
    assert response.id == activity.id
    assert response.title == activity.title


# ============================================================================
# ActivityListParams Tests
# ============================================================================


def test_activity_list_params_valid():
    """Test ActivityListParams with valid data."""
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    
    data = {
        "activity_type": "running",
        "date_from": started_at,
        "date_to": started_at + timedelta(days=7),
        "limit": 20,
        "offset": 10,
    }
    
    params = ActivityListParams.model_validate(data)
    assert params.activity_type == ActivityType.RUNNING
    assert params.limit == 20
    assert params.offset == 10


def test_activity_list_params_defaults():
    """Test ActivityListParams with default values."""
    params = ActivityListParams.model_validate({})
    assert params.activity_type is None
    assert params.date_from is None
    assert params.date_to is None
    assert params.limit == 50
    assert params.offset == 0


# ============================================================================
# ActivityListResponse Tests
# ============================================================================


def test_activity_list_response_valid():
    """Test ActivityListResponse with valid data."""
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)
    
    activity_data = {
        "id": uuid.uuid4(),
        "athlete_id": uuid.uuid4(),
        "activity_type": "running",
        "title": "Morning Run",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": 3600,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    
    data = {
        "items": [activity_data],
        "total": 1,
    }
    
    response = ActivityListResponse.model_validate(data)
    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].title == "Morning Run"


# ============================================================================
# ActivityListParams Validation Tests
# ============================================================================


def test_activity_list_params_rejects_invalid_limit():
    """Verify invalid pagination limits fail."""
    # Test limit above maximum (1000)
    with pytest.raises(ValidationError) as exc_info:
        ActivityListParams.model_validate({
            "limit": 1001,
        })
    assert "limit" in str(exc_info.value)

    # Test limit below minimum (1)
    with pytest.raises(ValidationError) as exc_info:
        ActivityListParams.model_validate({
            "limit": 0,
        })
    assert "limit" in str(exc_info.value)

    # Test negative limit
    with pytest.raises(ValidationError) as exc_info:
        ActivityListParams.model_validate({
            "limit": -1,
        })
    assert "limit" in str(exc_info.value)


def test_activity_list_params_rejects_negative_offset():
    """Verify negative offsets fail."""
    with pytest.raises(ValidationError) as exc_info:
        ActivityListParams.model_validate({
            "offset": -1,
        })
    assert "offset" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ActivityListParams.model_validate({
            "offset": -100,
        })
    assert "offset" in str(exc_info.value)


def test_activity_list_params_accepts_valid_boundaries():
    """Verify valid boundary values are accepted."""
    # Test minimum valid limit
    params = ActivityListParams.model_validate({"limit": 1})
    assert params.limit == 1

    # Test maximum valid limit
    params = ActivityListParams.model_validate({"limit": 1000})
    assert params.limit == 1000

    # Test minimum valid offset
    params = ActivityListParams.model_validate({"offset": 0})
    assert params.offset == 0


# ============================================================================
# ActivityCreate Validation Tests
# ============================================================================


def test_activity_create_requires_mandatory_fields():
    """Verify required activity fields are enforced."""
    # Test missing athlete_id
    with pytest.raises(ValidationError) as exc_info:
        ActivityCreate.model_validate({
            "activity_type": "running",
            "title": "Morning Run",
        })
    assert "athlete_id" in str(exc_info.value)

    # Test with empty athlete_id
    with pytest.raises(ValidationError) as exc_info:
        ActivityCreate.model_validate({
            "athlete_id": None,
            "activity_type": "running",
        })
    assert "athlete_id" in str(exc_info.value)


def test_activity_create_with_valid_athlete_id():
    """Verify ActivityCreate accepts valid athlete_id."""
    data = {
        "athlete_id": uuid.uuid4(),
        "activity_type": "running",
        "title": "Morning Run",
    }

    activity = ActivityCreate.model_validate(data)
    assert activity.athlete_id == data["athlete_id"]
    assert activity.activity_type == ActivityType.RUNNING
    assert activity.title == "Morning Run"


def test_activity_create_rejects_invalid_activity_type():
    """Verify invalid activity_type enum fails validation."""
    with pytest.raises(ValidationError) as exc_info:
        ActivityCreate.model_validate({
            "athlete_id": uuid.uuid4(),
            "activity_type": "invalid_activity",
        })
    assert "activity_type" in str(exc_info.value)