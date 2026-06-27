"""Integration tests for the ``AthletePreferences`` schema at the DB level.

Phase-1.2a introduces a new ``athlete_preferences`` table with:

* One-to-one ``athlete_id`` uniqueness (DB-enforced).
* DB-level CHECK constraint ``years_structured_training >= 0``.
* Structured JSONB ``weekly_schedule``.
* Enum-backed hardware and platform columns.

These tests verify the DB enforces every documented invariant.

Reference plan:
docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_preferences import AthletePreferences
from app.models.enums import (
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
    TrainingTimeOfDay,
)
from tests.utils.schema_helpers import db_columns, db_unique_constraints, db_check_constraints


TABLE = "athlete_preferences"


def _valid_weekly_schedule() -> dict:
    """Return a representative weekly-schedule payload."""
    return {
        "monday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "tuesday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "wednesday": {
            "available": True,
            "max_hours": 2.0,
            "long_workout": False,
            "doubles_eligible": True,
        },
        "thursday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "friday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "saturday": {
            "available": True,
            "max_hours": 3.0,
            "long_workout": True,
            "doubles_eligible": False,
        },
        "sunday": {
            "available": True,
            "max_hours": 1.0,
            "long_workout": False,
            "doubles_eligible": False,
        },
    }


class TestAthletePreferencesDBSchemaColumns:
    """The DB carries every Phase-1.2a column."""

    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "sport_background",
            "years_structured_training",
            "training_time_of_day",
            "weekly_schedule",
            "gps_source",
            "hr_source",
            "power_source",
            "primary_training_platform",
            "updated_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"athlete_preferences.{expected_column} missing from DB schema. "
            f"Phase-1.2a migration must add it."
        )


class TestAthletePreferencesUniqueness:
    """Phase-1.2a invariant: one AthletePreferences per Athlete."""

    async def test_athlete_id_unique_constraint_present(
        self, db_session: AsyncSession
    ) -> None:
        uniques = db_unique_constraints(TABLE)
        # The constraint may live on the column itself (``unique=True``
        # in the mapper) rather than as a separate UniqueConstraint
        # clause. Both forms are acceptable; we need at least one.
        has_table_constraint = any(
            tuple(constraint["column_names"]) == ("athlete_id",)
            for constraint in uniques
        )
        has_column_level_unique = any(
            col.get("unique") is True
            for col in db_columns(TABLE)
            if col["name"] == "athlete_id"
        )
        assert has_table_constraint or has_column_level_unique, (
            "athlete_preferences.athlete_id must be uniquely "
            "constrained (one preferences row per athlete)."
        )

    async def test_duplicate_preferences_rejected_for_same_athlete(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="dup-prefs@example.com")
        db_session.add(athlete)
        await db_session.flush()

        schedule = _valid_weekly_schedule()
        prefs_a = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=2,
            training_time_of_day=TrainingTimeOfDay.MORNING,
            weekly_schedule=schedule,
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        prefs_b = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.CYCLING,
            years_structured_training=5,
            training_time_of_day=TrainingTimeOfDay.EVENING,
            weekly_schedule=schedule,
            gps_source=GpsSource.APPLE_WATCH,
            hr_source=HrSource.WRIST_OPTICAL,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        db_session.add_all([prefs_a, prefs_b])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestYearsStructuredTrainingNonNegative:
    """Architecture invariant: ``years_structured_training >= 0``. This
    is enforced both at the model level (Integer) and at the DB level
    via ``CheckConstraint``."""

    async def test_db_check_constraint_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        # Look for a check whose SQL expression mentions the column
        # and 0.
        found = []
        for c in checks:
            sqltext = (c.get("sqltext") or "").lower()
            if "years_structured_training" in sqltext and ">= 0" in sqltext:
                found.append(c["name"])
        assert found, (
            "athlete_preferences must have a CHECK constraint "
            "`years_structured_training >= 0`. Missing from DB schema."
        )

    async def test_db_check_constraint_rejects_negative_value(
        self, db_session: AsyncSession
    ) -> None:
        """At the DB level, a negative ``years_structured_training``
        must fail with a check-violation IntegrityError."""
        athlete = Athlete(email="neg-years@example.com")
        db_session.add(athlete)
        await db_session.flush()

        schedule = _valid_weekly_schedule()
        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=-1,  # forced via Python to bypass ORM check
            training_time_of_day=TrainingTimeOfDay.MORNING,
            weekly_schedule=schedule,
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        db_session.add(prefs)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_zero_years_structured_training_accepted(
        self, db_session: AsyncSession
    ) -> None:
        """``0`` must satisfy the constraint — this boundary case is a
        common regression."""
        athlete = Athlete(email="zero-years@example.com")
        db_session.add(athlete)
        await db_session.flush()

        schedule = _valid_weekly_schedule()
        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.NONE,
            years_structured_training=0,
            training_time_of_day=TrainingTimeOfDay.AFTERNOON,
            weekly_schedule=schedule,
            gps_source=GpsSource.OTHER,
            hr_source=HrSource.WRIST_OPTICAL,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        db_session.add(prefs)
        await db_session.flush()
        await db_session.refresh(prefs)
        assert prefs.years_structured_training == 0


class TestAthletePreferencesPersistence:
    """A happy-path insert persists every required field."""

    async def test_persists_full_preferences_row(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="full-prefs@example.com")
        db_session.add(athlete)
        await db_session.flush()

        schedule = _valid_weekly_schedule()
        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=4,
            training_time_of_day=TrainingTimeOfDay.MORNING,
            weekly_schedule=schedule,
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.INTERVALS_ICU,
        )
        db_session.add(prefs)
        await db_session.flush()
        await db_session.refresh(prefs)

        assert prefs.id is not None
        assert prefs.sport_background is SportBackground.RUNNING_PRIMARY
        assert prefs.training_time_of_day is TrainingTimeOfDay.MORNING
        assert prefs.weekly_schedule == schedule
        assert prefs.gps_source is GpsSource.GARMIN_WATCH
        assert prefs.hr_source is HrSource.CHEST_STRAP_RR
        assert prefs.power_source is PowerSource.NONE
        assert (
            prefs.primary_training_platform
            is PrimaryTrainingPlatform.INTERVALS_ICU
        )

    async def test_weekly_schedule_stored_structure_preserved(
        self, db_session: AsyncSession
    ) -> None:
        """JSONB round-trip — the ``long_workout`` and ``doubles_eligible``
        flags (which gate plan generation) must survive persistence."""
        athlete = Athlete(email="schedule@example.com")
        db_session.add(athlete)
        await db_session.flush()

        schedule = _valid_weekly_schedule()
        schedule["saturday"]["long_workout"] = True
        schedule["wednesday"]["doubles_eligible"] = True

        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=3,
            training_time_of_day=TrainingTimeOfDay.EVENING,
            weekly_schedule=schedule,
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        db_session.add(prefs)
        await db_session.flush()
        await db_session.refresh(prefs)

        assert prefs.weekly_schedule["saturday"]["long_workout"] is True
        assert prefs.weekly_schedule["wednesday"]["doubles_eligible"] is True
        # Defensive — the ``available`` and ``max_hours`` keys feed the
        # session distribution in plan generation.
        assert prefs.weekly_schedule["monday"]["available"] is True
        assert prefs.weekly_schedule["monday"]["max_hours"] == 1.5
