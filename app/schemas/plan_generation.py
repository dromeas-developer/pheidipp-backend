from typing import Literal
from pydantic import BaseModel

from app.models.enums import MethodologyTrait, SessionType, TrainingPhase


class MethodologyProfile(BaseModel):
    trait_weights: dict[MethodologyTrait, float]


class SessionAssignment(BaseModel):
    session_type: SessionType
    target_duration_minutes: int | None = None
    is_key_session: bool = False


class WeekPlan(BaseModel):
    week_number: int
    phase: TrainingPhase
    sessions: dict[str, SessionAssignment]
    week_rationale: str


class PlanBlueprint(BaseModel):
    weeks: list[WeekPlan]
    plan_rationale: str


class PhaseArcPhase(BaseModel):
    phase: TrainingPhase
    start_week: int
    end_week: int


class PhaseArc(BaseModel):
    total_weeks: int
    phases: list[PhaseArcPhase]
    recovery_weeks: list[int]


class ConstraintViolation(BaseModel):
    rule: str
    week_number: int | None = None
    day: str | None = None
    details: str


class ValidationResult(BaseModel):
    is_valid: bool
    violations: list[ConstraintViolation] = []