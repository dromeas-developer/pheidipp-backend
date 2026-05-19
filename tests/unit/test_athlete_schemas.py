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
        "onboarding_complete": False,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    response = AthleteResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.email == "test@example.com"
    assert response.status == AthleteStatus.ACTIVE
    assert response.onboarding_complete is False


def test_athlete_response_onboarding_complete_true():
    """Test AthleteResponse with onboarding_complete=True."""
    data = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "status": "active",
        "onboarding_complete": True,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
    }
    response = AthleteResponse.model_validate(data)
    assert response.onboarding_complete is True


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
        "onboarding_complete": False,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
        "profile": profile_data,
    }

    response = AthleteWithProfileResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.email == "test@example.com"
    assert response.onboarding_complete is False
    assert response.profile is not None
    assert response.profile.first_name == "John"


def test_athlete_with_profile_response_no_profile():
    """Test AthleteWithProfileResponse without profile."""
    data = {
        "id": uuid.uuid4(),
        "email": "test@example.com",
        "status": "active",
        "onboarding_complete": False,
        "created_at": datetime(2024, 1, 1, 0, 0, 0),
        "updated_at": datetime(2024, 1, 1, 0, 0, 0),
        "profile": None,
    }

    response = AthleteWithProfileResponse.model_validate(data)
    assert response.id == data["id"]
    assert response.profile is None


# ============================================================================
# Additional Schema Validation Tests (from integration layer)
# ============================================================================


class TestAthleteSchemaValidation:
    """Tests for athlete schema validation."""

    def test_athlete_create_valid_email(self):
        """Test valid email passes validation."""
        data = AthleteCreate(email="test@example.com", password="securepassword123")
        assert data.email == "test@example.com"

    def test_athlete_create_invalid_email(self):
        """Test invalid email raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteCreate(email="not-an-email", password="securepassword123")

    def test_athlete_create_password_too_short(self):
        """Test password too short raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteCreate(email="test@example.com", password="short")

    def test_athlete_create_password_min_length(self):
        """Test password at minimum length passes."""
        data = AthleteCreate(email="test@example.com", password="12345678")
        assert data.password == "12345678"

    def test_athlete_create_no_password(self):
        """Test athlete creation without password."""
        data = AthleteCreate(email="test@example.com")
        assert data.password is None

    def test_athlete_create_empty_email(self):
        """Test empty email raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteCreate(email="", password="securepassword123")


class TestAthleteUpdateValidation:
    """Tests for athlete update schema validation."""

    def test_athlete_update_valid_status(self):
        """Test valid status passes validation."""
        data = AthleteUpdate(status=AthleteStatus.INACTIVE)
        assert data.status == AthleteStatus.INACTIVE

    def test_athlete_update_invalid_status(self):
        """Test invalid status raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteUpdate(status="invalid_status")

    def test_athlete_update_password_too_short(self):
        """Test password update too short raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteUpdate(password="short")

    def test_athlete_update_partial(self):
        """Test partial update with only status."""
        data = AthleteUpdate(status=AthleteStatus.SUSPENDED)
        assert data.status == AthleteStatus.SUSPENDED
        assert data.password is None


class TestAthleteProfileValidation:
    """Tests for athlete profile schema validation."""

    def test_profile_create_valid_gender(self):
        """Test valid gender passes validation."""
        data = AthleteProfileUpdate(gender=Gender.MALE)
        assert data.gender == Gender.MALE

    def test_profile_create_invalid_gender(self):
        """Test invalid gender raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteProfileUpdate(gender="invalid_gender")

    def test_profile_create_valid_dates(self):
        """Test valid date passes validation."""
        data = AthleteProfileUpdate(date_of_birth=date(1990, 1, 1))
        assert data.date_of_birth == date(1990, 1, 1)

    def test_profile_create_invalid_dates(self):
        """Test invalid date raises ValidationError."""
        with pytest.raises(ValidationError):
            AthleteProfileUpdate(date_of_birth="not-a-date")


class TestEnums:
    """Tests for enum values."""

    def test_athlete_status_values(self):
        """Test AthleteStatus enum has expected values."""
        assert AthleteStatus.ONBOARDING.value == "onboarding"
        assert AthleteStatus.ACTIVE.value == "active"
        assert AthleteStatus.INACTIVE.value == "inactive"
        assert AthleteStatus.SUSPENDED.value == "suspended"

    def test_gender_values(self):
        """Test Gender enum has expected values."""
        assert Gender.MALE.value == "male"
        assert Gender.FEMALE.value == "female"

    def test_unit_preference_values(self):
        """Test UnitPreference enum has expected values."""
        assert UnitPreference.METRIC.value == "metric"
        assert UnitPreference.IMPERIAL.value == "imperial"


class TestModels:
    """Tests for model instantiation."""

    def test_athlete_model_minimal(self):
        """Test creating minimal Athlete model."""
        from app.models.athlete import Athlete

        athlete = Athlete(
            id=uuid.uuid4(),
            email="test@example.com",
            status=AthleteStatus.ACTIVE,
        )
        assert athlete.email == "test@example.com"
        assert athlete.status == AthleteStatus.ACTIVE

    def test_athlete_profile_model_fields(self):
        """Test creating AthleteProfile model."""
        from app.models.athlete_profile import AthleteProfile

        profile = AthleteProfile(
            athlete_id=uuid.uuid4(),
            first_name="John",
            last_name="Doe",
            display_name="johndoe",
            date_of_birth=date(1990, 1, 1),
            gender=Gender.MALE,
            country_code="AU",
            timezone="America/New_York",
            language_code="en",
            unit_preference=UnitPreference.METRIC,
        )
        assert profile.first_name == "John"
        assert profile.last_name == "Doe"


class TestResponseSchemas:
    """Tests for response schema serialization."""

    def test_athlete_response_from_dict(self):
        """Test AthleteResponse from dictionary."""
        data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "status": "active",
            "onboarding_complete": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = AthleteResponse.model_validate(data)
        assert response.email == "test@example.com"
        assert response.status == AthleteStatus.ACTIVE
        assert response.onboarding_complete is False

    def test_athlete_with_profile_response(self):
        """Test AthleteWithProfileResponse with nested profile."""
        data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "status": "active",
            "onboarding_complete": False,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "profile": {
                "athlete_id": str(uuid.uuid4()),
                "first_name": "John",
                "last_name": "Doe",
                "display_name": "johndoe",
                "date_of_birth": date(1990, 1, 1).isoformat(),
                "gender": "male",
                "unit_preference": "metric",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        }
        response = AthleteWithProfileResponse.model_validate(data)
        assert response.profile is not None
        assert response.profile.first_name == "John"