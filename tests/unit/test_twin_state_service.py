"""Unit tests for TwinStateService."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.twin_state_service import TwinStateService
from tests.factories.twin_state_factory import make_twin_state


@pytest.fixture
def service():
    """TwinStateService instance."""
    return TwinStateService()


@pytest.fixture
def mock_uow():
    """Mock UnitOfWork with twin_states repository."""
    uow = MagicMock()
    uow.twin_states = MagicMock()
    uow.twin_states.get_by_athlete_id = AsyncMock()
    uow.twin_states.get_history_by_athlete_id = AsyncMock()
    return uow


class TestGetCurrentTwinState:
    """Tests for TwinStateService.get_current_twin_state()."""

    @pytest.mark.asyncio
    async def test_returns_twin_state_response_when_exists(self, service, mock_uow):
        """Verify get_current_twin_state() returns TwinStateResponse when a twin state exists."""
        athlete_id = uuid.uuid4()
        twin_state = make_twin_state(athlete_id=athlete_id)
        mock_uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin_state)

        result = await service.get_current_twin_state(athlete_id, mock_uow)

        assert result is not None
        assert result.athlete_id == athlete_id
        assert result.fitness_score == twin_state.fitness_score

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(self, service, mock_uow):
        """Verify get_current_twin_state() returns None when no twin state exists."""
        athlete_id = uuid.uuid4()
        mock_uow.twin_states.get_by_athlete_id = AsyncMock(return_value=None)

        result = await service.get_current_twin_state(athlete_id, mock_uow)

        assert result is None

    @pytest.mark.asyncio
    async def test_delegates_to_repository(self, service, mock_uow):
        """Verify get_current_twin_state() delegates to uow.twin_states.get_by_athlete_id()."""
        athlete_id = uuid.uuid4()
        mock_uow.twin_states.get_by_athlete_id = AsyncMock(return_value=None)

        await service.get_current_twin_state(athlete_id, mock_uow)

        mock_uow.twin_states.get_by_athlete_id.assert_called_once_with(athlete_id)


class TestGetTwinStateHistory:
    """Tests for TwinStateService.get_twin_state_history()."""

    @pytest.mark.asyncio
    async def test_returns_tuple_of_responses_and_total(self, service, mock_uow):
        """Verify get_twin_state_history() returns a tuple of (list of TwinStateResponse, total count)."""
        athlete_id = uuid.uuid4()
        twin_states = [
            make_twin_state(athlete_id=athlete_id),
            make_twin_state(athlete_id=athlete_id),
        ]
        mock_uow.twin_states.get_history_by_athlete_id = AsyncMock(
            return_value=(twin_states, 2)
        )

        result = await service.get_twin_state_history(athlete_id, mock_uow)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert len(result[0]) == 2
        assert result[1] == 2

    @pytest.mark.asyncio
    async def test_passes_limit_and_offset_to_repository(
        self, service, mock_uow
    ):
        """Verify get_twin_state_history() passes limit and offset to the repository."""
        athlete_id = uuid.uuid4()
        mock_uow.twin_states.get_history_by_athlete_id = AsyncMock(
            return_value=([], 0)
        )

        await service.get_twin_state_history(athlete_id, mock_uow, limit=10, offset=5)

        mock_uow.twin_states.get_history_by_athlete_id.assert_called_once_with(
            athlete_id, 10, 5
        )

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_history(self, service, mock_uow):
        """Verify get_twin_state_history() returns empty list and zero total when no history exists."""
        athlete_id = uuid.uuid4()
        mock_uow.twin_states.get_history_by_athlete_id = AsyncMock(
            return_value=([], 0)
        )

        result = await service.get_twin_state_history(athlete_id, mock_uow)

        assert result[0] == []
        assert result[1] == 0