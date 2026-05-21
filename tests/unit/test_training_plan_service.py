"""Unit tests for TrainingPlanService."""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import (
    GoalEventType,
    SessionType,
    PhysiologicalIntent,
    TrainingPhase,
    TrainingPlanStatus,
    ConfidenceLevel,
)
from app.schemas.plan_generation import (
    PlanBlueprint,
    WeekPlan,
    SessionAssignment,
    PhaseArc,
    PhaseArcPhase,
    MethodologyProfile,
    ValidationResult,
)
from app.schemas.training_plan import TrainingPlanResponse
from app.services.training_plan_service import (
    TrainingPlanService,
    SESSION_TYPE_TO_DOMINANT_INTENT,
)
from tests.factories import (
    make_athlete,
    make_athlete_profile,
    make_athlete_preferences,
    make_training_block,
    make_twin_state,
    make_training_plan,
    make_planned_session,
)


def _mock_agent():
    agent = MagicMock()
    agent.generate = AsyncMock()
    return agent


def _mock_validator():
    validator = MagicMock()
    return validator


def _mock_repair_engine():
    engine = MagicMock()
    return engine


def _mock_phase_arc_computer():
    computer = MagicMock()
    return computer


def _mock_brief_builder():
    builder = MagicMock()
    return builder


def _mock_methodology_profile_builder():
    builder = MagicMock()
    return builder


def _mock_training_plan_repo():
    repo = MagicMock()
    repo.session = MagicMock()
    repo.session.flush = AsyncMock()

    def _refresh(obj, *args, **kwargs):
        """Mock refresh that populates server-default fields."""
        import uuid as _uuid
        from datetime import datetime
        if obj.id is None:
            obj.id = _uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime(2024, 1, 1, 0, 0, 0)

    repo.session.refresh = AsyncMock(side_effect=_refresh)
    repo.session.add = MagicMock()
    return repo


def _mock_planned_session_repo():
    repo = MagicMock()
    repo.session = MagicMock()
    repo.session.flush = AsyncMock()

    def _refresh(obj, *args, **kwargs):
        """Mock refresh that populates server-default fields."""
        import uuid as _uuid
        from datetime import datetime
        if obj.id is None:
            obj.id = _uuid.uuid4()
        if obj.created_at is None:
            obj.created_at = datetime(2024, 1, 1, 0, 0, 0)

    repo.session.refresh = AsyncMock(side_effect=_refresh)
    repo.session.add = MagicMock()
    return repo


def _service(
    plan_repo=None, session_repo=None, phase_computer=None, brief_builder=None,
    agent=None, validator=None, repair_engine=None, methodology_builder=None
):
    return TrainingPlanService(
        training_plan_repo=plan_repo or _mock_training_plan_repo(),
        planned_session_repo=session_repo or _mock_planned_session_repo(),
        phase_arc_computer=phase_computer or _mock_phase_arc_computer(),
        brief_builder=brief_builder or _mock_brief_builder(),
        agent=agent or _mock_agent(),
        validator=validator or _mock_validator(),
        repair_engine=repair_engine or _mock_repair_engine(),
        methodology_profile_builder=methodology_builder or _mock_methodology_profile_builder(),
    )


