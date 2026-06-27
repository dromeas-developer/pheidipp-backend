"""Onboarding request and response schemas (Phase 1.3).

These are the wire-format contract for the eight onboarding endpoints
mounted by :mod:`app.api.v1.onboarding`. The schemas are deliberately
strict at the boundary so the service layer can trust its inputs:

* ``WeeklyScheduleIn`` enforces the 7-day shape expected by plan
  generation (``available`` / ``max_hours`` / ``long_workout`` /
  ``doubles_eligible`` per day).
* ``TrainingGoalIn`` enforces the per-``goal_type`` required-field
  rules (``race_event`` → event fields, ``target_performance`` →
  distance + time).
* IANA ``timezone`` is validated against :mod:`zoneinfo` so an invalid
  identifier is rejected with HTTP 422 before the service is invoked.
* The profile PATCH schema rejects any attempt to mutate the
  immutable ``date_of_birth`` / ``sex`` / ``timezone`` fields.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    GpsSource,
    GoalEventType,
    GoalType,
    HrSource,
    InjurySeverity,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    SportBackground,
    TwinConfidenceLevel,
    TwinTrigger,
    WellnessTrend,
)


# ---------------------------------------------------------------------------
# Weekly schedule — structured JSONB shape shared by AthletesPreferences
# and the plan-generation pipeline.
# ---------------------------------------------------------------------------


class WeeklyScheduleDayIn(BaseModel):
    """Per-day configuration entry on the athlete's weekly schedule.

    The full-shape contract for the POST path — every field is
    required (``available``, ``max_hours``) or has a meaningful
    default (``long_workout=False``, ``doubles_eligible=False``). The
    PATCH path uses the looser :class:`WeeklyScheduleDayPatchIn`
    instead so partial day deltas are accepted.
    """

    available: bool
    max_hours: float = Field(ge=0, le=24)
    long_workout: bool = False
    doubles_eligible: bool = False


class WeeklyScheduleDayPatchIn(BaseModel):
    """Per-day delta used only by the weekly_schedule PATCH path.

    The PATCH contract is "merge at the day level; fields not present
    in the request are preserved on the stored day". Each field on
    this schema is therefore ``Optional`` so a client can flip a
    single field — e.g. ``{"saturday": {"available": false}}`` — and
    have the other three preserved. Numeric / bounded validation
    still runs on the fields the client does send so invalid values
    (``max_hours=99``) are rejected with HTTP 422.

    This schema is consumed only by
    :func:`_validate_weekly_schedule_patch`. The POST path keeps
    using :class:`WeeklyScheduleDayIn` unchanged so the
    full-day-creation contract is not weakened.
    """

    available: Optional[bool] = None
    max_hours: Optional[float] = Field(default=None, ge=0, le=24)
    long_workout: Optional[bool] = None
    doubles_eligible: Optional[bool] = None


WeeklyScheduleIn = Dict[
    Literal[
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ],
    WeeklyScheduleDayIn,
]


def _validate_weekly_schedule_keys(value: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure exactly the seven canonical weekday keys are present.

    The architecture contract fixes the schedule to seven canonical
    days. Extra keys are rejected so plan generation never encounters
    unexpected weekdays; missing keys are rejected so a partial
    schedule never silently disables days.

    Returns a plain ``Dict[str, Any]`` whose per-day values are the
    validated and serialised ``WeeklyScheduleDayIn`` shape so the
    caller-side ``Dict[str, Any]`` field accepts the result.
    """
    expected = {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
    if set(value.keys()) != expected:
        missing = expected - set(value.keys())
        extra = set(value.keys()) - expected
        problems: list[str] = []
        if missing:
            problems.append(f"missing: {sorted(missing)}")
        if extra:
            problems.append(f"unexpected: {sorted(extra)}")
        raise ValueError(
            "weekly_schedule must contain exactly the seven weekdays "
            f"({'; '.join(problems)})"
        )
    return {
        day: WeeklyScheduleDayIn.model_validate(day_cfg).model_dump()
        for day, day_cfg in value.items()
    }


def _validate_weekly_schedule_patch(value: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a *partial* weekly_schedule patch — the day-level merge.

    PATCH semantics differ from POST: the caller's body lists only the
    days the client wants to flip. The service layer merges the patch
    on top of the stored schedule, so the seven-day XOR check does
    NOT apply here. We still reject any non-canonical day key
    (``"funday"`` would otherwise silently drop) and any value that
    does not satisfy :class:`WeeklyScheduleDayPatchIn`.

    Per-day validation uses :class:`WeeklyScheduleDayPatchIn` (every
    field optional) rather than :class:`WeeklyScheduleDayIn` so a
    delta like ``{"saturday": {"available": false}}`` is accepted and
    ``max_hours`` / ``long_workout`` / ``doubles_eligible`` on the
    existing stored day are preserved. ``model_dump(exclude_unset=True)``
    drops fields the caller did not supply so the service merge
    only sees keys that should overwrite the stored values — fields
    the caller omitted are never ``None``-stamped onto the stored
    day.

    Returns a plain ``Dict[str, Any]`` whose per-day values contain
    ONLY the fields the caller explicitly set.
    """
    canonical = {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }
    if not value:
        return {}
    extra = set(value.keys()) - canonical
    if extra:
        raise ValueError(
            "weekly_schedule patch contains non-canonical weekday keys "
            f"(unexpected: {sorted(extra)})"
        )
    return {
        day: WeeklyScheduleDayPatchIn.model_validate(day_cfg).model_dump(
            exclude_unset=True
        )
        for day, day_cfg in value.items()
    }


def _coerce_orm_value(value: Any) -> Any:
    """Coerce ORM / Python-only types into JSON-friendly shapes.

    Used by the response-schema ``model_validator(mode="before")`` so
    ``model_validate(row)`` accepts ORM rows directly:

    * ``Enum`` members → their ``.value`` string.
    * ``Decimal`` columns → ``float`` (response fields are typed as
      ``Optional[float]`` for the wire format).

    Plain values (strings, ints, bools, dicts, lists, ``None``) pass
    through unchanged. The function is intentionally tiny so it never
    silently swallows unexpected types.
    """
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    return value


def _coerce_orm_row(row: Any) -> Dict[str, Any]:
    """Convert an ORM row's mapped attributes into a response-shaped dict.

    Iterates over the row's ``__dict__`` (which holds mapped column /
    relationship values) and runs each through ``_coerce_orm_value``.
    Relationship proxies and detached state are skipped via the
    ``__mapper__`` introspection so we never try to coerce a
    collection.
    """
    if row is None:
        return {}
    mapper = getattr(row, "__mapper__", None)
    if mapper is None:
        # Plain dict-shaped input — pass it through unchanged.
        return row if isinstance(row, dict) else dict(row)
    coerced: Dict[str, Any] = {}
    for column in mapper.columns:
        coerced[column.key] = _coerce_orm_value(getattr(row, column.key))
    return coerced


# ---------------------------------------------------------------------------
# Onboarding request — profile, preferences, goal.
# ---------------------------------------------------------------------------


class OnboardingProfileIn(BaseModel):
    """Subset of ``AthleteProfile`` fields the onboarding transaction writes.

    ``timezone`` is required and validated against the IANA tz database.
    ``training_window`` and ``height_cm`` are optional — when omitted,
    the service leaves the existing column value untouched.
    """

    timezone: str = Field(min_length=1, max_length=64)
    training_window: Optional[Dict[str, Any]] = None
    height_cm: Optional[float] = Field(default=None, ge=50, le=300)

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown IANA timezone: {value}") from exc
        return value


class OnboardingPreferencesIn(BaseModel):
    """Full ``AthletePreferences`` payload — every non-derived field."""

    sport_background: SportBackground
    years_structured_training: int = Field(ge=0, le=80)
    training_time_of_day: Literal["morning", "afternoon", "evening", "variable"]
    weekly_schedule: Dict[str, Any]
    gps_source: GpsSource
    hr_source: HrSource
    power_source: PowerSource
    primary_training_platform: PrimaryTrainingPlatform

    @model_validator(mode="after")
    def _validate_weekly_schedule(self) -> "OnboardingPreferencesIn":
        self.weekly_schedule = _validate_weekly_schedule_keys(
            self.weekly_schedule
        )
        return self


class OnboardingTrainingGoalIn(BaseModel):
    """``TrainingGoal`` payload — per-``goal_type`` required-field rules.

    The validation rules implement the architecture contract:

    * ``race_event`` → ``goal_event_type`` / ``goal_event_date`` /
      ``goal_event_name`` required.
    * ``target_performance`` → ``target_distance_km`` /
      ``target_time_minutes`` required.
    * ``fitness_improvement`` / ``maintenance`` / ``recovery`` are
      rejected at the service layer (the whitelist check belongs there
      because it is a domain invariant, not a wire-format concern).
    """

    goal_type: GoalType
    goal_event_type: Optional[GoalEventType] = None
    goal_event_name: Optional[str] = Field(default=None, max_length=255)
    goal_event_date: Optional[date] = None
    custom_distance_km: Optional[float] = Field(default=None, gt=0)
    goal_description: Optional[str] = None
    weekly_volume_hours: float = Field(ge=0, le=80)
    weekly_volume_km: float = Field(ge=0, le=500)
    fitness_level: int = Field(ge=1, le=5)
    recent_injury: Optional[str] = None
    injury_severity: Optional[InjurySeverity] = None
    target_distance_km: Optional[float] = Field(default=None, gt=0)
    target_time_minutes: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "OnboardingTrainingGoalIn":
        if self.goal_type == GoalType.RACE_EVENT:
            missing: list[str] = []
            if self.goal_event_type is None:
                missing.append("goal_event_type")
            if self.goal_event_date is None:
                missing.append("goal_event_date")
            if not self.goal_event_name:
                missing.append("goal_event_name")
            if missing:
                raise ValueError(
                    "race_event goal requires: " + ", ".join(missing)
                )
        elif self.goal_type == GoalType.TARGET_PERFORMANCE:
            missing_tp: list[str] = []
            if self.target_distance_km is None:
                missing_tp.append("target_distance_km")
            if self.target_time_minutes is None:
                missing_tp.append("target_time_minutes")
            if missing_tp:
                raise ValueError(
                    "target_performance goal requires: "
                    + ", ".join(missing_tp)
                )
        return self


class OnboardingRequest(BaseModel):
    """Top-level onboarding request — exactly one of each sub-payload."""

    profile: OnboardingProfileIn
    preferences: OnboardingPreferencesIn
    goal: OnboardingTrainingGoalIn


# ---------------------------------------------------------------------------
# PATCH request schemas — mutable fields only.
# ---------------------------------------------------------------------------


# Fields that are immutable on AthleteProfile after registration. The PATCH
# schema rejects these explicitly so a client cannot accidentally (or
# deliberately) bypass the immutability invariant. Per the plan, a
# 422 is returned when any of these keys are present in the body.
_IMMUTABLE_PROFILE_FIELDS = frozenset({"date_of_birth", "sex", "timezone"})


class AthleteProfilePatchIn(BaseModel):
    """PATCH ``AthleteProfile`` — mutable fields only.

    ``date_of_birth``, ``sex``, and ``timezone`` are silently rejected:
    if any appear in the request body, the schema raises a 422.
    """

    model_config = ConfigDict(extra="forbid")

    height_cm: Optional[float] = Field(default=None, ge=50, le=300)
    location_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    location_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    training_window: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_immutable_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            forbidden = set(data.keys()) & _IMMUTABLE_PROFILE_FIELDS
            if forbidden:
                raise ValueError(
                    "profile fields are immutable after registration: "
                    + ", ".join(sorted(forbidden))
                )
        return data


class AthletePreferencesPatchIn(BaseModel):
    """PATCH ``AthletePreferences`` — every field optional, partial merge.

    ``weekly_schedule`` merges at the day level: ``{"saturday":
    {"available": false}}`` flips Saturday without touching the other
    six days. The patch validator accepts any subset of the seven
    canonical days and rejects only non-canonical keys — the seven-
    day XOR check belongs to the POST path.
    """

    model_config = ConfigDict(extra="forbid")

    sport_background: Optional[SportBackground] = None
    years_structured_training: Optional[int] = Field(default=None, ge=0, le=80)
    training_time_of_day: Optional[
        Literal["morning", "afternoon", "evening", "variable"]
    ] = None
    weekly_schedule: Optional[Dict[str, Any]] = None
    gps_source: Optional[GpsSource] = None
    hr_source: Optional[HrSource] = None
    power_source: Optional[PowerSource] = None
    primary_training_platform: Optional[PrimaryTrainingPlatform] = None

    @model_validator(mode="after")
    def _validate_weekly_schedule(self) -> "AthletePreferencesPatchIn":
        if self.weekly_schedule is not None:
            self.weekly_schedule = _validate_weekly_schedule_patch(
                self.weekly_schedule
            )
        return self


# ---------------------------------------------------------------------------
# Response schemas.
# ---------------------------------------------------------------------------


class OnboardingResponse(BaseModel):
    """Composite response for ``POST /athletes/{id}/onboarding``.

    The service returns enough state to render the bootstrap outcome
    without re-querying the database — twin_state_id, training_goal_id,
    data_tier, confidence_level, and the created athlete / profile /
    preferences / twin state records.
    """

    model_config = ConfigDict(from_attributes=True)

    athlete_id: UUID
    onboarding_complete: bool
    twin_state_id: UUID
    training_goal_id: UUID
    data_tier: int
    confidence_level: TwinConfidenceLevel
    created_at: datetime


class OnboardingStatusResponse(BaseModel):
    """Per-entity existence flags for ``GET /athletes/{id}/onboarding``.

    Returned whether or not onboarding has run; the flags are what the
    client uses to render the multi-step onboarding wizard.
    """

    onboarding_complete: bool
    has_profile: bool
    has_preferences: bool
    has_training_goal: bool
    has_twin_state: bool


class AthleteProfileResponse(BaseModel):
    """Public view of ``AthleteProfile``.

    Excludes the personalisation model JSONBs (``gap_curve_model`` /
    ``weather_response_model`` / ``banister_constants`` /
    ``cycle_personal_model`` / ``objective_thresholds``) — these
    belong to the personalisation surface (Phase 1.6+) and never
    appear in the public profile view.
    """

    model_config = ConfigDict(from_attributes=True)

    athlete_id: UUID
    date_of_birth: date
    sex: str
    height_cm: Optional[float]
    location_lat: Optional[float]
    location_lng: Optional[float]
    timezone: Optional[str]
    training_window: Optional[Dict[str, Any]]
    structural_risk_flag: Optional[bool]
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_orm(cls, data: Any) -> Any:
        """Accept ORM rows and coerce ``Enum``/``Decimal`` to wire types."""
        if isinstance(data, dict):
            return data
        return _coerce_orm_row(data)


class WeeklyScheduleDayOut(BaseModel):
    """Per-day public view of the weekly schedule."""

    available: bool
    max_hours: float
    long_workout: bool
    doubles_eligible: bool


WeeklyScheduleOut = Dict[
    Literal[
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ],
    WeeklyScheduleDayOut,
]


class AthletePreferencesResponse(BaseModel):
    """Public view of ``AthletePreferences`` — full shape, no fields hidden."""

    model_config = ConfigDict(from_attributes=True)

    athlete_id: UUID
    sport_background: SportBackground
    years_structured_training: int
    training_time_of_day: str
    weekly_schedule: Dict[str, WeeklyScheduleDayOut]
    gps_source: GpsSource
    hr_source: HrSource
    power_source: PowerSource
    primary_training_platform: PrimaryTrainingPlatform
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_orm(cls, data: Any) -> Any:
        """Accept ORM rows and coerce ``Enum`` members to ``.value``."""
        if isinstance(data, dict):
            return data
        return _coerce_orm_row(data)


class TwinStateResponse(BaseModel):
    """Public inline-snapshot view of ``TwinState``.

    The model stores fitness / fatigue / form / threshold values as
    flat columns and the metric-level confidence breakdown as JSONB;
    the response mirrors the storage shape so consumers can read
    historical snapshots verbatim.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    athlete_id: UUID
    training_goal_id: UUID
    activity_id: Optional[UUID]
    data_tier: int
    confidence_level: TwinConfidenceLevel
    trigger: TwinTrigger
    model_version: str
    fitness: float
    fatigue: float
    form: float
    lt1_pace_sec_per_km: Optional[float]
    lt1_power_watts: Optional[float]
    lt1_hr_bpm: Optional[float]
    lt2_pace_sec_per_km: Optional[float]
    lt2_power_watts: Optional[float]
    lt2_hr_bpm: Optional[float]
    cp_watts: Optional[float]
    readiness_level: RecoveryModifierLevel
    wellness_trend: Optional[WellnessTrend]
    metric_confidence: Dict[str, Optional[TwinConfidenceLevel]]
    created_at: datetime


class TwinStateHistoryResponse(BaseModel):
    """List of ``TwinStateResponse`` ordered by ``created_at`` desc."""

    items: List[TwinStateResponse]
    count: int
