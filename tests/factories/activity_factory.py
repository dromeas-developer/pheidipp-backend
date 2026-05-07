"""Factory functions for Activity model."""

import uuid
from datetime import datetime, timedelta

from app.models.activity import Activity
from app.models.enums import ActivityType, PerceivedEffort


def make_activity(athlete_id: uuid.UUID | None = None, **overrides) -> Activity:
    """Create a minimal valid Activity instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1)
    
    return Activity(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        activity_type=ActivityType.RUNNING,
        title="Morning Run",
        description=None,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=3600,
        perceived_effort=None,
        avg_heart_rate=None,
        max_heart_rate=None,
        avg_speed_m_per_s=None,
        max_speed_m_per_s=None,
        avg_power=None,
        max_power=None,
        distance_meters=None,
        elevation_gain_meters=None,
        elevation_loss_meters=None,
        calories=None,
        source=None,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_activity_full(athlete_id: uuid.UUID | None = None, **overrides) -> Activity:
    """Create an Activity instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    
    started_at = datetime(2024, 1, 1, 10, 0, 0)
    finished_at = started_at + timedelta(hours=1, minutes=30)
    
    return Activity(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        activity_type=ActivityType.CYCLING,
        title="Afternoon Ride",
        description="A scenic ride through the countryside",
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=5400,
        perceived_effort=PerceivedEffort.MODERATE,
        avg_heart_rate=145,
        max_heart_rate=175,
        avg_speed_m_per_s=8.5,
        max_speed_m_per_s=12.0,
        avg_power=200,
        max_power=400,
        distance_meters=45000.0,
        elevation_gain_meters=300.0,
        elevation_loss_meters=250.0,
        calories=1200,
        source="garmin",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_activity_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[Activity]:
    """Create a list of n Activity instances."""
    return [make_activity(athlete_id, **overrides) for _ in range(n)]
