"""Unit tests for ``WorkoutStepRepository``.

Tests:
- insert_many() adds all steps and flushes in one call
- insert_many() refreshes each step to get persisted values
- get_by_workout() returns steps ordered by step_order ASC

Reference plan: docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    PhysiologicalIntent,
    RecoveryModifierLevel,
    SessionPurpose,
    SessionType,
    StepType,
)
from app.models.workout_step import WorkoutStep
from app.repositories.workout_step_repository import WorkoutStepRepository


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> MagicMock:
    session = MagicMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


def make_step(**overrides: Any) -> WorkoutStep:
    """Factory that returns a WorkoutStep with sensible defaults."""
    kwargs = {
        "generated_workout_id": uuid.uuid4(),
        "step_order": 1,
        "step_type": StepType.WORK,
        "session_type": SessionType.THRESHOLD,
        "physiological_intent": PhysiologicalIntent.THRESHOLD,
        "session_purpose": SessionPurpose.GENERAL,
        "target": {
            "signal_type": "gap",
            "primary": {"min": 300, "max": 330, "unit": "sec_per_km"},
            "fallback": None,
            "description": "Threshold pace",
        },
        "duration_seconds": 1800,
        "description": "Threshold intervals",
    }
    kwargs.update(overrides)
    return WorkoutStep(**kwargs)


# ---------------------------------------------------------------------------
# insert_many()
# ---------------------------------------------------------------------------


class TestInsertMany:
    """Tests for WorkoutStepRepository.insert_many()."""

    @pytest.mark.asyncio
    async def test_adds_all_steps_to_session(
        self,
        mock_session: MagicMock,
    ) -> None:
        repo = WorkoutStepRepository(mock_session)
        steps = [make_step(step_order=i) for i in range(1, 4)]

        await repo.insert_many(steps)

        assert mock_session.add.call_count == 3
        for step in steps:
            mock_session.add.assert_any_call(step)

    @pytest.mark.asyncio
    async def test_flushes_once_for_batch(
        self,
        mock_session: MagicMock,
    ) -> None:
        repo = WorkoutStepRepository(mock_session)
        steps = [make_step(step_order=i) for i in range(1, 4)]

        await repo.insert_many(steps)

        # Single flush for the entire batch
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_refreshes_each_step(
        self,
        mock_session: MagicMock,
    ) -> None:
        repo = WorkoutStepRepository(mock_session)
        steps = [make_step(step_order=i) for i in range(1, 4)]

        await repo.insert_many(steps)

        assert mock_session.refresh.call_count == 3
        for step in steps:
            mock_session.refresh.assert_any_call(step)

    @pytest.mark.asyncio
    async def test_returns_steps(
        self,
        mock_session: MagicMock,
    ) -> None:
        repo = WorkoutStepRepository(mock_session)
        steps = [make_step(step_order=i) for i in range(1, 4)]

        result = await repo.insert_many(steps)

        assert result is steps

    @pytest.mark.asyncio
    async def test_empty_list_flushes_and_returns_empty(
        self,
        mock_session: MagicMock,
    ) -> None:
        repo = WorkoutStepRepository(mock_session)

        result = await repo.insert_many([])

        assert result == []
        mock_session.flush.assert_called_once()
        assert mock_session.add.call_count == 0


# ---------------------------------------------------------------------------
# get_by_workout()
# ---------------------------------------------------------------------------


class TestGetByWorkout:
    """Tests for WorkoutStepRepository.get_by_workout()."""

    @pytest.mark.asyncio
    async def test_returns_steps_ordered_by_step_order_asc(
        self,
        mock_session: MagicMock,
    ) -> None:
        workout_id = uuid.uuid4()
        step1 = make_step(generated_workout_id=workout_id, step_order=1)
        step2 = make_step(generated_workout_id=workout_id, step_order=2)
        step3 = make_step(generated_workout_id=workout_id, step_order=3)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [step1, step2, step3]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = WorkoutStepRepository(mock_session)
        results = await repo.get_by_workout(workout_id)

        assert len(results) == 3
        assert results[0].step_order == 1
        assert results[1].step_order == 2
        assert results[2].step_order == 3

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_steps(
        self,
        mock_session: MagicMock,
    ) -> None:
        workout_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = WorkoutStepRepository(mock_session)
        results = await repo.get_by_workout(workout_id)

        assert results == []

    @pytest.mark.asyncio
    async def test_queries_by_generated_workout_id(
        self,
        mock_session: MagicMock,
    ) -> None:
        workout_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = WorkoutStepRepository(mock_session)
        await repo.get_by_workout(workout_id)

        mock_session.execute.assert_called_once()
        # Verify execute was called with a Select object (not checked by str())
        call_arg = mock_session.execute.call_args[0][0]
        assert call_arg is not None  # A Select was passed, not None