"""AuthService result types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class IssuedTokens:
    """Raw tokens returned to the caller exactly once."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


@dataclass(frozen=True)
class AuthResult:
    """Result of register/login: athlete identity plus tokens."""

    athlete_id: UUID
    email: str
    onboarding_complete: bool
    created_at: datetime
    issued: IssuedTokens
