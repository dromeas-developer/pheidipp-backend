"""AthleteFitnessRepository — Banister rolling fitness/fatigue lookups and writes."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_fitness import AthleteFitness


class AthleteFitnessRepository:
    """Read and write operations for the ``athlete_fitness`` table.

    One ``AthleteFitness`` row per athlete — enforced by the
    ``uq_athlete_fitness_athlete`` ``UNIQUE`` index. The
    Phase-1.3 onboarding bootstrap is the first writer; the
    Phase-1.6 ``FitnessUpdateService`` performs all subsequent
    updates in place. The ``form = fitness - fatigue`` invariant is
    enforced at the DB layer by ``CheckConstraint`` on every populated
    dimensional block plus the aggregate.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_athlete_id(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthleteFitness]:
        result = await self.session.execute(
            select(AthleteFitness).where(AthleteFitness.athlete_id == athlete_id)
        )
        return result.scalar_one_or_none()

    async def add(self, fitness: AthleteFitness) -> AthleteFitness:
        """Add a fitness row to the session without committing."""
        self.session.add(fitness)
        await self.session.flush()
        await self.session.refresh(fitness)
        return fitness
