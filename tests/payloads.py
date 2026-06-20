"""Shared payload fixtures for the auth test suite.

This module is intentionally side-effect-free so test files can
``from tests.payloads import _register_payload, _login_payload`` —
the pytest conftest auto-discovers it via fixtures, the test files
import the payload helpers directly, and no module-level engine or
session is constructed at import time.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.models.enums import Sex


def make_register_payload(
    email: str = "athlete@example.com",
    password: str = "ValidPass123!",
    *,
    sex: Sex = Sex.NOT_SPECIFIED,
    height_cm: Optional[float] = 175.0,
    dob: Optional[date] = None,
) -> dict:
    """Return a registration request payload that matches the
    ``RegisterRequest`` schema exactly.
    """
    return {
        "email": email,
        "password": password,
        "profile": {
            "date_of_birth": (dob or date(1990, 1, 1)).isoformat(),
            "sex": sex.value,
            "height_cm": height_cm,
        },
    }


def make_login_payload(
    email: str = "athlete@example.com",
    password: str = "ValidPass123!",
) -> dict:
    """Return a ``LoginRequest`` payload with the given creds."""
    return {"email": email, "password": password}


# Aliases the existing test files already reference.
_register_payload = make_register_payload
_login_payload = make_login_payload
