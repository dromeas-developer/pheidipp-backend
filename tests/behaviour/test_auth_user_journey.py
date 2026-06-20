"""End-to-end behaviour tests for the email/password authentication flow.

These tests simulate full user journeys through the public HTTP
surface so a regression in any layer (validation, service, repository,
event publisher, dependency) shows up here. They also exercise the
audit-log-scanning invariant from a black-box standpoint.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import jwt as pyjwt
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enums import Sex
from app.models.system_event import SystemEvent
from app.services.auth_service import AuthService
from tests.payloads import _login_payload, _register_payload


# ---------------------------------------------------------------------------
# Full user journey
# ---------------------------------------------------------------------------


class TestFullUserJourney:
    """Register -> login -> refresh (chained)."""

    async def test_register_then_login_then_refresh_chain(
        self, client: AsyncClient
    ) -> None:
        # 1. Register.
        register = await client.post(
            "/api/v1/auth/register",
            json=_register_payload("journey@example.com"),
        )
        assert register.status_code == 201
        registered = register.json()
        athlete_id = registered["athlete"]["id"]

        # 2. Hit the protected route with the registration access token.
        first_access = registered["access_token"]
        protected_call = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami",
            headers={"Authorization": f"Bearer {first_access}"},
        )
        assert protected_call.status_code == 200

        # 3. Login (independent session; keep both refresh tokens alive).
        login = await client.post(
            "/api/v1/auth/login",
            json=_login_payload("journey@example.com"),
        )
        assert login.status_code == 200
        login_access = login.json()["access_token"]
        login_refresh = login.json()["refresh_token"]

        # 4. Use the login access token on the protected route.
        call_with_login_token = await client.get(
            f"/_protected/athletes/{athlete_id}/whoami",
            headers={"Authorization": f"Bearer {login_access}"},
        )
        assert call_with_login_token.status_code == 200

        # 5. Rotate the registration refresh token.
        rotate_register = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered["refresh_token"]},
        )
        assert rotate_register.status_code == 200

        # 6. Rotate the login refresh token.
        rotate_login = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_refresh},
        )
        assert rotate_login.status_code == 200

        # 7. Replays fail — both old refresh tokens are now revoked.
        replay_register = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered["refresh_token"]},
        )
        assert replay_register.status_code == 401
        replay_login = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_refresh},
        )
        assert replay_login.status_code == 401

        # 8. The newly-rotated tokens still work.
        reissue_again = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotate_register.json()["refresh_token"]},
        )
        assert reissue_again.status_code == 200


class TestExpiredAccessTokenLifecycle:
    """A 15-minute access token becomes unusable after its TTL."""

    async def test_crafted_expired_access_token_is_rejected(
        self, client: AsyncClient
    ) -> None:
        register = await client.post(
            "/api/v1/auth/register",
            json=_register_payload("lifecycle@example.com"),
        )
        athlete_id = register.json()["athlete"]["id"]

        now = int(time.time())
        expired = pyjwt.encode(
            {
                "sub": athlete_id,
                "athlete_id": athlete_id,
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
        # Expired token must be 401, not 403 — even when the athlete
        # matches.
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Secret-leakage audit (per plan testing requirement)
# ---------------------------------------------------------------------------


class TestSecretLeakageAudit:
    """Register a user, then sweep every observable surface for
    credential/PII leakage."""

    async def test_no_secrets_in_register_response(
        self, client: AsyncClient
    ) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json=_register_payload("audit@example.com"),
        )
        assert response.status_code == 201
        body = response.text.lower()
        # Direct fields that must never be in the wire format.
        for forbidden in (
            "hashed_password",
            "token_hash",
            "provider_tokens",
            "provider_user_id",
            '"password"',
            '"refresh_token_hash"',
        ):
            assert forbidden not in body

        # The plaintext password is also forbidden — easy to miss if
        # someone echoes the request back.
        assert "validpass123" not in body

    async def test_audit_logs_never_carry_secrets(
        self, client: AsyncClient, cap_auth_logs
    ) -> None:
        """Per the plan: API responses AND logs must exclude
        ``hashed_password`` and raw/stored token material."""
        await client.post(
            "/api/v1/auth/register",
            json=_register_payload("audit-logs@example.com"),
        )
        await client.post(
            "/api/v1/auth/login",
            json=_login_payload("audit-logs@example.com"),
        )

        # Build the catalogue of what flowed into the auth logger:
        # message + every ``extra=`` attribute the handler received.
        rendered: list[str] = []
        for record in cap_auth_logs.records:
            rendered.append(record.getMessage())
            extras = {
                k: v
                for k, v in record.__dict__.items()
                if k
                not in (
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                    "event",
                    "auth_provider",
                    "outcome",
                    "athlete_id",
                    "token_type",
                )
            }
            rendered.append(str(extras))

        joined = " ".join(rendered).lower()

        assert "hashed_password" not in joined
        assert "token_hash" not in joined
        assert "provider_tokens" not in joined
        assert "provider_user_id" not in joined
        # Email PII is denylisted by ``logging_utils.FORBIDDEN_KEYS``
        # and never reaches the auth logger.
        assert "audit-logs@example.com" not in joined

    async def test_refresh_event_payload_contains_truncated_ip_only(
        self, db_session: AsyncSession
    ) -> None:
        """Per ADR-005: any IP carried into the outbox event must be
        in /24 (IPv4) form, never the raw address.

        Driven through the service layer so we control the
        ``ip_address`` value going into ``rotate_refresh_token``
        directly — httpx's ASGITransport does not provide a real client
        socket, so the API layer would not see an IP here.
        """
        service = AuthService(session=db_session)
        register = await service.register(
            email="ip-via-service@example.com",
            password="ValidPass123!",
            date_of_birth=datetime(1990, 1, 1, tzinfo=timezone.utc).date(),
            sex=Sex.NOT_SPECIFIED,
            height_cm=180.0,
            ip_address="198.51.100.42",
            user_agent="IpTruncation/1.0",
        )

        # Trigger a rotation that carries the IP into the event payload.
        await service.rotate_refresh_token(
            raw_refresh_token=register.issued.refresh_token,
            ip_address="198.51.100.99",
            user_agent="IpTruncation/1.0",
        )

        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_logged_in",
                    SystemEvent.athlete_id == register.athlete_id,
                )
            )
        ).scalars().all()
        assert events, "Expected at least one athlete_logged_in event"
        for event in events:
            ip = event.payload.get("ip_address")
            assert ip is not None, "Event payload should carry an IP field"
            # Must be a CIDR-form prefix, truncated per ADR-005.
            assert ip.endswith("/24") or ip.endswith("/64"), (
                f"Stored event carries a non-truncated IP: {ip!r}"
            )
            # The raw octet ``.42`` or ``.99`` must NOT be visible —
            # only the network octets in the CIDR form.
            assert ".42" not in ip
            assert ".99" not in ip
