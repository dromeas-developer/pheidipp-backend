"""Onboarding API surface — eight endpoints behind ``require_self``.

Implements the Phase-1.3 contract from
docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md.

All endpoints live under ``/athletes/{athlete_id}`` and depend on
``require_self`` so the JWT's ``athlete_id`` must equal the path
parameter — mismatches surface as HTTP 403, never 404, so
authentication and authorization failures remain distinguishable.

ORM-to-response mapping is delegated to Pydantic's
``model_validate(row)`` (with ``from_attributes=True`` on the response
schemas) so the conversion lives in one place. The service layer
returns ORM rows directly; the snapshot dataclasses are kept for
internal use and downstream tests.

Error mapping follows the ``auth_router`` pattern: catch the
service-layer domain exceptions in the per-endpoint body and
translate them to ``HTTPException`` with a stable, user-facing
detail string. Internal cause / traceback never leaves the service.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    build_onboarding_service,
    build_onboarding_service_with_plan,
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
    _GoalInput,
    _PreferencesInput,
    _ProfileInput,
)
from app.services.plan_generation_errors import (
    PlanGenerationError,
    TrainingLengthGateError,
)


onboarding_router = APIRouter(prefix="/athletes", tags=["onboarding"])


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------


@onboarding_router.post(
    "/{athlete_id}/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_onboarding(
    payload: OnboardingRequest,
    athlete_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    service: OnboardingService = Depends(build_onboarding_service_with_plan),
) -> OnboardingResponse:
    """Run the atomic onboarding transaction for the path athlete.

    Phase-1.4: the onboarding service is built with a
    :class:`PlanGenerationService` so ``complete_onboarding`` invokes
    plan generation atomically at the end of the transaction. The plan
    service owns the commit; any plan-generation failure rolls the
    transaction back so ``onboarding_complete`` stays ``False``.

    201 on success; 409 when the athlete is already onboarded or when
    the partial unique index fires on a duplicate active goal; 422
    for invalid input (handled by Pydantic upstream of this handler);
    403 when the JWT does not match the path athlete.
    """
    profile_input = _ProfileInput(
        timezone=payload.profile.timezone,
        training_window=payload.profile.training_window,
        height_cm=payload.profile.height_cm,
    )
    prefs_input = _PreferencesInput(
        sport_background=payload.preferences.sport_background,
        years_structured_training=payload.preferences.years_structured_training,
        training_time_of_day=payload.preferences.training_time_of_day,
        weekly_schedule=payload.preferences.weekly_schedule,
        gps_source=payload.preferences.gps_source,
        hr_source=payload.preferences.hr_source,
        power_source=payload.preferences.power_source,
        primary_training_platform=payload.preferences.primary_training_platform,
    )
    goal_input = _GoalInput(
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
    except TrainingLengthGateError as exc:
        # Plan-generation gate refused to start a plan — surface the
        # gate's plain-language message so the API consumer can
        # present a coaching-style explanation to the athlete.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        )
    except PlanGenerationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Plan generation could not be completed.",
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
    """Return the public ``AthleteProfile`` view for the path athlete.

    The profile row always exists post-registration; a missing row
    surfaces as 404 here for completeness (the cross-athlete guard
    prevents the missing-row case for an authenticated owner).
    """
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
    """PATCH mutable profile fields. Immutable fields are rejected with 422.

    The ``AthleteProfilePatchIn`` schema enforces the rejection at the
    Pydantic boundary; this handler trusts its input and forwards to
    the service.
    """
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
    """Return the public ``AthletePreferences`` view for the path athlete.

    404 when preferences have not yet been created (i.e. onboarding
    has not run).
    """
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
    """PATCH ``AthletePreferences`` — partial merge per the architecture note.

    ``weekly_schedule`` merges at the day level inside the service.
    """
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
    """Return the latest ``TwinState`` snapshot for the path athlete.

    404 when no TwinState has been appended yet.
    """
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
