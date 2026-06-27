"""Integration tests for the ``AthletePhysiology`` schema at the DB level.

Phase-1.2c introduces the ``athlete_physiology`` table — a mutable
current-state entity that stores per-parameter posterior estimates
(``lt1``, ``lt2``, ``cp``, ``vo2max``, ``max_hr``) as per-dimension
JSONB columns.

The DB-level invariants codified here:

* The unique index ``uq_athlete_physiology_athlete`` on
  ``(athlete_id)`` enforces one row per athlete.
* ``lt1`` and ``lt2`` are NOT NULL — always populated.
* ``cp``, ``vo2max``, ``max_hr`` are nullable JSONB — null until a
  qualifying observation.
* FK ``athlete_id`` is ON DELETE CASCADE.
* Mutable — posterior updates succeed.

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_physiology import AthletePhysiology
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import db_columns, db_foreign_keys, db_indexes


TABLE = "athlete_physiology"


def _physiology_factory(
    *,
    athlete_id: uuid.UUID,
    lt1: dict | None = None,
    lt2: dict | None = None,
    cp: dict | None = None,
    vo2max: dict | None = None,
    max_hr: dict | None = None,
) -> AthletePhysiology:
    default_lt1 = {
        "hr": {
            "value": 152.0,
            "uncertainty": 8.5,
            "prior_weight": 0.5,
            "dominant_source": "questionnaire_estimate",
            "last_observation_date": "2026-06-24",
        },
        "power": None,
        "pace": None,
    }
    default_lt2 = {
        "hr": {
            "value": 168.0,
            "uncertainty": 7.0,
            "prior_weight": 0.5,
            "dominant_source": "questionnaire_estimate",
            "last_observation_date": "2026-06-24",
        },
        "power": None,
        "pace": None,
    }
    return AthletePhysiology(
        athlete_id=athlete_id,
        lt1=lt1 if lt1 is not None else default_lt1,
        lt2=lt2 if lt2 is not None else default_lt2,
        cp=cp,
        vo2max=vo2max,
        max_hr=max_hr,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "lt1",
            "lt2",
            "cp",
            "vo2max",
            "max_hr",
            "updated_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"athlete_physiology.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Unique index — one AthletePhysiology row per athlete.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyUniqueIndexDB:
    def test_unique_index_present(self) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or ()) == {"athlete_id"}
            and idx.get("unique")
        ]
        assert matched, (
            "athlete_physiology must declare UNIQUE (athlete_id) — "
            "one row per athlete. "
            f"Got: {[idx.get('column_names') for idx in db_indexes(TABLE)]}"
        )

    async def test_two_physiology_rows_same_athlete_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "phys-dup@example.com"
        )
        p1 = _physiology_factory(athlete_id=athlete.id)
        p2 = _physiology_factory(athlete_id=athlete.id)
        db_session.add_all([p1, p2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# NOT NULL constraints.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyNotNullConstraintsDB:
    """``lt1`` and ``lt2`` are NOT NULL JSONB.

    SQLAlchemy converts Python ``None`` to JSON ``null`` (a valid
    JSON value, stored as ``'null'::jsonb``) for JSONB columns —
    NOT to SQL ``NULL``. The ``NOT NULL`` constraint only fires on
    SQL ``NULL``. To exercise the constraint reliably we issue a
    raw ``INSERT`` with a literal ``NULL`` for the column under
    test, then assert the resulting ``IntegrityError``.
    """

    async def test_missing_lt1_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "phys-no-lt1@example.com"
        )
        # Raw INSERT with literal SQL NULL for ``lt1`` — bypasses
        # the JSONB ``None → JSON null`` mapping. The other JSONB
        # column carries a valid JSON value so the only constraint
        # under test is the NOT NULL on ``lt1``.
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    """
                    INSERT INTO athlete_physiology
                        (id, athlete_id, lt1, lt2, updated_at)
                    VALUES
                        (gen_random_uuid(), :athlete_id,
                         NULL, :lt2_value, now())
                    """
                ),
                {
                    "athlete_id": athlete.id,
                    "lt2_value": json.dumps(
                        {"hr": None, "power": None, "pace": None}
                    ),
                },
            )
        await db_session.rollback()

    async def test_missing_lt2_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "phys-no-lt2@example.com"
        )
        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    """
                    INSERT INTO athlete_physiology
                        (id, athlete_id, lt1, lt2, updated_at)
                    VALUES
                        (gen_random_uuid(), :athlete_id,
                         :lt1_value, NULL, now())
                    """
                ),
                {
                    "athlete_id": athlete.id,
                    "lt1_value": json.dumps(
                        {"hr": None, "power": None, "pace": None}
                    ),
                },
            )
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Nullable optional columns.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyNullableOptionalColumnsDB:
    """``cp``, ``vo2max``, ``max_hr`` are nullable JSONB."""

    async def test_minimal_row_with_only_lt1_lt2_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "phys-minimal@example.com"
        )
        row = AthletePhysiology(
            athlete_id=athlete.id,
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
            cp=None,
            vo2max=None,
            max_hr=None,
        )
        db_session.add(row)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.id is not None
        assert row.cp is None
        assert row.vo2max is None
        assert row.max_hr is None

    async def test_max_hr_only_persists(
        self, db_session: AsyncSession
    ) -> None:
        """The bootstrapped 220-age path: only ``max_hr`` populated,
        cp / vo2max still null."""
        athlete = await make_athlete(
            db_session, "phys-max-hr-only@example.com"
        )
        row = _physiology_factory(
            athlete_id=athlete.id,
            max_hr={
                "value": 190.0,
                "uncertainty": 2.0,
                "prior_weight": 0.5,
                "dominant_source": "questionnaire_estimate",
                "last_observation_date": "2026-06-24",
            },
        )
        db_session.add(row)
        await db_session.flush()
        await db_session.refresh(row)
        assert row.max_hr is not None
        assert row.max_hr["value"] == 190.0


# ---------------------------------------------------------------------------
# Foreign key cascade.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyForeignKeyCascadeDB:
    def test_athlete_id_fk_to_athletes(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk
            for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks, (
            "athlete_physiology.athlete_id must reference athletes(id)."
        )

    def test_ondelete_is_cascade_in_pg_catalog(self) -> None:
        fks = db_foreign_keys(TABLE)
        athlete_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ())
            == ("athlete_id",)
        ]
        assert athlete_fks, (
            "athlete_physiology.athlete_id FK must reference athletes(id)."
        )
        assert athlete_fks[0].get("options", {}).get("ondelete") == "CASCADE", (
            "athlete_physiology.athlete_id FK ON DELETE must be CASCADE."
        )


# ---------------------------------------------------------------------------
# Mutability — service-layer writes succeed.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyMutabilityDB:
    """AthletePhysiology is MUTABLE — the Phase-1.6 service layer
    updates posterior estimates in place. The schema must permit
    UPDATE."""

    async def test_update_lt1_succeeds(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "phys-update@example.com"
        )
        row = _physiology_factory(athlete_id=athlete.id)
        db_session.add(row)
        await db_session.flush()

        # Posterior update — replaces the lt1 JSONB value.
        new_lt1 = {
            "hr": {
                "value": 155.0,
                "uncertainty": 4.0,
                "prior_weight": 0.8,
                "dominant_source": "training_hr_deflection",
                "last_observation_date": "2026-06-25",
            },
            "power": None,
            "pace": None,
        }
        row.lt1 = new_lt1
        await db_session.flush()
        await db_session.refresh(row)
        assert row.lt1 == new_lt1
        assert row.lt1["hr"]["value"] == 155.0
        assert row.lt1["hr"]["dominant_source"] == "training_hr_deflection"

    async def test_populate_cp_later(
        self, db_session: AsyncSession
    ) -> None:
        """cp is null until a qualifying observation; populating
        it later must succeed (service layer concern)."""
        athlete = await make_athlete(
            db_session, "phys-populate-cp@example.com"
        )
        row = _physiology_factory(athlete_id=athlete.id, cp=None)
        db_session.add(row)
        await db_session.flush()
        assert row.cp is None

        row.cp = {
            "value": 280.0,
            "uncertainty": 12.0,
            "prior_weight": 0.7,
            "dominant_source": "training_power_hr_ratio",
            "last_observation_date": "2026-06-25",
        }
        await db_session.flush()
        await db_session.refresh(row)
        assert row.cp is not None
        assert row.cp["value"] == 280.0


# ---------------------------------------------------------------------------
# Round-trip persistence.
# ---------------------------------------------------------------------------


class TestAthletePhysiologyRoundTripDB:
    async def test_full_physiology_row_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(
            db_session, "phys-roundtrip@example.com"
        )
        row = _physiology_factory(
            athlete_id=athlete.id,
            cp={
                "value": 285.0,
                "uncertainty": 10.0,
                "prior_weight": 0.7,
                "dominant_source": "training_power_hr_ratio",
                "last_observation_date": "2026-06-24",
            },
            vo2max={
                "ml_kg_min": 58.0,
                "power": 380.0,
            },
            max_hr={
                "value": 192.0,
                "uncertainty": 2.0,
                "prior_weight": 0.5,
                "dominant_source": "questionnaire_estimate",
                "last_observation_date": "2026-06-24",
            },
        )
        db_session.add(row)
        await db_session.flush()
        row_id = row.id

        from sqlalchemy import select

        result = await db_session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.id == row_id
            )
        )
        loaded = result.scalar_one()
        assert loaded.cp is not None and loaded.cp["value"] == 285.0
        assert loaded.vo2max is not None
        assert loaded.vo2max["ml_kg_min"] == 58.0
        assert loaded.max_hr is not None and loaded.max_hr["value"] == 192.0