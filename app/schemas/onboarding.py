"""Onboarding request and response schemas (Phase 1.3)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Mapping, Optional, cast
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
    Sex,
    SportBackground,
    TrainingTimeOfDay,
    TwinConfidenceLevel,
    TwinTrigger,
    WellnessTrend,
)


class WeeklyScheduleDayIn(BaseModel):
    """Per-day configuration entry on the athlete's weekly schedule."""

    available: bool
    max_hours: float = Field(ge=0, le=24)
    long_workout: bool = False
    doubles_eligible: bool = False


class WeeklyScheduleDayPatchIn(BaseModel):
    """Per-day delta used only by the weekly_schedule PATCH path."""

    available: Optional[bool] = None
    max_hours: Optional[float] = Field(default=None, ge=0, le=24)
    long_workout: Optional[bool] = None
    doubles_eligible: Optional[bool] = None


class TrainingWindowIn(BaseModel):
    """Athlete's preferred daily training time window."""

    start: str = Field(min_length=1, max_length=5, pattern=r"^\d{2}:\d{2}$")
    end: str = Field(min_length=1, max_length=5, pattern=r"^\d{2}:\d{2}$")


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


def _validate_weekly_schedule_keys(
    value: Mapping[str, WeeklyScheduleDayIn | dict[str, Any]],
) -> Dict[str, WeeklyScheduleDayIn]:
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
        day: WeeklyScheduleDayIn.model_validate(day_cfg)
        for day, day_cfg in value.items()
    }


def _validate_weekly_schedule_patch(
    value: Mapping[str, WeeklyScheduleDayPatchIn | dict[str, Any]],
) -> Dict[str, WeeklyScheduleDayPatchIn]:
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
        day: WeeklyScheduleDayPatchIn.model_validate(day_cfg)
        for day, day_cfg in value.items()
    }


def _coerce_orm_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return float(value)
    return value


def _coerce_orm_row(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    mapper = getattr(row, "__mapper__", None)
    if mapper is None:
        if isinstance(row, dict):
            return cast(Dict[str, Any], row)
        return cast(Dict[str, Any], dict(row))
    coerced: Dict[str, Any] = {}
    for column in mapper.columns:
        coerced[column.key] = _coerce_orm_value(getattr(row, column.key))
    return coerced


class OnboardingProfileIn(BaseModel):
    """Subset of ``AthleteProfile`` fields the onboarding transaction writes."""

    timezone: str = Field(min_length=1, max_length=64)
    training_window: Optional[TrainingWindowIn] = None
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
    weekly_schedule: Dict[str, WeeklyScheduleDayIn]
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
    """``TrainingGoal`` payload — per-``goal_type`` required-field rules."""

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

    @field_validator("goal_event_date")
    @classmethod
    def _validate_event_date_in_future(
        cls, value: Optional[date], info: Any
    ) -> Optional[date]:
        if value is not None and value <= date.today():
            raise ValueError("goal_event_date must be in the future")
        return value

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


# Fields that are immutable on AthleteProfile after registration. The PATCH
# schema rejects these explicitly so a client cannot accidentally (or
# deliberately) bypass the immutability invariant. Per the plan, a
# 422 is returned when any of these keys are present in the body.
_IMMUTABLE_PROFILE_FIELDS = frozenset({"date_of_birth", "sex", "timezone"})


class AthleteProfilePatchIn(BaseModel):
    """PATCH ``AthleteProfile`` — mutable fields only."""

    model_config = ConfigDict(extra="forbid")

    height_cm: Optional[float] = Field(default=None, ge=50, le=300)
    location_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    location_lng: Optional[float] = Field(default=None, ge=-180, le=180)
    training_window: Optional[TrainingWindowIn] = None

    @model_validator(mode="before")
    @classmethod
    def _reject_immutable_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            restricted = cast(dict[str, Any], data)
            forbidden = restricted.keys() & _IMMUTABLE_PROFILE_FIELDS
            if forbidden:
                raise ValueError(
                    "profile fields are immutable after registration: "
                    + ", ".join(sorted(forbidden))
                )
        return cast(Any, data)


class AthletePreferencesPatchIn(BaseModel):
    """PATCH ``AthletePreferences`` — every field optional, partial merge."""

    model_config = ConfigDict(extra="forbid")

    sport_background: Optional[SportBackground] = None
    years_structured_training: Optional[int] = Field(default=None, ge=0, le=80)
    training_time_of_day: Optional[
        Literal["morning", "afternoon", "evening", "variable"]
    ] = None
    weekly_schedule: Optional[Dict[str, WeeklyScheduleDayPatchIn]] = None
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


class OnboardingResponse(BaseModel):
    """Composite response for ``POST /athletes/{id}/onboarding``."""

    model_config = ConfigDict(from_attributes=True)

    athlete_id: UUID
    onboarding_complete: bool
    twin_state_id: UUID
    training_goal_id: UUID
    data_tier: int
    confidence_level: TwinConfidenceLevel
    created_at: datetime


class OnboardingStatusResponse(BaseModel):
    """Per-entity existence flags for ``GET /athletes/{id}/onboarding``."""

    onboarding_complete: bool
    has_profile: bool
    has_preferences: bool
    has_training_goal: bool
    has_twin_state: bool


class AthleteProfileResponse(BaseModel):
    """Public view of ``AthleteProfile``."""

    model_config = ConfigDict(from_attributes=True)

    athlete_id: UUID
    date_of_birth: date
    sex: Sex
    height_cm: Optional[float]
    location_lat: Optional[float]
    location_lng: Optional[float]
    timezone: Optional[str]
    training_window: Optional[TrainingWindowIn]
    structural_risk_flag: Optional[bool]
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return cast(Dict[str, Any], data)
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
    training_time_of_day: TrainingTimeOfDay
    weekly_schedule: Dict[str, WeeklyScheduleDayOut]
    gps_source: GpsSource
    hr_source: HrSource
    power_source: PowerSource
    primary_training_platform: PrimaryTrainingPlatform
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def _coerce_from_orm(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return cast(Dict[str, Any], data)
        return _coerce_orm_row(data)


class TwinStateResponse(BaseModel):
    """Public inline-snapshot view of ``TwinState``."""

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
