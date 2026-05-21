"""Unit tests for training plan enums."""

import enum

import pytest

from app.models.enums import (
    TrainingPlanStatus,
    TrainingPhase,
    SessionType,
    PhysiologicalIntent,
    MethodologyTrait,
)


class TestTrainingPlanStatus:
    def test_has_active_value(self):
        assert TrainingPlanStatus.ACTIVE.value == "active"

    def test_has_archived_value(self):
        assert TrainingPlanStatus.ARCHIVED.value == "archived"

    def test_inherits_from_str_and_enum(self):
        assert issubclass(TrainingPlanStatus, str)
        assert issubclass(TrainingPlanStatus, enum.Enum)


class TestTrainingPhase:
    def test_has_all_expected_values(self):
        expected = {"base", "build", "peak", "taper", "race", "recovery"}
        actual = {phase.value for phase in TrainingPhase}
        assert actual == expected

    def test_inherits_from_str_and_enum(self):
        assert issubclass(TrainingPhase, str)
        assert issubclass(TrainingPhase, enum.Enum)


class TestSessionType:
    def test_has_all_17_expected_values(self):
        expected = {
            "rest",
            "recovery_run",
            "easy_run",
            "long_run",
            "medium_long_run",
            "steady_state",
            "tempo",
            "threshold",
            "vo2max",
            "hill_repeats",
            "fartlek",
            "race_specific",
            "strides",
            "drills_mobility",
            "cross_training",
            "test_session",
            "optional_run",
        }
        actual = {st.value for st in SessionType}
        assert actual == expected

    def test_inherits_from_str_and_enum(self):
        assert issubclass(SessionType, str)
        assert issubclass(SessionType, enum.Enum)


class TestPhysiologicalIntent:
    def test_has_all_8_expected_values(self):
        expected = {
            "low_aerobic",
            "high_aerobic",
            "threshold",
            "vo2max",
            "race_specific",
            "neuromuscular",
            "recovery_support",
            "calibration",
        }
        actual = {intent.value for intent in PhysiologicalIntent}
        assert actual == expected

    def test_inherits_from_str_and_enum(self):
        assert issubclass(PhysiologicalIntent, str)
        assert issubclass(PhysiologicalIntent, enum.Enum)


class TestMethodologyTrait:
    def test_has_all_10_expected_values(self):
        expected = {
            "HIGH_AEROBIC_VOLUME",
            "LOW_INTENSITY_DOMINANT",
            "THRESHOLD_DENSITY",
            "HIGH_INTENSITY_SPARSE",
            "HIGH_FREQUENCY",
            "STRUCTURAL_DURABILITY",
            "RACE_SPECIFICITY",
            "VARIETY_EMPHASIS",
            "NEUROMUSCULAR_SUPPORT",
            "CONSERVATIVE_PROGRESSION",
        }
        actual = {trait.value for trait in MethodologyTrait}
        assert actual == expected

    def test_inherits_from_str_and_enum(self):
        assert issubclass(MethodologyTrait, str)
        assert issubclass(MethodologyTrait, enum.Enum)