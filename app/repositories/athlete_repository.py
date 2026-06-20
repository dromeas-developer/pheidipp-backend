"""AthleteRepository — lookups and writes for the Athlete aggregate."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete


class AthleteRepository:
    """Read and write operations for the ``athletes`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, athlete_id: uuid.UUID) -> Optional[Athlete]:
        result = await self.session.execute(
            select(Athlete).where(Athlete.id == athlete_id)
        )
        return result.scalar_one_or_none()

    async def get_by_normalized_email(
        self, normalized_email: str
    ) -> Optional[Athlete]:
        """Look up an athlete by case-insensitive email match."""
        result = await self.session.execute(
            select(Athlete).where(
                Athlete.email == normalized_email.lower().strip()
            )
        )
        return result.scalar_one_or_none()

    async def add(self, athlete: Athlete) -> Athlete:
        """Add an Athlete to the session without committing.

        Caller is responsible for committing the surrounding transaction.
        """
        self.session.add(athlete)
        await self.session.flush()
        await self.session.refresh(athlete)
        return athlete

    async def email_exists(self, normalized_email: str) -> bool:
        """Return True if an athlete with this lowercase email exists.

        Uses an ``EXISTS`` query — cheaper than selecting the full row when
        the caller only cares about a uniqueness check.
        """
        result = await self.session.execute(
            select(Athlete.id).where(
                Athlete.email == normalized_email.lower().strip()
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def is_unique_violation(error: IntegrityError) -> bool:
        """True if *error* is a 23505 unique-constraint violation."""
        orig = getattr(error, "orig", None)
        pgcode = getattr(orig, "pgcode", None)
        return pgcode == "23505"
