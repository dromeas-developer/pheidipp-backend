"""Factory functions for CoachMessage model."""

import uuid
from datetime import datetime

from app.models.coach_message import CoachMessage
from app.models.enums import MessageType


def make_coach_message(
    athlete_id: uuid.UUID | None = None,
    twin_state_id: uuid.UUID | None = None,
    training_block_id: uuid.UUID | None = None,
    **overrides,
) -> CoachMessage:
    """Create a minimal valid CoachMessage instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    # Pop known fields from overrides to avoid duplicate keyword argument errors
    message_type = overrides.pop("message_type", MessageType.FIRST_MESSAGE)
    content = overrides.pop(
        "content",
        "Test coach message content.\n\nSecond paragraph.\n\nThird paragraph.",
    )
    generation_metadata = overrides.pop("generation_metadata", None)
    created_at = overrides.pop("created_at", None)

    # Default generation metadata
    default_metadata = {
        "model": "claude-sonnet-4-6",
        "prompt_version": "v1",
        "outcome": "success",
        "input_tokens": 100,
        "output_tokens": 200,
        "latency_ms": 1500,
        "stop_reason": "stop",
        "data_tier": "tier1",
        "confidence_level": "low",
        "context_budget": {
            "max_input_tokens": 4000,
            "include_recent_sessions": 0,
            "include_coach_messages": 0,
            "include_wellness_trend": False,
            "summarize_older_blocks": False,
            "omit_low_confidence_signals": True,
        },
    }

    return CoachMessage(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        twin_state_id=twin_state_id,
        training_block_id=training_block_id,
        message_type=message_type,
        content=content,
        generation_metadata=generation_metadata or default_metadata,
        created_at=created_at or datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_coach_message_full(
    athlete_id: uuid.UUID | None = None,
    twin_state_id: uuid.UUID | None = None,
    training_block_id: uuid.UUID | None = None,
    **overrides,
) -> CoachMessage:
    """Create a CoachMessage instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    # Pop known fields from overrides to avoid duplicate keyword argument errors
    message_id = overrides.pop("id", None)
    message_type = overrides.pop("message_type", MessageType.FIRST_MESSAGE)
    content = overrides.pop(
        "content",
        "Full coach message with detailed content.\n\nHere is the second paragraph with more details.\n\nAnd the third paragraph with even more information.",
    )
    generation_metadata = overrides.pop("generation_metadata", None)
    created_at = overrides.pop("created_at", None)

    full_metadata = {
        "model": "claude-sonnet-4-6",
        "prompt_version": "v1",
        "outcome": "success",
        "input_tokens": 150,
        "output_tokens": 350,
        "latency_ms": 2000,
        "stop_reason": "stop",
        "data_tier": "tier2",
        "confidence_level": "high",
        "context_budget": {
            "max_input_tokens": 4000,
            "include_recent_sessions": 0,
            "include_coach_messages": 0,
            "include_wellness_trend": False,
            "summarize_older_blocks": False,
            "omit_low_confidence_signals": False,
        },
    }

    return CoachMessage(
        id=message_id or uuid.uuid4(),
        athlete_id=athlete_id,
        twin_state_id=twin_state_id,
        training_block_id=training_block_id,
        message_type=message_type,
        content=content,
        generation_metadata=generation_metadata or full_metadata,
        created_at=created_at or datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_coach_message_batch(
    n: int,
    athlete_id: uuid.UUID | None = None,
    twin_state_id: uuid.UUID | None = None,
    training_block_id: uuid.UUID | None = None,
    **overrides,
) -> list[CoachMessage]:
    """Create a list of n CoachMessage instances."""
    return [
        make_coach_message(athlete_id, twin_state_id, training_block_id, **overrides)
        for _ in range(n)
    ]