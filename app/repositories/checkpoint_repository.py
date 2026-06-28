"""CheckpointRepository — planned-assessment persistence abstraction.

Implements the read/write surface for the ``checkpoints`` table
required by ``PlanGenerationService`` and the read-only
``GET /athletes/{id}/plan/checkpoints`` endpoint.

The architecture invariant "one checkpoint per PlannedSession" is
enforced at the DB layer by the unique constraint on
``planned_session_id`` on the model itself; the service inserts the
``PlannedSession`` first and then inserts the matching
``Checkpoint`` row referencing it — both inside the same transaction.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkpoint import Checkpoint


class CheckpointRepository:
    """Read and write operations for the ``checkpoints`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(self, checkpoints: List[Checkpoint]) -> List[Checkpoint]:
        """Insert a list of Checkpoint rows in one flush (no commit).

        ``PlanGenerationService`` synthesises one Checkpoint per
        scheduled assessment and calls this method once per plan.
        Each row references a ``PlannedSession`` that the service
        inserted earlier in the same transaction.
        """
        for checkpoint in checkpoints:
            self.session.add(checkpoint)
        await self.session.flush()
        for checkpoint in checkpoints:
            await self.session.refresh(checkpoint)
        return checkpoints

    async def get_for_training_plan(
        self, training_plan_id: uuid.UUID
    ) -> List[Checkpoint]:
        """Return all Checkpoints for *training_plan_id*, ordered by date.

        Joins through ``PlannedSession → WeeklyPlan → TrainingPlan``
        so that checkpoints belonging to superseded plans are
        naturally excluded — the join filters them out via
        ``WeeklyPlan.training_plan_id = :current_plan_id``. The DB
        index ``ix_checkpoints_planned_session`` makes the join
        point-lookup fast.
        """
        from app.models.planned_session import PlannedSession  # local import — avoid cycle
        from app.models.weekly_plan import WeeklyPlan  # local import — avoid cycle

        result = await self.session.execute(
            select(Checkpoint)
            .join(PlannedSession, PlannedSession.id == Checkpoint.planned_session_id)
            .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
            .where(WeeklyPlan.training_plan_id == training_plan_id)
            .order_by(PlannedSession.target_date.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, checkpoint_id: uuid.UUID
    ) -> Optional[Checkpoint]:
        """Return the Checkpoint by id, or ``None``."""
        result = await self.session.execute(
            select(Checkpoint).where(Checkpoint.id == checkpoint_id)
        )
        return result.scalar_one_or_none()
