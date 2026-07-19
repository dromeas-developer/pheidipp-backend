"""Authentication request and response schemas (Phase 1.1)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Sex


class RegisterProfileIn(BaseModel):
    """Minimal registration profile: DOB, sex, height."""

    date_of_birth: date
    sex: Sex
    height_cm: float | None = Field(default=None, ge=50, le=300)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    profile: RegisterProfileIn


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class AthleteResponse(BaseModel):
    """Public Athlete shape — never includes credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    onboarding_complete: bool
    created_at: datetime


class TokenPairResponse(BaseModel):
    """Token bundle returned by register, login and rotate."""

    access_token: str
    refresh_token: str
    access_token_expires_in: int  # seconds remaining until expiry
    refresh_token_expires_in: int  # seconds remaining until expiry
    token_type: Literal["bearer"] = "bearer"


class AuthResponse(BaseModel):
    """Combined athlete + tokens response for register/login."""

    athlete: AthleteResponse
    access_token: str
    refresh_token: str
    access_token_expires_in: int
    refresh_token_expires_in: int
    token_type: Literal["bearer"] = "bearer"


class RefreshResponse(BaseModel):
    """Refresh rotation response — no athlete payload."""

    access_token: str
    refresh_token: str
    access_token_expires_in: int
    refresh_token_expires_in: int
    token_type: Literal["bearer"] = "bearer"
