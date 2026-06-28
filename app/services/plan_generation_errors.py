"""Domain exceptions for the plan-generation surface.

Mirrors the per-subsystem ``*_errors.py`` pattern used by the auth and
onboarding services. The service layer raises these as plain Python
exceptions so the surface stays transport-agnostic; the API router
maps each exception type to its HTTP status code.

Exception → HTTP mapping:

* ``PlanGenerationError`` — base; non-specific generation failure (422).
* ``TrainingLengthGateError`` — gate result was not ``proceed``
  (propose_intermediate / propose_shorter_goal). The API layer surfaces
  this as 422 with the gate ``message`` and ``gate_reason``.
* ``InvalidGoalTypeError`` — goal type outside the Phase-1.4 whitelist
  ``{race_event, target_performance}`` (422).

Note: ``InvalidGoalTypeError`` is re-exported from the onboarding
errors module so a single name is shared across subsystems. Importing
it here keeps the service surface self-contained; the type identity
is preserved (``InvalidGoalTypeError`` from
``app.services.onboarding_errors``).
"""

from __future__ import annotations

from app.services.onboarding_errors import InvalidGoalTypeError

__all__ = [
    "InvalidGoalTypeError",
    "PlanGenerationError",
    "TrainingLengthGateError",
]


class PlanGenerationError(Exception):
    """Base for all plan-generation failures.

    All other plan-generation-specific exceptions inherit from this
    class so ``except PlanGenerationError`` at the API layer captures
    every plan-side failure type without enumerating them. Callers
    that need finer-grained handling match on the subclass.
    """


class TrainingLengthGateError(PlanGenerationError):
    """Training length gate rejected the goal.

    Raised when ``evaluate_training_length`` for ``race_event`` mode
    returns anything other than ``action='proceed'`` — either a goal
    that is too far out (``propose_intermediate``) or a goal-event /
    fitness combination that's unsafe (``propose_shorter_goal``).

    The constructor accepts the gate ``action``, human-readable
    ``message``, and ``gate_reason``; the API layer turns those into a
    stable 422 response body.
    """

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
