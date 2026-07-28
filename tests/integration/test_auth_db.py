import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.utils.email_utils import normalize_email


class TestEmailUniqueness:
    async def test_duplicate_email_rejected_with_integrity_error(
        self, db_session: AsyncSession
    ):
        email = "dup@example.com"
        athlete1 = Athlete(id=uuid.uuid4(), email=email)
        db_session.add(athlete1)
        await db_session.flush()

        athlete2 = Athlete(id=uuid.uuid4(), email=email)
        db_session.add(athlete2)
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.flush()

        assert getattr(exc_info.value.orig, "pgcode", None) == "23505"

    async def test_case_insensitive_email_uniqueness(self, db_session: AsyncSession):
        normalized = normalize_email("User@Example.com")
        assert normalized == "user@example.com"

        athlete1 = Athlete(id=uuid.uuid4(), email=normalized)
        db_session.add(athlete1)
        await db_session.flush()

        athlete2 = Athlete(id=uuid.uuid4(), email="user@example.com")
        db_session.add(athlete2)
        with pytest.raises(IntegrityError) as exc_info:
            await db_session.flush()

        assert getattr(exc_info.value.orig, "pgcode", None) == "23505"
