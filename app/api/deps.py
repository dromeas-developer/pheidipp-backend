"""FastAPI dependencies shared by the v1 API surface."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.token_service import TokenService
from app.db.session import get_db as _get_db_session
from app.services.auth_service import AuthService


# Re-export the canonical session dependency under one name so router
# modules have a single import path.
get_db = _get_db_session


_bearer_scheme = HTTPBearer(auto_error=False)


def build_auth_service(
    session: AsyncSession = Depends(get_db),
) -> AuthService:
    """Construct an :class:`AuthService` for the current request.

    The dependency carries a per-request ``AsyncSession`` so each request
    runs in its own database transaction. The session is closed when the
    request finishes.
    """
    return AuthService(session=session)


def _extract_bearer(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def get_current_athlete_id(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> UUID:
    """Decode the access-token Bearer header and return its ``athlete_id``.

    Raises 401 for missing, malformed, or expired tokens. The
    :func:`require_self` dependency enforces the cross-athlete guard on
    top of this.
    """
    token = _extract_bearer(credentials)
    try:
        claims = TokenService().verify_access_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return claims.athlete_id


def require_self(
    path_athlete_id: Annotated[UUID, Path(alias="athlete_id")],
    token_athlete_id: Annotated[UUID, Depends(get_current_athlete_id)],
) -> UUID:
    """Authorize that the JWT's athlete_id matches the path parameter.

    Returns the authenticated athlete_id. Raises 403 (never 404) when the
    path parameter and JWT disagree so that authentication failures can
    be distinguished from authorization failures.
    """
    if path_athlete_id != token_athlete_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to that profile.",
        )
    return token_athlete_id
