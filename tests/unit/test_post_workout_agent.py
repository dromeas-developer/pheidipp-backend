"""Unit tests for PostWorkoutAgent — idempotent three-paragraph message generation.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
docs/architecture/03-agents/post-workout-agent.md
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.post_workout_agent import (
    PostWorkoutAgent,
    PostWorkoutContext,
    describe_load,
    format_phase_position,
)
from app.models.activity import Activity
from app.models.coaching_message import CoachingMessage
from app.models.enums import RecoveryModifierLevel, TwinConfidenceLevel
from app.models.twin_state import TwinState
from app.services.compliance_service import ComplianceFindings


class TestDescribeLoad:
    """describe_load renders aerobic_load as plain-language descriptor."""

    def test_none_returns_no_load_recorded(self) -> None:
        assert describe_load(None) == "no load recorded"

    def test_light_load_under_30(self) -> None:
        assert describe_load(15.0) == "light aerobic load"

    def test_moderate_load_30_to_60(self) -> None:
        assert describe_load(45.0) == "moderate aerobic load"

    def test_steady_load_60_to_100(self) -> None:
        assert describe_load(80.0) == "steady aerobic load"

    def test_heavy_load_100_plus(self) -> None:
        assert describe_load(150.0) == "heavy aerobic load"


class TestFormatPhasePosition:
    """format_phase_position renders plan position for paragraph 3."""

    def test_no_planned_session_returns_neutral_phrase(self) -> None:
        twin_state = MagicMock()
        result = format_phase_position(None, twin_state)
        assert "early in the current training block" in result

    def test_with_planned_session_formats_week_and_phase(self) -> None:
        twin_state = MagicMock()
        planned_session = MagicMock()
        planned_session.week_number = 3
        # Mock the enum value
        planned_session.phase_label = MagicMock(value="threshold_build")
        result = format_phase_position(planned_session, twin_state)
        assert "week 3" in result
        assert "threshold build" in result


class TestPostWorkoutContext:
    """PostWorkoutContext dataclass serialisation."""

    def test_to_dict_includes_all_fields(self) -> None:
        ctx = PostWorkoutContext(
            prescribed={"session_type": "long_run"},
            compliance={"duration_delta_pct": 0.0},
            execution=None,
            comparable_session=None,
            objective_updates=[],
            readiness={"level": "green"},
            load_scores={"aerobic_load": 85.0},
        )
        d = ctx.to_dict()
        assert "prescribed" in d
        assert "compliance" in d
        assert "execution" in d
        assert "comparable_session" in d
        assert "objective_updates" in d
        assert "readiness" in d
        assert "load_scores" in d


class TestPostWorkoutAgentIdempotency:
    """Idempotency gate: second call returns existing message without LLM call."""

    @pytest.mark.asyncio
    async def test_idempotent_returns_existing_message(self) -> None:
        """When a CoachingMessage already exists, generate() returns it without LLM call."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        uuid.uuid4()

        # Existing message
        existing_message = MagicMock(spec=CoachingMessage)
        existing_message.id = uuid.uuid4()
        existing_message.content = "Already generated message"

        # Mock activity — must have matching athlete_id so the
        # activity-existence gate in generate() passes.
        mock_activity = MagicMock(spec=Activity)
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id

        # Mock repositories
        mock_coaching_messages = AsyncMock()
        mock_coaching_messages.get_by_activity_and_type.return_value = existing_message

        mock_gen_events = AsyncMock()
        mock_activities = AsyncMock()
        mock_activities.get_by_id.return_value = mock_activity
        mock_twin_states = AsyncMock()
        mock_planned_sessions = AsyncMock()
        mock_compliance = MagicMock()
        mock_prompt_registry = MagicMock()

        agent = PostWorkoutAgent(
            # session is stored as self._session and used for session.execute()
            # in _read_profile_date_of_birth(). MagicMock is sufficient since
            # the short-circuit path does not call _session.flush().
            session=MagicMock(),
            coaching_messages=mock_coaching_messages,
            generation_events=mock_gen_events,
            activities=mock_activities,
            planned_sessions=mock_planned_sessions,
            twin_states=mock_twin_states,
            prompt_registry=mock_prompt_registry,
            compliance_service=mock_compliance,
        )

        result = await agent.generate(athlete_id=athlete_id, activity_id=activity_id)

        assert result == existing_message
        mock_coaching_messages.get_by_activity_and_type.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotent_does_not_invoke_llm(self) -> None:
        """When existing message is found, no LLM call is made."""
        from unittest.mock import patch

        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        existing_message = MagicMock(spec=CoachingMessage)
        existing_message.id = uuid.uuid4()
        existing_message.content = "Existing content"

        # Mock activity — must pass the athlete_id check in generate().
        mock_activity = MagicMock(spec=Activity)
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id

        mock_coaching_messages = AsyncMock()
        mock_coaching_messages.get_by_activity_and_type.return_value = existing_message

        mock_activities = AsyncMock()
        mock_activities.get_by_id.return_value = mock_activity

        agent = PostWorkoutAgent(
            # session stored as self._session; short-circuit path doesn't use it.
            session=MagicMock(),
            coaching_messages=mock_coaching_messages,
            generation_events=AsyncMock(),
            activities=mock_activities,
            planned_sessions=AsyncMock(),
            twin_states=AsyncMock(),
            prompt_registry=MagicMock(),
        )

        # Patch the LLM client to fail if called
        with patch("openai.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = AssertionError(
                "LLM should not be called when message exists"
            )
            result = await agent.generate(athlete_id=athlete_id, activity_id=activity_id)

        assert result == existing_message


