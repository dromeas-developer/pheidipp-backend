"""Activity response schemas (Phase-1.6).

Wire-format contracts for the activity endpoints:

* ``POST /athletes/{id}/activities/upload``                  → ``ActivityUploadResponse``
* ``GET  /athletes/{id}/activities``                          → ``ActivityListResponse``
* ``GET  /athletes/{id}/activities/{aid}``                    → ``ActivityResponse``
* ``POST /athletes/{id}/activities/{aid}/analyse``            → ``PostWorkoutAnalysisResponse``
* ``GET  /athletes/{id}/activities/{aid}/analysis``           → ``PostWorkoutAnalysisResponse``

ORM-to-response mapping is delegated to Pydantic's
``model_validate`` (with ``from_attributes=True``) so the
conversion lives in one place. JSONB columns
(``quality_flags``) are declared as ``dict``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActivitySource, SportType


# ---------------------------------------------------------------------------
# ActivityResponse — single activity wire shape.
# ---------------------------------------------------------------------------


class ActivityResponse(BaseModel):
    """One ``Activity`` row returned by the API.

    Mirrors the schema from
    ``docs/architecture/01-entities/activity.md``. Load scores
    remain ``null`` for ``source = manual_entry``; signal flags
    (``has_hr``, ``has_power``) reflect what the FIT trace
    actually carried (HR is the only signal consumed at
    Phase-1.6).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    athlete_id: UUID
    planned_session_id: Optional[UUID]
    source: ActivitySource
    external_id: Optional[str]
    activity_date: date
    start_time: datetime
    duration_seconds: int
    aerobic_load: Optional[float]
    neuromuscular_load: Optional[float]
    structural_load: Optional[float]
    has_hr: bool
    has_rr_intervals: bool
    has_power: bool
    has_gps: bool
    calibration_eligible: bool
    quality_flags: Dict[str, Any]
    fit_file_key: Optional[str]
    ingestion_pipeline_version: Optional[str]
    cleaning_pipeline_version: Optional[str]
    sport_type: SportType
    sport_type_detection_version: Optional[str]
    notes: Optional[str]
    created_at: datetime


class ActivityUploadResponse(BaseModel):
    """Response for ``POST /athletes/{id}/activities/upload``.

    Returns the freshly staged ``Activity`` (with null load
    scores — the heavy pipeline runs async in the worker) plus
    the ``task_id`` of the ingestion worker so the client can
    poll for completion. ``ingestion_status`` indicates the
    initial state — ``pending`` until the worker picks the task
    up, then ``running``, then ``completed`` or ``failed``.
    """

    activity: ActivityResponse
    task_id: UUID
    ingestion_status: str = "pending"


class ActivityListResponse(BaseModel):
    """List of activities for the athlete (newest first)."""

    activities: List[ActivityResponse]
    total: int


# ---------------------------------------------------------------------------
# Post-workout analysis response — analysis + coaching message bundle.
# ---------------------------------------------------------------------------


class CoachingMessageSummary(BaseModel):
    """Subset of the ``CoachingMessage`` shape returned alongside
    the activity analysis.

    Avoids depending on the larger ``CoachingMessageResponse``
    schema (which carries fields only relevant to first-message
    listing).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_type: str
    content: str
    prompt_version: str
    twin_state_id: UUID
    generated_at: datetime


class PostWorkoutAnalysisResponse(BaseModel):
    """Response for ``POST /analyse`` and ``GET /analysis``.

    Returns the activity summary plus the generated (or
    pre-existing) post-workout coach message. The two endpoints
    return the same shape so the consumer can poll either path.
    """

    activity: ActivityResponse
    coaching_message: CoachingMessageSummary


# ---------------------------------------------------------------------------
# Error envelopes.
# ---------------------------------------------------------------------------


class ActivityNotFoundResponse(BaseModel):
    """HTTP 404 envelope for a missing activity."""

    activity_id: UUID


class FitParseErrorResponse(BaseModel):
    """HTTP 422 envelope for FIT parse failures."""

    message: str