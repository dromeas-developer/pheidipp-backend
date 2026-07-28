import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security.token_service import TokenService
from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile


@pytest.fixture
async def athlete_with_profile(db_session: AsyncSession) -> uuid.UUID:
    athlete_id = uuid.uuid4()
    athlete = Athlete(id=athlete_id, email=f"test-{athlete_id}@example.com")
    db_session.add(athlete)
    profile = AthleteProfile(
        athlete_id=athlete_id,
        date_of_birth=date(1990, 1, 15),
        sex="male",
    )
    db_session.add(profile)
    await db_session.flush()
    return athlete_id


async def _issue_token(athlete_id: uuid.UUID, expired: bool = False) -> str:
    svc = TokenService()
    if not expired:
        token, _ = svc.issue_access_token(athlete_id)
        return token

    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1)
    payload = {
        "sub": str(athlete_id),
        "athlete_id": str(athlete_id),
        "iat": now,
        "exp": exp,
        "iss": "pheidipp-api",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


class TestRequireSelf:
    async def test_authenticated_own_jwt_succeeds(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        token = await _issue_token(athlete_with_profile)
        response = await client.get(
            f"/athletes/{athlete_with_profile}/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (200, 404)

    async def test_authenticated_different_athlete_jwt_returns_403(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        token = await _issue_token(athlete_with_profile)
        other_id = uuid.uuid4()
        response = await client.get(
            f"/athletes/{other_id}/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_expired_access_token_returns_401(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        token = await _issue_token(athlete_with_profile, expired=True)
        response = await client.get(
            f"/athletes/{athlete_with_profile}/profile",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401

    async def test_missing_authorization_header_returns_401(self, client: AsyncClient):
        response = await client.get(f"/athletes/{uuid.uuid4()}/profile")
        assert response.status_code == 401
