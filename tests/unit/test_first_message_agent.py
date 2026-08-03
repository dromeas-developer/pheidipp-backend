"""Unit tests for FirstMessageAgent — pure logic, no LLM, no DB.

Covers the static helpers (paragraph-count validation), the LLM-client
construction (proxy routing per ADR-007), and the model-name format
(logical provider/model identifier).
"""

from __future__ import annotations

import re

from app.agents.first_message_agent import (
    FirstMessageAgent,
    ParagraphCountViolationError,
)


class TestValidateParagraphCount:
    def test_four_paragraphs_accepted(self):
        content = "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        FirstMessageAgent.validate_paragraph_count(content)

    def test_three_paragraphs_rejected(self):
        content = "Para one.\n\nPara two.\n\nPara three."
        try:
            FirstMessageAgent.validate_paragraph_count(content)
        except ParagraphCountViolationError as exc:
            assert "expected 4 paragraphs, got 3" in str(exc)
        else:
            raise AssertionError("ParagraphCountViolationError not raised")

    def test_five_paragraphs_rejected(self):
        content = "1\n\n2\n\n3\n\n4\n\n5"
        try:
            FirstMessageAgent.validate_paragraph_count(content)
        except ParagraphCountViolationError as exc:
            assert "expected 4 paragraphs, got 5" in str(exc)
        else:
            raise AssertionError("ParagraphCountViolationError not raised")

    def test_single_paragraph_rejected(self):
        content = "Only one paragraph with no double-newlines."
        try:
            FirstMessageAgent.validate_paragraph_count(content)
        except ParagraphCountViolationError as exc:
            assert "expected 4 paragraphs, got 1" in str(exc)
        else:
            raise AssertionError("ParagraphCountViolationError not raised")

    def test_empty_content_rejected(self):
        try:
            FirstMessageAgent.validate_paragraph_count("")
        except ParagraphCountViolationError as exc:
            assert "expected 4 paragraphs, got 0" in str(exc)
        else:
            raise AssertionError("ParagraphCountViolationError not raised")

    def test_excess_whitespace_paragraphs_trimmed(self):
        content = "\n\nPara one.\n\n\n\nPara two.\n\n   Para three.\n\nPara four.\n\n"
        FirstMessageAgent.validate_paragraph_count(content)


class TestProxyRouting:
    def test_build_llm_client_returns_async_openai_with_proxy_base_url(self):
        from openai import AsyncOpenAI

        from app.config import settings

        instance = FirstMessageAgent.__new__(FirstMessageAgent)
        client = instance._build_llm_client()

        assert isinstance(client, AsyncOpenAI)
        assert client.base_url == settings.LITELLM_BASE_URL
        assert client.api_key == settings.LITELLM_API_KEY

    def test_no_direct_provider_sdk_imports(self):
        import app.agents.first_message_agent as module

        source = open(module.__file__).read()
        forbidden_imports = [
            r"^\s*import anthropic\b",
            r"^\s*from anthropic\b",
            r"^\s*import cohere\b",
            r"^\s*from cohere\b",
        ]
        for pattern in forbidden_imports:
            match = re.search(pattern, source, flags=re.MULTILINE)
            assert match is None, (
                f"Forbidden direct provider SDK import found: {match.group(0)}"
            )


class TestLogicalModelIdentifier:
    def test_default_model_name_uses_provider_slash_model_format(self):
        from app.config import settings

        if settings.LLM_MODEL:
            assert "/" in settings.LLM_MODEL, (
                f"LLM_MODEL {settings.LLM_MODEL!r} must use '<provider>/<model>' format"
            )
            provider, _, model = settings.LLM_MODEL.partition("/")
            assert provider and model, (
                f"LLM_MODEL {settings.LLM_MODEL!r} must have both provider and model parts"
            )