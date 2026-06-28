"""Unit tests for the plan-generation error surface.

The plan-generation domain exception surface is small — only three
classes:

* ``PlanGenerationError`` — the base class.
* ``TrainingLengthGateError`` — gate rejection with action / message /
  gate_reason attributes.
* ``InvalidGoalTypeError`` — re-exported from onboarding_errors so the
  type identity is preserved (one shared class, not two distinct
  classes with the same name).

The router maps these to specific HTTP status codes; the service layer
raises them.

Reference plan:
docs/implementation/phase-1/phase-1-4-p1-plan-generation.md
"""

from __future__ import annotations

import pytest

from app.services.onboarding_errors import InvalidGoalTypeError as OnboardingInvalid
from app.services.plan_generation_errors import (
    InvalidGoalTypeError,
    PlanGenerationError,
    TrainingLengthGateError,
)


class TestExceptionHierarchy:
    """Inheritance invariants documented in the plan."""

    def test_training_length_gate_inherits_plan_generation(self) -> None:
        """All plan-generation failures inherit PlanGenerationError."""
        assert issubclass(TrainingLengthGateError, PlanGenerationError)

    def test_plan_generation_is_exception(self) -> None:
        assert issubclass(PlanGenerationError, Exception)

    def test_invalid_goal_type_identity_preserved(self) -> None:
        """The plan-generation ``InvalidGoalTypeError`` is identity-equal to
        the onboarding one — both modules reuse the same class so
        ``except InvalidGoalTypeError`` works regardless of import path."""
        assert InvalidGoalTypeError is OnboardingInvalid


class TestTrainingLengthGateErrorAttributes:
    """The error class exposes ``action`` / ``message`` / ``gate_reason``."""

    def test_propose_intermediate_attributes(self) -> None:
        err = TrainingLengthGateError(
            action="propose_intermediate",
            message="Goal is too far out.",
            gate_reason="goal_too_far",
        )
        assert err.action == "propose_intermediate"
        assert err.message == "Goal is too far out."
        assert err.gate_reason == "goal_too_far"

    def test_propose_shorter_goal_attributes(self) -> None:
        err = TrainingLengthGateError(
            action="propose_shorter_goal",
            message="10K or half marathon is more realistic.",
            gate_reason="fitness_insufficient_for_distance",
        )
        assert err.action == "propose_shorter_goal"
        assert (
            err.message
            == "10K or half marathon is more realistic."
        )
        assert err.gate_reason == "fitness_insufficient_for_distance"

    def test_message_includes_gate_reason_in_str(self) -> None:
        """``str(err)`` round-trips useful diagnostic info."""
        err = TrainingLengthGateError(
            action="propose_intermediate",
            message="Goal too far.",
            gate_reason="goal_too_far",
        )
        rendered = str(err)
        assert "goal_too_far" in rendered
        assert "propose_intermediate" in rendered

    def test_can_be_caught_by_base_class(self) -> None:
        """Use ``except PlanGenerationError`` to catch the gate error too."""
        err = TrainingLengthGateError(
            action="propose_intermediate",
            message="x",
            gate_reason="goal_too_far",
        )
        with pytest.raises(PlanGenerationError):
            raise err


class TestInvalidGoalTypeErrorMessage:
    """The message always references the rejected goal-type value."""

    def test_message_includes_rejected_goal_type(self) -> None:
        with pytest.raises(InvalidGoalTypeError) as excinfo:
            raise OnboardingInvalid(
                "goal_type 'fitness_improvement' is not supported"
            )
        assert "fitness_improvement" in str(excinfo.value)

    def test_can_be_caught_by_base(self) -> None:
        with pytest.raises(InvalidGoalTypeError) as excinfo:
            raise OnboardingInvalid("bad goal type")
        assert "bad" in str(excinfo.value).lower()
