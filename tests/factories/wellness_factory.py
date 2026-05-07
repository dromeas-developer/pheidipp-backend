"""Factory functions for AthleteWellness model."""

import uuid
from datetime import date, datetime

from app.models.wellness import AthleteWellness
from app.models.enums import WellnessSource


def make_athlete_wellness(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteWellness:
    """Create a minimal valid AthleteWellness instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    
    return AthleteWellness(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        metric_date=date(2024, 1, 1),
        sleep_total=None,
        sleep_light=None,
        sleep_deep=None,
        sleep_rem=None,
        sleep_awake=None,
        resting_hr=None,
        hrv=None,
        weight=None,
        source=WellnessSource.MANUAL,
        timezone="UTC",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_wellness_full(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteWellness:
    """Create an AthleteWellness instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    
    return AthleteWellness(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        metric_date=date(2024, 1, 1),
        sleep_total=480,
        sleep_light=240,
        sleep_deep=120,
        sleep_rem=90,
        sleep_awake=30,
        resting_hr=55,
        hrv=65,
        weight=75.5,
        source=WellnessSource.OURA,
        timezone="America/New_York",
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_wellness_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[AthleteWellness]:
    """Create a list of n AthleteWellness instances."""
    return [make_athlete_wellness(athlete_id, **overrides) for _ in range(n)]
