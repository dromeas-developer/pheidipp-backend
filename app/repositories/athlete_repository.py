from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.athlete import Athlete
from app.repositories.base_repository import BaseRepository


class AthleteRepository(BaseRepository[Athlete]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Athlete)

    async def get_by_email(self, email: str) -> Athlete | None:
        result = await self.session.execute(
            select(self.model).where(self.model.email == email)
        )
        return result.scalar_one_or_none()
    