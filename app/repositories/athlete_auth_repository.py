"""AthleteAuthRepository — credential lookups and writes for auth providers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.enums import AuthProvider


class AthleteAuthRepository:
    """Read and write operations for the ``athlete_auths`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_athlete_and_provider(
        self, athlete_id: uuid.UUID, provider: AuthProvider
    ) -> Optional[AthleteAuth]:
        result = await self.session.execute(
            select(AthleteAuth).where(
                AthleteAuth.athlete_id == athlete_id,
                AthleteAuth.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def get_email_auth_by_normalized_email(
        self, normalized_email: str
    ) -> Optional[AthleteAuth]:
        """Look up the email-provider AthleteAuth using a normalized email match.

        Joins ``athletes`` so we read ``lower(email)`` at the application
        layer; the DB-side ``lower(email)`` unique index guarantees that
        the same normalized email maps to the same row.
        """
        result = await self.session.execute(
            select(AthleteAuth)
            .join(Athlete, Athlete.id == AthleteAuth.athlete_id)
            .where(
                AthleteAuth.provider == AuthProvider.EMAIL,
                Athlete.email == normalized_email.lower().strip(),
            )
        )
        return result.scalar_one_or_none()

    async def add(self, auth: AthleteAuth) -> AthleteAuth:
        """Add an AthleteAuth record to the session without committing."""
        self.session.add(auth)
        await self.session.flush()
        await self.session.refresh(auth)
        return auth

    async def touch_last_login(self, auth: AthleteAuth) -> None:
        """Update ``last_login_at`` to *now* and flush, no commit."""
        auth.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()
