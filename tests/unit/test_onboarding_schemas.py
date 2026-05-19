"""Unit tests for Onboarding schemas."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.onboarding import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
)


# ============================================================================
# OnboardingRequest Tests
# ============================================================================


def test_onboarding_request_valid():
    """Test OnboardingRequest with valid nested preferences and training_block."""
    data = {
        "preferences": {
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
        },
        "training_block": {
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
        },
    }
    request = OnboardingRequest.model_validate(data)
    assert request.preferences is not None
    assert request.training_block is not None
    assert request.preferences.weekly_schedule is not None


def test_onboarding_request_missing_preferences():
    """Test OnboardingRequest rejects missing preferences."""
    data = {
        "training_block": {
            "goal_type": "race",
        },
    }
    with pytest.raises(ValidationError):
        OnboardingRequest.model_validate(data)


def test_onboarding_request_missing_training_block():
    """Test OnboardingRequest rejects missing training_block."""
    data = {
        "preferences": {
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
        },
    }
    with pytest.raises(ValidationError):
        OnboardingRequest.model_validate(data)


def test_onboarding_request_invalid_weekly_schedule():
    """Test OnboardingRequest rejects invalid weekly_schedule (propagates nested validation error)."""
    data = {
        "preferences": {
            "weekly_schedule": {
                "days": {
                    "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                    # Missing required days - should fail validation
                },
                "available_days_count": 1,
            },
        },
        "training_block": {
            "goal_type": "race",
        },
    }
    with pytest.raises(ValidationError):
        OnboardingRequest.model_validate(data)


# ============================================================================
# OnboardingResponse Tests
# ============================================================================


def test_onboarding_response_valid():
    """Test OnboardingResponse with all fields including twin_state=None."""
    data = {
        "onboarding_complete": True,
        "preferences": {
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
        },
        "training_block": {
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
        },
        "twin_state": None,
    }
    response = OnboardingResponse.model_validate(data)
    assert response.onboarding_complete is True
    assert response.preferences is not None
    assert response.training_block is not None
    assert response.twin_state is None


def test_onboarding_response_twin_state_optional():
    """Test that twin_state is optional and defaults to None."""
    data = {
        "onboarding_complete": True,
        "preferences": {
            "id": str(uuid.uuid4()),
            "athlete_id": str(uuid.uuid4()),
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        },
        "training_block": {
            "id": str(uuid.uuid4()),
            "athlete_id": str(uuid.uuid4()),
            "status": "active",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        },
    }
    response = OnboardingResponse.model_validate(data)
    assert response.twin_state is None


# ============================================================================
# OnboardingStatusResponse Tests
# ============================================================================


def test_onboarding_status_response_not_onboarded():
    """Test OnboardingStatusResponse with onboarding_complete=False and null nested objects."""
    data = {
        "onboarding_complete": False,
        "preferences": None,
        "training_block": None,
        "twin_state": None,
    }
    response = OnboardingStatusResponse.model_validate(data)
    assert response.onboarding_complete is False
    assert response.preferences is None
    assert response.training_block is None
    assert response.twin_state is None


def test_onboarding_status_response_onboarded():
    """Test OnboardingStatusResponse with onboarding_complete=True and populated nested objects."""
    data = {
        "onboarding_complete": True,
        "preferences": {
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
        },
        "training_block": {
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
        },
        "twin_state": None,
    }
    response = OnboardingStatusResponse.model_validate(data)
    assert response.onboarding_complete is True
    assert response.preferences is not None
    assert response.training_block is not None
    assert response.twin_state is None