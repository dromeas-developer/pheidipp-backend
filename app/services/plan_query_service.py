"""Read-only query surface for plan-related endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkpoint import Checkpoint
from app.models.planned_session import PlannedSession
from app.models.weekly_plan import WeeklyPlan


class PlanQueryService:
    """Own the read queries behind the plan API surface.

    Constructed with the per-request ``AsyncSession`` so every method
    participates in the caller's transaction. The service is
    read-only — it never commits, never calls ``EventPublisher``, and
    never mutates state. Route handlers receive the service via the
    ``build_plan_query_service`` FastAPI dependency and stay out of
    SQL building per the stack-truth layer rule
    (``api → services → repositories → models``: no direct
    SQLAlchemy execution in route handlers).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_sessions_for_plan(
        self, plan_id: uuid.UUID
    ) -> List[PlannedSession]:
        """Return all ``PlannedSession`` rows for *plan_id*.

        Joins ``PlannedSession → WeeklyPlan`` on
        ``weekly_plan_id`` and filters by
        ``WeeklyPlan.training_plan_id == plan_id``. The
        staleness-safe join is required because
        ``PlannedSession.training_plan_id`` is a denormalised
        column that can drift after plan supersession; the
        canonical relationship is via ``WeeklyPlan.training_plan_id``.
        """
        result = await self.session.execute(
            select(PlannedSession)
            .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
            .where(WeeklyPlan.training_plan_id == plan_id)
            .order_by(
                PlannedSession.target_date.asc(),
                PlannedSession.session_slot.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_upcoming_sessions(
        self,
        *,
        plan_id: uuid.UUID,
        limit: int = 5,
    ) -> List[PlannedSession]:
        """Return the next *limit* planned sessions from today onward.

        Caller resolves the active plan id (the route handler
        already does this for the 404 short-circuit) and passes it
        here. Filters by ``target_date >= today``, ordered
        chronologically with ``session_slot`` as a tie-breaker, and
        capped at *limit* (default 5). The
        staleness-safe join through ``WeeklyPlan.training_plan_id``
        is the same pattern :meth:`get_sessions_for_plan` uses.
        """
        today = datetime.now(timezone.utc).date()
        result = await self.session.execute(
            select(PlannedSession)
            .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
            .where(
                WeeklyPlan.training_plan_id == plan_id,
                PlannedSession.target_date >= today,
            )
            .order_by(
                PlannedSession.target_date.asc(),
                PlannedSession.session_slot.asc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_checkpoints_for_plan(
        self, plan_id: uuid.UUID
    ) -> List[Checkpoint]:
        """Return all ``Checkpoint`` rows attached to *plan_id*.

        Joins ``Checkpoint → PlannedSession → WeeklyPlan`` and
        filters by ``WeeklyPlan.training_plan_id == plan_id`` so
        checkpoints whose parent ``PlannedSession`` was superseded
        are not returned.
        """
        result = await self.session.execute(
            select(Checkpoint)
            .join(
                PlannedSession,
                PlannedSession.id == Checkpoint.planned_session_id,
            )
            .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
            .where(WeeklyPlan.training_plan_id == plan_id)
            .order_by(PlannedSession.target_date.asc())
        )
        return list(result.scalars().all())


__all__ = ["PlanQueryService"]
