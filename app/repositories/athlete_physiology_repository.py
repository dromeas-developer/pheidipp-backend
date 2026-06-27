"""AthletePhysiologyRepository — posterior threshold state lookups and writes."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_physiology import AthletePhysiology


class AthletePhysiologyRepository:
    """Read and write operations for the ``athlete_physiology`` table.

    One ``AthletePhysiology`` row per athlete — enforced by the
    ``uq_athlete_physiology_athlete`` ``UNIQUE`` index. The
    Phase-1.3 onboarding bootstrap is the first writer; the
    Phase-1.6 ``PhysiologyUpdateService`` performs all subsequent
    updates in place.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_athlete_id(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthletePhysiology]:
        result = await self.session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.athlete_id == athlete_id
            )
        )
        return result.scalar_one_or_none()

    async def add(
        self, physiology: AthletePhysiology
    ) -> AthletePhysiology:
        """Add a physiology row to the session without committing."""
        self.session.add(physiology)
        await self.session.flush()
        await self.session.refresh(physiology)
        return physiology