class TestTrainingPlanServiceGeneratePlan:
    @pytest.mark.asyncio
    async def test_generate_plan_raises_value_error_when_athlete_not_found(self):
        svc = _service()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.generate_plan(uuid.uuid4(), uow)

    @pytest.mark.asyncio
    async def test_generate_plan_raises_value_error_when_preferences_not_found(self):
        svc = _service()
        athlete = make_athlete()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Preferences"):
            await svc.generate_plan(athlete.id, uow)

    @pytest.mark.asyncio
    async def test_generate_plan_raises_value_error_when_training_block_not_found(self):
        svc = _service()
        athlete = make_athlete()
        prefs = make_athlete_preferences()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="TrainingBlock"):
            await svc.generate_plan(athlete.id, uow)

    @pytest.mark.asyncio
    async def test_generate_plan_raises_value_error_when_twin_state_not_found(self):
        svc = _service()
        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="TwinState"):
            await svc.generate_plan(athlete.id, uow)

    @pytest.mark.asyncio
    async def test_generate_plan_calls_phase_arc_computer(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        phase_computer = _mock_phase_arc_computer()
        brief_builder = _mock_brief_builder()
        methodology_builder = _mock_methodology_profile_builder()
        agent = _mock_agent()
        validator = _mock_validator()
        repair_engine = _mock_repair_engine()

        svc = _service(
            plan_repo, session_repo, phase_computer, brief_builder,
            agent, validator, repair_engine, methodology_builder
        )

        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block()
        twin = make_twin_state()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin)

        phase_computer.compute = MagicMock(return_value=PhaseArc(
            total_weeks=16,
            phases=[PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=16)],
            recovery_weeks=[],
        ))
        brief_builder.build = MagicMock(return_value=MagicMock())
        agent.generate = AsyncMock(return_value=(
            {
                "weeks": [
                    {"week_number": 1, "phase": "base", "sessions": {}, "week_rationale": ""}
                ],
                "plan_rationale": "Test plan.",
            },
            {},
        ))
        plan_repo.create = AsyncMock(side_effect=lambda **kw: make_training_plan(**kw))
        session_repo.bulk_create = AsyncMock(return_value=[])

        await svc.generate_plan(athlete.id, uow)

        phase_computer.compute.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_plan_calls_methodology_profile_builder(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        phase_computer = _mock_phase_arc_computer()
        brief_builder = _mock_brief_builder()
        methodology_builder = _mock_methodology_profile_builder()
        agent = _mock_agent()
        validator = _mock_validator()
        repair_engine = _mock_repair_engine()

        svc = _service(
            plan_repo, session_repo, phase_computer, brief_builder,
            agent, validator, repair_engine, methodology_builder
        )

        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block(goal_event_type=GoalEventType.MARATHON)
        twin = make_twin_state()

        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin)

        phase_arc = PhaseArc(
            total_weeks=16,
            phases=[PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=16)],
            recovery_weeks=[],
        )
        phase_computer.compute = MagicMock(return_value=phase_arc)
        methodology_builder.build = MagicMock(return_value=MethodologyProfile(trait_weights={}))
        brief_builder.build = MagicMock(return_value=MagicMock())
        agent.generate = AsyncMock(return_value=(
            {"weeks": [], "plan_rationale": "Test plan."},
            {},
        ))
        plan_repo.create = AsyncMock(side_effect=lambda **kw: make_training_plan(**kw))
        session_repo.bulk_create = AsyncMock(return_value=[])

        await svc.generate_plan(athlete.id, uow)

        methodology_builder.build.assert_called_once()
        call_kwargs = methodology_builder.build.call_args.kwargs
        assert call_kwargs["event_type"] == GoalEventType.MARATHON
        assert call_kwargs["weeks_to_goal"] == 16
        assert call_kwargs["training_age"] == prefs.years_structured_training
        assert "available_days" in call_kwargs
        assert call_kwargs["structural_capacity_score"] == twin.structural_capacity_score
        assert call_kwargs["adaptation_confidence_level"] == twin.confidence_level
        assert call_kwargs["consistency_score"] == 0.7

    @pytest.mark.asyncio
    async def test_generate_plan_calls_agent_generate(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        phase_computer = _mock_phase_arc_computer()
        brief_builder = _mock_brief_builder()
        methodology_builder = _mock_methodology_profile_builder()
        agent = _mock_agent()
        validator = _mock_validator()
        repair_engine = _mock_repair_engine()

        svc = _service(
            plan_repo, session_repo, phase_computer, brief_builder,
            agent, validator, repair_engine, methodology_builder
        )

        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block()
        twin = make_twin_state()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin)

        phase_computer.compute = MagicMock(return_value=PhaseArc(
            total_weeks=16, phases=[PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=16)], recovery_weeks=[]
        ))
        brief_builder.build = MagicMock(return_value=MagicMock())
        agent.generate = AsyncMock(return_value=(
            {"weeks": [], "plan_rationale": "Test plan."},
            {"model": "test-model"},
        ))
        plan_repo.create = AsyncMock(side_effect=lambda **kw: make_training_plan(**kw))
        session_repo.bulk_create = AsyncMock(return_value=[])

        await svc.generate_plan(athlete.id, uow)

        agent.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_plan_validates_blueprint(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        phase_computer = _mock_phase_arc_computer()
        brief_builder = _mock_brief_builder()
        methodology_builder = _mock_methodology_profile_builder()
        agent = _mock_agent()
        validator = _mock_validator()
        repair_engine = _mock_repair_engine()

        svc = _service(
            plan_repo, session_repo, phase_computer, brief_builder,
            agent, validator, repair_engine, methodology_builder
        )

        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block()
        twin = make_twin_state()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin)

        phase_computer.compute = MagicMock(return_value=PhaseArc(
            total_weeks=16, phases=[PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=16)], recovery_weeks=[]
        ))
        brief_builder.build = MagicMock(return_value=MagicMock())
        agent.generate = AsyncMock(return_value=(
            {"weeks": [], "plan_rationale": "Test plan."},
            {},
        ))
        validator.validate = MagicMock(return_value=ValidationResult(is_valid=True))
        plan_repo.create = AsyncMock(side_effect=lambda **kw: make_training_plan(**kw))
        session_repo.bulk_create = AsyncMock(return_value=[])

        await svc.generate_plan(athlete.id, uow)

        validator.validate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_plan_calls_repair_when_validation_fails(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        phase_computer = _mock_phase_arc_computer()
        brief_builder = _mock_brief_builder()
        methodology_builder = _mock_methodology_profile_builder()
        agent = _mock_agent()
        validator = _mock_validator()
        repair_engine = _mock_repair_engine()

        svc = _service(
            plan_repo, session_repo, phase_computer, brief_builder,
            agent, validator, repair_engine, methodology_builder
        )

        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block()
        twin = make_twin_state()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin)

        phase_computer.compute = MagicMock(return_value=PhaseArc(
            total_weeks=16, phases=[PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=16)], recovery_weeks=[]
        ))
        brief_builder.build = MagicMock(return_value=MagicMock())
        agent.generate = AsyncMock(return_value=(
            {"weeks": [], "plan_rationale": "Test plan."},
            {},
        ))
        invalid_result = ValidationResult(is_valid=False, violations=[])
        valid_result = ValidationResult(is_valid=True)
        validator.validate = MagicMock(side_effect=[invalid_result, valid_result])
        repaired_blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1, phase=TrainingPhase.BASE,
                    sessions={"mon": SessionAssignment(session_type=SessionType.EASY_RUN)},
                    week_rationale="Repaired.",
                )
            ],
            plan_rationale="Repaired plan.",
        )
        repair_engine.repair = MagicMock(return_value=repaired_blueprint)
        plan_repo.create = AsyncMock(side_effect=lambda **kw: make_training_plan(**kw))
        session_repo.bulk_create = AsyncMock(return_value=[])

        await svc.generate_plan(athlete.id, uow)

        repair_engine.repair.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_plan_returns_training_plan_response(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        phase_computer = _mock_phase_arc_computer()
        brief_builder = _mock_brief_builder()
        methodology_builder = _mock_methodology_profile_builder()
        agent = _mock_agent()
        validator = _mock_validator()
        repair_engine = _mock_repair_engine()

        svc = _service(
            plan_repo, session_repo, phase_computer, brief_builder,
            agent, validator, repair_engine, methodology_builder
        )

        athlete = make_athlete()
        prefs = make_athlete_preferences()
        block = make_training_block()
        twin = make_twin_state()
        uow = MagicMock()
        uow.athletes.get_by_id = AsyncMock(return_value=athlete)
        uow.preferences.get_by_athlete = AsyncMock(return_value=prefs)
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=block)
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=twin)

        phase_computer.compute = MagicMock(return_value=PhaseArc(
            total_weeks=16, phases=[PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=16)], recovery_weeks=[]
        ))
        brief_builder.build = MagicMock(return_value=MagicMock())
        agent.generate = AsyncMock(return_value=(
            {
                "weeks": [
                    {
                        "week_number": 1, "phase": "base",
                        "sessions": {"mon": {"session_type": "easy_run"}},
                        "week_rationale": "Week 1"
                    }
                ],
                "plan_rationale": "Test plan."
            },
            {},
        ))
        validator.validate = MagicMock(return_value=ValidationResult(is_valid=True))
        plan_repo.create = AsyncMock(side_effect=lambda **kw: make_training_plan(**kw))
        session_repo.bulk_create = AsyncMock(return_value=[])

        result = await svc.generate_plan(athlete.id, uow)

        assert isinstance(result, TrainingPlanResponse)


