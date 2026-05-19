"""Factory functions for Athlete and AthleteProfile models."""

import uuid
from datetime import date, datetime

from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    AthleteStatus,
    Gender,
    UnitPreference,
)


def make_athlete(**overrides) -> Athlete:
    """Create a minimal valid Athlete instance."""
    return Athlete(
        id=uuid.uuid4(),
        email=f"athlete_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
        onboarding_complete=False,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_full(**overrides) -> Athlete:
    """Create an Athlete instance with all fields populated."""
    return Athlete(
        id=uuid.uuid4(),
        email=f"athlete_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hashed_password_placeholder",
        status=AthleteStatus.ACTIVE,
        onboarding_complete=False,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_batch(n: int, **overrides) -> list[Athlete]:
    """Create a list of n Athlete instances."""
    return [make_athlete(**overrides) for _ in range(n)]


def make_athlete_profile(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteProfile:
    """Create a minimal valid AthleteProfile instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    return AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code="US",
        timezone="America/New_York",
        language_code="en",
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_profile_full(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteProfile:
    """Create an AthleteProfile instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    return AthleteProfile(
        athlete_id=athlete_id,
        first_name="John",
        last_name="Doe",
        display_name="johndoe",
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        country_code="US",
        timezone="America/New_York",
        language_code="en",
        unit_preference=UnitPreference.METRIC,
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_athlete_profile_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[AthleteProfile]:
    """Create a list of n AthleteProfile instances."""
    return [make_athlete_profile(athlete_id, **overrides) for _ in range(n)]
