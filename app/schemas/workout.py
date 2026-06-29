"""Workout response schemas (Phase-1.5b).

Wire-format contracts for the workout endpoints:

* ``GET /athletes/{id}/today``                              → ``TodayResponse``
* ``POST /athletes/{id}/sessions/{sid}/generate-workout``   → ``GenerateWorkoutResponse``

The two-column target display (``theoretical_targets`` /
``adjusted_targets``) on ``GeneratedWorkout`` is always populated;
Phase 1.5b ships them byte-equal because modifier services
(``WellnessModifierService``, ``WeatherAdjustmentService``,
``CyclePhaseService``) land in Phase 1.6 / later. The schema
preserves the field shape so the home-view render does not require
a data-shape migration when those services arrive.

ORM-to-response mapping is delegated to Pydantic's
``model_validate`` (with ``from_attributes=True`` on the response
schemas) so the conversion lives in one place. JSONB columns
(``theoretical_targets``, ``adjusted_targets``, ``target`` on each
step) are declared as ``dict`` since their shape is enforced by the
service layer's ``WorkoutGenerationAgent`` validator.
"""

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


# ---------------------------------------------------------------------------
# WorkoutTarget — sub-shape on every WorkoutStep + the aggregate
# GeneratedWorkout.theoretical_targets / adjusted_targets.
# ---------------------------------------------------------------------------


class WorkoutTargetPrimaryResponse(BaseModel):
    """The ``primary`` block of a ``WorkoutTarget`` JSONB payload.

    Holds the numeric range. ``min`` and ``max`` are null when the
    step is signal-type ``description`` (Tier 5-6 athletes). The
    ``unit`` string identifies the channel
    (``"watts" | "sec_per_km" | "bpm"``).
    """

    min: Optional[int]
    max: Optional[int]
    unit: str


class WorkoutTargetResponse(BaseModel):
    """One ``WorkoutTarget`` — the per-step target JSONB shape.

    Mirrors ``docs/architecture/01-entities/workout-step.md`` →
    ``WorkoutTarget``. ``fallback`` is ``null`` at this phase; Phase
    1.6's ``ExecutionAnalysisService`` will populate an alternative
    signal channel from raw sensor data.
    """

    signal_type: str  # 'power' | 'gap' | 'hr' | 'description'
    primary: Optional[WorkoutTargetPrimaryResponse]
    fallback: Optional["WorkoutTargetResponse"] = None
    description: str


# Pydantic v2 needs the forward-reference resolved. The recursive
# ``fallback`` field is allowed to reference the same model.
WorkoutTargetResponse.model_rebuild()


# ---------------------------------------------------------------------------
# TargetSet — the ``theoretical_targets`` / ``adjusted_targets`` JSONB shape.
# ---------------------------------------------------------------------------


class TargetSetResponse(BaseModel):
    """The ``TargetSet`` shape on ``GeneratedWorkout``.

    ``targets`` is the per-step target array; ``description`` is a
    plain-English summary. At Phase 1.5b
    ``theoretical_targets`` is byte-equal to ``adjusted_targets`` —
    modifier services are not yet wired up.
    """

    targets: List[WorkoutTargetResponse]
    description: str


# ---------------------------------------------------------------------------
# WorkoutStep — one segment of a generated workout.
# ---------------------------------------------------------------------------


class WorkoutStepResponse(BaseModel):
    """One ``WorkoutStep`` row.

    Mirrors ``docs/architecture/01-entities/workout-step.md``. The
    three-layer hierarchy (``session_type``,
    ``physiological_intent``, ``session_purpose``) is preserved so
    downstream consumers can render the same shape used in
    segmentation and execution analysis.
    """

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


# ---------------------------------------------------------------------------
# GeneratedWorkout — the day-of workout header.
# ---------------------------------------------------------------------------


class GeneratedWorkoutResponse(BaseModel):
    """One ``GeneratedWorkout`` row plus its ``WorkoutStep[]``.

    The two-column target structure (``theoretical_targets`` /
    ``adjusted_targets``) is always populated. The
    ``recovery_modifier_reason`` is ``null`` at Phase 1.5b —
    ``WellnessModifierService`` lands in Phase 1.6.
    """

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


# ---------------------------------------------------------------------------
# Wire-format response wrappers.
# ---------------------------------------------------------------------------


class TodayResponse(BaseModel):
    """Response for ``GET /athletes/{athlete_id}/today``.

    Returns the today's ``PlannedSession`` (per the active plan),
    the ``GeneratedWorkout`` (which the endpoint triggers when
    missing) and its ``WorkoutStep[]``. 404 when no session is
    scheduled for today on the active plan.
    """

    planned_session: PlannedSessionResponse
    generated_workout: GeneratedWorkoutResponse
    steps: List[WorkoutStepResponse]


class GenerateWorkoutResponse(BaseModel):
    """Response for ``POST /athletes/{athlete_id}/sessions/{sid}/generate-workout``.

    The explicit generate endpoint returns the freshly created
    ``GeneratedWorkout`` and its ``WorkoutStep[]`` on 201. On 409
    (workout already generated) the API layer surfaces a
    :class:`WorkoutAlreadyGeneratedConflictResponse` instead.
    """

    generated_workout: GeneratedWorkoutResponse
    steps: List[WorkoutStepResponse]


class WorkoutAlreadyGeneratedConflictResponse(BaseModel):
    """Response body when the explicit generate endpoint finds a workout
    already exists for ``(planned_session_id, generation_date)``.

    Surfaced as HTTP 409; the consumer may choose to call
    ``GET /athletes/{id}/today`` to fetch the existing workout.
    """

    existing_workout_id: UUID
    planned_session_id: UUID
    generation_date: date