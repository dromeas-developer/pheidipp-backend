"""Unit tests for TrainingPreferencesService."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import GoalType, GoalEventType
from app.models.training_preferences import TrainingPreferences
from app.schemas.training_preferences import TrainingPreferencesCreate
from app.services.training_preferences_service import TrainingPreferencesService


@pytest.fixture
def repo_mock():
    """Fixture for mocking TrainingPreferencesRepository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.list_by_athlete = AsyncMock()
    mock.get_active_by_athlete = AsyncMock()
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def service(repo_mock):
    """Fixture for TrainingPreferencesService with mocked repository."""
    return TrainingPreferencesService(repo_mock)


# ============================================================================
# create Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_training_preferences_creates_record(service, repo_mock):
    """Test that creating training preferences persists the record correctly."""
    athlete_id = uuid.uuid4()
    pref_id = uuid.uuid4()

    create_data = TrainingPreferencesCreate(
        athlete_id=athlete_id,
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.HALF_MARATHON,
        weekly_volume_hours=10.0,
    )

    created_preferences = TrainingPreferences(
        id=pref_id,
        athlete_id=athlete_id,
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.HALF_MARATHON,
        weekly_volume_hours=10.0,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    repo_mock.create = AsyncMock(return_value=created_preferences)

    result = await service.create(create_data)

    assert result.id == pref_id
    assert result.athlete_id == athlete_id
    assert result.goal_type == GoalType.RACE
    assert result.goal_event_type == GoalEventType.HALF_MARATHON
    assert result.weekly_volume_hours == 10.0

    repo_mock.create.assert_called_once_with(
        athlete_id=athlete_id,
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.HALF_MARATHON,
        weekly_volume_hours=10.0,
    )


# ============================================================================
# get_active_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_active_training_preferences_returns_latest(service, repo_mock):
    """Test that get_active_by_athlete returns the most recent preferences version."""
    athlete_id = uuid.uuid4()

    latest_preferences = TrainingPreferences(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        goal_type="race",
        weekly_volume_hours=15.0,
        created_at=datetime(2024, 2, 1, 0, 0, 0),
        updated_at=datetime(2024, 2, 1, 0, 0, 0),
    )

    repo_mock.get_active_by_athlete = AsyncMock(return_value=latest_preferences)

    result = await service.get_active_by_athlete(athlete_id)

    assert result is not None
    assert result.id == latest_preferences.id
    assert result.weekly_volume_hours == 15.0

    repo_mock.get_active_by_athlete.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_active_training_preferences_returns_none_when_missing(service, repo_mock):
    """Test that get_active_by_athlete returns None when athlete has no preferences."""
    athlete_id = uuid.uuid4()

    repo_mock.get_active_by_athlete = AsyncMock(return_value=None)

    result = await service.get_active_by_athlete(athlete_id)

    assert result is None

    repo_mock.get_active_by_athlete.assert_called_once_with(athlete_id)


# ============================================================================
# list_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_by_athlete_returns_all_versions(service, repo_mock):
    """Test that list_by_athlete returns all preference versions for an athlete."""
    athlete_id = uuid.uuid4()

    preferences_list = [
        TrainingPreferences(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            goal_type="race",
            created_at=datetime(2024, 2, 1, 0, 0, 0),
            updated_at=datetime(2024, 2, 1, 0, 0, 0),
        ),
        TrainingPreferences(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            goal_type="fitness_improvement",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            updated_at=datetime(2024, 1, 1, 0, 0, 0),
        ),
    ]

    repo_mock.list_by_athlete = AsyncMock(return_value=preferences_list)

    result = await service.list_by_athlete(athlete_id)

    assert len(result) == 2
    assert result[0].goal_type == "race"
    assert result[1].goal_type == "fitness_improvement"

    repo_mock.list_by_athlete.assert_called_once_with(athlete_id)


# ============================================================================
# get_by_id Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_by_id_returns_preferences(service, repo_mock):
    """Test that get_by_id returns the specific preferences record."""
    pref_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    preferences = TrainingPreferences(
        id=pref_id,
        athlete_id=athlete_id,
        goal_type="race",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    repo_mock.get_by_id = AsyncMock(return_value=preferences)

    result = await service.get_by_id(pref_id)

    assert result is not None
    assert result.id == pref_id

    repo_mock.get_by_id.assert_called_once_with(pref_id)


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_not_found(service, repo_mock):
    """Test that get_by_id returns None when preferences not found."""
    pref_id = uuid.uuid4()

    repo_mock.get_by_id = AsyncMock(return_value=None)

    result = await service.get_by_id(pref_id)

    assert result is None

    repo_mock.get_by_id.assert_called_once_with(pref_id)


# ============================================================================
# update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_modifies_preferences(service, repo_mock):
    """Test that update modifies the preferences record."""
    pref_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    updated_preferences = TrainingPreferences(
        id=pref_id,
        athlete_id=athlete_id,
        goal_type="race",
        weekly_volume_hours=20.0,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 2, 1, 0, 0, 0),
    )

    from app.schemas.training_preferences import TrainingPreferencesUpdate

    update_data = TrainingPreferencesUpdate(weekly_volume_hours=20.0)
    repo_mock.update = AsyncMock(return_value=updated_preferences)

    result = await service.update(pref_id, update_data)

    assert result is not None
    assert result.weekly_volume_hours == 20.0

    repo_mock.update.assert_called_once_with(pref_id, weekly_volume_hours=20.0)


# ============================================================================
# delete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_returns_true_when_deleted(service, repo_mock):
    """Test that delete returns True when the record is deleted."""
    pref_id = uuid.uuid4()

    repo_mock.delete = AsyncMock(return_value=True)

    result = await service.delete(pref_id)

    assert result is True

    repo_mock.delete.assert_called_once_with(pref_id)


@pytest.mark.asyncio
async def test_delete_returns_false_when_not_found(service, repo_mock):
    """Test that delete returns False when the record does not exist."""
    pref_id = uuid.uuid4()

    repo_mock.delete = AsyncMock(return_value=False)

    result = await service.delete(pref_id)

    assert result is False

    repo_mock.delete.assert_called_once_with(pref_id)