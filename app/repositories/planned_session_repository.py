"""PlannedSessionRepository — operability row lookups for workout generation.

Implements the read surface required by ``WorkoutGenerationAgent``
(Phase-1.5b). This repository is read-only — ``PlannedSession`` rows
are written by :class:`PlanGenerationService` (Phase-1.4) and never
mutated afterward.

The staleness invariant from the architecture contract:

* ``PlannedSession.training_plan_id`` is DENORMALIZED. After plan
  supersession, existing rows retain the old id while the source of
  truth moves to ``WeeklyPlan.training_plan_id``. Every "current
  plan session" lookup MUST join through ``WeeklyPlan.training_plan_id``
  so denormalization drift cannot surface a stale plan's sessions.

Today-path resolution:

* ``get_today_for_athlete`` joins ``PlannedSession → WeeklyPlan →
  TrainingPlan`` and filters by ``TrainingPlan.status = 'active'``
  plus ``PlannedSession.target_date = target_date``. Ordered by
  ``session_slot ASC`` so an AM session precedes a PM session of the
  same day. The join is narrowed to the athlete's active ``TrainingGoal``
  so cross-goal plans cannot leak today's session.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TrainingPlanStatus
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan


class PlannedSessionRepository:
    """Read operations for the ``planned_sessions`` table.

    The repository exposes only lookup methods — workout generation
    is the only writer at runtime, and it generates ``WorkoutStep``
    rows on a parent ``GeneratedWorkout`` rather than mutating the
    ``PlannedSession`` itself. Direct ownership of session writes
    belongs to ``PlanGenerationService`` (Phase-1.4).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self, session_id: uuid.UUID
    ) -> Optional[PlannedSession]:
        """Return the PlannedSession by id, or ``None``.

        Used by ``WorkoutGenerationAgent.generate`` to load the session
        detail before LLM context assembly. The session passed in by
        the API layer is verified to belong to the athlete's active
        plan before this is called.
        """
        result = await self.session.execute(
            select(PlannedSession).where(PlannedSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_today_for_athlete(
        self,
        athlete_id: uuid.UUID,
        target_date: date,
    ) -> List[PlannedSession]:
        """Return today's PlannedSession rows for the athlete's active plan.

        Joins ``PlannedSession → WeeklyPlan → TrainingPlan`` (the
        architecture's "denormalized PlannedSession.training_plan_id
        can be stale after supersession" invariant). Filters
        ``TrainingPlan.status = 'active'``,
        ``PlannedSession.target_date = target_date``, and the
        plan's parent ``TrainingGoal`` belongs to *athlete_id* with
        ``status = 'active'``. Multiple rows may exist for the same
        date (AM/PM double-session days); results are ordered by
        ``session_slot ASC`` so an AM session precedes a PM session
        of the same day, with NULL-slot single-session days ordered
        last by the database.
        """
        result = await self.session.execute(
            select(PlannedSession)
            .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
            .join(TrainingPlan, TrainingPlan.id == WeeklyPlan.training_plan_id)
            .join(TrainingGoal, TrainingGoal.id == TrainingPlan.training_goal_id)
            .where(
                TrainingGoal.athlete_id == athlete_id,
                TrainingGoal.status == "active",
                TrainingPlan.status == TrainingPlanStatus.ACTIVE,
                PlannedSession.target_date == target_date,
            )
            .order_by(PlannedSession.session_slot.asc())
        )
        return list(result.scalars().all())
