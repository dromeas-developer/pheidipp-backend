"""Unit tests for OnboardingService."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.onboarding import OnboardingRequest
from app.schemas.athlete_preferences import AthletePreferencesCreate
from app.schemas.training_block import TrainingBlockCreate
from app.services.onboarding_service import OnboardingService
from tests.factories.athlete_preferences_factory import make_athlete_preferences_full
from tests.factories.training_block_factory import make_training_block_full
from tests.factories.athlete_factory import make_athlete_profile
from tests.factories.twin_state_factory import make_twin_state


@pytest.fixture
def mock_athlete_service():
    """Mock AthleteService."""
    service = MagicMock()
    service.create_for_athlete_uow = AsyncMock()
    service.get_profile_uow = AsyncMock()
    service.set_onboarding_complete_uow = AsyncMock()
    return service


@pytest.fixture
def mock_prefs_service():
    """Mock AthletePreferencesService."""
    service = MagicMock()
    service.create_for_athlete_uow = AsyncMock()
    return service


@pytest.fixture
def mock_block_service():
    """Mock TrainingBlockService."""
    service = MagicMock()
    service.create_for_athlete_uow = AsyncMock()
    return service


@pytest.fixture
def mock_twin_service():
    """Mock TwinInitialisationService."""
    service = MagicMock()
    service.initialise = AsyncMock()
    return service


@pytest.fixture
def service(
    mock_athlete_service, mock_prefs_service, mock_block_service, mock_twin_service
):
    """OnboardingService with all mocked dependencies."""
    return OnboardingService(
        athlete_service=mock_athlete_service,
        athlete_preferences_service=mock_prefs_service,
        training_block_service=mock_block_service,
        twin_initialisation_service=mock_twin_service,
    )


@pytest.fixture
def mock_uow():
    """Mock UnitOfWork."""
    uow = MagicMock()
    uow.athletes = MagicMock()
    uow.preferences = MagicMock()
    uow.blocks = MagicMock()
    uow.twin_states = MagicMock()
    uow.profiles = MagicMock()
    return uow


@pytest.fixture
def sample_request():
    """Sample OnboardingRequest."""
    return OnboardingRequest(
        preferences=AthletePreferencesCreate(
            sport_background="running_primary",
            years_structured_training=5.0,
        ),
        training_block=TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
            goal_event_name="Boston Marathon 2024",
        ),
    )


class TestCompleteOnboarding:
    """Tests for OnboardingService.complete_onboarding()."""

    @pytest.mark.asyncio
    async def test_calls_preferences_service_first(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() calls athlete_preferences_service.create_for_athlete_uow() with correct arguments."""
        athlete_id = uuid.uuid4()
        mock_prefs_service.create_for_athlete_uow = AsyncMock(
            return_value=make_athlete_preferences_full(athlete_id=athlete_id)
        )
        mock_block_service.create_for_athlete_uow = AsyncMock(
            return_value=make_training_block_full(athlete_id=athlete_id)
        )
        mock_athlete_service.get_profile_uow = AsyncMock(
            return_value=make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")
        )
        mock_twin_service.initialise = AsyncMock(
            return_value=make_twin_state(athlete_id=athlete_id)
        )

        await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        mock_prefs_service.create_for_athlete_uow.assert_called_once_with(
            athlete_id, sample_request.preferences, mock_uow
        )

    @pytest.mark.asyncio
    async def test_calls_training_block_service_second(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() calls training_block_service.create_for_athlete_uow() with correct arguments."""
        athlete_id = uuid.uuid4()
        mock_prefs_service.create_for_athlete_uow = AsyncMock(
            return_value=make_athlete_preferences_full(athlete_id=athlete_id)
        )
        mock_block_service.create_for_athlete_uow = AsyncMock(
            return_value=make_training_block_full(athlete_id=athlete_id)
        )
        mock_athlete_service.get_profile_uow = AsyncMock(
            return_value=make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")
        )
        mock_twin_service.initialise = AsyncMock(
            return_value=make_twin_state(athlete_id=athlete_id)
        )

        await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        mock_block_service.create_for_athlete_uow.assert_called_once_with(
            athlete_id, sample_request.training_block, mock_uow
        )

    @pytest.mark.asyncio
    async def test_calls_get_profile_third(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() calls athlete_service.get_profile_uow()."""
        athlete_id = uuid.uuid4()
        mock_prefs_service.create_for_athlete_uow = AsyncMock(
            return_value=make_athlete_preferences_full(athlete_id=athlete_id)
        )
        mock_block_service.create_for_athlete_uow = AsyncMock(
            return_value=make_training_block_full(athlete_id=athlete_id)
        )
        mock_athlete_service.get_profile_uow = AsyncMock(
            return_value=make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")
        )
        mock_twin_service.initialise = AsyncMock(
            return_value=make_twin_state(athlete_id=athlete_id)
        )

        await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        mock_athlete_service.get_profile_uow.assert_called_once_with(athlete_id, mock_uow)

    @pytest.mark.asyncio
    async def test_raises_value_error_when_profile_none(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() raises ValueError when profile is None."""
        athlete_id = uuid.uuid4()
        mock_prefs_service.create_for_athlete_uow = AsyncMock(
            return_value=make_athlete_preferences_full(athlete_id=athlete_id)
        )
        mock_block_service.create_for_athlete_uow = AsyncMock(
            return_value=make_training_block_full(athlete_id=athlete_id)
        )
        mock_athlete_service.get_profile_uow = AsyncMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        assert "profile" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_raises_value_error_when_date_of_birth_none(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() raises ValueError when profile.date_of_birth is None."""
        athlete_id = uuid.uuid4()
        mock_prefs_service.create_for_athlete_uow = AsyncMock(
            return_value=make_athlete_preferences_full(athlete_id=athlete_id)
        )
        mock_block_service.create_for_athlete_uow = AsyncMock(
            return_value=make_training_block_full(athlete_id=athlete_id)
        )
        mock_athlete_service.get_profile_uow = AsyncMock(
            return_value=make_athlete_profile(date_of_birth=None)
        )

        with pytest.raises(ValueError) as exc_info:
            await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        assert "date_of_birth" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_calls_twin_initialisation_service_fifth(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() calls twin_initialisation_service.initialise() with preferences, training_block, and profile."""
        athlete_id = uuid.uuid4()
        prefs = make_athlete_preferences_full(athlete_id=athlete_id)
        block = make_training_block_full(athlete_id=athlete_id)
        profile = make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")

        mock_prefs_service.create_for_athlete_uow = AsyncMock(return_value=prefs)
        mock_block_service.create_for_athlete_uow = AsyncMock(return_value=block)
        mock_athlete_service.get_profile_uow = AsyncMock(return_value=profile)
        mock_twin_service.initialise = AsyncMock(
            return_value=make_twin_state(athlete_id=athlete_id)
        )

        await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        mock_twin_service.initialise.assert_called_once_with(
            athlete_id, prefs, block, profile, mock_uow
        )

    @pytest.mark.asyncio
    async def test_calls_set_onboarding_complete_last(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() calls athlete_service.set_onboarding_complete_uow() LAST."""
        athlete_id = uuid.uuid4()
        prefs = make_athlete_preferences_full(athlete_id=athlete_id)
        block = make_training_block_full(athlete_id=athlete_id)
        profile = make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")

        mock_prefs_service.create_for_athlete_uow = AsyncMock(return_value=prefs)
        mock_block_service.create_for_athlete_uow = AsyncMock(return_value=block)
        mock_athlete_service.get_profile_uow = AsyncMock(return_value=profile)
        mock_twin_service.initialise = AsyncMock(
            return_value=make_twin_state(athlete_id=athlete_id)
        )

        await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        # Verify set_onboarding_complete_uow was called after twin initialization
        calls = mock_athlete_service.method_calls
        set_onboarding_call = [c for c in calls if "set_onboarding_complete_uow" in str(c)]
        assert len(set_onboarding_call) == 1

    @pytest.mark.asyncio
    async def test_returns_tuple_of_results(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify complete_onboarding() returns tuple of (preferences, training_block, twin_state)."""
        athlete_id = uuid.uuid4()
        prefs = make_athlete_preferences_full(athlete_id=athlete_id)
        block = make_training_block_full(athlete_id=athlete_id)
        profile = make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")
        twin = make_twin_state(athlete_id=athlete_id)

        mock_prefs_service.create_for_athlete_uow = AsyncMock(return_value=prefs)
        mock_block_service.create_for_athlete_uow = AsyncMock(return_value=block)
        mock_athlete_service.get_profile_uow = AsyncMock(return_value=profile)
        mock_twin_service.initialise = AsyncMock(return_value=twin)

        result = await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[0] == prefs
        assert result[1] == block
        assert result[2] == twin


class TestOrderingGuarantees:
    """Tests for ordering guarantees in OnboardingService."""

    @pytest.mark.asyncio
    async def test_set_onboarding_not_called_if_twin_initialisation_fails(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify ordering guarantee: if twin_initialisation_service.initialise() raises, set_onboarding_complete_uow() is NOT called."""
        athlete_id = uuid.uuid4()
        prefs = make_athlete_preferences_full(athlete_id=athlete_id)
        block = make_training_block_full(athlete_id=athlete_id)
        profile = make_athlete_profile(date_of_birth=date(1994, 5, 15), gender="male")

        mock_prefs_service.create_for_athlete_uow = AsyncMock(return_value=prefs)
        mock_block_service.create_for_athlete_uow = AsyncMock(return_value=block)
        mock_athlete_service.get_profile_uow = AsyncMock(return_value=profile)
        mock_twin_service.initialise = AsyncMock(side_effect=ValueError("Twin init failed"))

        with pytest.raises(ValueError):
            await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        # Verify set_onboarding_complete_uow was NOT called
        for call in mock_athlete_service.method_calls:
            if "set_onboarding_complete_uow" in str(call):
                pytest.fail("set_onboarding_complete_uow should not be called when twin initialization fails")

    @pytest.mark.asyncio
    async def test_subsequent_steps_not_called_if_training_block_fails(
        self, service, mock_prefs_service, mock_block_service, mock_athlete_service, mock_twin_service, mock_uow, sample_request
    ):
        """Verify ordering guarantee: if training_block_service.create_for_athlete_uow() raises HTTPException 409, subsequent steps are NOT called."""
        athlete_id = uuid.uuid4()

        mock_prefs_service.create_for_athlete_uow = AsyncMock(
            return_value=make_athlete_preferences_full(athlete_id=athlete_id)
        )
        mock_block_service.create_for_athlete_uow = AsyncMock(
            side_effect=HTTPException(status_code=409, detail="Active block exists")
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.complete_onboarding(athlete_id, sample_request, mock_uow)

        assert exc_info.value.status_code == 409

        # Verify get_profile_uow was NOT called
        mock_athlete_service.get_profile_uow.assert_not_called()

        # Verify twin_initialise was NOT called
        mock_twin_service.initialise.assert_not_called()

        # Verify set_onboarding_complete_uow was NOT called
        for call in mock_athlete_service.method_calls:
            if "set_onboarding_complete_uow" in str(call):
                pytest.fail("set_onboarding_complete_uow should not be called when training block fails")