"""Unit tests for PlanGenerationAgent."""

import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.agents.plan_generation_agent import PlanGenerationAgent


class TestPlanGenerationAgentGenerate:
    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.completions.create = AsyncMock()
        return client

    @pytest.fixture
    def agent(self, mock_client):
        with patch("app.agents.plan_generation_agent.get_llm", return_value=mock_client):
            return PlanGenerationAgent()

    @pytest.mark.asyncio
    async def test_generate_calls_client_with_correct_params(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"weeks": [], "plan_rationale": "Test"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        blueprint_dict, metadata = await agent.generate(MagicMock(), brief)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.2
        assert call_kwargs["response_format"] == {"type": "json_object"}
        assert call_kwargs["model"] is not None
        assert call_kwargs["max_tokens"] is not None

    @pytest.mark.asyncio
    async def test_generate_returns_tuple_on_success(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"weeks": [], "plan_rationale": "Test"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        result = await agent.generate(MagicMock(), brief)

        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_generate_returns_metadata_with_required_fields(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"weeks": [], "plan_rationale": "Test"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        _, metadata = await agent.generate(MagicMock(), brief)

        assert "model" in metadata
        assert "prompt_version" in metadata
        assert "brief_version" in metadata
        assert metadata["outcome"] == "success"
        assert "input_tokens" in metadata
        assert "output_tokens" in metadata
        assert "latency_ms" in metadata
        assert "stop_reason" in metadata

    @pytest.mark.asyncio
    async def test_generate_raises_value_error_for_empty_content(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 0
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with pytest.raises(ValueError, match="empty"):
            await agent.generate(MagicMock(), brief)

    @pytest.mark.asyncio
    async def test_generate_raises_value_error_for_invalid_json(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json {"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with pytest.raises(ValueError, match="JSON"):
            await agent.generate(MagicMock(), brief)

    @pytest.mark.asyncio
    async def test_generate_raises_value_error_for_schema_validation_failure(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"invalid_field": "value"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with pytest.raises(ValueError, match="blueprint"):
            await agent.generate(MagicMock(), brief)

    @pytest.mark.asyncio
    async def test_generate_logs_malformed_event_for_empty_content(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 0
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            with pytest.raises(ValueError):
                await agent.generate(MagicMock(), brief)
            mock_log.assert_called()
            # _log_event is called twice: first MALFORMED, then INTERNAL_ERROR (from outer except)
            first_call = mock_log.call_args_list[0]
            assert first_call.args[1].value == "malformed"

    @pytest.mark.asyncio
    async def test_generate_logs_malformed_event_for_invalid_json(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json {"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            with pytest.raises(ValueError):
                await agent.generate(MagicMock(), brief)
            mock_log.assert_called()
            # _log_event is called twice: first MALFORMED, then INTERNAL_ERROR (from outer except)
            first_call = mock_log.call_args_list[0]
            assert first_call.args[1].value == "malformed"

    @pytest.mark.asyncio
    async def test_generate_logs_success_event_on_successful_generation(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"weeks": [], "plan_rationale": "Test"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            await agent.generate(MagicMock(), brief)
            mock_log.assert_called()
            call_args = mock_log.call_args
            assert call_args.args[1].value == "success"

    @pytest.mark.asyncio
    async def test_generate_catches_api_timeout_and_logs_event(self, agent, mock_client):
        # Create mock exception classes with distinct bases
        class MockTimeoutError(BaseException):
            pass
        class MockAPIStatusError(BaseException):
            pass
        mock_client.chat.completions.create = AsyncMock(side_effect=MockTimeoutError())

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            with patch("app.agents.plan_generation_agent.openai") as mock_openai:
                mock_openai.APITimeoutError = MockTimeoutError
                mock_openai.APIStatusError = MockAPIStatusError
                with pytest.raises(MockTimeoutError):
                    await agent.generate(MagicMock(), brief)
            mock_log.assert_called()
            call_args = mock_log.call_args
            assert call_args.args[1].value == "timeout"

    @pytest.mark.asyncio
    async def test_generate_catches_rate_limit_error(self, agent, mock_client):
        class MockTimeoutError(BaseException):
            pass
        class MockAPIStatusError(BaseException):
            def __init__(self, status_code):
                self.status_code = status_code
        rate_limit_error = MockAPIStatusError(status_code=429)
        mock_client.chat.completions.create = AsyncMock(side_effect=rate_limit_error)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            with patch("app.agents.plan_generation_agent.openai") as mock_openai:
                mock_openai.APITimeoutError = MockTimeoutError
                mock_openai.APIStatusError = MockAPIStatusError
                with pytest.raises(MockAPIStatusError):
                    await agent.generate(MagicMock(), brief)
            mock_log.assert_called()
            call_args = mock_log.call_args
            assert call_args.args[1].value == "rate_limited"

    @pytest.mark.asyncio
    async def test_generate_catches_non_rate_limit_api_status_error(self, agent, mock_client):
        class MockTimeoutError(BaseException):
            pass
        class MockAPIStatusError(BaseException):
            def __init__(self, status_code):
                self.status_code = status_code
        status_error = MockAPIStatusError(status_code=500)
        mock_client.chat.completions.create = AsyncMock(side_effect=status_error)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            with patch("app.agents.plan_generation_agent.openai") as mock_openai:
                mock_openai.APITimeoutError = MockTimeoutError
                mock_openai.APIStatusError = MockAPIStatusError
                with pytest.raises(MockAPIStatusError):
                    await agent.generate(MagicMock(), brief)
            mock_log.assert_called()
            call_args = mock_log.call_args
            assert call_args.args[1].value == "provider_error"

    @pytest.mark.asyncio
    async def test_generate_always_logs_before_return_or_raise(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"weeks": [], "plan_rationale": "Test"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        with patch.object(agent, "_log_event") as mock_log:
            await agent.generate(MagicMock(), brief)
            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_computes_latency_using_monotonic(self, agent, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"weeks": [], "plan_rationale": "Test"}'
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={})

        _, metadata = await agent.generate(MagicMock(), brief)

        assert metadata["latency_ms"] >= 0


class TestPlanGenerationAgentBuildUserMessage:
    def test_build_user_message_serializes_brief_to_json(self):
        from app.agents.plan_generation_agent import PlanGenerationAgent
        from app.agents.prompts.plan_generation_v1 import _build_user_message
        from app.models.enums import MethodologyTrait
        from app.schemas.plan_generation import MethodologyProfile, PhaseArc, PhaseArcPhase

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={
            "brief_version": "v1",
            "athlete_summary": {"name": "John"},
            "goal_summary": {"goal_event_type": "marathon"},
            "twin_summary": {"fitness_score": 0.7},
            "available_days": {"mon": {}},
            "phase_arc": {
                "total_weeks": 16,
                "phases": [{"phase": "base", "start_week": 1, "end_week": 16}],
                "recovery_weeks": [],
            },
            "explicit_constraints": [],
            "coaching_insights": {},
            "methodology_profile": {
                "trait_weights": {
                    MethodologyTrait.HIGH_AEROBIC_VOLUME: 1.0
                }
            },
        })

        msg = _build_user_message(brief)

        assert "athlete_summary" in msg
        assert "goal_summary" in msg
        assert "twin_summary" in msg
        assert "available_days" in msg
        assert "phase_arc" in msg
        assert "explicit_constraints" in msg
        assert "coaching_insights" in msg
        assert "methodology_profile" in msg

    def test_build_user_message_converts_enum_keys_to_strings(self):
        from app.agents.prompts.plan_generation_v1 import _build_user_message
        from app.models.enums import MethodologyTrait

        brief = MagicMock()
        brief.model_dump = MagicMock(return_value={
            "brief_version": "v1",
            "athlete_summary": {},
            "goal_summary": {},
            "twin_summary": {},
            "available_days": {},
            "phase_arc": {
                "total_weeks": 16,
                "phases": [{"phase": "base", "start_week": 1, "end_week": 16}],
                "recovery_weeks": [],
            },
            "explicit_constraints": [],
            "coaching_insights": {},
            "methodology_profile": {
                "trait_weights": {
                    MethodologyTrait.HIGH_AEROBIC_VOLUME: 1.0
                }
            },
        })

        msg = _build_user_message(brief)

        assert "HIGH_AEROBIC_VOLUME" in msg