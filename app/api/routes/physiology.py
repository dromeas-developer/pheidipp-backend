from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4

from app.api.dependencies import get_physiology_service
from app.schemas.physiology import (
    AthletePhysiologyCreate,
    AthletePhysiologyResponse,
    AthletePhysiologyUpdate,
)
from app.services.physiology_service import PhysiologyService

router = APIRouter(
    prefix="/athletes/{athlete_id}/physiology",
    tags=["physiology"],
)


@router.post("/", response_model=AthletePhysiologyResponse)
async def create_physiology(
    athlete_id: UUID4,
    payload: AthletePhysiologyCreate,
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    try:
        result = await service.create(athlete_id, payload)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[AthletePhysiologyResponse])
async def list_physiology(
    athlete_id: UUID4,
    skip: int = 0,
    limit: int = 50,
    service: PhysiologyService = Depends(get_physiology_service),
) -> list[AthletePhysiologyResponse]:
    try:
        return await service.list_by_athlete(athlete_id, skip=skip, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{physiology_id}", response_model=AthletePhysiologyResponse)
async def get_physiology(
    athlete_id: UUID4,
    physiology_id: UUID4,
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    result = await service.get_by_id(physiology_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return result


@router.get(
    "/effective/{target_date}", response_model=AthletePhysiologyResponse
)
async def get_effective_physiology(
    athlete_id: UUID4,
    target_date: str,
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    from datetime import date

    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format, use YYYY-MM-DD"
        )
    result = await service.get_effective(athlete_id, target)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No effective record"
        )
    return result


@router.patch("/{physiology_id}", response_model=AthletePhysiologyResponse)
async def update_physiology(
    athlete_id: UUID4,
    physiology_id: UUID4,
    payload: AthletePhysiologyUpdate,
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    result = await service.update(physiology_id, payload)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return result


@router.delete(
    "/{physiology_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_physiology(
    athlete_id: UUID4,
    physiology_id: UUID4,
    service: PhysiologyService = Depends(get_physiology_service),
) -> None:
    success = await service.delete(physiology_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
