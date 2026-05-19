"""Unit tests for WellnessService."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import WellnessSource
from app.models.wellness import AthleteWellness
from app.services.wellness_service import WellnessService
from app.schemas.wellness import WellnessCreate, WellnessUpdate, WellnessListParams


@pytest.fixture
def wellness_repo_mock():
    """Create a mock WellnessRepository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.get_by_athlete = AsyncMock()
    mock.get_by_athlete_date = AsyncMock()
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    mock.count_by_athlete = AsyncMock()
    return mock


@pytest.fixture
def athlete_repo_mock():
    """Create a mock AthleteRepository."""
    mock = MagicMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def service(wellness_repo_mock, athlete_repo_mock):
    """Create WellnessService with mocked dependencies."""
    return WellnessService(wellness_repo_mock, athlete_repo_mock)


class TestCreateWellness:
    """Tests for WellnessService.create_wellness."""

    @pytest.mark.asyncio
    async def test_create_wellness_success(self, service, wellness_repo_mock, athlete_repo_mock):
        """Test create_wellness success: athlete exists, no duplicate date, returns created record."""
        athlete_id = uuid.uuid4()
        metric_date = date(2024, 1, 15)

        # Mock athlete exists
        athlete_repo_mock.get_by_id.return_value = MagicMock(id=athlete_id)

        # Mock no existing record for date
        wellness_repo_mock.get_by_athlete_date.return_value = None

        # Mock created record
        created_record = AthleteWellness(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=metric_date,
            sleep_total=480,
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )
        wellness_repo_mock.create.return_value = created_record

        # Execute
        result = await service.create_wellness(
            WellnessCreate(
                athlete_id=athlete_id,
                metric_date=metric_date,
                sleep_total=480,
                source=WellnessSource.MANUAL,
                timezone="UTC",
            )
        )

        # Assert
        assert result is created_record
        athlete_repo_mock.get_by_id.assert_called_once_with(athlete_id)
        wellness_repo_mock.get_by_athlete_date.assert_called_once_with(athlete_id, metric_date)
        wellness_repo_mock.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_wellness_raises_value_error_for_missing_athlete(
        self, service, wellness_repo_mock, athlete_repo_mock
    ):
        """Test create_wellness raises ValueError for missing athlete."""
        athlete_id = uuid.uuid4()

        # Mock athlete not found
        athlete_repo_mock.get_by_id.return_value = None

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await service.create_wellness(
                WellnessCreate(
                    athlete_id=athlete_id,
                    metric_date=date(2024, 1, 15),
                    source=WellnessSource.MANUAL,
                    timezone="UTC",
                )
            )

        assert f"Athlete with id {athlete_id} not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_wellness_raises_value_error_for_duplicate_date(
        self, service, wellness_repo_mock, athlete_repo_mock
    ):
        """Test create_wellness raises ValueError for duplicate date."""
        athlete_id = uuid.uuid4()
        metric_date = date(2024, 1, 15)

        # Mock athlete exists
        athlete_repo_mock.get_by_id.return_value = MagicMock(id=athlete_id)

        # Mock existing record for date
        existing_record = AthleteWellness(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=metric_date,
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )
        wellness_repo_mock.get_by_athlete_date.return_value = existing_record

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await service.create_wellness(
                WellnessCreate(
                    athlete_id=athlete_id,
                    metric_date=metric_date,
                    source=WellnessSource.MANUAL,
                    timezone="UTC",
                )
            )

        assert f"already exists for athlete {athlete_id} on {metric_date}" in str(exc_info.value)


class TestGetWellness:
    """Tests for WellnessService.get_wellness."""

    @pytest.mark.asyncio
    async def test_get_wellness_returns_record_by_id(self, service, wellness_repo_mock):
        """Test get_wellness returns record by id."""
        wellness_id = uuid.uuid4()
        expected_record = AthleteWellness(
            id=wellness_id,
            athlete_id=uuid.uuid4(),
            metric_date=date(2024, 1, 15),
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )
        wellness_repo_mock.get_by_id.return_value = expected_record

        result = await service.get_wellness(wellness_id)

        assert result is expected_record
        wellness_repo_mock.get_by_id.assert_called_once_with(wellness_id)

    @pytest.mark.asyncio
    async def test_get_wellness_returns_none_when_not_found(self, service, wellness_repo_mock):
        """Test get_wellness returns None when not found."""
        wellness_id = uuid.uuid4()
        wellness_repo_mock.get_by_id.return_value = None

        result = await service.get_wellness(wellness_id)

        assert result is None


