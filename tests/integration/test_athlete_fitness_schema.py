"""Integration tests for the ``AthleteFitness`` schema at the DB level.

Phase-1.2c introduces the ``athlete_fitness`` table — a mutable
current-state entity that stores Banister rolling fitness/fatigue
scores (aggregate + per-dimension) with DB-enforced
``form = fitness - fatigue`` invariants.

The DB-level invariants codified here:

* The unique index ``uq_athlete_fitness_athlete`` on
  ``(athlete_id)`` enforces one row per athlete.
* CHECK ``ck_athlete_fitness_aggregate_form_invariant`` enforces
  ``form = fitness - fatigue`` on the aggregate JSONB.
* CHECK constraints for aerobic/neuromuscular/structural dimensional
  blocks enforce the same invariant but allow NULL (optional
  dimensions).
* CHECK ``ck_athlete_fitness_time_constants_source_valid`` bounds
  ``time_constants.source`` to ``population_default|individual_fitted``.
* FK ``athlete_id`` ON DELETE CASCADE; FK ``last_activity_id`` ON
  DELETE SET NULL.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete_fitness import AthleteFitness
from app.models.enums import ActivitySource
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_check_constraints,
    db_columns,
    db_foreign_keys,
    db_indexes,
    get_sync_database_url,
)


TABLE = "athlete_fitness"


def _aggregate(
    *, fitness: float, fatigue: float, form: float | None = None
) -> dict[str, Any]:
    return {
        "fitness": fitness,
        "fatigue": fatigue,
        "form": form if form is not None else (fitness - fatigue),
    }


def _default_time_constants(source: str = "population_default") -> dict[str, Any]:
    return {
        "fitness_tau_days": 42.0,
        "fatigue_tau_days": 7.0,
        "source": source,
        "fitted_at": None,
    }


def _fitness_factory(
    *,
    athlete_id: uuid.UUID,
    aggregate: dict[str, Any] | None = None,
    aerobic: dict[str, Any] | None = None,
    neuromuscular: dict[str, Any] | None = None,
    structural: dict[str, Any] | None = None,
    time_constants: dict[str, Any] | None = None,
    last_activity_id: uuid.UUID | None = None,
) -> AthleteFitness:
    return AthleteFitness(
        athlete_id=athlete_id,
        aggregate=aggregate
        if aggregate is not None
        else _aggregate(fitness=10.0, fatigue=2.0),
        aerobic=aerobic,
        neuromuscular=neuromuscular,
        structural=structural,
        time_constants=time_constants or _default_time_constants(),
        last_activity_id=last_activity_id,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestAthleteFitnessDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "aggregate",
            "aerobic",
            "neuromuscular",
            "structural",
            "time_constants",
            "last_activity_id",
            "updated_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"athlete_fitness.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Unique index — one AthleteFitness row per athlete.
# ---------------------------------------------------------------------------


class TestAthleteFitnessUniqueIndexDB:
    def test_unique_index_present(self) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ()) == {"athlete_id"}
            and idx.get("unique")
        ]
        assert matched, (
            "athlete_fitness must declare UNIQUE (athlete_id). "
            f"Got: {[idx.get('column_names') for idx in db_indexes(TABLE)]}"
        )

    async def test_two_fitness_rows_same_athlete_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-dup@example.com"
        )
        f1 = _fitness_factory(athlete_id=athlete.id)
        f2 = _fitness_factory(athlete_id=athlete.id)
        db_session.add_all([f1, f2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# CHECK constraints — form = fitness - fatigue invariant.
# ---------------------------------------------------------------------------


class TestAthleteFitnessAggregateFormCheckDB:
    """``aggregate->>'form'::float = (aggregate->>'fitness')::float -
    (aggregate->>'fatigue')::float`` — the architectural invariant."""

    def test_aggregate_form_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "aggregate" in (c.get("sqltext") or "").lower()
            and "fitness" in (c.get("sqltext") or "").lower()
            and "fatigue" in (c.get("sqltext") or "").lower()
            and "form" in (c.get("sqltext") or "").lower()
            and "-" in (c.get("sqltext") or "")
            for c in checks
        )
        assert found, (
            "athlete_fitness must declare CHECK constraint "
            "`aggregate->>'form'::float = aggregate->>'fitness'::float - "
            "aggregate->>'fatigue'::float`."
        )

    async def test_invalid_form_in_aggregate_rejected(
        self, db_session: AsyncSession
    ) -> None:
        """form != fitness - fatigue must raise IntegrityError."""
        athlete = await make_athlete(
            db_session, "fit-bad-form@example.com"
        )
        bad_aggregate = {"fitness": 10.0, "fatigue": 2.0, "form": 99.0}
        row = _fitness_factory(
            athlete_id=athlete.id, aggregate=bad_aggregate
        )
        db_session.add(row)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_valid_form_in_aggregate_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-good-form@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            aggregate=_aggregate(fitness=20.0, fatigue=5.0, form=15.0),
        )
        db_session.add(row)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.aggregate["form"] == 15.0

    async def test_negative_form_in_aggregate_accepted(
        self, db_session: AsyncSession
    ) -> None:
        """Architecture invariant: negative ``form`` is valid (load
        phase). No lower-bound CHECK is applied to ``form``."""
        athlete = await make_athlete(
            db_session, "fit-negative-form@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            aggregate=_aggregate(fitness=5.0, fatigue=15.0, form=-10.0),
        )
        db_session.add(row)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.aggregate["form"] == -10.0


class TestAthleteFitnessDimensionFormChecksDB:
    """Aerobic / neuromuscular / structural CHECKs fire only when
    the dimension is populated (NULL short-circuits)."""

    def test_aerobic_form_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        aerobic_checks = [
            c
            for c in checks
            if "aerobic" in (c.get("sqltext") or "").lower()
            and "form" in (c.get("sqltext") or "").lower()
        ]
        assert aerobic_checks, (
            "athlete_fitness must declare CHECK constraint "
            "enforcing `aerobic->>'form' = aerobic->>'fitness' - "
            "aerobic->>'fatigue'`."
        )
        aerobic_sqltext = (aerobic_checks[0].get("sqltext") or "").lower()
        assert "is null" in aerobic_sqltext, (
            "Aerobic form invariant must short-circuit on NULL — "
            "optional dimensional blocks must be permitted to be NULL."
        )

    def test_neuromuscular_form_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        neuromuscular_checks = [
            c
            for c in checks
            if "neuromuscular" in (c.get("sqltext") or "").lower()
            and "form" in (c.get("sqltext") or "").lower()
        ]
        assert neuromuscular_checks, (
            "athlete_fitness must declare CHECK constraint on "
            "neuromuscular block."
        )

    def test_structural_form_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        structural_checks = [
            c
            for c in checks
            if "structural" in (c.get("sqltext") or "").lower()
            and "form" in (c.get("sqltext") or "").lower()
        ]
        assert structural_checks, (
            "athlete_fitness must declare CHECK constraint on "
            "structural block."
        )

    async def test_null_aerobic_does_not_trigger_form_check(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-null-aerobic@example.com"
        )
        # aerobic, neuromuscular, structural all NULL — only the
        # aggregate CHECK should fire.
        row = _fitness_factory(
            athlete_id=athlete.id,
            aerobic=None,
            neuromuscular=None,
            structural=None,
        )
        db_session.add(row)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.aerobic is None
        assert row.neuromuscular is None
        assert row.structural is None

    async def test_populated_aerobic_with_bad_form_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-bad-aerobic@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            aerobic={
                "fitness": 8.0,
                "fatigue": 1.0,
                "form": 99.0,  # wrong — must be 7.0
            },
        )
        db_session.add(row)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_populated_aerobic_with_good_form_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-good-aerobic@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            aerobic={
                "fitness": 8.0,
                "fatigue": 1.0,
                "form": 7.0,
            },
        )
        db_session.add(row)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.aerobic is not None
        assert row.aerobic["form"] == 7.0


# ---------------------------------------------------------------------------
# CHECK constraint — time_constants.source valid.
# ---------------------------------------------------------------------------


class TestAthleteFitnessTimeConstantsSourceCheckDB:
    def test_source_check_present(self) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "time_constants" in (c.get("sqltext") or "").lower()
            and "source" in (c.get("sqltext") or "").lower()
            and "population_default" in (c.get("sqltext") or "").lower()
            and "individual_fitted" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "athlete_fitness must declare CHECK constraint "
            "bounding `time_constants.source` to "
            "`population_default|individual_fitted`."
        )

    async def test_invalid_source_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-bad-source@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            time_constants={
                "fitness_tau_days": 42.0,
                "fatigue_tau_days": 7.0,
                "source": "best_guess",  # not in the closed ontology
                "fitted_at": None,
            },
        )
        db_session.add(row)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestAthleteFitnessForeignKeysDB:
    def test_athlete_id_fk_to_athletes(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks

    def test_last_activity_id_fk_to_activities(self) -> None:
        fks = db_foreign_keys(TABLE)
        activity_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "activities"
            and tuple(fk.get("constrained_columns") or ())
            == ("last_activity_id",)
        ]
        assert activity_fks

    def test_athlete_fk_ondelete_is_cascade(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks, (
            "athlete_fitness.athlete_id FK must reference athletes(id)."
        )
        assert athlete_fks[0].get("options", {}).get("ondelete") == "CASCADE", (
            "athlete_fitness.athlete_id FK ON DELETE must be CASCADE."
        )

    def test_last_activity_fk_ondelete_is_set_null(self) -> None:
        fks = db_foreign_keys(TABLE)
        activity_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "activities"
            and tuple(fk.get("constrained_columns") or ())
            == ("last_activity_id",)
        ]
        assert activity_fks, (
            "athlete_fitness.last_activity_id FK must reference activities(id)."
        )
        assert activity_fks[0].get("options", {}).get("ondelete") == "SET NULL", (
            "athlete_fitness.last_activity_id FK ON DELETE must be SET NULL."
        )

    async def test_last_activity_id_set_null_on_activity_delete(
        self, db_session: AsyncSession
    ) -> None:
        """When the parent Activity is deleted, last_activity_id
        is set to NULL (history outlives the source activity)."""
        athlete = await make_athlete(
            db_session, "fit-activity-fk@example.com"
        )
        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
            activity_date=date(2026, 6, 19),
            start_time=datetime(2026, 6, 19, 7, 30, tzinfo=timezone.utc),
            duration_seconds=3600,
        )
        db_session.add(activity)
        await db_session.flush()

        row = _fitness_factory(
            athlete_id=athlete.id, last_activity_id=activity.id
        )
        db_session.add(row)
        await db_session.flush()
        row_id = row.id

        # Commit and then delete the activity.
        await db_session.commit()
        await db_session.delete(activity)
        await db_session.commit()

        # Query via a fresh sync connection.
        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT last_activity_id FROM athlete_fitness "
                        "WHERE id = :id"
                    ),
                    {"id": row_id},
                ).fetchone()
        finally:
            engine.dispose()
        assert result is not None
        assert result[0] is None, (
            f"last_activity_id must be SET NULL after activity delete. "
            f"Got: {result[0]!r}"
        )


# ---------------------------------------------------------------------------
# Mutability — service-layer rolling Banister updates.
# ---------------------------------------------------------------------------


class TestAthleteFitnessMutabilityDB:
    async def test_update_aggregate_succeeds(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-update@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            aggregate=_aggregate(fitness=10.0, fatigue=2.0, form=8.0),
        )
        db_session.add(row)
        await db_session.flush()

        # Service-layer rolling update — replaces aggregate.
        row.aggregate = _aggregate(fitness=15.0, fatigue=3.0, form=12.0)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.aggregate["fitness"] == 15.0
        assert row.aggregate["fatigue"] == 3.0
        assert row.aggregate["form"] == 12.0


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestAthleteFitnessRoundTripDB:
    async def test_minimal_fitness_row_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "fit-minimal@example.com"
        )
        row = _fitness_factory(
            athlete_id=athlete.id,
            aggregate=_aggregate(fitness=0.0, fatigue=0.0, form=0.0),
        )
        db_session.add(row)
        await db_session.flush()
        row_id = row.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(AthleteFitness).where(AthleteFitness.id == row_id)
        )
        loaded = result.scalar_one()
        assert loaded.aggregate["fitness"] == 0.0
        assert loaded.aggregate["fatigue"] == 0.0
        assert loaded.aggregate["form"] == 0.0
        assert loaded.time_constants["source"] == "population_default"
        assert loaded.aerobic is None
        assert loaded.neuromuscular is None
        assert loaded.structural is None