from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

from app.db.base import Base
from app.models.athlete import Athlete, AthleteProfile
from app.repositories.base_repository import BaseRepository


class AthleteRepository(BaseRepository[Athlete]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Athlete)

    async def get_by_email(self, email: str) -> Athlete | None:
        result = await self.session.execute(
            select(self.model).where(self.model.email == email)
        )
        return result.scalar_one_or_none()


class AthleteProfileRepository(BaseRepository[AthleteProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AthleteProfile)

    async def get_by_athlete_id(self, athlete_id: uuid.UUID) -> AthleteProfile | None:
        result = await self.session.execute(
            select(self.model).where(self.model.athlete_id == athlete_id)
        )
        return result.scalar_one_or_none()
