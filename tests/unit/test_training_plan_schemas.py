"""Unit tests for training_plan schemas."""

import uuid

import pytest
from pydantic import ValidationError

from app.models.enums import (
    TrainingPlanStatus,
    SessionType,
    PhysiologicalIntent,
    TrainingPhase,
)
from app.schemas.training_plan import (
    TrainingPlanBase,
    PlannedSessionBase,
    TrainingPlanResponse,
    TrainingPlanListItem,
    TrainingPlanListResponse,
)


class TestTrainingPlanBase:
    def test_validates_with_required_fields(self, sample_training_plan):
        schema = TrainingPlanBase.model_validate(sample_training_plan)
        assert schema.athlete_id == sample_training_plan.athlete_id
        assert schema.status == sample_training_plan.status

    def test_accepts_optional_fields(self):
        from datetime import datetime
        plan = TrainingPlanBase(
            id=uuid.uuid4(),
            athlete_id=uuid.uuid4(),
            status=TrainingPlanStatus.ACTIVE,
            created_at=datetime.now(),
            archived_at=None,
            plan_rationale=None,
        )
        assert plan.archived_at is None
        assert plan.plan_rationale is None


class TestPlannedSessionBase:
    def test_validates_with_required_fields(self, sample_planned_session):
        schema = PlannedSessionBase.model_validate(sample_planned_session)
        assert schema.session_type == sample_planned_session.session_type
        assert schema.phase == sample_planned_session.phase

    def test_accepts_optional_fields(self):
        from datetime import date, datetime
        session = PlannedSessionBase(
            id=uuid.uuid4(),
            training_plan_id=uuid.uuid4(),
            scheduled_date=date.today(),
            session_type=SessionType.EASY_RUN,
            dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            target_duration_minutes=None,
            is_key_session=False,
            week_number=1,
            phase=TrainingPhase.BASE,
            created_at=datetime.now(),
        )
        assert session.target_duration_minutes is None


class TestTrainingPlanResponse:
    def test_validates_with_nested_structures(self, sample_training_plan, sample_planned_session):
        response = TrainingPlanResponse(
            training_plan=TrainingPlanBase.model_validate(sample_training_plan),
            planned_sessions=[PlannedSessionBase.model_validate(sample_planned_session)],
        )
        assert response.training_plan is not None
        assert len(response.planned_sessions) == 1

    def test_validates_empty_planned_sessions_list(self, sample_training_plan):
        response = TrainingPlanResponse(
            training_plan=TrainingPlanBase.model_validate(sample_training_plan),
            planned_sessions=[],
        )
        assert response.planned_sessions == []


class TestTrainingPlanListItem:
    def test_validates_with_nested_structures(self, sample_training_plan):
        item = TrainingPlanListItem(
            training_plan=TrainingPlanBase.model_validate(sample_training_plan),
            planned_sessions=[],
        )
        assert item.training_plan is not None


class TestTrainingPlanListResponse:
    def test_validates_with_items_and_total(self, sample_training_plan):
        response = TrainingPlanListResponse(
            items=[
                TrainingPlanListItem(
                    training_plan=TrainingPlanBase.model_validate(sample_training_plan),
                    planned_sessions=[],
                )
            ],
            total=1,
        )
        assert response.total == 1
        assert len(response.items) == 1


# Fixtures for schema tests
@pytest.fixture
def sample_training_plan():
    from datetime import datetime
    from tests.factories import make_training_plan
    return make_training_plan()


@pytest.fixture
def sample_planned_session():
    from tests.factories import make_planned_session
    return make_planned_session()