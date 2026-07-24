"""Onboarding API surface — eight endpoints behind ``require_self``."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    build_onboarding_service,
    require_self,
)
from app.schemas.onboarding import (
    AthletePreferencesPatchIn,
    AthletePreferencesResponse,
    AthleteProfilePatchIn,
    AthleteProfileResponse,
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
    TwinStateHistoryResponse,
    TwinStateResponse,
)
from app.services.onboarding_errors import (
    AthleteNotFoundError,
    InvalidGoalTypeError,
    OnboardingAlreadyCompleteError,
    TrainingGoalConflictError,
)
from app.services.onboarding_service import (
    OnboardingService,
    GoalInput,
    PreferencesInput,
    ProfileInput,
)


onboarding_router = APIRouter(prefix="/athletes", tags=["onboarding"])


@onboarding_router.post(
    "/{athlete_id}/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_onboarding(
    payload: OnboardingRequest,
    athlete_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> OnboardingResponse:
    profile_input = ProfileInput(
        timezone=payload.profile.timezone,
        training_window=payload.profile.training_window,
        height_cm=payload.profile.height_cm,
    )
    prefs_input = PreferencesInput(
        sport_background=payload.preferences.sport_background,
        years_structured_training=payload.preferences.years_structured_training,
        training_time_of_day=payload.preferences.training_time_of_day,
        weekly_schedule=payload.preferences.weekly_schedule,
        gps_source=payload.preferences.gps_source,
        hr_source=payload.preferences.hr_source,
        power_source=payload.preferences.power_source,
        primary_training_platform=payload.preferences.primary_training_platform,
    )
    goal_input = GoalInput(
        goal_type=payload.goal.goal_type,
        goal_event_type=payload.goal.goal_event_type,
        goal_event_name=payload.goal.goal_event_name,
        goal_event_date=payload.goal.goal_event_date,
        custom_distance_km=payload.goal.custom_distance_km,
        goal_description=payload.goal.goal_description,
        weekly_volume_hours=payload.goal.weekly_volume_hours,
        weekly_volume_km=payload.goal.weekly_volume_km,
        fitness_level=payload.goal.fitness_level,
        recent_injury=payload.goal.recent_injury,
        injury_severity=payload.goal.injury_severity,
        target_distance_km=payload.goal.target_distance_km,
        target_time_minutes=payload.goal.target_time_minutes,
    )
    try:
        result = await service.complete_onboarding(
            athlete_id=athlete_id,
            profile_input=profile_input,
            prefs_input=prefs_input,
            goal_input=goal_input,
        )
    except OnboardingAlreadyCompleteError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Onboarding has already been completed for this athlete.",
        )
    except TrainingGoalConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active training goal already exists for this athlete.",
        )
    except InvalidGoalTypeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The supplied goal type is not permitted at onboarding.",
        )
    except AthleteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found.",
        )

    return OnboardingResponse(
        athlete_id=athlete_id,
        onboarding_complete=True,
        twin_state_id=result.twin_state.id,
        training_goal_id=result.training_goal.id,
        data_tier=result.data_tier,
        confidence_level=result.twin_state.confidence_level,
        created_at=result.twin_state.created_at,
    )


@onboarding_router.get(
    "/{athlete_id}/onboarding",
    response_model=OnboardingStatusResponse,
)
async def get_onboarding(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> OnboardingStatusResponse:
    """Return the per-entity existence flags for the path athlete."""
    try:
        status_snapshot = await service.get_onboarding_status(athlete_id)
    except AthleteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found.",
        )
    return OnboardingStatusResponse(
        onboarding_complete=status_snapshot.onboarding_complete,
        has_profile=status_snapshot.has_profile,
        has_preferences=status_snapshot.has_preferences,
        has_training_goal=status_snapshot.has_training_goal,
        has_twin_state=status_snapshot.has_twin_state,
    )


@onboarding_router.get(
    "/{athlete_id}/profile",
    response_model=AthleteProfileResponse,
)
async def get_profile(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> AthleteProfileResponse:
    row = await service.get_profile(athlete_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete profile not found.",
        )
    return AthleteProfileResponse.model_validate(row)


@onboarding_router.patch(
    "/{athlete_id}/profile",
    response_model=AthleteProfileResponse,
)
async def patch_profile(
    payload: AthleteProfilePatchIn,
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> AthleteProfileResponse:
    try:
        row = await service.update_profile(
            athlete_id,
            height_cm=payload.height_cm,
            location_lat=payload.location_lat,
            location_lng=payload.location_lng,
            training_window=payload.training_window,
        )
    except AthleteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete profile not found.",
        )
    return AthleteProfileResponse.model_validate(row)


@onboarding_router.get(
    "/{athlete_id}/preferences",
    response_model=AthletePreferencesResponse,
)
async def get_preferences(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> AthletePreferencesResponse:
    row = await service.get_preferences(athlete_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Athlete preferences not yet created. Complete onboarding "
                "first."
            ),
        )
    return AthletePreferencesResponse.model_validate(row)


@onboarding_router.patch(
    "/{athlete_id}/preferences",
    response_model=AthletePreferencesResponse,
)
async def patch_preferences(
    payload: AthletePreferencesPatchIn,
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> AthletePreferencesResponse:
    patch_dict = payload.model_dump(exclude_unset=True)
    try:
        row = await service.update_preferences(athlete_id, patch=patch_dict)
    except AthleteNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Athlete preferences not yet created. Complete onboarding "
                "first."
            ),
        )
    return AthletePreferencesResponse.model_validate(row)


@onboarding_router.get(
    "/{athlete_id}/twin",
    response_model=TwinStateResponse,
)
async def get_twin_state(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> TwinStateResponse:
    twin = await service.get_twin_state(athlete_id)
    if twin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Twin state has not yet been bootstrapped.",
        )
    return TwinStateResponse.model_validate(twin)


@onboarding_router.get(
    "/{athlete_id}/twin/history",
    response_model=TwinStateHistoryResponse,
)
async def get_twin_history(
    athlete_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    athlete_id_dep: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service),
) -> TwinStateHistoryResponse:
    """Return up to ``?limit=20`` (max 100) ``TwinState`` rows, newest first."""
    twins = await service.get_twin_history(athlete_id, limit=limit)
    return TwinStateHistoryResponse(
        items=[TwinStateResponse.model_validate(t) for t in twins],
        count=len(twins),
    )
