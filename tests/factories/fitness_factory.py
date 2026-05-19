"""Factory functions for AthleteFitness model."""

import uuid
from datetime import date, datetime

from app.models.fitness import AthleteFitness
from app.models.enums import DataSource


def make_athlete_fitness(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteFitness:
    """Create a minimal valid AthleteFitness instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    return AthleteFitness(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        metric_date=date(2024, 1, 1),
        tss=None,
        atl=None,
        ctl=None,
        tsb=None,
        source=DataSource.MANUAL,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_fitness_full(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteFitness:
    """Create an AthleteFitness instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    return AthleteFitness(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        metric_date=date(2024, 1, 1),
        tss=75.5,
        atl=42.0,
        ctl=65.0,
        tsb=23.0,
        source=DataSource.GARMIN,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_fitness_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[AthleteFitness]:
    """Create a list of n AthleteFitness instances."""
    return [make_athlete_fitness(athlete_id, **overrides) for _ in range(n)]