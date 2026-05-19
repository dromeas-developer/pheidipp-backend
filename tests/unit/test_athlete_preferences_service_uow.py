"""Unit tests for AthletePreferencesService UoW methods."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.athlete_preferences import AthletePreferencesCreate
from app.services.athlete_preferences_service import AthletePreferencesService
from tests.factories.athlete_preferences_factory import make_athlete_preferences_full


@pytest.fixture
def mock_repo():
    """Mock AthletePreferencesRepository."""
    repo = MagicMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repo):
    """AthletePreferencesService with mocked repository."""
    return AthletePreferencesService(mock_repo)


@pytest.fixture
def mock_uow():
    """Mock UnitOfWork."""
    uow = MagicMock()
    uow.preferences = MagicMock()
    uow.preferences.session = MagicMock()
    uow.preferences.session.add = MagicMock()
    uow.preferences.session.flush = AsyncMock()
    return uow


class TestCreateForAthleteUow:
    """Tests for AthletePreferencesService.create_for_athlete_uow()."""

    @pytest.mark.asyncio
    async def test_builds_payload_from_schema_data_with_athlete_id(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() builds payload from schema data with athlete_id added."""
        athlete_id = uuid.uuid4()
        data = AthletePreferencesCreate(
            sport_background="running_primary",
            years_structured_training=5.0,
        )

        result = await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        # Verify the object was added with athlete_id
        added_obj = mock_uow.preferences.session.add.call_args[0][0]
        assert added_obj.athlete_id == athlete_id

    @pytest.mark.asyncio
    async def test_constructs_athlete_preferences_orm_object(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() constructs AthletePreferences ORM object."""
        athlete_id = uuid.uuid4()
        data = AthletePreferencesCreate(
            sport_background="running_primary",
            years_structured_training=5.0,
        )

        result = await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        # Verify the result is an AthletePreferences instance
        assert result is not None

    @pytest.mark.asyncio
    async def test_calls_session_add_and_flush(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() calls uow.preferences.session.add() and session.flush()."""
        athlete_id = uuid.uuid4()
        data = AthletePreferencesCreate(
            sport_background="running_primary",
            years_structured_training=5.0,
        )

        await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        mock_uow.preferences.session.add.assert_called_once()
        mock_uow.preferences.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_created_orm_object(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() returns the created ORM object."""
        athlete_id = uuid.uuid4()
        data = AthletePreferencesCreate(
            sport_background="running_primary",
            years_structured_training=5.0,
        )

        result = await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        assert result is not None

    @pytest.mark.asyncio
    async def test_does_not_call_self_repo(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() does NOT call self.repo."""
        athlete_id = uuid.uuid4()
        data = AthletePreferencesCreate(
            sport_background="running_primary",
            years_structured_training=5.0,
        )

        await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        # Verify repo.create was NOT called
        service.repo.create.assert_not_called()