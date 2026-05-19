from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.dependencies import (
    get_activity_service,
    get_athlete_preferences_service,
    get_athlete_profile_service,
    get_athlete_service,
    get_fitness_service,
    get_training_block_service,
    get_wellness_service,
    get_onboarding_service,
    get_twin_state_service,
)
from app.db.session import get_db
from app.core.unit_of_work import UnitOfWork
from app.services.athlete_service import AthleteService
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
)
from app.services.athlete_profile_service import AthleteProfileService
from app.models.enums import AthleteStatus
from app.schemas.athlete_profile import (
    AthleteProfileUpdate,
    AthleteProfileResponse,
    AthleteWithProfileResponse,
)
from app.services.activity_service import ActivityService
from app.schemas.activity import (
    ActivityListParams,
    ActivityListResponse,
    ActivityResponse,
)
from app.services.wellness_service import WellnessService
from app.schemas.wellness import (
    WellnessListParams,
    WellnessListResponse,
    WellnessResponse,
)
from app.services.fitness_service import FitnessService
from app.schemas.fitness import (
    FitnessListParams,
    FitnessListResponse,
    FitnessResponse,
)
from app.services.athlete_preferences_service import AthletePreferencesService
from app.schemas.athlete_preferences import AthletePreferencesResponse
from app.services.training_block_service import TrainingBlockService
from app.schemas.training_block import TrainingBlockResponse
from app.schemas.onboarding import (
    OnboardingRequest,
    OnboardingResponse,
    OnboardingStatusResponse,
)
from app.schemas.twin_state import TwinStateResponse
from app.services.onboarding_service import OnboardingService
from app.services.twin_state_service import TwinStateService

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.post("/", response_model=AthleteResponse)
async def create_athlete(
    payload: AthleteCreate,
    service: AthleteService = Depends(get_athlete_service),
):
    athlete = await service.create_athlete(payload)
    return AthleteResponse.model_validate(athlete)


