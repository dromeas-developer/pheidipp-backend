"""Unit tests for get_litellm_client."""

from unittest.mock import patch, MagicMock

import pytest

from app.core.llm import get_litellm_client
from app.config import settings


class TestGetLitellmClient:
    """Tests for get_litellm_client singleton."""

    def test_returns_async_openai_instance(self):
        """Verify get_litellm_client returns an AsyncOpenAI instance."""
        client = get_litellm_client()
        # Check it's an AsyncOpenAI instance
        assert hasattr(client, "chat")
        assert hasattr(client, "api_key")

    def test_returns_same_instance_on_repeated_calls(self):
        """Verify get_litellm_client returns the same instance on repeated calls (lru_cache behavior)."""
        client1 = get_litellm_client()
        client2 = get_litellm_client()

        assert client1 is client2

    def test_client_base_url_matches_settings(self):
        """Verify the client's base_url matches settings.LITELLM_BASE_URL."""
        client = get_litellm_client()

        # Compare string representations (strip trailing slash from both sides)
        assert str(client.base_url).rstrip("/") == settings.LITELLM_BASE_URL.rstrip("/")

    def test_client_api_key_matches_settings(self):
        """Verify the client's api_key matches settings.LITELLM_API_KEY."""
        client = get_litellm_client()

        assert client.api_key == settings.LITELLM_API_KEY

    @patch("app.core.llm.lru_cache")
    def test_uses_lru_cache_decorator(self, mock_lru_cache):
        """Verify get_litellm_client uses lru_cache."""
        # The function should have lru_cache applied
        # We can check this by inspecting the function's attributes
        assert hasattr(get_litellm_client, "cache_info") or hasattr(get_litellm_client, "cache_clear")