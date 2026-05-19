"""Unit tests for TrainingBlockService."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.training_block import (
    TrainingBlockCreate,
    TrainingBlockUpdate,
)
from app.models.enums import GoalStatus
from app.services.training_block_service import TrainingBlockService
from tests.factories.training_block_factory import make_training_block, make_training_block_full


@pytest.fixture
def block_repo_mock():
    """Fixture for mocking TrainingBlockRepository."""
    mock = MagicMock()
    mock.get_active_by_athlete = AsyncMock()
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.update = AsyncMock()
    mock.list_by_athlete = AsyncMock()
    return mock


@pytest.fixture
def block_service(block_repo_mock):
    """Fixture for TrainingBlockService with mocked repository."""
    return TrainingBlockService(block_repo_mock)


# ============================================================================
# create_for_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_create_for_athlete_success(block_service, block_repo_mock):
    """Test successful creation of training block when no active block exists."""
    athlete_id = uuid.uuid4()
    block_data = TrainingBlockCreate(
        goal_type="race",
        goal_event_type="marathon",
        goal_event_name="Boston Marathon 2024",
    )

    # No active block exists
    block_repo_mock.get_active_by_athlete = AsyncMock(return_value=None)

    created_block = make_training_block_full(athlete_id=athlete_id)
    block_repo_mock.create = AsyncMock(return_value=created_block)

    result = await block_service.create_for_athlete(athlete_id, block_data)

    assert result == created_block
    block_repo_mock.get_active_by_athlete.assert_called_once_with(athlete_id)
    block_repo_mock.create.assert_called_once()
    call_kwargs = block_repo_mock.create.call_args.kwargs
    assert call_kwargs["athlete_id"] == athlete_id
    assert call_kwargs["status"] == GoalStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_for_athlete_active_block_exists(block_service, block_repo_mock):
    """Test creation raises 409 when active block already exists."""
    athlete_id = uuid.uuid4()
    block_data = TrainingBlockCreate(
        goal_type="race",
        goal_event_type="marathon",
    )

    # Active block already exists
    existing_block = make_training_block(athlete_id=athlete_id)
    block_repo_mock.get_active_by_athlete = AsyncMock(return_value=existing_block)

    with pytest.raises(HTTPException) as exc_info:
        await block_service.create_for_athlete(athlete_id, block_data)

    assert exc_info.value.status_code == 409
    assert "complete or abandon" in exc_info.value.detail.lower()
    block_repo_mock.create.assert_not_called()


# ============================================================================
# get_active_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_active_by_athlete(block_service, block_repo_mock):
    """Test successful retrieval of active training block."""
    athlete_id = uuid.uuid4()
    block = make_training_block(athlete_id=athlete_id)

    block_repo_mock.get_active_by_athlete = AsyncMock(return_value=block)

    result = await block_service.get_active_by_athlete(athlete_id)

    assert result == block
    block_repo_mock.get_active_by_athlete.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_get_active_by_athlete_not_found(block_service, block_repo_mock):
    """Test retrieval returns None when no active block exists."""
    athlete_id = uuid.uuid4()

    block_repo_mock.get_active_by_athlete = AsyncMock(return_value=None)

    result = await block_service.get_active_by_athlete(athlete_id)

    assert result is None
    block_repo_mock.get_active_by_athlete.assert_called_once_with(athlete_id)


# ============================================================================
# list_by_athlete Tests
# ============================================================================


@pytest.mark.asyncio
async def test_list_by_athlete(block_service, block_repo_mock):
    """Test successful listing of all training blocks for an athlete."""
    athlete_id = uuid.uuid4()
    blocks = [
        make_training_block(athlete_id=athlete_id),
        make_training_block(athlete_id=athlete_id),
    ]

    block_repo_mock.list_by_athlete = AsyncMock(return_value=blocks)

    result = await block_service.list_by_athlete(athlete_id)

    assert result == blocks
    block_repo_mock.list_by_athlete.assert_called_once_with(athlete_id)


@pytest.mark.asyncio
async def test_list_by_athlete_empty(block_service, block_repo_mock):
    """Test listing returns empty list when no blocks exist."""
    athlete_id = uuid.uuid4()

    block_repo_mock.list_by_athlete = AsyncMock(return_value=[])

    result = await block_service.list_by_athlete(athlete_id)

    assert result == []
    block_repo_mock.list_by_athlete.assert_called_once_with(athlete_id)


# ============================================================================
# update Tests
# ============================================================================


@pytest.mark.asyncio
async def test_update(block_service, block_repo_mock):
    """Test successful update of training block."""
    block_id = uuid.uuid4()
    update_data = TrainingBlockUpdate(
        goal_event_date=date(2024, 6, 1),
        goal_description="Updated description",
    )

    updated_block = make_training_block()
    updated_block.goal_event_date = date(2024, 6, 1)
    updated_block.goal_description = "Updated description"
    block_repo_mock.update = AsyncMock(return_value=updated_block)

    result = await block_service.update(block_id, update_data)

    assert result == updated_block
    block_repo_mock.update.assert_called_once()
    call_kwargs = block_repo_mock.update.call_args.kwargs
    assert call_kwargs["goal_event_date"] == date(2024, 6, 1)
    assert call_kwargs["goal_description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_not_found(block_service, block_repo_mock):
    """Test update returns None when block not found."""
    block_id = uuid.uuid4()
    update_data = TrainingBlockUpdate(goal_description="Updated")

    block_repo_mock.update = AsyncMock(return_value=None)

    result = await block_service.update(block_id, update_data)

    assert result is None
    block_repo_mock.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_only_accepts_allowed_fields(block_service, block_repo_mock):
    """Test that update only accepts fields in TrainingBlockUpdate schema."""
    block_id = uuid.uuid4()
    # Only status, goal_event_date, goal_description are allowed
    update_data = TrainingBlockUpdate(status=GoalStatus.COMPLETED)

    updated_block = make_training_block()
    updated_block.status = GoalStatus.COMPLETED
    block_repo_mock.update = AsyncMock(return_value=updated_block)

    result = await block_service.update(block_id, update_data)

    assert result == updated_block
    call_kwargs = block_repo_mock.update.call_args.kwargs
    # Verify that immutable fields are NOT passed
    assert "goal_type" not in call_kwargs
    assert "goal_event_type" not in call_kwargs
    assert "custom_distance_km" not in call_kwargs
    assert "weekly_volume_hours" not in call_kwargs
    assert "fitness_level" not in call_kwargs


# ============================================================================
# complete_block Tests
# ============================================================================


@pytest.mark.asyncio
async def test_complete_block(block_service, block_repo_mock):
    """Test completing a training block sets status to COMPLETED."""
    block_id = uuid.uuid4()

    completed_block = make_training_block()
    completed_block.status = GoalStatus.COMPLETED
    block_repo_mock.update = AsyncMock(return_value=completed_block)

    result = await block_service.complete_block(block_id)

    assert result == completed_block
    block_repo_mock.update.assert_called_once_with(block_id, status=GoalStatus.COMPLETED)


# ============================================================================
# abandon_block Tests
# ============================================================================


@pytest.mark.asyncio
async def test_abandon_block(block_service, block_repo_mock):
    """Test abandoning a training block sets status to ABANDONED."""
    block_id = uuid.uuid4()

    abandoned_block = make_training_block()
    abandoned_block.status = GoalStatus.ABANDONED
    block_repo_mock.update = AsyncMock(return_value=abandoned_block)

    result = await block_service.abandon_block(block_id)

    assert result == abandoned_block
    block_repo_mock.update.assert_called_once_with(block_id, status=GoalStatus.ABANDONED)