"""AthleteProfileRepository — minimal demographic profile lookups and writes."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_profile import AthleteProfile


class AthleteProfileRepository:
    """Read and write operations for the ``athlete_profiles`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_athlete_id(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthleteProfile]:
        result = await self.session.execute(
            select(AthleteProfile).where(AthleteProfile.athlete_id == athlete_id)
        )
        return result.scalar_one_or_none()

    async def add(self, profile: AthleteProfile) -> AthleteProfile:
        """Add a profile to the session without committing."""
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile
