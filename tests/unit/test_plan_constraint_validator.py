"""Unit tests for PlanConstraintValidator."""

import pytest

from app.models.enums import SessionType, TrainingPhase
from app.schemas.plan_generation import (
    PlanBlueprint,
    WeekPlan,
    SessionAssignment,
    PhaseArc,
    PhaseArcPhase,
    ValidationResult,
    ConstraintViolation,
)
from app.services.plan_constraint_validator import PlanConstraintValidator


class TestPlanConstraintValidatorValidate:
    def _validator(self) -> PlanConstraintValidator:
        return PlanConstraintValidator()

    def _phase_arc_16_weeks(self) -> PhaseArc:
        return PhaseArc(
            total_weeks=16,
            phases=[
                PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=4),
                PhaseArcPhase(phase=TrainingPhase.BUILD, start_week=5, end_week=14),
                PhaseArcPhase(phase=TrainingPhase.TAPER, start_week=15, end_week=16),
            ],
            recovery_weeks=[5],
        )

    def _available_days(self) -> dict[str, dict]:
        return {
            "mon": {"available": True},
            "wed": {"available": True},
            "fri": {"available": True},
            "sat": {"available": True},
            "sun": {"available": True},
        }

    def test_validate_returns_valid_for_blueprint_with_no_violations(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.EASY_RUN),
                        "wed": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN, is_key_session=True),
                    },
                    week_rationale="Build base.",
                )
            ],
            plan_rationale="A valid plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is True
        assert result.violations == []

    def test_validate_detects_session_on_non_available_day(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "fri": SessionAssignment(session_type=SessionType.EASY_RUN),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        available = {"mon": {"available": True}, "wed": {"available": True}}
        result = validator.validate(blueprint, available, self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "available_day_only" in rules

    def test_validate_detects_phase_not_in_phase_arc(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.RACE,  # Not in the 16-week phase arc
                    sessions={"mon": SessionAssignment(session_type=SessionType.EASY_RUN)},
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "phase_arc_alignment" in rules

    def test_validate_detects_back_to_back_threshold_sessions(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "tue": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        available = {"mon": {}, "tue": {}, "wed": {}}
        result = validator.validate(blueprint, available, self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "no_back_to_back_intensity" in rules

    def test_validate_detects_back_to_back_vo2max_sessions(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.VO2MAX),
                        "tue": SessionAssignment(session_type=SessionType.VO2MAX),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        available = {"mon": {}, "tue": {}, "wed": {}}
        result = validator.validate(blueprint, available, self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "no_back_to_back_intensity" in rules

    def test_validate_allows_threshold_followed_by_easy_run(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "tue": SessionAssignment(session_type=SessionType.EASY_RUN),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        available = {"mon": {}, "tue": {}, "wed": {}}
        result = validator.validate(blueprint, available, self._phase_arc_16_weeks())
        assert result.is_valid is True

    def test_validate_allows_easy_run_followed_by_threshold(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.EASY_RUN),
                        "tue": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        available = {"mon": {}, "tue": {}, "wed": {}}
        result = validator.validate(blueprint, available, self._phase_arc_16_weeks())
        assert result.is_valid is True

    def test_validate_detects_more_than_2_key_sessions_per_week(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "wed": SessionAssignment(session_type=SessionType.VO2MAX, is_key_session=True),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN, is_key_session=True),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "max_two_key_sessions" in rules

    def test_validate_allows_exactly_2_key_sessions(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN, is_key_session=True),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is True

    def test_validate_detects_recovery_week_with_gt_2_hard_sessions(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=5,
                    phase=TrainingPhase.BUILD,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "wed": SessionAssignment(session_type=SessionType.VO2MAX),
                        "fri": SessionAssignment(session_type=SessionType.LONG_RUN),
                    },
                    week_rationale="Recovery week.",
                )
            ],
            plan_rationale="Test plan.",
        )
        arc = self._phase_arc_16_weeks()
        result = validator.validate(blueprint, self._available_days(), arc)
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "recovery_week_density" in rules

    def test_validate_allows_recovery_week_with_lte_2_hard_sessions(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=5,
                    phase=TrainingPhase.BUILD,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                    },
                    week_rationale="Recovery week.",
                )
            ],
            plan_rationale="Test plan.",
        )
        arc = self._phase_arc_16_weeks()
        result = validator.validate(blueprint, self._available_days(), arc)
        assert result.is_valid is True

    def test_validate_detects_long_run_not_followed_by_easy_session(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                        "sun": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "long_run_recovery" in rules

    def test_validate_allows_long_run_followed_by_rest(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                        "sun": SessionAssignment(session_type=SessionType.REST),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is True

    def test_validate_allows_long_run_followed_by_recovery_run(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                        "sun": SessionAssignment(session_type=SessionType.RECOVERY_RUN),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is True

    def test_validate_detects_long_run_followed_by_threshold(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                        "sun": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "long_run_recovery" in rules

    def test_validate_detects_medium_long_run_not_followed_by_easy(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.MEDIUM_LONG_RUN),
                        "sun": SessionAssignment(session_type=SessionType.VO2MAX),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is False
        rules = [v.rule for v in result.violations]
        assert "long_run_recovery" in rules

    def test_validate_allows_long_run_as_last_session_in_plan(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=16,
                    phase=TrainingPhase.TAPER,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                    },
                    week_rationale="Final long run.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is True

    def test_validate_returns_all_violations_in_single_pass(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "tue": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "wed": SessionAssignment(session_type=SessionType.VO2MAX, is_key_session=True),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN, is_key_session=True),
                    },
                    week_rationale="Multiple violations.",
                )
            ],
            plan_rationale="Test plan.",
        )
        result = validator.validate(blueprint, self._available_days(), self._phase_arc_16_weeks())
        assert result.is_valid is False
        assert len(result.violations) > 1

    def test_validation_result_violations_have_correct_fields(self):
        validator = self._validator()
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "fri": SessionAssignment(session_type=SessionType.EASY_RUN),
                    },
                    week_rationale="Test.",
                )
            ],
            plan_rationale="Test plan.",
        )
        available = {"mon": {"available": True}}
        result = validator.validate(blueprint, available, self._phase_arc_16_weeks())
        violation = result.violations[0]
        assert violation.rule == "available_day_only"
        assert violation.week_number == 1
        assert violation.day == "fri"
        assert violation.details is not None
        assert len(violation.details) > 0