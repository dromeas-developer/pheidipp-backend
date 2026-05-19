"""Unit tests for new enums introduced in Phase 1a-patch."""

import enum
import pytest

from app.models.enums import (
    GoalType,
    GoalEventType,
    GoalStatus,
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
)


class TestGoalType:
    """Tests for GoalType enum."""

    def test_goal_type_is_string_enum(self):
        """Test GoalType inherits from str and enum.Enum."""
        assert issubclass(GoalType, str)
        assert issubclass(GoalType, enum.Enum)

    def test_goal_type_values(self):
        """Test GoalType has all expected values."""
        expected_values = {"race", "fitness_improvement", "maintenance", "recovery"}
        actual_values = {e.value for e in GoalType}
        assert actual_values == expected_values


class TestGoalEventType:
    """Tests for GoalEventType enum."""

    def test_goal_event_type_is_string_enum(self):
        """Test GoalEventType inherits from str and enum.Enum."""
        assert issubclass(GoalEventType, str)
        assert issubclass(GoalEventType, enum.Enum)

    def test_goal_event_type_values(self):
        """Test GoalEventType has all expected values."""
        expected_values = {"5k", "10k", "half_marathon", "marathon", "ultra", "custom"}
        actual_values = {e.value for e in GoalEventType}
        assert actual_values == expected_values


class TestGoalStatus:
    """Tests for GoalStatus enum."""

    def test_goal_status_is_string_enum(self):
        """Test GoalStatus inherits from str and enum.Enum."""
        assert issubclass(GoalStatus, str)
        assert issubclass(GoalStatus, enum.Enum)

    def test_goal_status_values(self):
        """Test GoalStatus has all expected values."""
        expected_values = {"active", "completed", "abandoned"}
        actual_values = {e.value for e in GoalStatus}
        assert actual_values == expected_values


class TestSportBackground:
    """Tests for SportBackground enum."""

    def test_sport_background_is_string_enum(self):
        """Test SportBackground inherits from str and enum.Enum."""
        assert issubclass(SportBackground, str)
        assert issubclass(SportBackground, enum.Enum)

    def test_sport_background_values(self):
        """Test SportBackground has all expected values."""
        expected_values = {
            "running_primary",
            "cycling_crossover",
            "swimming_crossover",
            "multi_sport",
            "other",
        }
        actual_values = {e.value for e in SportBackground}
        assert actual_values == expected_values


class TestTrainingTimeOfDay:
    """Tests for TrainingTimeOfDay enum."""

    def test_training_time_of_day_is_string_enum(self):
        """Test TrainingTimeOfDay inherits from str and enum.Enum."""
        assert issubclass(TrainingTimeOfDay, str)
        assert issubclass(TrainingTimeOfDay, enum.Enum)

    def test_training_time_of_day_values(self):
        """Test TrainingTimeOfDay has all expected values."""
        expected_values = {"morning", "afternoon", "mixed"}
        actual_values = {e.value for e in TrainingTimeOfDay}
        assert actual_values == expected_values


class TestGpsSource:
    """Tests for GpsSource enum."""

    def test_gps_source_is_string_enum(self):
        """Test GpsSource inherits from str and enum.Enum."""
        assert issubclass(GpsSource, str)
        assert issubclass(GpsSource, enum.Enum)

    def test_gps_source_values(self):
        """Test GpsSource has all expected values."""
        expected_values = {"none", "phone", "watch"}
        actual_values = {e.value for e in GpsSource}
        assert actual_values == expected_values


class TestHrSource:
    """Tests for HrSource enum."""

    def test_hr_source_is_string_enum(self):
        """Test HrSource inherits from str and enum.Enum."""
        assert issubclass(HrSource, str)
        assert issubclass(HrSource, enum.Enum)

    def test_hr_source_values(self):
        """Test HrSource has all expected values."""
        expected_values = {"none", "wrist_optical", "chest_strap"}
        actual_values = {e.value for e in HrSource}
        assert actual_values == expected_values


class TestPowerSource:
    """Tests for PowerSource enum."""

    def test_power_source_is_string_enum(self):
        """Test PowerSource inherits from str and enum.Enum."""
        assert issubclass(PowerSource, str)
        assert issubclass(PowerSource, enum.Enum)

    def test_power_source_values(self):
        """Test PowerSource has all expected values."""
        expected_values = {"none", "running_power"}
        actual_values = {e.value for e in PowerSource}
        assert actual_values == expected_values


class TestPrimaryTrainingPlatform:
    """Tests for PrimaryTrainingPlatform enum."""

    def test_primary_training_platform_is_string_enum(self):
        """Test PrimaryTrainingPlatform inherits from str and enum.Enum."""
        assert issubclass(PrimaryTrainingPlatform, str)
        assert issubclass(PrimaryTrainingPlatform, enum.Enum)

    def test_primary_training_platform_values(self):
        """Test PrimaryTrainingPlatform has all expected values."""
        expected_values = {
            "unknown",
            "garmin_connect",
            "coros",
            "polar_flow",
            "suunto",
            "intervals_icu",
            "strava",
            "trainingpeaks",
            "other",
        }
        actual_values = {e.value for e in PrimaryTrainingPlatform}
        assert actual_values == expected_values