from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.repositories.base_repository import BaseRepository
from app.models.athlete_preferences import AthletePreferences


class AthletePreferencesRepository(BaseRepository[AthletePreferences]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AthletePreferences)

    async def get_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> AthletePreferences | None:
        stmt = select(self.model).where(self.model.athlete_id == athlete_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    