from datetime import date, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.onboarding import (
    AthleteProfilePatchIn,
    OnboardingPreferencesIn,
    OnboardingProfileIn,
    OnboardingTrainingGoalIn,
)
from app.models.enums import (
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
)


def _full_weekday(available: bool = True, max_hours: float = 2.0) -> dict[str, Any]:
    return {
        "available": available,
        "max_hours": max_hours,
        "long_workout": False,
        "doubles_eligible": False,
    }


def _full_preferences(**overrides: Any) -> dict[str, Any]:
    base = {
        "sport_background": SportBackground.RUNNING_PRIMARY,
        "years_structured_training": 3,
        "training_time_of_day": "morning",
        "weekly_schedule": {
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
        },
        "gps_source": GpsSource.GARMIN_WATCH,
        "hr_source": HrSource.CHEST_STRAP_RR,
        "power_source": PowerSource.RUNNING_POWER_METER,
        "primary_training_platform": PrimaryTrainingPlatform.GARMIN_CONNECT,
    }
    base.update(overrides)
    return base


def _full_goal(**overrides: Any) -> dict[str, Any]:
    base = {
        "goal_type": GoalType.RACE_EVENT,
        "goal_event_type": GoalEventType.MARATHON,
        "goal_event_name": "Berlin Marathon",
        "goal_event_date": date.today() + timedelta(days=120),
        "weekly_volume_hours": 8.0,
        "weekly_volume_km": 60.0,
        "fitness_level": 3,
    }
    base.update(overrides)
    return base


class TestOnboardingProfileTimezone:
    def test_valid_iana_timezone_accepted(self):
        profile = OnboardingProfileIn(timezone="America/New_York")
        assert profile.timezone == "America/New_York"

    def test_valid_europe_london_accepted(self):
        profile = OnboardingProfileIn(timezone="Europe/London")
        assert profile.timezone == "Europe/London"

    def test_invalid_timezone_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingProfileIn(timezone="Not/A_Timezone")
        assert any(
            "unknown IANA timezone: Not/A_Timezone" in e["msg"]
            for e in exc_info.value.errors()
        )


