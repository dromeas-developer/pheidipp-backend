"""Activity response schemas (Phase-1.6)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActivitySource, SportType


class ActivityResponse(BaseModel):
    """One ``Activity`` row returned by the API."""

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
    """Response for ``POST /athletes/{id}/activities/upload``."""

    activity: ActivityResponse
    task_id: UUID
    ingestion_status: str = "pending"


class ActivityListResponse(BaseModel):
    """List of activities for the athlete (newest first)."""

    activities: List[ActivityResponse]
    total: int


class CoachingMessageSummary(BaseModel):
    """Subset of the ``CoachingMessage`` shape returned alongside the activity analysis."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_type: str
    content: str
    prompt_version: str
    twin_state_id: UUID
    generated_at: datetime


class PostWorkoutAnalysisResponse(BaseModel):
    """Response for ``POST /analyse`` and ``GET /analysis``."""

    activity: ActivityResponse
    coaching_message: CoachingMessageSummary


class ActivityNotFoundResponse(BaseModel):
    """HTTP 404 envelope for a missing activity."""

    activity_id: UUID


class FitParseErrorResponse(BaseModel):
    """HTTP 422 envelope for FIT parse failures."""

    message: str
