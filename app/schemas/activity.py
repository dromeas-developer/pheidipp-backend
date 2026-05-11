import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityType, PerceivedEffort


class ActivityBase(BaseModel):
    activity_type: Optional[ActivityType] = ActivityType.RUNNING
    title: Optional[str] = None
    description: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    perceived_effort: Optional[PerceivedEffort] = None
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    avg_speed_m_per_s: Optional[float] = None
    max_speed_m_per_s: Optional[float] = None
    avg_power: Optional[int] = None
    max_power: Optional[int] = None
    distance_meters: Optional[float] = None
    elevation_gain_meters: Optional[float] = None
    elevation_loss_meters: Optional[float] = None
    calories: Optional[int] = None
    source: Optional[str] = None
    planned_workout_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class ActivityCreate(ActivityBase):
    athlete_id: uuid.UUID


class ActivityUpdate(BaseModel):
    activity_type: Optional[ActivityType] = None
    title: Optional[str] = None
    description: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    perceived_effort: Optional[PerceivedEffort] = None
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    avg_speed_m_per_s: Optional[float] = None
    max_speed_m_per_s: Optional[float] = None
    avg_power: Optional[int] = None
    max_power: Optional[int] = None
    distance_meters: Optional[float] = None
    elevation_gain_meters: Optional[float] = None
    elevation_loss_meters: Optional[float] = None
    calories: Optional[int] = None
    source: Optional[str] = None
    planned_workout_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class ActivityResponse(ActivityBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityListParams(BaseModel):
    activity_type: Optional[ActivityType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ActivityListResponse(BaseModel):
    items: list[ActivityResponse]
    total: int
