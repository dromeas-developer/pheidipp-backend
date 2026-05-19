"""Unit tests for TwinState model and enums."""

import pytest
from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier
from app.models.twin_state import TwinState


class TestTwinTriggerEnum:
    """Tests for TwinTrigger enum values."""

    def test_twin_trigger_has_questionnaire(self):
        """Verify TwinTrigger enum has QUESTIONNAIRE value."""
        assert hasattr(TwinTrigger, "QUESTIONNAIRE")
        assert TwinTrigger.QUESTIONNAIRE.value == "questionnaire"

    def test_twin_trigger_has_calibration(self):
        """Verify TwinTrigger enum has CALIBRATION value."""
        assert hasattr(TwinTrigger, "CALIBRATION")
        assert TwinTrigger.CALIBRATION.value == "calibration"

    def test_twin_trigger_has_wellness_update(self):
        """Verify TwinTrigger enum has WELLNESS_UPDATE value."""
        assert hasattr(TwinTrigger, "WELLNESS_UPDATE")
        assert TwinTrigger.WELLNESS_UPDATE.value == "wellness_update"


class TestConfidenceLevelEnum:
    """Tests for ConfidenceLevel enum values."""

    def test_confidence_level_has_low(self):
        """Verify ConfidenceLevel enum has LOW value."""
        assert hasattr(ConfidenceLevel, "LOW")
        assert ConfidenceLevel.LOW.value == "low"

    def test_confidence_level_has_medium(self):
        """Verify ConfidenceLevel enum has MEDIUM value."""
        assert hasattr(ConfidenceLevel, "MEDIUM")
        assert ConfidenceLevel.MEDIUM.value == "medium"

    def test_confidence_level_has_high(self):
        """Verify ConfidenceLevel enum has HIGH value."""
        assert hasattr(ConfidenceLevel, "HIGH")
        assert ConfidenceLevel.HIGH.value == "high"


class TestDataTierEnum:
    """Tests for DataTier enum values."""

    def test_data_tier_has_tier1(self):
        """Verify DataTier enum has TIER1 value."""
        assert hasattr(DataTier, "TIER1")
        assert DataTier.TIER1.value == "tier1"

    def test_data_tier_has_tier2(self):
        """Verify DataTier enum has TIER2 value."""
        assert hasattr(DataTier, "TIER2")
        assert DataTier.TIER2.value == "tier2"

    def test_data_tier_has_tier3(self):
        """Verify DataTier enum has TIER3 value."""
        assert hasattr(DataTier, "TIER3")
        assert DataTier.TIER3.value == "tier3"

    def test_data_tier_has_tier4(self):
        """Verify DataTier enum has TIER4 value."""
        assert hasattr(DataTier, "TIER4")
        assert DataTier.TIER4.value == "tier4"

    def test_data_tier_has_tier5(self):
        """Verify DataTier enum has TIER5 value."""
        assert hasattr(DataTier, "TIER5")
        assert DataTier.TIER5.value == "tier5"


class TestTwinStateModel:
    """Tests for TwinState model structure."""

    def test_tablename_is_twin_states(self):
        """Verify TwinState.__tablename__ is 'twin_states'."""
        assert TwinState.__tablename__ == "twin_states"

    def test_model_has_all_expected_columns(self):
        """Verify TwinState model has all expected columns."""
        column_names = [c.name for c in TwinState.__table__.columns]
        expected_columns = [
            "id",
            "athlete_id",
            "athlete_preferences_id",
            "trigger",
            "confidence_level",
            "data_tier",
            "fitness_score",
            "fatigue_score",
            "max_hr_estimate",
            "lt1_hr_estimate",
            "lt2_hr_estimate",
            "lt1_pace_estimate",
            "lt2_pace_estimate",
            "structural_capacity_score",
            "fitness_time_constant",
            "fatigue_time_constant",
            "computation_summary",
            "computation_metadata",
            "created_at",
        ]
        for col in expected_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_model_has_athlete_relationship(self):
        """Verify TwinState has 'athlete' relationship defined."""
        assert "athlete" in TwinState.__mapper__.relationships

    def test_model_has_preferences_relationship(self):
        """Verify TwinState has 'preferences' relationship defined."""
        assert "preferences" in TwinState.__mapper__.relationships


class TestTwinStateConstraints:
    """Tests for TwinState table constraints."""

    def test_has_fitness_score_range_constraint(self):
        """Verify fitness_score range constraint exists."""
        constraint_names = [c.name for c in TwinState.__table__.constraints]
        assert "ck_twin_states_fitness_score_range" in constraint_names

    def test_has_max_hr_range_constraint(self):
        """Verify max_hr_estimate range constraint exists."""
        constraint_names = [c.name for c in TwinState.__table__.constraints]
        assert "ck_twin_states_max_hr_range" in constraint_names

    def test_has_fatigue_non_negative_constraint(self):
        """Verify fatigue_score non-negative constraint exists."""
        constraint_names = [c.name for c in TwinState.__table__.constraints]
        assert "ck_twin_states_fatigue_non_negative" in constraint_names

    def test_has_structural_capacity_range_constraint(self):
        """Verify structural_capacity_score range constraint exists."""
        constraint_names = [c.name for c in TwinState.__table__.constraints]
        assert "ck_twin_states_structural_capacity_range" in constraint_names