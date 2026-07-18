"""HTTP integration tests for the auth API surface.

These tests exercise the FastAPI routes through ``httpx.AsyncClient``
against the real FastAPI app, with the DB session overridden to share
the per-test transaction. They cover:

* ``POST /api/v1/auth/register`` — happy path, duplicate email,
  validation failures, and full-row atomicity.
* ``POST /api/v1/auth/login`` — happy path, wrong password, unknown
  account, validation.
* ``POST /api/v1/auth/refresh`` — happy path, expired/revoked token.
* ``require_self`` — 401 vs 403 distinction, and 200 on a matching
  athlete_id.

The ``require_self`` chain is exercised through the protected
``/_protected/athletes/{athlete_id}/whoami`` sub-app mounted by the
``client`` fixture.
"""

from __future__ import annotations

import time
from uuid import uuid4

import jwt as pyjwt
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.system_event import SystemEvent
from tests.payloads import login_payload, register_payload
from tests.utils.assertions import assert_no_secrets_in_text


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


class TestRegisterEndpoint:
    """``POST /api/v1/auth/register`` — happy + error paths."""

    async def test_register_returns_201_with_token_pair(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        response = await client.post(
            "/api/v1/auth/register", json=register_payload("register@example.com")
        )
        assert response.status_code == 201
        body = response.json()
        # Athlete identity is in the response.
        assert body["athlete"]["email"] == "register@example.com"
        assert body["athlete"]["onboarding_complete"] is False
        # Token pair shape.
        assert "access_token" in body and body["access_token"]
        assert "refresh_token" in body and body["refresh_token"]
        assert body["token_type"] == "bearer"
        assert body["access_token_expires_in"] > 0
        assert body["refresh_token_expires_in"] > 0
        # ``athlete_registered`` event was emitted (committed by the
        # service before this response came back). Verify by inspecting
        # the DB via the test session.
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_registered"
                )
            )
        ).scalars().all()
        assert len(events) == 1

    async def test_register_response_excludes_secrets(
        self, client: AsyncClient
    ) -> None:
        """The response payload must NOT include ``hashed_password``,
        ``token_hash``, ``provider_tokens``, or ``provider_user_id``
        anywhere in its structure."""
        response = await client.post(
            "/api/v1/auth/register",
            json=register_payload("leak-scan@example.com"),
        )
        assert response.status_code == 201
        assert_no_secrets_in_text(response.text, message="/auth/register response")

    async def test_register_duplicate_email_returns_409(
        self, client: AsyncClient
    ) -> None:
        await client.post(
            "/api/v1/auth/register",
            json=register_payload("dup@example.com"),
        )
        # Second attempt with different casing must also fail.
        response = await client.post(
            "/api/v1/auth/register",
            json=register_payload("DUP@example.com"),
        )
        assert response.status_code == 409
        assert "email" in response.json()["detail"].lower()

    async def test_register_validates_email_format(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "ValidPass123!",
                "profile": {
                    "date_of_birth": "1990-01-01",
                    "sex": "not_specified",
                    "height_cm": 175.0,
                },
            },
        )
        assert response.status_code == 422

    async def test_register_validates_password_min_length(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@example.com",
                # "tooshort" is exactly 8 chars and meets ``min_length=8``.
                # We need a string strictly shorter than 8 to trigger 422.
                "password": "short",
                "profile": {
                    "date_of_birth": "1990-01-01",
                    "sex": "not_specified",
                    "height_cm": 175.0,
                },
            },
        )
        assert response.status_code == 422

    async def test_register_validates_profile_height_range(
        self, client: AsyncClient
    ) -> None:
        for height in (10, 500):  # both outside the ge=50, le=300 range
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"h-{height}@example.com",
                    "password": "ValidPass123!",
                    "profile": {
                        "date_of_birth": "1990-01-01",
                        "sex": "not_specified",
                        "height_cm": height,
                    },
                },
            )
            assert response.status_code == 422

    async def test_register_normalises_email_in_response(
        self, client: AsyncClient
    ) -> None:
        """The stored email and the email in the response are both lowercase."""
        response = await client.post(
            "/api/v1/auth/register",
            json=register_payload("MiXedCase@Example.com"),
        )
        assert response.status_code == 201
        assert response.json()["athlete"]["email"] == "mixedcase@example.com"


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    """``POST /api/v1/auth/login``."""

    async def test_login_returns_token_pair(
        self, client: AsyncClient
    ) -> None:
        await client.post(
            "/api/v1/auth/register",
            json=register_payload("login@example.com"),
        )
        response = await client.post(
            "/api/v1/auth/login", json=login_payload("login@example.com")
        )
        assert response.status_code == 200
        body = response.json()
        assert body["athlete"]["email"] == "login@example.com"
        assert body["access_token"]
        assert body["refresh_token"]

    async def test_login_wrong_password_returns_401(
        self, client: AsyncClient
    ) -> None:
        await client.post(
            "/api/v1/auth/register",
            json=register_payload("wrong@example.com"),
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@example.com", "password": "NotTheRightOne"},
        )
        assert response.status_code == 401
        # The error message must NOT reveal whether the email exists.
        detail = response.json()["detail"].lower()
        assert "incorrect" in detail or "wrong" in detail

    async def test_login_unknown_email_returns_401(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "any-password"},
        )
        assert response.status_code == 401

    async def test_login_incorrect_message_is_identical_to_unknown(
        self, client: AsyncClient
    ) -> None:
        """The 401 detail must be byte-identical between wrong-password
        and unknown-email — that's the no-credential-leakage invariant."""
        await client.post(
            "/api/v1/auth/register",
            json=register_payload("known@example.com"),
        )
        wrong = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "known@example.com",
                "password": "definitely-wrong",
            },
        )
        unknown = await client.post(
            "/api/v1/auth/login",
            json={"email": "absent@example.com", "password": "definitely-wrong"},
        )
        assert wrong.status_code == 401
        assert unknown.status_code == 401
        assert wrong.json()["detail"] == unknown.json()["detail"]

    async def test_login_invalidates_request_body_for_email(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "not-an-email", "password": "anything"},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


