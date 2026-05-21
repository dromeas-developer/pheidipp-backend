"""Unit tests for TrainingPlan ORM model."""

import uuid
from datetime import datetime

import pytest

from app.models.training_plan import TrainingPlan
from app.models.enums import TrainingPlanStatus


class TestTrainingPlanInstantiation:
    def test_can_instantiate_with_minimal_required_fields(self):
        athlete_id = uuid.uuid4()
        plan = TrainingPlan(athlete_id=athlete_id)
        assert plan.athlete_id == athlete_id

    def test_status_defaults_to_active(self):
        athlete_id = uuid.uuid4()
        plan = TrainingPlan(athlete_id=athlete_id, status=TrainingPlanStatus.ACTIVE)
        assert plan.status == TrainingPlanStatus.ACTIVE

    def test_generation_metadata_defaults_to_empty_dict(self):
        athlete_id = uuid.uuid4()
        plan = TrainingPlan(athlete_id=athlete_id, generation_metadata={})
        assert plan.generation_metadata == {}

    def test_archived_at_defaults_to_none(self):
        athlete_id = uuid.uuid4()
        plan = TrainingPlan(athlete_id=athlete_id)
        assert plan.archived_at is None

    def test_planned_sessions_defaults_to_empty_list(self):
        athlete_id = uuid.uuid4()
        plan = TrainingPlan(athlete_id=athlete_id)
        assert plan.planned_sessions == []


class TestTrainingPlanTable:
    def test_table_name_is_training_plans(self):
        assert TrainingPlan.__tablename__ == "training_plans"


class TestTrainingPlanTableArgs:
    def test_contains_partial_unique_index(self):
        table_args = TrainingPlan.__table_args__
        # Find the index that has postgresql_where
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "ix_training_plans_active_per_athlete" in index_names

    def test_contains_composite_index(self):
        table_args = TrainingPlan.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "ix_training_plans_athlete_created_at" in index_names