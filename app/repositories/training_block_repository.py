from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
from app.repositories.base_repository import BaseRepository
from app.models.training_block import TrainingBlock
from app.models.enums import GoalStatus


class TrainingBlockRepository(BaseRepository[TrainingBlock]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TrainingBlock)

    async def get_active_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> TrainingBlock | None:
        stmt = (
            select(self.model)
            .where(
                self.model.athlete_id == athlete_id,
                self.model.status == GoalStatus.ACTIVE,
            )
            .order_by(desc(self.model.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> list[TrainingBlock]:
        stmt = (
            select(self.model)
            .where(self.model.athlete_id == athlete_id)
            .order_by(desc(self.model.created_at))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    