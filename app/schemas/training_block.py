from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
import uuid
from datetime import date, datetime
from app.models.enums import GoalType, GoalEventType, GoalStatus


class TrainingBlockBase(BaseModel):
    goal_type: Optional[GoalType] = None
    goal_event_type: Optional[GoalEventType] = None
    goal_event_name: Optional[str] = Field(None, max_length=200)
    goal_event_date: Optional[date] = None
    goal_description: Optional[str] = Field(None, max_length=500)
    custom_distance_km: Optional[float] = Field(None, gt=0)
    weekly_volume_hours: Optional[float] = Field(None, ge=0)
    weekly_volume_km: Optional[float] = Field(None, ge=0)
    fitness_level: Optional[int] = Field(None, ge=1, le=5)
    recent_injury: Optional[bool] = None


class TrainingBlockCreate(TrainingBlockBase):
    pass


class TrainingBlockUpdate(BaseModel):
    """
    Restricted update schema. Only status, event date, and description
    are patchable after creation. Semantic fields (goal_type, goal_event_type,
    bootstrap snapshot fields) are immutable. To change goal type or event,
    close the current block and open a new one via the onboarding or
    new-block endpoint.
    """
    status: Optional[GoalStatus] = None
    goal_event_date: Optional[date] = None
    goal_description: Optional[str] = Field(None, max_length=500)


class TrainingBlockResponse(TrainingBlockBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    status: GoalStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
