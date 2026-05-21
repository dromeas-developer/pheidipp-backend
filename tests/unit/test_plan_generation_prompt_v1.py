"""Unit tests for plan_generation_v1 prompt registration."""

import pytest

from app.agents.prompts.registry import PromptRegistry


class TestPlanGenerationV1PromptRegistration:
    def test_prompt_registered_under_plan_generation_v1(self):
        record = PromptRegistry.get("plan_generation", "v1")
        assert record is not None
        assert record.version == "v1"

    def test_prompt_has_correct_max_output_tokens(self):
        record = PromptRegistry.get("plan_generation", "v1")
        assert record.max_output_tokens == 4000

    def test_prompt_current_resolves_to_v1(self):
        record = PromptRegistry.current("plan_generation")
        assert record.version == "v1"

    def test_system_prompt_contains_session_types(self):
        from app.agents.prompts.plan_generation_v1 import SYSTEM_PROMPT
        assert "session" in SYSTEM_PROMPT.lower() or "types" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_methodology_tendencies(self):
        from app.agents.prompts.plan_generation_v1 import SYSTEM_PROMPT
        assert "methodology" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_phase_arc(self):
        from app.agents.prompts.plan_generation_v1 import SYSTEM_PROMPT
        assert "phase" in SYSTEM_PROMPT.lower() or "arc" in SYSTEM_PROMPT.lower()

    def test_system_prompt_describes_soft_guidance(self):
        from app.agents.prompts.plan_generation_v1 import SYSTEM_PROMPT
        # The system prompt should indicate methodology is soft guidance
        assert "guidance" in SYSTEM_PROMPT.lower() or "guideline" in SYSTEM_PROMPT.lower() or "tendency" in SYSTEM_PROMPT.lower()