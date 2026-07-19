"""Domain exceptions for the plan-generation surface."""

from __future__ import annotations

from app.services.onboarding_errors import InvalidGoalTypeError

__all__ = [
    "InvalidGoalTypeError",
    "PlanGenerationError",
    "TrainingLengthGateError",
]


class PlanGenerationError(Exception):
    """Base for all plan-generation failures."""


class TrainingLengthGateError(PlanGenerationError):
    """Training length gate rejected the goal."""

    def __init__(
        self,
        *,
        action: str,
        message: str,
        gate_reason: str,
    ) -> None:
        super().__init__(
            f"training length gate rejected: {gate_reason} ({action})"
        )
        self.action = action
        self.message = message
        self.gate_reason = gate_reason
