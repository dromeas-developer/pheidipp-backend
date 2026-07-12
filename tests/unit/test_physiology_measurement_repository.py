"""Unit tests for ``PhysiologyMeasurementRepository``.

Phase-2.3-P1 introduces the ``PhysiologyMeasurementRepository`` —
read and write operations for the ``physiology_measurements`` table.

The table is append-only: this repository exposes only ``insert`` and
read methods, no UPDATE or DELETE. Corrections are made by inserting
a new observation with a higher ``confidence_weight`` or a more
authoritative ``source``.

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import MeasurementSource, PhysiologyParameter
from app.models.physiology_measurement import PhysiologyMeasurement
from app.repositories.physiology_measurement_repository import (
    PhysiologyMeasurementRepository,
)


def _make_measurement(
    *,
    athlete_id: uuid.UUID | None = None,
    activity_id: uuid.UUID | None = None,
    parameter: PhysiologyParameter = PhysiologyParameter.LT1_HR,
    observed_value: float = 150.0,
    source: MeasurementSource = MeasurementSource.TRAINING_HR_DEFLECTION,
    measurement_date: date | None = None,
    algorithm_used: str | None = "hr_deflection_v1",
    confidence_weight: float | None = 0.85,
) -> MagicMock:
    """Build a mock PhysiologyMeasurement with the specified attributes."""
    mock = MagicMock(spec=PhysiologyMeasurement)
    mock.id = uuid.uuid4()
    mock.athlete_id = athlete_id or uuid.uuid4()
    mock.activity_id = activity_id
    mock.parameter = parameter
    mock.observed_value = observed_value
    mock.source = source
    mock.measurement_date = measurement_date or date(2026, 6, 15)
    mock.algorithm_used = algorithm_used
    mock.confidence_weight = confidence_weight
    return mock


# ---------------------------------------------------------------------------
# Test: insert() flushes without committing.
# ---------------------------------------------------------------------------


class TestInsert:
    """``insert()`` adds the measurement to the session and flushes,
    but does NOT commit. The caller is responsible for committing."""

    @pytest.mark.asyncio
    async def test_insert_adds_to_session(self) -> None:
        """The measurement is added to the session via ``session.add``."""
        mock_session = AsyncMock()
        measurement = _make_measurement()
        repo = PhysiologyMeasurementRepository(mock_session)

        await repo.insert(measurement)

        mock_session.add.assert_called_once_with(measurement)

    @pytest.mark.asyncio
    async def test_insert_flushes_session(self) -> None:
        """The session is flushed after the measurement is added."""
        mock_session = AsyncMock()
        measurement = _make_measurement()
        repo = PhysiologyMeasurementRepository(mock_session)

        await repo.insert(measurement)

        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_refreshes_measurement(self) -> None:
        """The measurement is refreshed after flush so server-side
        defaults (e.g. ``created_at``) are populated."""
        mock_session = AsyncMock()
        measurement = _make_measurement()
        repo = PhysiologyMeasurementRepository(mock_session)

        await repo.insert(measurement)

        mock_session.refresh.assert_called_once_with(measurement)

    @pytest.mark.asyncio
    async def test_insert_does_not_commit(self) -> None:
        """``insert()`` does NOT call ``session.commit()`` — the
        caller owns the transaction boundary."""
        mock_session = AsyncMock()
        measurement = _make_measurement()
        repo = PhysiologyMeasurementRepository(mock_session)

        await repo.insert(measurement)

        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_insert_returns_measurement(self) -> None:
        """``insert()`` returns the measurement (post-refresh)."""
        mock_session = AsyncMock()
        measurement = _make_measurement()
        repo = PhysiologyMeasurementRepository(mock_session)

        result = await repo.insert(measurement)

        assert result is measurement


# ---------------------------------------------------------------------------
# Test: get_by_athlete() returns newest first.
# ---------------------------------------------------------------------------


class TestGetByAthlete:
    """``get_by_athlete()`` returns the most recent measurements for
    an athlete, ordered by ``measurement_date`` descending."""

    @pytest.mark.asyncio
    async def test_get_by_athlete_returns_scalars(self) -> None:
        """The repository unwraps the SQLAlchemy result and returns a
        list of PhysiologyMeasurement instances."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        m1 = _make_measurement(athlete_id=athlete_id)
        m2 = _make_measurement(athlete_id=athlete_id)

        # Build a mock result that supports .scalars().all()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [m1, m2]
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        result = await repo.get_by_athlete(athlete_id, limit=10)

        assert result == [m1, m2]

    @pytest.mark.asyncio
    async def test_get_by_athlete_filters_by_athlete_id(self) -> None:
        """The query filters by ``athlete_id``.

        The SQL compilation is performed with
        ``literal_binds=True`` so we can inspect the rendered WHERE
        clause. PostgreSQL's UUID bind processor renders the literal
        in its native 32-char hex form (no dashes); the dashed form
        is a Python ``str(uuid)`` artefact. The assertion below
        accepts both forms so the test is robust to whichever path
        SQLAlchemy chooses — the only thing being verified is that
        *this specific athlete's* UUID is the one bound, not some
        placeholder.
        """
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        await repo.get_by_athlete(athlete_id, limit=10)

        # Verify the execute call was made with a select statement
        # that filters by athlete_id.
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        stmt = call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # Accept either the dashed (Python str()) or undashed (PG
        # native) UUID representation in the compiled SQL.
        dashed = str(athlete_id)  # e.g. "c4834b53-01e8-..."
        undashed = athlete_id.hex  # e.g. "c4834b5301e84960..."
        assert dashed in compiled or undashed in compiled, (
            f"expected athlete_id ({dashed} or {undashed}) in compiled "
            f"SQL but got: {compiled!r}"
        )

    @pytest.mark.asyncio
    async def test_get_by_athlete_orders_by_measurement_date_desc(self) -> None:
        """The query orders by ``measurement_date`` descending so the
        newest measurements come first."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        await repo.get_by_athlete(athlete_id, limit=10)

        call_args = mock_session.execute.call_args
        stmt = call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # ORDER BY measurement_date DESC
        assert "ORDER BY" in compiled.upper()
        assert "DESC" in compiled.upper()
        assert "measurement_date" in compiled

    @pytest.mark.asyncio
    async def test_get_by_athlete_applies_limit(self) -> None:
        """The query applies the ``limit`` parameter."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        await repo.get_by_athlete(athlete_id, limit=5)

        call_args = mock_session.execute.call_args
        stmt = call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 5" in compiled.upper()


