"""Domain exceptions for the onboarding surface."""

from __future__ import annotations


class OnboardingError(Exception):
    """Base for all onboarding-domain errors."""


class OnboardingAlreadyCompleteError(OnboardingError):
    """Onboarding already complete (HTTP 409)."""


class AthleteNotFoundError(OnboardingError):
    """Athlete_id does not match any Athlete row (HTTP 404)."""


class OnboardingIncompleteError(OnboardingError):
    """Athlete has not finished onboarding (HTTP 409)."""


class TrainingGoalConflictError(OnboardingError):
    """Second active TrainingGoal for the same athlete (HTTP 409)."""


class InvalidGoalTypeError(OnboardingError):
    """Goal type outside the onboarding whitelist (HTTP 422)."""
