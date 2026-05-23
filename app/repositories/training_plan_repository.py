from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.training_plan import TrainingPlan
from app.models.enums import TrainingPlanStatus
from app.repositories.base_repository import BaseRepository


class TrainingPlanRepository(BaseRepository[TrainingPlan]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TrainingPlan)



    async def get_active_by_athlete(self, athlete_id: UUID) -> Optional[TrainingPlan]:
        result = await self.session.execute(
            select(TrainingPlan)
            .where(
                TrainingPlan.athlete_id == athlete_id,
                TrainingPlan.status == TrainingPlanStatus.ACTIVE,
            )
            .options(selectinload(TrainingPlan.planned_sessions))
        )
        return result.scalar_one_or_none()

    async def archive_plan(self, plan_id: UUID) -> Optional[TrainingPlan]:
        plan = await self.get_by_id(plan_id)
        if plan is None:
            return None
        plan.status = TrainingPlanStatus.ARCHIVED
        from datetime import datetime, timezone
        plan.archived_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan