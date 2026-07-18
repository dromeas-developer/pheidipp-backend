"""WeeklyPlanRepository — single-week plan persistence abstraction.

Implements the read/write surface for the ``weekly_plans`` and
``weekly_sessions`` tables required by ``PlanGenerationService`` and
the read-only ``GET /athletes/{id}/plan``-family endpoints.

Both insert paths here perform a single ``flush()`` per call (no
commit) so the service layer can compose the full plan hierarchy in
one transaction. Reading sessions catalog-style for the API layer
joins directly through ``WeeklyPlan.training_plan_id`` per the
architecture's "denormalized PlannedSession.training_plan_id can
go stale" invariant.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weekly_plan import WeeklyPlan, WeeklySession


class WeeklyPlanRepository:
    """Read and write operations for the ``weekly_plans`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(
        self, weekly_plans: List[WeeklyPlan]
    ) -> List[WeeklyPlan]:
        """Insert multiple WeeklyPlan rows in one flush.

        ``PlanGenerationService`` synthesises a WeeklyPlan per week of
        the plan and inserts the full collection in one call so the
        surrounding transaction sees a single SQL flush boundary for
        the entire weekly layer. ``commit()`` is owned by the caller.
        """
        for weekly_plan in weekly_plans:
            self.session.add(weekly_plan)
        await self.session.flush()
        for weekly_plan in weekly_plans:
            await self.session.refresh(weekly_plan)
        return weekly_plans

    async def get_for_training_plan(
        self, training_plan_id: uuid.UUID
    ) -> List[WeeklyPlan]:
        """Return all WeeklyPlans for *training_plan_id*, ordered by week.

        The unique constraint ``uq_weekly_plans_plan_week`` guarantees
        at most one row per ``(training_plan_id, week_number)``; no
        further dedupe is required.
        """
        result = await self.session.execute(
            select(WeeklyPlan)
            .where(WeeklyPlan.training_plan_id == training_plan_id)
            .order_by(WeeklyPlan.week_number.asc())
        )
        return list(result.scalars().all())

    async def get_by_plan_and_week(
        self,
        training_plan_id: uuid.UUID,
        week_number: int,
    ) -> Optional[WeeklyPlan]:
        """Return the WeeklyPlan for ``(training_plan_id, week_number)``.

        Used by recovery paths that need to look up a specific week
        (e.g. the weekly-synthesis agent that lands in Phase 2+). The
        ``uq_weekly_plans_plan_week`` unique index makes this O(1).
        """
        result = await self.session.execute(
            select(WeeklyPlan).where(
                WeeklyPlan.training_plan_id == training_plan_id,
                WeeklyPlan.week_number == week_number,
            )
        )
        return result.scalar_one_or_none()


class WeeklySessionRepository:
    """Persistence for the ``weekly_sessions`` table — one row per session.

    Kept in this module because the table shares its parent
    ``WeeklyPlan`` lifecycle with the plan-generation service. The
    service persists ``WeeklySession`` rows immediately after their
    parent ``WeeklyPlan`` is created so the entire hierarchy is
    committed in a single transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_many(self, sessions: List[WeeklySession]) -> List[WeeklySession]:
        """Insert all ``WeeklySession`` rows in one flush (no commit)."""
        for weekly_session in sessions:
            self.session.add(weekly_session)
        await self.session.flush()
        for weekly_session in sessions:
            await self.session.refresh(weekly_session)
        return sessions
