"""TrainingGoalRepository — goal-of-training lookups and writes."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TrainingGoalStatus
from app.models.training_goal import TrainingGoal


class TrainingGoalRepository:
    """Read and write operations for the ``training_goals`` table.

    The ``one active goal per athlete`` invariant is enforced at the DB
    layer via the partial unique index
    ``ix_training_goals_athlete_active`` — a second ``add`` of a goal
    with ``status='active'`` for the same athlete raises an
    ``IntegrityError`` (PostgreSQL ``23505``). Callers map that to
    ``TrainingGoalConflictError`` → HTTP 409.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, athlete_id: uuid.UUID) -> Optional[TrainingGoal]:
        result = await self.session.execute(
            select(TrainingGoal).where(
                TrainingGoal.athlete_id == athlete_id,
                TrainingGoal.status == TrainingGoalStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, goal_id: uuid.UUID) -> Optional[TrainingGoal]:
        result = await self.session.execute(
            select(TrainingGoal).where(TrainingGoal.id == goal_id)
        )
        return result.scalar_one_or_none()

    async def add(self, goal: TrainingGoal) -> TrainingGoal:
        """Add a goal to the session without committing.

        Caller is responsible for committing the surrounding transaction.
        """
        self.session.add(goal)
        await self.session.flush()
        await self.session.refresh(goal)
        return goal
