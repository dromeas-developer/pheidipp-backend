"""Unit tests for Athlete and AthleteProfile models."""

import uuid
from datetime import date, datetime

import pytest

from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.models.athlete_preferences import AthletePreferences
from app.models.training_block import TrainingBlock
from app.models.enums import (
    AthleteStatus,
    Gender,
    UnitPreference,
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    GoalType,
    GoalEventType,
    GoalStatus,
)


class TestAthleteModel:
    """Tests for Athlete model."""

    def test_athlete_model_minimal(self):
        """Test minimal Athlete model creation."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email="test@example.com",
            status=AthleteStatus.ACTIVE,
        )
        assert athlete.email == "test@example.com"
        assert athlete.status == AthleteStatus.ACTIVE

    def test_athlete_model_all_fields(self):
        """Test Athlete model with all fields."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email="test@example.com",
            hashed_password="hashed",
            status=AthleteStatus.ACTIVE,
            onboarding_complete=False,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert athlete.hashed_password == "hashed"
        assert athlete.onboarding_complete is False


class TestAthleteProfileModel:
    """Tests for AthleteProfile model."""

    def test_athlete_profile_model_minimal(self):
        """Test minimal AthleteProfile model creation."""
        profile = AthleteProfile(
            athlete_id=uuid.uuid4(),
            first_name="John",
            last_name="Doe",
            display_name="johndoe",
        )
        assert profile.first_name == "John"
        assert profile.last_name == "Doe"

    def test_athlete_profile_model_all_fields(self):
        """Test AthleteProfile model with all fields."""
        profile = AthleteProfile(
            athlete_id=uuid.uuid4(),
            first_name="John",
            last_name="Doe",
            display_name="johndoe",
            date_of_birth=date(1990, 1, 1),
            gender=Gender.MALE,
            country_code="US",
            timezone="America/New_York",
            language_code="en",
            unit_preference=UnitPreference.METRIC,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert profile.gender == Gender.MALE
        assert profile.unit_preference == UnitPreference.METRIC


class TestAthletePreferencesModel:
    """Tests for AthletePreferences model."""

    def test_athlete_preferences_model_minimal(self):
        """Test minimal AthletePreferences model creation."""
        prefs = AthletePreferences(
            athlete_id=uuid.uuid4(),
        )
        assert prefs.athlete_id is not None
        assert prefs.sport_background is None
        assert prefs.years_structured_training is None

    def test_athlete_preferences_model_all_fields(self):
        """Test AthletePreferences model with all fields populated."""
        weekly_schedule = {
            "days": {
                "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                "tue": {"available": False, "max_hours": 0, "long_workout": False},
                "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                "thu": {"available": False, "max_hours": 0, "long_workout": False},
                "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
            },
            "available_days_count": 5,
        }
        prefs = AthletePreferences(
            athlete_id=uuid.uuid4(),
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=5.0,
            training_time_of_day=TrainingTimeOfDay.MORNING,
            weekly_schedule=weekly_schedule,
            gps_source=GpsSource.WATCH,
            hr_source=HrSource.CHEST_STRAP,
            power_source=PowerSource.RUNNING_POWER,
            primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert prefs.sport_background == SportBackground.RUNNING_PRIMARY
        assert prefs.training_time_of_day == TrainingTimeOfDay.MORNING
        assert prefs.gps_source == GpsSource.WATCH
        assert prefs.hr_source == HrSource.CHEST_STRAP
        assert prefs.power_source == PowerSource.RUNNING_POWER
        assert prefs.primary_training_platform == PrimaryTrainingPlatform.GARMIN_CONNECT

    def test_athlete_preferences_weekly_schedule_accepts_dict(self):
        """Test that weekly_schedule accepts a plain dict."""
        weekly_schedule = {
            "days": {
                "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                "tue": {"available": False, "max_hours": 0, "long_workout": False},
                "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                "thu": {"available": False, "max_hours": 0, "long_workout": False},
                "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
            },
            "available_days_count": 5,
        }
        prefs = AthletePreferences(
            athlete_id=uuid.uuid4(),
            weekly_schedule=weekly_schedule,
        )
        assert prefs.weekly_schedule == weekly_schedule


class TestTrainingBlockModel:
    """Tests for TrainingBlock model."""

    def test_training_block_model_minimal(self):
        """Test minimal TrainingBlock model creation with required fields."""
        block = TrainingBlock(
            athlete_id=uuid.uuid4(),
            status=GoalStatus.ACTIVE,
        )
        assert block.athlete_id is not None
        assert block.status == GoalStatus.ACTIVE

    def test_training_block_model_all_fields(self):
        """Test TrainingBlock model with all fields populated."""
        block = TrainingBlock(
            athlete_id=uuid.uuid4(),
            goal_type=GoalType.RACE,
            goal_event_type=GoalEventType.MARATHON,
            goal_event_name="Boston Marathon 2024",
            goal_event_date=date(2024, 4, 15),
            goal_description="Prepare for Boston Marathon",
            custom_distance_km=42.195,
            weekly_volume_hours=10.0,
            weekly_volume_km=80.0,
            fitness_level=3,
            recent_injury=False,
            status=GoalStatus.ACTIVE,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
        )
        assert block.goal_type == GoalType.RACE
        assert block.goal_event_type == GoalEventType.MARATHON
        assert block.custom_distance_km == 42.195
        assert block.fitness_level == 3
        assert block.status == GoalStatus.ACTIVE

    def test_training_block_status_can_be_set(self):
        """Test that status can be set to different values."""
        block = TrainingBlock(
            athlete_id=uuid.uuid4(),
            status=GoalStatus.COMPLETED,
        )
        assert block.status == GoalStatus.COMPLETED

    def test_training_block_goal_event_date_accepts_date(self):
        """Test that goal_event_date accepts a date object."""
        block = TrainingBlock(
            athlete_id=uuid.uuid4(),
            status=GoalStatus.ACTIVE,
            goal_event_date=date(2024, 4, 15),
        )
        assert block.goal_event_date == date(2024, 4, 15)

    def test_athlete_profile_model_minimal(self):
        """Test creating minimal AthleteProfile model."""
        profile = AthleteProfile(
            athlete_id=uuid.uuid4(),
        )
        assert profile.athlete_id is not None
        assert profile.first_name is None
        assert profile.last_name is None
        assert profile.display_name is None

    def test_athlete_profile_model_all_genders(self):
        """Test AthleteProfile model with all gender values."""
        for gender in Gender:
            profile = AthleteProfile(
                athlete_id=uuid.uuid4(),
                gender=gender,
            )
            assert profile.gender == gender

    def test_athlete_profile_model_all_unit_preferences(self):
        """Test AthleteProfile model with all unit preference values."""
        for unit_pref in UnitPreference:
            profile = AthleteProfile(
                athlete_id=uuid.uuid4(),
                unit_preference=unit_pref,
            )
            assert profile.unit_preference == unit_pref

    def test_athlete_profile_model_unit_preference_field_exists(self):
        """Test AthleteProfile model has unit_preference field."""
        profile = AthleteProfile(
            athlete_id=uuid.uuid4(),
            unit_preference=UnitPreference.METRIC,
        )
        assert profile.unit_preference == UnitPreference.METRIC