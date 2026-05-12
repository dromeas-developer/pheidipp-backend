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
    K5 = "5k"
    K10 = "10k"
    HALF_MARATHON = "half_marathon"
    MARATHON = "marathon"
    ULTRA = "ultra"
    CUSTOM = "custom"


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
