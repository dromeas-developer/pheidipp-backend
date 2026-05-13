import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    GoalType,
    GoalEventType,
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
)


class TrainingPreferencesBase(BaseModel):
    goal_type: Optional[GoalType] = None
    goal_event_type: Optional[GoalEventType] = None
    custom_distance_km: Optional[float] = None
    goal_event_date: Optional[date] = None
    goal_description: Optional[str] = Field(default=None, max_length=500)
    weekly_volume_hours: Optional[float] = None
    weekly_volume_km: Optional[float] = None
    years_structured_training: Optional[float] = None
    sport_background: Optional[SportBackground] = None
    recent_injury: Optional[bool] = None
    weekly_schedule: Optional[dict] = None
    gps_source: Optional[GpsSource] = None
    hr_source: Optional[HrSource] = None
    power_source: Optional[PowerSource] = None
    primary_training_platform: Optional[PrimaryTrainingPlatform] = None
    fitness_level: Optional[int] = None

    @field_validator('fitness_level')
    @classmethod
    def validate_fitness_level(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 10):
            raise ValueError('fitness_level must be between 1 and 10')
        return v

    @field_validator('weekly_volume_hours', 'weekly_volume_km')
    @classmethod
    def validate_positive_volume(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError('volume must be non-negative')
        return v


class TrainingPreferencesCreate(TrainingPreferencesBase):
    athlete_id: Optional[uuid.UUID] = None


class TrainingPreferencesUpdate(TrainingPreferencesBase):
    pass


class TrainingPreferencesResponse(TrainingPreferencesBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)