"""AthletePreferencesRepository — mutable training configuration lookups/writes."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_preferences import AthletePreferences


class AthletePreferencesRepository:
    """Read and write operations for the ``athlete_preferences`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_athlete_id(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthletePreferences]:
        result = await self.session.execute(
            select(AthletePreferences).where(
                AthletePreferences.athlete_id == athlete_id
            )
        )
        return result.scalar_one_or_none()

    async def add(self, preferences: AthletePreferences) -> AthletePreferences:
        """Add a preferences row to the session without committing."""
        self.session.add(preferences)
        await self.session.flush()
        await self.session.refresh(preferences)
        return preferences
