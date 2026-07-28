"""RefreshTokenRepository — append-only ledger lookups and writes."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """Read and write operations for the ``athlete_refresh_tokens`` table."""

    # 7-day IP retention window (ADR-005).
    IP_RETENTION_DAYS = 7

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_token_hash(self, token_hash: str) -> Optional[RefreshToken]:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_athlete_id(self, athlete_id: uuid.UUID) -> list[RefreshToken]:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.athlete_id == athlete_id)
        )
        return list(result.scalars().all())

    async def add(self, token: RefreshToken) -> RefreshToken:
        """Add a refresh token to the session without committing."""
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def discard_old_ips(
        self,
        *,
        retention_days: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> int:
        """Null out ``ip_address`` on rows older than the retention window.

        Implements the storage-retention half of ADR-005: the raw IP is
        kept in the table for ``retention_days`` (default 7) so security
        analysis can still correlate short-lived session activity, and
        then dropped to ``NULL`` while leaving the rest of the revocation
        record (hashed token, expiry, replacement link) intact.

        Returns the number of rows updated. Callers control the
        transaction boundary — this method flushes but does not commit.
        """
        days = retention_days if retention_days is not None else self.IP_RETENTION_DAYS
        anchor = now or datetime.now(timezone.utc)
        cutoff = anchor - timedelta(days=days)
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.ip_address.is_not(None),
                RefreshToken.created_at < cutoff,
            )
            .values(ip_address=None)
            .execution_options(synchronize_session="fetch")
        )
        cursor_result = cast("CursorResult[Any]", result)
        return cursor_result.rowcount

    @staticmethod
    def is_active(token: RefreshToken, now: Optional[datetime] = None) -> bool:
        """True when token is un-revoked and not yet expired."""
        anchor = now or datetime.now(timezone.utc)
        if token.revoked_at is not None:
            return False
        if token.expires_at <= anchor:
            return False
        return True
