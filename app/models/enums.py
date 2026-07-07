"""Enumerations shared across models in the Athis architecture."""

from enum import Enum


class AuthProvider(str, Enum):
    """Authentication method used by a given AthleteAuth record."""

    EMAIL = "email"
    GOOGLE = "google"
    STRAVA = "strava"


class Sex(str, Enum):
    """Biological sex for demographic identity and cycle tracking."""

    MALE = "male"
    FEMALE = "female"
    NOT_SPECIFIED = "not_specified"


class ActivitySource(str, Enum):
    """Origin of an ``Activity`` record.

    Phase-1.2a contract.

    ``manual_entry`` is the only source allowed to omit ``fit_file_key``
    and load scores (Tier 6 invariant). See
    ``docs/architecture/01-entities/activity.md``.
    """

    INTERVALS_ICU = "intervals_icu"
    MANUAL_UPLOAD = "manual_upload"
    GARMIN_DIRECT = "garmin_direct"
    MANUAL_ENTRY = "manual_entry"


class DataTier(int, Enum):
    """Hardware capability tier of an athlete.

    Drives load computation and threshold detection capabilities. See
    ``docs/architecture/00-foundations/data-tiers.md``. Tier 6 is the
    fallback for athletes with no measurable signals (manual entry only).
    """

    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3
    TIER_4 = 4
    TIER_5 = 5
    TIER_6 = 6


class SportBackground(str, Enum):
    """Primary sport background for the athlete.

    Phase-1.2a contract for ``AthletePreferences``. ``running_primary`` is
    the canonical running-only path; any other value signals a
    crossover athlete and triggers the structural capacity ramp in
    plan generation.
    """

    RUNNING_PRIMARY = "running_primary"
    CYCLING_PRIMARY = "cycling_primary"
    SWIMMING_PRIMARY = "swimming_primary"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    TRIATHLON = "triathlon"
    TEAM_SPORT = "team_sport"
    GYM_FITNESS = "gym_fitness"
    NONE = "none"


class TrainingTimeOfDay(str, Enum):
    """Athlete's preferred training time window.

    Feeds the time-of-day modifier in ``WellnessModifierService``.
    """

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    VARIABLE = "variable"


class GpsSource(str, Enum):
    """GPS-capable device used by the athlete."""

    GARMIN_WATCH = "garmin_watch"
    APPLE_WATCH = "apple_watch"
    POLAR = "polar"
    SUUNTO = "suunto"
    COROS = "coros"
    OTHER = "other"


class HrSource(str, Enum):
    """Heart-rate source and quality.

    Primary input for data tier inference. See
    ``docs/architecture/00-foundations/data-tiers.md``.

    * ``chest_strap_rr`` enables RR intervals (Tier 1 or 3).
    * ``chest_strap_no_rr`` / ``wrist_optical`` → Tier 4.
    * ``none`` → Tier 5.
    """

    CHEST_STRAP_RR = "chest_strap_rr"
    CHEST_STRAP_NO_RR = "chest_strap_no_rr"
    WRIST_OPTICAL = "wrist_optical"
    NONE = "none"


class PowerSource(str, Enum):
    """Running power meter availability."""

    RUNNING_POWER_METER = "running_power_meter"
    NONE = "none"


class SportType(str, Enum):
    """Sport type detected from FIT file sport message.

    See docs/architecture/01-entities/activity.md → SportType enum.
    Values are used for calibration eligibility gating (Principle #8:
    non-running activities excluded from twin calibration).
    """

    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    STRENGTH = "strength"
    YOGA_MOBILITY = "yoga_mobility"
    OTHER = "other"
    UNKNOWN = "unknown"


class PrimaryTrainingPlatform(str, Enum):
    """Primary platform used by the athlete for activity uploads."""

    INTERVALS_ICU = "intervals_icu"
    GARMIN_CONNECT = "garmin_connect"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Phase-1.2b — Plan / Session / Checkpoint enums.
