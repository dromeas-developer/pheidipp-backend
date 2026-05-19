"""Unit tests for TwinState Pydantic schemas."""

import uuid
from datetime import datetime
from pydantic import ValidationError
import pytest

from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier
from app.schemas.twin_state import TwinStateBase, TwinStateCreate, TwinStateResponse
from tests.factories.twin_state_factory import make_twin_state


class TestTwinStateBaseValidation:
    """Tests for TwinStateBase schema validation."""

    def test_accepts_all_required_fields(self):
        """Verify TwinStateBase accepts all required fields."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test summary",
            "computation_metadata": {"test": "data"},
        }
        schema = TwinStateBase(**data)
        assert schema.athlete_id == data["athlete_id"]
        assert schema.fitness_score == 50.0

    def test_validates_fitness_score_range_0(self):
        """Verify fitness_score accepts 0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.fitness_score == 0

    def test_validates_fitness_score_range_100(self):
        """Verify fitness_score accepts 100."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 100,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.fitness_score == 100

    def test_rejects_fitness_score_below_0(self):
        """Verify fitness_score rejects values below 0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": -1,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        with pytest.raises(ValidationError):
            TwinStateBase(**data)

    def test_rejects_fitness_score_above_100(self):
        """Verify fitness_score rejects values above 100."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 101,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        with pytest.raises(ValidationError):
            TwinStateBase(**data)

    def test_rejects_fatigue_score_below_0(self):
        """Verify fatigue_score rejects values below 0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "fatigue_score": -1,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        with pytest.raises(ValidationError):
            TwinStateBase(**data)

    def test_rejects_structural_capacity_score_below_0(self):
        """Verify structural_capacity_score rejects values below 0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": -0.1,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        with pytest.raises(ValidationError):
            TwinStateBase(**data)

    def test_rejects_structural_capacity_score_above_1(self):
        """Verify structural_capacity_score rejects values above 1."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 1.1,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        with pytest.raises(ValidationError):
            TwinStateBase(**data)

    def test_defaults_confidence_level_to_low(self):
        """Verify confidence_level defaults to ConfidenceLevel.LOW."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.confidence_level == ConfidenceLevel.LOW

    def test_defaults_fatigue_score_to_0(self):
        """Verify fatigue_score defaults to 0.0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.fatigue_score == 0.0

    def test_defaults_lt1_pace_estimate_to_none(self):
        """Verify lt1_pace_estimate defaults to None."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.lt1_pace_estimate is None

    def test_defaults_lt2_pace_estimate_to_none(self):
        """Verify lt2_pace_estimate defaults to None."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.lt2_pace_estimate is None

    def test_defaults_fitness_time_constant_to_42(self):
        """Verify fitness_time_constant defaults to 42.0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.fitness_time_constant == 42.0

    def test_defaults_fatigue_time_constant_to_7(self):
        """Verify fatigue_time_constant defaults to 7.0."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "data_tier": DataTier.TIER1,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.fatigue_time_constant == 7.0

    def test_accepts_enum_values_as_enum_members(self):
        """Verify schema accepts enum values as enum members."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": TwinTrigger.QUESTIONNAIRE,
            "confidence_level": ConfidenceLevel.MEDIUM,
            "data_tier": DataTier.TIER2,
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.trigger == TwinTrigger.QUESTIONNAIRE
        assert schema.confidence_level == ConfidenceLevel.MEDIUM
        assert schema.data_tier == DataTier.TIER2

    def test_accepts_enum_values_as_string_values(self):
        """Verify schema accepts enum values as string values."""
        data = {
            "athlete_id": uuid.uuid4(),
            "athlete_preferences_id": uuid.uuid4(),
            "trigger": "questionnaire",
            "confidence_level": "medium",
            "data_tier": "tier2",
            "fitness_score": 50.0,
            "max_hr_estimate": 187.0,
            "lt1_hr_estimate": 130.9,
            "lt2_hr_estimate": 155.2,
            "structural_capacity_score": 0.7,
            "computation_summary": "Test",
            "computation_metadata": {},
        }
        schema = TwinStateBase(**data)
        assert schema.trigger == TwinTrigger.QUESTIONNAIRE
        assert schema.confidence_level == ConfidenceLevel.MEDIUM
        assert schema.data_tier == DataTier.TIER2


class TestTwinStateCreate:
    """Tests for TwinStateCreate schema."""

    def test_inherits_all_fields_from_base(self):
        """Verify TwinStateCreate inherits all fields from TwinStateBase with no additions."""
        # TwinStateCreate should have the same fields as TwinStateBase
        create_fields = set(TwinStateCreate.model_fields.keys())
        base_fields = set(TwinStateBase.model_fields.keys())
        assert create_fields == base_fields


class TestTwinStateResponse:
    """Tests for TwinStateResponse schema."""

    def test_includes_id_field(self):
        """Verify TwinStateResponse includes id (UUID) field."""
        assert "id" in TwinStateResponse.model_fields

    def test_includes_created_at_field(self):
        """Verify TwinStateResponse includes created_at (datetime) field."""
        assert "created_at" in TwinStateResponse.model_fields

    def test_model_validate_serializes_orm_instance(self):
        """Verify TwinStateResponse.model_validate() correctly serializes a TwinState ORM instance."""
        twin_state = make_twin_state()
        response = TwinStateResponse.model_validate(twin_state)
        assert response.id == twin_state.id
        assert response.athlete_id == twin_state.athlete_id
        assert response.fitness_score == twin_state.fitness_score
        assert isinstance(response.created_at, datetime)