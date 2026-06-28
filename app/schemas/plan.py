"""Plan response schemas (Phase-1.4).

Wire-format contracts for the four read-only plan endpoints:

* ``GET /athletes/{id}/plan``          → ``TrainingPlanResponse``
* ``GET /athletes/{id}/plan/sessions`` → ``list[PlannedSessionResponse]``
* ``GET /athletes/{id}/plan/upcoming`` → ``list[PlannedSessionResponse]``
  (capped at the next five)
* ``GET /athletes/{id}/plan/checkpoints`` → ``list[CheckpointResponse]``

All ORM rows feed directly into Pydantic via ``model_validate`` /
``from_attributes=True`` so the conversion lives in one place. JSONB
columns (phase_definitions, weekly_distributions, checkpoint_schedule,
strategic_rationale, secondary_metrics) are declared as ``dict`` /
``list`` since their shape is enforced at the service layer.
"""

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


# ---------------------------------------------------------------------------
# Phase descriptor — used both as a sub-shape of TrainingPlanResponse.phases
# and as the explicit ``phases_summary`` view on a TrainingPlan row.
# ---------------------------------------------------------------------------


class PhaseDescriptorResponse(BaseModel):
    """Per-phase summary — label, date range, weeks, focus, session count.

    Mirrors the ``PhaseDescriptor`` shape in
    ``docs/architecture/01-entities/training-plan.md``. The
    ``weekly_session_count`` is the static plan-time value and does
    NOT reflect per-week adjustments from pre-week review.
    """

    model_config = ConfigDict(from_attributes=True)

    label: PhaseLabel
    start_date: date
    end_date: date
    weeks: int
    primary_focus: str
    weekly_session_count: int


# ---------------------------------------------------------------------------
# TrainingPlan — top-level plan view.
# ---------------------------------------------------------------------------


class TrainingPlanResponse(BaseModel):
    """Top-level response for ``GET /athletes/{id}/plan``.

    Carries the periodised structure: ordered phases,
    adaptation-strategy phase definitions, per-week distributions,
    lifecycle status, optional strategic rationale (set only for
    ``race_event`` / ``target_performance`` modes), and the scheduled
    checkpoint descriptors.
    """

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


# ---------------------------------------------------------------------------
# PlannedSession — one session on the calendar.
# ---------------------------------------------------------------------------


class PlannedSessionResponse(BaseModel):
    """One PlannedSession record — operability surface for a workout.

    Denormalised ``training_plan_id`` is read-only here; the API
    consumer joins through ``WeeklyPlan.training_plan_id`` to find
    the current plan's sessions. Per the architecture, this column
    can be stale after plan supersession.
    """

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


# ---------------------------------------------------------------------------
# Checkpoint — one planned assessment point.
# ---------------------------------------------------------------------------


class CheckpointResponse(BaseModel):
    """One Checkpoint record attached to the PlannedSession that IS
    the checkpoint.

    ``trajectory_status`` and ``proposal`` are populated only when
    the plan was generated for a ``target_performance`` goal; for
    ``race_event`` plans they remain ``None`` until a coach trajectory
    review runs in a later phase.
    """

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


# ---------------------------------------------------------------------------
# Convenience wrapper for the upcoming-sessions endpoint — kept here so the
# router has a single import path. The schema is just a list of
# ``PlannedSessionResponse`` capped at the next five from today.
# ---------------------------------------------------------------------------


class UpcomingSessionsResponse(BaseModel):
    """Wrapper for ``GET /plan/upcoming`` — ``sessions`` is the next five
    ``PlannedSession`` records from today (inclusive), ordered by
    ``target_date ASC`` then ``session_slot ASC``. The list is empty
    rather than null when no upcoming sessions exist.
    """

    sessions: List[PlannedSessionResponse]