#
# These closed ontologies implement the contracts declared in
# docs/architecture/01-entities/training-goal.md, training-plan.md,
# weekly-plan.md, planned-session.md, checkpoint.md, and
# 00-foundations/terminology.md. Values are part of the public
# architecture contract: changing them is a breaking change for
# downstream services. Legacy aliases on ``PhaseLabel`` are mapped
# to canonical labels by the deterministic expansion layer.
# ---------------------------------------------------------------------------


class GoalType(str, Enum):
    """Training-objective mode. Drives coaching posture and language.

    See docs/architecture/01-entities/training-goal.md and
    docs/vision/product/goal-modes.md.
    """

    RACE_EVENT = "race_event"
    TARGET_PERFORMANCE = "target_performance"
    FITNESS_IMPROVEMENT = "fitness_improvement"
    MAINTENANCE = "maintenance"
    RECOVERY = "recovery"


class GoalEventType(str, Enum):
    """Race / performance event type that any training goal may target.

    Used on ``TrainingGoal`` and also reused on ``SecondaryEvent``.
    """

    MARATHON = "marathon"
    HALF_MARATHON = "half_marathon"
    TEN_K = "10k"
    FIVE_K = "5k"
    ULTRA = "ultra"
    TRAIL_RACE = "trail_race"
    CUSTOM = "custom"


class TrainingGoalStatus(str, Enum):
    """Lifecycle status of a ``TrainingGoal``.

    Enforces ``one active per athlete`` via a partial unique index on
    ``(athlete_id) WHERE status = 'active'``.
    """

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class InjurySeverity(str, Enum):
    """How severe the athlete-reported injury is.

    Required when ``TrainingGoal.goal_type = 'recovery'``; null for all
    other goal types. Drives the recovery-mode phase duration and
    load progression rules in plan generation.

    See docs/architecture/00-foundations/terminology.md → Shared Enums.
    """

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"


class SecondaryEventPriority(str, Enum):
    """B-races and C-races tracked as secondary events (B-races are
    higher priority than C-races).
    """

    B = "B"
    C = "C"


class TrainingPlanStatus(str, Enum):
    """Lifecycle status of a ``TrainingPlan``.

    Old plans transition to ``superseded`` rather than being deleted;
    ``completed`` is reserved for plans that ran their full duration
    without being replaced.
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    COMPLETED = "completed"


class PhaseLabel(str, Enum):
    """Closed ontology of methodology-specific phase labels.

    Canonical labels are the primary values; legacy aliases
    (``base_building``, ``threshold_development``, ``race_specific``)
    are mapped to canonical labels by the deterministic expansion
    layer per docs/architecture/00-foundations/terminology.md.
    New plans should use canonical labels directly.
    """

    # Aerobic development — canonical.
    AEROBIC_BASE = "aerobic_base"
    AEROBIC_FOUNDATION = "aerobic_foundation"
    AEROBIC_ACCUMULATION = "aerobic_accumulation"
    AEROBIC_BUILD = "aerobic_build"

    # Structural — canonical.
    HILL_PHASE = "hill_phase"
    STRUCTURAL_TOLERANCE = "structural_tolerance"

    # Threshold — canonical.
    THRESHOLD_BUILD = "threshold_build"
    THRESHOLD_PEAK = "threshold_peak"
    THRESHOLD_CONSOLIDATION = "threshold_consolidation"

    # VO2max — canonical.
    VO2MAX_DEVELOPMENT = "vo2max_development"
    VO2MAX_SHARPENING = "vo2max_sharpening"

    # Race-specific — canonical.
    SPECIAL_ENDURANCE = "special_endurance"
    SPECIFIC_ENDURANCE = "specific_endurance"
    RACE_REHEARSAL = "race_rehearsal"

    # Integration — canonical.
    SHARPENING = "sharpening"
    TAPER = "taper"
    RACE_WEEK = "race_week"

    # Recovery / maintenance — canonical.
    RECOVERY = "recovery"
    TRANSITION = "transition"
    ROLLING_BLOCK = "rolling_block"

    # Legacy aliases — mapped by deterministic expansion layer.
    BASE_BUILDING = "base_building"                # → 'aerobic_base'
    THRESHOLD_DEVELOPMENT = "threshold_development"  # → 'threshold_build'
    RACE_SPECIFIC = "race_specific"                # → 'specific_endurance'


class SessionType(str, Enum):
    """The concrete workout prescription shown on the calendar.

    16 session types → 6 physiological intents via
    ``SESSION_INTENT_MAP`` in docs/architecture/00-foundations/terminology.md.
    Note: ``race_specific`` is a ``SessionPurpose``, not a ``SessionType``.
    """

    REST = "rest"
    RECOVERY_RUN = "recovery_run"
    EASY_RUN = "easy_run"
    LONG_RUN = "long_run"
    MEDIUM_LONG_RUN = "medium_long_run"
    STEADY_STATE = "steady_state"
    TEMPO = "tempo"
    THRESHOLD = "threshold"
    VO2MAX = "vo2max"
    HILL_REPEATS = "hill_repeats"
    FARTLEK = "fartlek"
    STRIDES = "strides"
    DRILLS_MOBILITY = "drills_mobility"
    CROSS_TRAINING = "cross_training"
    TEST_SESSION = "test_session"
    OPTIONAL_RUN = "optional_run"


class SessionSlot(str, Enum):
    """AM/PM session designation on double-day schedules.

    ``None`` for single-session days.
    """

    AM = "am"
    PM = "pm"


class SessionPriority(str, Enum):
    """Workout generation priority.

    Primary sessions receive full workout generation. Secondary
    sessions may be suggested without detailed targets.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"


