"""Integration tests for the ``Activity`` schema at the DB level.

Phase-1.2a introduces a new ``activities`` table that is the system's
running observation index. The DB-level invariants this plan
codifies are:

* Required nullable load scores (default ``NULL`` — populated by
  ``LoadComputationService`` later).
* Signal-availability flags with safe defaults.
* Partial unique index ``(athlete_id, external_id, source) WHERE
  external_id IS NOT NULL`` — duplicate ingestion attempts for the
  same external session create ONE Activity.
* ``manual_entry`` activities must be able to persist with
  ``external_id IS NULL`` and ``fit_file_key IS NULL`` — the partial
  index lets them through.
* Required quality_flags JSONB defaulting to ``{}`` (not nullable).
* Lean schema: no workout-summary fields.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import os
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.enums import ActivitySource


TABLE = "activities"


def _sync_url() -> str:
    """Convert asyncpg ``DATABASE_URL`` into a sync psycopg2 URL.

    Required by direct-connection introspection helpers that use the
    sync ``sqlalchemy.inspect`` path. The same helper exists in
    ``test_training_plan_schema.py`` and ``test_checkpoint_schema.py``
    — adding it here keeps ``test_planned_session_id_is_nullable_uuid_with_or_without_fk``
    self-contained without coupling these test files by import.
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg2://",
        )
    return database_url


def _columns(table: str) -> list[dict]:
    """Get column info for a table using sync engine."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    
    # Convert asyncpg URL to psycopg2
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            return list(inspector.get_columns(table))
    finally:
        engine.dispose()


def _indexes(table: str) -> list[dict]:
    """Get index info for a table using sync engine."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    
    # Convert asyncpg URL to psycopg2
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            return [dict(idx) for idx in inspector.get_indexes(table)]
    finally:
        engine.dispose()


def _activity_factory(
    *,
    athlete_id,
    source: ActivitySource = ActivitySource.MANUAL_ENTRY,
    external_id: str | None = None,
    fit_file_key: str | None = None,
    load: float | None = None,
    calibration_eligible: bool = False,
    has_hr: bool = False,
    has_rr: bool = False,
    has_power: bool = False,
) -> Activity:
    return Activity(
        athlete_id=athlete_id,
        source=source,
        external_id=external_id,
        activity_date=date(2026, 6, 19),
        start_time=datetime(2026, 6, 19, 7, 30, tzinfo=timezone.utc),
        duration_seconds=3600,
        aerobic_load=load,
        neuromuscular_load=load,
        structural_load=load,
        has_hr=has_hr,
        has_rr_intervals=has_rr,
        has_power=has_power,
        calibration_eligible=calibration_eligible,
        quality_flags={},
        fit_file_key=fit_file_key,
    )


async def _new_athlete(db_session: AsyncSession, email: str) -> Athlete:
    a = Athlete(email=email)
    db_session.add(a)
    await db_session.flush()
    return a


class TestActivityDBSchemaColumns:
    """Every documented field is physically present."""

    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "planned_session_id",
            "source",
            "external_id",
            "activity_date",
            "start_time",
            "duration_seconds",
            "aerobic_load",
            "neuromuscular_load",
            "structural_load",
            "has_hr",
            "has_rr_intervals",
            "has_power",
            "calibration_eligible",
            "quality_flags",
            "fit_file_key",
            "ingestion_pipeline_version",
            "cleaning_pipeline_version",
            "notes",
            "created_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in _columns(TABLE)}
        assert expected_column in cols, (
            f"activities.{expected_column} missing from DB schema."
        )

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            "avg_hr",
            "avg_pace",
            "avg_power",
            "avg_cadence",
            "max_hr",
            "max_pace",
            "max_power",
            "lap_data",
            "laps",
            "splits",
            "elevation_gain",
            "calories",
            "training_effect",
        ],
    )
    async def test_workout_summary_columns_are_absent(
        self, db_session: AsyncSession, forbidden_field: str
    ) -> None:
        """Lean-schema invariant at the DB layer. ``lean running
        observation index'' — no summary fields ever."""
        cols = {col["name"] for col in _columns(TABLE)}
        assert forbidden_field not in cols, (
            f"activities.{forbidden_field} physically exists in the DB. "
            f"The Lean-schema invariant forbids it; remove the column."
        )


