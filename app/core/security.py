import secrets
import hashlib
import hmac


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2 with SHA256."""
    salt = secrets.token_hex(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a hash."""
    if not hashed:
        return False
    try:
        salt, stored_hash = hashed.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(dk.hex(), stored_hash)
    except (ValueError, TypeError):
        return False
