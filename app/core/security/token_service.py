"""Token service: JWT access tokens and opaque refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from jose import JWTError, jwt

from app.config import settings


class TokenVerificationError(Exception):
    """Raised when a JWT is missing, malformed, expired, or unverifiable."""


@dataclass(frozen=True)
class AccessTokenClaims:
    """Decoded JWT access-token claims used by the auth dependency."""

    athlete_id: UUID
    auth_provider: str | None
    issued_at: datetime
    expires_at: datetime


class TokenService:
    """Issue and verify JWT access tokens and opaque refresh tokens."""

    REFRESH_HASH_ALGO = "sha256"

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str | None = None,
        issuer: str | None = None,
        access_ttl_minutes: int | None = None,
        refresh_ttl_days: int | None = None,
    ) -> None:
        self._secret_key = secret_key or settings.JWT_SECRET_KEY
        if not self._secret_key:
            raise RuntimeError("JWT_SECRET_KEY is not configured")
        self._algorithm = algorithm or settings.JWT_ALGORITHM
        self._issuer = issuer or settings.JWT_ISSUER
        self._access_ttl = timedelta(
            minutes=access_ttl_minutes or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        self._refresh_ttl = timedelta(
            days=refresh_ttl_days or settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )

    # ---------- JWT access token ----------
    def issue_access_token(
        self,
        athlete_id: UUID,
        auth_provider: str | None = None,
    ) -> tuple[str, datetime]:
        """Sign and return a JWT access token plus its expiry instant."""
        # Every issuance embeds a fresh random ``jti`` (UUID4) so that
        # two tokens issued for the same athlete within the same second
        # still produce distinct JWT strings. ``jti`` is informational:
        # verification does not consult any replay ledger and tokens
        # issued before this patch (without ``jti``) remain valid until
        # their existing expiry (see
        # ``docs/architecture/01-entities/athlete-auth.md``).
        now = datetime.now(timezone.utc)
        exp = now + self._access_ttl
        claims: dict[str, Any] = {
            "sub": str(athlete_id),
            "athlete_id": str(athlete_id),
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "iss": self._issuer,
            "jti": str(uuid4()),
        }
        if auth_provider is not None:
            claims["auth_provider"] = auth_provider
        token = jwt.encode(claims, self._secret_key, algorithm=self._algorithm)
        return token, exp

    def verify_access_token(self, token: str) -> AccessTokenClaims:
        """Verify a JWT and return its claims. Raises TokenVerificationError otherwise."""
        if not token:
            raise TokenVerificationError("missing token")
        try:
            payload = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise TokenVerificationError(str(exc)) from exc

        sub = payload.get("sub") or payload.get("athlete_id")
        if not sub:
            raise TokenVerificationError("missing athlete_id claim")
        try:
            athlete_id = UUID(str(sub))
        except (ValueError, TypeError) as exc:
            raise TokenVerificationError("invalid athlete_id claim") from exc

        iat_raw = payload.get("iat")
        exp_raw = payload.get("exp")
        if not isinstance(iat_raw, (int, float)) or not isinstance(
            exp_raw, (int, float)
        ):
            raise TokenVerificationError("missing iat/exp claim")
        issued_at = datetime.fromtimestamp(int(iat_raw), tz=timezone.utc)
        expires_at = datetime.fromtimestamp(int(exp_raw), tz=timezone.utc)
        auth_provider_raw = payload.get("auth_provider")
        auth_provider = (
            str(auth_provider_raw) if auth_provider_raw is not None else None
        )

        return AccessTokenClaims(
            athlete_id=athlete_id,
            auth_provider=auth_provider,
            issued_at=issued_at,
            expires_at=expires_at,
        )

    @property
    def access_ttl(self) -> timedelta:
        return self._access_ttl

    # ---------- Opaque refresh token ----------

    @staticmethod
    def generate_refresh_token() -> str:
        """Generate a fresh opaque refresh token (returned to caller once)."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_refresh_token(raw: str) -> str:
        """One-way SHA-256 hex digest of a refresh token."""
        if not raw:
            raise ValueError("refresh token must be a non-empty string")
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def refresh_expiry(self, now: datetime | None = None) -> datetime:
        """30-day expiry for a refresh token issued *now* (or supplied now)."""
        # INVARIANT (ADR-005): refresh tokens live for exactly
        # ``JWT_REFRESH_TOKEN_EXPIRE_DAYS`` (default 30) from issuance.
        # Expired tokens are rejected by :meth:`RefreshTokenRepository.is_active`
        # even if not yet revoked, so the rotation/revocation ledger and this
        # TTL form two independent expiry mechanisms on the same row.
        anchor = now or datetime.now(timezone.utc)
        return anchor + self._refresh_ttl

    @property
    def refresh_ttl(self) -> timedelta:
        return self._refresh_ttl
