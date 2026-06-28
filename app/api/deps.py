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
from app.services.onboarding_service import OnboardingService
from app.services.plan_generation_service import PlanGenerationService


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


def build_onboarding_service(
    session: AsyncSession = Depends(get_db),
) -> OnboardingService:
    """Construct an :class:`OnboardingService` for the current request.

    Mirrors :func:`build_auth_service` — every request gets its own
    ``AsyncSession`` so the onboarding transaction is isolated from
    concurrent requests and the underlying connection pool.

    The Plan-1.4 onboarding integration requires the onboarding service
    to share its session with a :class:`PlanGenerationService` so
    ``complete_onboarding`` and ``generate_plan`` participate in the
    same transaction. To avoid silently regressing the
    Phase-1.3-transaction boundary, we keep the legacy factory
    (``OnboardingService`` without a ``plan_service``) for the read
    endpoints (which never call ``complete_onboarding``) and expose a
    separate :func:`build_onboarding_service_with_plan` for the POST
    handler that drives onboarding completion.
    """
    return OnboardingService(session=session)


def build_onboarding_service_with_plan(
    session: AsyncSession = Depends(get_db),
) -> OnboardingService:
    """Construct an :class:`OnboardingService` for the POST onboarding path.

    Wires a :class:`PlanGenerationService` that shares the same
    ``AsyncSession`` so plan generation lands atomically with
    onboarding. Used only by the ``complete_onboarding`` route.
    """
    plan_service = PlanGenerationService(session=session)
    return OnboardingService(
        session=session,
        plan_service=plan_service,
    )


def build_plan_service(
    session: AsyncSession = Depends(get_db),
) -> PlanGenerationService:
    """Construct a :class:`PlanGenerationService` for the current request.

    Used by :func:`build_onboarding_service_with_plan` to wire plan
    generation into onboarding. Read-only ``GET /plan`` family does
    not depend on this — those endpoints query repositories directly
    through ``get_db``.
    """
    return PlanGenerationService(session=session)


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
