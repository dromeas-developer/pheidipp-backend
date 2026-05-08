from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.base import Base
from app.models.activity import Activity, ActivityType
from app.models.enums import PerceivedEffort
from app.repositories.base_repository import BaseRepository


class ActivityRepository(BaseRepository[Activity]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Activity)

    async def get_by_athlete(
        self,
        athlete_id: UUID,
        skip: int = 0,
        limit: int = 50,
        activity_type: Optional[ActivityType] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Activity]:
        query = select(self.model).where(self.model.athlete_id == athlete_id)

        if activity_type is not None:
            query = query.where(self.model.activity_type == activity_type)

        if date_from is not None:
            query = query.where(self.model.started_at >= date_from)

        if date_to is not None:
            query = query.where(self.model.started_at <= date_to)

        query = query.order_by(self.model.started_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_athlete(self, athlete_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(self.model.athlete_id == athlete_id)
        )
        return result.scalar_one()
