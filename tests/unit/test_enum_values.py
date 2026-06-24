"""Unit tests for the Phase-1.1, Phase-1.2a, and Phase-1.2b enum contracts.

These are pure-Python tests that lock down the closed ontologies used
across the schema. The values are public contract: changing them is a
breaking change for downstream services (data-tier inference, plan
generation, weekly synthesis, workout generation, deduplication,
INGEST pipelines).

Anything outside these tests asserting "the values are what we typed"
duplicates this contract; this module is the single source of truth
for enum membership and ordering.

Plan reference:

* Phase-1.1: docs/implementation/phase-1/phase-1-1-p1-email-password-auth.md
* Phase-1.2a: docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md
* Phase-1.2b: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md

Architecture:

* docs/architecture/00-foundations/terminology.md (closed ontologies)
* docs/architecture/01-entities/athlete-profile.md (Sex)
* docs/architecture/01-entities/activity.md (ActivitySource)
* docs/architecture/00-foundations/data-tiers.md (DataTier)
* docs/architecture/01-entities/athlete-preferences.md (preference enums)
* docs/architecture/01-entities/training-goal.md (GoalType, GoalEventType, TrainingGoalStatus, InjurySeverity, SecondaryEventPriority)
* docs/architecture/01-entities/training-plan.md (TrainingPlanStatus)
* docs/architecture/01-entities/weekly-plan.md (SessionType, WeeklyPlanStatus)
* docs/architecture/01-entities/planned-session.md (SessionSlot, SessionPriority, PlannedSessionStatus)
* docs/architecture/01-entities/checkpoint.md (CheckpointType, CheckpointStatus, PhaseLabel)
* docs/architecture/00-foundations/objectives.md (ObjectiveCategory)
"""

from __future__ import annotations

import pytest

