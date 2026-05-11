"""Unit tests for AthleteService."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import hash_password, verify_password
from app.models.athlete import Athlete, AthleteProfile
from app.models.enums import AthleteStatus, Gender, UnitPreference
from app.schemas.athlete import AthleteCreate, AthleteUpdate, AthleteProfileUpdate
from app.services.athlete_service import AthleteService


# Use valid ISO country code strings
TEST_COUNTRY_CODE = "AU"
TEST_TIMEZONE = "America/New_York"


@pytest.fixture
def athlete_repo_mock():
    """Fixture for mocking AthleteRepository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.update = AsyncMock()
    mock.session = MagicMock()
    return mock


@pytest.fixture
def profile_repo_mock():
    """Fixture for mocking AthleteProfileRepository."""
    mock = MagicMock()
    mock.get_by_athlete_id = AsyncMock()
    mock.create = AsyncMock()
    mock.update = AsyncMock()
    return mock


@pytest.fixture
def athlete_service(athlete_repo_mock, profile_repo_mock):
    """Fixture for AthleteService with mocked repositories."""
    return AthleteService(athlete_repo_mock, profile_repo_mock)


# ============================================================================
# create_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_athlete(athlete_service, athlete_repo_mock):
    """Test successful athlete creation with password hashing."""
    athlete_id = uuid.uuid4()
    test_password = "securepassword123"
    athlete_data = AthleteCreate(
        email="test@example.com",
        password=test_password,
    )

    call_args = {}

    async def mock_create(**kwargs):
        call_args.update(kwargs)
        return Athlete(
            id=athlete_id,
            email="test@example.com",
            hashed_password=kwargs.get("hashed_password"),
            status=AthleteStatus.ONBOARDING,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        )

    athlete_repo_mock.create = mock_create

    result = await athlete_service.create_athlete(athlete_data)

    assert result.id == athlete_id
    assert result.email == "test@example.com"
    assert result.status == AthleteStatus.ONBOARDING

    assert "hashed_password" in call_args
    assert call_args["hashed_password"] is not None
    assert verify_password(test_password, call_args["hashed_password"])
    assert "password" not in call_args


@pytest.mark.asyncio
async def test_create_athlete_no_password(athlete_service, athlete_repo_mock):
    """Test athlete creation without password - should not hash None."""
    athlete_id = uuid.uuid4()
    athlete_data = AthleteCreate(
        email="test@example.com",
        password=None,
    )

    call_args = {}

    async def mock_create(**kwargs):
        call_args.update(kwargs)
        return Athlete(
            id=athlete_id,
            email="test@example.com",
            hashed_password=None,
            status=AthleteStatus.ONBOARDING,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        )

    athlete_repo_mock.create = mock_create

    result = await athlete_service.create_athlete(athlete_data)

    assert result.id == athlete_id
    assert result.email == "test@example.com"
    assert result.hashed_password is None
    assert "hashed_password" not in call_args


@pytest.mark.asyncio
async def test_create_athlete_email_only(athlete_service, athlete_repo_mock):
    """Test athlete creation with email only (no password field)."""
    athlete_id = uuid.uuid4()
    athlete_data = AthleteCreate(
        email="test@example.com",
    )

    call_args = {}

    async def mock_create(**kwargs):
        call_args.update(kwargs)
        return Athlete(
            id=athlete_id,
            email="test@example.com",
            hashed_password=None,
            status=AthleteStatus.ONBOARDING,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        )

    athlete_repo_mock.create = mock_create

    result = await athlete_service.create_athlete(athlete_data)

    assert result.id == athlete_id
    assert result.email == "test@example.com"
    assert result.hashed_password is None


