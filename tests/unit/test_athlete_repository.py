"""Unit tests for AthleteRepository."""

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.models.athlete import Athlete, AthleteProfile
from app.models.enums import AthleteStatus, Gender, CountryCode, Timezone, LanguageCode, UnitPreference
from app.repositories.athlete_repository import AthleteRepository, AthleteProfileRepository


@pytest_asyncio.fixture
async def db_session():
    """Create an async in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        from app.db.base import Base
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def athlete_repo(db_session):
    """Fixture for AthleteRepository with a test database session."""
    return AthleteRepository(db_session)


@pytest_asyncio.fixture
async def profile_repo(db_session):
    """Fixture for AthleteProfileRepository with a test database session."""
    return AthleteProfileRepository(db_session)


@pytest.fixture
def sample_athlete_data():
    """Sample athlete data for testing."""
    return {
        "id": uuid.uuid4(),
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "hashed_password": "hashed_password_placeholder",
        "status": AthleteStatus.ACTIVE,
    }


@pytest.fixture
def sample_profile_data():
    """Sample profile data for testing."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "display_name": "johndoe",
        "gender": Gender.MALE,
        "country_code": CountryCode.AU,
        "timezone": Timezone.America_New_York,
        "language_code": LanguageCode.en,
        "unit_preference": UnitPreference.METRIC,
    }


# ============================================================================
# AthleteRepository Tests
# ============================================================================


@pytest.mark.asyncio
async def test_athlete_create(db_session, sample_athlete_data):
    """Test creating an athlete."""
    repo = AthleteRepository(db_session)

    created = await repo.create(**sample_athlete_data)

    assert created.id == sample_athlete_data["id"]
    assert created.email == sample_athlete_data["email"]
    assert created.status == sample_athlete_data["status"]


@pytest.mark.asyncio
async def test_athlete_get_by_id(db_session, sample_athlete_data):
    """Test getting an athlete by ID."""
    repo = AthleteRepository(db_session)

    created = await repo.create(**sample_athlete_data)
    fetched = await repo.get_by_id(created.id)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.email == created.email


