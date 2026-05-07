"""Unit tests for AthleteWellness schemas."""

import uuid
from datetime import date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.enums import WellnessSource
from app.schemas.wellness import (
    WellnessBase,
    WellnessCreate,
    WellnessUpdate,
    WellnessResponse,
    WellnessListParams,
    WellnessListResponse,
)


# ============================================================================
# WellnessBase Tests
# ============================================================================


def test_wellness_base_valid():
    """Test WellnessBase with valid data."""
    data = {
        "metric_date": date(2024, 1, 1),
        "sleep_total": 480,
        "sleep_light": 240,
        "sleep_deep": 120,
        "sleep_rem": 90,
        "sleep_awake": 30,
        "resting_hr": 55,
        "hrv": 65,
        "weight": 75.5,
        "source": "manual",
        "timezone": "UTC",
    }
    
    wellness = WellnessBase.model_validate(data)
    assert wellness.metric_date == date(2024, 1, 1)
    assert wellness.sleep_total == 480
    assert wellness.source == WellnessSource.MANUAL
    assert wellness.timezone == "UTC"


def test_wellness_base_partial():
    """Test WellnessBase with partial data."""
    data = {
        "metric_date": date(2024, 1, 1),
        "source": "oura",
        "timezone": "America/New_York",
    }
    
    wellness = WellnessBase.model_validate(data)
    assert wellness.metric_date == date(2024, 1, 1)
    assert wellness.source == WellnessSource.OURA
    assert wellness.timezone == "America/New_York"
    assert wellness.sleep_total is None
    assert wellness.resting_hr is None


def test_wellness_base_invalid_source():
    """Test WellnessBase with invalid source."""
    with pytest.raises(ValidationError):
        WellnessBase.model_validate({
            "metric_date": date(2024, 1, 1),
            "source": "invalid_source",
            "timezone": "UTC",
        })


def test_wellness_base_missing_required():
    """Test WellnessBase with missing required fields."""
    with pytest.raises(ValidationError):
        WellnessBase.model_validate({
            "sleep_total": 480,
            # Missing metric_date, source, timezone
        })


# ============================================================================
# WellnessCreate Tests
# ============================================================================


def test_wellness_create_valid():
    """Test WellnessCreate with valid data."""
    data = {
        "athlete_id": uuid.uuid4(),
        "metric_date": date(2024, 1, 1),
        "sleep_total": 480,
        "source": "manual",
        "timezone": "UTC",
    }
    
    wellness = WellnessCreate.model_validate(data)
    assert wellness.athlete_id == data["athlete_id"]
    assert wellness.metric_date == date(2024, 1, 1)
    assert wellness.source == WellnessSource.MANUAL


def test_wellness_create_missing_required():
    """Test WellnessCreate with missing required fields."""
    with pytest.raises(ValidationError):
        WellnessCreate.model_validate({
            "metric_date": date(2024, 1, 1),
            "source": "manual",
            "timezone": "UTC",
            # Missing athlete_id
        })


# ============================================================================
# WellnessUpdate Tests
# ============================================================================


def test_wellness_update_valid():
    """Test WellnessUpdate with valid data."""
    data = {
        "sleep_total": 500,
        "resting_hr": 58,
        "source": "garmin",
    }
    
    update = WellnessUpdate.model_validate(data)
    assert update.sleep_total == 500
    assert update.resting_hr == 58
    assert update.source == WellnessSource.GARMIN


def test_wellness_update_partial():
    """Test WellnessUpdate with partial data."""
    data = {"sleep_total": 500}
    update = WellnessUpdate.model_validate(data)
    assert update.sleep_total == 500
    assert update.resting_hr is None
    assert update.source is None


# ============================================================================
# WellnessResponse Tests
# ============================================================================


def test_wellness_response_valid():
    """Test WellnessResponse with valid data."""
    data = {
        "id": uuid.uuid4(),
        "athlete_id": uuid.uuid4(),
        "metric_date": date(2024, 1, 1),
        "sleep_total": 480,
        "sleep_light": 240,
        "sleep_deep": 120,
        "sleep_rem": 90,
        "sleep_awake": 30,
        "resting_hr": 55,
        "hrv": 65,
        "weight": 75.5,
        "source": "manual",
        "timezone": "UTC",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    
    response = WellnessResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.metric_date == date(2024, 1, 1)
    assert response.sleep_total == 480
    assert response.source == WellnessSource.MANUAL


def test_wellness_response_from_attributes():
    """Test WellnessResponse.from_attributes with model instance."""
    from app.models.wellness import AthleteWellness
    
    wellness = AthleteWellness(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        metric_date=date(2024, 1, 1),
        sleep_total=480,
        sleep_light=240,
        sleep_deep=120,
        sleep_rem=90,
        sleep_awake=30,
        resting_hr=55,
        hrv=65,
        weight=75.5,
        source=WellnessSource.MANUAL,
        timezone="UTC",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    response = WellnessResponse.model_validate(wellness)
    assert response.id == wellness.id
    assert response.metric_date == wellness.metric_date
    assert response.sleep_total == wellness.sleep_total


# ============================================================================
# WellnessListParams Tests
# ============================================================================


def test_wellness_list_params_valid():
    """Test WellnessListParams with valid data."""
    data = {
        "date_from": date(2024, 1, 1),
        "date_to": date(2024, 1, 31),
        "limit": 20,
        "offset": 10,
    }
    
    params = WellnessListParams.model_validate(data)
    assert params.date_from == date(2024, 1, 1)
    assert params.date_to == date(2024, 1, 31)
    assert params.limit == 20
    assert params.offset == 10


def test_wellness_list_params_defaults():
    """Test WellnessListParams with default values."""
    params = WellnessListParams.model_validate({})
    assert params.date_from is None
    assert params.date_to is None
    assert params.limit == 50
    assert params.offset == 0


def test_wellness_list_params_invalid_limit():
    """Test WellnessListParams with invalid limit."""
    with pytest.raises(ValidationError):
        WellnessListParams.model_validate({"limit": 2000})  # Max is 1000


# ============================================================================
# WellnessListResponse Tests
# ============================================================================


def test_wellness_list_response_valid():
    """Test WellnessListResponse with valid data."""
    wellness_data = {
        "id": uuid.uuid4(),
        "athlete_id": uuid.uuid4(),
        "metric_date": date(2024, 1, 1),
        "sleep_total": 480,
        "source": "manual",
        "timezone": "UTC",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    
    data = {
        "items": [wellness_data],
        "total": 1,
    }
    
    response = WellnessListResponse.model_validate(data)
    assert response.total == 1
    assert len(response.items) == 1
    assert response.items[0].metric_date == date(2024, 1, 1)
    assert response.items[0].sleep_total == 480