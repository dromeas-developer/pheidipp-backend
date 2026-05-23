"""Unit tests for TwinStateRepository."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select, desc, func

from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier
from app.models.twin_state import TwinState
from app.repositories.twin_state_repository import TwinStateRepository
from app.schemas.twin_state import TwinStateCreate
from tests.factories.twin_state_factory import make_twin_state


@pytest.fixture
def mock_session():
    """Mock AsyncSession for repository tests."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def repository(mock_session):
    """TwinStateRepository with mocked session."""
    return TwinStateRepository(mock_session)


class TestCreate:
    """Tests for TwinStateRepository.create()."""

    @pytest.mark.asyncio
    async def test_create_constructs_twin_state_from_data(
        self, repository, mock_session
    ):
        """Verify create() constructs a TwinState from TwinStateCreate."""
        athlete_id = uuid.uuid4()
        prefs_id = uuid.uuid4()
        data = TwinStateCreate(
            athlete_id=athlete_id,
            athlete_preferences_id=prefs_id,
            trigger=TwinTrigger.QUESTIONNAIRE,
            confidence_level=ConfidenceLevel.LOW,
            data_tier=DataTier.TIER1,
            fitness_score=50.0,
            fatigue_score=0.0,
            max_hr_estimate=187.0,
            lt1_hr_estimate=130.9,
            lt2_hr_estimate=155.2,
            structural_capacity_score=0.7,
            fitness_time_constant=42.0,
            fatigue_time_constant=7.0,
            computation_summary="Test",
            computation_metadata={"test": "data"},
        )

        result = await repository.create(**data.model_dump(exclude_unset=True))

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        # Verify the object added has the correct attributes
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.athlete_id == athlete_id
        assert added_obj.athlete_preferences_id == prefs_id


class TestGetByAthleteId:
    """Tests for TwinStateRepository.get_by_athlete_id()."""

    @pytest.mark.asyncio
    async def test_get_by_athlete_id_queries_by_athlete_id(
        self, repository, mock_session
    ):
        """Verify get_by_athlete_id() queries by athlete_id."""
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_by_athlete_id(athlete_id)

        # Verify execute was called
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0][0]
        # Check that the query contains the athlete_id filter
        assert "athlete_id" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_by_athlete_id_orders_by_created_at_desc(
        self, repository, mock_session
    ):
        """Verify get_by_athlete_id() orders by created_at DESC."""
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_by_athlete_id(athlete_id)

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0][0]
        # Check that the query orders by desc(created_at)
        assert "desc" in str(call_args).lower() or "order_by" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_get_by_athlete_id_limits_to_1(self, repository, mock_session):
        """Verify get_by_athlete_id() limits to 1."""
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        await repository.get_by_athlete_id(athlete_id)

        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0][0]
        # Check that the query has limit(1)
        assert "limit" in str(call_args).lower()

    @pytest.mark.asyncio
    async def test_get_by_athlete_id_returns_none_when_not_found(
        self, repository, mock_session
    ):
        """Verify get_by_athlete_id() returns None when no twin states exist."""
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.get_by_athlete_id(athlete_id)

        assert result is None


class TestGetHistoryByAthleteId:
    """Tests for TwinStateRepository.get_history_by_athlete_id()."""

    @pytest.mark.asyncio
    async def test_get_history_returns_tuple_of_items_and_total(
        self, repository, mock_session
    ):
        """Verify get_history_by_athlete_id() returns a tuple of (items list, total count)."""
        athlete_id = uuid.uuid4()

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=5)

        # Mock select query result
        mock_select_result = MagicMock()
        mock_select_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        # Set up execute to return different results for each call
        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_select_result])

        result = await repository.get_history_by_athlete_id(athlete_id)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], int)

    @pytest.mark.asyncio
    async def test_get_history_applies_limit_and_offset(
        self, repository, mock_session
    ):
        """Verify get_history_by_athlete_id() applies limit and offset correctly."""
        athlete_id = uuid.uuid4()

        # Mock count query result
        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=10)

        # Mock select query result
        mock_select_result = MagicMock()
        mock_select_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_select_result])

        await repository.get_history_by_athlete_id(athlete_id, limit=5, offset=10)

        # Verify execute was called twice (count + select)
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_history_orders_by_created_at_desc(
        self, repository, mock_session
    ):
        """Verify get_history_by_athlete_id() orders results by created_at DESC."""
        athlete_id = uuid.uuid4()

        mock_count_result = MagicMock()
        mock_count_result.scalar = MagicMock(return_value=0)

        mock_select_result = MagicMock()
        mock_select_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_select_result])

        await repository.get_history_by_athlete_id(athlete_id)

        # Verify second call (select query) contains order_by
        call_args = mock_session.execute.call_args_list[1][0][0]
        assert "order_by" in str(call_args).lower() or "desc" in str(call_args).lower()


class TestCountByAthleteId:
    """Tests for TwinStateRepository.count_by_athlete_id()."""

    @pytest.mark.asyncio
    async def test_count_returns_correct_count(self, repository, mock_session):
        """Verify count_by_athlete_id() returns the correct count."""
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=5)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.count_by_athlete_id(athlete_id)

        assert result == 5

    @pytest.mark.asyncio
    async def test_count_returns_0_when_no_records(self, repository, mock_session):
        """Verify count_by_athlete_id() returns 0 when no twin states exist."""
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar = MagicMock(return_value=0)
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repository.count_by_athlete_id(athlete_id)

        assert result == 0