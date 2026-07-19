"""Password hashing for the email auth provider."""

from __future__ import annotations

import bcrypt

# Architecture constraint: cost factor >= 12 for bcrypt.
BCRYPT_COST = 12


class PasswordHasher:
    """Bcrypt password hasher/verifier for the email auth provider."""

    @staticmethod
    def hash(password: str) -> str:
        """Hash *password* with bcrypt at the configured cost factor."""
        if not password:
            raise ValueError("password must be a non-empty string")
        # Bcrypt has a 72-byte input cap; truncate to that length to avoid
        # silent truncation asymmetry between hash and verify.
        password_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=BCRYPT_COST)
        return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    @staticmethod
    def verify(password: str, hashed: str) -> bool:
        """Constant-time verification of *password* against the stored bcrypt hash."""
        if not password or not hashed:
            return False
        try:
            password_bytes = password.encode("utf-8")[:72]
            return bcrypt.checkpw(password_bytes, hashed.encode("utf-8"))
        except (ValueError, TypeError):
            return False
