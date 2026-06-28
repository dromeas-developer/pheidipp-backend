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
from app.services.context_budget_service import ContextBudgetService
from app.services.event_publisher import EventPublisher, OutboxEvent
from app.services.first_message_agent import (
    FirstMessageAgent,
    FirstMessageAlreadyExistsError,
    LLMServiceUnavailableError,
)
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
from app.services.plan_generation_errors import (
    PlanGenerationError,
    TrainingLengthGateError,
)
from app.services.plan_generation_service import (
    PlanGenerationResult,
    PlanGenerationService,
    SessionDayAssignment,
)
from app.core.prompt_registry import PromptNotFoundError, PromptRegistry
from app.services.twin_context_assembler import (
    AthleteTwinContext,
    ComputedObservations,
    TwinContextAssembler,
    TwinContextSummary,
)

__all__ = [
    "AthleteNotFoundError",
    "AthleteTwinContext",
    "AuthError",
    "AuthResult",
    "AuthService",
    "ContextBudgetService",
    "CrossAthleteAccessError",
    "DuplicateEmailError",
    "EventPublisher",
    "FirstMessageAgent",
    "FirstMessageAlreadyExistsError",
    "InvalidCredentialsError",
    "InvalidGoalTypeError",
    "InvalidRefreshTokenError",
    "IssuedTokens",
    "LLMServiceUnavailableError",
    "OnboardingAlreadyCompleteError",
    "OnboardingError",
    "OnboardingIncompleteError",
    "OnboardingResult",
    "OnboardingService",
    "OnboardingStatus",
    "OutboxEvent",
    "PlanGenerationError",
    "PlanGenerationResult",
    "PlanGenerationService",
    "PreferencesSnapshot",
    "ProfileSnapshot",
    "PromptNotFoundError",
    "PromptRegistry",
    "SessionDayAssignment",
    "TrainingGoalConflictError",
    "TrainingLengthGateError",
    "TwinContextAssembler",
    "TwinContextSummary",
    "UnauthenticatedError",
    "_GoalInput",
    "_PreferencesInput",
    "_ProfileInput",
    "ComputedObservations",
]