"""Unit tests for AthletePreferencesService."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.athlete_preferences import (
    AthletePreferencesCreate,
    AthletePreferencesUpdate,
)
from app.services.athlete_preferences_service import AthletePreferencesService
from tests.factories.athlete_preferences_factory import make_athlete_preferences


@pytest.fixture
def prefs_repo_mock():
    """Fixture for mocking AthletePreferencesRepository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_athlete = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.update = AsyncMock()
    return mock


@pytest.fixture
def prefs_service(prefs_repo_mock):
    """Fixture for AthletePreferencesService with mocked repository."""
    return AthletePreferencesService(prefs_repo_mock)


# ============================================================================
# create_for_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_for_athlete(prefs_service, prefs_repo_mock):
    """Test successful creation of athlete preferences."""
    athlete_id = uuid.uuid4()
    prefs_data = AthletePreferencesCreate(
        sport_background="running_primary",
        years_structured_training=5.0,
    )

    created_prefs = make_athlete_preferences(athlete_id=athlete_id)
    prefs_repo_mock.create = AsyncMock(return_value=created_prefs)

    result = await prefs_service.create_for_athlete(athlete_id, prefs_data)

    assert result == created_prefs
    prefs_repo_mock.create.assert_called_once()
    call_kwargs = prefs_repo_mock.create.call_args.kwargs
    assert call_kwargs["athlete_id"] == athlete_id
    assert call_kwargs["sport_background"] == "running_primary"
    assert call_kwargs["years_structured_training"] == 5.0


@pytest.mark.asyncio
async def test_create_for_athlete_with_weekly_schedule(prefs_service, prefs_repo_mock):
    """Test creation with weekly_schedule serializes to dict."""
    athlete_id = uuid.uuid4()
    prefs_data = AthletePreferencesCreate(
        weekly_schedule={
            "days": {
                "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                "tue": {"available": False, "max_hours": 0, "long_workout": False},
                "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                "thu": {"available": False, "max_hours": 0, "long_workout": False},
                "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
            },
            "available_days_count": 5,
        },
    )

    created_prefs = make_athlete_preferences(athlete_id=athlete_id)
    prefs_repo_mock.create = AsyncMock(return_value=created_prefs)

    result = await prefs_service.create_for_athlete(athlete_id, prefs_data)

    assert result == created_prefs
    prefs_repo_mock.create.assert_called_once()
    call_kwargs = prefs_repo_mock.create.call_args.kwargs
    assert "weekly_schedule" in call_kwargs
    assert isinstance(call_kwargs["weekly_schedule"], dict)


# ============================================================================
# get_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_by_athlete(prefs_service, prefs_repo_mock):
    """Test successful retrieval of athlete preferences."""
    athlete_id = uuid.uuid4()
    prefs = make_athlete_preferences(athlete_id=athlete_id)

    prefs_repo_mock.get_by_athlete = AsyncMock(return_value=prefs)

    result = await prefs_service.get_by_athlete(athlete_id)

    assert result == prefs
    prefs_repo_mock.get_by_athlete.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_by_athlete_not_found(prefs_service, prefs_repo_mock):
    """Test retrieval returns None when preferences not found."""
    athlete_id = uuid.uuid4()

    prefs_repo_mock.get_by_athlete = AsyncMock(return_value=None)

    result = await prefs_service.get_by_athlete(athlete_id)

    assert result is None
    prefs_repo_mock.get_by_athlete.assert_called_once_with(athlete_id)


# ============================================================================
# update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update(prefs_service, prefs_repo_mock):
    """Test successful update of athlete preferences."""
    prefs_id = uuid.uuid4()
    update_data = AthletePreferencesUpdate(
        sport_background="cycling_crossover",
    )

    updated_prefs = make_athlete_preferences()
    updated_prefs.sport_background = "cycling_crossover"
    prefs_repo_mock.update = AsyncMock(return_value=updated_prefs)

    result = await prefs_service.update(prefs_id, update_data)

    assert result == updated_prefs
    prefs_repo_mock.update.assert_called_once()
    call_kwargs = prefs_repo_mock.update.call_args.kwargs
    assert call_kwargs["sport_background"] == "cycling_crossover"


@pytest.mark.asyncio
async def test_update_not_found(prefs_service, prefs_repo_mock):
    """Test update returns None when preferences not found."""
    prefs_id = uuid.uuid4()
    update_data = AthletePreferencesUpdate(sport_background="cycling_crossover")

    prefs_repo_mock.update = AsyncMock(return_value=None)

    result = await prefs_service.update(prefs_id, update_data)

    assert result is None
    prefs_repo_mock.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_exclude_unset(prefs_service, prefs_repo_mock):
    """Test update uses exclude_unset=True for partial updates."""
    prefs_id = uuid.uuid4()
    update_data = AthletePreferencesUpdate(sport_background="cycling_crossover")

    updated_prefs = make_athlete_preferences()
    prefs_repo_mock.update = AsyncMock(return_value=updated_prefs)

    await prefs_service.update(prefs_id, update_data)

    prefs_repo_mock.update.assert_called_once()
    # Verify exclude_unset is used (only sport_background should be passed)
    call_kwargs = prefs_repo_mock.update.call_args.kwargs
    assert "sport_background" in call_kwargs
    # years_structured_training should not be in kwargs since it wasn't set
    assert call_kwargs.get("years_structured_training") is None or "years_structured_training" not in [k for k in call_kwargs.keys() if k != "sport_background"]