@router.get("/{athlete_id}", response_model=AthleteWithProfileResponse)
async def get_athlete(
    athlete_id: UUID,
    service: AthleteService = Depends(get_athlete_service),
):
    athlete = await service.get_athlete_with_profile(athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return AthleteWithProfileResponse.model_validate(athlete)


@router.patch("/{athlete_id}", response_model=AthleteResponse)
async def update_athlete(
    athlete_id: UUID,
    payload: AthleteUpdate,
    service: AthleteService = Depends(get_athlete_service),
):
    athlete = await service.update_athlete(athlete_id, payload)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return AthleteResponse.model_validate(athlete)


@router.put("/{athlete_id}/profile", response_model=AthleteProfileResponse)
async def upsert_profile(
    athlete_id: UUID,
    payload: AthleteProfileUpdate,
    service: AthleteProfileService = Depends(get_athlete_profile_service),
):
    profile = await service.upsert_profile(athlete_id, payload)
    return AthleteProfileResponse.model_validate(profile)


@router.get("/{athlete_id}/profile", response_model=AthleteProfileResponse)
async def get_profile(
    athlete_id: UUID,
    service: AthleteProfileService = Depends(get_athlete_profile_service),
):
    profile = await service.get_profile(athlete_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return AthleteProfileResponse.model_validate(profile)


@router.get("/{athlete_id}/activities", response_model=ActivityListResponse)
async def list_athlete_activities(
    athlete_id: UUID,
    params: ActivityListParams = Depends(),
    service: ActivityService = Depends(get_activity_service),
):
    activities = await service.list_athlete_activities(athlete_id, params)
    total = await service.count_by_athlete(
        athlete_id,
        activity_type=params.activity_type,
        date_from=params.date_from,
        date_to=params.date_to,
    )
    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.get("/{athlete_id}/wellness", response_model=WellnessListResponse)
async def list_athlete_wellness(
    athlete_id: UUID,
    params: WellnessListParams = Depends(),
    service: WellnessService = Depends(get_wellness_service),
):
    wellness_records = await service.list_athlete_wellness(athlete_id, params)
    total = await service.count_by_athlete(athlete_id)
    return WellnessListResponse(
        items=[WellnessResponse.model_validate(w) for w in wellness_records],
        total=total,
    )


@router.get("/{athlete_id}/fitness", response_model=FitnessListResponse)
async def list_athlete_fitness(
    athlete_id: UUID,
    params: FitnessListParams = Depends(),
    service: FitnessService = Depends(get_fitness_service),
):
    fitness_records = await service.list_athlete_fitness(athlete_id, params)
    total = await service.count_by_athlete(athlete_id)
    return FitnessListResponse(
        items=[FitnessResponse.model_validate(f) for f in fitness_records],
        total=total,
    )


@router.get(
    "/{athlete_id}/preferences",
    response_model=AthletePreferencesResponse,
    summary="Get athlete preferences",
)
async def get_athlete_preferences(
    athlete_id: UUID,
    service: AthletePreferencesService = Depends(get_athlete_preferences_service),
):
    result = await service.get_by_athlete(athlete_id)
    if not result:
        raise HTTPException(status_code=404, detail="No preferences found. Complete onboarding first.")
    return result


@router.get(
    "/{athlete_id}/training-blocks",
    response_model=list[TrainingBlockResponse],
    summary="List all training blocks",
)
async def list_training_blocks(
    athlete_id: UUID,
    service: TrainingBlockService = Depends(get_training_block_service),
):
    """Returns all blocks ordered by created_at DESC (active, completed, abandoned).
    Returns an empty list if none exist."""
    return await service.list_by_athlete(athlete_id)


@router.get(
    "/{athlete_id}/training-blocks/active",
    response_model=TrainingBlockResponse,
    summary="Get the current active training block",
)
async def get_active_training_block(
    athlete_id: UUID,
    service: TrainingBlockService = Depends(get_training_block_service),
):
    """
    Returns the current active training block or 404.

    Route ordering note: this endpoint must be registered before any future
    /{athlete_id}/training-blocks/{block_id} route to prevent FastAPI matching
    the literal string "active" as a block_id path parameter. Block-id endpoints
    live on the separate /training-blocks router so this is not currently an
    issue, but preserve the convention as the codebase grows.
    """
    result = await service.get_active_by_athlete(athlete_id)
    if not result:
        raise HTTPException(status_code=404, detail="No active training block found for this athlete.")
    return result


# Valid athlete statuses for onboarding — adjust to match AthleteStatus enum values
ONBOARDABLE_STATUSES = {AthleteStatus.ACTIVE}


@router.post(
    "/{athlete_id}/onboarding",
    response_model=OnboardingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete athlete onboarding",
)
async def onboard_athlete(
    athlete_id: UUID,
    payload: OnboardingRequest,
    athlete_service: AthleteService = Depends(get_athlete_service),
    onboarding_service: OnboardingService = Depends(get_onboarding_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Transitions the athlete into a trainable state by atomically creating:
      - AthletePreferences (stable config)
      - TrainingBlock (first active goal cycle — origin of twin lineage)
      - TwinState (digital twin initial state)
      - onboarding_complete flag

    Pre-flight validation (outside transaction):
      404  Athlete not found
      422  AthleteProfile missing or athlete status not valid for onboarding
      409  Onboarding already complete

    Inside transaction:
      409  Active training block already exists (handled by service)

    Returns 422 if WeeklySchedule validation fails (Pydantic, before any DB write).
    """

    # ── Pre-flight validation (outside transaction) ───────────────────────────

    athlete = await athlete_service.get_athlete(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found",
        )

    # Profile must exist — Phase 1c needs date_of_birth for threshold estimates
    profile = await athlete_service.get_profile(athlete_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Athlete profile is incomplete. "
                "Create a profile with at least date_of_birth before onboarding."
            ),
        )

    # Status must permit onboarding
    if athlete.status not in ONBOARDABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Athlete status '{athlete.status}' does not permit onboarding.",
        )

    # State conflict — repeat onboarding attempt
    if athlete.onboarding_complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Onboarding already complete. "
                "Use PATCH /athlete-preferences/{id} to update preferences, "
                "or close the current training block before starting a new one."
            ),
        )

    # ── Atomic transaction ────────────────────────────────────────────────────

    async with UnitOfWork(db) as uow:
        # Idempotency recheck inside transaction — re-verify onboarding not yet complete
        athlete = await uow.athletes.get_by_id(athlete_id)
        if not athlete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Athlete not found",
            )
        if athlete.onboarding_complete:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Onboarding already complete. "
                    "Use PATCH /athlete-preferences/{id} to update preferences, "
                    "or close the current training block before starting a new one."
                ),
            )

        preferences, training_block, twin_state = (
            await onboarding_service.complete_onboarding(athlete_id, payload, uow)
        )

    return OnboardingResponse(
        onboarding_complete=True,
        preferences=AthletePreferencesResponse.model_validate(preferences),
        training_block=TrainingBlockResponse.model_validate(training_block),
        twin_state=TwinStateResponse.model_validate(twin_state),
    )


@router.get(
    "/{athlete_id}/onboarding",
    response_model=OnboardingStatusResponse,
    summary="Get athlete onboarding status",
)
async def get_onboarding_status(
    athlete_id: UUID,
    athlete_service: AthleteService = Depends(get_athlete_service),
    ap_service: AthletePreferencesService = Depends(get_athlete_preferences_service),
    tb_service: TrainingBlockService = Depends(get_training_block_service),
    twin_service: TwinStateService = Depends(get_twin_state_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns onboarding status, current preferences, and active training block.
    Always returns 200 — an incomplete onboarding is a valid, not an error state.
    Returns 404 only if the athlete does not exist.
    """

    athlete = await athlete_service.get_athlete(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Athlete not found",
        )

    preferences = await ap_service.get_by_athlete(athlete_id)
    training_block = await tb_service.get_active_by_athlete(athlete_id)

    # Get current twin state
    twin_state = None
    if athlete.onboarding_complete:
        async with UnitOfWork(db) as uow:
            twin_state = await twin_service.get_current_twin_state(athlete_id, uow)

    return OnboardingStatusResponse(
        onboarding_complete=athlete.onboarding_complete,
        preferences=(
            AthletePreferencesResponse.model_validate(preferences)
            if preferences else None
        ),
        training_block=(
            TrainingBlockResponse.model_validate(training_block)
            if training_block else None
        ),
        twin_state=twin_state,
    )
