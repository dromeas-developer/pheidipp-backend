from typing import List, Optional
from uuid import UUID
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.base import Base
from app.models.wellness import AthleteWellness
from app.repositories.base_repository import BaseRepository


class WellnessRepository(BaseRepository[AthleteWellness]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AthleteWellness)

    async def get_by_id(self, wellness_id: UUID) -> Optional[AthleteWellness]:
        return await super().get_by_id(wellness_id)

    async def update_by_id(self, wellness_id: UUID, **kwargs) -> Optional[AthleteWellness]:
        return await super().update(wellness_id, **kwargs)

    async def delete_by_id(self, wellness_id: UUID) -> bool:
        existing = await self.get_by_id(wellness_id)
        if not existing:
            return False
        self.session.delete(existing)
        await self.session.commit()
        return True

    async def get_by_athlete_date(
        self, athlete_id: UUID, metric_date: date
    ) -> Optional[AthleteWellness]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .where(self.model.metric_date == metric_date)
        )
        return result.scalar_one_or_none()

    async def get_by_athlete(
        self,
        athlete_id: UUID,
        skip: int = 0,
        limit: int = 50,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[AthleteWellness]:
        query = select(self.model).where(self.model.athlete_id == athlete_id)

        if date_from is not None:
            query = query.where(self.model.metric_date >= date_from)

        if date_to is not None:
            query = query.where(self.model.metric_date <= date_to)

        query = query.order_by(self.model.metric_date.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self, athlete_id: UUID, metric_date: date, **kwargs
    ) -> Optional[AthleteWellness]:
        """Update wellness record by composite key (athlete_id, metric_date)."""
        existing = await self.get_by_athlete_date(athlete_id, metric_date)
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        return None

    async def delete_by_composite_key(
        self, athlete_id: UUID, metric_date: date
    ) -> bool:
        """Delete wellness record by composite key (athlete_id, metric_date)."""
        existing = await self.get_by_athlete_date(athlete_id, metric_date)
        if not existing:
            return False
        self.session.delete(existing)
        await self.session.commit()
        return True

    async def count_by_athlete(self, athlete_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(self.model.athlete_id == athlete_id)
        )
        return result.scalar_one()
