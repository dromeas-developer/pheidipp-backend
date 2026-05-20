from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models.coach_message import CoachMessage
from app.models.enums import MessageType
from app.repositories.base_repository import BaseRepository


class CoachMessageRepository(BaseRepository[CoachMessage]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, CoachMessage)

    async def create(self, **kwargs) -> CoachMessage:
        instance = CoachMessage(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get_latest_by_athlete(self, athlete_id: UUID) -> Optional[CoachMessage]:
        result = await self.session.execute(
            select(CoachMessage)
            .where(CoachMessage.athlete_id == athlete_id)
            .order_by(CoachMessage.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_first_message_by_athlete(
        self, athlete_id: UUID
    ) -> Optional[CoachMessage]:
        result = await self.session.execute(
            select(CoachMessage)
            .where(
                CoachMessage.athlete_id == athlete_id,
                CoachMessage.message_type == MessageType.FIRST_MESSAGE,
            )
            .order_by(CoachMessage.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_first_message(self, athlete_id: UUID) -> bool:
        result = await self.session.execute(
            select(func.count(CoachMessage.id))
            .where(
                CoachMessage.athlete_id == athlete_id,
                CoachMessage.message_type == MessageType.FIRST_MESSAGE,
            )
        )
        count = result.scalar()
        return (count or 0) > 0

    async def list_by_athlete(
        self, athlete_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[CoachMessage], int]:
        result = await self.session.execute(
            select(CoachMessage)
            .where(CoachMessage.athlete_id == athlete_id)
            .order_by(CoachMessage.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        messages = list(result.scalars().all())

        count_result = await self.session.execute(
            select(func.count(CoachMessage.id)).where(
                CoachMessage.athlete_id == athlete_id
            )
        )
        total = count_result.scalar() or 0

        return messages, total