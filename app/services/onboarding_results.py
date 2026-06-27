"""Onboarding result value types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState


@dataclass(frozen=True)
class OnboardingResult:
    """Value object returned by ``OnboardingService.complete_onboarding``.

    Carries the freshly created twin state and active training goal so the
    API layer can build the response without re-querying the session.
    """

    twin_state: TwinState
    training_goal: TrainingGoal
    preferences: AthletePreferences
    profile: AthleteProfile
    data_tier: int


@dataclass(frozen=True)
class OnboardingStatus:
    """Snapshot of post-onboarding state used by ``GET /onboarding``.

    Each flag is the result of a single targeted repository lookup; the
    service keeps them together so the API layer can render a single
    status response.
    """

    onboarding_complete: bool
    has_profile: bool
    has_preferences: bool
    has_training_goal: bool
    has_twin_state: bool


@dataclass(frozen=True)
class ProfileSnapshot:
    """Frozen read view of ``AthleteProfile`` for internal use and tests.

    The service layer's public ``get_profile`` method returns the
    ``AthleteProfile`` ORM row directly so the API layer can map it to
    the public response via ``model_validate``; this dataclass remains
    available for in-process callers that need a detached value object.
    """

    athlete_id: UUID
    date_of_birth: date
    sex: str
    height_cm: Optional[float]
    timezone: Optional[str]
    location_lat: Optional[float]
    location_lng: Optional[float]
    training_window: Optional[dict]
    structural_risk_flag: Optional[bool]


@dataclass(frozen=True)
class PreferencesSnapshot:
    """Frozen read view of ``AthletePreferences`` for internal use and tests.

    The service layer's public ``get_preferences`` method returns the
    ``AthletePreferences`` ORM row directly so the API layer can map it
    to the public response via ``model_validate``; this dataclass
    remains available for in-process callers that need a detached value
    object.
    """

    athlete_id: UUID
    sport_background: str
    years_structured_training: int
    training_time_of_day: str
    weekly_schedule: dict
    gps_source: str
    hr_source: str
    power_source: str
    primary_training_platform: str
