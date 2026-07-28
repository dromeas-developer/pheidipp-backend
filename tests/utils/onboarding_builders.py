from datetime import date, timedelta
from typing import Any

from app.models.enums import (
    GoalEventType,
    GoalType,
    HrSource,
    PowerSource,
    SportBackground,
)
from app.services.onboarding_service import (
    GoalInput,
    PreferencesInput,
    ProfileInput,
)


def _full_weekday(available: bool = True, max_hours: float = 2.0) -> dict[str, bool | float]:
    return {
        "available": available,
        "max_hours": max_hours,
        "long_workout": False,
        "doubles_eligible": False,
    }


def _full_week_schedule() -> dict[str, dict[str, bool | float]]:
    return {
        day: _full_weekday()
        for day in [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
    }


def make_profile_input(**overrides: Any) -> ProfileInput:
    base = {
        "timezone": "Europe/London",
        "training_window": None,
        "height_cm": 175.0,
    }
    base.update(overrides)
    return ProfileInput(**base)


def make_preferences_input(**overrides: Any) -> PreferencesInput:
    base = {
        "sport_background": SportBackground.RUNNING_PRIMARY,
        "years_structured_training": 3,
        "training_time_of_day": "morning",
        "weekly_schedule": _full_week_schedule(),
        "gps_source": "garmin_watch",
        "hr_source": HrSource.CHEST_STRAP_RR,
        "power_source": PowerSource.RUNNING_POWER_METER,
        "primary_training_platform": "garmin_connect",
    }
    base.update(overrides)
    return PreferencesInput(**base)


def make_goal_input(**overrides: Any) -> GoalInput:
    base = {
        "goal_type": GoalType.RACE_EVENT,
        "goal_event_type": GoalEventType.MARATHON,
        "goal_event_name": "Berlin Marathon",
        "goal_event_date": date.today() + timedelta(days=120),
        "custom_distance_km": None,
        "goal_description": None,
        "weekly_volume_hours": 8.0,
        "weekly_volume_km": 60.0,
        "fitness_level": 3,
        "recent_injury": None,
        "injury_severity": None,
        "target_distance_km": None,
        "target_time_minutes": None,
    }
    base.update(overrides)
    return GoalInput(**base)
