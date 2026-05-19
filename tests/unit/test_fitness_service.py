"""Unit tests for FitnessService."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import DataSource
from app.models.fitness import AthleteFitness
from app.services.fitness_service import FitnessService
from app.schemas.fitness import FitnessCreate, FitnessUpdate, FitnessListParams


@pytest.fixture
def fitness_repo_mock():
    """Create a mock FitnessRepository."""
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
def service(fitness_repo_mock, athlete_repo_mock):
    """Create FitnessService with mocked dependencies."""
    return FitnessService(fitness_repo_mock, athlete_repo_mock)


class TestCreateFitness:
    """Tests for FitnessService.create_fitness."""

    @pytest.mark.asyncio
    async def test_create_fitness_success(self, service, fitness_repo_mock, athlete_repo_mock):
        """Test create_fitness success: athlete exists, no duplicate date, returns created record."""
        athlete_id = uuid.uuid4()
        metric_date = date(2024, 1, 15)

        # Mock athlete exists
        athlete_repo_mock.get_by_id.return_value = MagicMock(id=athlete_id)

        # Mock no existing record for date
        fitness_repo_mock.get_by_athlete_date.return_value = None

        # Mock created record
        created_record = AthleteFitness(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=metric_date,
            tss=75.5,
            source=DataSource.MANUAL,
        )
        fitness_repo_mock.create.return_value = created_record

        # Execute
        result = await service.create_fitness(
            FitnessCreate(
                athlete_id=athlete_id,
                metric_date=metric_date,
                tss=75.5,
            )
        )

        # Assert
        assert result is created_record
        athlete_repo_mock.get_by_id.assert_called_once_with(athlete_id)
        fitness_repo_mock.get_by_athlete_date.assert_called_once_with(athlete_id, metric_date)
        fitness_repo_mock.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_fitness_raises_value_error_for_missing_athlete(
        self, service, fitness_repo_mock, athlete_repo_mock
    ):
        """Test create_fitness raises ValueError for missing athlete."""
        athlete_id = uuid.uuid4()

        # Mock athlete not found
        athlete_repo_mock.get_by_id.return_value = None

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await service.create_fitness(
                FitnessCreate(
                    athlete_id=athlete_id,
                    metric_date=date(2024, 1, 15),
                )
            )

        assert f"Athlete with id {athlete_id} not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_fitness_raises_value_error_for_duplicate_date(
        self, service, fitness_repo_mock, athlete_repo_mock
    ):
        """Test create_fitness raises ValueError for duplicate date."""
        athlete_id = uuid.uuid4()
        metric_date = date(2024, 1, 15)

        # Mock athlete exists
        athlete_repo_mock.get_by_id.return_value = MagicMock(id=athlete_id)

        # Mock existing record for date
        existing_record = AthleteFitness(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=metric_date,
        )
        fitness_repo_mock.get_by_athlete_date.return_value = existing_record

        # Execute and assert
        with pytest.raises(ValueError) as exc_info:
            await service.create_fitness(
                FitnessCreate(
                    athlete_id=athlete_id,
                    metric_date=metric_date,
                )
            )

        assert f"already exists for athlete {athlete_id} on {metric_date}" in str(exc_info.value)


class TestGetFitness:
    """Tests for FitnessService.get_fitness."""

    @pytest.mark.asyncio
    async def test_get_fitness_returns_record_by_id(self, service, fitness_repo_mock):
        """Test get_fitness returns record by id."""
        fitness_id = uuid.uuid4()
        expected_record = AthleteFitness(
            id=fitness_id,
            athlete_id=uuid.uuid4(),
            metric_date=date(2024, 1, 15),
            source=DataSource.MANUAL,
        )
        fitness_repo_mock.get_by_id.return_value = expected_record

        result = await service.get_fitness(fitness_id)

        assert result is expected_record
        fitness_repo_mock.get_by_id.assert_called_once_with(fitness_id)

    @pytest.mark.asyncio
    async def test_get_fitness_returns_none_when_not_found(self, service, fitness_repo_mock):
        """Test get_fitness returns None when not found."""
        fitness_id = uuid.uuid4()
        fitness_repo_mock.get_by_id.return_value = None

        result = await service.get_fitness(fitness_id)

        assert result is None


class TestListAthleteFitness:
    """Tests for FitnessService.list_athlete_fitness."""

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_passes_pagination_and_date_filters(
        self, service, fitness_repo_mock
    ):
        """Test list_athlete_fitness passes pagination and date filters to repository."""
        athlete_id = uuid.uuid4()
        params = FitnessListParams(
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            limit=10,
            offset=5,
        )

        fitness_repo_mock.get_by_athlete.return_value = []

        await service.list_athlete_fitness(athlete_id, params)

        fitness_repo_mock.get_by_athlete.assert_called_once_with(
            athlete_id=athlete_id,
            skip=5,
            limit=10,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
        )


class TestUpdateFitness:
    """Tests for FitnessService.update_fitness."""

    @pytest.mark.asyncio
    async def test_update_fitness_success(self, service, fitness_repo_mock):
        """Test update_fitness success: record exists, no date conflict."""
        fitness_id = uuid.uuid4()
        athlete_id = uuid.uuid4()
        existing_record = AthleteFitness(
            id=fitness_id,
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            tss=50.0,
            source=DataSource.MANUAL,
        )
        updated_record = AthleteFitness(
            id=fitness_id,
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            tss=75.0,
            source=DataSource.MANUAL,
        )

        fitness_repo_mock.get_by_id.return_value = existing_record
        fitness_repo_mock.get_by_athlete_date.return_value = None
        fitness_repo_mock.update.return_value = updated_record

        result = await service.update_fitness(
            fitness_id,
            FitnessUpdate(metric_date=date(2024, 1, 15), tss=75.0),
        )

        assert result is updated_record

    @pytest.mark.asyncio
    async def test_update_fitness_returns_none_when_not_found(self, service, fitness_repo_mock):
        """Test update_fitness returns None when record not found."""
        fitness_id = uuid.uuid4()
        fitness_repo_mock.get_by_id.return_value = None

        result = await service.update_fitness(
            fitness_id,
            FitnessUpdate(metric_date=date(2024, 1, 15), tss=75.0),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_fitness_raises_value_error_for_date_conflict(
        self, service, fitness_repo_mock
    ):
        """Test update_fitness raises ValueError when changing metric_date to an already-existing date."""
        fitness_id = uuid.uuid4()
        athlete_id = uuid.uuid4()
        existing_record = AthleteFitness(
            id=fitness_id,
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 15),
            tss=50.0,
            source=DataSource.MANUAL,
        )
        # Another record already exists for the new date
        conflicting_record = AthleteFitness(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            metric_date=date(2024, 1, 20),
            tss=60.0,
            source=DataSource.MANUAL,
        )

        fitness_repo_mock.get_by_id.return_value = existing_record
        fitness_repo_mock.get_by_athlete_date.return_value = conflicting_record

        with pytest.raises(ValueError) as exc_info:
            await service.update_fitness(
                fitness_id,
                FitnessUpdate(metric_date=date(2024, 1, 20)),
            )

        assert "already exists" in str(exc_info.value)


class TestDeleteFitness:
    """Tests for FitnessService.delete_fitness."""

    @pytest.mark.asyncio
    async def test_delete_fitness_returns_true_on_success(self, service, fitness_repo_mock):
        """Test delete_fitness returns True on success."""
        fitness_id = uuid.uuid4()
        fitness_repo_mock.delete.return_value = True

        result = await service.delete_fitness(fitness_id)

        assert result is True
        fitness_repo_mock.delete.assert_called_once_with(fitness_id)

    @pytest.mark.asyncio
    async def test_delete_fitness_returns_false_when_not_found(self, service, fitness_repo_mock):
        """Test delete_fitness returns False when not found."""
        fitness_id = uuid.uuid4()
        fitness_repo_mock.delete.return_value = False

        result = await service.delete_fitness(fitness_id)

        assert result is False


class TestCountByAthlete:
    """Tests for FitnessService.count_by_athlete."""

    @pytest.mark.asyncio
    async def test_count_by_athlete_delegates_to_repository(self, service, fitness_repo_mock):
        """Test count_by_athlete delegates to repository."""
        athlete_id = uuid.uuid4()
        fitness_repo_mock.count_by_athlete.return_value = 10

        result = await service.count_by_athlete(athlete_id)

        assert result == 10
        fitness_repo_mock.count_by_athlete.assert_called_once_with(athlete_id)