"""Integration test for the IP-discard background task.

Validates:

* Task is idempotent — running it twice discards only on the first
  pass.
* Task commits its own transaction (callers don't need to).
* Task honours a custom ``retention_days`` override.

The implementation under test opens its own ``AsyncSession`` (see
``app/tasks/discard_refresh_token_ips.py``) which is a different
transaction from the per-test ``db_session`` fixture. This means the
test must explicitly commit the seeded rows so the task's separate
session can see them. Schemas are dropped at the end of the
pytest session, so per-test row leakage is not a correctness
concern — the uniqe-id pattern in the helpers makes cross-test
collisions essentially impossible.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.refresh_token import RefreshToken
from app.repositories.refresh_token_repository import RefreshTokenRepository
import app.tasks.discard_refresh_token_ips as task_module


async def _make_athlete(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(email=f"athlete-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def _make_old_token(
    db_session: AsyncSession, athlete: Athlete, days_old: int
) -> RefreshToken:
    """Create + flush + return a token. ``created_at`` is set in memory."""
    token = RefreshToken(
        athlete_id=athlete.id,
        token_hash=f"hash-{uuid.uuid4()}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        ip_address="198.51.100.42",
    )
    token.created_at = datetime.now(timezone.utc) - timedelta(days=days_old)
    db_session.add(token)
    await db_session.flush()
    return token


class TestDiscardRefreshTokenIpsTask:
    """End-to-end behaviour of the periodic cleanup task."""

    async def test_task_discards_ips_older_than_seven_days(
        self,
        db_session: AsyncSession,
        test_session_local,
        monkeypatch,
    ) -> None:
        athlete = await _make_athlete(db_session)
        token = await _make_old_token(db_session, athlete, days_old=8)
        await db_session.commit()  # make rows visible to the task session

        # Keep the task on the per-test engine/session factory so asyncpg
        # connections are bound to the current pytest-asyncio event loop.
        monkeypatch.setattr(task_module, "AsyncSessionLocal", test_session_local)

        try:
            count = await task_module.discard_refresh_token_ips()
            assert count >= 1

            # Capture the token hash before expiring, then re-query to verify
            # the task's commit is visible from this session.
            token_hash = token.token_hash
            db_session.expire(token)
            repo = RefreshTokenRepository(db_session)
            refreshed = await repo.get_by_token_hash(token_hash)
            assert refreshed is not None
            assert refreshed.ip_address is None
        finally:
            await db_session.rollback()

    async def test_task_preserves_ip_freshly(
        self,
        db_session: AsyncSession,
        test_session_local,
        monkeypatch,
    ) -> None:
        """Rows whose age is well within the retention window are untouched."""
        athlete = await _make_athlete(db_session)
        token = await _make_old_token(db_session, athlete, days_old=2)
        await db_session.commit()

        # Keep the task on the per-test engine/session factory so asyncpg
        # connections are bound to the current pytest-asyncio event loop.
        monkeypatch.setattr(task_module, "AsyncSessionLocal", test_session_local)

        try:
            await task_module.discard_refresh_token_ips()

            # Capture the token hash before expiring, then re-query to verify
            # the task's commit is visible from this session.
            token_hash = token.token_hash
            db_session.expire(token)
            repo = RefreshTokenRepository(db_session)
            refreshed = await repo.get_by_token_hash(token_hash)
            # Row unchanged — IP still present.
            assert refreshed is not None
            assert refreshed.ip_address == "198.51.100.42"
        finally:
            await db_session.rollback()

    async def test_task_is_idempotent(
        self,
        db_session: AsyncSession,
        test_session_local,
        monkeypatch,
    ) -> None:
        athlete = await _make_athlete(db_session)
        token = await _make_old_token(db_session, athlete, days_old=8)
        await db_session.commit()

        # Keep the task on the per-test engine/session factory so asyncpg
        # connections are bound to the current pytest-asyncio event loop.
        monkeypatch.setattr(task_module, "AsyncSessionLocal", test_session_local)

        try:
            first_run = await task_module.discard_refresh_token_ips()
            second_run = await task_module.discard_refresh_token_ips()

            # Second pass must report zero rows touched.
            # And the first run must have done at least one — sanity.
            assert second_run == 0
            assert first_run >= 1

            # Capture the token hash before expiring, then re-query to verify
            # the task's commit is visible from this session.
            token_hash = token.token_hash
            db_session.expire(token)
            repo = RefreshTokenRepository(db_session)
            refreshed = await repo.get_by_token_hash(token_hash)
            assert refreshed is not None
            assert refreshed.ip_address is None
        finally:
            await db_session.rollback()

    async def test_task_honours_custom_retention_days(
        self,
        db_session: AsyncSession,
        test_session_local,
        monkeypatch,
    ) -> None:
        athlete = await _make_athlete(db_session)
        # Two-day-old token under a 1-day retention window should be
        # discarded; under the default 7-day window it would be kept.
        token = await _make_old_token(db_session, athlete, days_old=2)
        await db_session.commit()

        # Keep the task on the per-test engine/session factory so asyncpg
        # connections are bound to the current pytest-asyncio event loop.
        monkeypatch.setattr(task_module, "AsyncSessionLocal", test_session_local)

        try:
            await task_module.discard_refresh_token_ips(retention_days=1)

            # Capture the token hash before expiring, then re-query to verify
            # the task's commit is visible from this session.
            token_hash = token.token_hash
            db_session.expire(token)
            repo = RefreshTokenRepository(db_session)
            refreshed = await repo.get_by_token_hash(token_hash)
            assert refreshed is not None
            assert refreshed.ip_address is None
        finally:
            await db_session.rollback()
