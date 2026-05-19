"""Factory functions for TrainingBlock model."""

import uuid
from datetime import date, datetime

from app.models.training_block import TrainingBlock
from app.models.enums import (
    GoalType,
    GoalEventType,
    GoalStatus,
)


def make_training_block(athlete_id: uuid.UUID | None = None, **overrides) -> TrainingBlock:
    """Create a minimal valid TrainingBlock instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    return TrainingBlock(
        athlete_id=athlete_id,
        status=GoalStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_training_block_full(athlete_id: uuid.UUID | None = None, **overrides) -> TrainingBlock:
    """Create a TrainingBlock instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    return TrainingBlock(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.MARATHON,
        goal_event_name="Boston Marathon 2024",
        goal_event_date=date(2024, 4, 15),
        goal_description="Prepare for Boston Marathon with a structured 16-week plan",
        custom_distance_km=42.195,
        weekly_volume_hours=10.0,
        weekly_volume_km=80.0,
        fitness_level=3,
        recent_injury=False,
        status=GoalStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_training_block_batch(
    n: int, athlete_id: uuid.UUID | None = None, **overrides
) -> list[TrainingBlock]:
    """Create a list of n TrainingBlock instances."""
    return [make_training_block(athlete_id, **overrides) for _ in range(n)]