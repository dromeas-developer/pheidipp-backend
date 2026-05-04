from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date

from app.db.session import get_db
from app.repositories.wellness_repository import WellnessRepository
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.wellness import (
    WellnessCreate,
    WellnessListParams,
    WellnessListResponse,
    WellnessResponse,
    WellnessUpdate,
)
from app.services.wellness_service import WellnessService

router = APIRouter(prefix="/wellness", tags=["wellness"])


@router.post("/", response_model=WellnessResponse, status_code=status.HTTP_201_CREATED)
async def create_wellness(
    payload: WellnessCreate,
    db: AsyncSession = Depends(get_db),
):
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    service = WellnessService(wellness_repo, athlete_repo)
    try:
        wellness = await service.create_wellness(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return WellnessResponse.model_validate(wellness)


@router.get("/{wellness_id}", response_model=WellnessResponse)
async def get_wellness(
    wellness_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    service = WellnessService(wellness_repo, athlete_repo)
    wellness = await service.get_wellness(wellness_id)
    if not wellness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    return WellnessResponse.model_validate(wellness)


@router.get("/athletes/{athlete_id}/wellness", response_model=WellnessListResponse)
async def list_athlete_wellness(
    athlete_id: UUID,
    params: WellnessListParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    service = WellnessService(wellness_repo, athlete_repo)
    wellness_records = await service.list_athlete_wellness(athlete_id, params)

    total = await wellness_repo.count_by_athlete(athlete_id)

    return WellnessListResponse(
        items=[WellnessResponse.model_validate(w) for w in wellness_records],
        total=total,
    )


@router.patch("/{wellness_id}", response_model=WellnessResponse)
async def update_wellness(
    wellness_id: UUID,
    payload: WellnessUpdate,
    db: AsyncSession = Depends(get_db),
):
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    service = WellnessService(wellness_repo, athlete_repo)
    try:
        wellness = await service.update_wellness(wellness_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not wellness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    return WellnessResponse.model_validate(wellness)


@router.delete("/{wellness_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wellness(
    wellness_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    service = WellnessService(wellness_repo, athlete_repo)
    success = await service.delete_wellness(wellness_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    return None
