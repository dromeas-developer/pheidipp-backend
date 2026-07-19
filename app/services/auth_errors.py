"""Domain exceptions for the auth surface."""

from __future__ import annotations


class AuthError(Exception):
    """Base for all auth-domain errors."""


class DuplicateEmailError(AuthError):
    """Registration with an email that already exists (HTTP 409)."""


class InvalidCredentialsError(AuthError):
    """Always raised with a generic message — never leaks which condition failed."""


class InvalidRefreshTokenError(AuthError):
    """Refresh token missing, revoked, or expired (HTTP 401)."""


class CrossAthleteAccessError(AuthError):
    """JWT athlete_id does not match the path athlete_id (HTTP 403)."""


class UnauthenticatedError(AuthError):
    """JWT missing, malformed, or expired (HTTP 401)."""
