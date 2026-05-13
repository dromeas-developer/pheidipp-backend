"""Unit tests for ActivityService."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.activity import Activity
from app.models.enums import ActivityType, PerceivedEffort
from app.schemas.activity import ActivityCreate, ActivityListParams
from app.services.activity_service import ActivityService


@pytest.fixture
def activity_repo_mock():
    """Fixture for mocking ActivityRepository."""
    mock = MagicMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.get_by_athlete = AsyncMock()
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    mock.count_by_athlete = AsyncMock()
    return mock


@pytest.fixture
def athlete_repo_mock():
    """Fixture for mocking AthleteRepository."""
    mock = MagicMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def service(activity_repo_mock, athlete_repo_mock):
    """Fixture for ActivityService with mocked repositories."""
    return ActivityService(activity_repo_mock, athlete_repo_mock)


# ============================================================================
# create_activity Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_activity_persists_activity(service, activity_repo_mock, athlete_repo_mock):
    """Test that creating an activity stores all expected fields."""
    athlete_id = uuid.uuid4()
    activity_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=True)

    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)

    create_data = ActivityCreate(
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        title="Morning Run",
        description="A nice run",
        started_at=started_at,
        finished_at=finished_at,
        perceived_effort=PerceivedEffort.MODERATE,
        avg_heart_rate=145,
        max_heart_rate=175,
        distance_meters=10000.0,
        calories=500,
    )

    created_activity = Activity(
        id=activity_id,
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        title="Morning Run",
        description="A nice run",
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=3600,
        perceived_effort=PerceivedEffort.MODERATE,
        avg_heart_rate=145,
        max_heart_rate=175,
        distance_meters=10000.0,
        calories=500,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )

    activity_repo_mock.create = AsyncMock(return_value=created_activity)

    result = await service.create_activity(create_data)

    assert result.id == activity_id
    assert result.athlete_id == athlete_id
    assert result.activity_type == ActivityType.RUNNING
    assert result.title == "Morning Run"
    assert result.description == "A nice run"
    assert result.duration_seconds == 3600
    assert result.perceived_effort == PerceivedEffort.MODERATE
    assert result.avg_heart_rate == 145
    assert result.max_heart_rate == 175
    assert result.distance_meters == 10000.0
    assert result.calories == 500

    activity_repo_mock.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_activity_raises_error_for_missing_athlete(service, activity_repo_mock, athlete_repo_mock):
    """Test that creating an activity raises error when athlete does not exist."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=None)

    create_data = ActivityCreate(
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        started_at=datetime(2024, 1, 1, 10, 0, 0),
        finished_at=datetime(2024, 1, 1, 11, 0, 0),
    )

    with pytest.raises(ValueError, match=f"Athlete with id {athlete_id} not found"):
        await service.create_activity(create_data)

    activity_repo_mock.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_activity_raises_error_when_finished_before_started(service, activity_repo_mock, athlete_repo_mock):
    """Test that creating an activity raises error when finished_at <= started_at."""
    athlete_id = uuid.uuid4()

    athlete_repo_mock.get_by_id = AsyncMock(return_value=True)

    create_data = ActivityCreate(
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        started_at=datetime(2024, 1, 1, 11, 0, 0),
        finished_at=datetime(2024, 1, 1, 10, 0, 0),
    )

    with pytest.raises(ValueError, match="finished_at must be after started_at"):
        await service.create_activity(create_data)

    activity_repo_mock.create.assert_not_called()


# ============================================================================
# list_athlete_activities Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_activities_filters_by_date_range(service, activity_repo_mock):
    """Test that date_from and date_to filtering works correctly."""
    athlete_id = uuid.uuid4()

    date_from = datetime(2024, 1, 1, 0, 0, 0)
    date_to = datetime(2024, 1, 31, 23, 59, 59)

    params = ActivityListParams(
        date_from=date_from,
        date_to=date_to,
    )

    activities = [
        Activity(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            activity_type=ActivityType.RUNNING,
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            finished_at=datetime(2024, 1, 15, 11, 0, 0),
            created_at=datetime(2024, 1, 15, 0, 0, 0),
            updated_at=datetime(2024, 1, 15, 0, 0, 0),
        ),
    ]

    activity_repo_mock.get_by_athlete = AsyncMock(return_value=activities)

    result = await service.list_athlete_activities(athlete_id, params)

    assert len(result) == 1

    activity_repo_mock.get_by_athlete.assert_called_once_with(
        athlete_id=athlete_id,
        skip=0,
        limit=50,
        activity_type=None,
        date_from=date_from,
        date_to=date_to,
    )


