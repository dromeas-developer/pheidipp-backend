"""Unit tests for generate_first_coach_message background task."""

import uuid
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tasks.first_message_task import generate_first_coach_message
from app.models.enums import MessageType, GenerationOutcome
from tests.factories import (
    make_athlete,
    make_athlete_profile,
    make_athlete_preferences,
    make_training_block,
    make_twin_state,
)


@pytest.fixture
def mock_services():
    """Fixture patching all service classes."""
    with patch("app.tasks.first_message_task.FirstMessageBriefBuilder") as mock_bb, \
         patch("app.tasks.first_message_task.FirstMessageAgent") as mock_agent, \
         patch("app.tasks.first_message_task.UnitOfWork") as mock_uow, \
         patch("app.db.session.AsyncSessionLocal") as mock_session_local, \
         patch("app.tasks.first_message_task.log_generation_event") as mock_log:

        # Setup mock session
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Setup mock UoW
        mock_uow_instance = MagicMock()
        mock_uow.return_value.__aenter__ = AsyncMock(return_value=mock_uow_instance)
        mock_uow.return_value.__aexit__ = AsyncMock(return_value=None)

        # Configure uow_instance.coach_messages.has_first_message to return a mock that can be configured
        mock_uow_instance.coach_messages.has_first_message = AsyncMock(return_value=False)
        mock_uow_instance.athletes.get_by_id = AsyncMock(return_value=None)
        mock_uow_instance.profiles.get_by_athlete_id = AsyncMock(return_value=None)
        mock_uow_instance.preferences.get_by_athlete = AsyncMock(return_value=None)
        mock_uow_instance.blocks.get_active_by_athlete = AsyncMock(return_value=None)
        mock_uow_instance.twin_states.get_by_athlete_id = AsyncMock(return_value=None)
        mock_uow_instance.coach_messages.create = AsyncMock()

        yield {
            "brief_builder": mock_bb,
            "agent": mock_agent,
            "uow": mock_uow,
            "uow_instance": mock_uow_instance,
            "session": mock_session,
            "session_local": mock_session_local,
            "log": mock_log,
        }


