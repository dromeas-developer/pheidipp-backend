"""WorkoutStepRepository — append-only workout segment storage.

Implements the write/read surface required by ``WorkoutGenerationAgent``
(Phase-1.5b) per the architecture contract in
``docs/architecture/01-entities/workout-step.md``.

Atomicity is owned by the agent. Every method here ``flush()``s inside
the caller's ``AsyncSession`` and never commits — the agent wraps
``WorkoutStep`` rows in the same transaction as their parent
``GeneratedWorkout`` row, ``GenerationEvent``, and system-event/outbox
rows. The API route handler calls ``session.commit()`` after
:meth:`WorkoutGenerationAgent.generate` returns.

Ordered retrieval:

* ``get_by_workout`` orders by ``step_order ASC`` using the existing
  ``ix_workout_steps_generated_workout_order`` composite index —
  the unique constraint on ``(generated_workout_id, step_order)``
  guarantees at most one row per order position per workout.

Mutation rules:

* Append-only — no ``update()`` or ``delete()``. A regenerated
  workout creates a new ``WorkoutStep[]`` collection on the new
  ``GeneratedWorkout`` row rather than mutating existing steps.
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workout_step import WorkoutStep


class WorkoutStepRepository:
    """Append-only read/write operations for the ``workout_steps`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert_many(
        self, steps: List[WorkoutStep]
    ) -> List[WorkoutStep]:
        """Insert a batch of WorkoutStep rows in one flush.

        Adds every step to the session, flushes once for the entire
        batch, then refreshes each row so caller-side attributes
        (e.g. defaulted ``session_purpose``) reflect the persisted
        state. Unique-constraint violations surface here as
        ``IntegrityError`` — the agent validates step orders before
        this call so the DB remains the safety net rather than the
        primary check.

        No commit: the surrounding transaction holds the
        ``GeneratedWorkout`` insert, ``GenerationEvent``, system-event
        row, and outbox row atomic with this batch.
        """
        for step in steps:
            self.session.add(step)
        await self.session.flush()
        for step in steps:
            await self.session.refresh(step)
        return steps

    async def get_by_workout(
        self, generated_workout_id: uuid.UUID
    ) -> List[WorkoutStep]:
        """Return all WorkoutStep rows for *generated_workout_id*, ordered by step_order ASC.

        Ordered by ``step_order`` ASC so the API response can emit
        ``WorkoutStepResponse[]`` in sequence without re-sorting. Used
        by the ``GET /athletes/{id}/today`` family and the workout
        history endpoint when those land in later phases.
        """
        result = await self.session.execute(
            select(WorkoutStep)
            .where(WorkoutStep.generated_workout_id == generated_workout_id)
            .order_by(WorkoutStep.step_order.asc())
        )
        return list(result.scalars().all())
