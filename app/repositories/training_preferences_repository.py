import uuid
from typing import Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_preferences import TrainingPreferences
from app.repositories.base_repository import BaseRepository


class TrainingPreferencesRepository(BaseRepository[TrainingPreferences]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TrainingPreferences)

    async def list_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> list[TrainingPreferences]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.created_at), desc(self.model.id))
        )
        return list(result.scalars().all())

    async def get_active_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> Optional[TrainingPreferences]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.created_at), desc(self.model.id))
            .limit(1)
        )
        return result.scalar_one_or_none()