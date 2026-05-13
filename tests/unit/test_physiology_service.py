"""Unit tests for PhysiologyService."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.physiology import AthletePhysiology
from app.models.enums import DataSource
from app.schemas.physiology import AthletePhysiologyCreate
from app.services.physiology_service import PhysiologyService


@pytest.fixture
def physiology_repo_mock():
    """Fixture for mocking PhysiologyRepository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.get_by_athlete = AsyncMock()
    mock.get_by_athlete_and_date = AsyncMock()
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    mock.has_overlap = AsyncMock()
    return mock


@pytest.fixture
def athlete_repo_mock():
    """Fixture for mocking AthleteRepository."""
    mock = MagicMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def service(physiology_repo_mock, athlete_repo_mock):
    """Fixture for PhysiologyService with mocked repositories."""
    return PhysiologyService(physiology_repo_mock, athlete_repo_mock)


# ============================================================================
# create Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_physiology_record_without_overlap(service, physiology_repo_mock, athlete_repo_mock):
    """Test that non-overlapping physiology records are allowed."""
    athlete_id = uuid.uuid4()
    physiology_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=True)
    physiology_repo_mock.has_overlap = AsyncMock(return_value=False)

    create_data = AthletePhysiologyCreate(
        ftp=280,
        lt1=220,
        lt2=250,
        vo2_max=65.5,
        max_hr=190,
        source=DataSource.MANUAL,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
    )

    created_physiology = AthletePhysiology(
        id=physiology_id,
        athlete_id=athlete_id,
        ftp=280,
        lt1=220,
        lt2=250,
        vo2_max=65.5,
        max_hr=190,
        source=DataSource.MANUAL,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    physiology_repo_mock.create = AsyncMock(return_value=created_physiology)

    result = await service.create(athlete_id, create_data)

    assert result.id == physiology_id
    assert result.athlete_id == athlete_id
    assert result.ftp == 280
    assert result.lt1 == 220
    assert result.lt2 == 250
    assert result.vo2_max == 65.5
    assert result.max_hr == 190
    assert result.effective_from == date(2024, 1, 1)
    assert result.effective_to == date(2024, 6, 30)

    physiology_repo_mock.has_overlap.assert_called_once_with(
        athlete_id,
        date(2024, 1, 1),
        date(2024, 6, 30),
        None,
    )
    physiology_repo_mock.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_physiology_record_detects_overlap(service, physiology_repo_mock, athlete_repo_mock):
    """Test that overlapping physiology periods are rejected."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=True)
    physiology_repo_mock.has_overlap = AsyncMock(return_value=True)

    create_data = AthletePhysiologyCreate(
        ftp=280,
        lt1=220,
        lt2=250,
        source=DataSource.MANUAL,
        effective_from=date(2024, 3, 1),
        effective_to=date(2024, 5, 31),
    )

    with pytest.raises(ValueError, match="Date range overlaps with an existing physiology record"):
        await service.create(athlete_id, create_data)

    physiology_repo_mock.has_overlap.assert_called_once_with(
        athlete_id,
        date(2024, 3, 1),
        date(2024, 5, 31),
        None,
    )
    physiology_repo_mock.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_physiology_raises_error_for_missing_athlete(service, physiology_repo_mock, athlete_repo_mock):
    """Test that creating physiology raises error when athlete does not exist."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=None)

    create_data = AthletePhysiologyCreate(
        ftp=280,
        source=DataSource.MANUAL,
        effective_from=date(2024, 1, 1),
    )

    with pytest.raises(ValueError, match="Athlete not found"):
        await service.create(athlete_id, create_data)

    physiology_repo_mock.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_physiology_raises_error_for_invalid_date_range(service, physiology_repo_mock, athlete_repo_mock):
    """Test that creating physiology raises error when effective_from > effective_to."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=True)

    create_data = AthletePhysiologyCreate(
        ftp=280,
        source=DataSource.MANUAL,
        effective_from=date(2024, 6, 30),
        effective_to=date(2024, 1, 1),
    )

    with pytest.raises(ValueError, match="effective_from must be <= effective_to"):
        await service.create(athlete_id, create_data)

    physiology_repo_mock.create.assert_not_called()


# ============================================================================
# has_overlap Tests
# ============================================================================


@pytest.mark.asyncio
async def test_has_overlap_detects_open_ended_ranges(service, physiology_repo_mock):
    """Test that overlap logic works with effective_to=None."""
    athlete_id = uuid.uuid4()

    # Test case: existing record has effective_to=None (open-ended)
    # New record starts during the existing record's period
    physiology_repo_mock.has_overlap = AsyncMock(return_value=True)

    result = await physiology_repo_mock.has_overlap(
        athlete_id,
        effective_from=date(2024, 3, 1),
        effective_to=None,  # New record is open-ended
        exclude_id=None,
    )

    assert result is True


@pytest.mark.asyncio
async def test_has_overlap_returns_false_for_non_overlapping(service, physiology_repo_mock):
    """Test that has_overlap returns False when no overlap exists."""
    athlete_id = uuid.uuid4()

    physiology_repo_mock.has_overlap = AsyncMock(return_value=False)

    result = await physiology_repo_mock.has_overlap(
        athlete_id,
        effective_from=date(2024, 7, 1),
        effective_to=date(2024, 12, 31),
        exclude_id=None,
    )

    assert result is False


# ============================================================================
# list_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_by_athlete_returns_physiology_records(service, physiology_repo_mock, athlete_repo_mock):
    """Test that list_by_athlete returns physiology records for an athlete."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=True)

    physiology_list = [
        AthletePhysiology(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            ftp=280,
            effective_from=date(2024, 1, 1),
            effective_to=date(2024, 6, 30),
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        ),
        AthletePhysiology(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            ftp=300,
            effective_from=date(2024, 7, 1),
            effective_to=None,
            created_at=datetime(2024, 7, 1, 0, 0, 0),
            updated_at=datetime(2024, 7, 1, 0, 0, 0),
        ),
    ]

    physiology_repo_mock.get_by_athlete = AsyncMock(return_value=physiology_list)

    result = await service.list_by_athlete(athlete_id)

    assert len(result) == 2
    assert result[0].ftp == 280
    assert result[1].ftp == 300


@pytest.mark.asyncio
async def test_list_by_athlete_raises_error_for_missing_athlete(service, physiology_repo_mock, athlete_repo_mock):
    """Test that list_by_athlete raises error when athlete does not exist."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(ValueError, match="Athlete not found"):
        await service.list_by_athlete(athlete_id)


# ============================================================================
# get_by_id Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_by_id_returns_physiology(service, physiology_repo_mock):
    """Test that get_by_id returns the physiology record."""
    physiology_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    physiology = AthletePhysiology(
        id=physiology_id,
        athlete_id=athlete_id,
        ftp=280,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    physiology_repo_mock.get_by_id = AsyncMock(return_value=physiology)

    result = await service.get_by_id(physiology_id)

    assert result is not None
    assert result.id == physiology_id

    physiology_repo_mock.get_by_id.assert_called_once_with(physiology_id)


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(service, physiology_repo_mock):
    """Test that get_by_id returns None when physiology not found."""
    physiology_id = uuid.uuid4()

    physiology_repo_mock.get_by_id = AsyncMock(return_value=None)

    result = await service.get_by_id(physiology_id)

    assert result is None


# ============================================================================
# get_effective Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_effective_returns_physiology_for_date(service, physiology_repo_mock):
    """Test that get_effective returns the physiology record effective for a given date."""
    athlete_id = uuid.uuid4()
    target_date = date(2024, 3, 15)

    physiology = AthletePhysiology(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        ftp=280,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    physiology_repo_mock.get_by_athlete_and_date = AsyncMock(return_value=physiology)

    result = await service.get_effective(athlete_id, target_date)

    assert result is not None
    assert result.ftp == 280

    physiology_repo_mock.get_by_athlete_and_date.assert_called_once_with(athlete_id, target_date)


# ============================================================================
# update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_modifies_physiology(service, physiology_repo_mock):
    """Test that update modifies the physiology record."""
    physiology_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    existing = AthletePhysiology(
        id=physiology_id,
        athlete_id=athlete_id,
        ftp=280,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    from app.schemas.physiology import AthletePhysiologyUpdate

    update_data = AthletePhysiologyUpdate(ftp=300)

    physiology_repo_mock.get_by_id = AsyncMock(return_value=existing)
    physiology_repo_mock.has_overlap = AsyncMock(return_value=False)

    updated_physiology = AthletePhysiology(
        id=physiology_id,
        athlete_id=athlete_id,
        ftp=300,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 2, 1, 0, 0, 0),
    )

    physiology_repo_mock.update = AsyncMock(return_value=updated_physiology)

    result = await service.update(physiology_id, update_data)

    assert result is not None
    assert result.ftp == 300


@pytest.mark.asyncio
async def test_update_returns_none_when_not_found(service, physiology_repo_mock):
    """Test that update returns None when physiology not found."""
    physiology_id = uuid.uuid4()

    physiology_repo_mock.get_by_id = AsyncMock(return_value=None)

    from app.schemas.physiology import AthletePhysiologyUpdate

    update_data = AthletePhysiologyUpdate(ftp=300)

    result = await service.update(physiology_id, update_data)

    assert result is None


# ============================================================================
# delete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_returns_true_when_deleted(service, physiology_repo_mock):
    """Test that delete returns True when the record is deleted."""
    physiology_id = uuid.uuid4()

    physiology_repo_mock.delete = AsyncMock(return_value=True)

    result = await service.delete(physiology_id)

    assert result is True

    physiology_repo_mock.delete.assert_called_once_with(physiology_id)


@pytest.mark.asyncio
async def test_delete_returns_false_when_not_found(service, physiology_repo_mock):
    """Test that delete returns False when the record does not exist."""
    physiology_id = uuid.uuid4()

    physiology_repo_mock.delete = AsyncMock(return_value=False)

    result = await service.delete(physiology_id)

    assert result is False

    physiology_repo_mock.delete.assert_called_once_with(physiology_id)