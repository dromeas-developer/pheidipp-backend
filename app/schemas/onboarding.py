from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.athlete_preferences import (
    AthletePreferencesCreate,
    AthletePreferencesResponse,
)
from app.schemas.training_block import TrainingBlockCreate, TrainingBlockResponse


class OnboardingRequest(BaseModel):
    """
    Single onboarding payload covering both domain models.
    The UI presents this as one form; the API splits it into two writes.
    """
    preferences: AthletePreferencesCreate
    training_block: TrainingBlockCreate


class OnboardingResponse(BaseModel):
    """
    Returned after successful onboarding.
    twin_state is null until Phase 1c wires in TwinInitialisationService.
    """
    onboarding_complete: bool
    preferences: AthletePreferencesResponse
    training_block: TrainingBlockResponse
    twin_state: Optional[dict] = None  # replaced with TwinStateResponse in Phase 1c

    model_config = ConfigDict(from_attributes=True)


class OnboardingStatusResponse(BaseModel):
    """
    Returned by GET /athletes/{athlete_id}/onboarding.
    Gives the frontend everything it needs on app load to determine routing.
    preferences and training_block are null before onboarding is complete.
    """
    onboarding_complete: bool
    preferences: Optional[AthletePreferencesResponse] = None
    training_block: Optional[TrainingBlockResponse] = None
    twin_state: Optional[dict] = None  # replaced with TwinStateResponse in Phase 1c

    model_config = ConfigDict(from_attributes=True)