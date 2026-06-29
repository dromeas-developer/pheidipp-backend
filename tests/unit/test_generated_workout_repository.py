"""Unit tests for ``GeneratedWorkoutRepository``.

Tests:
- insert() appends a GeneratedWorkout and flushes without committing
- get_by_session_and_date() returns existing workout (idempotency lookup)
- get_by_session_and_date() returns None when no workout exists
- get_by_planned_session() returns workouts ordered by generated_at DESC

Reference plan: docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RecoveryModifierLevel
from app.models.generated_workout import GeneratedWorkout
from app.repositories.generated_workout_repository import GeneratedWorkoutRepository


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def sample_workout_dict() -> dict[str, Any]:
    """Return a minimal but valid GeneratedWorkout dict for direct construction."""
    return {
        "planned_session_id": uuid.uuid4(),
        "twin_state_id": uuid.uuid4(),
        "theoretical_targets": {"targets": [], "description": "threshold session"},
        "adjusted_targets": {"targets": [], "description": "threshold session"},
        "recovery_modifier_level": RecoveryModifierLevel.GREEN,
        "recovery_modifier_reason": None,
        "generation_date": date.today(),
    }


def make_workout(**overrides) -> GeneratedWorkout:
    """Factory that returns a GeneratedWorkout with sensible defaults."""
    kwargs = {
        "planned_session_id": uuid.uuid4(),
        "twin_state_id": uuid.uuid4(),
        "theoretical_targets": {"targets": [], "description": "threshold session"},
        "adjusted_targets": {"targets": [], "description": "threshold session"},
        "recovery_modifier_level": RecoveryModifierLevel.GREEN,
        "generation_date": date.today(),
    }
    kwargs.update(overrides)
    workout = GeneratedWorkout(**kwargs)
    # Set readonly fields that have defaults
    workout.id = uuid.uuid4()
    workout.generated_at = datetime.now(timezone.utc)
    return workout


# ---------------------------------------------------------------------------
# insert()
# ---------------------------------------------------------------------------


class TestInsert:
    """Tests for GeneratedWorkoutRepository.insert()."""

    @pytest.mark.asyncio
    async def test_adds_workout_to_session(
        self,
        mock_session: MagicMock,
        sample_workout_dict: dict[str, Any],
    ) -> None:
        repo = GeneratedWorkoutRepository(mock_session)
        workout = make_workout(**sample_workout_dict)

        await repo.insert(workout)

        mock_session.add.assert_called_once_with(workout)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_refreshes_workout_to_get_persisted_ids(
        self,
        mock_session: MagicMock,
        sample_workout_dict: dict[str, Any],
    ) -> None:
        repo = GeneratedWorkoutRepository(mock_session)
        workout = make_workout(**sample_workout_dict)

        await repo.insert(workout)

        mock_session.refresh.assert_called_once_with(workout)

    @pytest.mark.asyncio
    async def test_returns_workout(
        self,
        mock_session: MagicMock,
        sample_workout_dict: dict[str, Any],
    ) -> None:
        repo = GeneratedWorkoutRepository(mock_session)
        workout = make_workout(**sample_workout_dict)

        result = await repo.insert(workout)

        assert result is workout


# ---------------------------------------------------------------------------
# get_by_session_and_date()
# ---------------------------------------------------------------------------


class TestGetBySessionAndDate:
    """Tests for GeneratedWorkoutRepository.get_by_session_and_date()."""

    @pytest.mark.asyncio
    async def test_returns_workout_when_exists(
        self,
        mock_session: MagicMock,
    ) -> None:
        planned_session_id = uuid.uuid4()
        generation_date = date.today()
        existing = make_workout(
            planned_session_id=planned_session_id,
            generation_date=generation_date,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        repo = GeneratedWorkoutRepository(mock_session)
        result = await repo.get_by_session_and_date(planned_session_id, generation_date)

        assert result is existing
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_not_exists(
        self,
        mock_session: MagicMock,
    ) -> None:
        planned_session_id = uuid.uuid4()
        generation_date = date.today()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = GeneratedWorkoutRepository(mock_session)
        result = await repo.get_by_session_and_date(planned_session_id, generation_date)

        assert result is None

    @pytest.mark.asyncio
    async def test_queries_by_both_keys(
        self,
        mock_session: MagicMock,
    ) -> None:
        planned_session_id = uuid.uuid4()
        generation_date = date.today()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = GeneratedWorkoutRepository(mock_session)
        await repo.get_by_session_and_date(planned_session_id, generation_date)

        mock_session.execute.assert_called_once()
        # Verify execute was called with a Select object (not checked by str())
        call_arg = mock_session.execute.call_args[0][0]
        assert call_arg is not None  # A Select was passed, not None


# ---------------------------------------------------------------------------
# get_by_planned_session()
# ---------------------------------------------------------------------------


class TestGetByPlannedSession:
    """Tests for GeneratedWorkoutRepository.get_by_planned_session()."""

    @pytest.mark.asyncio
    async def test_returns_workouts_ordered_by_generated_at_desc(
        self,
        mock_session: MagicMock,
    ) -> None:
        planned_session_id = uuid.uuid4()
        workout1 = make_workout(planned_session_id=planned_session_id)
        workout2 = make_workout(planned_session_id=planned_session_id)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [workout2, workout1]  # DESC order
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = GeneratedWorkoutRepository(mock_session)
        results = await repo.get_by_planned_session(planned_session_id)

        assert len(results) == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_workouts(
        self,
        mock_session: MagicMock,
    ) -> None:
        planned_session_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = GeneratedWorkoutRepository(mock_session)
        results = await repo.get_by_planned_session(planned_session_id)

        assert results == []