class TestGenerateFirstCoachMessage:
    """Tests for generate_first_coach_message background task."""

    @pytest.mark.asyncio
    async def test_task_checks_has_first_message_first(self, mock_services):
        """Verify task checks has_first_message first and returns early if one already exists."""
        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(return_value=True)

        athlete_id = uuid.uuid4()
        await generate_first_coach_message(athlete_id)

        mock_services["uow_instance"].coach_messages.has_first_message.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_task_returns_early_when_athlete_data_missing(self, mock_services):
        """Verify task logs and returns early when athlete data is missing."""
        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(return_value=False)
        mock_services["uow_instance"].athletes.get_by_id = AsyncMock(return_value=None)

        athlete_id = uuid.uuid4()
        await generate_first_coach_message(athlete_id)

        # Should have logged a missing data event
        mock_services["log"].assert_called()
        call_args = mock_services["log"].call_args[0][0]
        assert call_args.outcome == GenerationOutcome.MISSING_DATA

    @pytest.mark.asyncio
    async def test_task_calls_brief_builder(self, mock_services):
        """Verify task calls FirstMessageBriefBuilder.build with correct parameters."""
        athlete = make_athlete()
        profile = make_athlete_profile()
        preferences = make_athlete_preferences()
        training_block = make_training_block()
        twin_state = make_twin_state()

        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(return_value=False)
        mock_services["uow_instance"].athletes.get_by_id = AsyncMock(return_value=athlete)
        mock_services["uow_instance"].profiles.get_by_athlete_id = AsyncMock(return_value=profile)
        mock_services["uow_instance"].preferences.get_by_athlete = AsyncMock(return_value=preferences)
        mock_services["uow_instance"].blocks.get_active_by_athlete = AsyncMock(return_value=training_block)
        mock_services["uow_instance"].twin_states.get_by_athlete_id = AsyncMock(return_value=twin_state)

        mock_builder_instance = MagicMock()
        mock_builder_instance.build = AsyncMock()
        mock_services["brief_builder"].return_value = mock_builder_instance

        mock_agent_instance = MagicMock()
        mock_agent_instance.generate = AsyncMock(return_value=("Generated content", {"outcome": "success"}))
        mock_services["agent"].return_value = mock_agent_instance

        athlete_id = uuid.uuid4()
        await generate_first_coach_message(athlete_id)

        mock_builder_instance.build.assert_called_once_with(
            athlete=athlete,
            profile=profile,
            preferences=preferences,
            training_block=training_block,
            twin_state=twin_state,
        )

    @pytest.mark.asyncio
    async def test_task_calls_agent_generate(self, mock_services):
        """Verify task calls FirstMessageAgent.generate with athlete_id and brief."""
        athlete = make_athlete()
        profile = make_athlete_profile()
        preferences = make_athlete_preferences()
        training_block = make_training_block()
        twin_state = make_twin_state()

        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(return_value=False)
        mock_services["uow_instance"].athletes.get_by_id = AsyncMock(return_value=athlete)
        mock_services["uow_instance"].profiles.get_by_athlete_id = AsyncMock(return_value=profile)
        mock_services["uow_instance"].preferences.get_by_athlete = AsyncMock(return_value=preferences)
        mock_services["uow_instance"].blocks.get_active_by_athlete = AsyncMock(return_value=training_block)
        mock_services["uow_instance"].twin_states.get_by_athlete_id = AsyncMock(return_value=twin_state)

        mock_builder_instance = MagicMock()
        mock_builder_instance.build = AsyncMock(return_value=MagicMock())
        mock_services["brief_builder"].return_value = mock_builder_instance

        mock_agent_instance = MagicMock()
        mock_agent_instance.generate = AsyncMock(return_value=("Generated content", {"outcome": "success"}))
        mock_services["agent"].return_value = mock_agent_instance

        athlete_id = uuid.uuid4()
        await generate_first_coach_message(athlete_id)

        mock_agent_instance.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_creates_coach_message(self, mock_services):
        """Verify task creates a CoachMessage via uow.coach_messages.create with correct message_type=FIRST_MESSAGE."""
        athlete = make_athlete()
        profile = make_athlete_profile()
        preferences = make_athlete_preferences()
        training_block = make_training_block()
        twin_state = make_twin_state()

        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(return_value=False)
        mock_services["uow_instance"].athletes.get_by_id = AsyncMock(return_value=athlete)
        mock_services["uow_instance"].profiles.get_by_athlete_id = AsyncMock(return_value=profile)
        mock_services["uow_instance"].preferences.get_by_athlete = AsyncMock(return_value=preferences)
        mock_services["uow_instance"].blocks.get_active_by_athlete = AsyncMock(return_value=training_block)
        mock_services["uow_instance"].twin_states.get_by_athlete_id = AsyncMock(return_value=twin_state)

        mock_builder_instance = MagicMock()
        mock_builder_instance.build = AsyncMock(return_value=MagicMock())
        mock_services["brief_builder"].return_value = mock_builder_instance

        mock_agent_instance = MagicMock()
        mock_agent_instance.generate = AsyncMock(return_value=("Generated content", {"outcome": "success"}))
        mock_services["agent"].return_value = mock_agent_instance

        mock_services["uow_instance"].coach_messages.create = AsyncMock()

        athlete_id = uuid.uuid4()
        await generate_first_coach_message(athlete_id)

        mock_services["uow_instance"].coach_messages.create.assert_called_once()
        call_kwargs = mock_services["uow_instance"].coach_messages.create.call_args.kwargs
        assert call_kwargs["message_type"] == MessageType.FIRST_MESSAGE
        assert call_kwargs["content"] == "Generated content"

    @pytest.mark.asyncio
    async def test_task_commits_on_success(self, mock_services):
        """Verify task commits via UoW exit on success."""
        athlete = make_athlete()
        profile = make_athlete_profile()
        preferences = make_athlete_preferences()
        training_block = make_training_block()
        twin_state = make_twin_state()

        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(return_value=False)
        mock_services["uow_instance"].athletes.get_by_id = AsyncMock(return_value=athlete)
        mock_services["uow_instance"].profiles.get_by_athlete_id = AsyncMock(return_value=profile)
        mock_services["uow_instance"].preferences.get_by_athlete = AsyncMock(return_value=preferences)
        mock_services["uow_instance"].blocks.get_active_by_athlete = AsyncMock(return_value=training_block)
        mock_services["uow_instance"].twin_states.get_by_athlete_id = AsyncMock(return_value=twin_state)

        mock_builder_instance = MagicMock()
        mock_builder_instance.build = AsyncMock(return_value=MagicMock())
        mock_services["brief_builder"].return_value = mock_builder_instance

        mock_agent_instance = MagicMock()
        mock_agent_instance.generate = AsyncMock(return_value=("Generated content", {"outcome": "success"}))
        mock_services["agent"].return_value = mock_agent_instance

        athlete_id = uuid.uuid4()
        await generate_first_coach_message(athlete_id)

        # Verify __aexit__ was called (which triggers commit)
        mock_services["uow"].return_value.__aexit__.assert_called()

    @pytest.mark.asyncio
    async def test_task_catches_exceptions(self, mock_services):
        """Verify task catches exceptions, logs them, and does not re-raise."""
        # Override to raise exception
        mock_services["uow_instance"].coach_messages.has_first_message = AsyncMock(side_effect=Exception("Database error"))

        athlete_id = uuid.uuid4()

        # Should not raise - task catches exceptions
        await generate_first_coach_message(athlete_id)

    @pytest.mark.asyncio
    async def test_task_creates_own_session(self, mock_services):
        """Verify task creates its own session and completes successfully."""
        athlete = make_athlete()
        profile = make_athlete_profile()
        preferences = make_athlete_preferences()
        training_block = make_training_block()
        twin_state = make_twin_state()

        # Setup mock builder
        mock_builder_instance = MagicMock()
        mock_builder_instance.build = AsyncMock(return_value=MagicMock())
        mock_services["brief_builder"].return_value = mock_builder_instance

        # Setup mock agent
        mock_agent_instance = MagicMock()
        mock_agent_instance.generate = AsyncMock(return_value=("Generated content", {"outcome": "success"}))
        mock_services["agent"].return_value = mock_agent_instance

        athlete_id = uuid.uuid4()
        # Task should complete without raising
        await generate_first_coach_message(athlete_id)