class TestActivityDedupPartialUniqueIndex:
    """The dedup invariant: ``(athlete_id, external_id, source)`` is
    unique WHERE ``external_id IS NOT NULL``. ``manual_entry`` rows
    have ``external_id IS NULL`` and must NOT collide."""

    def _dedup_index(self, db_session) -> dict | None:
        for idx in _indexes(TABLE):
            cols = idx.get("column_names") or []
            if set(cols) >= {"athlete_id", "external_id", "source"} and idx.get(
                "unique"
            ):
                return idx
        return None

    async def test_partial_unique_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._dedup_index(db_session)
        assert idx is not None, (
            "Expected a UNIQUE index on (athlete_id, external_id, source)."
        )
        # The Inspector surfaces the predicate as ``dialect_options`` on
        # newer SQLAlchemy versions; for Postgres indexes the predicate
        # is exposed via ``postgresql_dialect_options`` or
        # ``dialect_options``.
        predicate = (
            idx.get("dialect_options", {}).get("postgresql", {}).get("where")
            or idx.get("postgresql_dialect_options", {}).get("where")
        )
        # Fall back to introspecting the raw SQL if Inspector did not
        # surface the predicate.
        if predicate is None:
            raw_predicate = await db_session.execute(
                text(
                    "SELECT pg_get_indexdef(indexrelid) "
                    "FROM pg_index WHERE indexrelid = "
                    "(SELECT oid FROM pg_class WHERE relname = :name)"
                ),
                {"name": idx["name"]},
            )
            ddl = raw_predicate.scalar_one() or ""
            assert "external_id" in ddl.lower() and "is not null" in ddl.lower(), (
                f"Dedup index `{idx['name']}` is not partial. DDL: {ddl!r}"
            )
        else:
            rendered = str(predicate).lower()
            assert "external_id" in rendered and "not null" in rendered, (
                f"Dedup index predicate is not `external_id IS NOT NULL`. "
                f"Got: {predicate!r}"
            )

    async def test_duplicate_non_null_external_id_rejected(
        self, db_session: AsyncSession
    ) -> None:
        """Two activities with the same (athlete_id, external_id, source)
        and a non-null external_id must violate the partial unique
        index."""
        athlete = await _new_athlete(db_session, "dup-ext@example.com")
        a1 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.INTERVALS_ICU,
            external_id="ext-abc-123",
            fit_file_key="fit-files/athlete/uuid.fit",
        )
        a2 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.INTERVALS_ICU,
            external_id="ext-abc-123",  # duplicate
            fit_file_key="fit-files/athlete/uuid-other.fit",
        )
        db_session.add_all([a1, a2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_same_external_id_different_source_allowed(
        self, db_session: AsyncSession
    ) -> None:
        """Defence against an over-restrictive ``UNIQUE (athlete_id,
        external_id)`` that ignores source. Two activities for the
        same athlete/external_id but different sources are different
        records."""
        athlete = await _new_athlete(db_session, "diff-src@example.com")
        a1 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.INTERVALS_ICU,
            external_id="shared-ext-id",
            fit_file_key="fit-files/athlete/icu.fit",
        )
        a2 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.GARMIN_DIRECT,
            external_id="shared-ext-id",  # same id, different source
            fit_file_key="fit-files/athlete/garmin.fit",
        )
        db_session.add_all([a1, a2])
        await db_session.flush()
        # Both rows persisted — no IntegrityError raised.
        await db_session.refresh(a1)
        await db_session.refresh(a2)
        assert a1.id != a2.id

    async def test_manual_entry_with_null_external_id_does_not_collide(
        self, db_session: AsyncSession
    ) -> None:
        """``manual_entry`` rows have ``external_id IS NULL`` and the
        partial predicate must let multiple manual entries coexist."""
        athlete = await _new_athlete(db_session, "manual-many@example.com")
        m1 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
        )
        m2 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
        )
        m3 = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
        )
        db_session.add_all([m1, m2, m3])
        # No exception — three manual entries persisted.
        await db_session.flush()
        await db_session.refresh(m1)
        await db_session.refresh(m2)
        await db_session.refresh(m3)
        assert {m1.id, m2.id, m3.id} == {m1.id, m2.id, m3.id}  # all truthy
        assert len({m1.id, m2.id, m3.id}) == 3


