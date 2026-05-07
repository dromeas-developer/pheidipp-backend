"""Unit tests for AthleteService."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.athlete import Athlete, AthleteProfile
from app.models.enums import AthleteStatus, Gender, CountryCode, Timezone, LanguageCode, UnitPreference
from app.repositories.athlete_repository import AthleteRepository, AthleteProfileRepository
from app.schemas.athlete import AthleteCreate, AthleteUpdate, AthleteProfileUpdate
from app.services.athlete_service import AthleteService


@pytest.fixture
def athlete_repo_mock():
    """Fixture for mocking AthleteRepository."""
    return MagicMock(spec=AthleteRepository)


@pytest.fixture
def profile_repo_mock():
    """Fixture for mocking AthleteProfileRepository."""
    return MagicMock(spec=AthleteProfileRepository)


@pytest.fixture
def athlete_service(athlete_repo_mock, profile_repo_mock):
    """Fixture for AthleteService with mocked repositories."""
    return AthleteService(athlete_repo_mock, profile_repo_mock)


# ============================================================================
# create_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_athlete(athlete_service, athlete_repo_mock):
    """Test successful athlete creation."""
    # Setup
    athlete_id = uuid.uuid4()
    athlete_data = AthleteCreate(
        email="test@example.com",
        password="securepassword123",
    )
    
    # Mock repository
    athlete_repo_mock.create.return_value = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.ONBOARDING,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    # Execute
    result = await athlete_service.create_athlete(athlete_data)
    
    # Verify
    assert result.id == athlete_id
    assert result.email == "test@example.com"
    assert result.status == AthleteStatus.ONBOARDING
    
    # Check that password was hashed and not stored directly
    args, kwargs = athlete_repo_mock.create.call_args
    assert "hashed_password" in kwargs
    assert kwargs["hashed_password"] == hash_password("securepassword123")
    assert "password" not in kwargs


@pytest.mark.asyncio
async def test_create_athlete_no_password(athlete_service, athlete_repo_mock):
    """Test athlete creation without password."""
    # Setup
    athlete_id = uuid.uuid4()
    athlete_data = AthleteCreate(
        email="test@example.com",
        password=None,
    )
    
    # Mock repository
    athlete_repo_mock.create.return_value = Athlete(
        id=athlete_id,
        email="test@example.com",
        hashed_password=None,
        status=AthleteStatus.ONBOARDING,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    # Execute
    result = await athlete_service.create_athlete(athlete_data)
    
    # Verify
    assert result.id == athlete_id
    assert result.email == "test@example.com"
    assert result.hashed_password is None
    
    # Check that no password was passed to repository
    args, kwargs = athlete_repo_mock.create.call_args
    assert "hashed_password" not in kwargs


# ============================================================================
# get_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_athlete(athlete_service, athlete_repo_mock):
    """Test successful athlete retrieval."""
    # Setup
    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    # Mock repository
    athlete_repo_mock.get_by_id.return_value = athlete
    
    # Execute
    result = await athlete_service.get_athlete(athlete_id)
    
    # Verify
    assert result == athlete
    athlete_repo_mock.get_by_id.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_athlete_not_found(athlete_service, athlete_repo_mock):
    """Test athlete retrieval when athlete does not exist."""
    # Setup
    athlete_id = uuid.uuid4()
    
    # Mock repository
    athlete_repo_mock.get_by_id.return_value = None
    
    # Execute
    result = await athlete_service.get_athlete(athlete_id)
    
    # Verify
    assert result is None
    athlete_repo_mock.get_by_id.assert_called_once_with(athlete_id)


# ============================================================================
# get_athlete_with_profile Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_athlete_with_profile(athlete_service, athlete_repo_mock):
    """Test successful athlete retrieval with profile."""
    # Setup
    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    profile = AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code=CountryCode.US,
        timezone=Timezone.America_New_York,
        language_code=LanguageCode.en,
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    athlete.profile = profile
    
    # Mock repository
    athlete_repo_mock.session.execute.return_value.scalar_one_or_none.return_value = athlete
    
    # Execute
    result = await athlete_service.get_athlete_with_profile(athlete_id)
    
    # Verify
    assert result == athlete
    assert result.profile == profile


@pytest.mark.asyncio
async def test_get_athlete_with_profile_not_found(athlete_service, athlete_repo_mock):
    """Test athlete retrieval with profile when athlete does not exist."""
    # Setup
    athlete_id = uuid.uuid4()
    
    # Mock repository
    athlete_repo_mock.session.execute.return_value.scalar_one_or_none.return_value = None
    
    # Execute
    result = await athlete_service.get_athlete_with_profile(athlete_id)
    
    # Verify
    assert result is None


# ============================================================================
# update_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_athlete(athlete_service, athlete_repo_mock):
    """Test successful athlete update."""
    # Setup
    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    update_data = AthleteUpdate(
        status=AthleteStatus.INACTIVE,
        password="newpassword123",
    )
    
    # Mock repository
    athlete_repo_mock.update.return_value = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.INACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 2, 0, 0, 0),
    )
    
    # Execute
    result = await athlete_service.update_athlete(athlete_id, update_data)
    
    # Verify
    assert result is not None
    assert result.id == athlete_id
    assert result.status == AthleteStatus.INACTIVE
    
    # Check that password was hashed and status was updated
    args, kwargs = athlete_repo_mock.update.call_args
    assert kwargs["status"] == AthleteStatus.INACTIVE
    assert "hashed_password" in kwargs
    assert kwargs["hashed_password"] == hash_password("newpassword123")
    assert "password" not in kwargs


@pytest.mark.asyncio
async def test_update_athlete_partial(athlete_service, athlete_repo_mock):
    """Test athlete update with partial data."""
    # Setup
    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    update_data = AthleteUpdate(
        status=AthleteStatus.INACTIVE,
    )
    
    # Mock repository
    athlete_repo_mock.update.return_value = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.INACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 2, 0, 0, 0),
    )
    
    # Execute
    result = await athlete_service.update_athlete(athlete_id, update_data)
    
    # Verify
    assert result is not None
    assert result.id == athlete_id
    assert result.status == AthleteStatus.INACTIVE
    
    # Check that only status was updated
    args, kwargs = athlete_repo_mock.update.call_args
    assert kwargs["status"] == AthleteStatus.INACTIVE
    assert "hashed_password" not in kwargs


@pytest.mark.asyncio
async def test_update_athlete_not_found(athlete_service, athlete_repo_mock):
    """Test athlete update when athlete does not exist."""
    # Setup
    athlete_id = uuid.uuid4()
    update_data = AthleteUpdate(
        status=AthleteStatus.INACTIVE,
    )
    
    # Mock repository
    athlete_repo_mock.update.return_value = None
    
    # Execute
    result = await athlete_service.update_athlete(athlete_id, update_data)
    
    # Verify
    assert result is None
    athlete_repo_mock.update.assert_called_once_with(athlete_id, status=AthleteStatus.INACTIVE)


# ============================================================================
# get_profile Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_profile(athlete_service, profile_repo_mock):
    """Test successful profile retrieval."""
    # Setup
    athlete_id = uuid.uuid4()
    profile = AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code=CountryCode.US,
        timezone=Timezone.America_New_York,
        language_code=LanguageCode.en,
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    # Mock repository
    profile_repo_mock.get_by_athlete_id.return_value = profile
    
    # Execute
    result = await athlete_service.get_profile(athlete_id)
    
    # Verify
    assert result == profile
    profile_repo_mock.get_by_athlete_id.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_profile_not_found(athlete_service, profile_repo_mock):
    """Test profile retrieval when profile does not exist."""
    # Setup
    athlete_id = uuid.uuid4()
    
    # Mock repository
    profile_repo_mock.get_by_athlete_id.return_value = None
    
    # Execute
    result = await athlete_service.get_profile(athlete_id)
    
    # Verify
    assert result is None
    profile_repo_mock.get_by_athlete_id.assert_called_once_with(athlete_id)


# ============================================================================
# upsert_profile Tests
# ============================================================================


@pytest.mark.asyncio
async def test_upsert_profile_create(athlete_service, profile_repo_mock):
    """Test profile creation when profile does not exist."""
    # Setup
    athlete_id = uuid.uuid4()
    profile_data = AthleteProfileUpdate(
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code=CountryCode.US,
        timezone=Timezone.America_New_York,
        language_code=LanguageCode.en,
        unit_preference=UnitPreference.METRIC,
    )
    
    # Mock repository
    profile_repo_mock.get_by_athlete_id.return_value = None
    profile_repo_mock.create.return_value = AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code=CountryCode.US,
        timezone=Timezone.America_New_York,
        language_code=LanguageCode.en,
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    
    # Execute
    result = await athlete_service.upsert_profile(athlete_id, profile_data)
    
    # Verify
    assert result is not None
    assert result.athlete_id == athlete_id
    assert result.first_name == "John"
    
    # Check that create was called
    profile_repo_mock.create.assert_called_once()
    profile_repo_mock.update.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_profile_update(athlete_service, profile_repo_mock):
    """Test profile update when profile exists."""
    # Setup
    athlete_id = uuid.uuid4()
    existing_profile = AthleteProfile(
        athlete_id=athlete_id,
        first_name="Old",
        last_name="Name",
        display_name="oldname",
        date_of_birth=date(1985, 1, 1),
        gender=Gender.MALE,
        country_code=CountryCode.US,
        timezone=Timezone.America_New_York,
        language_code=LanguageCode.en,
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    profile_data = AthleteProfileUpdate(
        first_name="John",
        last_name="Doe",
    )
    
    # Mock repository
    profile_repo_mock.get_by_athlete_id.return_value = existing_profile
    profile_repo_mock.update.return_value = AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="oldname",  # Should keep existing value
        date_of_birth=date(1985, 1, 1),  # Should keep existing value
        gender=Gender.MALE,
        country_code=CountryCode.US,
        timezone=Timezone.America_New_York,
        language_code=LanguageCode.en,
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 2, 0, 0, 0),
    )
    
    # Execute
    result = await athlete_service.upsert_profile(athlete_id, profile_data)
    
    # Verify
    assert result is not None
    assert result.athlete_id == athlete_id
    assert result.first_name == "John"
    assert result.last_name == "Doe"
    
    # Check that update was called with correct data
    profile_repo_mock.update.assert_called_once_with(athlete_id, first_name="John", last_name="Doe")
    profile_repo_mock.create.assert_not_called()