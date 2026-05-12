import uuid
from typing import Optional

from app.models.training_preferences import TrainingPreferences
from app.repositories.training_preferences_repository import TrainingPreferencesRepository
from app.schemas.training_preferences import (
    TrainingPreferencesCreate,
    TrainingPreferencesUpdate,
)


class TrainingPreferencesService:
    def __init__(self, repo: TrainingPreferencesRepository):
        self.repo = repo

    async def create(
        self, data: TrainingPreferencesCreate
    ) -> TrainingPreferences:
        return await self.repo.create(
            **data.model_dump(exclude_unset=True)
        )

    async def get_by_id(
        self, pref_id: uuid.UUID
    ) -> Optional[TrainingPreferences]:
        return await self.repo.get_by_id(pref_id)

    async def list_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> list[TrainingPreferences]:
        return await self.repo.list_by_athlete(athlete_id)

    async def get_active_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> Optional[TrainingPreferences]:
        return await self.repo.get_active_by_athlete(athlete_id)

    async def update(
        self, pref_id: uuid.UUID, data: TrainingPreferencesUpdate
    ) -> Optional[TrainingPreferences]:
        return await self.repo.update(
            pref_id, **data.model_dump(exclude_unset=True)
        )

    async def delete(self, pref_id: uuid.UUID) -> bool:
        return await self.repo.delete(pref_id)