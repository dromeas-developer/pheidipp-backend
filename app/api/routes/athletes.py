from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.repositories.athlete_repository import (
    AthleteRepository,
    AthleteProfileRepository,
)
from app.services.athlete_service import AthleteService
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
    AthleteResponse,
    AthleteProfileUpdate,
    AthleteProfileResponse,
    AthleteWithProfileResponse,
)

router = APIRouter(prefix="/athletes", tags=["athletes"])


@router.post("/", response_model=AthleteResponse)
async def create_athlete(
    payload: AthleteCreate,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    profile_repo = AthleteProfileRepository(db)
    service = AthleteService(athlete_repo, profile_repo)
    athlete = await service.create_athlete(payload)
    return AthleteResponse.model_validate(athlete)


@router.get("/{athlete_id}", response_model=AthleteWithProfileResponse)
async def get_athlete(
    athlete_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    profile_repo = AthleteProfileRepository(db)
    service = AthleteService(athlete_repo, profile_repo)
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
    profile_repo = AthleteProfileRepository(db)
    service = AthleteService(athlete_repo, profile_repo)
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
    athlete_repo = AthleteRepository(db)
    profile_repo = AthleteProfileRepository(db)
    service = AthleteService(athlete_repo, profile_repo)
    profile = await service.upsert_profile(athlete_id, payload)
    return AthleteProfileResponse.model_validate(profile)


@router.get("/{athlete_id}/profile", response_model=AthleteProfileResponse)
async def get_profile(
    athlete_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    athlete_repo = AthleteRepository(db)
    profile_repo = AthleteProfileRepository(db)
    service = AthleteService(athlete_repo, profile_repo)
    profile = await service.get_profile(athlete_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return AthleteProfileResponse.model_validate(profile)