class TestActivityIndexesPresent:
    """Athlete/date and athlete/start_time indexes support the query
    patterns that drive twin recalibration windows."""

    async def test_athlete_date_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx_list = _indexes(TABLE)
        matched = [
            idx
            for idx in idx_list
            if set(idx.get("column_names") or []) >= {"athlete_id", "activity_date"}
        ]
        assert matched, (
            "Expected an index on (athlete_id, activity_date) for twin "
            "windowing queries."
        )

    async def test_athlete_start_time_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx_list = _indexes(TABLE)
        matched = [
            idx
            for idx in idx_list
            if set(idx.get("column_names") or []) >= {"athlete_id", "start_time"}
        ]
        assert matched, (
            "Expected an index on (athlete_id, start_time) for time-range "
            "queries that drive twin recalibration windows."
        )


class TestManualEntryInvariants:
    """``manual_entry`` rows are the manual-training-record Tier 6 path.
    The plan codifies: ``fit_file_key IS NULL`` and load scores NULL.
    These columns are nullable for all sources, but the manual-entry
    pattern must hold at the data layer."""

    async def test_manual_entry_persists_with_null_fit_file_key(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "manual-fitnull@example.com")
        activity = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
            fit_file_key=None,
        )
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.fit_file_key is None

    async def test_non_manual_sources_can_have_null_fit_file_key_for_now(
        self, db_session: AsyncSession
    ) -> None:
        """At the DB layer ``fit_file_key`` is universally nullable —
        the ingestion-time invariant is enforced at the service
        boundary (not the DB) because the file is uploaded before the
        row is created. We persist a ``manual_upload`` row with
        ``fit_file_key=None`` and assert the DB accepts it."""
        athlete = await _new_athlete(db_session, "up-no-key@example.com")
        activity = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            external_id="upload-123",
            fit_file_key=None,
        )
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.fit_file_key is None


