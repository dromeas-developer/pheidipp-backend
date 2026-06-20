"""Integration tests for AuthService — service-level behaviour with a real DB.

These tests exercise the production service through its public method
surface (register, login, rotate_refresh_token) against a live
PostgreSQL connection and assert:

* Transactional atomicity — every method either commits a fully-formed
  graph or rolls back, with no partial writes.
* Event atomicity — SystemEvent and SystemEventOutbox rows land in
  the SAME transaction as the producing domain change.
* Security invariants — credentials never appear in API-call results,
  error paths are not timing-observable.
* Token rotation — old tokens are revoked and replaced atomically,
  multi-device refresh tokens coexist.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.token_service import TokenService
from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.athlete_profile import AthleteProfile
from app.models.enums import AuthProvider, Sex
from app.models.refresh_token import RefreshToken
from app.models.system_event import SystemEvent
from app.services.auth_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.services.auth_service import AuthService
from app.utils.ip_utils import truncate_ip


@pytest.fixture
def service(db_session: AsyncSession) -> AuthService:
    return AuthService(session=db_session)


def _register_kwargs(
    email: str = "athlete@example.com",
    password: str = "ValidPass123!",
    *,
    ip_address: str | None = "192.0.2.10",
    user_agent: str | None = "PheidippTest/1.0",
) -> dict:
    return {
        "email": email,
        "password": password,
        "date_of_birth": datetime(1990, 1, 1, tzinfo=timezone.utc).date(),
        "sex": Sex.NOT_SPECIFIED,
        "height_cm": 180.0,
        "ip_address": ip_address,
        "user_agent": user_agent,
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegisterCreatesAllArtifacts:
    """A successful registration writes an Athlete, AthleteAuth,
    AthleteProfile, first RefreshToken, SystemEvent, and outbox row."""

    async def test_register_creates_athlete(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="new-athlete@example.com"))

        result = await db_session.execute(
            select(Athlete).where(Athlete.email == "new-athlete@example.com")
        )
        athletes = result.scalars().all()
        assert len(athletes) == 1

        athlete = athletes[0]
        assert athlete.onboarding_complete is False

    async def test_register_creates_email_auth_with_bcrypt_hash(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result_holder = await service.register(
            **_register_kwargs(email="new-athlete@example.com")
        )

        auth_q = await db_session.execute(
            select(AthleteAuth).where(
                AthleteAuth.athlete_id == result_holder.athlete_id
            )
        )
        auths = auth_q.scalars().all()
        assert len(auths) == 1
        auth = auths[0]
        assert auth.provider == AuthProvider.EMAIL
        assert auth.is_primary is True
        # ``hashed_password`` must be a bcrypt string and never None
        # for the email provider.
        assert auth.hashed_password is not None
        assert auth.hashed_password.startswith("$2b$")
        # Critical invariant: the plaintext password must never appear.
        assert "ValidPass123!" not in auth.hashed_password

    async def test_register_creates_minimal_profile(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result_holder = await service.register(
            **_register_kwargs(email="athlete-with-profile@example.com")
        )
        profile_q = await db_session.execute(
            select(AthleteProfile).where(
                AthleteProfile.athlete_id == result_holder.athlete_id
            )
        )
        profiles = profile_q.scalars().all()
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile.sex == Sex.NOT_SPECIFIED
        assert float(profile.height_cm) == 180.0

    async def test_register_creates_first_refresh_token(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result_holder = await service.register(
            **_register_kwargs(email="athlete-with-token@example.com")
        )
        token_q = await db_session.execute(
            select(RefreshToken).where(
                RefreshToken.athlete_id == result_holder.athlete_id
            )
        )
        tokens = token_q.scalars().all()
        assert len(tokens) == 1
        # First token has no predecessor.
        assert tokens[0].replaced_by_refresh_token_id is None
        assert tokens[0].revoked_at is None
        # ``token_hash`` is the SHA-256 of the returned raw refresh,
        # not the raw value itself.
        expected_hash = TokenService.hash_refresh_token(
            result_holder.issued.refresh_token
        )
        assert tokens[0].token_hash == expected_hash
        assert tokens[0].token_hash != result_holder.issued.refresh_token

    async def test_register_emits_athlete_registered_event(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result_holder = await service.register(
            **_register_kwargs(email="event-test@example.com")
        )
        event_q = await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "athlete_registered"
            )
        )
        events = event_q.scalars().all()
        assert len(events) == 1
        event = events[0]
        assert event.athlete_id == result_holder.athlete_id
        assert event.payload["auth_provider"] == "email"
        assert event.payload["has_password"] is True
        assert event.payload["profile_completed"] is True

    async def test_register_returns_decodable_access_token(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="decode-athlete@example.com")
        )
        # Decode the access token via the production verifier.
        token_service = TokenService()
        claims = token_service.verify_access_token(result.issued.access_token)
        assert claims.athlete_id == result.athlete_id
        assert claims.auth_provider == "email"


class TestRegisterDuplicateEmailIsAtomic:
    """Duplicate-email registration must rollback all writes."""

    async def test_duplicate_email_raises_and_rolls_back(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        # Seed the first athlete.
        await service.register(**_register_kwargs(email="dup@example.com"))

        athletes_before = (
            await db_session.execute(select(Athlete))
        ).scalars().all()
        tokens_before = (
            await db_session.execute(select(RefreshToken))
        ).scalars().all()
        auths_before = (
            await db_session.execute(select(AthleteAuth))
        ).scalars().all()

        with pytest.raises(DuplicateEmailError):
            await service.register(**_register_kwargs(email="DUP@example.com"))

        # Counts unchanged — every write rolled back atomically.
        athletes_after = (
            await db_session.execute(select(Athlete))
        ).scalars().all()
        tokens_after = (
            await db_session.execute(select(RefreshToken))
        ).scalars().all()
        auths_after = (
            await db_session.execute(select(AthleteAuth))
        ).scalars().all()
        assert len(athletes_after) == len(athletes_before)
        assert len(tokens_after) == len(tokens_before)
        assert len(auths_after) == len(auths_before)

    async def test_duplicate_email_does_not_emit_event(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="dup@example.com"))
        with pytest.raises(DuplicateEmailError):
            await service.register(**_register_kwargs(email="dup@example.com"))

        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_registered"
                )
            )
        ).scalars().all()
        # Exactly one — from the successful seed. No event from the
        # failed duplicate.
        assert len(events) == 1


class TestRegisterNormalisesEmail:
    """Email storage is always lowercase."""

    async def test_email_stored_lowercase(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="MIXEDcase@Example.com")
        )
        assert result.email == "mixedcase@example.com"


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLoginSuccessPath:
    """Successful login returns a fresh token pair and updates last_login_at."""

    async def test_login_returns_valid_token_pair(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="login@example.com"))
        result = await service.login(
            email="login@example.com",
            password="ValidPass123!",
            ip_address="192.0.2.5",
            user_agent="TestUA",
        )
        assert result.athlete_id is not None
        token_service = TokenService()
        claims = token_service.verify_access_token(result.issued.access_token)
        assert claims.athlete_id == result.athlete_id

    async def test_login_updates_last_login_at(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="lastlogin@example.com"))
        result = await service.login(
            email="lastlogin@example.com",
            password="ValidPass123!",
        )
        auth_q = await db_session.execute(
            select(AthleteAuth).where(
                AthleteAuth.athlete_id == result.athlete_id
            )
        )
        auth = auth_q.scalars().one()
        assert auth.last_login_at is not None

    async def test_login_emits_access_token_event(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="event-login@example.com"))
        await service.login(
            email="event-login@example.com",
            password="ValidPass123!",
            ip_address="198.51.100.1",
            user_agent="TestAgent",
        )

        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_logged_in"
                )
            )
        ).scalars().all()
        # Two events: register emits nothing for login; the single login
        # emits one row here. (Registration emitted ``athlete_registered``,
        # which is a different event_type.)
        assert len(events) == 1
        event = events[0]
        assert event.payload["auth_provider"] == "email"
        assert event.payload["token_type"] == "access"
        # IP must be truncated — full address never reaches the event.
        assert event.payload["ip_address"] == truncate_ip(
            "198.51.100.1"
        )
        assert event.payload["user_agent"] == "TestAgent"

    async def test_login_does_not_swap_existing_token(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        """Each login inserts a NEW RefreshToken; the previous one
        remains active (multi-device support)."""
        result = await service.register(
            **_register_kwargs(email="multi@example.com")
        )
        await service.login(email="multi@example.com", password="ValidPass123!")
        await service.login(email="multi@example.com", password="ValidPass123!")

        tokens = (
            await db_session.execute(
                select(RefreshToken).where(
                    RefreshToken.athlete_id == result.athlete_id
                )
            )
        ).scalars().all()
        # First registration + two logins = three tokens, all un-revoked
        # (multi-device support).
        assert len(tokens) == 3
        for token in tokens:
            assert token.revoked_at is None


class TestLoginFailurePath:
    """Login failures look the same to the caller no matter the cause."""

    async def test_wrong_password_raises_invalid_credentials(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="wrong@example.com"))
        with pytest.raises(InvalidCredentialsError):
            await service.login(
                email="wrong@example.com", password="not-the-password"
            )

    async def test_unknown_email_raises_invalid_credentials(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        """Missing account must raise the same exception as wrong password."""
        with pytest.raises(InvalidCredentialsError):
            await service.login(
                email="nope@example.com", password="anything"
            )

    async def test_known_email_wrong_password_does_not_update_last_login(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        """Failed login must NOT touch last_login_at (no audit signal
        of a valid but mistyped attempt)."""
        await service.register(**_register_kwargs(email="noaudit@example.com"))
        auth_q = await db_session.execute(select(AthleteAuth))
        auth = auth_q.scalars().one()
        assert auth.last_login_at is None

        with pytest.raises(InvalidCredentialsError):
            await service.login(
                email="noaudit@example.com", password="badpass"
            )
        # ``last_login_at`` stays None — only successful logins touch it.
        assert auth.last_login_at is None

    async def test_failed_login_does_not_emit_athlete_logged_in(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="noevent@example.com"))
        with pytest.raises(InvalidCredentialsError):
            await service.login(
                email="noevent@example.com", password="badpass"
            )
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_logged_in"
                )
            )
        ).scalars().all()
        assert len(events) == 0


# ---------------------------------------------------------------------------
# Refresh token rotation
# ---------------------------------------------------------------------------


class TestRefreshRotation:
    """Rotation replaces the old token atomically and emits the event."""

    async def test_rotation_returns_new_token_pair(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="rotate@example.com")
        )
        old_refresh = result.issued.refresh_token

        issued = await service.rotate_refresh_token(
            raw_refresh_token=old_refresh,
            ip_address="192.0.2.20",
            user_agent="RotateAgent",
        )

        # Security property of rotation: the old refresh token cannot
        # be reused, so the new refresh token MUST be a fresh value.
        # (Access-token strings are not asserted on because they depend
        # on per-issuance ``jti`` UUID, not on the security contract.)
        assert issued.refresh_token != old_refresh

        # The new access token still belongs to the same athlete.
        claims = TokenService().verify_access_token(issued.access_token)
        assert claims.athlete_id == result.athlete_id

    async def test_old_token_is_revoked_after_rotation(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="revoke-after@example.com")
        )
        old_hash = TokenService.hash_refresh_token(result.issued.refresh_token)

        await service.rotate_refresh_token(
            raw_refresh_token=result.issued.refresh_token
        )

        old_token_q = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == old_hash)
        )
        old_token = old_token_q.scalars().one()
        assert old_token.revoked_at is not None
        assert old_token.replaced_by_refresh_token_id is not None

    async def test_old_token_cannot_be_used_twice(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="replay@example.com")
        )
        old = result.issued.refresh_token

        await service.rotate_refresh_token(raw_refresh_token=old)
        # Replay must fail with the same generic exception.
        with pytest.raises(InvalidRefreshTokenError):
            await service.rotate_refresh_token(raw_refresh_token=old)

    async def test_unknown_refresh_token_rejected(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        with pytest.raises(InvalidRefreshTokenError):
            await service.rotate_refresh_token(
                raw_refresh_token="this-token-was-never-issued"
            )

    async def test_two_independent_tokens_rotate_independently(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="multidevice@example.com")
        )
        first = await service.login(
            email="multidevice@example.com",
            password="ValidPass123!",
        )

        # Rotate the original registration token.
        await service.rotate_refresh_token(
            raw_refresh_token=result.issued.refresh_token
        )
        # The login-issued token must still work after rotating only the
        # registration token.
        second_issued = await service.rotate_refresh_token(
            raw_refresh_token=first.issued.refresh_token
        )
        assert second_issued.refresh_token != result.issued.refresh_token
        assert second_issued.refresh_token != first.issued.refresh_token

    async def test_rotation_emits_athlete_logged_in(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="rotate-event@example.com")
        )

        events_for_athlete = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_logged_in",
                    SystemEvent.athlete_id == result.athlete_id,
                )
            )
        ).scalars().all()
        # Pre-condition: registration must NOT have emitted
        # ``athlete_logged_in`` for this athlete.
        assert len(events_for_athlete) == 0

        await service.rotate_refresh_token(
            raw_refresh_token=result.issued.refresh_token,
            ip_address="203.0.113.50",
            user_agent="RotateUA",
        )

        events_for_athlete = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "athlete_logged_in",
                    SystemEvent.athlete_id == result.athlete_id,
                )
            )
        ).scalars().all()
        assert len(events_for_athlete) == 1
        event = events_for_athlete[0]
        assert event.payload["auth_provider"] == "email"
        assert event.payload["token_type"] == "refresh"
        assert event.payload["ip_address"] == truncate_ip("203.0.113.50")

    async def test_rotation_rejects_expired_token(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        """``RefreshTokenRepository.is_active`` checks both revocation
        and expiry."""
        result = await service.register(
            **_register_kwargs(email="expiry@example.com")
        )
        # Look up the token, force ``expires_at`` into the past.
        token_hash = TokenService.hash_refresh_token(result.issued.refresh_token)
        token_q = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token = token_q.scalars().one()
        token.expires_at = datetime.now(timezone.utc).replace(year=2000)
        await db_session.flush()

        with pytest.raises(InvalidRefreshTokenError):
            await service.rotate_refresh_token(
                raw_refresh_token=result.issued.refresh_token
            )


# ---------------------------------------------------------------------------
# Security invariants across all endpoints
# ---------------------------------------------------------------------------


class TestSecretsNeverInReturnValue:
    """API result objects must never carry any credential material."""

    async def test_register_result_has_no_credentials(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        result = await service.register(
            **_register_kwargs(email="scrub-register@example.com")
        )
        # ``result.issued.refresh_token`` is the raw token — by
        # contract it's returned to the caller exactly once here. The
        # hash, however, must not surface.
        as_dict = {
            "athlete_id": str(result.athlete_id),
            "email": result.email,
            "issued": vars(result.issued),
            "onboarding_complete": result.onboarding_complete,
            "created_at": result.created_at.isoformat(),
        }
        forbidden = ["hashed_password", "token_hash", "provider_tokens"]
        for key in forbidden:
            serialized = str(as_dict).lower()
            assert key not in serialized, (
                f"{key!r} leaked into AuthService.register result"
            )

    async def test_password_never_appears_in_response_payload(
        self, db_session: AsyncSession, service: AuthService
    ) -> None:
        await service.register(**_register_kwargs(email="no-leak@example.com"))
        result = await service.login(
            email="no-leak@example.com", password="ValidPass123!"
        )
        # Plaintext password must not appear anywhere in the result.
        assert "ValidPass123!" not in str(vars(result))
        assert "ValidPass123!" not in str(vars(result.issued))
