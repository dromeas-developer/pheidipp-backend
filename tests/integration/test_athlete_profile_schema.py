"""Integration tests for the ``AthleteProfile`` schema at the DB level.

Phase-1.2a extends the existing Phase-1.1 ``athlete_profiles`` table.
These tests inspect the live database via SQLAlchemy's ``Inspector``
and assert:

* Every Phase-1.2a column physically exists on the table.
* The Phase-1.1 unique constraint on ``athlete_id`` is still enforced.
* Existing Phase-1.1 inserts (minimal profile rows) continue to work
  — onboarding enrichment is intentionally nullable.
* Extended columns can be populated in any subset and persisted; the
  DB is flexible enough to host partial profiles during onboarding.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.models.enums import Sex
from tests.utils.schema_helpers import db_columns, db_unique_constraints


TABLE = "athlete_profiles"


class TestAthleteProfileDBSchemaColumns:
    """The DB physically carries every Phase-1.2a column."""

    @pytest.mark.parametrize(
        "expected_column",
        [
            # Phase-1.1 preserved
            "id",
            "athlete_id",
            "date_of_birth",
            "sex",
            "height_cm",
            "updated_at",
            # Phase-1.2a additions
            "gap_curve_model",
            "weather_response_model",
            "banister_constants",
            "cycle_personal_model",
            "location_lat",
            "location_lng",
            "timezone",
            "training_window",
            "current_effort_generation",
            "structural_risk_flag",
            "objective_thresholds",
        ],
    )
    async def test_required_column_present_on_table(
        self,
        db_session: AsyncSession,
        expected_column: str,
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"athlete_profiles.{expected_column} must exist on the DB. "
            f"Missing after Phase-1.2a migration."
        )


class TestAthleteProfileUniqueConstraintPreserved:
    """Phase-1.1 invariant: one AthleteProfile per Athlete."""

    async def test_athlete_id_is_uniquely_constrained(
        self, db_session: AsyncSession
    ) -> None:
        """``athlete_id`` must appear in a unique-constraint group
        (a single-column ``UniqueConstraint`` or an inline
        ``unique=True`` on the column)."""
        # Table-level UniqueConstraint discovered via Inspector.
        table_level = any(
            tuple(uc["column_names"]) == ("athlete_id",)
            for uc in db_unique_constraints(TABLE)
        )
        # Column-level ``unique=True`` (which SQLAlchemy renders as a
        # UNIQUE constraint too, but Inspector sometimes reports it on
        # the column description rather than as a separate ``info``).
        column_level = any(
            col.get("unique") is True
            for col in db_columns(TABLE)
            if col["name"] == "athlete_id"
        )
        assert table_level or column_level, (
            "athlete_profiles.athlete_id must be uniquely constrained "
            "(Phase-1.1 invariant — preserved by Phase-1.2a)."
        )

    async def test_duplicate_profile_rejected_for_same_athlete(
        self, db_session: AsyncSession
    ) -> None:
        """Two profiles for the same athlete must raise a uniqueness
        violation at the DB level."""
        athlete = Athlete(email="dup-profile@example.com")
        db_session.add(athlete)
        await db_session.flush()

        profile_a = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
        )
        profile_b = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
        )
        db_session.add_all([profile_a, profile_b])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestAthleteProfileMinimalInsertWorks:
    """Phase-1.1 minimal registration must still produce a valid
    profile — onboarding-enrichment columns remain NULL."""

    async def test_minimal_profile_persists_without_phase_12a_columns(
        self, db_session: AsyncSession
    ) -> None:
        """A Phase-1.1 registration produces a profile with only
        ``date_of_birth`` / ``sex`` / ``height_cm`` populated. All
        Phase-1.2a columns must be nullable AND persistable as None.
        """
        athlete = Athlete(email="minimal@example.com")
        db_session.add(athlete)
        await db_session.flush()

        profile = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
            height_cm=180.0,
        )
        db_session.add(profile)
        await db_session.flush()

        # Re-read — flush may not have materialised all defaults.
        await db_session.refresh(profile)

        assert profile.id is not None
        assert profile.gap_curve_model is None
        assert profile.weather_response_model is None
        assert profile.banister_constants is None
        assert profile.cycle_personal_model is None
        assert profile.location_lat is None
        assert profile.location_lng is None
        assert profile.timezone is None
        assert profile.training_window is None
        assert profile.current_effort_generation is None
        assert profile.structural_risk_flag is None
        assert profile.objective_thresholds is None
        assert profile.updated_at is not None


class TestAthleteProfilePartialOnboardingPersistable:
    """Onboarding is incremental. Each subset must be persistable; the
    schema must not force any single enrichment column."""

    async def test_persisting_timezone_only_enrichment(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="tz-only@example.com")
        db_session.add(athlete)
        await db_session.flush()
        profile = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
            timezone="Europe/Lisbon",
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)
        assert profile.timezone == "Europe/Lisbon"

    async def test_persisting_location_only_enrichment(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="loc-only@example.com")
        db_session.add(athlete)
        await db_session.flush()
        profile = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
            location_lat=38.7223,
            location_lng=-9.1393,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)
        assert float(profile.location_lat) == pytest.approx(38.7223)
        assert float(profile.location_lng) == pytest.approx(-9.1393)

    async def test_persisting_personalisation_jsonb_only(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="gap-only@example.com")
        db_session.add(athlete)
        await db_session.flush()
        gap_curve = {
            "formula": "per_athlete_v1",
            "coefficients": {"a": 12.5, "b": -0.13},
            "fitted_from_sessions": 22,
            "fitted_at": "2026-06-19T10:00:00Z",
            "r_squared": 0.81,
        }
        profile = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
            gap_curve_model=gap_curve,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        assert profile.gap_curve_model == gap_curve

    async def test_structural_risk_flag_persists_as_true(
        self, db_session: AsyncSession
    ) -> None:
        """``structural_risk_flag = true`` is set by onboarding for
        crossover athletes (sport_background != running_primary)."""
        athlete = Athlete(email="crossover@example.com")
        db_session.add(athlete)
        await db_session.flush()
        profile = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.NOT_SPECIFIED,
            structural_risk_flag=True,
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)
        assert profile.structural_risk_flag is True


class TestAthleteProfileSchemaNotDropped:
    """Defence-in-depth: ensure the Phase-1.1 table was extended, not
    re-created. If a downgrade ever miscreases this, the migration
    regresses existing rows. We can't easily check rows here (each test
    starts clean), but we CAN assert against ID/UUID type continuity.
    """

    async def test_id_column_type_is_uuid(self, db_session: AsyncSession) -> None:
        """``id`` is a UUID PK. Phase-1.1 used the same type; if a
        recreate swapped it to BIGINT we'd see a migration in the
        diff and break every existing row reference."""
        columns = {
            col["name"]: col for col in db_columns(TABLE)
        }
        id_col = columns["id"]
        # Postgres stores UUID type as ``uuid``. The Inspector
        # surfaces it as ``UUID`` (case varies).
        assert id_col["type"].__class__.__name__.upper() in {"UUID", "PG_UUID"}
