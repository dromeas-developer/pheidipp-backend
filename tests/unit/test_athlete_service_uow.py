"""Unit tests for AthleteService UoW methods."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.athlete_service import AthleteService
from tests.factories.athlete_factory import make_athlete, make_athlete_profile


@pytest.fixture
def mock_athlete_repo():
    """Mock AthleteRepository."""
    repo = MagicMock()
    repo.get_by_id = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_profile_repo():
    """Mock AthleteProfileRepository."""
    repo = MagicMock()
    repo.get_by_athlete_id = AsyncMock()
    return repo


@pytest.fixture
def service(mock_athlete_repo, mock_profile_repo):
    """AthleteService with mocked repositories."""
    return AthleteService(mock_athlete_repo, mock_profile_repo)


@pytest.fixture
def mock_uow():
    """Mock UnitOfWork."""
    uow = MagicMock()
    uow.athletes = MagicMock()
    uow.athletes.get_by_id = AsyncMock()
    uow.athletes.session = MagicMock()
    uow.athletes.session.flush = AsyncMock()
    uow.profiles = MagicMock()
    uow.profiles.get_by_athlete_id = AsyncMock()
    return uow


class TestSetOnboardingCompleteUow:
    """Tests for AthleteService.set_onboarding_complete_uow()."""

    @pytest.mark.asyncio
    async def test_fetches_athlete_via_uow_athletes_get_by_id(
        self, service, mock_uow
    ):
        """Verify set_onboarding_complete_uow() fetches athlete via uow.athletes.get_by_id()."""
        athlete_id = uuid.uuid4()
        athlete = make_athlete(id=athlete_id, onboarding_complete=False)
        mock_uow.athletes.get_by_id = AsyncMock(return_value=athlete)

        await service.set_onboarding_complete_uow(athlete_id, mock_uow)

        mock_uow.athletes.get_by_id.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_sets_onboarding_complete_true(
        self, service, mock_uow
    ):
        """Verify set_onboarding_complete_uow() sets athlete.onboarding_complete = True."""
        athlete_id = uuid.uuid4()
        athlete = make_athlete(id=athlete_id, onboarding_complete=False)
        mock_uow.athletes.get_by_id = AsyncMock(return_value=athlete)

        await service.set_onboarding_complete_uow(athlete_id, mock_uow)

        assert athlete.onboarding_complete is True

    @pytest.mark.asyncio
    async def test_calls_session_flush(
        self, service, mock_uow
    ):
        """Verify set_onboarding_complete_uow() calls session.flush()."""
        athlete_id = uuid.uuid4()
        athlete = make_athlete(id=athlete_id, onboarding_complete=False)
        mock_uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        mock_uow.athletes.session.flush = AsyncMock()

        await service.set_onboarding_complete_uow(athlete_id, mock_uow)

        mock_uow.athletes.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_value_error_when_athlete_not_found(
        self, service, mock_uow
    ):
        """Verify set_onboarding_complete_uow() raises ValueError when athlete not found."""
        athlete_id = uuid.uuid4()
        mock_uow.athletes.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await service.set_onboarding_complete_uow(athlete_id, mock_uow)

        assert str(athlete_id) in str(exc_info.value)


class TestGetProfileUow:
    """Tests for AthleteService.get_profile_uow()."""

    @pytest.mark.asyncio
    async def test_delegates_to_uow_profiles_get_by_athlete_id(
        self, service, mock_uow
    ):
        """Verify get_profile_uow() delegates to uow.profiles.get_by_athlete_id()."""
        athlete_id = uuid.uuid4()
        profile = make_athlete_profile(athlete_id=athlete_id)
        mock_uow.profiles.get_by_athlete_id = AsyncMock(return_value=profile)

        result = await service.get_profile_uow(athlete_id, mock_uow)

        mock_uow.profiles.get_by_athlete_id.assert_called_once_with(athlete_id)
        assert result == profile

    @pytest.mark.asyncio
    async def test_returns_none_when_profile_not_found(
        self, service, mock_uow
    ):
        """Verify get_profile_uow() returns None when profile not found."""
        athlete_id = uuid.uuid4()
        mock_uow.profiles.get_by_athlete_id = AsyncMock(return_value=None)

        result = await service.get_profile_uow(athlete_id, mock_uow)

        assert result is None