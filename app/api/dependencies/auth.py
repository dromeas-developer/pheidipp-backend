import logging
import uuid
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.core.jwt import decode_access_token

logger = logging.getLogger("pheidipp.auth")

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_athlete_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> uuid.UUID:
    """Extract and validate athlete ID from JWT access token.
    
    Raises:
        HTTPException: 401 if token is missing or invalid.
    """
    if credentials is None:
        logger.warning("auth.token.missing")
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        athlete_id = decode_access_token(credentials.credentials)
    except JWTError:
        logger.warning("auth.token.invalid")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return athlete_id


async def require_self(
    athlete_id: uuid.UUID,
    current_athlete_id: uuid.UUID = Depends(get_current_athlete_id),
) -> uuid.UUID:
    """Require that the current user is the same as the requested resource owner.
    
    Use for routes that take an athlete_id path parameter to ensure
    users can only access their own data.
    
    Raises:
        HTTPException: 403 if access denied.
    """
    if athlete_id != current_athlete_id:
        logger.warning(
            "auth.access.denied",
            extra={
                "requested_athlete_id": str(athlete_id),
                "current_athlete_id": str(current_athlete_id),
            },
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )

    return current_athlete_id