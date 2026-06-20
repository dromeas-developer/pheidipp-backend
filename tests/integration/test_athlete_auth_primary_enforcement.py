"""Integration test for the Phase-1.1-P3 single-primary Auth invariant.

These tests assert the database-level enforcement established by
migration ``fd373abd4b9e``:

* The partial unique index ``ix_athlete_auths_single_primary`` rejects
  a second ``AthleteAuth`` row with ``is_primary = true`` for the same
  athlete.
* Multiple non-primary rows for the same athlete are permitted (they
  fall outside the index predicate).
* The constraint fires only when ``is_primary = true``.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.enums import AuthProvider


async def _make_athlete(db_session: AsyncSession) -> Athlete:
    athlete = Athlete(email=f"athlete-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()
    return athlete


async def _make_auth(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    provider: AuthProvider,
    is_primary: bool,
) -> AthleteAuth:
    auth = AthleteAuth(
        athlete_id=athlete_id,
        provider=provider,
        is_primary=is_primary,
    )
    db_session.add(auth)
    await db_session.flush()
    return auth


class TestSinglePrimaryEnforcement:
    """The DB index prevents two primaries per athlete."""

    async def test_first_primary_succeeds(self, db_session: AsyncSession) -> None:
        athlete = await _make_athlete(db_session)
        # First primary insert succeeds.
        await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            is_primary=True,
        )
        # No exception means success.

    async def test_second_primary_raises_integrity_error(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _make_athlete(db_session)
        await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            is_primary=True,
        )
        # Second primary on the same athlete must violate the partial
        # unique index.
        with pytest.raises(IntegrityError):
            await _make_auth(
                db_session,
                athlete_id=athlete.id,
                provider=AuthProvider.GOOGLE,
                is_primary=True,
            )
        await db_session.rollback()

    async def test_multiple_non_primaries_succeed(
        self, db_session: AsyncSession
    ) -> None:
        """The partial index excludes ``is_primary = false`` rows, so
        multiple non-primary methods may coexist on one athlete."""
        athlete = await _make_athlete(db_session)
        await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.GOOGLE,
            is_primary=False,
        )
        # Second non-primary succeeds because the predicate excludes it.
        await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.STRAVA,
            is_primary=False,
        )

    async def test_one_primary_plus_one_non_primary_succeeds(
        self, db_session: AsyncSession
    ) -> None:
        """Sanity: one primary plus a not-primary is permitted."""
        athlete = await _make_athlete(db_session)
        await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            is_primary=True,
        )
        await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.GOOGLE,
            is_primary=False,
        )

    async def test_index_rejects_primary_after_demoting_existing(
        self, db_session: AsyncSession
    ) -> None:
        """Demoting the existing primary flips the partial-index state —
        a new primary must then be allowed, not blocked by stale data."""
        athlete = await _make_athlete(db_session)
        primary = await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            is_primary=True,
        )
        primary.is_primary = False
        await db_session.flush()
        # Now a *different* row can claim the primary.
        replacement = await _make_auth(
            db_session,
            athlete_id=athlete.id,
            provider=AuthProvider.GOOGLE,
            is_primary=True,
        )
        assert replacement.id != primary.id
