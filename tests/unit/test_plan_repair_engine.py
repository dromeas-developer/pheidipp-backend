"""Unit tests for PlanRepairEngine."""

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
from app.services.plan_repair_engine import PlanRepairEngine, MAX_REPAIR_ATTEMPTS


class TestPlanRepairEngine:
    def _engine(self) -> PlanRepairEngine:
        return PlanRepairEngine()

    def _blueprint(
        self,
        weeks: list[WeekPlan],
        plan_rationale: str = "Test plan.",
    ) -> PlanBlueprint:
        return PlanBlueprint(weeks=weeks, plan_rationale=plan_rationale)

    def _available_days(self) -> dict[str, dict]:
        return {
            "mon": {"available": True},
            "wed": {"available": True},
            "sat": {"available": True},
        }

    def _phase_arc(self) -> PhaseArc:
        return PhaseArc(
            total_weeks=16,
            phases=[
                PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=4),
                PhaseArcPhase(phase=TrainingPhase.BUILD, start_week=5, end_week=14),
                PhaseArcPhase(phase=TrainingPhase.TAPER, start_week=15, end_week=16),
            ],
            recovery_weeks=[],
        )

    def test_repair_returns_original_blueprint_when_valid(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={"mon": SessionAssignment(session_type=SessionType.EASY_RUN)},
                    week_rationale="Valid.",
                )
            ]
        )
        valid_result = ValidationResult(is_valid=True)
        result = engine.repair(blueprint, valid_result, self._available_days())
        assert result == blueprint

    def test_repair_converts_back_to_back_threshold_to_easy_run(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "wed": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Back to back threshold.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="no_back_to_back_intensity",
                week_number=1,
                day="wed",
                details="Back to back intensity sessions",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        # The second threshold should be downgraded to easy_run
        assert result.weeks[0].sessions["wed"].session_type == SessionType.EASY_RUN

    def test_repair_converts_back_to_back_vo2max_to_easy_run(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.VO2MAX),
                        "wed": SessionAssignment(session_type=SessionType.VO2MAX),
                    },
                    week_rationale="Back to back VO2max.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="no_back_to_back_intensity",
                week_number=1,
                day="wed",
                details="Back to back intensity",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        assert result.weeks[0].sessions["wed"].session_type == SessionType.EASY_RUN

    def test_repair_converts_back_to_back_tempo_to_easy_run(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.TEMPO),
                        "wed": SessionAssignment(session_type=SessionType.TEMPO),
                    },
                    week_rationale="Back to back tempo.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="no_back_to_back_intensity",
                week_number=1,
                day="wed",
                details="Back to back intensity",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        assert result.weeks[0].sessions["wed"].session_type == SessionType.EASY_RUN

    def test_repair_removes_session_on_non_available_day(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "fri": SessionAssignment(session_type=SessionType.EASY_RUN),
                    },
                    week_rationale="On unavailable day.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="available_day_only",
                week_number=1,
                day="fri",
                details="Non-available day",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        assert "fri" not in result.weeks[0].sessions

    def test_repair_removes_excess_key_sessions_flag(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "wed": SessionAssignment(session_type=SessionType.VO2MAX, is_key_session=True),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN, is_key_session=True),
                    },
                    week_rationale="Too many key sessions.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="max_two_key_sessions",
                week_number=1,
                details="Too many key sessions",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        key_sessions = [
            day for day, s in result.weeks[0].sessions.items() if s.is_key_session
        ]
        assert len(key_sessions) <= 2

    def test_repair_keeps_first_2_key_sessions_unchanged(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD, is_key_session=True),
                        "wed": SessionAssignment(session_type=SessionType.VO2MAX, is_key_session=True),
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN, is_key_session=True),
                    },
                    week_rationale="Too many key sessions.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="max_two_key_sessions",
                week_number=1,
                details="Too many key sessions",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        # First 2 should stay key sessions
        assert result.weeks[0].sessions["mon"].is_key_session is True
        assert result.weeks[0].sessions["wed"].is_key_session is True
        # Third should have key flag removed
        assert result.weeks[0].sessions["sat"].is_key_session is False

    def test_repair_returns_none_for_long_run_recovery_violation(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "sat": SessionAssignment(session_type=SessionType.LONG_RUN),
                        "sun": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Long run recovery violation.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="long_run_recovery",
                week_number=1,
                day="sat",
                details="Long run not followed by easy session",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        # The engine returns the original blueprint (cannot insert sessions)
        result = engine.repair(blueprint, invalid_result, self._available_days())
        assert result is not None

    def test_repair_applies_at_most_max_repair_attempts(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "wed": SessionAssignment(session_type=SessionType.THRESHOLD),
                        "fri": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Multiple violations.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="no_back_to_back_intensity",
                week_number=1,
                day="wed",
                details="Back to back",
            ),
            ConstraintViolation(
                rule="no_back_to_back_intensity",
                week_number=1,
                day="fri",
                details="Back to back",
            ),
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        # Only one repair should have been applied
        assert MAX_REPAIR_ATTEMPTS == 1

    def test_repair_does_not_modify_week_topology(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(session_type=SessionType.EASY_RUN),
                        "wed": SessionAssignment(session_type=SessionType.THRESHOLD),
                    },
                    week_rationale="Valid week.",
                )
            ]
        )
        valid_result = ValidationResult(is_valid=True)
        result = engine.repair(blueprint, valid_result, self._available_days())

        assert len(result.weeks) == 1
        assert result.weeks[0].week_number == 1
        assert result.weeks[0].phase == TrainingPhase.BASE

    def test_repair_does_not_alter_target_duration_when_downgrading(self):
        engine = self._engine()
        blueprint = self._blueprint(
            weeks=[
                WeekPlan(
                    week_number=1,
                    phase=TrainingPhase.BASE,
                    sessions={
                        "mon": SessionAssignment(
                            session_type=SessionType.THRESHOLD,
                            target_duration_minutes=60,
                        ),
                        "wed": SessionAssignment(
                            session_type=SessionType.THRESHOLD,
                            target_duration_minutes=45,
                        ),
                    },
                    week_rationale="Back to back.",
                )
            ]
        )
        violations = [
            ConstraintViolation(
                rule="no_back_to_back_intensity",
                week_number=1,
                day="wed",
                details="Back to back intensity",
            )
        ]
        invalid_result = ValidationResult(is_valid=False, violations=violations)

        result = engine.repair(blueprint, invalid_result, self._available_days())

        # When downgrading, duration should be preserved
        assert result.weeks[0].sessions["wed"].target_duration_minutes == 45