class PlannedSessionStatus(str, Enum):
    """Lifecycle status of a ``PlannedSession`` once the workout
    generation pipeline has run.
    """

    PENDING = "pending"
    GENERATED = "generated"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    MISSED = "missed"
    REDISTRIBUTED = "redistributed"


class WeeklyPlanStatus(str, Enum):
    """Lifecycle status of a ``WeeklyPlan``."""

    SYNTHESISED = "synthesised"
    ACTIVE = "active"
    COMPLETED = "completed"


class CheckpointType(str, Enum):
    """Closed ontology of checkpoint categories.

    See docs/architecture/01-entities/checkpoint.md.
    """

    CALIBRATION = "calibration"
    BENCHMARK = "benchmark"
    RACE_SIMULATION = "race_simulation"
    SECONDARY_RACE = "secondary_race"
    PROGRESS_REVIEW = "progress_review"


class CheckpointStatus(str, Enum):
    """Lifecycle status of a ``Checkpoint``."""

    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class ObjectiveCategory(str, Enum):
    """Shared objective taxonomy between phase definitions and
    athlete-facing coaching objectives.
    """

    AEROBIC_BASE = "aerobic_base"
    THRESHOLD_QUALITY = "threshold_quality"
    PACING_DISCIPLINE = "pacing_discipline"
    INTENSITY_DISTRIBUTION = "intensity_distribution"
    STRUCTURAL_TOLERANCE = "structural_tolerance"
    NEUROMUSCULAR_SHARPNESS = "neuromuscular_sharpness"
    DURABILITY = "durability"
    INTENSITY_COMPLIANCE = "intensity_compliance"
    RECOVERY_EFFICIENCY = "recovery_efficiency"


# ---------------------------------------------------------------------------
# Phase-1.2c — Twin / Fitness / Coaching / Workout enums.
#
# These closed ontologies implement the contracts declared in
# docs/architecture/01-entities/twin-state.md, athlete-physiology.md,
# athlete-fitness.md, coaching-message.md, generation-event.md,
# generated-workout.md, workout-step.md and
# 00-foundations/terminology.md → Shared Enums.
# Values are part of the public architecture contract: changing them is a
# breaking change for downstream services, prompt payloads, and persisted
# JSONB schemas.
# ---------------------------------------------------------------------------


class TwinTrigger(str, Enum):
    """What caused a ``TwinState`` snapshot to be appended.

    See docs/architecture/01-entities/twin-state.md → Schema.
    """

    QUESTIONNAIRE = "questionnaire"
    ACTIVITY_SYNC = "activity_sync"
    CALIBRATION = "calibration"
    PHYSIOLOGY_INPUT = "physiology_input"
    WELLNESS_UPDATE = "wellness_update"