# ---------------------------------------------------------------------------
# Test: get_by_athlete_and_parameter() filters by parameter.
# ---------------------------------------------------------------------------


class TestGetByAthleteAndParameter:
    """``get_by_athlete_and_parameter()`` returns the most recent
    measurements for one parameter, ordered by ``measurement_date``
    descending."""

    @pytest.mark.asyncio
    async def test_get_by_athlete_and_parameter_filters_by_parameter(
        self,
    ) -> None:
        """The query filters by both ``athlete_id`` and ``parameter``.

        ``athlete_id`` may render in either dashed (Python ``str(uuid)``)
        or undashed (PostgreSQL native hex) form depending on
        SQLAlchemy's bind-processor choice. The assertion accepts
        both — see ``test_get_by_athlete_filters_by_athlete_id`` for
        the rationale.
        """
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        await repo.get_by_athlete_and_parameter(
            athlete_id, PhysiologyParameter.LT1_HR, limit=10
        )

        call_args = mock_session.execute.call_args
        stmt = call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # Accept either dashed or undashed UUID rendering.
        dashed = str(athlete_id)
        undashed = athlete_id.hex
        assert dashed in compiled or undashed in compiled
        assert "lt1_hr" in compiled

    @pytest.mark.asyncio
    async def test_get_by_athlete_and_parameter_returns_scalars(self) -> None:
        """The repository unwraps the SQLAlchemy result and returns a
        list of PhysiologyMeasurement instances."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        m1 = _make_measurement(
            athlete_id=athlete_id, parameter=PhysiologyParameter.LT1_HR
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [m1]
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        result = await repo.get_by_athlete_and_parameter(
            athlete_id, PhysiologyParameter.LT1_HR, limit=10
        )

        assert result == [m1]


# ---------------------------------------------------------------------------
# Test: get_recent_for_parameter() filters by source and from_date.
# ---------------------------------------------------------------------------


class TestGetRecentForParameter:
    """``get_recent_for_parameter()`` returns recent measurements for
    one (parameter, source) pair, filtered by ``from_date``."""

    @pytest.mark.asyncio
    async def test_get_recent_for_parameter_filters_by_source(self) -> None:
        """The query filters by ``source``."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        await repo.get_recent_for_parameter(
            athlete_id,
            PhysiologyParameter.LT1_HR,
            MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 1, 1),
            limit=10,
        )

        call_args = mock_session.execute.call_args
        stmt = call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "training_hr_deflection" in compiled

    @pytest.mark.asyncio
    async def test_get_recent_for_parameter_filters_by_from_date(
        self,
    ) -> None:
        """The query filters by ``measurement_date >= from_date``."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        await repo.get_recent_for_parameter(
            athlete_id,
            PhysiologyParameter.LT1_HR,
            MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 1, 1),
            limit=10,
        )

        call_args = mock_session.execute.call_args
        stmt = call_args.args[0]
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        # The from_date filter is present in the WHERE clause.
        assert "2026-01-01" in compiled

    @pytest.mark.asyncio
    async def test_get_recent_for_parameter_returns_scalars(self) -> None:
        """The repository unwraps the SQLAlchemy result and returns a
        list of PhysiologyMeasurement instances."""
        mock_session = AsyncMock()
        athlete_id = uuid.uuid4()
        m1 = _make_measurement(athlete_id=athlete_id)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [m1]
        mock_session.execute.return_value = mock_result

        repo = PhysiologyMeasurementRepository(mock_session)
        result = await repo.get_recent_for_parameter(
            athlete_id,
            PhysiologyParameter.LT1_HR,
            MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 1, 1),
            limit=10,
        )

        assert result == [m1]


# ---------------------------------------------------------------------------
# Test: no update/delete methods exist on the repository.
# ---------------------------------------------------------------------------


class TestNoUpdateOrDeleteMethods:
    """The repository is append-only — no UPDATE or DELETE methods
    exist. Corrections are made by inserting a new observation."""

    def test_repository_has_no_update_method(self) -> None:
        """No ``update`` method exists on the repository."""
        mock_session = AsyncMock()
        repo = PhysiologyMeasurementRepository(mock_session)
        assert not hasattr(repo, "update")

    def test_repository_has_no_delete_method(self) -> None:
        """No ``delete`` method exists on the repository."""
        mock_session = AsyncMock()
        repo = PhysiologyMeasurementRepository(mock_session)
        assert not hasattr(repo, "delete")

    def test_repository_has_no_remove_method(self) -> None:
        """No ``remove`` method exists on the repository."""
        mock_session = AsyncMock()
        repo = PhysiologyMeasurementRepository(mock_session)
        assert not hasattr(repo, "remove")

    def test_repository_has_no_upsert_method(self) -> None:
        """No ``upsert`` method exists — the table is append-only."""
        mock_session = AsyncMock()
        repo = PhysiologyMeasurementRepository(mock_session)
        assert not hasattr(repo, "upsert")
