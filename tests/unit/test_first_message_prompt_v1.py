"""Unit tests for first_message_v1 prompt module."""

import pytest

from app.agents.prompts import first_message_v1
from app.agents.prompts.registry import PromptRegistry


class TestFirstMessagePromptV1:
    """Tests for first_message_v1 module constants and self-registration."""

    def test_prompt_version_equals_v1(self):
        """Verify PROMPT_VERSION == 'v1'."""
        assert first_message_v1.PROMPT_VERSION == "v1"

    def test_system_prompt_is_non_empty_string(self):
        """Verify SYSTEM_PROMPT is a non-empty string."""
        assert isinstance(first_message_v1.SYSTEM_PROMPT, str)
        assert len(first_message_v1.SYSTEM_PROMPT) > 0

    def test_system_prompt_contains_coaching_voice_guidelines(self):
        """Verify SYSTEM_PROMPT contains coaching voice guidelines."""
        prompt = first_message_v1.SYSTEM_PROMPT

        # Should have voice guidelines
        assert "coach" in prompt.lower() or "coaching" in prompt.lower()

    def test_system_prompt_no_cheerleader_phrases(self):
        """Verify SYSTEM_PROMPT does not contain cheerleader phrases."""
        prompt = first_message_v1.SYSTEM_PROMPT.lower()

        # These phrases should not appear
        assert "you've got this" not in prompt
        assert "believe in yourself" not in prompt

    def test_system_prompt_no_precise_numbers(self):
        """Verify SYSTEM_PROMPT instructs not to mention precise numbers."""
        prompt = first_message_v1.SYSTEM_PROMPT.lower()

        # Should have guidance about not using precise numbers
        assert "precise" in prompt or "numbers" in prompt or "threshold" in prompt

    def test_max_output_tokens_equals_600(self):
        """Verify MAX_OUTPUT_TOKENS == 600."""
        assert first_message_v1.MAX_OUTPUT_TOKENS == 600

    def test_module_registers_prompt_in_registry(self):
        """Verify importing the module registers the prompt in PromptRegistry under agent 'first_message', version 'v1'."""
        # The prompt should already be registered from the import
        record = PromptRegistry.get("first_message", "v1")

        assert record.version == "v1"
        assert record.system_prompt == first_message_v1.SYSTEM_PROMPT
        assert record.max_output_tokens == first_message_v1.MAX_OUTPUT_TOKENS