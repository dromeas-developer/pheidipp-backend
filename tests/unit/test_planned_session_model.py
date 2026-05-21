"""Unit tests for PlannedSession ORM model."""

import uuid
from datetime import date, datetime

import pytest

from app.models.planned_session import PlannedSession
from app.models.enums import SessionType, PhysiologicalIntent, TrainingPhase


class TestPlannedSessionInstantiation:
    def test_can_instantiate_with_required_fields(self):
        plan_id = uuid.uuid4()
        session = PlannedSession(
            training_plan_id=plan_id,
            scheduled_date=date(2024, 1, 15),
            session_type=SessionType.EASY_RUN,
            dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            week_number=1,
            phase=TrainingPhase.BASE,
        )
        assert session.training_plan_id == plan_id
        assert session.scheduled_date == date(2024, 1, 15)
        assert session.session_type == SessionType.EASY_RUN

    def test_is_key_session_defaults_to_false(self):
        plan_id = uuid.uuid4()
        session = PlannedSession(
            training_plan_id=plan_id,
            scheduled_date=date(2024, 1, 15),
            session_type=SessionType.EASY_RUN,
            dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            week_number=1,
            phase=TrainingPhase.BASE,
            is_key_session=False,
        )
        assert session.is_key_session is False

    def test_generation_metadata_defaults_to_none(self):
        plan_id = uuid.uuid4()
        session = PlannedSession(
            training_plan_id=plan_id,
            scheduled_date=date(2024, 1, 15),
            session_type=SessionType.EASY_RUN,
            dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            week_number=1,
            phase=TrainingPhase.BASE,
        )
        assert session.generation_metadata is None


class TestPlannedSessionTable:
    def test_table_name_is_planned_sessions(self):
        assert PlannedSession.__tablename__ == "planned_sessions"


class TestPlannedSessionTableArgs:
    def test_contains_both_indexes(self):
        table_args = PlannedSession.__table_args__
        index_names = [arg.name for arg in table_args if hasattr(arg, "name")]
        assert "ix_planned_sessions_plan_date" in index_names
        assert "ix_planned_sessions_plan_week" in index_names