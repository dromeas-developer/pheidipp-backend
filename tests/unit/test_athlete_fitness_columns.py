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
    DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.athlete_fitness import AthleteFitness
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_check_constraints,
    get_foreign_keys_referencing,
    get_check_text,
    get_server_default_text,
)


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestAthleteFitnessRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(AthleteFitness)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = get_columns(AthleteFitness)["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — fitness rows are wiped
        when the athlete account is deleted."""
        fks = get_foreign_keys_referencing(AthleteFitness, "athlete_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_aggregate_required_jsonb(self) -> None:
        """``aggregate`` is NOT NULL — always populated. Carries the
        ``{fitness, fatigue, form}`` shape; the ``form`` field is
        enforced equal to ``fitness - fatigue`` by a CHECK constraint."""
        col = get_columns(AthleteFitness)["aggregate"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_aerobic_nullable_jsonb(self) -> None:
        col = get_columns(AthleteFitness)["aerobic"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_neuromuscular_nullable_jsonb(self) -> None:
        col = get_columns(AthleteFitness)["neuromuscular"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_structural_nullable_jsonb(self) -> None:
        col = get_columns(AthleteFitness)["structural"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_time_constants_required_jsonb(self) -> None:
        """``time_constants`` is NOT NULL — BanisterTimeConstants JSONB."""
        col = get_columns(AthleteFitness)["time_constants"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_last_activity_id_nullable_uuid(self) -> None:
        col = get_columns(AthleteFitness)["last_activity_id"]
        assert col.nullable is True
        assert isinstance(col.type, PG_UUID)

    def test_last_activity_id_set_null_fk_to_activities(self) -> None:
        """Activity FK ON DELETE SET NULL — fitness history is
        preserved when an Activity is deleted (fitness score
        outlives the source activity)."""
        fks = get_foreign_keys_referencing(AthleteFitness, "last_activity_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "activities"
        assert fk.ondelete == "SET NULL"

    def test_updated_at_required_datetime(self) -> None:
        col = get_columns(AthleteFitness)["updated_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_updated_at_has_server_default_now(self) -> None:
        col = get_columns(AthleteFitness)["updated_at"]
        assert col.server_default is not None
        assert "now" in get_server_default_text(col).lower()


# ---------------------------------------------------------------------------
# CHECK constraints — form = fitness - fatigue invariant.
# ---------------------------------------------------------------------------


class TestAthleteFitnessFormInvariantChecks:
    """The architectural invariant: ``form == fitness - fatigue``
    for aggregate + each populated dimension. CHECK constraints
    enforce it at the DB layer."""

    def test_aggregate_form_invariant_check(self) -> None:
        checks = get_check_constraints(AthleteFitness)
        assert any(
            "aggregate" in get_check_text(c)
            and "fitness" in get_check_text(c)
            and "fatigue" in get_check_text(c)
            and "form" in get_check_text(c)
            and "-" in get_check_text(c)
            for c in checks
        ), (
            "AthleteFitness must declare a CHECK constraint on "
            "aggregate enforcing `form = fitness - fatigue`."
        )

    def test_aerobic_form_invariant_check(self) -> None:
        """Aerobic form invariant only fires when the block is
        populated — the predicate includes an ``IS NULL`` short
        circuit so optional blocks are not blocked."""
        checks = get_check_constraints(AthleteFitness)
        aerobic_checks = [
            c
            for c in checks
            if "aerobic" in get_check_text(c).lower()
            and "form" in get_check_text(c).lower()
        ]
        assert aerobic_checks, (
            "AthleteFitness must declare a CHECK constraint on the "
            "aerobic block enforcing `form = fitness - fatigue`."
        )
        aerobic_text = get_check_text(aerobic_checks[0]).lower()
        assert "is null" in aerobic_text, (
            "Aerobic form invariant must short-circuit on NULL — "
            "optional dimensional blocks must be permitted to be "
            "NULL without triggering the form check."
        )

    def test_neuromuscular_form_invariant_check(self) -> None:
        checks = get_check_constraints(AthleteFitness)
        neuromuscular_checks = [
            c
            for c in checks
            if "neuromuscular" in get_check_text(c).lower()
            and "form" in get_check_text(c).lower()
        ]
        assert neuromuscular_checks, (
            "AthleteFitness must declare a CHECK constraint on the "
            "neuromuscular block enforcing `form = fitness - fatigue`."
        )

    def test_structural_form_invariant_check(self) -> None:
        checks = get_check_constraints(AthleteFitness)
        structural_checks = [
            c
            for c in checks
            if "structural" in get_check_text(c).lower()
            and "form" in get_check_text(c).lower()
        ]
        assert structural_checks, (
            "AthleteFitness must declare a CHECK constraint on the "
            "structural block enforcing `form = fitness - fatigue`."
        )


class TestAthleteFitnessTimeConstantsSourceCheck:
    """``time_constants.source`` is bounded to
    ``population_default`` or ``individual_fitted``."""

    def test_time_constants_source_check_present(self) -> None:
        checks = get_check_constraints(AthleteFitness)
        found = any(
            "time_constants" in get_check_text(c).lower()
            and "source" in get_check_text(c).lower()
            and "population_default" in get_check_text(c).lower()
            and "individual_fitted" in get_check_text(c).lower()
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
        indexes = get_indexes(AthleteFitness)
        assert "uq_athlete_fitness_athlete" in indexes, (
            "AthleteFitness must declare `uq_athlete_fitness_athlete` "
            "to enforce one row per athlete at the DB layer."
        )

    def test_unique_index_is_unique(self) -> None:
        idx = get_indexes(AthleteFitness)["uq_athlete_fitness_athlete"]
        assert idx.unique is True

    def test_unique_index_columns(self) -> None:
        idx = get_indexes(AthleteFitness)["uq_athlete_fitness_athlete"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id"}


class TestAthleteFitnessLastActivityIndex:
    """``ix_athlete_fitness_last_activity`` supports reverse lookup
    from the last activity that drove the update."""

    def test_last_activity_index_present(self) -> None:
        indexes = get_indexes(AthleteFitness)
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
        assert forbidden_field not in get_columns(AthleteFitness), (
            f"AthleteFitness must not carry `{forbidden_field}`. "
            "Fitness/fatigue/form live on the aggregate JSONB; "
            "physiology parameters live on AthletePhysiology."
        )