"""Factory functions for AthletePhysiology model."""

import uuid
from datetime import date, datetime

from app.models.physiology import AthletePhysiology
from app.models.enums import WellnessSource


def make_athlete_physiology(athlete_id: uuid.UUID | None = None, **overrides) -> AthletePhysiology:
    """Create a minimal valid AthletePhysiology instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    
    return AthletePhysiology(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        ftp=None,
        lt1=None,
        lt2=None,
        vo2_max=None,
        max_hr=None,
        source=WellnessSource.MANUAL,
        effective_from=date(2024, 1, 1),
        effective_to=None,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_physiology_full(athlete_id: uuid.UUID | None = None, **overrides) -> AthletePhysiology:
    """Create an AthletePhysiology instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    
    return AthletePhysiology(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        ftp=280,
        lt1=220,
        lt2=250,
        vo2_max=65.5,
        max_hr=190,
        source=WellnessSource.GARMIN,
        effective_from=date(2024, 1, 1),
        effective_to=date(2024, 6, 30),
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_physiology_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[AthletePhysiology]:
    """Create a list of n AthletePhysiology instances."""
    return [make_athlete_physiology(athlete_id, **overrides) for _ in range(n)]