class TestRefreshEndpoint:
    """``POST /api/v1/auth/refresh``."""

    async def test_refresh_returns_new_token_pair(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("refresh@example.com"),
        )
        register_body = register.json()
        old_refresh = register_body["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert response.status_code == 200
        body = response.json()

        # Security property of rotation: the old refresh token cannot
        # be reused, so the new refresh token MUST be a fresh value.
        # (Access-token strings are not asserted on because they depend
        # on per-issuance ``jti`` UUID, not on the security contract.)
        assert body["refresh_token"] != old_refresh
        assert body["access_token"]

    async def test_refresh_with_revoked_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("replay@example.com"),
        )
        old_refresh = register.json()["refresh_token"]
        # First rotation succeeds.
        await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        )
        # Replay with the same token now fails.
        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert response.status_code == 401

    async def test_refresh_with_unknown_token_returns_401(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "this-token-was-never-issued"},
        )
        assert response.status_code == 401

    async def test_refresh_response_excludes_secrets(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("no-leak-refresh@example.com"),
        )
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": register.json()["refresh_token"]},
        )
        assert response.status_code == 200
        assert_no_secrets_in_text(response.text, message="/auth/refresh response")


# ---------------------------------------------------------------------------
# require_self dependency (mounted at /_protected/athletes/{athlete_id}/whoami)
# ---------------------------------------------------------------------------


class TestRequireSelfEndpoint:
    """``require_self`` is enforced via the protected sub-app."""

    async def test_require_self_returns_200_for_matching_athlete(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("self-ok@example.com"),
        )
        athlete_id = register.json()["athlete"]["id"]
        access_token = register.json()["access_token"]

        response = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        assert response.json()["athlete_id"] == athlete_id

    async def test_require_self_returns_403_on_athlete_mismatch(
        self, client: AsyncClient
    ) -> None:
        """Per the architecture: a JWT for athlete A hitting an
        athlete_id of B must return 403, NEVER 404."""
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("mismatch@example.com"),
        )
        access_token = register.json()["access_token"]
        # A different UUID the JWT does not cover.
        other_id = str(uuid4())

        response = await client.get(
            f"/_protected/athletes/{other_id}/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 403

    async def test_require_self_returns_401_without_authorization_header(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("no-auth-header@example.com"),
        )
        athlete_id = register.json()["athlete"]["id"]

        response = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami"
        )
        assert response.status_code == 401

    async def test_require_self_returns_401_for_malformed_bearer(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("bad-bearer@example.com"),
        )
        athlete_id = register.json()["athlete"]["id"]

        response = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        assert response.status_code == 401

    async def test_require_self_returns_401_for_expired_token(
        self, client: AsyncClient
    ) -> None:
        """Craft an expired JWT directly and verify 401, not 403."""
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("expired-jwt@example.com"),
        )
        athlete_id = register.json()["athlete"]["id"]

        # Build an expired JWT carrying the right athlete_id, signed
        # with the configured key so only the ``exp`` branch triggers
        # the rejection (signature/issuer checks pass cleanly).
        athlete_uuid = athlete_id
        now = int(time.time())
        expired = pyjwt.encode(
            {
                "sub": athlete_uuid,
                "athlete_id": athlete_uuid,
                "iat": now - 3600,
                "exp": now - 60,
                "iss": settings.JWT_ISSUER,
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        response = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami",
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert response.status_code == 401

    async def test_require_self_distinguishes_401_from_403(
        self, client: AsyncClient
    ) -> None:
        """401 (token problem) and 403 (mismatched athlete) must
        produce distinct status codes — the architecture relies on
        clients being able to differentiate auth from authz failures."""
        register = await client.post(
            "/api/v1/auth/register",
            json=register_payload("distinct@example.com"),
        )
        athlete_id = register.json()["athlete"]["id"]
        access_token = register.json()["access_token"]
        other_id = str(uuid4())

        # Expired/invalid token  → 401.
        bad = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami",
            headers={"Authorization": "Bearer garbage.jwt.value"},
        )
        # Valid token, mismatched athlete → 403.
        mismatch = await client.get(
            f"/_protected/athletes/{other_id}/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert bad.status_code == 401
        assert mismatch.status_code == 403
        assert bad.status_code != mismatch.status_code