class TestPostWorkoutAgentLLMCall:
    """Every LLM call writes GenerationEvent before the call."""

    @pytest.mark.asyncio
    async def test_generation_event_written_before_llm_call(self) -> None:
        """GenerationEvent with success=True is written after successful LLM call."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        twin_state_id = uuid.uuid4()

        # Mock activity
        mock_activity = MagicMock(spec=Activity)
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        # Must be a float — describe_load does numeric comparison (< 30, etc.).
        # Without this, MagicMock() is compared, raising TypeError.
        mock_activity.aerobic_load = 85.0
        # neuromuscular_load and structural_load are serialised to JSON inside
        # the context dict — MagicMock breaks json.dumps().
        mock_activity.neuromuscular_load = None
        mock_activity.structural_load = None

        # Mock twin state
        mock_twin_state = MagicMock(spec=TwinState)
        mock_twin_state.id = twin_state_id
        # readiness_level.value must be a real string for JSON serialization in
        # the context dict passed to the LLM — MagicMock breaks JSON encoding.
        mock_twin_state.readiness_level = RecoveryModifierLevel.GREEN
        # confidence_level.value is also serialized to JSON — must be a real enum.
        mock_twin_state.confidence_level = TwinConfidenceLevel.LOW

        # Mock repositories
        mock_activities = AsyncMock()
        mock_activities.get_by_id.return_value = mock_activity

        mock_twin_states = AsyncMock()
        mock_twin_states.get_latest.return_value = mock_twin_state

        mock_coaching_messages = AsyncMock()
        mock_coaching_messages.get_by_activity_and_type.return_value = None  # No existing message

        mock_planned_sessions = AsyncMock()
        mock_planned_sessions.get_by_id.return_value = None

        mock_gen_events = AsyncMock()
        mock_gen_events.insert = AsyncMock()

        # Mock prompt registry
        mock_prompt_registry = MagicMock()
        mock_prompt_registry.get_prompt.return_value = "You are a coach."

        # Mock compliance service
        mock_compliance = MagicMock()
        mock_compliance.evaluate.return_value = ComplianceFindings(
            duration_delta_pct=0.0,
            duration_delta_descriptor="duration matched the prescription",
            session_type_match=True,
            session_type_descriptor="session matched",
            has_prescribed_session=False,
        )

        # planned_session_id must be None so the agent skips the
        # planned_sessions.get_by_id path — MagicMock() as id would flow
        # through format_phase_position and corrupt the LLM context string.
        mock_activity.planned_session_id = None

        # Mock LLM response
        mock_llm_response = MagicMock()
        mock_llm_response.usage = MagicMock(total_tokens=100)
        mock_llm_response.choices = [MagicMock(message=MagicMock(content="Para one.\n\nPara two.\n\nPara three."))]

        agent = PostWorkoutAgent(
            session=AsyncMock(),  # must be awaitable — session.commit/flush are async
            coaching_messages=mock_coaching_messages,
            generation_events=mock_gen_events,
            activities=mock_activities,
            planned_sessions=mock_planned_sessions,
            twin_states=mock_twin_states,
            prompt_registry=mock_prompt_registry,
            compliance_service=mock_compliance,
        )

        with patch("app.agents.post_workout_agent.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.return_value = mock_llm_response

            await agent.generate(athlete_id=athlete_id, activity_id=activity_id)

        # Verify GenerationEvent was inserted.
        # self._events = generation_events = mock_gen_events (set in __init__).
        # No patch wrapper needed — use the real _events reference.
        mock_gen_events.insert.assert_called_once()
        call_args = mock_gen_events.insert.call_args
        gen_event = call_args[0][0]
        assert gen_event.success is True
        assert gen_event.failure_reason is None

    @pytest.mark.asyncio
    async def test_llm_failure_writes_failure_event(self) -> None:
        """When LLM call fails, GenerationEvent with success=False is written."""
        from openai import APITimeoutError

        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_activity = MagicMock(spec=Activity)
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        # Must be a float — describe_load does numeric comparison (< 30, etc.).
        mock_activity.aerobic_load = 85.0
        # neuromuscular_load and structural_load are serialised to JSON inside
        # the context dict — MagicMock breaks json.dumps().
        mock_activity.neuromuscular_load = None
        mock_activity.structural_load = None
        # planned_session_id must be None so the agent skips the
        # planned_sessions.get_by_id path — MagicMock() as id would flow
        # through format_phase_position and corrupt the LLM context string.
        mock_activity.planned_session_id = None

        mock_twin_state = MagicMock(spec=TwinState)
        mock_twin_state.id = uuid.uuid4()
        mock_twin_state.readiness_level = RecoveryModifierLevel.GREEN
        mock_twin_state.confidence_level = TwinConfidenceLevel.LOW

        mock_activities = AsyncMock()
        mock_activities.get_by_id.return_value = mock_activity

        mock_twin_states = AsyncMock()
        mock_twin_states.get_latest.return_value = mock_twin_state

        mock_coaching_messages = AsyncMock()
        mock_coaching_messages.get_by_activity_and_type.return_value = None

        mock_planned_sessions = AsyncMock()

        # Use MagicMock() as parent to avoid AsyncMock auto-creating child mocks
        # that could shadow our explicit `insert` AsyncMock assignment. The agent's
        # failure path does `await self._generation_events.insert(GenerationEvent(...))`,
        # which must record on the mock we control.
        mock_gen_events = MagicMock()
        mock_gen_events.insert = AsyncMock()

        mock_prompt_registry = MagicMock()
        mock_prompt_registry.get_prompt.return_value = "You are a coach."

        mock_compliance = MagicMock()
        mock_compliance.evaluate.return_value = ComplianceFindings(
            duration_delta_pct=0.0,
            duration_delta_descriptor="duration matched",
            session_type_match=True,
            session_type_descriptor="matched",
            has_prescribed_session=False,
        )

        agent = PostWorkoutAgent(
            session=MagicMock(),  # session.flush() is NOT called in the failure path
            coaching_messages=mock_coaching_messages,
            generation_events=mock_gen_events,
            activities=mock_activities,
            planned_sessions=mock_planned_sessions,
            twin_states=mock_twin_states,
            prompt_registry=mock_prompt_registry,
            compliance_service=mock_compliance,
        )

        with patch("app.agents.post_workout_agent.AsyncOpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            mock_client.chat.completions.create.side_effect = APITimeoutError(
                request=MagicMock()
            )

            with pytest.raises(Exception):
                await agent.generate(athlete_id=athlete_id, activity_id=activity_id)

        # Verify failure event was inserted.
        # self._generation_events = mock_gen_events (set in __init__).
        # The agent's failure path calls await self._generation_events.insert()
        # with a GenerationEvent(success=False, failure_reason="timeout").
        mock_gen_events.insert.assert_called()
        call_args = mock_gen_events.insert.call_args
        gen_event = call_args[0][0]
        assert gen_event.success is False
        assert gen_event.failure_reason is not None


class TestPostWorkoutAgentValidation:
    """LLM output must be three paragraphs."""

    def test_validate_three_paragraphs_valid(self) -> None:
        """Three-paragraph content passes validation."""
        content = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        # Should not raise
        PostWorkoutAgent._validate_three_paragraphs(content)  # type: ignore

    def test_validate_three_paragraphs_too_few_raises(self) -> None:
        """Content with fewer than 3 paragraphs raises PostWorkoutContractError."""
        content = "Only one paragraph."
        from app.agents.post_workout_agent import PostWorkoutContractError
        with pytest.raises(PostWorkoutContractError):
            PostWorkoutAgent._validate_three_paragraphs(content)  # type: ignore

    def test_validate_three_paragraphs_two_paragraphs_raises(self) -> None:
        """Content with 2 paragraphs raises PostWorkoutContractError."""
        content = "Paragraph one.\n\nParagraph two."
        from app.agents.post_workout_agent import PostWorkoutContractError
        with pytest.raises(PostWorkoutContractError):
            PostWorkoutAgent._validate_three_paragraphs(content)  # type: ignore


class TestPostWorkoutAgentActivityNotFound:
    """Activity not found raises ActivityNotFoundError (404 at API layer)."""

    @pytest.mark.asyncio
    async def test_activity_not_found_raises(self) -> None:
        from app.agents.post_workout_agent import ActivityNotFoundError

        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_activities = AsyncMock()
        mock_activities.get_by_id.return_value = None

        mock_coaching_messages = AsyncMock()
        # Must be None so the idempotency gate does not short-circuit
        # before the activity-not-found check runs.
        mock_coaching_messages.get_by_activity_and_type.return_value = None

        agent = PostWorkoutAgent(
            session=MagicMock(),
            coaching_messages=mock_coaching_messages,
            generation_events=AsyncMock(),
            activities=mock_activities,
            planned_sessions=AsyncMock(),
            twin_states=AsyncMock(),
            prompt_registry=MagicMock(),
        )

        with pytest.raises(ActivityNotFoundError) as exc_info:
            await agent.generate(athlete_id=athlete_id, activity_id=activity_id)

        assert exc_info.value.activity_id == activity_id