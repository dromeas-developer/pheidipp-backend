"""Integration tests for ``PhysiologyMeasurementRepository`` — real-DB CRUD contract.

The unit tests in ``tests/unit/test_physiology_measurement_repository.py``
exercise the repository surface with ``AsyncMock``-backed sessions, so they
only prove the SQL composition is correct. This integration layer
exercises the *real* database to confirm the contract holds end-to-end:

* ``insert()`` round-trips a row — the persisted columns reflect the
  Python attributes, the id and ``created_at`` are populated by the DB
  defaults, and a fresh read returns the same row.
* ``get_by_athlete()`` returns rows newest-first, respects the
  ``limit`` bound, and only returns rows for the requested athlete.
* ``get_by_athlete_and_parameter()`` filters by both athlete AND
  parameter — observations of a different parameter for the same
  athlete are not returned.
* ``get_recent_for_parameter()`` filters by source AND ``from_date``
  AND ``limit``, in that order; a query before ``from_date`` does not
  match.
* The ``activity_id`` ``ON DELETE SET NULL`` cascade is enforced at
  the DB layer — deleting the parent Activity preserves the historical
  measurement with ``activity_id = NULL``.
* The ``athlete_id`` ``ON DELETE CASCADE`` cascade is enforced at the
  DB layer — deleting the parent Athlete removes the measurement.
* The repository is append-only at the application layer — no
  ``update`` / ``delete`` / ``remove`` / ``upsert`` method exists
  (this is the same property the unit tests cover; the integration
  test pins it at the persistence layer too).

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import (
    ActivitySource,
    MeasurementSource,
    PhysiologyParameter,
    SportType,
)
from app.models.physiology_measurement import PhysiologyMeasurement
from app.repositories.activity_repository import ActivityRepository
from app.repositories.physiology_measurement_repository import (
    PhysiologyMeasurementRepository,
)
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _create_calibration_eligible_running_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    activity_date: date = date(2026, 6, 15),
    has_hr: bool = True,
    has_rr_intervals: bool = False,
    has_power: bool = False,
) -> Activity:
    """Insert a real ``Activity`` row that the integration test can
    attach ``PhysiologyMeasurement`` rows to.

    The activity is created with ``calibration_eligible = True``,
    ``sport_type = RUNNING``, and a populated ``fit_file_key`` because
    those columns are referenced by the threshold detection pipeline
    but are not relevant to repository-level integration tests; they
    just have to satisfy the NOT NULL / FK constraints.
    """
    activity = Activity(
        athlete_id=athlete_id,
        source=ActivitySource.MANUAL_UPLOAD,
        external_id=None,
        activity_date=activity_date,
        start_time=datetime(
            activity_date.year, activity_date.month, activity_date.day,
            8, 0, tzinfo=timezone.utc,
        ),
        duration_seconds=600,
        aerobic_load=85.0,
        has_hr=has_hr,
        has_rr_intervals=has_rr_intervals,
        has_power=has_power,
        has_gps=True,
        sport_type=SportType.RUNNING,
        calibration_eligible=True,
        quality_flags={},
        fit_file_key="fit-files/test/uploaded.fit",
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version="v1-signal-cleaning",
    )
    db_session.add(activity)
    await db_session.flush()
    await db_session.refresh(activity)
    return activity


def _make_measurement(
    *,
    athlete_id: uuid.UUID,
    activity_id: Optional[uuid.UUID] = None,
    parameter: PhysiologyParameter = PhysiologyParameter.LT1_HR,
    observed_value: float = 150.0,
    source: MeasurementSource = MeasurementSource.TRAINING_HR_DEFLECTION,
    measurement_date: date = date(2026, 6, 15),
    algorithm_used: Optional[str] = "hr_deflection_v1",
    confidence_weight: Optional[float] = 0.85,
) -> PhysiologyMeasurement:
    """Build a real ``PhysiologyMeasurement`` instance.

    All NOT NULL columns are populated. The id and ``created_at`` are
    left unset so DB defaults populate them on insert.
    """
    return PhysiologyMeasurement(
        athlete_id=athlete_id,
        activity_id=activity_id,
        parameter=parameter,
        observed_value=observed_value,
        source=source,
        measurement_date=measurement_date,
        algorithm_used=algorithm_used,
        confidence_weight=confidence_weight,
    )


# ---------------------------------------------------------------------------
# Test: insert() round-trips a real row.
# ---------------------------------------------------------------------------


class TestInsertRoundTrip:
    """``insert()`` persists a row that can be re-read with full
    column fidelity."""

    @pytest.mark.asyncio
    async def test_insert_persists_row_with_all_columns(
        self, db_session: AsyncSession
    ) -> None:
        """After insert, a fresh ``SELECT`` returns the same row with
        every populated column matching the inserted value."""
        athlete = await make_athlete(db_session)
        activity = await _create_calibration_eligible_running_activity(
            db_session, athlete_id=athlete.id
        )

        measurement = _make_measurement(
            athlete_id=athlete.id,
            activity_id=activity.id,
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=160.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            algorithm_used="hr_deflection_v1",
            confidence_weight=0.92,
        )
        repo = PhysiologyMeasurementRepository(db_session)
        await repo.insert(measurement)
        await db_session.commit()

        # Fresh session query — uses a new ORM identity, no in-memory
        # state to confuse us.
        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.id == measurement.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]

        assert row.athlete_id == athlete.id
        assert row.activity_id == activity.id
        assert row.parameter == PhysiologyParameter.LT1_HR
        assert row.observed_value == pytest.approx(160.0)
        assert row.source == MeasurementSource.TRAINING_HR_DEFLECTION
        assert row.measurement_date == date(2026, 6, 15)
        assert row.algorithm_used == "hr_deflection_v1"
        assert row.confidence_weight == pytest.approx(0.92)

    @pytest.mark.asyncio
    async def test_insert_populates_id_and_created_at_defaults(
        self, db_session: AsyncSession
    ) -> None:
        """The DB populates ``id`` (UUID default) and ``created_at``
        (server_default ``now()``) — they are NOT NULL after insert
        even though the Python instance was constructed without them."""
        athlete = await make_athlete(db_session)
        measurement = _make_measurement(athlete_id=athlete.id)

        # Sanity check — the Python instance has no id yet.
        assert measurement.id is None
        assert measurement.created_at is None

        repo = PhysiologyMeasurementRepository(db_session)
        await repo.insert(measurement)
        await db_session.commit()

        # After insert, the in-memory instance is refreshed with DB
        # defaults. Both columns are non-null.
        assert measurement.id is not None
        assert isinstance(measurement.id, uuid.UUID)
        assert measurement.created_at is not None
        # ``created_at`` is timezone-aware UTC.
        assert measurement.created_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_insert_persists_nullable_fields_as_null(
        self, db_session: AsyncSession
    ) -> None:
        """An instance constructed without ``activity_id``,
        ``algorithm_used``, or ``confidence_weight`` round-trips with
        those columns NULL — manual / lab-test entries do not have an
        algorithm or a confidence score."""
        athlete = await make_athlete(db_session)
        measurement = _make_measurement(
            athlete_id=athlete.id,
            activity_id=None,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.LAB_TEST,
            algorithm_used=None,
            confidence_weight=None,
        )
        repo = PhysiologyMeasurementRepository(db_session)
        await repo.insert(measurement)
        await db_session.commit()

        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.id == measurement.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        row = rows[0]
        assert row.activity_id is None
        assert row.algorithm_used is None
        assert row.confidence_weight is None
        # source still reflects the lab_test enum string.
        assert row.source == MeasurementSource.LAB_TEST

    @pytest.mark.asyncio
    async def test_insert_is_flush_only_does_not_implicitly_commit(
        self, db_session: AsyncSession
    ) -> None:
        """``insert()`` is documented to call ``flush()`` only — the
        caller owns the transaction boundary. Verifying this at the
        real-DB level proves the contract: a second session cannot
        see the row until the test commits."""
        athlete = await make_athlete(db_session)
        measurement = _make_measurement(athlete_id=athlete.id)
        repo = PhysiologyMeasurementRepository(db_session)
        await repo.insert(measurement)

        # No commit yet — a SELECT from a fresh session would not see
        # the row. The test does not assert that directly (would need
        # a second connection), but it documents the contract and
        # confirms ``insert()`` did not raise on rollback path.
        await db_session.rollback()

        # After rollback, the measurement id was never committed. A
        # SELECT confirms the row is absent.
        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert rows == []


# ---------------------------------------------------------------------------
# Test: get_by_athlete() — newest first + limit + athlete scoping.
# ---------------------------------------------------------------------------


class TestGetByAthlete:
    """``get_by_athlete()`` returns rows newest first and respects the
    ``limit`` and athlete-scoping filters."""

    @pytest.mark.asyncio
    async def test_get_by_athlete_returns_rows_newest_first(
        self, db_session: AsyncSession
    ) -> None:
        """Rows are ordered by ``measurement_date`` descending — the
        newest observation comes first regardless of insert order."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        # Insert in non-chronological order to prove the query
        # produces the right order, not the insert order.
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            measurement_date=date(2026, 6, 10),
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            measurement_date=date(2026, 6, 18),
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            measurement_date=date(2026, 6, 14),
        ))
        await db_session.commit()

        result = await repo.get_by_athlete(athlete.id, limit=10)
        assert len(result) == 3
        # Newest first: 6-18, 6-14, 6-10.
        assert result[0].measurement_date == date(2026, 6, 18)
        assert result[1].measurement_date == date(2026, 6, 14)
        assert result[2].measurement_date == date(2026, 6, 10)

    @pytest.mark.asyncio
    async def test_get_by_athlete_respects_limit(
        self, db_session: AsyncSession
    ) -> None:
        """The ``limit`` parameter caps the result size — even when
        more rows exist for the athlete."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        for i in range(5):
            await repo.insert(_make_measurement(
                athlete_id=athlete.id,
                parameter=PhysiologyParameter.LT1_HR,
                measurement_date=date(2026, 6, 1 + i),
            ))
        await db_session.commit()

        result = await repo.get_by_athlete(athlete.id, limit=2)
        assert len(result) == 2
        # Limit returns the two newest.
        assert result[0].measurement_date == date(2026, 6, 5)
        assert result[1].measurement_date == date(2026, 6, 4)

    @pytest.mark.asyncio
    async def test_get_by_athlete_filters_by_athlete_id(
        self, db_session: AsyncSession
    ) -> None:
        """The query is scoped to the requested ``athlete_id`` —
        rows for a different athlete are not returned."""
        athlete_a = await make_athlete(db_session)
        athlete_b = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        await repo.insert(_make_measurement(
            athlete_id=athlete_a.id, parameter=PhysiologyParameter.LT1_HR
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete_b.id, parameter=PhysiologyParameter.LT1_HR
        ))
        await db_session.commit()

        result_a = await repo.get_by_athlete(athlete_a.id, limit=10)
        result_b = await repo.get_by_athlete(athlete_b.id, limit=10)
        assert len(result_a) == 1
        assert len(result_b) == 1
        assert result_a[0].athlete_id == athlete_a.id
        assert result_b[0].athlete_id == athlete_b.id

    @pytest.mark.asyncio
    async def test_get_by_athlete_returns_empty_when_no_rows(
        self, db_session: AsyncSession
    ) -> None:
        """A query for an athlete with no measurements returns ``[]``,
        not ``None`` — the empty list is the documented contract."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        result = await repo.get_by_athlete(athlete.id, limit=10)
        assert result == []


