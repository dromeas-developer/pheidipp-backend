import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token, create_refresh_token, hash_token
from app.core.unit_of_work import UnitOfWork
from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.models.enums import AthleteStatus
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)

logger = logging.getLogger("pheidipp.auth")


class AuthService:
    """Authentication service handling registration, login, token refresh and logout."""

    async def register(
        self,
        data: RegisterRequest,
        uow: UnitOfWork,
    ) -> tuple[Athlete, TokenResponse]:
        """Register a new athlete and issue tokens."""
        email = data.email.strip().lower()

        # Check if email already exists
        existing = await uow.athletes.get_by_email(email)
        if existing:
            email_hash = hash_password(email)[:16] if hasattr(self, '_') else email[:16]
            logger.warning("auth.register.email_exists", extra={"email_prefix": email[:16]})
            raise ValueError("Email already registered")

        try:
            # Create athlete
            athlete = Athlete(
                email=email,
                hashed_password=hash_password(data.password),
                status=AthleteStatus.ACTIVE,
            )
            uow.session.add(athlete)
            await uow.session.flush()

            # Create profile if any optional profile fields are explicitly set
            if any([
                data.first_name is not None,
                data.last_name is not None,
                data.date_of_birth is not None,
                data.gender is not None,
                data.unit_preference is not None,
            ]):
                profile = AthleteProfile(
                    athlete_id=athlete.id,
                    first_name=data.first_name,
                    last_name=data.last_name,
                    date_of_birth=data.date_of_birth,
                    gender=data.gender,
                    unit_preference=data.unit_preference,
                )
                uow.session.add(profile)
                await uow.session.flush()

        except IntegrityError:
            logger.warning("auth.register.integrity_error", extra={"email": email[:16]})
            raise ValueError("Email already registered")

        # Issue token pair
        token_response = await self._issue_token_pair(athlete.id, None, uow)

        logger.info("auth.register.success", extra={"athlete_id": str(athlete.id)})
        return athlete, token_response

    async def login(
        self,
        data: LoginRequest,
        uow: UnitOfWork,
    ) -> TokenResponse:
        """Authenticate an athlete and issue tokens."""
        email = data.email.strip().lower()

        athlete = await uow.athletes.get_by_email(email)
        if not athlete:
            logger.warning("auth.login.invalid_credentials", extra={"email_prefix": email[:16]})
            raise ValueError("Invalid credentials")

        if not verify_password(data.password, athlete.hashed_password or ""):
            logger.warning("auth.login.invalid_password", extra={"athlete_id": str(athlete.id)})
            raise ValueError("Invalid credentials")

        if athlete.status != AthleteStatus.ACTIVE:
            logger.warning("auth.login.inactive_account", extra={"athlete_id": str(athlete.id), "status": athlete.status})
            raise ValueError("Account is not active")

        token_response = await self._issue_token_pair(athlete.id, data.device_hint, uow)

        logger.info("auth.login.success", extra={"athlete_id": str(athlete.id)})
        return token_response

    async def refresh(
        self,
        raw_refresh_token: str,
        uow: UnitOfWork,
    ) -> TokenResponse:
        """Refresh access token using a valid refresh token."""
        token_hash = hash_token(raw_refresh_token)

        # Get active token with row lock
        token = await uow.refresh_tokens.get_active_by_hash(token_hash)
        if not token:
            logger.warning("auth.refresh.invalid_token")
            raise ValueError("Invalid or expired refresh token")

        athlete_id = token.athlete_id

        # Revoke the old token
        await uow.refresh_tokens.revoke(token.id)

        # Issue new token pair
        token_response = await self._issue_token_pair(athlete_id, token.device_hint, uow)

        logger.info("auth.refresh.success", extra={"athlete_id": str(athlete_id)})
        return token_response

    async def logout(
        self,
        raw_refresh_token: str,
        uow: UnitOfWork,
    ) -> None:
        """Logout by revoking the refresh token."""
        token_hash = hash_token(raw_refresh_token)

        token = await uow.refresh_tokens.get_active_by_hash(token_hash)
        if not token:
            # Idempotent - no active token to revoke
            return

        await uow.refresh_tokens.revoke(token.id)
        logger.info("auth.logout.success", extra={"athlete_id": str(token.athlete_id)})

    async def _issue_token_pair(
        self,
        athlete_id: uuid.UUID,
        device_hint: Optional[str],
        uow: UnitOfWork,
    ) -> TokenResponse:
        """Issue a new access/refresh token pair."""
        # Create access token
        access_token = create_access_token(athlete_id)

        # Create refresh token
        raw_refresh, token_hash = create_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

        await uow.refresh_tokens.create(
            athlete_id=athlete_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_hint=device_hint,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            athlete_id=athlete_id,
        )