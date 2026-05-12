import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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


class TrainingPreferencesCreate(TrainingPreferencesBase):
    pass


class TrainingPreferencesUpdate(BaseModel):
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


class TrainingPreferencesResponse(TrainingPreferencesBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)