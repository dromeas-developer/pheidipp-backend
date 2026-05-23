import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """Repository for refresh token data access."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        athlete_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        device_hint: Optional[str] = None,
    ) -> RefreshToken:
        """Create a new refresh token."""
        token = RefreshToken(
            athlete_id=athlete_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_hint=device_hint,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_active_by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        """Get an active (non-revoked, non-expired) token by its hash.
        
        Uses FOR UPDATE to lock the row during refresh operations.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .where(RefreshToken.revoked_at.is_(None))
            .where(RefreshToken.expires_at > now)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, token_id: uuid.UUID) -> None:
        """Revoke a token by setting its revoked_at timestamp."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def touch(self, token_id: uuid.UUID) -> None:
        """Update last_used_at timestamp for an active token."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.id == token_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_for_athlete(self, athlete_id: uuid.UUID) -> None:
        """Revoke all active tokens for an athlete."""
        now = datetime.now(timezone.utc)
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.athlete_id == athlete_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def count_active_for_athlete(self, athlete_id: uuid.UUID) -> int:
        """Count active (non-revoked, non-expired) tokens for an athlete."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(func.count(RefreshToken.id))
            .where(RefreshToken.athlete_id == athlete_id)
            .where(RefreshToken.revoked_at.is_(None))
            .where(RefreshToken.expires_at > now)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0