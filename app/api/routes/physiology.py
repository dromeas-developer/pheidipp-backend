from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from uuid import UUID

from app.api.dependencies import get_physiology_service, get_current_athlete_id
from app.schemas.physiology import (
    AthletePhysiologyCreate,
    AthletePhysiologyResponse,
    AthletePhysiologyUpdate,
)
from app.services.physiology_service import PhysiologyService

router = APIRouter(
    prefix="/physiology",
    tags=["physiology"],
)


@router.post("/", response_model=AthletePhysiologyResponse, status_code=status.HTTP_201_CREATED)
async def create_physiology(
    payload: AthletePhysiologyCreate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    if payload.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        result = await service.create(payload)
        return AthletePhysiologyResponse.model_validate(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{physiology_id}", response_model=AthletePhysiologyResponse)
async def get_physiology(
    physiology_id: UUID4,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    result = await service.get_by_id(physiology_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    if result.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return AthletePhysiologyResponse.model_validate(result)


@router.patch("/{physiology_id}", response_model=AthletePhysiologyResponse)
async def update_physiology(
    physiology_id: UUID4,
    payload: AthletePhysiologyUpdate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: PhysiologyService = Depends(get_physiology_service),
) -> AthletePhysiologyResponse:
    result = await service.get_by_id(physiology_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    if result.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    result = await service.update(physiology_id, payload)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    return AthletePhysiologyResponse.model_validate(result)


@router.delete(
    "/{physiology_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_physiology(
    physiology_id: UUID4,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: PhysiologyService = Depends(get_physiology_service),
) -> None:
    result = await service.get_by_id(physiology_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )
    if result.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    success = await service.delete(physiology_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Record not found"
        )