# ============================================================================
# get_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_athlete(athlete_service, athlete_repo_mock):
    """Test successful athlete retrieval."""
    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email="test@example.com",
        status=AthleteStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    athlete_repo_mock.get_by_id = AsyncMock(return_value=athlete)

    result = await athlete_service.get_athlete(athlete_id)

    assert result == athlete
    athlete_repo_mock.get_by_id.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_athlete_not_found(athlete_service, athlete_repo_mock):
    """Test athlete retrieval when athlete does not exist."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=None)

    result = await athlete_service.get_athlete(athlete_id)

    assert result is None
    athlete_repo_mock.get_by_id.assert_called_once_with(athlete_id)


# ============================================================================
# get_athlete_with_profile Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_athlete_with_profile(athlete_service, athlete_repo_mock):
    """Test successful athlete retrieval with profile."""
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
        country_code=TEST_COUNTRY_CODE,
        timezone=TEST_TIMEZONE,
        language_code="en",
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )
    athlete.profile = profile

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = athlete
    athlete_repo_mock.session.execute = AsyncMock(return_value=mock_result)

    result = await athlete_service.get_athlete_with_profile(athlete_id)

    assert result == athlete
    assert result.profile == profile
    athlete_repo_mock.session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_athlete_with_profile_not_found(athlete_service, athlete_repo_mock):
    """Test athlete retrieval with profile when athlete does not exist."""
    athlete_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    athlete_repo_mock.session.execute = AsyncMock(return_value=mock_result)

    result = await athlete_service.get_athlete_with_profile(athlete_id)

    assert result is None


# ============================================================================
# update_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_athlete(athlete_service, athlete_repo_mock):
    """Test successful athlete update with password change."""
    athlete_id = uuid.uuid4()
    new_password = "newpassword123"

    call_args = {}

    async def mock_update(athlete_id, **kwargs):
        call_args.update(kwargs)
        return Athlete(
            id=athlete_id,
            email="test@example.com",
            hashed_password=kwargs.get("hashed_password"),
            status=kwargs.get("status", AthleteStatus.ACTIVE),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )

    athlete_repo_mock.update = mock_update

    update_data = AthleteUpdate(
        status=AthleteStatus.INACTIVE,
        password=new_password,
    )
    result = await athlete_service.update_athlete(athlete_id, update_data)

    assert result is not None
    assert result.id == athlete_id
    assert result.status == AthleteStatus.INACTIVE

    assert "hashed_password" in call_args
    assert verify_password(new_password, call_args["hashed_password"])
    assert "password" not in call_args


@pytest.mark.asyncio
async def test_update_athlete_partial(athlete_service, athlete_repo_mock):
    """Test athlete update with partial data (no password change)."""
    athlete_id = uuid.uuid4()

    call_args = {}

    async def mock_update(athlete_id, **kwargs):
        call_args.update(kwargs)
        return Athlete(
            id=athlete_id,
            email="test@example.com",
            status=kwargs.get("status", AthleteStatus.INACTIVE),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )

    athlete_repo_mock.update = mock_update

    update_data = AthleteUpdate(
        status=AthleteStatus.INACTIVE,
    )
    result = await athlete_service.update_athlete(athlete_id, update_data)

    assert result is not None
    assert result.id == athlete_id
    assert result.status == AthleteStatus.INACTIVE

    assert "hashed_password" not in call_args


@pytest.mark.asyncio
async def test_update_athlete_not_found(athlete_service, athlete_repo_mock):
    """Test athlete update when athlete does not exist."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.update = AsyncMock(return_value=None)

    update_data = AthleteUpdate(
        status=AthleteStatus.INACTIVE,
    )
    result = await athlete_service.update_athlete(athlete_id, update_data)

    assert result is None
    athlete_repo_mock.update.assert_called_once_with(athlete_id, status=AthleteStatus.INACTIVE)


# ============================================================================
# get_profile Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_profile(athlete_service, profile_repo_mock):
    """Test successful profile retrieval."""
    athlete_id = uuid.uuid4()
    profile = AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code=TEST_COUNTRY_CODE,
        timezone=TEST_TIMEZONE,
        language_code="en",
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    profile_repo_mock.get_by_athlete_id = AsyncMock(return_value=profile)

    result = await athlete_service.get_profile(athlete_id)

    assert result == profile
    profile_repo_mock.get_by_athlete_id.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_profile_not_found(athlete_service, profile_repo_mock):
    """Test profile retrieval when profile does not exist."""
    athlete_id = uuid.uuid4()

    profile_repo_mock.get_by_athlete_id = AsyncMock(return_value=None)

    result = await athlete_service.get_profile(athlete_id)

    assert result is None
    profile_repo_mock.get_by_athlete_id.assert_called_once_with(athlete_id)


# ============================================================================
# upsert_profile Tests
# ============================================================================


@pytest.mark.asyncio
async def test_upsert_profile_create(athlete_service, profile_repo_mock):
    """Test profile creation when profile does not exist."""
    athlete_id = uuid.uuid4()
    profile_data = AthleteProfileUpdate(
        first_name="John",
        last_name="Doe",
    )

    profile_repo_mock.get_by_athlete_id = AsyncMock(return_value=None)
    profile_repo_mock.create = AsyncMock(
        return_value=AthleteProfile(
            athlete_id=athlete_id,
            first_name="John",
            last_name="Doe",
            display_name="default",
            date_of_birth=date(1990, 1, 1),
            gender=Gender.MALE,
            country_code=TEST_COUNTRY_CODE,
            timezone=TEST_TIMEZONE,
            language_code="en",
            unit_preference=UnitPreference.METRIC,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        )
    )

    result = await athlete_service.upsert_profile(athlete_id, profile_data)

    assert result is not None
    assert result.athlete_id == athlete_id
    assert result.first_name == "John"
    assert result.last_name == "Doe"

    profile_repo_mock.create.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_profile_update(athlete_service, profile_repo_mock):
    """Test profile update when profile exists."""
    athlete_id = uuid.uuid4()
    existing_profile = AthleteProfile(
        athlete_id=athlete_id,
        first_name="Old",
        last_name="Name",
        display_name="oldname",
        date_of_birth=date(1985, 1, 1),
        gender=Gender.MALE,
        country_code=TEST_COUNTRY_CODE,
        timezone=TEST_TIMEZONE,
        language_code="en",
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    profile_repo_mock.get_by_athlete_id = AsyncMock(return_value=existing_profile)
    profile_repo_mock.update_by_athlete_id = AsyncMock(
        return_value=AthleteProfile(
            athlete_id=athlete_id,
            first_name="John",
            last_name="Doe",
            display_name="oldname",
            date_of_birth=date(1985, 1, 1),
            gender=Gender.MALE,
            country_code=TEST_COUNTRY_CODE,
            timezone=TEST_TIMEZONE,
            language_code="en",
            unit_preference=UnitPreference.METRIC,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 2, 0, 0, 0),
        )
    )

    profile_data = AthleteProfileUpdate(
        first_name="John",
        last_name="Doe",
    )
    result = await athlete_service.upsert_profile(athlete_id, profile_data)

    assert result is not None
    assert result.athlete_id == athlete_id
    assert result.first_name == "John"
    assert result.last_name == "Doe"

    profile_repo_mock.update_by_athlete_id.assert_called_once_with(
        athlete_id, first_name="John", last_name="Doe"
    )