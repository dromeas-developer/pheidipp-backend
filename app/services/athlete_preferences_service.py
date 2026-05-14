import uuid
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.schemas.athlete_preferences import AthletePreferencesCreate, AthletePreferencesUpdate
from app.models.athlete_preferences import AthletePreferences


class AthletePreferencesService:
    def __init__(self, repo: AthletePreferencesRepository):
        self.repo = repo

    async def create_for_athlete(
        self, athlete_id: uuid.UUID, data: AthletePreferencesCreate
    ) -> AthletePreferences:
        payload = data.model_dump(exclude_unset=True)
        payload["athlete_id"] = athlete_id
        return await self.repo.create(**payload)

    async def get_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> AthletePreferences | None:
        return await self.repo.get_by_athlete(athlete_id)

    async def update(
        self, preferences_id: uuid.UUID, data: AthletePreferencesUpdate
    ) -> AthletePreferences | None:
        return await self.repo.update(
            preferences_id, **data.model_dump(exclude_unset=True)
        )
    