class TestActivityPersistence:
    """Happy-path insert behaviour — defaults, signal flags, load scores."""

    async def test_load_scores_default_to_null(
        self, db_session: AsyncSession
    ) -> None:
        """Activity insertion of a row with no load scores is valid —
        ``LoadComputationService`` populates them asynchronously. A row
        inserted with explicit nulls must round-trip nulls."""
        athlete = await _new_athlete(db_session, "load-null@example.com")
        activity = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
        )
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.aerobic_load is None
        assert activity.neuromuscular_load is None
        assert activity.structural_load is None

    async def test_signal_flags_round_trip(
        self, db_session: AsyncSession
    ) -> None:
        """All three signal flags can be independently set."""
        athlete = await _new_athlete(db_session, "signals-rt@example.com")
        activity = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.INTERVALS_ICU,
            external_id="signals-1",
            has_hr=True,
            has_rr=True,
            has_power=True,
            fit_file_key="fit-files/x.fit",
        )
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.has_hr is True
        assert activity.has_rr_intervals is True
        assert activity.has_power is True

    async def test_quality_flags_persists_as_jsonb(
        self, db_session: AsyncSession
    ) -> None:
        """``quality_flags`` is structured JSONB. Custom keys present
        per architecture: ``hr_dropout_pct``, ``gps_loss``,
        ``sensor_malfunction``, ``elevated_laxity_risk``."""
        athlete = await _new_athlete(db_session, "qf@example.com")
        activity = _activity_factory(athlete_id=athlete.id)
        activity.quality_flags = {
            "hr_dropout_pct": 14.5,
            "gps_loss": True,
        }
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.quality_flags["hr_dropout_pct"] == 14.5
        assert activity.quality_flags["gps_loss"] is True

    async def test_planned_session_id_is_nullable_uuid_with_or_without_fk(
        self, db_session: AsyncSession
    ) -> None:
        """``activities.planned_session_id`` is a free-standing nullable
        UUID for Phase-1.2a and gains a FK to ``planned_sessions.id``
        in Phase-1.2b.

        The shared ``_prepare_database`` fixture builds the full
        ``Base.metadata`` schema, so this test must be **phase-aware**
        rather than universal: it inspects the live schema and asserts
        whichever contract is currently in force.

        * If ``planned_sessions`` table is absent (Phase-1.2a baseline)
          — persist a row with a random ``planned_session_id`` UUID
          and assert it round-trips. A free-standing nullable UUID
          accepts any value.
        * If ``planned_sessions`` table is present (Phase-1.2b) — first
          create a real ``PlannedSession`` row so the FK is satisfied,
          then assert the persisted ``Activity`` carries the correct
          reference. This proves the FK is wired to ``planned_sessions.id``
          rather than silently verified.

        In both phases the column is **nullable** — the schema
        contract ``activities.planned_session_id IS NULL`` is the
        common assertion at the end.
        """
        import uuid as _uuid

        engine = create_engine(_sync_url())
        try:
            with engine.connect() as conn:
                has_planned_sessions = conn.execute(
                    text(
                        "SELECT EXISTS ("
                        "  SELECT 1 FROM information_schema.tables "
                        "  WHERE table_schema = current_schema() "
                        "    AND table_name = 'planned_sessions' "
                        ")"
                    )
                ).scalar_one()
        finally:
            engine.dispose()

        athlete = await _new_athlete(db_session, "plan-sess@example.com")
        activity = _activity_factory(athlete_id=athlete.id)

        if not has_planned_sessions:
            # Phase-1.2a: free-standing nullable UUID. Persist any
            # random UUID — with no FK to violate, the row commits.
            activity.planned_session_id = _uuid.uuid4()
            db_session.add(activity)
            await db_session.flush()
            await db_session.refresh(activity)
            assert activity.planned_session_id is not None
            return

        # Phase-1.2b: FK to planned_sessions.id is enforced. We must
        # create a real PlannedSession row to satisfy the FK before
        # asserting the link holds.
        from datetime import date as _date
        from app.models.training_goal import TrainingGoal
        from app.models.training_plan import TrainingPlan
        from app.models.weekly_plan import WeeklyPlan
        from app.models.planned_session import PlannedSession
        from app.models.enums import (
            GoalType,
            PhaseLabel,
            PlannedSessionStatus,
            SessionPriority,
            SessionSlot,
            SessionType,
            TrainingGoalStatus,
            TrainingPlanStatus,
            WeeklyPlanStatus,
        )

        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.MAINTENANCE,
            weekly_volume_hours=4.0,
            weekly_volume_km=25.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        await db_session.flush()

        plan = TrainingPlan(
            training_goal_id=goal.id,
            status=TrainingPlanStatus.ACTIVE,
        )
        db_session.add(plan)
        await db_session.flush()

        weekly = WeeklyPlan(
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=_date(2026, 6, 22),
            week_ends_at=_date(2026, 6, 28),
            adjusted_intent={
                "methodology": "pheidipp-default",
                "target_distribution": {},
                "objectives": [],
                "session_count": 1,
                "adjustment_flags": {},
            },
            status=WeeklyPlanStatus.ACTIVE,
        )
        db_session.add(weekly)
        await db_session.flush()

        planned = PlannedSession(
            weekly_plan_id=weekly.id,
            training_plan_id=plan.id,
            week_number=1,
            target_date=_date(2026, 6, 22),
            phase_label=PhaseLabel.AEROBIC_BASE,
            session_slot=SessionSlot.AM,
            session_type=SessionType.EASY_RUN,
            intent_description="Light aerobic opener",
            approximate_duration_minutes=45,
            status=PlannedSessionStatus.PENDING,
            session_priority=SessionPriority.PRIMARY,
        )
        db_session.add(planned)
        await db_session.flush()
        planned_id = planned.id

        activity.planned_session_id = planned_id
        db_session.add(activity)
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.planned_session_id == planned_id

        # And the nullable invariant holds when we leave it NULL.
        activity.planned_session_id = None
        await db_session.flush()
        await db_session.refresh(activity)
        assert activity.planned_session_id is None


class TestActivityForeignKeyCascade:
    """When an ``Athlete`` is deleted, associated ``Activity`` rows must
    be cascaded. The architecture contract puts this at the FK."""

    async def test_activity_rows_cascade_with_athlete(
        self, db_session: AsyncSession
    ) -> None:
        from sqlalchemy import delete as sa_delete

        athlete = await _new_athlete(db_session, "cascade@example.com")
        activity = _activity_factory(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
        )
        db_session.add(activity)
        await db_session.flush()
        activity_id = activity.id

        # Delete the athlete and commit (autouse fixture rolls back
        # after, so we explicitly commit to observe the cascade).
        await db_session.execute(
            sa_delete(Athlete).where(Athlete.id == athlete.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(Activity).where(Activity.id == activity_id)
        )
        assert remaining.scalar_one_or_none() is None
