from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planned_session import PlannedSession
from app.repositories.base_repository import BaseRepository


class PlannedSessionRepository(BaseRepository[PlannedSession]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PlannedSession)

    async def create(self, **kwargs) -> PlannedSession:
        instance = PlannedSession(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def list_by_plan(self, training_plan_id: UUID) -> list[PlannedSession]:
        result = await self.session.execute(
            select(PlannedSession)
            .where(PlannedSession.training_plan_id == training_plan_id)
            .order_by(PlannedSession.scheduled_date)
        )
        return list(result.scalars().all())

    async def bulk_create(self, sessions_data: list[dict]) -> list[PlannedSession]:
        instances = [PlannedSession(**data) for data in sessions_data]
        for instance in instances:
            self.session.add(instance)
        await self.session.flush()
        for instance in instances:
            await self.session.refresh(instance)
        return instances