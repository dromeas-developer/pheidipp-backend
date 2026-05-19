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
    # Extract known fields from overrides to avoid conflicts
    known_fields = {
        "id", "email", "hashed_password", "status", "onboarding_complete",
        "created_at", "updated_at"
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return Athlete(
        id=overrides.get("id", uuid.uuid4()),
        email=overrides.get("email", f"athlete_{uuid.uuid4().hex[:8]}@example.com"),
        hashed_password=overrides.get("hashed_password", None),
        status=overrides.get("status", AthleteStatus.ACTIVE),
        onboarding_complete=overrides.get("onboarding_complete", False),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        updated_at=overrides.get("updated_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_athlete_full(**overrides) -> Athlete:
    """Create an Athlete instance with all fields populated."""
    # Extract known fields from overrides to avoid conflicts
    known_fields = {
        "id", "email", "hashed_password", "status", "onboarding_complete",
        "created_at", "updated_at"
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return Athlete(
        id=overrides.get("id", uuid.uuid4()),
        email=overrides.get("email", f"athlete_{uuid.uuid4().hex[:8]}@example.com"),
        hashed_password=overrides.get("hashed_password", "hashed_password_placeholder"),
        status=overrides.get("status", AthleteStatus.ACTIVE),
        onboarding_complete=overrides.get("onboarding_complete", False),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        updated_at=overrides.get("updated_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_athlete_batch(n: int, **overrides) -> list[Athlete]:
    """Create a list of n Athlete instances."""
    return [make_athlete(**overrides) for _ in range(n)]


def make_athlete_profile(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteProfile:
    """Create a minimal valid AthleteProfile instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    # Extract known fields from overrides to avoid conflicts
    known_fields = {
        "athlete_id", "first_name", "last_name", "display_name",
        "date_of_birth", "gender", "country_code", "timezone",
        "language_code", "unit_preference", "created_at", "updated_at"
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return AthleteProfile(
        athlete_id=athlete_id,
        first_name=overrides.get("first_name", "John"),
        last_name=overrides.get("last_name", "Doe"),
        display_name=overrides.get("display_name", "johndoe"),
        date_of_birth=overrides.get("date_of_birth", date(1990, 1, 1)),
        gender=overrides.get("gender", Gender.MALE),
        country_code=overrides.get("country_code", "US"),
        timezone=overrides.get("timezone", "America/New_York"),
        language_code=overrides.get("language_code", "en"),
        unit_preference=overrides.get("unit_preference", UnitPreference.METRIC),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        updated_at=overrides.get("updated_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_athlete_profile_full(athlete_id: uuid.UUID | None = None, **overrides) -> AthleteProfile:
    """Create an AthleteProfile instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    # Extract known fields from overrides to avoid conflicts
    known_fields = {
        "athlete_id", "first_name", "last_name", "display_name",
        "date_of_birth", "gender", "country_code", "timezone",
        "language_code", "unit_preference", "created_at", "updated_at"
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return AthleteProfile(
        athlete_id=athlete_id,
        first_name=overrides.get("first_name", "John"),
        last_name=overrides.get("last_name", "Doe"),
        display_name=overrides.get("display_name", "johndoe"),
        date_of_birth=overrides.get("date_of_birth", date(1990, 1, 1)),
        gender=overrides.get("gender", Gender.MALE),
        country_code=overrides.get("country_code", "US"),
        timezone=overrides.get("timezone", "America/New_York"),
        language_code=overrides.get("language_code", "en"),
        unit_preference=overrides.get("unit_preference", UnitPreference.METRIC),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        updated_at=overrides.get("updated_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_athlete_profile_batch(n: int, athlete_id: uuid.UUID | None = None, **overrides) -> list[AthleteProfile]:
    """Create a list of n AthleteProfile instances."""
    return [make_athlete_profile(athlete_id, **overrides) for _ in range(n)]
