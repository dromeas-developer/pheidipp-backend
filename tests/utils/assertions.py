"""Shared assertion patterns that codify security and domain invariants."""
from __future__ import annotations

# Security invariants
SECRET_LEAKAGE_FIELDS = (
    "hashed_password",
    "token_hash",
    "provider_tokens",
    "provider_user_id",
)


def assert_no_secrets_in_text(text: str, *, message: str = "") -> None:
    """Assert that no forbidden credential/PII fields appear in text."""
    lower = text.lower()
    for field in SECRET_LEAKAGE_FIELDS:
        assert field not in lower, f"{message or 'Forbidden field'} '{field}' found in response/text."


def assert_no_secrets_in_logs(
    records: list, *, extra_keys: tuple[str, ...] = ()
) -> None:
    """Scan LogRecord.__dict__ for forbidden fields.

    Complements ``cap_auth_logs`` fixture in behaviour tests.
    """
    rendered = " ".join(str(r.__dict__) for r in records).lower()
    for field in (*SECRET_LEAKAGE_FIELDS, "password", *extra_keys):
        assert field not in rendered, f"Secret field '{field}' leaked into logs."
