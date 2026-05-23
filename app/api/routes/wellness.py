from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from datetime import date

from app.api.dependencies import get_wellness_service, get_current_athlete_id
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
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: WellnessService = Depends(get_wellness_service),
):
    if payload.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        wellness = await service.create_wellness(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return WellnessResponse.model_validate(wellness)


@router.get("/{wellness_id}", response_model=WellnessResponse)
async def get_wellness(
    wellness_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: WellnessService = Depends(get_wellness_service),
):
    wellness = await service.get_wellness(wellness_id)
    if not wellness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    if wellness.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return WellnessResponse.model_validate(wellness)


@router.patch("/{wellness_id}", response_model=WellnessResponse)
async def update_wellness(
    wellness_id: UUID,
    payload: WellnessUpdate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: WellnessService = Depends(get_wellness_service),
):
    wellness = await service.get_wellness(wellness_id)
    if not wellness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    if wellness.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        wellness = await service.update_wellness(wellness_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return WellnessResponse.model_validate(wellness)


@router.delete("/{wellness_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wellness(
    wellness_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: WellnessService = Depends(get_wellness_service),
):
    wellness = await service.get_wellness(wellness_id)
    if not wellness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    if wellness.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    success = await service.delete_wellness(wellness_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wellness record not found")
    return None
