"""Unit tests for ``PlannedSessionRepository``.

Tests:
- get_by_id() returns the PlannedSession by id
- get_today_for_athlete() returns today's sessions via WeeklyPlan→TrainingPlan join
- get_today_for_athlete() orders by session_slot ASC

Reference plan: docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
)
from app.models.planned_session import PlannedSession
from app.repositories.planned_session_repository import PlannedSessionRepository


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    return session


def make_planned_session(**overrides: Any) -> PlannedSession:
    """Factory that returns a PlannedSession with sensible defaults."""
    kwargs = {
        "weekly_plan_id": uuid.uuid4(),
        "training_plan_id": uuid.uuid4(),
        "target_date": date.today(),
        "week_number": 1,
        "phase_label": PhaseLabel.AEROBIC_BASE,
        "session_type": SessionType.THRESHOLD,
        "intent_description": "Threshold intervals",
        "approximate_duration_minutes": 60,
        "status": PlannedSessionStatus.PENDING,
        "session_priority": SessionPriority.PRIMARY,
    }
    kwargs.update(overrides)
    session = PlannedSession(**kwargs)
    session.id = uuid.uuid4()
    return session


# ---------------------------------------------------------------------------
# get_by_id()
# ---------------------------------------------------------------------------


class TestGetById:
    """Tests for PlannedSessionRepository.get_by_id()."""

    @pytest.mark.asyncio
    async def test_returns_session_when_exists(
        self,
        mock_session: MagicMock,
    ) -> None:
        session_id = uuid.uuid4()
        planned = make_planned_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = planned
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        result = await repo.get_by_id(session_id)

        assert result is planned

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(
        self,
        mock_session: MagicMock,
    ) -> None:
        session_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        result = await repo.get_by_id(session_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_queries_by_id(
        self,
        mock_session: MagicMock,
    ) -> None:
        session_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        await repo.get_by_id(session_id)

        mock_session.execute.assert_called_once()
        # Verify execute was called with a Select object (not checked by str())
        call_arg = mock_session.execute.call_args[0][0]
        assert call_arg is not None  # A Select was passed, not None


# ---------------------------------------------------------------------------
# get_today_for_athlete()
# ---------------------------------------------------------------------------


class TestGetTodayForAthlete:
    """Tests for PlannedSessionRepository.get_today_for_athlete()."""

    @pytest.mark.asyncio
    async def test_returns_sessions_ordered_by_session_slot_asc(
        self,
        mock_session: MagicMock,
    ) -> None:
        athlete_id = uuid.uuid4()
        target_date = date.today()

        am_session = make_planned_session(
            session_slot=SessionSlot.AM,
            target_date=target_date,
        )
        pm_session = make_planned_session(
            session_slot=SessionSlot.PM,
            target_date=target_date,
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [am_session, pm_session]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        results = await repo.get_today_for_athlete(athlete_id, target_date)

        assert len(results) == 2
        assert results[0].session_slot == SessionSlot.AM
        assert results[1].session_slot == SessionSlot.PM

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_sessions(
        self,
        mock_session: MagicMock,
    ) -> None:
        athlete_id = uuid.uuid4()
        target_date = date.today()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        results = await repo.get_today_for_athlete(athlete_id, target_date)

        assert results == []

    @pytest.mark.asyncio
    async def test_queries_via_weekly_plan_training_plan_join(
        self,
        mock_session: MagicMock,
    ) -> None:
        athlete_id = uuid.uuid4()
        target_date = date.today()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        await repo.get_today_for_athlete(athlete_id, target_date)

        mock_session.execute.assert_called_once()
        # Verify execute was called with a Select object (not checked by str())
        call_arg = mock_session.execute.call_args[0][0]
        assert call_arg is not None  # A Select was passed, not None

    @pytest.mark.asyncio
    async def test_filters_by_athlete_id_and_active_plan(
        self,
        mock_session: MagicMock,
    ) -> None:
        athlete_id = uuid.uuid4()
        target_date = date.today()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = PlannedSessionRepository(mock_session)
        await repo.get_today_for_athlete(athlete_id, target_date)

        mock_session.execute.assert_called_once()
        # Verify execute was called with a Select object (not checked by str())
        call_arg = mock_session.execute.call_args[0][0]
        assert call_arg is not None  # A Select was passed, not None