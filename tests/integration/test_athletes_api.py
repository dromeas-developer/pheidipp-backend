"""Integration tests for Athletes API endpoints.

These tests verify API validation and error handling without database dependencies.
"""

import uuid

import pytest

from app.schemas.athlete import AthleteCreate, AthleteUpdate
from app.schemas.athlete_profile import AthleteProfileUpdate


# ============================================================================
# Schema Validation Tests
# ============================================================================


class TestAthleteSchemaValidation:
    """Tests for athlete schema validation."""

    def test_athlete_create_valid_email(self):
        """Test valid email passes validation."""
        data = AthleteCreate(email="test@example.com", password="securepassword123")
        assert data.email == "test@example.com"

    def test_athlete_create_invalid_email(self):
        """Test invalid email raises ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AthleteCreate(email="not-an-email", password="securepassword123")

    def test_athlete_create_password_too_short(self):
        """Test password too short raises ValidationError."""
        from pydantic import ValidationError
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
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AthleteCreate(email="", password="securepassword123")


class TestAthleteUpdateValidation:
    """Tests for athlete update schema validation."""

    def test_athlete_update_valid_status(self):
        """Test valid status passes validation."""
        from app.models.enums import AthleteStatus
        data = AthleteUpdate(status=AthleteStatus.INACTIVE)
        assert data.status == AthleteStatus.INACTIVE

    def test_athlete_update_invalid_status(self):
        """Test invalid status raises ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AthleteUpdate(status="invalid_status")

    def test_athlete_update_password_too_short(self):
        """Test password update too short raises ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AthleteUpdate(password="short")

    def test_athlete_update_partial(self):
        """Test partial update with only status."""
        from app.models.enums import AthleteStatus
        data = AthleteUpdate(status=AthleteStatus.SUSPENDED)
        assert data.status == AthleteStatus.SUSPENDED
        assert data.password is None


class TestAthleteProfileValidation:
    """Tests for athlete profile schema validation."""

    def test_profile_create_valid_gender(self):
        """Test valid gender passes validation."""
        from app.models.enums import Gender
        data = AthleteProfileUpdate(gender=Gender.MALE)
        assert data.gender == Gender.MALE

    def test_profile_create_invalid_gender(self):
        """Test invalid gender raises ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AthleteProfileUpdate(gender="invalid_gender")

    def test_profile_create_valid_dates(self):
        """Test valid date passes validation."""
        from datetime import date
        data = AthleteProfileUpdate(date_of_birth=date(1990, 1, 1))
        assert data.date_of_birth == date(1990, 1, 1)

    def test_profile_create_invalid_dates(self):
        """Test invalid date raises ValidationError."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AthleteProfileUpdate(date_of_birth="not-a-date")


# ============================================================================
# Enum Tests
# ============================================================================


class TestEnums:
    """Tests for enum values."""

    def test_athlete_status_values(self):
        """Test AthleteStatus enum has expected values."""
        from app.models.enums import AthleteStatus
        assert AthleteStatus.ONBOARDING.value == "onboarding"
        assert AthleteStatus.ACTIVE.value == "active"
        assert AthleteStatus.INACTIVE.value == "inactive"
        assert AthleteStatus.SUSPENDED.value == "suspended"

    def test_gender_values(self):
        """Test Gender enum has expected values."""
        from app.models.enums import Gender
        assert Gender.MALE.value == "male"
        assert Gender.FEMALE.value == "female"

    def test_unit_preference_values(self):
        """Test UnitPreference enum has expected values."""
        from app.models.enums import UnitPreference
        assert UnitPreference.METRIC.value == "metric"
        assert UnitPreference.IMPERIAL.value == "imperial"


# ============================================================================
# Model Tests
# ============================================================================


class TestModels:
    """Tests for model instantiation."""

    def test_athlete_model_minimal(self):
        """Test creating minimal Athlete model."""
        from datetime import datetime
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus

        athlete = Athlete(
            id=uuid.uuid4(),
            email="test@example.com",
            status=AthleteStatus.ACTIVE,
        )
        assert athlete.email == "test@example.com"
        assert athlete.status == AthleteStatus.ACTIVE

    def test_athlete_profile_model_fields(self):
        """Test creating AthleteProfile model."""
        from datetime import date, datetime
        from app.models.athlete_profile import AthleteProfile
        from app.models.enums import Gender, UnitPreference

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


# ============================================================================
# Response Schema Tests
# ============================================================================


class TestResponseSchemas:
    """Tests for response schema serialization."""

    def test_athlete_response_from_dict(self):
        """Test AthleteResponse from dictionary."""
        from datetime import datetime
        from app.schemas.athlete import AthleteResponse
        from app.models.enums import AthleteStatus

        data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = AthleteResponse.model_validate(data)
        assert response.email == "test@example.com"
        assert response.status == AthleteStatus.ACTIVE

    def test_athlete_with_profile_response(self):
        """Test AthleteWithProfileResponse with nested profile."""
        from datetime import datetime, date
        from app.schemas.athlete_profile import AthleteWithProfileResponse

        data = {
            "id": str(uuid.uuid4()),
            "email": "test@example.com",
            "status": "active",
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