class TestTrainingPlanServiceGetActivePlan:
    @pytest.mark.asyncio
    async def test_get_active_plan_returns_plan_when_exists(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        plan = make_training_plan()

        plan_repo.get_active_by_athlete = AsyncMock(return_value=plan)
        session_repo.list_by_plan = AsyncMock(return_value=[])

        svc = _service(plan_repo, session_repo)

        uow = MagicMock()
        result = await svc.get_active_plan(plan.athlete_id, uow)

        assert result is not None
        assert result.training_plan.id == plan.id

    @pytest.mark.asyncio
    async def test_get_active_plan_returns_none_when_not_exists(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        plan_repo.get_active_by_athlete = AsyncMock(return_value=None)

        svc = _service(plan_repo, session_repo)
        uow = MagicMock()

        result = await svc.get_active_plan(uuid.uuid4(), uow)
        assert result is None


class TestTrainingPlanServiceGetPlanById:
    @pytest.mark.asyncio
    async def test_get_plan_by_id_returns_plan_when_exists(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        plan = make_training_plan()

        plan_repo.get_by_id = AsyncMock(return_value=plan)
        session_repo.list_by_plan = AsyncMock(return_value=[])

        svc = _service(plan_repo, session_repo)
        uow = MagicMock()

        result = await svc.get_plan_by_id(plan.id, uow)
        assert result is not None
        assert result.training_plan.id == plan.id

    @pytest.mark.asyncio
    async def test_get_plan_by_id_returns_none_when_not_exists(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        plan_repo.get_by_id = AsyncMock(return_value=None)

        svc = _service(plan_repo, session_repo)
        uow = MagicMock()

        result = await svc.get_plan_by_id(uuid.uuid4(), uow)
        assert result is None


class TestTrainingPlanServiceArchivePlan:
    @pytest.mark.asyncio
    async def test_archive_plan_calls_repository(self):
        plan_repo = _mock_training_plan_repo()
        session_repo = _mock_planned_session_repo()
        plan_repo.archive_plan = AsyncMock()
        plan_repo.get_by_id = AsyncMock(return_value=make_training_plan())

        svc = _service(plan_repo, session_repo)
        uow = MagicMock()
        plan_id = uuid.uuid4()

        await svc.archive_plan(plan_id, uow)

        plan_repo.archive_plan.assert_called_once_with(plan_id)


class TestTrainingPlanServiceCountAvailableDays:
    def test_count_available_days_returns_correct_count(self):
        prefs = make_athlete_preferences(
            weekly_schedule={
                "days": {
                    "mon": {"available": True},
                    "tue": {"available": False},
                    "wed": {"available": True},
                    "thu": {"available": False},
                    "fri": {"available": True},
                    "sat": {"available": True},
                    "sun": {"available": False},
                }
            }
        )
        svc = _service()
        count = svc._count_available_days(prefs)
        assert count == 4  # mon, wed, fri, sat

    def test_count_available_days_returns_0_when_schedule_none(self):
        prefs = make_athlete_preferences(weekly_schedule=None)
        svc = _service()
        count = svc._count_available_days(prefs)
        assert count == 0

    def test_count_available_days_returns_0_when_days_missing(self):
        prefs = make_athlete_preferences(weekly_schedule={})
        svc = _service()
        count = svc._count_available_days(prefs)
        assert count == 0