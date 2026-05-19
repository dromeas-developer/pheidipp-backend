import uuid
from typing import Optional

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.twin_state import TwinState
from app.schemas.twin_state import TwinStateCreate
from app.repositories.base_repository import BaseRepository


class TwinStateRepository(BaseRepository[TwinState]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TwinState)

    async def create(self, data: TwinStateCreate) -> TwinState:
        db_obj = TwinState(**data.model_dump())
        self.session.add(db_obj)
        await self.session.flush()
        return db_obj

    async def get_by_athlete_id(self, athlete_id: uuid.UUID) -> Optional[TwinState]:
        stmt = (
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_history_by_athlete_id(
        self, athlete_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> tuple[list[TwinState], int]:
        # Count query
        count_stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.athlete_id == athlete_id)
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # Select query with pagination
        select_stmt = (
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(select_stmt)
        items = list(result.scalars().all())

        return items, total

    async def count_by_athlete_id(self, athlete_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.athlete_id == athlete_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0