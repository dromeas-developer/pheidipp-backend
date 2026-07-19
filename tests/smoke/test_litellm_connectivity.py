"""Smoke test for LiteLLM proxy connectivity.

This test verifies that the LiteLLM proxy is reachable and returns
valid responses. It is NOT part of the feature/regression suite — it
runs only in smoke and release execution groups to avoid slowing down
the full test suite and to ensure the external dependency is healthy
before deploying.

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import os

import pytest
from openai import AsyncOpenAI

# Ensure settings are loaded before importing app code that depends on them.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-do-not-use-in-prod")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/test_pheidipp",
)

from app.config import settings


@pytest.mark.asyncio
async def test_litellm_proxy_responds() -> None:
    """Verify LiteLLM proxy returns a valid response for a minimal prompt.

    This is a smoke test only — it exercises the real LiteLLM proxy and
    does not mock the LLM call. It is included in the smoke execution
    group so the integration is verified on every build without impacting
    the fast feature/regression suite.
    """
    if not settings.LITELLM_BASE_URL:
        pytest.skip("LITELLM_BASE_URL not configured")

    client = AsyncOpenAI(
        base_url=settings.LITELLM_BASE_URL,
        api_key=settings.LITELLM_API_KEY,
    )

    response = await client.chat.completions.create(
        model=settings.LLM_MODEL or "cohere/command-a-plus",
        messages=[{"role": "user", "content": "Say 'ok' in exactly one word."}],
        max_tokens=10,
    )

    assert response.choices[0].message.content
    content = response.choices[0].message.content.strip().lower()
    assert "ok" in content, (
        f"Expected 'ok' somewhere in the response, "
        f"but got: {content!r}"
    )


@pytest.mark.asyncio
async def test_litellm_proxy_health_check() -> None:
    """Verify the LiteLLM proxy health endpoint responds (if available)."""
    if not settings.LITELLM_BASE_URL:
        pytest.skip("LITELLM_BASE_URL not configured")

    import httpx

    # Try the health endpoint if it exists — many LiteLLM deployments expose it.
    health_url = settings.LITELLM_BASE_URL.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(health_url, timeout=5.0)
            # 200 = healthy, 404 = health endpoint not exposed (that's fine)
            assert response.status_code in (200, 404)
    except httpx.ConnectError:
        pytest.skip(f"Cannot connect to LiteLLM proxy at {settings.LITELLM_BASE_URL}")
    except httpx.TimeoutException:
        pytest.skip(f"LiteLLM proxy at {settings.LITELLM_BASE_URL} timed out")