class TestWeeklyScheduleCompleteness:
    def test_seven_days_accepted(self):
        prefs = OnboardingPreferencesIn(**_full_preferences())
        assert set(prefs.weekly_schedule.keys()) == {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }

    def test_missing_day_rejected(self):
        schedule = {
            day: _full_weekday()
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            OnboardingPreferencesIn(**_full_preferences(weekly_schedule=schedule))
        assert any("missing: ['sunday']" in e["msg"] for e in exc_info.value.errors())

    def test_extra_day_rejected(self):
        schedule = {
            day: _full_weekday()
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "funday",
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            OnboardingPreferencesIn(**_full_preferences(weekly_schedule=schedule))
        assert any(
            "unexpected: ['funday']" in e["msg"] for e in exc_info.value.errors()
        )

    def test_missing_and_extra_both_reported(self):
        schedule = {
            day: _full_weekday()
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "funday",
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            OnboardingPreferencesIn(**_full_preferences(weekly_schedule=schedule))
        msg = " | ".join(e["msg"] for e in exc_info.value.errors())
        assert "missing: ['sunday']" in msg
        assert "unexpected: ['funday']" in msg


class TestGoalRequiredFieldsPerType:
    def test_race_event_with_all_fields_accepted(self):
        goal = OnboardingTrainingGoalIn(**_full_goal())
        assert goal.goal_type == GoalType.RACE_EVENT

    def test_race_event_missing_goal_event_type_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(**_full_goal(goal_event_type=None))
        assert any(
            "race_event goal requires: goal_event_type" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_race_event_missing_goal_event_date_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(**_full_goal(goal_event_date=None))
        assert any(
            "race_event goal requires: goal_event_date" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_race_event_missing_goal_event_name_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(**_full_goal(goal_event_name=None))
        assert any(
            "race_event goal requires: goal_event_name" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_target_performance_with_all_fields_accepted(self):
        goal = OnboardingTrainingGoalIn(
            **_full_goal(
                goal_type=GoalType.TARGET_PERFORMANCE,
                goal_event_type=None,
                goal_event_name=None,
                goal_event_date=None,
                target_distance_km=10.0,
                target_time_minutes=50,
            )
        )
        assert goal.goal_type == GoalType.TARGET_PERFORMANCE

    def test_target_performance_missing_target_distance_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(
                **_full_goal(
                    goal_type=GoalType.TARGET_PERFORMANCE,
                    goal_event_type=None,
                    goal_event_name=None,
                    goal_event_date=None,
                    target_distance_km=None,
                    target_time_minutes=50,
                )
            )
        assert any(
            "target_performance goal requires: target_distance_km" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_target_performance_missing_target_time_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(
                **_full_goal(
                    goal_type=GoalType.TARGET_PERFORMANCE,
                    goal_event_type=None,
                    goal_event_name=None,
                    goal_event_date=None,
                    target_distance_km=10.0,
                    target_time_minutes=None,
                )
            )
        assert any(
            "target_performance goal requires: target_time_minutes" in e["msg"]
            for e in exc_info.value.errors()
        )


class TestGoalEventDateInFuture:
    def test_future_date_accepted(self):
        goal = OnboardingTrainingGoalIn(
            **_full_goal(goal_event_date=date.today() + timedelta(days=30))
        )
        assert goal.goal_event_date == date.today() + timedelta(days=30)

    def test_today_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(**_full_goal(goal_event_date=date.today()))
        assert any(
            "goal_event_date must be in the future" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_past_date_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            OnboardingTrainingGoalIn(
                **_full_goal(goal_event_date=date.today() - timedelta(days=1))
            )
        assert any(
            "goal_event_date must be in the future" in e["msg"]
            for e in exc_info.value.errors()
        )


class TestOnboardingFieldBounds:
    def test_years_structured_training_above_80_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingPreferencesIn(**_full_preferences(years_structured_training=85))

    def test_years_structured_training_zero_accepted(self):
        prefs = OnboardingPreferencesIn(
            **_full_preferences(years_structured_training=0)
        )
        assert prefs.years_structured_training == 0

    def test_fitness_level_zero_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingTrainingGoalIn(**_full_goal(fitness_level=0))

    def test_fitness_level_six_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingTrainingGoalIn(**_full_goal(fitness_level=6))

    def test_weekly_volume_hours_above_80_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingTrainingGoalIn(**_full_goal(weekly_volume_hours=80.5))

    def test_weekly_volume_km_above_500_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingTrainingGoalIn(**_full_goal(weekly_volume_km=500.1))

    def test_height_cm_below_50_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingProfileIn(timezone="Europe/London", height_cm=49)

    def test_height_cm_above_300_rejected(self):
        with pytest.raises(ValidationError):
            OnboardingProfileIn(timezone="Europe/London", height_cm=301)


class TestProfileImmutability:
    def test_patch_date_of_birth_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AthleteProfilePatchIn.model_validate({"date_of_birth": "1995-01-01"})
        assert any(
            "profile fields are immutable after registration: date_of_birth" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_patch_sex_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AthleteProfilePatchIn.model_validate({"sex": "female"})
        assert any(
            "profile fields are immutable after registration: sex" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_patch_timezone_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AthleteProfilePatchIn.model_validate({"timezone": "UTC"})
        assert any(
            "profile fields are immutable after registration: timezone" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_patch_multiple_immutable_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AthleteProfilePatchIn.model_validate(
                {
                    "date_of_birth": "1995-01-01",
                    "sex": "female",
                }
            )
        msg = " | ".join(e["msg"] for e in exc_info.value.errors())
        assert "date_of_birth" in msg
        assert "sex" in msg

    def test_patch_height_cm_accepted(self):
        patch = AthleteProfilePatchIn.model_validate({"height_cm": 175})
        assert patch.height_cm == 175

    def test_patch_unknown_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AthleteProfilePatchIn.model_validate({"unknown_field": "value"})
        assert any(
            "Extra inputs are not permitted" in e["msg"]
            for e in exc_info.value.errors()
        )

    def test_empty_patch_accepted(self):
        patch = AthleteProfilePatchIn.model_validate({})
        assert patch.model_dump(exclude_none=True) == {}
