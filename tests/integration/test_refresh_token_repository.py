"""Integration tests for the RefreshToken repository.

Validates the append-only revocation-ledger semantics:

* ``add`` persists a token and returns the resulting row.
* ``is_active`` rejects revoked and expired rows; both checks fire
  independently.
* ``discard_old_ips`` enforces the 7-day IP-retention invariant from
  ADR-005: rows older than 7 days have ``ip_address`` zeroed while
  everything else (token hash, expiry, replacement linkage) remains
  intact.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.refresh_token import RefreshToken
from app.repositories.refresh_token_repository import RefreshTokenRepository


async def _make_athlete(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(email=f"athlete-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def _make_token(
    db_session: AsyncSession,
    athlete: Athlete,
    *,
    created_at: datetime | None = None,
    ip_address: str | None = "192.0.2.1",
    revoked_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> RefreshToken:
    """Create + flush + return a token. ``created_at`` is set in memory.

    ``created_at`` cannot be overridden via SQLAlchemy defaults so we set
    it in Python before ``flush`` — production code only ever inserts
    new tokens with the server default.
    """
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    token = RefreshToken(
        athlete_id=athlete.id,
        token_hash=f"hash-{uuid.uuid4()}",
        expires_at=expires_at,
        ip_address=ip_address,
        revoked_at=revoked_at,
    )
    if created_at is not None:
        token.created_at = created_at
    db_session.add(token)
    await db_session.flush()
    return token


class TestAdd:
    """``add`` persists a token and returns the row with a primary key."""

    async def test_add_populates_primary_key(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        repo = RefreshTokenRepository(db_session)
        token = await repo.add(
            RefreshToken(
                athlete_id=athlete.id,
                token_hash=f"hash-{uuid.uuid4()}",
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
        )
        assert token.id is not None


class TestIsActive:
    """``is_active`` requires both un-revoked and un-expired."""

    async def test_brand_new_token_is_active(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        token = await _make_token(db_session, athlete)
        assert RefreshTokenRepository.is_active(token) is True

    async def test_revoked_token_is_inactive(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        token = await _make_token(
            db_session,
            athlete,
            revoked_at=datetime.now(timezone.utc),
        )
        assert RefreshTokenRepository.is_active(token) is False

    async def test_expired_token_is_inactive(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        token = await _make_token(db_session, athlete, expires_at=past)
        assert RefreshTokenRepository.is_active(token) is False


class TestDiscardOldIps:
    """The 7-day retention window (ADR-005): IPs are dropped at the boundary."""

    async def test_ip_discarded_after_seven_days(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
        token = await _make_token(
            db_session,
            athlete,
            created_at=eight_days_ago,
            ip_address="192.0.2.1",
        )
        token_hash = token.token_hash  # Capture before any operations

        repo = RefreshTokenRepository(db_session)
        await repo.discard_old_ips()
        await db_session.flush()

        # Query fresh to verify the change
        refreshed = await repo.get_by_token_hash(token_hash)
        assert refreshed is not None
        assert refreshed.ip_address is None
        # Everything else (hash, expiry) must be preserved.
        assert refreshed.token_hash.startswith("hash-")
        assert refreshed.expires_at is not None

    async def test_ip_preserved_at_six_days(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        six_days_ago = datetime.now(timezone.utc) - timedelta(days=6)
        token = await _make_token(
            db_session,
            athlete,
            created_at=six_days_ago,
            ip_address="10.0.0.1",
        )

        repo = RefreshTokenRepository(db_session)
        await repo.discard_old_ips()

        # 6-day-old row sits inside the retention window — IP must
        # still be present.
        assert token.ip_address == "10.0.0.1"

    async def test_discard_is_idempotent(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
        token = await _make_token(
            db_session,
            athlete,
            created_at=eight_days_ago,
            ip_address="192.0.2.99",
        )

        repo = RefreshTokenRepository(db_session)
        first = await repo.discard_old_ips()
        # Re-running should produce a zero rowcount — IPs are already
        # NULL.
        second = await repo.discard_old_ips()
        await db_session.flush()

        assert first == 1
        assert second == 0
        assert token.ip_address is None

    async def test_discard_custom_retention_window(
        self, db_session: AsyncSession
    ) -> None:
        """Custom retention_days is honoured (e.g., for tests / shorter windows)."""
        athlete = await _make_athlete(db_session)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        token = await _make_token(
            db_session,
            athlete,
            created_at=two_days_ago,
            ip_address="203.0.113.7",
        )

        repo = RefreshTokenRepository(db_session)
        count = await repo.discard_old_ips(retention_days=1)
        await db_session.flush()

        assert count == 1
        assert token.ip_address is None


class TestGetByAthleteId:
    """``get_by_athlete_id`` returns all tokens for an athlete."""

    async def test_returns_all_tokens_for_athlete(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        await _make_token(db_session, athlete)
        await _make_token(db_session, athlete)
        await _make_token(db_session, athlete)

        repo = RefreshTokenRepository(db_session)
        tokens = await repo.get_by_athlete_id(athlete.id)
        assert len(tokens) == 3
