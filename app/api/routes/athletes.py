from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.repositories.athlete_repository import AthleteRepository
from app.services.athlete_service import AthleteService
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
)
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.services.athlete_profile_service import AthleteProfileService
from app.schemas.athlete_profile import (
    AthleteProfileUpdate,
    AthleteProfileResponse,
    AthleteWithProfileResponse,
)
from app.services.activity_service import ActivityService
from app.repositories.activity_repository import ActivityRepository
from app.schemas.activity import (
    ActivityListParams,
    ActivityListResponse,
    ActivityResponse,
)
from app.services.wellness_service import WellnessService
from app.repositories.wellness_repository import WellnessRepository
from app.schemas.wellness import (
    WellnessListParams,
    WellnessListResponse,
    WellnessResponse,
)
from app.services.fitness_service import FitnessService
from app.repositories.fitness_repository import FitnessRepository
from app.schemas.fitness import (
    FitnessListParams,
    FitnessListResponse,
    FitnessResponse,
)
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.services.athlete_preferences_service import AthletePreferencesService
from app.schemas.athlete_preferences import AthletePreferencesResponse
from app.repositories.training_block_repository import TrainingBlockRepository
from app.services.training_block_service import TrainingBlockService
from app.schemas.training_block import TrainingBlockResponse

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.post("/", response_model=AthleteResponse)
async def create_athlete(
    payload: AthleteCreate,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    service = AthleteService(athlete_repo)
    athlete = await service.create_athlete(payload)
    return AthleteResponse.model_validate(athlete)


@router.get("/{athlete_id}", response_model=AthleteWithProfileResponse)
async def get_athlete(
    athlete_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    service = AthleteService(athlete_repo)
    athlete = await service.get_athlete_with_profile(athlete_id)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return AthleteWithProfileResponse.model_validate(athlete)


@router.patch("/{athlete_id}", response_model=AthleteResponse)
async def update_athlete(
    athlete_id: UUID,
    payload: AthleteUpdate,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    service = AthleteService(athlete_repo)
    athlete = await service.update_athlete(athlete_id, payload)
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    return AthleteResponse.model_validate(athlete)


@router.put("/{athlete_id}/profile", response_model=AthleteProfileResponse)
async def upsert_profile(
    athlete_id: UUID,
    payload: AthleteProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    profile_repo = AthleteProfileRepository(db)
    service = AthleteProfileService(profile_repo)
    profile = await service.upsert_profile(athlete_id, payload)
    return AthleteProfileResponse.model_validate(profile)


@router.get("/{athlete_id}/profile", response_model=AthleteProfileResponse)
async def get_profile(
    athlete_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    profile_repo = AthleteProfileRepository(db)
    service = AthleteProfileService(profile_repo)
    profile = await service.get_profile(athlete_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return AthleteProfileResponse.model_validate(profile)


async def get_activity_service(
    db: AsyncSession = Depends(get_db),
) -> ActivityService:
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    return ActivityService(activity_repo, athlete_repo)


async def get_wellness_service(
    db: AsyncSession = Depends(get_db),
) -> WellnessService:
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    return WellnessService(wellness_repo, athlete_repo)


async def get_fitness_service(
    db: AsyncSession = Depends(get_db),
) -> FitnessService:
    fitness_repo = FitnessRepository(db)
    athlete_repo = AthleteRepository(db)
    return FitnessService(fitness_repo, athlete_repo)


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


def get_athlete_preferences_service(
    db: AsyncSession = Depends(get_db),
) -> AthletePreferencesService:
    return AthletePreferencesService(AthletePreferencesRepository(db))


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


def get_training_block_service(
    db: AsyncSession = Depends(get_db),
) -> TrainingBlockService:
    return TrainingBlockService(TrainingBlockRepository(db))


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
