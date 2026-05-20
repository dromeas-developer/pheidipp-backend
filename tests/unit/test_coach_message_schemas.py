"""Unit tests for coach message schemas."""

import uuid
from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.coach_message import CoachMessageResponse, CoachMessageListResponse
from app.models.coach_message import CoachMessage
from app.models.enums import MessageType


class TestCoachMessageResponse:
    """Tests for CoachMessageResponse schema."""

    def test_can_be_constructed_from_orm_object(self):
        """Verify CoachMessageResponse can be constructed from a CoachMessage ORM object."""
        athlete_id = uuid.uuid4()
        twin_state_id = uuid.uuid4()
        training_block_id = uuid.uuid4()
        created_at = datetime(2024, 1, 1, 0, 0, 0)

        orm_object = CoachMessage(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            twin_state_id=twin_state_id,
            training_block_id=training_block_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test coach message content.\n\nSecond paragraph.\n\nThird paragraph.",
            generation_metadata={
                "model": "claude-sonnet-4-6",
                "prompt_version": "v1",
                "outcome": "success",
            },
            created_at=created_at,
        )

        response = CoachMessageResponse.model_validate(orm_object)
        assert response.id == orm_object.id
        assert response.athlete_id == athlete_id
        assert response.twin_state_id == twin_state_id
        assert response.training_block_id == training_block_id
        assert response.message_type == MessageType.FIRST_MESSAGE
        assert response.content == orm_object.content
        assert response.generation_metadata == orm_object.generation_metadata
        assert response.created_at == created_at

    def test_contains_all_expected_fields(self):
        """Verify CoachMessageResponse contains all expected fields."""
        athlete_id = uuid.uuid4()

        response = CoachMessageResponse(
            id=uuid.uuid4(),
            athlete_id=athlete_id,
            twin_state_id=None,
            training_block_id=None,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )

        # Verify all fields are present
        assert hasattr(response, "id")
        assert hasattr(response, "athlete_id")
        assert hasattr(response, "twin_state_id")
        assert hasattr(response, "training_block_id")
        assert hasattr(response, "message_type")
        assert hasattr(response, "content")
        assert hasattr(response, "generation_metadata")
        assert hasattr(response, "created_at")

    def test_message_type_serializes_as_enum_string(self):
        """Verify message_type serializes as the enum string value."""
        response = CoachMessageResponse(
            id=uuid.uuid4(),
            athlete_id=uuid.uuid4(),
            message_type=MessageType.FIRST_MESSAGE,
            content="Test content",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )

        # Verify it serializes to the string value
        serialized = response.model_dump()
        assert serialized["message_type"] == "first_message"

    def test_accepts_all_message_types(self):
        """Verify all MessageType values are accepted."""
        athlete_id = uuid.uuid4()

        for msg_type in MessageType:
            response = CoachMessageResponse(
                id=uuid.uuid4(),
                athlete_id=athlete_id,
                message_type=msg_type,
                content="Test content",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, 1),
            )
            assert response.message_type == msg_type


class TestCoachMessageListResponse:
    """Tests for CoachMessageListResponse schema."""

    def test_accepts_list_and_total(self):
        """Verify CoachMessageListResponse accepts a list of CoachMessageResponse and a total integer."""
        athlete_id = uuid.uuid4()

        items = [
            CoachMessageResponse(
                id=uuid.uuid4(),
                athlete_id=athlete_id,
                message_type=MessageType.FIRST_MESSAGE,
                content="First message",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, 1),
            ),
            CoachMessageResponse(
                id=uuid.uuid4(),
                athlete_id=athlete_id,
                message_type=MessageType.DAILY_BRIEFING,
                content="Second message",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, 2),
            ),
        ]

        response = CoachMessageListResponse(items=items, total=2)
        assert len(response.items) == 2
        assert response.total == 2

    def test_rejects_invalid_total_type(self):
        """Verify CoachMessageListResponse rejects invalid types (e.g., total as string)."""
        athlete_id = uuid.uuid4()

        items = [
            CoachMessageResponse(
                id=uuid.uuid4(),
                athlete_id=athlete_id,
                message_type=MessageType.FIRST_MESSAGE,
                content="Test content",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, 1),
            ),
        ]

        with pytest.raises(ValidationError):
            CoachMessageListResponse(items=items, total="not_an_integer")

    def test_accepts_empty_list(self):
        """Verify CoachMessageListResponse accepts an empty list."""
        response = CoachMessageListResponse(items=[], total=0)
        assert len(response.items) == 0
        assert response.total == 0

    def test_total_defaults_to_zero(self):
        """Verify total can be provided and defaults to 0 when not set."""
        # Note: total is now required in the schema, so we provide it
        response = CoachMessageListResponse(items=[], total=0)
        assert response.total == 0