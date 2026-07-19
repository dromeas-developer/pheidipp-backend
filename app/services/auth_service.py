"""Register/login/refresh for the email auth provider."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_utils import log_event, record_metric
from app.core.security.password_hasher import PasswordHasher
from app.core.security.token_service import TokenService
from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.athlete_profile import AthleteProfile
from app.models.enums import AuthProvider, Sex
from app.models.refresh_token import RefreshToken
from app.repositories.athlete_auth_repository import AthleteAuthRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from app.repositories.system_event_repository import SystemEventRepository
from app.services.auth_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.services.auth_results import AuthResult, IssuedTokens
from app.services.event_publisher import EventPublisher
from app.utils.email_utils import normalize_email
from app.utils.ip_utils import truncate_ip


class AuthService:
    """Email/password registration, login, and refresh-token rotation."""

    PASSWORD_PROVIDER = AuthProvider.EMAIL

    def __init__(
        self,
        session: AsyncSession,
        token_service: TokenService | None = None,
        password_hasher: PasswordHasher | None = None,
    ) -> None:
        self.session = session
        self.token_service = token_service or TokenService()
        self.password_hasher = password_hasher or PasswordHasher()
        self.athletes = AthleteRepository(session)
        self.auths = AthleteAuthRepository(session)
        self.profiles = AthleteProfileRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.events = EventPublisher(
            SystemEventRepository(session),
            SystemEventOutboxRepository(session),
        )

    async def register(
        self,
        *,
        email: str,
        password: str,
        date_of_birth: date,
        sex: Sex,
        height_cm: Optional[float],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuthResult:
        """Create athlete + auth + profile + first refresh token atomically."""
        normalized_email = normalize_email(email)
        athlete = Athlete(email=normalized_email, onboarding_complete=False)
        password_hash = self.password_hasher.hash(password)

        # Track the athlete_id generated for FK wiring of auth/profile/refresh
        # — we add() then flush() inside the surrounding transaction so the
        # Athlete row exists before we attach dependents. Flushing surfaces
        # the unique-index violation early and atomically; the outer
        # ``commit`` releases either all four inserts or none of them.
        try:
            await self.athletes.add(athlete)
        except IntegrityError as exc:
            await self.session.rollback()
            if AthleteRepository.is_unique_violation(exc):
                self._log(
                    event="athlete.registration.duplicate",
                    outcome="failed",
                )
                record_metric(
                    "athlete.auth.registrations.total",
                    auth_provider="email",
                    outcome="failed",
                )
                raise DuplicateEmailError("email already in use") from exc
            raise

        athlete_id = athlete.id

        auth = AthleteAuth(
            athlete_id=athlete_id,
            provider=self.PASSWORD_PROVIDER,
            hashed_password=password_hash,
            is_primary=True,
        )
        profile = AthleteProfile(
            athlete_id=athlete_id,
            date_of_birth=date_of_birth,
            sex=sex,
            height_cm=height_cm,
        )
        await self.auths.add(auth)
        await self.profiles.add(profile)

        issued = self._mint_tokens(
            athlete_id=athlete_id,
            auth_provider=self.PASSWORD_PROVIDER,
        )
        await self._persist_first_refresh_token(
            athlete_id=athlete_id,
            raw_refresh_token=issued.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.events.publish(
            event_type="athlete_registered",
            athlete_id=athlete_id,
            payload={
                "auth_provider": AuthProvider.EMAIL.value,
                "has_password": True,
                "profile_completed": True,
            },
        )

        await self.session.commit()

        self._log(
            event="athlete.registered",
            athlete_id=athlete_id,
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )
        record_metric(
            "athlete.auth.registrations.total",
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )

        return AuthResult(
            athlete_id=athlete_id,
            email=normalized_email,
            onboarding_complete=False,
            created_at=athlete.created_at,
            issued=issued,
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuthResult:
        """Validate email/password and mint a fresh token pair."""
        normalized_email = normalize_email(email)
        auth_record = await self.auths.get_email_auth_by_normalized_email(
            normalized_email
        )

        # Run ``verify`` even when ``auth_record`` is missing, hashing a
        # throw-away password so the response time cannot be used to
        # distinguish "no such account" from "wrong password".
        if auth_record is None or auth_record.hashed_password is None:
            self._password_hasher_constant_time_dummy()
            self._log(
                event="athlete.login",
                outcome="failed",
            )
            record_metric(
                "athlete.auth.logins.failed.total",
                auth_provider=AuthProvider.EMAIL.value,
                outcome="failed",
            )
            raise InvalidCredentialsError("invalid credentials")

        if not self.password_hasher.verify(password, auth_record.hashed_password):
            self._log(
                event="athlete.login",
                outcome="failed",
            )
            record_metric(
                "athlete.auth.logins.failed.total",
                auth_provider=AuthProvider.EMAIL.value,
                outcome="failed",
            )
            raise InvalidCredentialsError("invalid credentials")

        athlete = await self.athletes.get_by_id(auth_record.athlete_id)
        if athlete is None:
            self._log(event="athlete.login", outcome="failed")
            record_metric(
                "athlete.auth.logins.failed.total",
                auth_provider=AuthProvider.EMAIL.value,
                outcome="failed",
            )
            raise InvalidCredentialsError("invalid credentials")

        await self.auths.touch_last_login(auth_record)
        issued = self._mint_tokens(
            athlete_id=athlete.id,
            auth_provider=self.PASSWORD_PROVIDER,
        )
        await self._persist_refresh_token(
            athlete_id=athlete.id,
            raw_refresh_token=issued.refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self.events.publish(
            event_type="athlete_logged_in",
            athlete_id=athlete.id,
            payload={
                "auth_provider": AuthProvider.EMAIL.value,
                "token_type": "access",
                "ip_address": truncate_ip(ip_address),
                "user_agent": user_agent,
            },
        )

        await self.session.commit()

        self._log(
            event="athlete.logged_in",
            athlete_id=athlete.id,
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )
        record_metric(
            "athlete.auth.logins.total",
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )

        return AuthResult(
            athlete_id=athlete.id,
            email=athlete.email,
            onboarding_complete=athlete.onboarding_complete,
            created_at=athlete.created_at,
            issued=issued,
        )

    async def rotate_refresh_token(
        self,
        *,
        raw_refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> IssuedTokens:
        """Atomically revoke old token and insert successor."""
        token_hash = TokenService.hash_refresh_token(raw_refresh_token)
        existing = await self.refresh_tokens.get_by_token_hash(token_hash)
        if existing is None:
            self._log(event="athlete.refresh", outcome="failed")
            record_metric(
                "athlete.auth.refresh.failed.total",
                auth_provider=AuthProvider.EMAIL.value,
                outcome="failed",
            )
            raise InvalidRefreshTokenError("invalid refresh token")

        if not RefreshTokenRepository.is_active(existing):
            self._log(
                event="athlete.refresh",
                athlete_id=existing.athlete_id,
                outcome="failed",
            )
            record_metric(
                "athlete.auth.refresh.failed.total",
                auth_provider=AuthProvider.EMAIL.value,
                outcome="failed",
            )
            raise InvalidRefreshTokenError("invalid refresh token")

        new_raw = TokenService.generate_refresh_token()
        new_hash = TokenService.hash_refresh_token(new_raw)
        new_expires = self.token_service.refresh_expiry()
        replacement = RefreshToken(
            athlete_id=existing.athlete_id,
            token_hash=new_hash,
            expires_at=new_expires,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.refresh_tokens.add(replacement)
        # replacement.id is populated after flush
        existing.revoked_at = datetime.now(timezone.utc)
        existing.replaced_by_refresh_token_id = replacement.id
        await self.session.flush()

        access_token, access_exp = self.token_service.issue_access_token(
            existing.athlete_id, auth_provider=self.PASSWORD_PROVIDER.value
        )

        await self.events.publish(
            event_type="athlete_logged_in",
            athlete_id=existing.athlete_id,
            payload={
                "auth_provider": AuthProvider.EMAIL.value,
                "token_type": "refresh",
                "ip_address": truncate_ip(ip_address),
                "user_agent": user_agent,
            },
        )

        await self.session.commit()

        self._log(
            event="athlete.refresh",
            athlete_id=existing.athlete_id,
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )
        record_metric(
            "athlete.auth.refresh.total",
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )
        record_metric(
            "athlete.auth.rotation.total",
            auth_provider=AuthProvider.EMAIL.value,
            outcome="success",
        )

        return IssuedTokens(
            access_token=access_token,
            refresh_token=new_raw,
            access_expires_at=access_exp,
            refresh_expires_at=new_expires,
        )

    def _mint_tokens(
        self,
        *,
        athlete_id: uuid.UUID,
        auth_provider: AuthProvider,
    ) -> IssuedTokens:
        access, access_exp = self.token_service.issue_access_token(
            athlete_id, auth_provider=auth_provider.value
        )
        raw_refresh = TokenService.generate_refresh_token()
        refresh_exp = self.token_service.refresh_expiry()
        return IssuedTokens(
            access_token=access,
            refresh_token=raw_refresh,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
        )

    async def _persist_first_refresh_token(
        self,
        *,
        athlete_id: uuid.UUID,
        raw_refresh_token: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> RefreshToken:
        token_hash = TokenService.hash_refresh_token(raw_refresh_token)
        record = RefreshToken(
            athlete_id=athlete_id,
            token_hash=token_hash,
            expires_at=self.token_service.refresh_expiry(),
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return await self.refresh_tokens.add(record)

    async def _persist_refresh_token(
        self,
        *,
        athlete_id: uuid.UUID,
        raw_refresh_token: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
    ) -> RefreshToken:
        return await self._persist_first_refresh_token(
            athlete_id=athlete_id,
            raw_refresh_token=raw_refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def _password_hasher_constant_time_dummy(self) -> None:
        try:
            self.password_hasher.verify(
                "timing-defence-no-such-account",
                "$2b$12$CwTycUXWue0Thq9StjUM0uJ8Dxx5Z0G1Q9X1q6w2M1qXk0QFq8uOa",
            )
        except Exception:  # Any failure is acceptable — only the work itself matters.
            return

    @staticmethod
    def _log(
        *,
        event: str,
        athlete_id: Optional[uuid.UUID] = None,
        auth_provider: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> None:
        fields: dict[str, object] = {"outcome": outcome}
        if athlete_id is not None:
            fields["athlete_id"] = str(athlete_id)
        if auth_provider is not None:
            fields["auth_provider"] = auth_provider
        log_event(event=event, **fields)  # type: ignore[arg-type]
