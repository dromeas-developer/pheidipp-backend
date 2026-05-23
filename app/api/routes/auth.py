from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.unit_of_work import UnitOfWork
from app.services.auth_service import AuthService
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RefreshRequest,
    LogoutRequest,
    TokenResponse,
)
from app.api.dependencies import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Register a new athlete and receive access/refresh tokens."""
    async with UnitOfWork(db) as uow:
        try:
            athlete, token_response = await auth_service.register(payload, uow)
        except ValueError as e:
            if "already registered" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(e),
                )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )
    return token_response


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and receive access/refresh tokens."""
    async with UnitOfWork(db) as uow:
        try:
            token_response = await auth_service.login(payload, uow)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
    return token_response


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using a valid refresh token."""
    async with UnitOfWork(db) as uow:
        try:
            token_response = await auth_service.refresh(payload.refresh_token, uow)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )
    return token_response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db),
):
    """Logout by revoking the refresh token. Idempotent - safe to call multiple times."""
    async with UnitOfWork(db) as uow:
        await auth_service.logout(payload.refresh_token, uow)
    return None