"""TrainingPlanRepository — periodised-plan persistence abstraction.

Implements the read/write surface required by
``PlanGenerationService`` and the read-only ``GET /athletes/{id}/plan``
endpoint family.

Atomicity is owned by the service layer. Every method here ``flush()``s
inside the caller's ``AsyncSession`` and never commits — the service
wraps the full hierarchy (TrainingPlan → WeeklyPlan → PlannedSession
→ Checkpoint) plus the supersession of any previous active plan in a
single transaction. Per ADR-004, the ``training_plan_generated``
event/outbox rows also land in that same transaction, owned by the
service.

The "one active plan per goal" invariant is enforced at the
application level — supersession moves a previous active record to
``status='superseded'`` and stamps ``superseded_at`` before the new
plan is inserted. There is no DB-level uniqueness on
``(training_goal_id, status='active')``; the rollback boundary in
the service catches duplicate writes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TrainingPlanStatus
from app.models.training_plan import TrainingPlan


class TrainingPlanRepository:
    """Read and write operations for the ``training_plans`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_for_goal(
        self, training_goal_id: uuid.UUID
    ) -> Optional[TrainingPlan]:
        """Return the currently active plan for *training_goal_id*, or ``None``.

        Used both by the plan router (GET endpoints) and the service
        (supersession lookup before inserting a new plan). The
        composite ``ix_training_plans_goal_status`` index on
        ``(training_goal_id, status)`` supports this lookup without a
        scan.
        """
        result = await self.session.execute(
            select(TrainingPlan).where(
                TrainingPlan.training_goal_id == training_goal_id,
                TrainingPlan.status == TrainingPlanStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_for_athlete(
        self, athlete_id: uuid.UUID
    ) -> Optional[TrainingPlan]:
        """Return the active plan for an athlete's active TrainingGoal.

        Performs a single join against ``training_goals`` to resolve
        the active goal before the plan lookup. ``None`` is returned
        when the athlete has no active goal or no active plan — the
        API layer maps that to HTTP 404.
        """
        from app.models.training_goal import TrainingGoal  # local import: avoid cycle

        result = await self.session.execute(
            select(TrainingPlan)
            .join(
                TrainingGoal,
                TrainingGoal.id == TrainingPlan.training_goal_id,
            )
            .where(
                TrainingGoal.athlete_id == athlete_id,
                TrainingGoal.status == "active",
                TrainingPlan.status == TrainingPlanStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, plan_id: uuid.UUID
    ) -> Optional[TrainingPlan]:
        """Return the TrainingPlan row by id, or ``None``."""
        result = await self.session.execute(
            select(TrainingPlan).where(TrainingPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def add(self, plan: TrainingPlan) -> TrainingPlan:
        """Insert a TrainingPlan within the caller's transaction.

        Flushes (no commit) so the caller's surrounding transaction
        owns the commit boundary. The service inserts the plan after
        flagging the previous active plan as superseded so the new
        row + supersession mutation land atomically.
        """
        self.session.add(plan)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan

    async def supersede(
        self, plan: TrainingPlan, *, superseded_at: Optional[datetime] = None
    ) -> TrainingPlan:
        """Mark *plan* as superseded and stamp ``superseded_at``.

        Flushes (no commit) so the service layer's single transaction
        holds the supersession mutation atomic with the new plan's
        insert. Per the architecture invariants, the row is never
        deleted — ``superseded_at`` is the only mutation applied here.
        """
        plan.status = TrainingPlanStatus.SUPERSEDED
        plan.superseded_at = superseded_at or datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(plan)
        return plan
