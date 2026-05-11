from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.schemas.fitness import (
    FitnessCreate,
    FitnessListParams,
    FitnessListResponse,
    FitnessResponse,
    FitnessUpdate,
)
from app.services.fitness_service import FitnessService
from app.repositories.fitness_repository import FitnessRepository
from app.repositories.athlete_repository import AthleteRepository

router = APIRouter(prefix="/fitness", tags=["fitness"])


async def get_fitness_service(
    db: AsyncSession = Depends(get_db),
) -> FitnessService:
    fitness_repo = FitnessRepository(db)
    athlete_repo = AthleteRepository(db)
    return FitnessService(fitness_repo, athlete_repo)


@router.post("/", response_model=FitnessResponse, status_code=status.HTTP_201_CREATED)
async def create_fitness(
    payload: FitnessCreate,
    service: FitnessService = Depends(get_fitness_service),
):
    try:
        fitness = await service.create_fitness(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return FitnessResponse.model_validate(fitness)


@router.get("/{fitness_id}", response_model=FitnessResponse)
async def get_fitness(
    fitness_id: UUID,
    service: FitnessService = Depends(get_fitness_service),
):
    fitness = await service.get_fitness(fitness_id)
    if not fitness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    return FitnessResponse.model_validate(fitness)


@router.patch("/{fitness_id}", response_model=FitnessResponse)
async def update_fitness(
    fitness_id: UUID,
    payload: FitnessUpdate,
    service: FitnessService = Depends(get_fitness_service),
):
    try:
        fitness = await service.update_fitness(fitness_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not fitness:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    return FitnessResponse.model_validate(fitness)


@router.delete("/{fitness_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_fitness(
    fitness_id: UUID,
    service: FitnessService = Depends(get_fitness_service),
):
    success = await service.delete_fitness(fitness_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fitness record not found")
    return None