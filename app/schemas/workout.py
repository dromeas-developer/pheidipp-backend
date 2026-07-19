"""Workout response schemas (Phase-1.5b)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    PhysiologicalIntent,
    RecoveryModifierLevel,
    SessionPurpose,
    SessionType,
    StepType,
)

from app.schemas.plan import PlannedSessionResponse


class WorkoutTargetPrimaryResponse(BaseModel):
    """The ``primary`` block of a ``WorkoutTarget`` JSONB payload."""

    min: Optional[int]
    max: Optional[int]
    unit: str


class WorkoutTargetResponse(BaseModel):
    """One ``WorkoutTarget`` — the per-step target JSONB shape."""

    signal_type: str  # 'power' | 'gap' | 'hr' | 'description'
    primary: Optional[WorkoutTargetPrimaryResponse]
    fallback: Optional["WorkoutTargetResponse"] = None
    description: str


# Pydantic v2 needs the forward-reference resolved. The recursive
# ``fallback`` field is allowed to reference the same model.
WorkoutTargetResponse.model_rebuild()


class TargetSetResponse(BaseModel):
    """The ``TargetSet`` shape on ``GeneratedWorkout``."""

    targets: List[WorkoutTargetResponse]
    description: str


class WorkoutStepResponse(BaseModel):
    """One ``WorkoutStep`` row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    generated_workout_id: UUID
    step_order: int
    step_type: StepType
    session_type: SessionType
    physiological_intent: PhysiologicalIntent
    session_purpose: SessionPurpose
    target: WorkoutTargetResponse = Field(
        # Inbound: ORM ``WorkoutStep.target`` JSONB column is the
        # source-of-truth attribute. ``validation_alias`` lets
        # ``model_validate(step_row)`` locate it.
        # Outbound: the public wire-format key is ``target`` in the
        # architecture doc — match that name in the JSON response
        # body.
        validation_alias="target",
        serialization_alias="target",
    )
    duration_seconds: Optional[int]
    description: str


class GeneratedWorkoutResponse(BaseModel):
    """One ``GeneratedWorkout`` row plus its ``WorkoutStep[]``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    planned_session_id: UUID
    twin_state_id: UUID
    theoretical_targets: Dict[str, Any]
    adjusted_targets: Dict[str, Any]
    recovery_modifier_level: RecoveryModifierLevel
    recovery_modifier_reason: Optional[str]
    generation_date: date
    generated_at: datetime


class TodayResponse(BaseModel):
    """Response for ``GET /athletes/{athlete_id}/today``."""

    planned_session: PlannedSessionResponse
    generated_workout: GeneratedWorkoutResponse
    steps: List[WorkoutStepResponse]


class GenerateWorkoutResponse(BaseModel):
    """Response for ``POST /athletes/{athlete_id}/sessions/{sid}/generate-workout``."""

    generated_workout: GeneratedWorkoutResponse
    steps: List[WorkoutStepResponse]


class WorkoutAlreadyGeneratedConflictResponse(BaseModel):
    """Response body when the explicit generate endpoint finds a workout already exists for ``(planned_session_id, generation_date)``."""

    existing_workout_id: UUID
    planned_session_id: UUID
    generation_date: date