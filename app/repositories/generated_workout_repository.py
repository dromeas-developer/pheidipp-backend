"""GeneratedWorkoutRepository — append-only day-of workout storage.

Implements the write/read surface required by ``WorkoutGenerationAgent``
(Phase-1.5b) per the architecture contract in
``docs/architecture/01-entities/generated-workout.md``.

Atomicity is owned by the agent. Every method here ``flush()``s inside
the caller's ``AsyncSession`` and never commits — the agent wraps the
full hierarchy (``GeneratedWorkout`` → ``WorkoutStep[]`` →
``GenerationEvent`` → ``SystemEvent`` → ``SystemEventOutbox``) in a
single transaction. The API route handler calls ``session.commit()``
after :meth:`WorkoutGenerationAgent.generate` returns.

Idempotency:

* The ``uq_generated_workouts_planned_session_generation_date`` unique
  constraint enforces "at most one row per
  ``(planned_session_id, generation_date)``". The
  ``get_by_session_and_date`` lookup supports the agent's idempotency
  gate — when a workout already exists, the agent returns it without
  calling the LLM.

Mutation rules:

* Append-only — no ``update()`` or ``delete()``. A regenerated
  workout creates a new ``GeneratedWorkout`` row with new
  ``WorkoutStep`` rows.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_workout import GeneratedWorkout


class GeneratedWorkoutRepository:
    """Append-only read/write operations for the ``generated_workouts`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(self, workout: GeneratedWorkout) -> GeneratedWorkout:
        """Append a new GeneratedWorkout to the session without committing.

        This is the ONLY write method exposed by the repository. Per
        the architecture contract, ``GeneratedWorkout`` rows are
        append-only — regeneration produces a new row rather than
        mutating an existing one. Caller owns the commit boundary so
        the flush participates in the same transaction as the
        companion ``WorkoutStep`` rows, ``GenerationEvent``, and
        system-event/outbox rows.
        """
        self.session.add(workout)
        await self.session.flush()
        await self.session.refresh(workout)
        return workout

    async def get_by_session_and_date(
        self,
        planned_session_id: uuid.UUID,
        generation_date: date,
    ) -> Optional[GeneratedWorkout]:
        """Return the existing GeneratedWorkout for the idempotency key.

        Backed by the ``uq_generated_workouts_planned_session_generation_date``
        unique constraint — the lookup is O(1). ``None`` when no
        workout exists for ``(planned_session_id, generation_date)``
        yet; ``WorkoutGenerationAgent`` treats that as the "no prior
        generation" branch and proceeds with LLM-driven generation.
        """
        result = await self.session.execute(
            select(GeneratedWorkout).where(
                GeneratedWorkout.planned_session_id == planned_session_id,
                GeneratedWorkout.generation_date == generation_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_planned_session(
        self, planned_session_id: uuid.UUID
    ) -> list[GeneratedWorkout]:
        """Return all GeneratedWorkouts for *planned_session_id*, newest first.

        Ordered by ``generated_at DESC`` so the most recent generation
        comes first — multiple rows can exist when the agent is
        rerun across dates for the same session (idempotency is per
        ``(planned_session_id, generation_date)``, not per session).
        """
        result = await self.session.execute(
            select(GeneratedWorkout)
            .where(GeneratedWorkout.planned_session_id == planned_session_id)
            .order_by(GeneratedWorkout.generated_at.desc())
        )
        return list(result.scalars().all())
