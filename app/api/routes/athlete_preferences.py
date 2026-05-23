from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.db.session import get_db
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.services.athlete_preferences_service import AthletePreferencesService
from app.schemas.athlete_preferences import AthletePreferencesUpdate, AthletePreferencesResponse
from app.api.dependencies import get_current_athlete_id

router = APIRouter(prefix="/athlete-preferences", tags=["athlete-preferences"])


def get_service(db: AsyncSession = Depends(get_db)) -> AthletePreferencesService:
    return AthletePreferencesService(AthletePreferencesRepository(db))


@router.get("/{preferences_id}", response_model=AthletePreferencesResponse)
async def get_preferences(
    preferences_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: AthletePreferencesService = Depends(get_service),
):
    result = await service.repo.get_by_id(preferences_id)
    if not result:
        raise HTTPException(status_code=404, detail="Preferences not found")
    if result.athlete_id != current_athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return result


@router.patch("/{preferences_id}", response_model=AthletePreferencesResponse)
async def update_preferences(
    preferences_id: UUID,
    payload: AthletePreferencesUpdate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: AthletePreferencesService = Depends(get_service),
):
    result = await service.repo.get_by_id(preferences_id)
    if not result:
        raise HTTPException(status_code=404, detail="Preferences not found")
    if result.athlete_id != current_athlete_id:
        raise HTTPException(status_code=403, detail="Access denied")
    result = await service.update(preferences_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Preferences not found")
    return result

# No DELETE endpoint — preferences are not deletable