from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional
import uuid
from datetime import datetime
from app.models.enums import (
    SportBackground, TrainingTimeOfDay,
    GpsSource, HrSource, PowerSource, PrimaryTrainingPlatform
)

VALID_DAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


class DaySchedule(BaseModel):
    """Per-day training schedule entry."""
    available: bool
    max_hours: float = Field(ge=0, description="Maximum session duration in hours for this day")
    long_workout: bool = Field(
        description="Whether long workouts (e.g. long run) are preferred on this day"
    )


class WeeklySchedule(BaseModel):
    """
    Structured weekly training schedule.

    Example:
    {
      "days": {
        "mon": {"available": true,  "max_hours": 1.0,  "long_workout": false},
        "tue": {"available": false, "max_hours": 0,    "long_workout": false},
        "wed": {"available": true,  "max_hours": 1.5,  "long_workout": false},
        "thu": {"available": false, "max_hours": 0,    "long_workout": false},
        "fri": {"available": true,  "max_hours": 1.0,  "long_workout": false},
        "sat": {"available": true,  "max_hours": 2.5,  "long_workout": true},
        "sun": {"available": true,  "max_hours": 3.0,  "long_workout": true}
      },
      "available_days_count": 5
    }
    """
    days: dict[str, DaySchedule]
    available_days_count: int = Field(ge=0, le=7)

    @model_validator(mode="after")
    def validate_structure(self) -> "WeeklySchedule":
        # All keys must be valid day names
        invalid_keys = set(self.days.keys()) - VALID_DAYS
        if invalid_keys:
            raise ValueError(f"Invalid day keys: {invalid_keys}. Must be one of {VALID_DAYS}")

        # All seven days must be present — unavailable days use available=false
        missing = VALID_DAYS - set(self.days.keys())
        if missing:
            raise ValueError(f"Missing day entries: {missing}. All 7 days must be specified.")

        # available_days_count must match actual available days
        derived = sum(1 for d in self.days.values() if d.available)
        if derived != self.available_days_count:
            raise ValueError(
                f"available_days_count ({self.available_days_count}) does not match "
                f"count of available days in schedule ({derived})"
            )

        # long_workout may only be true on available days
        invalid_long = [
            day for day, sched in self.days.items()
            if sched.long_workout and not sched.available
        ]
        if invalid_long:
            raise ValueError(
                f"long_workout=true on unavailable days: {invalid_long}"
            )

        return self


class AthletePreferencesBase(BaseModel):
    sport_background: Optional[SportBackground] = None
    years_structured_training: Optional[float] = Field(None, ge=0)
    training_time_of_day: Optional[TrainingTimeOfDay] = None
    weekly_schedule: Optional[WeeklySchedule] = None
    gps_source: Optional[GpsSource] = None
    hr_source: Optional[HrSource] = None
    power_source: Optional[PowerSource] = None
    primary_training_platform: Optional[PrimaryTrainingPlatform] = None


class AthletePreferencesCreate(AthletePreferencesBase):
    pass


class AthletePreferencesUpdate(AthletePreferencesBase):
    pass


class AthletePreferencesResponse(AthletePreferencesBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
    