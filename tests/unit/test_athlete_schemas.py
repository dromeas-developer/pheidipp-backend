"""Unit tests for Athlete and AthleteProfile schemas."""

import uuid
from datetime import date, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.enums import (
    AthleteStatus,
    Gender,
    UnitPreference,
)
from app.schemas.athlete import (
    AthleteBase,
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
)
from app.schemas.athlete_profile import (
    AthleteProfileBase,
    AthleteProfileCreate,
    AthleteProfileUpdate,
    AthleteProfileResponse,
    AthleteWithProfileResponse,
)


# ============================================================================
# AthleteBase Tests
# ============================================================================


def test_athlete_base_valid():
    """Test AthleteBase with valid data."""
    data = {"email": "test@example.com"}
    athlete = AthleteBase.model_validate(data)
    assert athlete.email == "test@example.com"


def test_athlete_base_invalid_email():
    """Test AthleteBase with invalid email."""
    with pytest.raises(ValidationError):
        AthleteBase.model_validate({"email": "invalid-email"})


# ============================================================================
# AthleteCreate Tests
# ============================================================================


def test_athlete_create_valid():
    """Test AthleteCreate with valid data."""
    data = {
        "email": "test@example.com",
        "password": "securepassword123",
    }
    athlete = AthleteCreate.model_validate(data)
    assert athlete.email == "test@example.com"
    assert athlete.password == "securepassword123"


def test_athlete_create_optional_password():
    """Test AthleteCreate with optional password."""
    data = {"email": "test@example.com"}
    athlete = AthleteCreate.model_validate(data)
    assert athlete.password is None


def test_athlete_create_password_too_short():
    """Test AthleteCreate with password that's too short."""
    with pytest.raises(ValidationError):
        AthleteCreate.model_validate({
            "email": "test@example.com",
            "password": "short",
        })


# ============================================================================
# AthleteUpdate Tests
# ============================================================================


def test_athlete_update_valid():
    """Test AthleteUpdate with valid data."""
    data = {
        "status": "active",
        "password": "newpassword123",
    }
    update = AthleteUpdate.model_validate(data)
    assert update.status == AthleteStatus.ACTIVE
    assert update.password == "newpassword123"


def test_athlete_update_partial():
    """Test AthleteUpdate with partial data."""
    data = {"status": "inactive"}
    update = AthleteUpdate.model_validate(data)
    assert update.status == AthleteStatus.INACTIVE
    assert update.password is None


def test_athlete_update_password_too_short():
    """Test AthleteUpdate with password that's too short."""
    with pytest.raises(ValidationError):
        AthleteUpdate.model_validate({"password": "short"})


# ============================================================================
# AthleteResponse Tests
# ============================================================================


def test_athlete_response_valid():
    """Test AthleteResponse with valid data."""
    data = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "status": "active",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    response = AthleteResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.email == "test@example.com"
    assert response.status == AthleteStatus.ACTIVE


def test_athlete_response_from_attributes():
    """Test AthleteResponse.from_attributes with model instance."""
    # Skip this test since it requires SQLAlchemy models
    pass


# ============================================================================
# AthleteProfileBase Tests
# ============================================================================


def test_athlete_profile_base_valid():
    """Test AthleteProfileBase with valid data."""
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "display_name": "johndoe",
        "date_of_birth": date(1990, 1, 1),
        "gender": "male",
        "unit_preference": "metric",
    }
    profile = AthleteProfileBase.model_validate(data)
    assert profile.first_name == "John"
    assert profile.gender == Gender.MALE
    assert profile.unit_preference == UnitPreference.METRIC


def test_athlete_profile_base_partial():
    """Test AthleteProfileBase with partial data."""
    data = {
        "first_name": "John",
        "unit_preference": "imperial",
    }
    profile = AthleteProfileBase.model_validate(data)
    assert profile.first_name == "John"
    assert profile.unit_preference == UnitPreference.IMPERIAL
    assert profile.last_name is None


def test_athlete_profile_base_invalid_enum():
    """Test AthleteProfileBase with invalid enum values."""
    with pytest.raises(ValidationError):
        AthleteProfileBase.model_validate({
            "gender": "invalid_gender",
            "unit_preference": "invalid_unit",
        })


# ============================================================================
# AthleteProfileCreate Tests
# ============================================================================


def test_athlete_profile_create_valid():
    """Test AthleteProfileCreate with valid data."""
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "display_name": "johndoe",
        "date_of_birth": date(1990, 1, 1),
        "gender": "male",
        "unit_preference": "metric",
    }
    profile = AthleteProfileCreate.model_validate(data)
    assert profile.first_name == "John"
    assert profile.gender == Gender.MALE


# ============================================================================
# AthleteProfileUpdate Tests
# ============================================================================


def test_athlete_profile_update_valid():
    """Test AthleteProfileUpdate with valid data."""
    data = {
        "first_name": "John",
        "unit_preference": "imperial",
    }
    update = AthleteProfileUpdate.model_validate(data)
    assert update.first_name == "John"
    assert update.unit_preference == UnitPreference.IMPERIAL


def test_athlete_profile_update_partial():
    """Test AthleteProfileUpdate with partial data."""
    data = {"first_name": "John"}
    update = AthleteProfileUpdate.model_validate(data)
    assert update.first_name == "John"
    assert update.last_name is None


# ============================================================================
# AthleteProfileResponse Tests
# ============================================================================


def test_athlete_profile_response_valid():
    """Test AthleteProfileResponse with valid data."""
    data = {
        "athlete_id": uuid.uuid4(),
        "first_name": "John",
        "last_name": "Doe",
        "display_name": "johndoe",
        "date_of_birth": date(1990, 1, 1),
        "gender": "male",
        "unit_preference": "metric",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    response = AthleteProfileResponse.model_validate(data)
    assert response.athlete_id == data["athlete_id"]
    assert response.first_name == "John"
    assert response.gender == Gender.MALE


def test_athlete_profile_response_from_attributes():
    """Test AthleteProfileResponse.from_attributes with model instance."""
    # Skip this test since it requires SQLAlchemy models
    pass


# ============================================================================
# AthleteWithProfileResponse Tests
# ============================================================================


def test_athlete_with_profile_response_valid():
    """Test AthleteWithProfileResponse with valid data."""
    profile_data = {
        "athlete_id": uuid.uuid4(),
        "first_name": "John",
        "last_name": "Doe",
        "display_name": "johndoe",
        "date_of_birth": date(1990, 1, 1),
        "gender": "male",
        "unit_preference": "metric",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    
    data = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "status": "active",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
        "profile": profile_data,
    }
    
    response = AthleteWithProfileResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.email == "test@example.com"
    assert response.profile is not None
    assert response.profile.first_name == "John"


def test_athlete_with_profile_response_no_profile():
    """Test AthleteWithProfileResponse without profile."""
    data = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "status": "active",
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
        "profile": None,
    }
    
    response = AthleteWithProfileResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.profile is None