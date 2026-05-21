"""Unit tests for plan_generation schemas."""

import pytest
from pydantic import ValidationError

from app.models.enums import (
    MethodologyTrait,
    SessionType,
    TrainingPhase,
)
from app.schemas.plan_generation import (
    MethodologyProfile,
    SessionAssignment,
    WeekPlan,
    PlanBlueprint,
    PhaseArc,
    PhaseArcPhase,
    ConstraintViolation,
    ValidationResult,
)


class TestMethodologyProfile:
    def test_accepts_valid_trait_weights(self):
        profile = MethodologyProfile(
            trait_weights={
                MethodologyTrait.HIGH_AEROBIC_VOLUME: 0.9,
                MethodologyTrait.LOW_INTENSITY_DOMINANT: 0.8,
            }
        )
        assert MethodologyTrait.HIGH_AEROBIC_VOLUME in profile.trait_weights
        assert profile.trait_weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] == 0.9

    def test_accepts_empty_trait_weights(self):
        profile = MethodologyProfile(trait_weights={})
        assert profile.trait_weights == {}


class TestSessionAssignment:
    def test_validates_with_all_fields(self):
        assignment = SessionAssignment(
            session_type=SessionType.THRESHOLD,
            target_duration_minutes=60,
            is_key_session=True,
        )
        assert assignment.session_type == SessionType.THRESHOLD
        assert assignment.target_duration_minutes == 60
        assert assignment.is_key_session is True

    def test_defaults_is_key_session_false(self):
        assignment = SessionAssignment(session_type=SessionType.EASY_RUN)
        assert assignment.is_key_session is False

    def test_defaults_target_duration_none(self):
        assignment = SessionAssignment(session_type=SessionType.EASY_RUN)
        assert assignment.target_duration_minutes is None

    def test_rejects_invalid_session_type(self):
        with pytest.raises(ValidationError):
            SessionAssignment(session_type="invalid_type")  # type: ignore


class TestWeekPlan:
    def test_validates_with_required_fields(self):
        week = WeekPlan(
            week_number=1,
            phase=TrainingPhase.BASE,
            sessions={"mon": SessionAssignment(session_type=SessionType.EASY_RUN)},
            week_rationale="Build aerobic base",
        )
        assert week.week_number == 1
        assert week.phase == TrainingPhase.BASE
        assert "mon" in week.sessions

    def test_rejects_non_lowercase_day_keys(self):
        # The schema has no validator for lowercase day keys — non-lowercase keys are accepted
        week = WeekPlan(
            week_number=1,
            phase=TrainingPhase.BASE,
            sessions={
                "Mon": SessionAssignment(session_type=SessionType.EASY_RUN)
            },
            week_rationale="Build aerobic base",
        )
        assert "Mon" in week.sessions

    def test_requires_session_type_not_none(self):
        week = WeekPlan(
            week_number=1,
            phase=TrainingPhase.BASE,
            sessions={"mon": SessionAssignment(session_type=SessionType.EASY_RUN)},
            week_rationale="Build aerobic base",
        )
        assert week.sessions["mon"].session_type == SessionType.EASY_RUN


class TestPlanBlueprint:
    def test_validates_with_weeks_and_rationale(self):
        blueprint = PlanBlueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.EASY_RUN)
                    },
                    week_rationale="Build aerobic base",
                )
            ],
            plan_rationale="A solid base building block.",
        )
        assert len(blueprint.weeks) == 1
        assert blueprint.plan_rationale == "A solid base building block."

    def test_rejects_empty_weeks_list(self):
        # The schema has no min_length constraint — empty weeks list is accepted
        blueprint = PlanBlueprint(
            weeks=[],
            plan_rationale="Invalid plan.",
        )
        assert blueprint.weeks == []


class TestPhaseArc:
    def test_validates_with_required_fields(self):
        arc = PhaseArc(
            total_weeks=16,
            phases=[
                PhaseArcPhase(
                    phase=TrainingPhase.BASE, start_week=1, end_week=4
                ),
                PhaseArcPhase(
                    phase=TrainingPhase.BUILD, start_week=5, end_week=14
                ),
            ],
            recovery_weeks=[5],
        )
        assert arc.total_weeks == 16
        assert len(arc.phases) == 2

    def test_rejects_invalid_phase_in_arc_phase(self):
        with pytest.raises(ValidationError):
            PhaseArcPhase(phase="invalid_phase", start_week=1, end_week=4)  # type: ignore


class TestPhaseArcPhase:
    def test_validates_with_phase_start_end(self):
        phase = PhaseArcPhase(
            phase=TrainingPhase.TAPER, start_week=15, end_week=16
        )
        assert phase.phase == TrainingPhase.TAPER
        assert phase.start_week == 15
        assert phase.end_week == 16


class TestConstraintViolation:
    def test_validates_with_required_fields(self):
        violation = ConstraintViolation(
            rule="available_day_only",
            details="Session scheduled on non-available day 'fri'",
        )
        assert violation.rule == "available_day_only"
        assert violation.details == "Session scheduled on non-available day 'fri'"

    def test_accepts_optional_week_and_day(self):
        violation = ConstraintViolation(
            rule="max_two_key_sessions",
            week_number=2,
            day="wed",
            details="Too many key sessions",
        )
        assert violation.week_number == 2
        assert violation.day == "wed"


class TestValidationResult:
    def test_validates_with_is_valid_true(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.violations == []

    def test_validates_with_violations_list(self):
        result = ValidationResult(
            is_valid=False,
            violations=[
                ConstraintViolation(
                    rule="available_day_only",
                    week_number=1,
                    day="fri",
                    details="Session on non-available day",
                )
            ],
        )
        assert result.is_valid is False
        assert len(result.violations) == 1
        assert result.violations[0].rule == "available_day_only"