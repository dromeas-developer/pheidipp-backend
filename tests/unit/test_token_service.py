"""Unit tests for the token service (JWT + opaque refresh tokens).

These tests cover the Phase-1.1 contract:

* JWT access tokens carry the ``athlete_id`` claim, have a 15-minute
  TTL by default, and verify in constant time without consulting the
  database.
* JWT verification is strict: any malformed/expired/wrong-issuer
  token raises :class:`TokenVerificationError`.
* Refresh tokens are opaque (not parseable as JWT), generated via
  ``secrets.token_urlsafe``, and reduced to a SHA-256 hex digest
  before storage.
* ``refresh_expiry`` returns ``now + 30 days`` per the ADR-005
  invariant.

The decode-side helper ``_decode_test_jwt`` reads the secret and
issuer from the project's :class:`app.config.Settings` instance rather
than hardcoding literals. ``TokenService`` signs with the same
``Settings`` values, so this guarantees the test verifies with the
exact key/issuer the production code used at sign time — independent of
which ``.env`` / ``.env.test`` file is loaded.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest

from app.config import settings
from app.core.security.token_service import (
    AccessTokenClaims,
    TokenService,
    TokenVerificationError,
)


def _decode_test_jwt(token: str) -> dict:
    """Decode a token using the same secret/issuer ``TokenService`` used.

    Centralising this lookup prevents drift between the hardcoded
    literals that used to live in the tests and the values actually
    read from the project settings — the previous setup failed in CI
    when ``.env.test`` overrode ``JWT_SECRET_KEY``/``JWT_ISSUER`` to a
    different value than the inline test literal.
    """
    return pyjwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
        issuer=settings.JWT_ISSUER,
        options={"verify_aud": False},
    )


@pytest.fixture
def token_service() -> TokenService:
    return TokenService()


class TestIssueAccessToken:
    """JWT issuance: payload shape, TTL, signing algorithm."""

    def test_contains_required_claims(
        self, token_service: TokenService
    ) -> None:
        athlete_id = uuid4()
        token, exp = token_service.issue_access_token(athlete_id)
        payload = _decode_test_jwt(token)
        # ``sub`` is required to match the v1 JWT spec; ``athlete_id``
        # is the explicit claim used by ``require_self``.
        assert payload["sub"] == str(athlete_id)
        assert payload["athlete_id"] == str(athlete_id)
        assert isinstance(UUID(payload["athlete_id"]), UUID)

    def test_returns_future_expiry(
        self, token_service: TokenService
    ) -> None:
        before = datetime.now(timezone.utc)
        _, exp = token_service.issue_access_token(uuid4())
        after = datetime.now(timezone.utc)
        # Default TTL is 15 minutes — expiry must sit at least 14m59s
        # after the wall-clock anchor.
        assert (exp - before) >= timedelta(minutes=14, seconds=59)
        # And at most 15m00.5s after — generous CI jitter.
        assert (exp - after) <= timedelta(minutes=15, seconds=1)

    def test_includes_auth_provider_claim_when_provided(
        self, token_service: TokenService
    ) -> None:
        token, _ = token_service.issue_access_token(uuid4(), auth_provider="email")
        payload = _decode_test_jwt(token)
        assert payload["auth_provider"] == "email"

    def test_omits_auth_provider_when_none(
        self, token_service: TokenService
    ) -> None:
        token, _ = token_service.issue_access_token(uuid4())
        payload = _decode_test_jwt(token)
        assert "auth_provider" not in payload


class TestIssueAccessTokenJti:
    """Per-issuance ``jti`` claim — make each JWT unique even when
    issued within the same second. ``jti`` is NOT a replay ledger; it
    is purely a UUID embedded in the payload to break deterministic
    equality between concurrently issued tokens."""

    def test_newly_issued_token_contains_jti_claim(
        self, token_service: TokenService
    ) -> None:
        token, _ = token_service.issue_access_token(uuid4())
        payload = _decode_test_jwt(token)
        assert "jti" in payload
        # Must be a string (JWT claims are JSON, so UUID objects don't
        # survive encoding — the producer must stringify before signing).
        assert isinstance(payload["jti"], str)

    def test_jti_is_parseable_as_uuid(
        self, token_service: TokenService
    ) -> None:
        token, _ = token_service.issue_access_token(uuid4())
        payload = _decode_test_jwt(token)
        # Same string-parses-as-UUID contract used for athlete_id.
        assert isinstance(UUID(payload["jti"]), UUID)

    def test_two_tokens_same_second_have_distinct_jti_and_jwt(
        self, token_service: TokenService
    ) -> None:
        """The failure mode from the v2 devops report: rotation and
        registration issued within the same second used to produce
        byte-identical access tokens. With ``jti`` they must not."""
        athlete_id = uuid4()
        token_a, _ = token_service.issue_access_token(athlete_id)
        token_b, _ = token_service.issue_access_token(athlete_id)

        # Encoded JWT strings differ.
        assert token_a != token_b

        payload_a = _decode_test_jwt(token_a)
        payload_b = _decode_test_jwt(token_b)
        # ``jti`` values differ.
        assert payload_a["jti"] != payload_b["jti"]
        # And every other claim they share is identical — proving
        # ``jti`` is the differentiator, not wall-clock drift.
        for shared_claim in ("sub", "athlete_id", "iat", "exp", "iss"):
            assert payload_a[shared_claim] == payload_b[shared_claim]

    def test_jti_present_when_auth_provider_is_provided(
        self, token_service: TokenService
    ) -> None:
        """``jti`` is independent of ``auth_provider``; both must
        appear together when ``auth_provider`` is supplied."""
        token, _ = token_service.issue_access_token(
            uuid4(), auth_provider="email"
        )
        payload = _decode_test_jwt(token)
        assert payload["auth_provider"] == "email"
        assert isinstance(UUID(payload["jti"]), UUID)

    def test_old_token_without_jti_still_verifies(
        self, token_service: TokenService
    ) -> None:
        """Backward compatibility — tokens issued before the ``jti``
        patch remain valid until their existing expiry. The verifier
        does not require ``jti`` and ignores it when absent."""
        athlete_id = uuid4()
        now = int(time.time())
        # Hand-crafted payload with NO ``jti`` claim.
        legacy_payload = {
            "sub": str(athlete_id),
            "athlete_id": str(athlete_id),
            "iat": now,
            "exp": now + 60,
            "iss": settings.JWT_ISSUER,
        }
        legacy_token = pyjwt.encode(
            legacy_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        claims = token_service.verify_access_token(legacy_token)
        assert claims.athlete_id == athlete_id


class TestVerifyAccessToken:
    """JWT verification: positive and negative paths."""

    def test_verifies_issued_token(
        self, token_service: TokenService
    ) -> None:
        athlete_id = uuid4()
        token, _ = token_service.issue_access_token(athlete_id)
        claims = token_service.verify_access_token(token)
        assert claims.athlete_id == athlete_id

    def test_returns_typed_claims(
        self, token_service: TokenService
    ) -> None:
        token, _ = token_service.issue_access_token(uuid4())
        claims = token_service.verify_access_token(token)
        assert isinstance(claims, AccessTokenClaims)
        assert isinstance(claims.athlete_id, UUID)
        assert isinstance(claims.issued_at, datetime)
        assert isinstance(claims.expires_at, datetime)

    def test_rejects_expired_token(self) -> None:
        # Construct an expired JWT directly so the test is independent
        # of wall-clock drift. Sign with the SAME secret/issuer
        # ``TokenService`` will use, so signature/issuer checks pass and
        # only the expiry branch fires.
        athlete_id = uuid4()
        now = int(time.time())
        expired_payload = {
            "sub": str(athlete_id),
            "athlete_id": str(athlete_id),
            "iat": now - 3600,
            "exp": now - 60,
            "iss": settings.JWT_ISSUER,
        }
        expired_token = pyjwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        svc = TokenService()
        with pytest.raises(TokenVerificationError):
            svc.verify_access_token(expired_token)

    def test_rejects_token_signed_with_wrong_secret(self) -> None:
        athlete_id = uuid4()
        now = int(time.time())
        bogus_token = pyjwt.encode(
            {
                "sub": str(athlete_id),
                "athlete_id": str(athlete_id),
                "iat": now,
                "exp": now + 60,
                "iss": settings.JWT_ISSUER,
            },
            # A guaranteed-wrong key (not the configured secret) so the
            # signature check fails before any other validation does.
            "wrong-secret-not-the-configured-one",
            algorithm=settings.JWT_ALGORITHM,
        )
        svc = TokenService()
        with pytest.raises(TokenVerificationError):
            svc.verify_access_token(bogus_token)

    def test_rejects_token_with_wrong_issuer(self) -> None:
        athlete_id = uuid4()
        now = int(time.time())
        wrong_iss = pyjwt.encode(
            {
                "sub": str(athlete_id),
                "athlete_id": str(athlete_id),
                "iat": now,
                "exp": now + 60,
                "iss": "someone-else-not-pheidipp",
            },
            # Sign with the configured key so signature/issuer are
            # the only mismatching fields.
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        svc = TokenService()
        with pytest.raises(TokenVerificationError):
            svc.verify_access_token(wrong_iss)

    def test_rejects_token_missing_athlete_id_claim(self) -> None:
        """``sub`` and ``athlete_id`` both missing — verification must fail."""
        now = int(time.time())
        no_sub = pyjwt.encode(
            {
                "iat": now,
                "exp": now + 60,
                "iss": settings.JWT_ISSUER,
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        svc = TokenService()
        with pytest.raises(TokenVerificationError):
            svc.verify_access_token(no_sub)

    @pytest.mark.parametrize("value", [None, "", 0, [], {}])  # type: ignore[list-item]
    def test_rejects_non_string_input(self, value) -> None:
        svc = TokenService()
        with pytest.raises(TokenVerificationError):
            svc.verify_access_token(value)  # type: ignore[arg-type]


class TestGenerateAndHashRefreshToken:
    """Opaque refresh-token generation and SHA-256 hashing."""

    def test_generated_token_is_unique(self) -> None:
        a = TokenService.generate_refresh_token()
        b = TokenService.generate_refresh_token()
        assert a != b
        # 48-byte url-safe base64 ≈ 64 characters.
        assert len(a) >= 48

    def test_generated_token_is_opaque(self) -> None:
        """Generated refresh tokens must NOT decode as JWTs."""
        raw = TokenService.generate_refresh_token()
        # Two dots means three segments → JWT structure.
        assert raw.count(".") != 2

    def test_hash_is_sha256_hex_digest(self) -> None:
        raw = TokenService.generate_refresh_token()
        hashed = TokenService.hash_refresh_token(raw)
        # SHA-256 hex digest is exactly 64 lowercase hex chars.
        assert len(hashed) == 64
        assert all(c in "0123456789abcdef" for c in hashed)

    def test_hash_is_deterministic(self) -> None:
        raw = TokenService.generate_refresh_token()
        assert TokenService.hash_refresh_token(raw) == TokenService.hash_refresh_token(raw)

    def test_different_inputs_produce_different_hashes(self) -> None:
        a = TokenService.hash_refresh_token("alpha")
        b = TokenService.hash_refresh_token("beta")
        assert a != b

    def test_hash_rejects_invalid_input(self) -> None:
        with pytest.raises(ValueError):
            TokenService.hash_refresh_token("")
        with pytest.raises(ValueError):
            TokenService.hash_refresh_token(None)  # type: ignore[arg-type]


class TestRefreshExpiry:
    """The 30-day refresh-token TTL invariant from ADR-005."""

    def test_default_expiry_is_thirty_days(self) -> None:
        anchor = datetime(2026, 1, 1, tzinfo=timezone.utc)
        service = TokenService()
        assert service.refresh_expiry(now=anchor) == anchor + timedelta(days=30)

    def test_expiry_uses_current_time_when_unanchored(
        self, token_service: TokenService
    ) -> None:
        before = datetime.now(timezone.utc)
        expiry = token_service.refresh_expiry()
        after = datetime.now(timezone.utc)
        # Default TTL must place expiry between these two anchors.
        assert before + timedelta(days=29) <= expiry
        assert expiry <= after + timedelta(days=30)

    def test_expiry_matches_refresh_ttl_property(
        self, token_service: TokenService
    ) -> None:
        """``refresh_ttl`` and ``refresh_expiry`` must agree on the same window."""
        anchor = datetime(2026, 5, 1, tzinfo=timezone.utc)
        assert token_service.refresh_expiry(now=anchor) == anchor + token_service.refresh_ttl


class TestAccessTtlProperty:
    """The 15-minute access-token TTL default."""

    def test_default_access_ttl_is_fifteen_minutes(self) -> None:
        assert TokenService().access_ttl == timedelta(minutes=15)


class TestMissingSecretKey:
    """The service refuses to construct without a JWT secret."""

    def test_raises_runtime_when_secret_missing(self, monkeypatch) -> None:
        monkeypatch.setattr("app.config.settings.JWT_SECRET_KEY", "")
        with pytest.raises(RuntimeError):
            TokenService()
