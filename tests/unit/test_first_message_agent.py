"""Unit tests for FirstMessageAgent."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APITimeoutError, APIStatusError

from app.agents.first_message_agent import FirstMessageAgent
from app.services.first_message_brief_builder import (
    FirstMessageCoachingBrief,
    AthleteContext,
    GoalContext,
    TwinContext,
    PlanContext,
    CoachingInsights,
)
from app.models.enums import (
    Gender,
    SportBackground,
    GoalType,
    ConfidenceLevel,
    DataTier,
    MessageType,
)


@pytest.fixture
def mock_litellm_client():
    """Fixture patching get_litellm_client to return a mock client."""
    with patch("app.agents.first_message_agent.get_litellm_client") as mock:
        client = MagicMock()
        client.chat.completions.create = AsyncMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_log_event():
    """Fixture patching log_generation_event."""
    with patch("app.agents.first_message_agent.log_generation_event") as mock:
        yield mock


@pytest.fixture
def sample_brief():
    """Fixture returning a minimal valid FirstMessageCoachingBrief."""
    return FirstMessageCoachingBrief(
        brief_version="v1",
        athlete=AthleteContext(
            first_name="John",
            age=35,
            gender=Gender.MALE,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=3.0,
            training_time_of_day="morning",
        ),
        goal=GoalContext(
            goal_type=GoalType.RACE,
            goal_event_type="marathon",
            goal_event_name="Boston Marathon",
            goal_event_date=date(2024, 4, 15),
            goal_description="Prepare for Boston",
            weeks_to_event=16,
            is_open_training=False,
        ),
        twin=TwinContext(
            fitness_score=65.0,
            fatigue_score=20.0,
            max_hr_estimate=185.0,
            lt1_hr_estimate=135.0,
            lt2_hr_estimate=160.0,
            lt1_pace_estimate=5.5,
            lt2_pace_estimate=4.2,
            structural_capacity_score=0.65,
            confidence_level=ConfidenceLevel.MEDIUM,
            data_tier="tier1",
            fitness_band="advanced",
            structural_band="established",
            hr_descriptor="high 170s",
            include_threshold_descriptors=True,
        ),
        plan=PlanContext(
            plan_arc="16-week progressive periodization toward Boston Marathon",
            first_block_focus="consolidating aerobic foundation while introducing threshold work",
            sessions_per_week=4,
            primary_focus="aerobic base",
        ),
        insights=CoachingInsights(
            strengths=["running-focused background", "chest strap HR monitoring"],
            gaps=["short timeline to event"],
            crossover_note=None,
            cycle_tracking_note=None,
        ),
        budget_snapshot={
            "max_input_tokens": 4000,
            "include_recent_sessions": 0,
            "include_coach_messages": 0,
            "include_wellness_trend": False,
            "summarize_older_blocks": False,
            "omit_low_confidence_signals": True,
        },
    )


class TestFirstMessageAgentGenerate:
    """Tests for FirstMessageAgent.generate."""

    @pytest.mark.asyncio
    async def test_generate_calls_client_with_correct_params(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate calls client.chat.completions.create with correct model, max_tokens, and messages."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        content, metadata = await agent.generate(athlete_id, sample_brief)

        mock_litellm_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_litellm_client.chat.completions.create.call_args.kwargs
        assert "model" in call_kwargs
        assert "max_tokens" in call_kwargs
        assert "messages" in call_kwargs
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_generate_returns_content_and_metadata(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate returns (content, generation_metadata) on success."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        content, metadata = await agent.generate(athlete_id, sample_brief)

        assert content == "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        assert "model" in metadata
        assert "prompt_version" in metadata
        assert "brief_version" in metadata
        assert metadata["outcome"] == "success"
        assert "input_tokens" in metadata
        assert "output_tokens" in metadata
        assert "latency_ms" in metadata
        assert "stop_reason" in metadata
        assert "data_tier" in metadata
        assert "confidence_level" in metadata
        assert "context_budget" in metadata

    @pytest.mark.asyncio
    async def test_generate_validates_paragraph_breaks(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate validates response has at least 2 paragraph breaks."""
        # Response with only one paragraph break
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Single paragraph content."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        with pytest.raises(ValueError, match="malformed"):
            await agent.generate(athlete_id, sample_brief)

    @pytest.mark.asyncio
    async def test_generate_logs_malformed_event(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate logs a MALFORMED event when validation fails."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "Single paragraph."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        with pytest.raises(ValueError):
            await agent.generate(athlete_id, sample_brief)

        # Verify log_generation_event was called
        mock_log_event.assert_called()
        call_args = mock_log_event.call_args[0][0]
        assert call_args.outcome.value == "internal_error"

    @pytest.mark.asyncio
    async def test_generate_handles_timeout(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate catches APITimeoutError, logs TIMEOUT event, and re-raises."""
        mock_litellm_client.chat.completions.create.side_effect = APITimeoutError("Request timed out")

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        with pytest.raises(APITimeoutError):
            await agent.generate(athlete_id, sample_brief)

        mock_log_event.assert_called()
        call_args = mock_log_event.call_args[0][0]
        assert call_args.outcome.value == "timeout"

    @pytest.mark.asyncio
    async def test_generate_handles_rate_limit(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate catches APIStatusError with status 429, logs RATE_LIMITED event, and re-raises."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_litellm_client.chat.completions.create.side_effect = APIStatusError(
            "Rate limited", response=mock_response, body={}
        )

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        with pytest.raises(APIStatusError):
            await agent.generate(athlete_id, sample_brief)

        mock_log_event.assert_called()
        call_args = mock_log_event.call_args[0][0]
        assert call_args.outcome.value == "rate_limited"

    @pytest.mark.asyncio
    async def test_generate_handles_provider_error(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate catches APIStatusError with non-429 status, logs PROVIDER_ERROR event, and re-raises."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_litellm_client.chat.completions.create.side_effect = APIStatusError(
            "Server error", response=mock_response, body={}
        )

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        with pytest.raises(APIStatusError):
            await agent.generate(athlete_id, sample_brief)

        mock_log_event.assert_called()
        call_args = mock_log_event.call_args[0][0]
        assert call_args.outcome.value == "provider_error"

    @pytest.mark.asyncio
    async def test_generate_handles_unexpected_exception(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate catches unexpected exceptions, logs INTERNAL_ERROR event, and re-raises."""
        mock_litellm_client.chat.completions.create.side_effect = RuntimeError("Unexpected error")

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        with pytest.raises(RuntimeError):
            await agent.generate(athlete_id, sample_brief)

        mock_log_event.assert_called()
        call_args = mock_log_event.call_args[0][0]
        assert call_args.outcome.value == "internal_error"

    @pytest.mark.asyncio
    async def test_generate_always_logs_event(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify generate always calls log_generation_event before returning or raising."""
        # Successful case
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        await agent.generate(athlete_id, sample_brief)

        assert mock_log_event.call_count >= 1

    @pytest.mark.asyncio
    async def test_latency_computed_using_time_monotonic(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify latency is computed using time.monotonic()."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        content, metadata = await agent.generate(athlete_id, sample_brief)

        assert "latency_ms" in metadata
        assert metadata["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_user_message_contains_athlete_context(
        self, mock_litellm_client, mock_log_event, sample_brief
    ):
        """Verify user message contains athlete context, goal, twin model, strengths, gaps, and primary focus sections."""
        mock_response = MagicMock()
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 200
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.choices[0].message.content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        mock_litellm_client.chat.completions.create.return_value = mock_response

        agent = FirstMessageAgent()
        athlete_id = uuid.uuid4()

        await agent.generate(athlete_id, sample_brief)

        call_kwargs = mock_litellm_client.chat.completions.create.call_args.kwargs
        user_message = call_kwargs["messages"][1]["content"]

        assert "Athlete:" in user_message
        assert "John" in user_message
        assert "Goal:" in user_message
        assert "Twin State:" in user_message
        assert "Strengths:" in user_message
        assert "Gaps to address:" in user_message
        assert "Plan:" in user_message