"""Unit tests for the ``AthletePhysiology`` declarative surface (no DB).

Phase-1.2c introduces the ``AthletePhysiology`` schema — a mutable
current-state entity that stores per-parameter posterior estimates
(``lt1``, ``lt2``, ``cp``, ``vo2max``, ``max_hr``) as per-dimension
JSONB columns.

Invariants pinned here:

* One row per athlete — enforced by the unique index
  ``uq_athlete_physiology_athlete`` on ``(athlete_id)``.
* MUTABLE — the Phase-1.6 ``PhysiologyUpdateService`` is the only
  writer; the table itself is fully mutable so posterior decay and
  rescaling can rewrite the row.
* ``lt1`` and ``lt2`` are NOT NULL (always populated — defaults at
  onboarding include at least a ``max_hr`` bootstrapped value).
* ``cp``, ``vo2max``, ``max_hr`` are nullable JSONB (null until a
  qualifying observation is made).
* ``updated_at`` is set by the service on every posterior update.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/athlete-physiology.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.athlete_physiology import AthletePhysiology


def _columns() -> dict[str, object]:
    return {column.key: column for column in AthletePhysiology.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in AthletePhysiology.__table__.indexes}


def _foreign_keys_referencing(column_key: str) -> list[ForeignKey]:
    return [
        fk
        for fk in AthletePhysiology.__table__.foreign_keys
        if fk.parent.name == column_key
    ]


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_required_uuid(self) -> None:
        col = _columns()["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_athlete_id_cascade_fk_to_athletes(self) -> None:
        """Athlete FK ON DELETE CASCADE — physiology rows are wiped
        when the athlete account is deleted."""
        fks = _foreign_keys_referencing("athlete_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "athletes"
        assert fk.ondelete == "CASCADE"

    def test_lt1_required_jsonb(self) -> None:
        """``lt1`` is NOT NULL — always populated. Carries the three
        per-signal state objects (hr / power / pace) or JSON null."""
        col = _columns()["lt1"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_lt2_required_jsonb(self) -> None:
        """``lt2`` is NOT NULL — same shape as lt1."""
        col = _columns()["lt2"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_cp_nullable_jsonb(self) -> None:
        """``cp`` is NULL until first qualifying observation."""
        col = _columns()["cp"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_vo2max_nullable_jsonb(self) -> None:
        """``vo2max`` is NULL until first qualifying observation —
        either ml_kg_min or power sub-state may populate later."""
        col = _columns()["vo2max"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_max_hr_nullable_jsonb(self) -> None:
        """``max_hr`` is bootstrapped from 220 - age at onboarding,
        but the column is nullable at the schema level so a fresh
        row can be inserted before the service populates it."""
        col = _columns()["max_hr"]
        assert col.nullable is True
        assert isinstance(col.type, JSONB)

    def test_updated_at_required_datetime(self) -> None:
        col = _columns()["updated_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_updated_at_has_server_default_now(self) -> None:
        """``updated_at`` server_default is ``now()`` so inserts
        without an explicit value still produce a usable timestamp."""
        col = _columns()["updated_at"]
        assert col.server_default is not None
        assert "now" in str(col.server_default.arg).lower()


# ---------------------------------------------------------------------------
# Unique index — one AthletePhysiology row per athlete.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyUniqueIndex:
    """DB-enforced one-per-athlete invariant via the unique index
    ``uq_athlete_physiology_athlete`` on ``(athlete_id)``."""

    def test_unique_index_present(self) -> None:
        indexes = _indexes()
        assert "uq_athlete_physiology_athlete" in indexes, (
            "AthletePhysiology must declare "
            "`uq_athlete_physiology_athlete` to enforce one row "
            "per athlete at the DB layer."
        )

    def test_unique_index_is_unique(self) -> None:
        idx = _indexes()["uq_athlete_physiology_athlete"]
        assert idx.unique is True

    def test_unique_index_columns(self) -> None:
        idx = _indexes()["uq_athlete_physiology_athlete"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id"}


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on AthletePhysiology.
# ---------------------------------------------------------------------------


class TestAthletePhysiologySchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # History belongs in append-only TwinState — current-state
            # entity must not carry a soft-delete or version column.
            "deleted_at",
            "is_deleted",
            "version",
            # Service-layer concerns.
            "twin_state_id",
            "raw_observation",
            "measurement_source",
            # Activity FKs — Physiology links to Athlete only.
            "activity_id",
            "last_activity_id",
            # Aggregate scores belong on AthleteFitness, not here.
            "fitness",
            "fatigue",
            "form",
            "aggregate",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _columns(), (
            f"AthletePhysiology must not carry `{forbidden_field}`. "
            "Current-state per-parameter posterior estimates only; "
            "history lives on append-only TwinState, fitness scores "
            "live on AthleteFitness."
        )