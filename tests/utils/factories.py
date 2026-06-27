"""Shared test factories for creating domain model instances.

These are async helpers that use the per-test db_session fixture.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.enums import AuthProvider

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken


async def make_athlete(db_session, email: str | None = None) -> Athlete:
    """Create and flush an Athlete with a unique email."""
    if email is None:
        email = f"athlete-{uuid.uuid4()}@example.com"
    athlete = Athlete(email=email)
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def make_auth(
    db_session,
    *,
    athlete_id: uuid.UUID,
    provider: AuthProvider = AuthProvider.EMAIL,
    is_primary: bool = True,
) -> AthleteAuth:
    """Create and flush an AthleteAuth row."""
    auth = AthleteAuth(
        athlete_id=athlete_id,
        provider=provider,
        is_primary=is_primary,
    )
    db_session.add(auth)
    await db_session.flush()
    return auth


async def make_refresh_token(
    db_session,
    athlete_id: uuid.UUID,
    *,
    token_hash: str | None = None,
    ip_address: str | None = None,
    expires_at: datetime | None = None,
) -> "RefreshToken":
    """Create a RefreshToken row with sensible defaults."""
    if token_hash is None:
        token_hash = f"hash-{uuid.uuid4()}"

    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    from app.models.refresh_token import RefreshToken

    token = RefreshToken(
        athlete_id=athlete_id,
        token_hash=token_hash,
        expires_at=expires_at,
        ip_address=ip_address,
    )
    db_session.add(token)
    await db_session.flush()
    return token
