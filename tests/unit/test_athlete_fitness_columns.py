"""Unit tests for the ``AthleteFitness`` declarative surface (no DB).

Phase-1.2c introduces the ``AthleteFitness`` schema — a mutable
current-state entity that stores Banister rolling fitness/fatigue
scores (aggregate + per-dimension), the time-constants config, and
the ``last_activity_id`` anchoring reference.

Invariants pinned here:

* One row per athlete — enforced by the unique index
  ``uq_athlete_fitness_athlete`` on ``(athlete_id)``.
* MUTABLE — the Phase-1.6 ``FitnessUpdateService`` is the only
  writer; the table itself is fully mutable so rolling Banister
  scores can rewrite the row.
* ``aggregate`` JSONB is NOT NULL — always populated.
* ``aerobic``, ``neuromuscular``, ``structural`` are nullable JSONB.
* ``form = fitness - fatigue`` CHECK enforced for aggregate (always)
  and each populated dimension (aerobic / neuromuscular / structural).
* ``time_constants.source`` is bounded to ``population_default`` or
  ``individual_fitted``.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/athlete-fitness.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.athlete_fitness import AthleteFitness


def _columns() -> dict[str, object]:
    return {column.key: column for column in AthleteFitness.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in AthleteFitness.__table__.indexes}


def _check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in AthleteFitness.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


def _foreign_keys_referencing(column_key: str) -> list[ForeignKey]:
    return [
        fk
        for fk in AthleteFitness.__table__.foreign_keys
        if fk.parent.name == column_key
    ]


def _check_text(check: CheckConstraint) -> str:
    """Return the SQL expression text of a CheckConstraint as a string.

    Shared helper across multiple test classes so that each class does
    not have to redefine it. SQLAlchemy exposes the constraint's
    expression via ``.expression`` (modern) or ``.sqltext`` (legacy) —
    this helper accepts either.
    """
    expr = getattr(check, "expression", None) or getattr(
        check, "sqltext", None
    )
    return str(expr) if expr is not None else ""


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestAthleteFitnessRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = _columns()["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — fitness rows are wiped
        when the athlete account is deleted."""
        fks = _foreign_keys_referencing("athlete_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_aggregate_required_jsonb(self) -> None:
        """``aggregate`` is NOT NULL — always populated. Carries the
        ``{fitness, fatigue, form}`` shape; the ``form`` field is
        enforced equal to ``fitness - fatigue`` by a CHECK constraint."""
        col = _columns()["aggregate"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_aerobic_nullable_jsonb(self) -> None:
        col = _columns()["aerobic"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_neuromuscular_nullable_jsonb(self) -> None:
        col = _columns()["neuromuscular"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_structural_nullable_jsonb(self) -> None:
        col = _columns()["structural"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_time_constants_required_jsonb(self) -> None:
        """``time_constants`` is NOT NULL — BanisterTimeConstants JSONB."""
        col = _columns()["time_constants"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_last_activity_id_nullable_uuid(self) -> None:
        col = _columns()["last_activity_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)

    def test_last_activity_id_set_null_fk_to_activities(self) -> None:
        """Activity FK ON DELETE SET NULL — fitness history is
        preserved when an Activity is deleted (fitness score
        outlives the source activity)."""
        fks = _foreign_keys_referencing("last_activity_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "activities"
        assert fk.ondelete == "SET NULL"

    def test_updated_at_required_datetime(self) -> None:
        col = _columns()["updated_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_updated_at_has_server_default_now(self) -> None:
        col = _columns()["updated_at"]
        assert col.server_default is not None
        assert "now" in str(col.server_default.arg).lower()


# ---------------------------------------------------------------------------
# CHECK constraints — form = fitness - fatigue invariant.
# ---------------------------------------------------------------------------


class TestAthleteFitnessFormInvariantChecks:
    """The architectural invariant: ``form == fitness - fatigue``
    for aggregate + each populated dimension. CHECK constraints
    enforce it at the DB layer."""

    def test_aggregate_form_invariant_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "aggregate" in _check_text(c)
            and "fitness" in _check_text(c)
            and "fatigue" in _check_text(c)
            and "form" in _check_text(c)
            and "-" in _check_text(c)
            for c in checks
        ), (
            "AthleteFitness must declare a CHECK constraint on "
            "aggregate enforcing `form = fitness - fatigue`."
        )

    def test_aerobic_form_invariant_check(self) -> None:
        """Aerobic form invariant only fires when the block is
        populated — the predicate includes an ``IS NULL`` short
        circuit so optional blocks are not blocked."""
        checks = _check_constraints()
        aerobic_checks = [
            c
            for c in checks
            if "aerobic" in _check_text(c).lower()
            and "form" in _check_text(c).lower()
        ]
        assert aerobic_checks, (
            "AthleteFitness must declare a CHECK constraint on the "
            "aerobic block enforcing `form = fitness - fatigue`."
        )
        aerobic_text = _check_text(aerobic_checks[0]).lower()
        assert "is null" in aerobic_text, (
            "Aerobic form invariant must short-circuit on NULL — "
            "optional dimensional blocks must be permitted to be "
            "NULL without triggering the form check."
        )

    def test_neuromuscular_form_invariant_check(self) -> None:
        checks = _check_constraints()
        neuromuscular_checks = [
            c
            for c in checks
            if "neuromuscular" in _check_text(c).lower()
            and "form" in _check_text(c).lower()
        ]
        assert neuromuscular_checks, (
            "AthleteFitness must declare a CHECK constraint on the "
            "neuromuscular block enforcing `form = fitness - fatigue`."
        )

    def test_structural_form_invariant_check(self) -> None:
        checks = _check_constraints()
        structural_checks = [
            c
            for c in checks
            if "structural" in _check_text(c).lower()
            and "form" in _check_text(c).lower()
        ]
        assert structural_checks, (
            "AthleteFitness must declare a CHECK constraint on the "
            "structural block enforcing `form = fitness - fatigue`."
        )


class TestAthleteFitnessTimeConstantsSourceCheck:
    """``time_constants.source`` is bounded to
    ``population_default`` or ``individual_fitted``."""

    def test_time_constants_source_check_present(self) -> None:
        checks = _check_constraints()
        found = any(
            "time_constants" in _check_text(c).lower()
            and "source" in _check_text(c).lower()
            and "population_default" in _check_text(c).lower()
            and "individual_fitted" in _check_text(c).lower()
            for c in checks
        )
        assert found, (
            "AthleteFitness must declare a CHECK constraint "
            "bounding `time_constants.source` to "
            "`population_default` or `individual_fitted`."
        )


# ---------------------------------------------------------------------------
# Unique index — one AthleteFitness row per athlete.
# ---------------------------------------------------------------------------


class TestAthleteFitnessUniqueIndex:
    def test_unique_index_present(self) -> None:
        indexes = _indexes()
        assert "uq_athlete_fitness_athlete" in indexes, (
            "AthleteFitness must declare `uq_athlete_fitness_athlete` "
            "to enforce one row per athlete at the DB layer."
        )

    def test_unique_index_is_unique(self) -> None:
        idx = _indexes()["uq_athlete_fitness_athlete"]
        assert idx.unique is True

    def test_unique_index_columns(self) -> None:
        idx = _indexes()["uq_athlete_fitness_athlete"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id"}


class TestAthleteFitnessLastActivityIndex:
    """``ix_athlete_fitness_last_activity`` supports reverse lookup
    from the last activity that drove the update."""

    def test_last_activity_index_present(self) -> None:
        indexes = _indexes()
        assert "ix_athlete_fitness_last_activity" in indexes


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on AthleteFitness.
# ---------------------------------------------------------------------------


class TestAthleteFitnessSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # History belongs on append-only TwinState.
            "deleted_at",
            "is_deleted",
            # Physiology parameters live on AthletePhysiology, not here.
            "lt1",
            "lt2",
            "cp",
            "vo2max",
            "max_hr",
            "twin_state_id",
            # Form must derive from fitness - fatigue — never stored
            # as a separate mutable field.
            "form_value",
            "raw_form",
            # Confidence / metric lives on TwinState.metric_confidence.
            "metric_confidence",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _columns(), (
            f"AthleteFitness must not carry `{forbidden_field}`. "
            "Fitness/fatigue/form live on the aggregate JSONB; "
            "physiology parameters live on AthletePhysiology."
        )