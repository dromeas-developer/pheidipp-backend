"""Plan response schemas (Phase-1.4)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    CheckpointStatus,
    CheckpointType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
)


class PhaseDescriptorResponse(BaseModel):
    """Per-phase summary — label, date range, weeks, focus, session count."""

    model_config = ConfigDict(from_attributes=True)

    label: PhaseLabel
    start_date: date
    end_date: date
    weeks: int
    primary_focus: str
    weekly_session_count: int


class TrainingPlanResponse(BaseModel):
    """Top-level response for ``GET /athletes/{id}/plan``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    training_goal_id: UUID
    twin_state_id: Optional[UUID]
    phases: List[PhaseDescriptorResponse] = Field(
        # Inbound: ORM ``TrainingPlan.phases_summary`` JSONB column
        # is the source-of-truth attribute. ``validation_alias`` lets
        # ``model_validate(plan_row)`` locate it.
        # Outbound: the public wire-format key is documented as
        # ``phases`` in the Phase-1.4 plan (Step 4) and in
        # ``docs/architecture/01-entities/training-plan.md``;
        # ``serialization_alias`` keeps that name in the JSON
        # response body. Without the split, Pydantic v2 would emit
        # ``phases_summary`` for both directions.
        validation_alias="phases_summary",
        serialization_alias="phases",
    )
    phase_definitions: List[Dict[str, Any]]
    weekly_distributions: List[Dict[str, Any]]
    status: str
    strategic_rationale: Optional[Dict[str, Any]]
    checkpoint_schedule: List[Dict[str, Any]]
    superseded_at: Optional[datetime]
    created_at: datetime


class PlannedSessionResponse(BaseModel):
    """One PlannedSession record — operability surface for a workout."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    weekly_plan_id: UUID
    training_plan_id: UUID
    target_date: date
    week_number: int
    phase_label: PhaseLabel
    session_type: SessionType
    intent_description: str
    approximate_duration_minutes: int
    checkpoint_type: Optional[CheckpointType]
    checkpoint_metric: Optional[str]
    status: PlannedSessionStatus
    session_slot: Optional[SessionSlot]
    session_priority: SessionPriority
    is_suggested: bool


class CheckpointResponse(BaseModel):
    """One Checkpoint record attached to the PlannedSession that IS the checkpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    planned_session_id: UUID
    type: CheckpointType
    target_metric: str
    secondary_metrics: List[str]
    twin_update_expected: bool
    replan_trigger: bool
    status: CheckpointStatus
    trajectory_status: Optional[str]
    proposal: Optional[str]
    created_at: datetime


class UpcomingSessionsResponse(BaseModel):
    """Wrapper for ``GET /plan/upcoming`` — next five ``PlannedSession`` records from today."""

    sessions: List[PlannedSessionResponse]
