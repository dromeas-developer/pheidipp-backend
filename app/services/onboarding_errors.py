"""Domain exceptions for the onboarding surface.

These map to HTTP status codes at the API layer; the service layer raises
them as plain Python exceptions so the surface stays transport-agnostic.
Mirrors ``app.services.auth_errors`` for consistency.
"""

from __future__ import annotations


class OnboardingError(Exception):
    """Base for all onboarding-domain errors."""


class OnboardingAlreadyCompleteError(OnboardingError):
    """POST /athletes/{id}/onboarding called for an athlete whose
    ``onboarding_complete`` gate is already ``true`` (HTTP 409).

    Re-onboarding is not supported. Athletes update preferences via PATCH.
    """


class AthleteNotFoundError(OnboardingError):
    """The path ``athlete_id`` does not match any ``Athlete`` row (HTTP 404).

    In practice the cross-athlete guard (``require_self``) prevents this
    case for authenticated endpoints (returning 403 instead). This error
    is reserved for service-layer callers that bypass the API surface.
    """


class OnboardingIncompleteError(OnboardingError):
    """A read endpoint was called for an athlete that has not yet finished
    onboarding — preferences / twin / twin history do not exist yet (HTTP 409).

    The API layer maps this to 404 on GET endpoints per the plan; the
    exception type is shared between read endpoints and the service layer
    so both translate through the same mapping table.
    """


class TrainingGoalConflictError(OnboardingError):
    """A second ``TrainingGoal`` with ``status='active'`` was inserted for
    the same athlete, violating the partial unique index
    ``ix_training_goals_athlete_active`` (HTTP 409).
    """


class InvalidGoalTypeError(OnboardingError):
    """The supplied ``goal_type`` is outside the onboarding whitelist
    ``{race_event, target_performance}`` (HTTP 422).

    Even though ``GoalType`` carries five enum values, only those two are
    accepted at onboarding; ``fitness_improvement``, ``maintenance``, and
    ``recovery`` are rejected per the architecture contract.
    """