@pytest.mark.asyncio
async def test_athlete_get_by_id_not_found(db_session):
    """Test getting a non-existent athlete."""
    repo = AthleteRepository(db_session)

    result = await repo.get_by_id(uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_athlete_get_by_email(db_session, sample_athlete_data):
    """Test getting an athlete by email."""
    repo = AthleteRepository(db_session)

    created = await repo.create(**sample_athlete_data)
    fetched = await repo.get_by_email(created.email)

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.email == created.email


@pytest.mark.asyncio
async def test_athlete_get_by_email_not_found(db_session):
    """Test getting a non-existent athlete by email."""
    repo = AthleteRepository(db_session)

    result = await repo.get_by_email("nonexistent@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_athlete_update(db_session, sample_athlete_data):
    """Test updating an athlete."""
    repo = AthleteRepository(db_session)

    created = await repo.create(**sample_athlete_data)
    updated = await repo.update(created.id, status=AthleteStatus.INACTIVE)

    assert updated is not None
    assert updated.id == created.id
    assert updated.status == AthleteStatus.INACTIVE


@pytest.mark.asyncio
async def test_athlete_update_not_found(db_session):
    """Test updating a non-existent athlete."""
    repo = AthleteRepository(db_session)

    result = await repo.update(uuid.uuid4(), status=AthleteStatus.INACTIVE)

    assert result is None


@pytest.mark.asyncio
async def test_athlete_delete(db_session, sample_athlete_data):
    """Test deleting an athlete."""
    repo = AthleteRepository(db_session)

    created = await repo.create(**sample_athlete_data)
    deleted = await repo.delete(created.id)

    assert deleted is True

    fetched = await repo.get_by_id(created.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_athlete_delete_not_found(db_session):
    """Test deleting a non-existent athlete."""
    repo = AthleteRepository(db_session)

    result = await repo.delete(uuid.uuid4())

    assert result is False


@pytest.mark.asyncio
async def test_athlete_list(db_session, sample_athlete_data):
    """Test listing all athletes."""
    repo = AthleteRepository(db_session)

    # Create multiple athletes
    await repo.create(**sample_athlete_data)
    await repo.create(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed_password_placeholder",
        status=AthleteStatus.ACTIVE,
    )

    athletes = await repo.list()

    assert len(athletes) == 2


# ============================================================================
# AthleteProfileRepository Tests
# ============================================================================


@pytest.mark.asyncio
async def test_profile_create(db_session, sample_athlete_data, sample_profile_data):
    """Test creating a profile."""
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create(**sample_athlete_data)

    profile_repo = AthleteProfileRepository(db_session)
    profile_data = {**sample_profile_data, "athlete_id": athlete.id}

    created = await profile_repo.create(**profile_data)

    assert created.athlete_id == athlete.id
    assert created.first_name == sample_profile_data["first_name"]
    assert created.last_name == sample_profile_data["last_name"]


@pytest.mark.asyncio
async def test_profile_get_by_athlete_id(db_session, sample_athlete_data, sample_profile_data):
    """Test getting a profile by athlete ID."""
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create(**sample_athlete_data)

    profile_repo = AthleteProfileRepository(db_session)
    profile_data = {**sample_profile_data, "athlete_id": athlete.id}
    created = await profile_repo.create(**profile_data)

    fetched = await profile_repo.get_by_athlete_id(athlete.id)

    assert fetched is not None
    assert fetched.athlete_id == athlete.id
    assert fetched.first_name == created.first_name


@pytest.mark.asyncio
async def test_profile_get_by_athlete_id_not_found(db_session):
    """Test getting a non-existent profile."""
    profile_repo = AthleteProfileRepository(db_session)

    result = await profile_repo.get_by_athlete_id(uuid.uuid4())

    assert result is None


@pytest.mark.asyncio
async def test_profile_update(db_session, sample_athlete_data, sample_profile_data):
    """Test updating a profile using update_by_athlete_id method."""
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create(**sample_athlete_data)

    profile_repo = AthleteProfileRepository(db_session)
    profile_data = {**sample_profile_data, "athlete_id": athlete.id}
    await profile_repo.create(**profile_data)

    # Update the profile using the repository's update_by_athlete_id method
    updated = await profile_repo.update_by_athlete_id(athlete.id, first_name="Jane")

    assert updated is not None
    assert updated.first_name == "Jane"
    # Other fields should be preserved
    assert updated.last_name == sample_profile_data["last_name"]


@pytest.mark.asyncio
async def test_profile_update_not_found(db_session):
    """Test updating a non-existent profile."""
    profile_repo = AthleteProfileRepository(db_session)

    result = await profile_repo.update_by_athlete_id(uuid.uuid4(), first_name="Jane")

    assert result is None


@pytest.mark.asyncio
async def test_profile_delete(db_session, sample_athlete_data, sample_profile_data):
    """Test deleting a profile using delete_by_athlete_id method."""
    athlete_repo = AthleteRepository(db_session)
    athlete = await athlete_repo.create(**sample_athlete_data)

    profile_repo = AthleteProfileRepository(db_session)
    profile_data = {**sample_profile_data, "athlete_id": athlete.id}
    await profile_repo.create(**profile_data)

    # Delete the profile using the repository's delete_by_athlete_id method
    deleted = await profile_repo.delete_by_athlete_id(athlete.id)

    assert deleted is True

    # Verify profile is gone
    fetched = await profile_repo.get_by_athlete_id(athlete.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_profile_delete_not_found(db_session):
    """Test deleting a non-existent profile."""
    profile_repo = AthleteProfileRepository(db_session)

    result = await profile_repo.delete_by_athlete_id(uuid.uuid4())

    assert result is False