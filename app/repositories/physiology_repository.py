import uuid
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.physiology import AthletePhysiology
from app.repositories.base_repository import BaseRepository


class PhysiologyRepository(BaseRepository[AthletePhysiology]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AthletePhysiology)

    async def get_by_athlete(
        self, athlete_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[AthletePhysiology]:
        result = await self.session.execute(
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(self.model.effective_from.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_athlete_and_date(
        self, athlete_id: uuid.UUID, target_date: date
    ) -> Optional[AthletePhysiology]:
        result = await self.session.execute(
            select(self.model)
            .where(
                self.model.athlete_id == athlete_id,
                self.model.effective_from <= target_date,
                (self.model.effective_to.is_(None))
                | (self.model.effective_to >= target_date),
            )
            .order_by(self.model.effective_from.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def has_overlap(
        self,
        athlete_id: uuid.UUID,
        effective_from: date,
        effective_to: Optional[date],
        exclude_id: Optional[uuid.UUID] = None,
    ) -> bool:
        conditions = [
            self.model.athlete_id == athlete_id,
            # Existing record overlaps if its end is after (or open-ended relative to) new start
            (self.model.effective_to.is_(None)) | (self.model.effective_to >= effective_from),
        ]
        # Only constrain by new record's end if it isn't open-ended
        if effective_to is not None:
            conditions.append(self.model.effective_from <= effective_to)

        stmt = select(self.model.id).where(*conditions)
        if exclude_id:
            stmt = stmt.where(self.model.id != exclude_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
