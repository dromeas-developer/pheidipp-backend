from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date

from app.db.session import get_db
from app.schemas.wellness import (
    WellnessCreate,
    WellnessListParams,
    WellnessListResponse,
    WellnessResponse,
    WellnessUpdate,
)
from app.services.wellness_service import WellnessService
from app.repositories.wellness_repository import WellnessRepository
from app.repositories.athlete_repository import AthleteRepository

router = APIRouter(prefix="/wellness", tags=["wellness"])


async def get_wellness_service(
    db: AsyncSession = Depends(get_db),
) -> WellnessService:
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    return WellnessService(wellness_repo, athlete_repo)


@router.post("/", response_model=WellnessResponse, status_code=status.HTTP_201_CREATED)
async def create_wellness(
    payload: WellnessCreate,
    service: WellnessService = Depends(get_wellness_service),
):
    try:
        wellness = await service.create_wellness(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return WellnessResponse.model_validate(wellness)


@router.get("/{wellness_id}", response_model=WellnessResponse)
async def get_wellness(
    wellness_id: UUID,
    service: WellnessService = Depends(get_wellness_service),
):
    wellness = await service.get_wellness(wellness_id)
    if not wellness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    return WellnessResponse.model_validate(wellness)


@router.patch("/{wellness_id}", response_model=WellnessResponse)
async def update_wellness(
    wellness_id: UUID,
    payload: WellnessUpdate,
    service: WellnessService = Depends(get_wellness_service),
):
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
    service: WellnessService = Depends(get_wellness_service),
):
    success = await service.delete_wellness(wellness_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    return None