from app.models.enums import (
    ActivitySource,
    CheckpointStatus,
    CheckpointType,
    DataTier,
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    InjurySeverity,
    ObjectiveCategory,
    PhaseLabel,
    PlannedSessionStatus,
    PowerSource,
    PrimaryTrainingPlatform,
    SecondaryEventPriority,
    SessionPriority,
    SessionSlot,
    SessionType,
    Sex,
    SportBackground,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TrainingTimeOfDay,
    WeeklyPlanStatus,
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
            # Phase-1.1 / Phase-1.2a enums
            "ActivitySource",
            "DataTier",
            "Sex",
            "GpsSource",
            "HrSource",
            "PowerSource",
            "PrimaryTrainingPlatform",
            "SportBackground",
            "TrainingTimeOfDay",
            # Phase-1.2b enums — must be discoverable by Alembic autogen.
            "GoalType",
            "GoalEventType",
            "TrainingGoalStatus",
            "InjurySeverity",
            "SecondaryEventPriority",
            "TrainingPlanStatus",
            "PhaseLabel",
            "SessionType",
            "SessionSlot",
            "SessionPriority",
            "PlannedSessionStatus",
            "WeeklyPlanStatus",
            "CheckpointType",
            "CheckpointStatus",
            "ObjectiveCategory",
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
        import app.models as models_pkg  # noqa: PLC0415

        assert hasattr(models_pkg, enum_class_name), (
            f"`{enum_class_name}` must be re-exported from "
            f"`app.models.__init__` — Alembic autogen will otherwise "
            "miss the enum and emit DROP/CREATE rather than ALTER."
        )

        from app.models.enums import (  # noqa: PLC0415
            CheckpointStatus,
            CheckpointType,
            GoalEventType,
            GoalType,
            InjurySeverity,
            ObjectiveCategory,
            PhaseLabel,
            PlannedSessionStatus,
            SecondaryEventPriority,
            SessionPriority,
            SessionSlot,
            SessionType,
            TrainingGoalStatus,
            TrainingPlanStatus,
            WeeklyPlanStatus,
        )

        enum_map = {
            "CheckpointStatus": CheckpointStatus,
            "CheckpointType": CheckpointType,
            "GoalEventType": GoalEventType,
            "GoalType": GoalType,
            "InjurySeverity": InjurySeverity,
            "ObjectiveCategory": ObjectiveCategory,
            "PhaseLabel": PhaseLabel,
            "PlannedSessionStatus": PlannedSessionStatus,
            "SecondaryEventPriority": SecondaryEventPriority,
            "SessionPriority": SessionPriority,
            "SessionSlot": SessionSlot,
            "SessionType": SessionType,
            "TrainingGoalStatus": TrainingGoalStatus,
            "TrainingPlanStatus": TrainingPlanStatus,
            "WeeklyPlanStatus": WeeklyPlanStatus,
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
        assert getattr(models_pkg, enum_class_name) is expected


# ---------------------------------------------------------------------------
# Phase-1.2b — Plan / Session / Checkpoint enum contracts.
#
# These values are part of the public architecture. Changing them is a
# breaking change for plan generation, weekly synthesis, and session
# lifecycle services (Phase 1.4, 1.5, 4). The tests below pin the exact
# closed ontology declared in
# docs/architecture/00-foundations/terminology.md and
# docs/architecture/01-entities/{training-goal,training-plan,
# weekly-plan,planned-session,checkpoint}.md.
# ---------------------------------------------------------------------------


class TestGoalTypeContract:
    """``GoalType`` drives coaching posture — race_event,
    target_performance, fitness_improvement, maintenance, recovery.
    Closed ontology: no aliases."""

    def test_goal_type_has_exactly_five_values(self) -> None:
        assert {member.value for member in GoalType} == {
            "race_event",
            "target_performance",
            "fitness_improvement",
            "maintenance",
            "recovery",
        }

    def test_goal_type_values_are_lowercase_strings(self) -> None:
        for member in GoalType:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower()

    def test_goal_type_includes_recovery(self) -> None:
        """``recovery`` requires the InjurySeverity closed ontology
        on ``TrainingGoal.injury_severity``."""
        assert GoalType.RECOVERY.value == "recovery"


class TestGoalEventTypeContract:
    """``GoalEventType`` is reused on ``SecondaryEvent`` — both
    primary race and B/C-race routing share the same enum."""

    def test_goal_event_type_has_expected_values(self) -> None:
        assert {member.value for member in GoalEventType} == {
            "marathon",
            "half_marathon",
            "10k",
            "5k",
            "ultra",
            "trail_race",
            "custom",
        }

    def test_goal_event_type_includes_custom(self) -> None:
        """``custom`` requires ``custom_distance_km`` to be set."""
        assert GoalEventType.CUSTOM.value == "custom"

    def test_goal_event_type_values_are_lowercase_or_alphanumeric(self) -> None:
        for member in GoalEventType:
            assert isinstance(member.value, str)
            assert member.value == member.value.lower(), (
                f"GoalEventType.{member.name} value {member.value!r} "
                "must be lowercase."
            )


class TestTrainingGoalStatusContract:
    """``TrainingGoalStatus`` enforces "one active per athlete" via
    a partial unique index — must include active, completed, abandoned."""

    def test_training_goal_status_values(self) -> None:
        assert {member.value for member in TrainingGoalStatus} == {
            "active",
            "completed",
            "abandoned",
        }

    def test_training_goal_status_active_value(self) -> None:
        assert TrainingGoalStatus.ACTIVE.value == "active"


class TestInjurySeverityContract:
    """``InjurySeverity`` required on ``TrainingGoal.injury_severity``
    when ``goal_type = 'recovery'``. Closed ontology: minor, moderate,
    major."""

    def test_injury_severity_values(self) -> None:
        assert {member.value for member in InjurySeverity} == {
            "minor",
            "moderate",
            "major",
        }

    def test_injury_severity_count(self) -> None:
        assert len(list(InjurySeverity)) == 3


class TestSecondaryEventPriorityContract:
    """``SecondaryEventPriority`` distinguishes B-races from C-races.
    The set is ``{B, C}`` exactly — no other letter classes."""

    def test_secondary_event_priority_values(self) -> None:
        assert {member.value for member in SecondaryEventPriority} == {
            "B",
            "C",
        }

    def test_only_two_priority_levels(self) -> None:
        """Anti-goal: no "D", "E", "A_minus" levels sneak in."""
        assert len(list(SecondaryEventPriority)) == 2


class TestTrainingPlanStatusContract:
    """Old plans transition to ``superseded`` rather than being
    deleted. ``completed`` is reserved for plans that ran their
    full duration without being replaced."""

    def test_training_plan_status_values(self) -> None:
        assert {member.value for member in TrainingPlanStatus} == {
            "active",
            "superseded",
            "completed",
        }

    def test_training_plan_status_has_exactly_three_values(self) -> None:
        assert len(list(TrainingPlanStatus)) == 3


class TestPhaseLabelContract:
    """Closed ontology of methodology-specific phase labels. Canonical
    labels are the primary values; legacy aliases (base_building,
    threshold_development, race_specific) are mapped to canonical
    labels by the deterministic expansion layer."""

    def test_phase_label_includes_canonical_labels(self) -> None:
        canonical = {
            "aerobic_base",
            "aerobic_foundation",
            "aerobic_accumulation",
            "aerobic_build",
            "hill_phase",
            "structural_tolerance",
            "threshold_build",
            "threshold_peak",
            "threshold_consolidation",
            "vo2max_development",
            "vo2max_sharpening",
            "special_endurance",
            "specific_endurance",
            "race_rehearsal",
            "sharpening",
            "taper",
            "race_week",
            "recovery",
            "transition",
            "rolling_block",
        }
        actual = {member.value for member in PhaseLabel}
        assert canonical.issubset(actual), (
            f"PhaseLabel missing canonical labels: {canonical - actual}"
        )

    def test_phase_label_includes_legacy_aliases(self) -> None:
        """Legacy aliases map to canonical labels by the deterministic
        expansion layer per terminology.md."""
        assert PhaseLabel.BASE_BUILDING.value == "base_building"
        assert PhaseLabel.THRESHOLD_DEVELOPMENT.value == "threshold_development"
        assert PhaseLabel.RACE_SPECIFIC.value == "race_specific"

    def test_phase_label_value_count(self) -> None:
        """20 canonical + 3 legacy aliases = 23."""
        assert len(list(PhaseLabel)) == 23


class TestSessionTypeContract:
    """16 session types — the concrete workout prescription shown
    on the calendar. ``race_specific`` is NOT a SessionType (it is
    a SessionPurpose)."""

    CANONICAL_VALUES = {
        "rest",
        "recovery_run",
        "easy_run",
        "long_run",
        "medium_long_run",
        "steady_state",
        "tempo",
        "threshold",
        "vo2max",
        "hill_repeats",
        "fartlek",
        "strides",
        "drills_mobility",
        "cross_training",
        "test_session",
        "optional_run",
    }

    def test_session_type_has_exactly_sixteen_values(self) -> None:
        assert {member.value for member in SessionType} == self.CANONICAL_VALUES

    def test_session_type_excludes_race_specific(self) -> None:
        """``race_specific`` is a SessionPurpose, NOT a SessionType.
        Mixing the two vocabularies corrupts the determinism rule
        that maps SessionType -> SessionIntent."""
        assert "race_specific" not in {member.value for member in SessionType}


class TestSessionSlotContract:
    """AM/PM session designation on double-day schedules. ``None``
    for single-session days."""

    def test_session_slot_values(self) -> None:
        assert {member.value for member in SessionSlot} == {"am", "pm"}

    def test_session_slot_count(self) -> None:
        assert len(list(SessionSlot)) == 2


class TestSessionPriorityContract:
    """Primary sessions receive full workout generation; secondary
    sessions may be suggested without detailed targets."""

    def test_session_priority_values(self) -> None:
        assert {member.value for member in SessionPriority} == {
            "primary",
            "secondary",
        }


class TestPlannedSessionStatusContract:
    """Lifecycle status of a ``PlannedSession`` once the workout
    generation pipeline has run."""

    def test_planned_session_status_values(self) -> None:
        assert {member.value for member in PlannedSessionStatus} == {
            "pending",
            "generated",
            "completed",
            "skipped",
            "missed",
            "redistributed",
        }

    def test_pending_status_exists(self) -> None:
        """``pending`` is the default state before workout generation."""
        assert PlannedSessionStatus.PENDING.value == "pending"


class TestWeeklyPlanStatusContract:
    """Lifecycle status of a ``WeeklyPlan``."""

    def test_weekly_plan_status_values(self) -> None:
        assert {member.value for member in WeeklyPlanStatus} == {
            "synthesised",
            "active",
            "completed",
        }


class TestCheckpointTypeContract:
    """Closed ontology of checkpoint categories."""

    def test_checkpoint_type_values(self) -> None:
        assert {member.value for member in CheckpointType} == {
            "calibration",
            "benchmark",
            "race_simulation",
            "secondary_race",
            "progress_review",
        }


class TestCheckpointStatusContract:
    """Lifecycle status of a ``Checkpoint``."""

    def test_checkpoint_status_values(self) -> None:
        assert {member.value for member in CheckpointStatus} == {
            "scheduled",
            "completed",
            "skipped",
        }


class TestObjectiveCategoryContract:
    """Shared objective taxonomy between phase definitions and
    athlete-facing coaching objectives."""

    def test_objective_category_values(self) -> None:
        assert {member.value for member in ObjectiveCategory} == {
            "aerobic_base",
            "threshold_quality",
            "pacing_discipline",
            "intensity_distribution",
            "structural_tolerance",
            "neuromuscular_sharpness",
            "durability",
            "intensity_compliance",
            "recovery_efficiency",
        }