@pytest.mark.asyncio
async def test_list_activities_filters_by_activity_type(service, activity_repo_mock):
    """Test that only requested activity type is returned."""
    athlete_id = uuid.uuid4()

    params = ActivityListParams(
        activity_type=ActivityType.RUNNING,
    )

    activities = [
        Activity(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            activity_type=ActivityType.RUNNING,
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            finished_at=datetime(2024, 1, 15, 11, 0, 0),
            created_at=datetime(2024, 1, 15, 0, 0, 0),
            updated_at=datetime(2024, 1, 15, 0, 0, 0),
        ),
    ]

    activity_repo_mock.get_by_athlete = AsyncMock(return_value=activities)

    result = await service.list_athlete_activities(athlete_id, params)

    assert len(result) == 1
    assert result[0].activity_type == ActivityType.RUNNING

    activity_repo_mock.get_by_athlete.assert_called_once_with(
        athlete_id=athlete_id,
        skip=0,
        limit=50,
        activity_type=ActivityType.RUNNING,
        date_from=None,
        date_to=None,
    )


@pytest.mark.asyncio
async def test_list_activities_applies_limit_and_offset(service, activity_repo_mock):
    """Test that pagination behaves correctly."""
    athlete_id = uuid.uuid4()

    params = ActivityListParams(
        limit=10,
        offset=20,
    )

    activities = [
        Activity(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            activity_type=ActivityType.RUNNING,
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            finished_at=datetime(2024, 1, 15, 11, 0, 0),
            created_at=datetime(2024, 1, 15, 0, 0, 0),
            updated_at=datetime(2024, 1, 15, 0, 0, 0),
        ),
    ]

    activity_repo_mock.get_by_athlete = AsyncMock(return_value=activities)

    result = await service.list_athlete_activities(athlete_id, params)

    assert len(result) == 1

    activity_repo_mock.get_by_athlete.assert_called_once_with(
        athlete_id=athlete_id,
        skip=20,
        limit=10,
        activity_type=None,
        date_from=None,
        date_to=None,
    )


# ============================================================================
# delete_activity Tests
# ============================================================================


@pytest.mark.asyncio
async def test_delete_activity_removes_record(service, activity_repo_mock):
    """Test that delete actually removes the activity."""
    activity_id = uuid.uuid4()

    activity_repo_mock.delete = AsyncMock(return_value=True)

    result = await service.delete_activity(activity_id)

    assert result is True

    activity_repo_mock.delete.assert_called_once_with(activity_id)


@pytest.mark.asyncio
async def test_delete_missing_activity_returns_false(service, activity_repo_mock):
    """Test that deleting nonexistent activity is handled safely."""
    activity_id = uuid.uuid4()

    activity_repo_mock.delete = AsyncMock(return_value=False)

    result = await service.delete_activity(activity_id)

    assert result is False

    activity_repo_mock.delete.assert_called_once_with(activity_id)


# ============================================================================
# get_activity Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_activity_returns_activity(service, activity_repo_mock):
    """Test that get_activity returns the activity when found."""
    activity_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    activity = Activity(
        id=activity_id,
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        started_at=datetime(2024, 1, 15, 10, 0, 0),
        finished_at=datetime(2024, 1, 15, 11, 0, 0),
        created_at=datetime(2024, 1, 15, 0, 0, 0),
        updated_at=datetime(2024, 1, 15, 0, 0, 0),
    )

    activity_repo_mock.get_by_id = AsyncMock(return_value=activity)

    result = await service.get_activity(activity_id)

    assert result is not None
    assert result.id == activity_id

    activity_repo_mock.get_by_id.assert_called_once_with(activity_id)


@pytest.mark.asyncio
async def test_get_activity_returns_none_when_not_found(service, activity_repo_mock):
    """Test that get_activity returns None when activity not found."""
    activity_id = uuid.uuid4()

    activity_repo_mock.get_by_id = AsyncMock(return_value=None)

    result = await service.get_activity(activity_id)

    assert result is None

    activity_repo_mock.get_by_id.assert_called_once_with(activity_id)


# ============================================================================
# update_activity Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update_activity_modifies_activity(service, activity_repo_mock):
    """Test that update_activity modifies the activity."""
    activity_id = uuid.uuid4()
    athlete_id = uuid.uuid4()

    from app.schemas.activity import ActivityUpdate

    update_data = ActivityUpdate(
        title="Updated Title",
        description="Updated description",
    )

    updated_activity = Activity(
        id=activity_id,
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        title="Updated Title",
        description="Updated description",
        started_at=datetime(2024, 1, 15, 10, 0, 0),
        finished_at=datetime(2024, 1, 15, 11, 0, 0),
        created_at=datetime(2024, 1, 15, 0, 0, 0),
        updated_at=datetime(2024, 1, 16, 0, 0, 0),
    )

    activity_repo_mock.update = AsyncMock(return_value=updated_activity)

    result = await service.update_activity(activity_id, update_data)

    assert result is not None
    assert result.title == "Updated Title"
    assert result.description == "Updated description"

    activity_repo_mock.update.assert_called_once()


# ============================================================================
# count_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_count_by_athlete_returns_count(service, activity_repo_mock):
    """Test that count_by_athlete returns the correct count."""
    athlete_id = uuid.uuid4()

    activity_repo_mock.count_by_athlete = AsyncMock(return_value=42)

    result = await service.count_by_athlete(athlete_id)

    assert result == 42

    activity_repo_mock.count_by_athlete.assert_called_once_with(
        athlete_id, activity_type=None, date_from=None, date_to=None
    )