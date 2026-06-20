"""Integration tests for the athlete and athlete-auth repositories.

Covers the Phase-1.1 invariants at the persistence boundary:

* Email uniqueness is in lowercase canonical form.
* ``is_unique_violation`` correctly identifies a 23505 violation.
* Password touches (``last_login_at``) update atomically.
* Email-provider lookup joins on the case-normalised email column.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.enums import AuthProvider
from app.repositories.athlete_auth_repository import AthleteAuthRepository
from app.repositories.athlete_repository import AthleteRepository


class TestAthleteRepositoryEmailLookup:
    """Email lookup is case-sensitive at the column level — we always
    canonicalise before lookup."""

    async def test_lookup_canonicalised_email(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="athlete@example.com")
        db_session.add(athlete)
        await db_session.flush()

        repo = AthleteRepository(db_session)
        # Service code always invokes ``.lower().strip()``; the repo
        # also normalises defensively.
        result = await repo.get_by_normalized_email("  athlete@example.com  ")
        assert result is not None
        assert result.id == athlete.id

    async def test_email_exists_returns_true_for_match(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="exists@example.com")
        db_session.add(athlete)
        await db_session.flush()

        repo = AthleteRepository(db_session)
        assert await repo.email_exists("exists@example.com") is True
        assert await repo.email_exists("missing@example.com") is False

    async def test_get_by_id_returns_none_when_missing(
        self, db_session: AsyncSession
    ) -> None:
        repo = AthleteRepository(db_session)
        assert await repo.get_by_id(uuid.uuid4()) is None


class TestAthleteRepositoryUniqueViolation:
    """The DB-enforced unique index ``ix_athletes_lower_email_unique``
    must surface as an ``IntegrityError`` whose Postgres code is 23505."""

    async def test_lowercase_email_is_uniquely_enforced(
        self, db_session: AsyncSession
    ) -> None:
        a = Athlete(email="athlete@example.com")
        b = Athlete(email="athlete@example.com")  # identical
        db_session.add(a)
        await db_session.flush()
        db_session.add(b)
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.flush()
        assert AthleteRepository.is_unique_violation(exc_info.value) is True
        await db_session.rollback()


class TestAthleteAuthRepository:
    """Email-provider credential lookups and ``last_login_at`` updates."""

    async def test_get_email_auth_by_normalized_email(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="athlete@example.com")
        db_session.add(athlete)
        await db_session.flush()
        auth = AthleteAuth(
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            hashed_password="$2b$12$abcdef",
            is_primary=True,
        )
        db_session.add(auth)
        await db_session.flush()

        repo = AthleteAuthRepository(db_session)
        result = await repo.get_email_auth_by_normalized_email(
            "athlete@example.com"
        )
        assert result is not None
        assert result.provider == AuthProvider.EMAIL

    async def test_get_email_auth_returns_none_for_missing(
        self, db_session: AsyncSession
    ) -> None:
        repo = AthleteAuthRepository(db_session)
        assert await repo.get_email_auth_by_normalized_email(
            "no-such-email@example.com"
        ) is None

    async def test_get_by_athlete_and_provider(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="athlete@example.com")
        db_session.add(athlete)
        await db_session.flush()
        auth = AthleteAuth(
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            hashed_password="$2b$12$abcdef",
            is_primary=True,
        )
        db_session.add(auth)
        await db_session.flush()

        repo = AthleteAuthRepository(db_session)
        result = await repo.get_by_athlete_and_provider(
            athlete.id, AuthProvider.EMAIL
        )
        assert result is not None
        assert result.athlete_id == athlete.id

    async def test_touch_last_login_sets_field(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email="athlete@example.com")
        db_session.add(athlete)
        await db_session.flush()
        auth = AthleteAuth(
            athlete_id=athlete.id,
            provider=AuthProvider.EMAIL,
            hashed_password="$2b$12$abcdef",
            is_primary=True,
        )
        db_session.add(auth)
        await db_session.flush()
        assert auth.last_login_at is None

        repo = AthleteAuthRepository(db_session)
        await repo.touch_last_login(auth)
        assert auth.last_login_at is not None
        assert auth.last_login_at.tzinfo is not None
        # Should be within the last few seconds.
        now = datetime.now(timezone.utc)
        assert (now - auth.last_login_at).total_seconds() < 5