# ---------------------------------------------------------------------------
# Test: get_by_athlete_and_parameter() — parameter scoping.
# ---------------------------------------------------------------------------


class TestGetByAthleteAndParameter:
    """``get_by_athlete_and_parameter()`` filters by both athlete AND
    parameter, with newest-first ordering and limit."""

    @pytest.mark.asyncio
    async def test_filters_by_parameter_only_returns_matching_rows(
        self, db_session: AsyncSession
    ) -> None:
        """The query excludes rows with a different parameter — only
        the requested parameter is returned."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            measurement_date=date(2026, 6, 15),
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT2_HR,
            measurement_date=date(2026, 6, 16),
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.CP,
            measurement_date=date(2026, 6, 17),
        ))
        await db_session.commit()

        result = await repo.get_by_athlete_and_parameter(
            athlete.id, PhysiologyParameter.LT1_HR, limit=10
        )
        assert len(result) == 1
        assert result[0].parameter == PhysiologyParameter.LT1_HR
        assert result[0].measurement_date == date(2026, 6, 15)

    @pytest.mark.asyncio
    async def test_filters_by_athlete_id_too(
        self, db_session: AsyncSession
    ) -> None:
        """The query is scoped to the requested athlete — a different
        athlete with the same parameter is not returned."""
        athlete_a = await make_athlete(db_session)
        athlete_b = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        await repo.insert(_make_measurement(
            athlete_id=athlete_a.id,
            parameter=PhysiologyParameter.LT1_HR,
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete_b.id,
            parameter=PhysiologyParameter.LT1_HR,
        ))
        await db_session.commit()

        result = await repo.get_by_athlete_and_parameter(
            athlete_a.id, PhysiologyParameter.LT1_HR, limit=10
        )
        assert len(result) == 1
        assert result[0].athlete_id == athlete_a.id

    @pytest.mark.asyncio
    async def test_orders_by_measurement_date_desc_and_respects_limit(
        self, db_session: AsyncSession
    ) -> None:
        """The query orders by ``measurement_date`` descending and
        applies the ``limit`` bound."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        for i in range(4):
            await repo.insert(_make_measurement(
                athlete_id=athlete.id,
                parameter=PhysiologyParameter.LT1_HR,
                measurement_date=date(2026, 6, 1 + i * 5),
            ))
        await db_session.commit()

        result = await repo.get_by_athlete_and_parameter(
            athlete.id, PhysiologyParameter.LT1_HR, limit=2
        )
        assert len(result) == 2
        # Newest two first.
        assert result[0].measurement_date == date(2026, 6, 16)
        assert result[1].measurement_date == date(2026, 6, 11)


