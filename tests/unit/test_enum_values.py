"""Unit tests for the Phase-1.2a enum contracts.

These are pure-Python tests that lock down the closed ontologies used by
``AthleteProfile``, ``AthletePreferences``, and ``Activity``. The values
are public contract: changing them is a breaking change for downstream
services (Tier inference, plan generation, deduplication, INGEST
pipelines).

Anything outside these tests asserting "the values are what we typed"
duplicates this contract; this module is the single source of truth
for enum membership and ordering.

Plan reference: docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
Architecture:

* docs/architecture/00-foundations/terminology.md (closed ontologies)
* docs/architecture/01-entities/athlete-profile.md (Sex)
* docs/architecture/01-entities/activity.md (ActivitySource)
* docs/architecture/00-foundations/data-tiers.md (DataTier)
* docs/architecture/01-entities/athlete-preferences.md (preference enums)
"""

from __future__ import annotations

import pytest

from app.models.enums import (
    ActivitySource,
    DataTier,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    Sex,
    SportBackground,
    TrainingTimeOfDay,
)


# ---------------------------------------------------------------------------
# Sex — Phase-1.1 contract must remain stable (registration writes this).
# ---------------------------------------------------------------------------


class TestSexContract:
    """Sex membership is part of the Phase-1.1 registration contract;
    Phase-1.2a must not break it."""

    def test_sex_has_exactly_three_values(self) -> None:
        assert {member.value for member in Sex} == {
            "male",
            "female",
            "not_specified",
        }

    def test_sex_values_are_lowercase_strings(self) -> None:
        for member in Sex:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()


# ---------------------------------------------------------------------------
# ActivitySource — Phase-1.2a closed ontology.
# ---------------------------------------------------------------------------


class TestActivitySourceContract:
    """``ActivitySource`` is the ingestion-source enum. ``manual_entry``
    is the ONLY source allowed to omit ``fit_file_key`` and load scores."""

    def test_activity_source_has_exactly_four_values(self) -> None:
        assert {member.value for member in ActivitySource} == {
            "intervals_icu",
            "manual_upload",
            "garmin_direct",
            "manual_entry",
        }

    def test_activity_source_values_are_lowercase_strings(self) -> None:
        for member in ActivitySource:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()

    def test_activity_source_includes_manual_entry(self) -> None:
        """``manual_entry`` is the Tier 6 path with no FIT file requirement."""
        assert ActivitySource.MANUAL_ENTRY.value == "manual_entry"

    def test_activity_source_excludes_multi_sport_sources(self) -> None:
        """Anti-goal: no cycling/swimming/etc. as ActivitySource."""
        forbidden = {
            "cycling",
            "swimming",
            "kayaking",
            "strength",
            "rowing",
            "elliptical",
        }
        actual = {member.value for member in ActivitySource}
        assert actual.isdisjoint(forbidden)


# ---------------------------------------------------------------------------
# DataTier — six-tier hardware classification.
# ---------------------------------------------------------------------------


class TestDataTierContract:
    """DataTier is an int enum with values 1..6 exactly. Order matters
    for the inference algorithm and downstream threshold detection."""

    def test_data_tier_has_exactly_six_values(self) -> None:
        assert {member.value for member in DataTier} == {1, 2, 3, 4, 5, 6}

    def test_data_tier_values_are_integers(self) -> None:
        for member in DataTier:
            assert isinstance(member.value, int)
            assert not isinstance(member.value, bool)

    def test_data_tier_ordered_low_to_high(self) -> None:
        ordered = sorted([member.value for member in DataTier])
        assert ordered == [1, 2, 3, 4, 5, 6]


# ---------------------------------------------------------------------------
# AthletePreferences enums — closed ontologies for hardware/platform config.
# ---------------------------------------------------------------------------


class TestSportBackgroundContract:
    """``running_primary`` is canonical; any other value marks crossover."""

    def test_sport_background_includes_running_primary(self) -> None:
        assert SportBackground.RUNNING_PRIMARY.value == "running_primary"

    def test_sport_background_values_are_lowercase_strings_or_none(self) -> None:
        for member in SportBackground:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()

    def test_sport_background_count(self) -> None:
        """Closed ontology: sensible coverage without bloat."""
        assert len(list(SportBackground)) == 7


class TestTrainingTimeOfDayContract:
    def test_training_time_of_day_values(self) -> None:
        assert {m.value for m in TrainingTimeOfDay} == {
            "morning",
            "afternoon",
            "evening",
            "variable",
        }


class TestGpsSourceContract:
    def test_gps_source_values(self) -> None:
        assert {m.value for m in GpsSource} == {
            "garmin_watch",
            "apple_watch",
            "polar",
            "suunto",
            "coros",
            "other",
        }


class TestHrSourceContract:
    """``HrSource`` is the primary input for data-tier inference."""

    def test_hr_source_includes_chest_strap_rr(self) -> None:
        assert HrSource.CHEST_STRAP_RR.value == "chest_strap_rr"

    def test_hr_source_includes_none(self) -> None:
        """``HrSource.NONE`` is the Tier 5 path (no HR at all)."""
        assert HrSource.NONE.value == "none"

    def test_hr_source_value_count(self) -> None:
        assert len(list(HrSource)) == 4


class TestPowerSourceContract:
    def test_power_source_values(self) -> None:
        assert {m.value for m in PowerSource} == {
            "running_power_meter",
            "none",
        }


class TestPrimaryTrainingPlatformContract:
    def test_primary_training_platform_values(self) -> None:
        assert {m.value for m in PrimaryTrainingPlatform} == {
            "intervals_icu",
            "garmin_connect",
            "manual",
        }


# ---------------------------------------------------------------------------
# Enum registrations — every model-level enum must be re-exported from
# ``app.models.__init__`` so Alembic autogenerate discovers them.
# ---------------------------------------------------------------------------


class TestEnumReExports:
    """Every model-level enum must be re-exported from
    ``app.models.__init__`` so Alembic autogenerate discovers them."""

    @pytest.mark.parametrize(
        "enum_class_name",
        [
            "ActivitySource",
            "DataTier",
            "Sex",
            "GpsSource",
            "HrSource",
            "PowerSource",
            "PrimaryTrainingPlatform",
            "SportBackground",
            "TrainingTimeOfDay",
        ],
    )
    def test_enum_is_exported_from_models_package(
        self, enum_class_name: str
    ) -> None:
        """Without the ``app.models`` import, Alembic autogen sees a
        smaller metadata and may emit ``DROP``/``CREATE`` rather than
        ``ALTER`` for the new ENUM types."""
        # Late import: keep module import surface cheap and avoid
        # side-effects at collection time.
        from app.models import (  # noqa: PLC0415
            ActivitySource,
            DataTier,
            GpsSource,
            HrSource,
            PowerSource,
            PrimaryTrainingPlatform,
            Sex,
            SportBackground,
            TrainingTimeOfDay,
        )

        enum_map = {
            "ActivitySource": ActivitySource,
            "DataTier": DataTier,
            "GpsSource": GpsSource,
            "HrSource": HrSource,
            "PowerSource": PowerSource,
            "PrimaryTrainingPlatform": PrimaryTrainingPlatform,
            "Sex": Sex,
            "SportBackground": SportBackground,
            "TrainingTimeOfDay": TrainingTimeOfDay,
        }
        expected = enum_map[enum_class_name]
        import app.models as models_pkg  # noqa: PLC0415

        assert hasattr(models_pkg, enum_class_name)
        assert getattr(models_pkg, enum_class_name) is expected
