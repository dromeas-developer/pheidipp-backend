"""HTTP-level test helpers for registering athletes and building headers.

These helpers work through the HTTP surface (``httpx.AsyncClient``)
rather than the database directly, so they exercise auth routes and
token issuance as part of test setup.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from httpx import AsyncClient


def bearer_header(token: str) -> dict[str, str]:
    """Return an ``Authorization`` header dict for the given bearer token."""
    return {"Authorization": f"Bearer {token}"}


async def http_register(client: "AsyncClient", email: str) -> tuple[uuid.UUID, str]:
    """Register a fresh athlete through the HTTP surface.

    Returns ``(athlete_id, access_token)``.
    Raises ``AssertionError`` if the registration does not return 201.
    """
    from tests.payloads import _register_payload

    response = await client.post(
        "/api/v1/auth/register", json=_register_payload(email)
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return uuid.UUID(body["athlete"]["id"]), body["access_token"]
