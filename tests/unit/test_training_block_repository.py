"""Integration tests for TrainingBlockRepository."""

import uuid
from datetime import date, datetime

import pytest

from app.models.athlete import Athlete
from app.models.training_block import TrainingBlock
from app.models.enums import AthleteStatus, GoalStatus, GoalType, GoalEventType
from app.repositories.training_block_repository import TrainingBlockRepository
from tests.factories.athlete_factory import make_athlete
from tests.factories.training_block_factory import make_training_block, make_training_block_full


@pytest.mark.asyncio
async def test_get_active_by_athlete_returns_active_block(test_db_session):
    """Test get_active_by_athlete returns the active block for a given athlete."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()
    await test_db_session.refresh(athlete)

    # Create active training block
    block = make_training_block_full(athlete_id=athlete.id)
    test_db_session.add(block)
    await test_db_session.commit()
    await test_db_session.refresh(block)

    # Retrieve active block
    repo = TrainingBlockRepository(test_db_session)
    result = await repo.get_active_by_athlete(athlete.id)

    assert result is not None
    assert result.id == block.id
    assert result.status == GoalStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_active_by_athlete_returns_none_when_no_active_block(test_db_session):
    """Test get_active_by_athlete returns None when no active block exists."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # Create completed block (not active)
    block = make_training_block(athlete_id=athlete.id)
    block.status = GoalStatus.COMPLETED
    test_db_session.add(block)
    await test_db_session.commit()

    # Try to retrieve active block
    repo = TrainingBlockRepository(test_db_session)
    result = await repo.get_active_by_athlete(athlete.id)

    assert result is None


@pytest.mark.asyncio
async def test_get_active_by_athlete_returns_most_recent(test_db_session):
    """Test get_active_by_athlete returns the most recent active block when multiple exist."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # Create first active block (older)
    block1 = make_training_block(athlete_id=athlete.id)
    block1.created_at = datetime(2024, 1, 1, 0, 0, 0)
    test_db_session.add(block1)

    # Create second active block (more recent)
    block2 = make_training_block(athlete_id=athlete.id)
    block2.created_at = datetime(2024, 2, 1, 0, 0, 0)
    test_db_session.add(block2)

    await test_db_session.commit()

    # Retrieve active block - should return the most recent
    repo = TrainingBlockRepository(test_db_session)
    result = await repo.get_active_by_athlete(athlete.id)

    assert result is not None
    assert result.id == block2.id


@pytest.mark.asyncio
async def test_list_by_athlete_returns_all_blocks(test_db_session):
    """Test list_by_athlete returns all blocks ordered by created_at DESC."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # Create multiple blocks
    block1 = make_training_block(athlete_id=athlete.id)
    block1.created_at = datetime(2024, 1, 1, 0, 0, 0)
    test_db_session.add(block1)

    block2 = make_training_block(athlete_id=athlete.id)
    block2.created_at = datetime(2024, 2, 1, 0, 0, 0)
    test_db_session.add(block2)

    await test_db_session.commit()

    # List all blocks
    repo = TrainingBlockRepository(test_db_session)
    result = await repo.list_by_athlete(athlete.id)

    assert len(result) == 2
    # Should be ordered by created_at DESC (most recent first)
    assert result[0].id == block2.id
    assert result[1].id == block1.id


@pytest.mark.asyncio
async def test_list_by_athlete_returns_empty_list(test_db_session):
    """Test list_by_athlete returns empty list when no blocks exist."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # List blocks
    repo = TrainingBlockRepository(test_db_session)
    result = await repo.list_by_athlete(athlete.id)

    assert result == []


@pytest.mark.asyncio
async def test_create(test_db_session):
    """Test creating a training block."""
    # Create athlete
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    # Create block
    repo = TrainingBlockRepository(test_db_session)
    created = await repo.create(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.MARATHON,
        status=GoalStatus.ACTIVE,
    )

    await test_db_session.commit()
    await test_db_session.refresh(created)

    assert created.id is not None
    assert created.athlete_id == athlete.id
    assert created.goal_type == GoalType.RACE
    assert created.status == GoalStatus.ACTIVE


@pytest.mark.asyncio
async def test_get_by_id(test_db_session):
    """Test getting a block by ID."""
    # Create athlete and block
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    block = make_training_block_full(athlete_id=athlete.id)
    test_db_session.add(block)
    await test_db_session.commit()
    await test_db_session.refresh(block)

    # Retrieve by ID
    repo = TrainingBlockRepository(test_db_session)
    result = await repo.get_by_id(block.id)

    assert result is not None
    assert result.id == block.id


@pytest.mark.asyncio
async def test_update(test_db_session):
    """Test updating a training block."""
    # Create athlete and block
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    block = make_training_block(athlete_id=athlete.id)
    test_db_session.add(block)
    await test_db_session.commit()
    await test_db_session.refresh(block)

    # Update block
    repo = TrainingBlockRepository(test_db_session)
    updated = await repo.update(
        block.id,
        status=GoalStatus.COMPLETED,
        goal_description="Updated description",
    )

    await test_db_session.commit()
    await test_db_session.refresh(updated)

    assert updated.status == GoalStatus.COMPLETED
    assert updated.goal_description == "Updated description"


@pytest.mark.asyncio
async def test_delete(test_db_session):
    """Test deleting a training block."""
    # Create athlete and block
    athlete = make_athlete()
    test_db_session.add(athlete)
    await test_db_session.commit()

    block = make_training_block(athlete_id=athlete.id)
    test_db_session.add(block)
    await test_db_session.commit()
    await test_db_session.refresh(block)

    # Delete block
    repo = TrainingBlockRepository(test_db_session)
    await repo.delete(block.id)

    await test_db_session.commit()

    # Verify deleted
    result = await repo.get_by_id(block.id)
    assert result is None