class TwinConfidenceLevel(str, Enum):
    """Coarse confidence for the twin as a whole.

    See docs/architecture/00-foundations/confidence-model.md and
    01-entities/twin-state.md. Per-metric confidence lives on
    ``TwinState.metric_confidence``.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MessageType(str, Enum):
    """Closed ontology of coach-to-athlete message categories.

    See docs/architecture/01-entities/coaching-message.md → MessageType.
    """

    FIRST_MESSAGE = "first_message"
    POST_WORKOUT = "post_workout"
    WELLNESS_ALERT = "wellness_alert"
    PHASE_TRANSITION = "phase_transition"
    PLAN_REGENERATION = "plan_regeneration"
    CONFIDENCE_UPGRADE = "confidence_upgrade"
    CYCLE_CHECK_IN = "cycle_check_in"
    WEEKLY_SUMMARY = "weekly_summary"


class StepType(str, Enum):
    """Closed ontology of segment categories inside a workout.

    See docs/architecture/01-entities/workout-step.md → StepType.
    """

    WARMUP = "warmup"
    WORK = "work"
    RECOVERY = "recovery"
    COOLDOWN = "cooldown"


class RecoveryModifierLevel(str, Enum):
    """GREEN / AMBER / RED readiness signal produced by WellnessModifierService.

    See docs/architecture/00-foundations/terminology.md → Shared Enums.
    """

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class WellnessTrend(str, Enum):
    """7-day composite wellness trend direction at snapshot time.

    ``WellnessTrend`` is not explicitly defined in the architecture but
    is referenced by ``TwinState.wellness_trend`` and by the
    ``form_trend`` field on the ``AthleteFitnessResponse`` derivation
    inline union ``'improving' | 'stable' | 'declining'``. Values are
    aligned per the plan's Coder Handoff Notes.
    """

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class PhysiologicalIntent(str, Enum):
    """Physiological adaptation a session or step targets — the primary
    coaching abstraction. Six values; many:1 mapping from SessionType.

    See docs/architecture/00-foundations/terminology.md → Shared Enums /
    PhysiologicalIntent.
    """

    LOW_AEROBIC = "low_aerobic"
    HIGH_AEROBIC = "high_aerobic"
    THRESHOLD = "threshold"
    VO2MAX = "vo2max"
    NEUROMUSCULAR = "neuromuscular"
    RECOVERY = "recovery"


class MeasurementSource(str, Enum):
    """Provenance of a physiological observation / measurement.

    See docs/architecture/01-entities/athlete-physiology.md →
    MeasurementSource.
    """

    QUESTIONNAIRE_ESTIMATE = "questionnaire_estimate"
    TRAINING_HR_DEFLECTION = "training_hr_deflection"
    TRAINING_RR_INFLECTION = "training_rr_inflection"
    TRAINING_POWER_HR_RATIO = "training_power_hr_ratio"
    FIELD_TEST = "field_test"
    LAB_TEST = "lab_test"


class SignalType(str, Enum):
    """Signal channel that a ``WorkoutTarget`` carries targets in.

    ``description`` is a non-numeric plain-language target variant used
    when no numeric signal is appropriate (Tier 6 / no-signal sessions).
    See docs/architecture/01-entities/generated-workout.md →
    ``WorkoutTarget`` and 00-foundations/terminology.md.
    """

    POWER = "power"
    GAP = "gap"
    HR = "hr"
    DESCRIPTION = "description"


class SessionPurpose(str, Enum):
    """Why the session is being run — distinct from ``PhysiologicalIntent`` /
    ``SessionType``. ``race_specific`` is NOT a ``SessionType`` and
    ``calibration`` annotates test sessions so the compliance family uses
    the data-quality assessment instead of the standard compliance
    assessment.

    See docs/architecture/00-foundations/terminology.md → SessionPurpose.
    Required by Phase-1.2c's WorkoutStep contract (architecture
    01-entities/workout-step.md). Plan step 1 does not list this enum
    explicitly but ``WorkoutStep.session_purpose`` references it; the
    enum is added here to keep step 8's "all fields from architecture
    contract" implementation faithful.
    """

    GENERAL = "general"
    RACE_SPECIFIC = "race_specific"
    CALIBRATION = "calibration"
