"""Service layer for Pheidipp domain operations."""

from app.services.auth_errors import (
    AuthError,
    CrossAthleteAccessError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UnauthenticatedError,
)
from app.services.auth_results import AuthResult, IssuedTokens
from app.services.auth_service import AuthService
from app.services.event_publisher import EventPublisher, OutboxEvent

__all__ = [
    "AuthError",
    "AuthResult",
    "AuthService",
    "CrossAthleteAccessError",
    "DuplicateEmailError",
    "EventPublisher",
    "InvalidCredentialsError",
    "InvalidRefreshTokenError",
    "IssuedTokens",
    "OutboxEvent",
    "UnauthenticatedError",
]
