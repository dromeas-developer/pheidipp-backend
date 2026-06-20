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


class PrimaryTrainingPlatform(str, Enum):
    """Primary platform used by the athlete for activity uploads."""

    INTERVALS_ICU = "intervals_icu"
    GARMIN_CONNECT = "garmin_connect"
    MANUAL = "manual"
