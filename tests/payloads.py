"""Shared payload fixtures for the auth test suite.

This module is intentionally side-effect-free so test files can
``from tests.payloads import _register_payload, _login_payload`` —
the pytest conftest auto-discovers it via fixtures, the test files
import the payload helpers directly, and no module-level engine or
session is constructed at import time.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Optional

from app.models.enums import (
    GpsSource,
    GoalEventType,
    GoalType,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
    Sex,
)


def make_register_payload(
    email: str = "athlete@example.com",
    password: str = "ValidPass123!",
    *,
    sex: Sex = Sex.NOT_SPECIFIED,
    height_cm: Optional[float] = 175.0,
    dob: Optional[date] = None,
) -> dict:
    """Return a registration request payload that matches the
    ``RegisterRequest`` schema exactly.
    """
    return {
        "email": email,
        "password": password,
        "profile": {
            "date_of_birth": (dob or date(1990, 1, 1)).isoformat(),
            "sex": sex.value,
            "height_cm": height_cm,
        },
    }


def make_login_payload(
    email: str = "athlete@example.com",
    password: str = "ValidPass123!",
) -> dict:
    """Return a ``LoginRequest`` payload with the given creds."""
    return {"email": email, "password": password}


# Aliases the existing test files already reference.
_register_payload = make_register_payload
_login_payload = make_login_payload


# ---------------------------------------------------------------------------
# Onboarding payload helpers — Phase 1.3.
#
# These mirror the wire-format contract on
# ``app/schemas/onboarding.py``. Tests pass the dict through the FastAPI
# client verbatim so the per-field validation runs against the same
# Pydantic schemas that production uses.
# ---------------------------------------------------------------------------


def _weekly_schedule_payload() -> dict[str, dict[str, Any]]:
    """Return a representative 7-day weekly schedule payload.

    Mirrors the canonical shape expected by ``OnboardingPreferencesIn``
    and the architecture's plan generation pipeline.
    """
    return {
        "monday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "tuesday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "wednesday": {
            "available": True,
            "max_hours": 2.0,
            "long_workout": False,
            "doubles_eligible": True,
        },
        "thursday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "friday": {
            "available": True,
            "max_hours": 1.5,
            "long_workout": False,
            "doubles_eligible": False,
        },
        "saturday": {
            "available": True,
            "max_hours": 3.0,
            "long_workout": True,
            "doubles_eligible": False,
        },
        "sunday": {
            "available": True,
            "max_hours": 1.0,
            "long_workout": False,
            "doubles_eligible": False,
        },
    }


def make_onboarding_profile_in(
    *,
    timezone: str = "Europe/Lisbon",
    height_cm: Optional[float] = 180.0,
    training_window: Optional[dict] = None,
) -> dict:
    """Return an ``OnboardingProfileIn`` payload."""
    return {
        "timezone": timezone,
        "height_cm": height_cm,
        "training_window": training_window,
    }


def make_onboarding_preferences_in(
    *,
    sport_background: SportBackground = SportBackground.RUNNING_PRIMARY,
    years_structured_training: int = 3,
    training_time_of_day: str = "morning",
    weekly_schedule: Optional[dict] = None,
    gps_source: GpsSource = GpsSource.GARMIN_WATCH,
    hr_source: HrSource = HrSource.CHEST_STRAP_RR,
    power_source: PowerSource = PowerSource.NONE,
    primary_training_platform: PrimaryTrainingPlatform = (
        PrimaryTrainingPlatform.MANUAL
    ),
) -> dict:
    """Return an ``OnboardingPreferencesIn`` payload.

    Default sources map to ``DataTier.TIER_3`` (chest-strap-RR +
    no power). Tests that exercise other tiers override
    ``hr_source`` / ``power_source``.
    """
    return {
        "sport_background": sport_background.value
        if hasattr(sport_background, "value")
        else sport_background,
        "years_structured_training": years_structured_training,
        "training_time_of_day": training_time_of_day,
        "weekly_schedule": weekly_schedule or _weekly_schedule_payload(),
        "gps_source": gps_source.value
        if hasattr(gps_source, "value")
        else gps_source,
        "hr_source": hr_source.value
        if hasattr(hr_source, "value")
        else hr_source,
        "power_source": power_source.value
        if hasattr(power_source, "value")
        else power_source,
        "primary_training_platform": primary_training_platform.value
        if hasattr(primary_training_platform, "value")
        else primary_training_platform,
    }


def make_onboarding_goal_in_race_event(
    *,
    event_name: str = "Lisbon Half Marathon",
    event_type: GoalEventType = GoalEventType.HALF_MARATHON,
    event_date: Optional[date] = None,
    weekly_volume_hours: float = 6.0,
    weekly_volume_km: float = 40.0,
    fitness_level: int = 3,
    recent_injury: Optional[str] = None,
) -> dict:
    """Return an ``OnboardingTrainingGoalIn`` payload for a ``race_event``.

    ``event_date`` defaults to 90 days out so the wire-format string
    is a future date; callers can override for past-date scenarios.
    """
    return {
        "goal_type": GoalType.RACE_EVENT.value,
        "goal_event_type": event_type.value,
        "goal_event_name": event_name,
        "goal_event_date": (event_date or date.today()).isoformat(),
        "custom_distance_km": None,
        "goal_description": None,
        "weekly_volume_hours": weekly_volume_hours,
        "weekly_volume_km": weekly_volume_km,
        "fitness_level": fitness_level,
        "recent_injury": recent_injury,
        "injury_severity": None,
        "target_distance_km": None,
        "target_time_minutes": None,
    }


def make_onboarding_goal_in_target_performance(
    *,
    target_distance_km: float = 10.0,
    target_time_minutes: int = 45,
    weekly_volume_hours: float = 5.0,
    weekly_volume_km: float = 30.0,
    fitness_level: int = 3,
) -> dict:
    """Return an ``OnboardingTrainingGoalIn`` payload for ``target_performance``."""
    return {
        "goal_type": GoalType.TARGET_PERFORMANCE.value,
        "goal_event_type": None,
        "goal_event_name": None,
        "goal_event_date": None,
        "custom_distance_km": None,
        "goal_description": None,
        "weekly_volume_hours": weekly_volume_hours,
        "weekly_volume_km": weekly_volume_km,
        "fitness_level": fitness_level,
        "recent_injury": None,
        "injury_severity": None,
        "target_distance_km": target_distance_km,
        "target_time_minutes": target_time_minutes,
    }


def make_onboarding_payload(
    *,
    email: Optional[str] = None,
    timezone: str = "Europe/Lisbon",
    sport_background: SportBackground = SportBackground.RUNNING_PRIMARY,
    hr_source: HrSource = HrSource.CHEST_STRAP_RR,
    power_source: PowerSource = PowerSource.NONE,
    goal_kind: str = "race_event",
    height_cm: Optional[float] = 180.0,
) -> dict:
    """Return a full ``OnboardingRequest`` payload.

    Combines profile + preferences + goal so a single call satisfies
    the wire contract for ``POST /athletes/{id}/onboarding``. The
    ``email`` argument exists for symmetry with the registered user
    (the wire request itself does not carry it).
    """
    if goal_kind == "race_event":
        goal = make_onboarding_goal_in_race_event()
    elif goal_kind == "target_performance":
        goal = make_onboarding_goal_in_target_performance()
    else:
        raise ValueError(f"unknown goal_kind: {goal_kind!r}")
    return {
        "profile": make_onboarding_profile_in(
            timezone=timezone, height_cm=height_cm
        ),
        "preferences": make_onboarding_preferences_in(
            sport_background=sport_background,
            hr_source=hr_source,
            power_source=power_source,
        ),
        "goal": goal,
    }


def make_profile_patch_payload(
    *,
    height_cm: Optional[float] = None,
    location_lat: Optional[float] = None,
    location_lng: Optional[float] = None,
    training_window: Optional[dict] = None,
) -> dict:
    """Return an ``AthleteProfilePatchIn`` payload — mutable fields only."""
    return {
        "height_cm": height_cm,
        "location_lat": location_lat,
        "location_lng": location_lng,
        "training_window": training_window,
    }


def make_preferences_patch_payload(
    *,
    weekly_schedule: Optional[dict] = None,
    sport_background: Optional[SportBackground] = None,
    years_structured_training: Optional[int] = None,
    training_time_of_day: Optional[str] = None,
    hr_source: Optional[HrSource] = None,
    power_source: Optional[PowerSource] = None,
) -> dict:
    """Return an ``AthletePreferencesPatchIn`` payload — every field optional.

    ``model_dump(exclude_unset=True)`` at the API layer means any
    field left at its default is treated as "not set"; tests rely
    on this when asserting the partial-merge semantics.
    """
    raw = {
        "weekly_schedule": weekly_schedule,
        "sport_background": sport_background.value
        if sport_background is not None
        and hasattr(sport_background, "value")
        else sport_background,
        "years_structured_training": years_structured_training,
        "training_time_of_day": training_time_of_day,
        "hr_source": hr_source.value
        if hr_source is not None and hasattr(hr_source, "value")
        else hr_source,
        "power_source": power_source.value
        if power_source is not None and hasattr(power_source, "value")
        else power_source,
    }
    # Strip None values so the JSON body does NOT send null for
    # unset fields — Pydantic's exclude_unset=True relies on the
    # field being absent in the JSON, not set-to-null, to treat it
    # as "not provided".
    return {k: v for k, v in raw.items() if v is not None}


# Convenience aliases mirroring the auth-payload convention.
_onboarding_payload = make_onboarding_payload
_profile_patch_payload = make_profile_patch_payload
_preferences_patch_payload = make_preferences_patch_payload
