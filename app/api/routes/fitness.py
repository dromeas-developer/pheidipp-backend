from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from app.api.dependencies import get_fitness_service, get_current_athlete_id
from app.schemas.fitness import (
    FitnessCreate,
    FitnessListParams,
    FitnessListResponse,
    FitnessResponse,
    FitnessUpdate,
)
from app.services.fitness_service import FitnessService

router = APIRouter(prefix="/fitness", tags=["fitness"])


@router.post("/", response_model=FitnessResponse, status_code=status.HTTP_201_CREATED)
async def create_fitness(
    payload: FitnessCreate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: FitnessService = Depends(get_fitness_service),
):
    if payload.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        fitness = await service.create_fitness(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return FitnessResponse.model_validate(fitness)


@router.get("/{fitness_id}", response_model=FitnessResponse)
async def get_fitness(
    fitness_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: FitnessService = Depends(get_fitness_service),
):
    fitness = await service.get_fitness(fitness_id)
    if not fitness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    if fitness.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return FitnessResponse.model_validate(fitness)


@router.patch("/{fitness_id}", response_model=FitnessResponse)
async def update_fitness(
    fitness_id: UUID,
    payload: FitnessUpdate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: FitnessService = Depends(get_fitness_service),
):
    fitness = await service.get_fitness(fitness_id)
    if not fitness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    if fitness.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        fitness = await service.update_fitness(fitness_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return FitnessResponse.model_validate(fitness)


@router.delete("/{fitness_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fitness(
    fitness_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: FitnessService = Depends(get_fitness_service),
):
    fitness = await service.get_fitness(fitness_id)
    if not fitness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    if fitness.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    success = await service.delete_fitness(fitness_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    return None