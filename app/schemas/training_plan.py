import uuid
from datetime import datetime, date
from pydantic import BaseModel

from app.models.enums import TrainingPlanStatus, SessionType, PhysiologicalIntent, TrainingPhase


class PlannedSessionBase(BaseModel):
    id: uuid.UUID
    training_plan_id: uuid.UUID
    scheduled_date: date
    session_type: SessionType
    dominant_physiological_intent: PhysiologicalIntent
    target_duration_minutes: int | None = None
    is_key_session: bool
    week_number: int
    phase: TrainingPhase
    created_at: datetime

    model_config = {"from_attributes": True}


class TrainingPlanBase(BaseModel):
    id: uuid.UUID
    athlete_id: uuid.UUID
    training_block_id: uuid.UUID | None = None
    status: TrainingPlanStatus
    created_at: datetime
    archived_at: datetime | None = None
    plan_rationale: str | None = None

    model_config = {"from_attributes": True}


class TrainingPlanResponse(BaseModel):
    training_plan: TrainingPlanBase
    planned_sessions: list[PlannedSessionBase]


class TrainingPlanListItem(BaseModel):
    training_plan: TrainingPlanBase
    planned_sessions: list[PlannedSessionBase]


class TrainingPlanListResponse(BaseModel):
    items: list[TrainingPlanListItem]
    total: int