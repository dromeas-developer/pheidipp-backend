import enum


class AthleteStatus(str, enum.Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    NON_BINARY = "non_binary"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class UnitPreference(str, enum.Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class ActivityType(str, enum.Enum):
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    YOGA = "yoga"
    STRENGTH = "strength"
    CROSS_TRAINING = "cross_training"
    WALKING = "walking"
    OTHER = "other"


class PerceivedEffort(str, enum.Enum):
    VERY_EASY = "very_easy"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    VERY_HARD = "very_hard"
    MAXIMUM = "maximum"


class WellnessSource(str, enum.Enum):
    MANUAL = "manual"
    GARMIN = "garmin"
    WHOOP = "whoop"
    OURA = "oura"
    POLAR = "polar"


class DataSource(str, enum.Enum):
    MANUAL = "manual"
    LAB_TEST = "lab_test"
    ESTIMATED = "estimated"
    GARMIN = "garmin"
    COROS = "coros"
    POLAR = "polar"
    INTERVALS_ICU = "intervals_icu"


class GoalType(str, enum.Enum):
    RACE = "race"
    FITNESS_IMPROVEMENT = "fitness_improvement"
    MAINTENANCE = "maintenance"
    RECOVERY = "recovery"


class GoalEventType(str, enum.Enum):
    FIVE_K = "5k"
    TEN_K = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    ULTRA = "ultra"
    CUSTOM = "custom"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SportBackground(str, enum.Enum):
    RUNNING_PRIMARY = "running_primary"
    CYCLING_CROSSOVER = "cycling_crossover"
    SWIMMING_CROSSOVER = "swimming_crossover"
    MULTI_SPORT = "multi_sport"
    OTHER = "other"


class TrainingTimeOfDay(str, enum.Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    MIXED = "mixed"


class GpsSource(str, enum.Enum):
    NONE = "none"
    PHONE = "phone"
    WATCH = "watch"


class HrSource(str, enum.Enum):
    NONE = "none"
    WRIST_OPTICAL = "wrist_optical"
    CHEST_STRAP = "chest_strap"


class PowerSource(str, enum.Enum):
    NONE = "none"
    RUNNING_POWER = "running_power"


class PrimaryTrainingPlatform(str, enum.Enum):
    UNKNOWN = "unknown"
    GARMIN_CONNECT = "garmin_connect"
    COROS = "coros"
    POLAR_FLOW = "polar_flow"
    SUUNTO = "suunto"
    INTERVALS_ICU = "intervals_icu"
    STRAVA = "strava"
    TRAININGPEAKS = "trainingpeaks"
    OTHER = "other"


class TwinTrigger(str, enum.Enum):
    QUESTIONNAIRE = "questionnaire"
    CALIBRATION = "calibration"
    WELLNESS_UPDATE = "wellness_update"


class ConfidenceLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataTier(str, enum.Enum):
    TIER1 = "tier1"
    TIER2 = "tier2"
    TIER3 = "tier3"
    TIER4 = "tier4"
    TIER5 = "tier5"


class MessageType(str, enum.Enum):
    FIRST_MESSAGE = "first_message"
    DAILY_BRIEFING = "daily_briefing"
    POST_WORKOUT = "post_workout"
    WEEKLY_REVIEW = "weekly_review"
    RECOVERY_ALERT = "recovery_alert"
    PHASE_TRANSITION = "phase_transition"


class GenerationOutcome(str, enum.Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMITED = "rate_limited"
    SAFETY_REFUSAL = "safety_refusal"
    MALFORMED = "malformed"
    MISSING_DATA = "missing_data"
    INTERNAL_ERROR = "internal_error"


class TrainingPlanStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TrainingPhase(str, enum.Enum):
    BASE = "base"
    BUILD = "build"
    PEAK = "peak"
    TAPER = "taper"
    RACE = "race"
    RECOVERY = "recovery"


class SessionType(str, enum.Enum):
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
    RACE_SPECIFIC = "race_specific"
    STRIDES = "strides"
    DRILLS_MOBILITY = "drills_mobility"
    CROSS_TRAINING = "cross_training"
    TEST_SESSION = "test_session"
    OPTIONAL_RUN = "optional_run"


class PhysiologicalIntent(str, enum.Enum):
    LOW_AEROBIC = "low_aerobic"
    HIGH_AEROBIC = "high_aerobic"
    THRESHOLD = "threshold"
    VO2MAX = "vo2max"
    RACE_SPECIFIC = "race_specific"
    NEUROMUSCULAR = "neuromuscular"
    RECOVERY_SUPPORT = "recovery_support"
    CALIBRATION = "calibration"


class MethodologyTrait(str, enum.Enum):
    HIGH_AEROBIC_VOLUME = "HIGH_AEROBIC_VOLUME"
    LOW_INTENSITY_DOMINANT = "LOW_INTENSITY_DOMINANT"
    THRESHOLD_DENSITY = "THRESHOLD_DENSITY"
    HIGH_INTENSITY_SPARSE = "HIGH_INTENSITY_SPARSE"
    HIGH_FREQUENCY = "HIGH_FREQUENCY"
    STRUCTURAL_DURABILITY = "STRUCTURAL_DURABILITY"
    RACE_SPECIFICITY = "RACE_SPECIFICITY"
    VARIETY_EMPHASIS = "VARIETY_EMPHASIS"
    NEUROMUSCULAR_SUPPORT = "NEUROMUSCULAR_SUPPORT"
    CONSERVATIVE_PROGRESSION = "CONSERVATIVE_PROGRESSION"
