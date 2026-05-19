"""Unit tests for TrainingBlockService UoW methods."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.training_block import TrainingBlockCreate
from app.models.enums import GoalStatus
from app.services.training_block_service import TrainingBlockService
from tests.factories.training_block_factory import make_training_block_full, make_training_block


@pytest.fixture
def mock_repo():
    """Mock TrainingBlockRepository."""
    repo = MagicMock()
    repo.get_active_by_athlete = AsyncMock()
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def service(mock_repo):
    """TrainingBlockService with mocked repository."""
    return TrainingBlockService(mock_repo)


@pytest.fixture
def mock_uow():
    """Mock UnitOfWork."""
    uow = MagicMock()
    uow.blocks = MagicMock()
    uow.blocks.get_active_by_athlete = AsyncMock()
    uow.blocks.session = MagicMock()
    uow.blocks.session.add = MagicMock()
    uow.blocks.session.flush = AsyncMock()
    return uow


class TestCreateForAthleteUow:
    """Tests for TrainingBlockService.create_for_athlete_uow()."""

    @pytest.mark.asyncio
    async def test_checks_for_existing_active_block_via_uow(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() checks for existing active block via uow.blocks.get_active_by_athlete()."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        mock_uow.blocks.get_active_by_athlete.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_raises_409_when_active_block_exists(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() raises HTTPException 409 when active block exists."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        existing_block = make_training_block(athlete_id=athlete_id)
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=existing_block)

        with pytest.raises(HTTPException) as exc_info:
            await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_builds_payload_with_athlete_id_and_status_active(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() builds payload with athlete_id and status=GoalStatus.ACTIVE."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        added_obj = mock_uow.blocks.session.add.call_args[0][0]
        assert added_obj.athlete_id == athlete_id
        assert added_obj.status == GoalStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_constructs_training_block_orm_object(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() constructs TrainingBlock ORM object."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        result = await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        assert result is not None

    @pytest.mark.asyncio
    async def test_calls_session_add_and_flush(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() calls uow.blocks.session.add() and session.flush()."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        mock_uow.blocks.session.add.assert_called_once()
        mock_uow.blocks.session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_created_orm_object(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() returns the created ORM object."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        result = await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        assert result is not None

    @pytest.mark.asyncio
    async def test_does_not_call_self_repo(
        self, service, mock_uow
    ):
        """Verify create_for_athlete_uow() does NOT call self.repo."""
        athlete_id = uuid.uuid4()
        data = TrainingBlockCreate(
            goal_type="race",
            goal_event_type="marathon",
        )
        mock_uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        await service.create_for_athlete_uow(athlete_id, data, mock_uow)

        # Verify repo.create was NOT called
        service.repo.create.assert_not_called()