"""Email utilities shared across the application."""

from __future__ import annotations


def normalize_email(email: str) -> str:
    """Normalize email to lowercase and strip leading/trailing whitespace.

    Call this before any email persistence or lookup to ensure
    case-insensitive matching. The database enforces uniqueness via
    a lower(email) index on the athletes table.
    """
    return email.strip().lower()
