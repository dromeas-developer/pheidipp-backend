"""Service layer for Pheidipp domain operations."""

from app.services.activity_ingestion_service import (
    ActivityIngestionError,
    ActivityIngestionResult,
    ActivityIngestionService,
    AthleteNotFoundForIngestionError,
    ObjectStorageFailureError,
    TwinRecalibrationFailureError,
)
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
from app.services.calibration_eligibility_service import (
    CalibrationEligibilityService,
)
from app.services.compliance_service import (
    ComplianceError,
    ComplianceFindings,
    ComplianceService,
)
from app.services.context_budget_service import ContextBudgetService
from app.services.event_publisher import EventPublisher, OutboxEvent
from app.services.fit_parser_service import (
    FitParseEmptyError,
    FitParseError,
    FitParserService,
    GpsRecord,
    ParsedFitData,
    BytesReader,
)
from app.agents.first_message_agent import (
    FirstMessageAgent,
    FirstMessageAlreadyExistsError,
    LLMServiceUnavailableError,
)
from app.services.load_computation_service import (
    LoadComputationError,
    LoadComputationInputs,
    LoadComputationService,
    LoadScores,
    MissingCriticalPowerError,
    MissingHeartRateError,
    estimate_max_hr_from_age,
)
from app.services.twin_recalibration_service import (
    BanisterUpdateResult,
    CalibrationRecalibrationResult,
    MissingAthleteFitnessError,
    MissingTrainingGoalError,
    RecalibrationResult,
    TwinRecalibrationService,
    TwinRecalibrationError,
)
from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageConflictError,
    ObjectStorageError,
    ObjectStorageNotConfiguredError,
    ObjectStorageUploadError,
    StoredFitObject,
    get_object_storage_client,
    reset_object_storage_client,
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
    GoalInput,
    PreferencesInput,
    ProfileInput,
)
from app.services.outbox_publisher_service import OutboxPublisherService
from app.services.physiology_update_service import (
    MissingAthletePhysiologyError,
    PhysiologyUpdateResult,
    PhysiologyUpdateService,
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
from app.services.plan_query_service import PlanQueryService
from app.core.prompt_registry import PromptNotFoundError, PromptRegistry
from app.services.signal_cleaning_service import SignalCleaningService
from app.agents.workout_generation_agent import WorkoutGenerationAgent
from app.services.workout_generation_errors import (
    LLMServiceUnavailableError as WorkoutLLMServiceUnavailableError,
    PlannedSessionNotFoundError,
    WorkoutAlreadyGeneratedError,
    WorkoutGenerationContractError,
    WorkoutGenerationError,
)
from app.services.workout_target_types import (
    DATA_TIER_TARGET_TYPE,
    SESSION_INTENT_MAP,
    get_step_physiological_intent,
)
from app.services.twin_context_assembler import (
    AthleteTwinContext,
    ComputedObservations,
    TwinContextAssembler,
    TwinContextSummary,
)
from app.services.threshold_detection_service import (
    ThresholdDetectionService,
    ThresholdObservation,
)

__all__ = [
    "ActivityIngestionError",
    "ActivityIngestionResult",
    "ActivityIngestionService",
    "AthleteNotFoundError",
    "AthleteNotFoundForIngestionError",
    "AthleteTwinContext",
    "AuthError",
    "AuthResult",
    "AuthService",
    "BanisterUpdateResult",
    "CalibrationEligibilityService",
    "CalibrationRecalibrationResult",
    "ComplianceError",
    "ComplianceFindings",
    "ComplianceService",
    "ContextBudgetService",
    "CrossAthleteAccessError",
    "DATA_TIER_TARGET_TYPE",
    "DuplicateEmailError",
    "EventPublisher",
    "FitParseEmptyError",
    "FitParseError",
    "FitParserService",
    "FirstMessageAgent",
    "FirstMessageAlreadyExistsError",
    "GpsRecord",
    "InvalidCredentialsError",
    "InvalidGoalTypeError",
    "InvalidRefreshTokenError",
    "IssuedTokens",
    "LLMServiceUnavailableError",
    "LoadComputationError",
    "LoadComputationInputs",
    "LoadComputationService",
    "LoadScores",
    "MissingAthleteFitnessError",
    "MissingAthletePhysiologyError",
    "MissingCriticalPowerError",
    "MissingHeartRateError",
    "MissingTrainingGoalError",
    "ObjectStorageClient",
    "ObjectStorageConflictError",
    "ObjectStorageError",
    "ObjectStorageFailureError",
    "ObjectStorageNotConfiguredError",
    "ObjectStorageUploadError",
    "OnboardingAlreadyCompleteError",
    "OnboardingError",
    "OnboardingIncompleteError",
    "OnboardingResult",
    "OnboardingService",
    "OnboardingStatus",
    "OutboxEvent",
    "OutboxPublisherService",
    "ParsedFitData",
    "PhysiologyUpdateResult",
    "PhysiologyUpdateService",
    "PlanGenerationError",
    "PlanGenerationResult",
    "PlanGenerationService",
    "PlanQueryService",
    "PlannedSessionNotFoundError",
    "PreferencesSnapshot",
    "ProfileSnapshot",
    "PromptNotFoundError",
    "PromptRegistry",
    "RecalibrationResult",
    "SESSION_INTENT_MAP",
    "SessionDayAssignment",
    "SignalCleaningService",
    "StoredFitObject",
    "ThresholdDetectionService",
    "ThresholdObservation",
    "TrainingGoalConflictError",
    "TrainingLengthGateError",
    "TwinContextAssembler",
    "TwinContextSummary",
    "TwinRecalibrationError",
    "TwinRecalibrationFailureError",
    "TwinRecalibrationService",
    "UnauthenticatedError",
    "WorkoutAlreadyGeneratedError",
    "WorkoutGenerationAgent",
    "WorkoutGenerationContractError",
    "WorkoutGenerationError",
    "WorkoutLLMServiceUnavailableError",
    "BytesReader",
    "GoalInput",
    "PreferencesInput",
    "ProfileInput",
    "ComputedObservations",
    "estimate_max_hr_from_age",
    "get_object_storage_client",
    "get_step_physiological_intent",
    "reset_object_storage_client",
]
