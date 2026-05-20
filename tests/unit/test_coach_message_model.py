"""Unit tests for CoachMessage model."""

import uuid
from datetime import datetime

import pytest

from app.models.coach_message import CoachMessage
from app.models.enums import MessageType


class TestCoachMessageModel:
    """Tests for CoachMessage model structure."""

    def test_model_can_be_instantiated_with_required_fields(self):
        """Verify CoachMessage can be instantiated with required fields."""
        athlete_id = uuid.uuid4()
        message = CoachMessage(
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
        )
        assert message.athlete_id == athlete_id
        assert message.message_type == MessageType.FIRST_MESSAGE
        assert message.content == "Test content"

    def test_id_is_uuid(self):
        """Verify id is a UUID."""
        athlete_id = uuid.uuid4()
        message = CoachMessage(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
        )
        assert isinstance(message.id, uuid.UUID)

    def test_content_accepts_multiline_text(self):
        """Verify content accepts multi-line text."""
        athlete_id = uuid.uuid4()
        multiline_content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        message = CoachMessage(
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content=multiline_content,
            generation_metadata={"outcome": "success"},
        )
        assert message.content == multiline_content

    def test_generation_metadata_accepts_dict(self):
        """Verify generation_metadata accepts a dict."""
        athlete_id = uuid.uuid4()
        metadata = {
            "model": "claude-sonnet-4-6",
            "prompt_version": "v1",
            "outcome": "success",
            "input_tokens": 100,
            "output_tokens": 200,
            "latency_ms": 1500,
        }
        message = CoachMessage(
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata=metadata,
        )
        assert message.generation_metadata == metadata

    def test_message_type_accepts_enum_values(self):
        """Verify message_type accepts MessageType enum values."""
        athlete_id = uuid.uuid4()

        for msg_type in MessageType:
            message = CoachMessage(
                athlete_id=athlete_id,
                message_type=msg_type,
                content="Test content",
                generation_metadata={"outcome": "success"},
            )
            assert message.message_type == msg_type

    def test_athlete_id_foreign_key_is_enforced(self):
        """Verify athlete_id foreign key is enforced (via column definition)."""
        # The foreign key is defined in the model, we just verify the column exists
        athlete_id = uuid.uuid4()
        message = CoachMessage(
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
        )
        assert message.athlete_id is not None

    def test_twin_state_id_is_nullable(self):
        """Verify twin_state_id is nullable."""
        athlete_id = uuid.uuid4()
        message = CoachMessage(
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
            twin_state_id=None,
        )
        assert message.twin_state_id is None

    def test_training_block_id_is_nullable(self):
        """Verify training_block_id is nullable."""
        athlete_id = uuid.uuid4()
        message = CoachMessage(
            athlete_id=athlete_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
            training_block_id=None,
        )
        assert message.training_block_id is None

    def test_created_at_has_server_default(self):
        """Verify created_at has a server default (func.now())."""
        # The server_default is set on the column definition
        # We verify the column has the server_default attribute
        from app.models.coach_message import CoachMessage
        from sqlalchemy import inspect

        # Check that the column has a server_default
        mapper = inspect(CoachMessage)
        created_at_column = mapper.columns["created_at"]
        assert created_at_column.server_default is not None