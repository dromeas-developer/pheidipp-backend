"""Service layer for Pheidipp domain operations."""

from app.services.auth_errors import (
    AuthError,
    CrossAthleteAccessError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UnauthenticatedError,
)
from app.services.auth_results import AuthResult, IssuedTokens
from app.services.auth_service import AuthService
from app.services.event_publisher import EventPublisher, OutboxEvent
from app.services.onboarding_errors import (
    AthleteNotFoundError,
    InvalidGoalTypeError,
    OnboardingAlreadyCompleteError,
    OnboardingError,
    OnboardingIncompleteError,
    TrainingGoalConflictError,
)
from app.services.onboarding_results import (
    OnboardingResult,
    OnboardingStatus,
    PreferencesSnapshot,
    ProfileSnapshot,
)
from app.services.onboarding_service import (
    OnboardingService,
    _GoalInput,
    _PreferencesInput,
    _ProfileInput,
)

__all__ = [
    "AthleteNotFoundError",
    "AuthError",
    "AuthResult",
    "AuthService",
    "CrossAthleteAccessError",
    "DuplicateEmailError",
    "EventPublisher",
    "InvalidCredentialsError",
    "InvalidGoalTypeError",
    "InvalidRefreshTokenError",
    "IssuedTokens",
    "OnboardingAlreadyCompleteError",
    "OnboardingError",
    "OnboardingIncompleteError",
    "OnboardingResult",
    "OnboardingService",
    "OnboardingStatus",
    "OutboxEvent",
    "PreferencesSnapshot",
    "ProfileSnapshot",
    "TrainingGoalConflictError",
    "UnauthenticatedError",
    "_GoalInput",
    "_PreferencesInput",
    "_ProfileInput",
]
