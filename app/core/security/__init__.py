"""Security primitives: hashing, token issuance, and request authentication.

This package owns credential hashing (passwords and refresh-token digests)
and the signing/verification of access tokens. It does not own athlete
identity, which lives in the model layer.
"""

from app.core.security.password_hasher import BCRYPT_COST, PasswordHasher
from app.core.security.token_service import (
    AccessTokenClaims,
    TokenService,
    TokenVerificationError,
)

__all__ = [
    "AccessTokenClaims",
    "BCRYPT_COST",
    "PasswordHasher",
    "TokenService",
    "TokenVerificationError",
]