class TestListAthleteWellness:
    """Tests for WellnessService.list_athlete_wellness."""

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_passes_filters_and_pagination(
        self, service, wellness_repo_mock
    ):
        """Test list_athlete_wellness passes filters and pagination to repository."""
        athlete_id = uuid.uuid4()
        params = WellnessListParams(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            limit=10,
            offset=5,
        )

        wellness_repo_mock.get_by_athlete.return_value = []

        await service.list_athlete_wellness(athlete_id, params)

        wellness_repo_mock.get_by_athlete.assert_called_once_with(
            athlete_id=athlete_id,
            skip=5,
            limit=10,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
        )


class TestUpdateWellness:
    """Tests for WellnessService.update_wellness."""

    @pytest.mark.asyncio
    async def test_update_wellness_success(self, service, wellness_repo_mock):
        """Test update_wellness success: record exists, no date conflict."""
        wellness_id = uuid.uuid4()
        athlete_id = uuid.uuid4()
        existing_record = AthleteWellness(
            id=wellness_id,
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            sleep_total=400,
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )
        updated_record = AthleteWellness(
            id=wellness_id,
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            sleep_total=480,
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )

        wellness_repo_mock.get_by_id.return_value = existing_record
        wellness_repo_mock.get_by_athlete_date.return_value = None
        wellness_repo_mock.update.return_value = updated_record

        result = await service.update_wellness(
            wellness_id,
            WellnessUpdate(sleep_total=480),
        )

        assert result is updated_record

    @pytest.mark.asyncio
    async def test_update_wellness_returns_none_when_record_missing(self, service, wellness_repo_mock):
        """Test update_wellness returns None when record missing."""
        wellness_id = uuid.uuid4()
        wellness_repo_mock.get_by_id.return_value = None

        result = await service.update_wellness(
            wellness_id,
            WellnessUpdate(sleep_total=480),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_wellness_raises_value_error_on_date_conflict(
        self, service, wellness_repo_mock
    ):
        """Test update_wellness raises ValueError on date conflict with a different record."""
        wellness_id = uuid.uuid4()
        athlete_id = uuid.uuid4()
        existing_record = AthleteWellness(
            id=wellness_id,
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            sleep_total=400,
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )
        # Another record already exists for the new date
        conflicting_record = AthleteWellness(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 20),
            sleep_total=450,
            source=WellnessSource.MANUAL,
            timezone="UTC",
        )

        wellness_repo_mock.get_by_id.return_value = existing_record
        wellness_repo_mock.get_by_athlete_date.return_value = conflicting_record

        with pytest.raises(ValueError) as exc_info:
            await service.update_wellness(
                wellness_id,
                WellnessUpdate(metric_date=date(2024, 1, 20)),
            )

        assert "already exists" in str(exc_info.value)


class TestDeleteWellness:
    """Tests for WellnessService.delete_wellness."""

    @pytest.mark.asyncio
    async def test_delete_wellness_returns_true_on_success(self, service, wellness_repo_mock):
        """Test delete_wellness returns True on success."""
        wellness_id = uuid.uuid4()
        wellness_repo_mock.delete.return_value = True

        result = await service.delete_wellness(wellness_id)

        assert result is True
        wellness_repo_mock.delete.assert_called_once_with(wellness_id)

    @pytest.mark.asyncio
    async def test_delete_wellness_returns_false_when_missing(self, service, wellness_repo_mock):
        """Test delete_wellness returns False when missing."""
        wellness_id = uuid.uuid4()
        wellness_repo_mock.delete.return_value = False

        result = await service.delete_wellness(wellness_id)

        assert result is False


class TestCountByAthlete:
    """Tests for WellnessService.count_by_athlete."""

    @pytest.mark.asyncio
    async def test_count_by_athlete_delegates_to_repository(self, service, wellness_repo_mock):
        """Test count_by_athlete delegates to repository."""
        athlete_id = uuid.uuid4()
        wellness_repo_mock.count_by_athlete.return_value = 10

        result = await service.count_by_athlete(athlete_id)

        assert result == 10
        wellness_repo_mock.count_by_athlete.assert_called_once_with(athlete_id)