# ---------------------------------------------------------------------------
# Test: get_recent_for_parameter() — source + from_date + limit.
# ---------------------------------------------------------------------------


class TestGetRecentForParameter:
    """``get_recent_for_parameter()`` filters by source AND
    ``from_date`` AND ``limit``, in that order."""

    @pytest.mark.asyncio
    async def test_filters_by_source(
        self, db_session: AsyncSession
    ) -> None:
        """The query excludes observations of the same parameter with
        a different source."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            measurement_date=date(2026, 6, 15),
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_RR_INFLECTION,
            measurement_date=date(2026, 6, 15),
        ))
        await db_session.commit()

        result = await repo.get_recent_for_parameter(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 1, 1),
            limit=10,
        )
        assert len(result) == 1
        assert result[0].source == MeasurementSource.TRAINING_HR_DEFLECTION

    @pytest.mark.asyncio
    async def test_filters_by_from_date_excludes_earlier_rows(
        self, db_session: AsyncSession
    ) -> None:
        """Observations with ``measurement_date < from_date`` are
        excluded — the date filter is applied at the SQL layer
        (translated to ``>= from_date``)."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            measurement_date=date(2026, 1, 15),  # before from_date
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            measurement_date=date(2026, 6, 15),  # on/after from_date
        ))
        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            measurement_date=date(2026, 7, 1),  # after from_date
        ))
        await db_session.commit()

        result = await repo.get_recent_for_parameter(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 6, 1),
            limit=10,
        )
        # The January observation is excluded by the from_date filter.
        assert len(result) == 2
        dates = {r.measurement_date for r in result}
        assert dates == {date(2026, 6, 15), date(2026, 7, 1)}

    @pytest.mark.asyncio
    async def test_respects_limit(
        self, db_session: AsyncSession
    ) -> None:
        """The ``limit`` parameter caps the result size even when
        more matching rows exist in the window."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        for i in range(5):
            await repo.insert(_make_measurement(
                athlete_id=athlete.id,
                parameter=PhysiologyParameter.LT1_HR,
                source=MeasurementSource.TRAINING_HR_DEFLECTION,
                measurement_date=date(2026, 6, 1 + i),
            ))
        await db_session.commit()

        result = await repo.get_recent_for_parameter(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 1, 1),
            limit=3,
        )
        assert len(result) == 3
        # Newest three first.
        assert result[0].measurement_date == date(2026, 6, 5)
        assert result[1].measurement_date == date(2026, 6, 4)
        assert result[2].measurement_date == date(2026, 6, 3)

    @pytest.mark.asyncio
    async def test_from_date_inclusive(
        self, db_session: AsyncSession
    ) -> None:
        """``from_date`` is inclusive — an observation on exactly
        ``from_date`` is included in the result."""
        athlete = await make_athlete(db_session)
        repo = PhysiologyMeasurementRepository(db_session)

        await repo.insert(_make_measurement(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            measurement_date=date(2026, 6, 1),
        ))
        await db_session.commit()

        result = await repo.get_recent_for_parameter(
            athlete_id=athlete.id,
            parameter=PhysiologyParameter.LT1_HR,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            from_date=date(2026, 6, 1),  # exactly the row's date
            limit=10,
        )
        assert len(result) == 1
        assert result[0].measurement_date == date(2026, 6, 1)


# ---------------------------------------------------------------------------
# Test: ON DELETE SET NULL on activity_id.
# ---------------------------------------------------------------------------


class TestActivityIdOnDeleteSetNull:
    """The ``activity_id`` foreign key is declared ``ON DELETE SET
    NULL``. Deleting the parent ``Activity`` row preserves the
    historical ``PhysiologyMeasurement`` with ``activity_id`` set to
    NULL — the observation is a record of a physiological state, not
    a property of the activity, and must survive the activity being
    removed."""

    @pytest.mark.asyncio
    async def test_deleting_activity_nullifies_measurement_activity_id(
        self, db_session: AsyncSession
    ) -> None:
        """After deleting the parent ``Activity`` row, the
        ``PhysiologyMeasurement`` survives with ``activity_id = NULL``.

        The ON DELETE SET NULL cascade is enforced at the DB layer
        (see migration ``8413e6547a40`` — the FK is declared
        ``ondelete='SET NULL'``). The test pins that contract at the
        real-DB boundary.
        """
        athlete = await make_athlete(db_session)
        activity = await _create_calibration_eligible_running_activity(
            db_session, athlete_id=athlete.id
        )
        measurement = _make_measurement(
            athlete_id=athlete.id,
            activity_id=activity.id,
            parameter=PhysiologyParameter.LT1_HR,
        )
        repo = PhysiologyMeasurementRepository(db_session)
        await repo.insert(measurement)
        await db_session.commit()

        # Delete the parent activity. The CASCADE / SET NULL
        # semantics are evaluated by the DB; we delete via the
        # ActivityRepository to exercise the same path production
        # code would use.
        activity_repo = ActivityRepository(db_session)
        fetched = await activity_repo.get_by_id(activity.id)
        assert fetched is not None
        await db_session.delete(fetched)
        await db_session.commit()

        # CRITICAL: capture the scalar id BEFORE expire_all(). After
        # expire_all(), the ``measurement`` instance is expired and
        # accessing ``measurement.id`` would trigger an async lazy
        # load outside the greenlet context (MissingGreenlet under
        # async SQLAlchemy + NullPool). The id is already populated
        # by the DB default after the first commit, so capturing it
        # here is safe and avoids the lazy load entirely.
        # See tests/README.md "expire_all() + async lazy load on
        # captured scalar" — capture scalars first, then expire,
        # then SELECT.
        measurement_id = measurement.id
        assert measurement_id is not None

        # Expire so the post-cascade SELECT reloads fresh instances
        # from the DB. Without this, the identity map serves the
        # stale ``PhysiologyMeasurement`` instance with the
        # pre-delete ``activity_id``, and the assertion
        # ``activity_id is None`` would fail even though the DB
        # correctly NULLed the column.
        db_session.expire_all()

        # The measurement still exists. Its activity_id is now NULL.
        # ``populate_existing=True`` forces SQLAlchemy to bypass the
        # identity map and rebuild the instance from the result row
        # — without it, the identity map returns the expired
        # ``measurement`` instance (whose ``athlete_id`` was loaded
        # before the cascade), and accessing ``surviving.athlete_id``
        # triggers an async lazy load outside the greenlet context
        # (MissingGreenlet under async SQLAlchemy + NullPool).
        # See tests/README.md "expire_all() + populate_existing on
        # post-cascade SELECT" — the capture-first pattern alone is
        # not sufficient when the SELECT returns the same row that
        # was just expired; ``populate_existing=True`` is the
        # belt-and-braces fix.
        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement)
                .where(PhysiologyMeasurement.id == measurement_id)
                .execution_options(populate_existing=True)
            )
        ).scalars().all()
        assert len(rows) == 1
        surviving = rows[0]
        assert surviving.id == measurement_id
        assert surviving.athlete_id == athlete.id
        assert surviving.activity_id is None
        # Other columns are unaffected.
        assert surviving.parameter == PhysiologyParameter.LT1_HR
        assert surviving.observed_value == pytest.approx(150.0)
        assert surviving.source == MeasurementSource.TRAINING_HR_DEFLECTION


# ---------------------------------------------------------------------------
# Test: ON DELETE CASCADE on athlete_id.
# ---------------------------------------------------------------------------


class TestAthleteIdOnDeleteCascade:
    """The ``athlete_id`` foreign key is declared ``ON DELETE CASCADE``.
    Deleting the parent ``Athlete`` row removes the measurement —
    the observation has no meaning without the athlete it describes."""

    @pytest.mark.asyncio
    async def test_deleting_athlete_removes_measurement(
        self, db_session: AsyncSession
    ) -> None:
        """After deleting the parent ``Athlete`` row, the
        ``PhysiologyMeasurement`` is removed by the cascade."""
        athlete = await make_athlete(db_session)
        measurement = _make_measurement(athlete_id=athlete.id)
        repo = PhysiologyMeasurementRepository(db_session)
        await repo.insert(measurement)
        await db_session.commit()

        # Sanity: the row exists.
        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1

        # Delete the parent athlete. CASCADE removes the measurement.
        await db_session.delete(athlete)
        await db_session.commit()

        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert rows == []


# ---------------------------------------------------------------------------
# Test: append-only at the application layer (property pinned at the
# persistence boundary too).
# ---------------------------------------------------------------------------


class TestRepositoryAppendOnlySurface:
    """The repository exposes only insert and read methods. No
    ``update`` / ``delete`` / ``remove`` / ``upsert`` method exists.
    The unit tests already pin this on the class object; the
    integration layer re-pins it because callers could in principle
    reach in and call a hypothetical update path via a different
    surface — this test is the structural guarantee that no such
    method exists on the production repository class as it stands."""

    def test_repository_has_no_update_method(self) -> None:
        mock_session = type("S", (), {})()  # noqa: F841 — placeholder
        repo = PhysiologyMeasurementRepository.__init__  # noqa: F841
        # The class does not define a method called ``update``.
        assert not hasattr(PhysiologyMeasurementRepository, "update")
        # Sanity: the documented methods ARE present.
        assert hasattr(PhysiologyMeasurementRepository, "insert")
        assert hasattr(PhysiologyMeasurementRepository, "get_by_athlete")
        assert hasattr(
            PhysiologyMeasurementRepository, "get_by_athlete_and_parameter"
        )
        assert hasattr(
            PhysiologyMeasurementRepository, "get_recent_for_parameter"
        )

    def test_repository_has_no_delete_method(self) -> None:
        assert not hasattr(PhysiologyMeasurementRepository, "delete")

    def test_repository_has_no_remove_method(self) -> None:
        assert not hasattr(PhysiologyMeasurementRepository, "remove")

    def test_repository_has_no_upsert_method(self) -> None:
        assert not hasattr(PhysiologyMeasurementRepository, "upsert")
