import hashlib
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from jose import jwt, JWTError
from jose.exceptions import JWTError as JOSEJWTError

from app.config import settings

logger = logging.getLogger("pheidipp.jwt")


def create_access_token(athlete_id: uuid.UUID) -> str:
    """Create a JWT access token with athlete_id as subject."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(athlete_id),
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token() -> Tuple[str, str]:
    """Create a raw refresh token and its hash.
    
    Returns:
        Tuple of (raw_token, token_hash). Raw token goes to client, hash stored in DB.
    """
    raw = uuid.uuid4().hex + uuid.uuid4().hex
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    return raw, token_hash


def decode_access_token(token: str) -> uuid.UUID:
    """Decode and validate an access token.
    
    Returns:
        The athlete_id UUID from the token's subject.
        
    Raises:
        JWTError: If token is invalid, expired, or missing required claims.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JOSEJWTError as e:
        logger.warning("jwt.decode.failed", extra={"error": str(e)})
        raise JWTError("Invalid token")

    # Validate required claims
    required_keys = {"sub", "type", "jti", "iss", "exp"}
    missing = required_keys - set(payload.keys())
    if missing:
        logger.warning("jwt.payload.missing_keys", extra={"missing": missing})
        raise JWTError("Invalid token: missing claims")

    # Validate token type
    if payload.get("type") != "access":
        logger.warning("jwt.payload.invalid_type", extra={"type": payload.get("type")})
        raise JWTError("Invalid token type")

    # Validate issuer
    if payload.get("iss") != settings.JWT_ISSUER:
        logger.warning("jwt.payload.invalid_issuer", extra={"iss": payload.get("iss")})
        raise JWTError("Invalid token issuer")

    # Parse and validate subject as UUID
    try:
        athlete_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        logger.warning("jwt.payload.invalid_sub", extra={"sub": payload.get("sub")})
        raise JWTError("Invalid token subject")

    return athlete_id


def hash_token(raw: str) -> str:
    """Hash a raw token using SHA-256."""
    return hashlib.sha256(raw.encode()).hexdigest()