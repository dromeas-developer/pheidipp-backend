from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.training_preferences_repository import TrainingPreferencesRepository
from app.services.training_preferences_service import TrainingPreferencesService
from app.schemas.training_preferences import (
    TrainingPreferencesUpdate,
    TrainingPreferencesResponse,
)


router = APIRouter(prefix="/training-preferences", tags=["training-preferences"])


async def get_service(
    db: AsyncSession = Depends(get_db),
) -> TrainingPreferencesService:
    repo = TrainingPreferencesRepository(db)
    return TrainingPreferencesService(repo)


@router.get("/{pref_id}", response_model=TrainingPreferencesResponse)
async def get_training_preferences(
    pref_id: UUID,
    service: TrainingPreferencesService = Depends(get_service),
):
    pref = await service.get_by_id(pref_id)
    if not pref:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training preferences not found",
        )
    return TrainingPreferencesResponse.model_validate(pref)


@router.delete("/{pref_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_preferences(
    pref_id: UUID,
    service: TrainingPreferencesService = Depends(get_service),
):
    success = await service.delete(pref_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training preferences not found",
        )