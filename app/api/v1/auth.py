"""Auth API surface: register, login, refresh-token rotation.

All endpoints follow the brand-philosophy rule: user-facing errors are
plain and non-technical. Internals never leak distinguishing detail —
login failure looks the same whether the account is missing or the
password is wrong.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import build_auth_service
from app.schemas.auth import (
    AthleteResponse,
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
)
from app.services.auth_errors import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)
from app.services.auth_results import AuthResult, IssuedTokens
from app.services.auth_service import AuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


# --------- token TTL helpers ---------


def _seconds_until(when: datetime) -> int:
    """Return whole-second TTL for an absolute UTC timestamp."""
    delta = (when - datetime.now(timezone.utc)).total_seconds()
    # Clamp to a minimum of 1 so clients never see a non-positive TTL.
    return max(1, int(delta))


# --------- response builders ---------


def _auth_response(result: AuthResult) -> AuthResponse:
    return AuthResponse(
        athlete=AthleteResponse(
            id=result.athlete_id,
            email=result.email,
            onboarding_complete=result.onboarding_complete,
            created_at=result.created_at,
        ),
        access_token=result.issued.access_token,
        refresh_token=result.issued.refresh_token,
        access_token_expires_in=_seconds_until(result.issued.access_expires_at),
        refresh_token_expires_in=_seconds_until(result.issued.refresh_expires_at),
    )


def _refresh_response(issued: IssuedTokens) -> RefreshResponse:
    return RefreshResponse(
        access_token=issued.access_token,
        refresh_token=issued.refresh_token,
        access_token_expires_in=_seconds_until(issued.access_expires_at),
        refresh_token_expires_in=_seconds_until(issued.refresh_expires_at),
    )


# --------- request-context extraction ---------


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client is not None else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


# --------- endpoints ---------


@auth_router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    request: Request,
    auth_service: AuthService = Depends(build_auth_service),
) -> AuthResponse:
    try:
        result = await auth_service.register(
            email=payload.email,
            password=payload.password,
            date_of_birth=payload.profile.date_of_birth,
            sex=payload.profile.sex,
            height_cm=payload.profile.height_cm,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That email is already in use.",
        )

    return _auth_response(result)


@auth_router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(build_auth_service),
) -> AuthResponse:
    try:
        result = await auth_service.login(
            email=payload.email,
            password=payload.password,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )
    return _auth_response(result)


@auth_router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    auth_service: AuthService = Depends(build_auth_service),
) -> RefreshResponse:
    try:
        issued = await auth_service.rotate_refresh_token(
            raw_refresh_token=payload.refresh_token,
            ip_address=_client_ip(request),
            user_agent=_user_agent(request),
        )
    except InvalidRefreshTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )
    return _refresh_response(issued)
