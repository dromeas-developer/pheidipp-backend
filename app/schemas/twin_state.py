from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier


class TwinStateBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    athlete_id: uuid.UUID
    athlete_preferences_id: uuid.UUID
    trigger: TwinTrigger
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    data_tier: DataTier
    fitness_score: float = Field(ge=0, le=100)
    fatigue_score: float = Field(ge=0, default=0.0)
    max_hr_estimate: float
    lt1_hr_estimate: float
    lt2_hr_estimate: float
    lt1_pace_estimate: Optional[float] = None
    lt2_pace_estimate: Optional[float] = None
    structural_capacity_score: float = Field(ge=0, le=1)
    fitness_time_constant: float = 42.0
    fatigue_time_constant: float = 7.0
    computation_summary: str
    computation_metadata: dict


class TwinStateCreate(TwinStateBase):
    pass


class TwinStateResponse(TwinStateBase):
    id: uuid.UUID
    created_at: datetime