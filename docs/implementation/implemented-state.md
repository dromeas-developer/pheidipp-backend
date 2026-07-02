# implemented-state

Commit:
b22c6da

## Change Set

Base Commit:
b22c6da

Current Commit:
b22c6da

Files Added:
- app/utils/email_utils.py

Files Modified:
- app/repositories/athlete_auth_repository.py
- app/repositories/athlete_repository.py
- app/services/activity_ingestion_service.py
- app/services/auth_service.py

Files Deleted:
- none

Touched Areas:
- repositories
- services
- app

Generated:
2026-07-02T01:55:37.766208+00:00 UTC

Current DB Revision:
d1579f4430e7 (head)

Python Files Scanned:
108

---

## Verified Facts

### Domain Layer

Entities:
- Activity (activities) — app/models/activity.py
- Athlete (athletes) — app/models/athlete.py
- AthleteAuth (athlete_auths) — app/models/athlete_auth.py
- AthleteFitness (athlete_fitness) — app/models/athlete_fitness.py
- AthletePhysiology (athlete_physiology) — app/models/athlete_physiology.py
- AthletePreferences (athlete_preferences) — app/models/athlete_preferences.py
- AthleteProfile (athlete_profiles) — app/models/athlete_profile.py
- Checkpoint (checkpoints) — app/models/checkpoint.py
- CoachingMessage (coaching_messages) — app/models/coaching_message.py
- GeneratedWorkout (generated_workouts) — app/models/generated_workout.py
- GenerationEvent (generation_events) — app/models/generation_event.py
- PlannedSession (planned_sessions) — app/models/planned_session.py
- RefreshToken (athlete_refresh_tokens) — app/models/refresh_token.py
- RegenerationTask (regeneration_tasks) — app/models/regeneration_task.py
- SecondaryEvent (secondary_events) — app/models/secondary_event.py
- SystemEvent (system_events) — app/models/system_event.py
- SystemEventOutbox (system_event_outbox) — app/models/system_event.py
- TrainingGoal (training_goals) — app/models/training_goal.py
- TrainingPlan (training_plans) — app/models/training_plan.py
- TwinState (twin_states) — app/models/twin_state.py
- WeeklyPlan (weekly_plans) — app/models/weekly_plan.py
- WeeklySession (weekly_sessions) — app/models/weekly_plan.py
- WorkoutStep (workout_steps) — app/models/workout_step.py

Enums:
- ActivitySource — app/models/enums.py
- AuthProvider — app/models/enums.py
- CheckpointStatus — app/models/enums.py
- CheckpointType — app/models/enums.py
- DataTier — app/models/enums.py
- EventPublicationStatus — app/models/system_event.py
- GoalEventType — app/models/enums.py
- GoalType — app/models/enums.py
- GpsSource — app/models/enums.py
- HrSource — app/models/enums.py
- InjurySeverity — app/models/enums.py
- MeasurementSource — app/models/enums.py
- MessageType — app/models/enums.py
- ObjectiveCategory — app/models/enums.py
- PhaseLabel — app/models/enums.py
- PhysiologicalIntent — app/models/enums.py
- PlannedSessionStatus — app/models/enums.py
- PowerSource — app/models/enums.py
- PrimaryTrainingPlatform — app/models/enums.py
- RecoveryModifierLevel — app/models/enums.py
- SecondaryEventPriority — app/models/enums.py
- SessionPriority — app/models/enums.py
- SessionPurpose — app/models/enums.py
- SessionSlot — app/models/enums.py
- SessionType — app/models/enums.py
- Sex — app/models/enums.py
- SignalType — app/models/enums.py
- SportBackground — app/models/enums.py
- StepType — app/models/enums.py
- TrainingGoalStatus — app/models/enums.py
- TrainingPlanStatus — app/models/enums.py
- TrainingTimeOfDay — app/models/enums.py
- TwinConfidenceLevel — app/models/enums.py
- TwinTrigger — app/models/enums.py
- WeeklyPlanStatus — app/models/enums.py
- WellnessTrend — app/models/enums.py

### Persistence Layer

Repositories:
- ActivityRepository -> Activity (app/repositories/activity_repository.py)
- AthleteAuthRepository -> AthleteAuth (app/repositories/athlete_auth_repository.py)
- AthleteFitnessRepository -> AthleteFitness (app/repositories/athlete_fitness_repository.py)
- AthletePhysiologyRepository -> AthletePhysiology (app/repositories/athlete_physiology_repository.py)
- AthletePreferencesRepository -> AthletePreferences (app/repositories/athlete_preferences_repository.py)
- AthleteProfileRepository -> AthleteProfile (app/repositories/athlete_profile_repository.py)
- AthleteRepository -> Athlete (app/repositories/athlete_repository.py)
- CheckpointRepository -> Checkpoint (app/repositories/checkpoint_repository.py)
- CoachingMessageRepository -> CoachingMessage (app/repositories/coaching_message_repository.py)
- GeneratedWorkoutRepository -> GeneratedWorkout (app/repositories/generated_workout_repository.py)
- GenerationEventRepository -> GenerationEvent (app/repositories/generation_event_repository.py)
- PlannedSessionRepository -> PlannedSession (app/repositories/planned_session_repository.py)
- RefreshTokenRepository -> RefreshToken (app/repositories/refresh_token_repository.py)
- SystemEventOutboxRepository -> SystemEventOutbox (app/repositories/system_event_outbox_repository.py)
- SystemEventRepository -> SystemEvent (app/repositories/system_event_repository.py)
- TrainingGoalRepository -> TrainingGoal (app/repositories/training_goal_repository.py)
- TrainingPlanRepository -> TrainingPlan (app/repositories/training_plan_repository.py)
- TwinStateRepository -> TwinState (app/repositories/twin_state_repository.py)
- WeeklyPlanRepository -> WeeklyPlan (app/repositories/weekly_plan_repository.py)
- WeeklySessionRepository -> WeeklySession (app/repositories/weekly_plan_repository.py)
- WorkoutStepRepository -> WorkoutStep (app/repositories/workout_step_repository.py)

Migrations:
- 1b9e9026db1e (down: e7ffc8764335) — alembic/versions/1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py
- 79dc97d4e433 (down: 1b9e9026db1e) — alembic/versions/79dc97d4e433_phase_1_2c_twin_fitness_coaching_.py
- 8265efd46112 (down: fd373abd4b9e) — alembic/versions/8265efd46112_phase_1_1_p3_single_primary_auth_.py
- d1579f4430e7 (down: 79dc97d4e433) — alembic/versions/d1579f4430e7_add_training_plans_twin_state_fk.py
- e7ffc8764335 (down: 8265efd46112) — alembic/versions/e7ffc8764335_phase_1_2a_profile_preferences_activity.py
- fd373abd4b9e (down: none) — alembic/versions/fd373abd4b9e_phase_1_1_email_password_auth.py

### Service Layer

Services:
- ActivityIngestionService — app/services/activity_ingestion_service.py
- AuthService — app/services/auth_service.py
- ContextBudgetService — app/services/context_budget_service.py
- EventPublisher — app/services/event_publisher.py
- FirstMessageAgent — app/services/first_message_agent.py
- FirstMessageAlreadyExistsError — app/services/first_message_agent.py
- _BytesReader — app/services/fit_parser_service.py
- ObjectStorageClient — app/services/object_storage_client.py
- OnboardingService — app/services/onboarding_service.py
- _GoalInput — app/services/onboarding_service.py
- _PreferencesInput — app/services/onboarding_service.py
- _ProfileInput — app/services/onboarding_service.py
- TrainingLengthGateError — app/services/plan_generation_errors.py
- PlanGenerationService — app/services/plan_generation_service.py
- TwinRecalibrationService — app/services/twin_recalibration_service.py
- WorkoutGenerationAgent — app/services/workout_generation_agent.py
- PlannedSessionNotFoundError — app/services/workout_generation_errors.py
- WorkoutAlreadyGeneratedError — app/services/workout_generation_errors.py

### API Surface

Public API:
- GET /api/v1/athletes/{athlete_id}/activities (app/api/v1/activity.py:257 list_activities, router=activity_router)
- POST /api/v1/athletes/{athlete_id}/activities/upload (app/api/v1/activity.py:167 post_upload_activity, router=activity_router)
- GET /api/v1/athletes/{athlete_id}/activities/{activity_id} (app/api/v1/activity.py:289 get_activity, router=activity_router)
- POST /api/v1/athletes/{athlete_id}/activities/{activity_id}/analyse (app/api/v1/activity.py:309 post_analyse_activity, router=activity_router)
- GET /api/v1/athletes/{athlete_id}/activities/{activity_id}/analysis (app/api/v1/activity.py:367 get_activity_analysis, router=activity_router)
- POST /api/v1/athletes/{athlete_id}/coach/first-message (app/api/v1/coach.py:93 post_first_message, router=coach_router)
- GET /api/v1/athletes/{athlete_id}/coach/messages (app/api/v1/coach.py:134 get_coach_messages, router=coach_router)
- GET /api/v1/athletes/{athlete_id}/onboarding (app/api/v1/onboarding.py:181 get_onboarding, router=onboarding_router)
- POST /api/v1/athletes/{athlete_id}/onboarding (app/api/v1/onboarding.py:76 complete_onboarding, router=onboarding_router)
- GET /api/v1/athletes/{athlete_id}/plan (app/api/v1/plan.py:105 get_plan, router=plan_router)
- GET /api/v1/athletes/{athlete_id}/plan/checkpoints (app/api/v1/plan.py:210 get_plan_checkpoints, router=plan_router)
- GET /api/v1/athletes/{athlete_id}/plan/sessions (app/api/v1/plan.py:131 get_plan_sessions, router=plan_router)
- GET /api/v1/athletes/{athlete_id}/plan/upcoming (app/api/v1/plan.py:167 get_upcoming_sessions, router=plan_router)
- GET /api/v1/athletes/{athlete_id}/preferences (app/api/v1/onboarding.py:263 get_preferences, router=onboarding_router)
- PATCH /api/v1/athletes/{athlete_id}/preferences (app/api/v1/onboarding.py:289 patch_preferences, router=onboarding_router)
- GET /api/v1/athletes/{athlete_id}/profile (app/api/v1/onboarding.py:207 get_profile, router=onboarding_router)
- PATCH /api/v1/athletes/{athlete_id}/profile (app/api/v1/onboarding.py:231 patch_profile, router=onboarding_router)
- POST /api/v1/athletes/{athlete_id}/sessions/{session_id}/generate-workout (app/api/v1/workout.py:192 post_generate_workout, router=workout_router)
- GET /api/v1/athletes/{athlete_id}/today (app/api/v1/workout.py:126 get_today, router=workout_router)
- GET /api/v1/athletes/{athlete_id}/twin (app/api/v1/onboarding.py:317 get_twin_state, router=onboarding_router)
- GET /api/v1/athletes/{athlete_id}/twin/history (app/api/v1/onboarding.py:339 get_twin_history, router=onboarding_router)
- POST /api/v1/auth/login (app/api/v1/auth.py:116 login, router=auth_router)
- POST /api/v1/auth/refresh (app/api/v1/auth.py:137 refresh, router=auth_router)
- POST /api/v1/auth/register (app/api/v1/auth.py:91 register, router=auth_router)
- GET /api/v1/health/live (app/api/v1/health.py:11 live, router=health_router)
- GET /api/v1/health/ready (app/api/v1/health.py:19 ready, router=health_router)

### Contracts

- ActivityListResponse — app/schemas/activity.py
- ActivityNotFoundResponse — app/schemas/activity.py
- ActivityResponse — app/schemas/activity.py
- ActivityUploadResponse — app/schemas/activity.py
- CoachingMessageSummary — app/schemas/activity.py
- FitParseErrorResponse — app/schemas/activity.py
- PostWorkoutAnalysisResponse — app/schemas/activity.py
- AthleteResponse — app/schemas/auth.py
- AuthResponse — app/schemas/auth.py
- LoginRequest — app/schemas/auth.py
- RefreshRequest — app/schemas/auth.py
- RefreshResponse — app/schemas/auth.py
- RegisterProfileIn — app/schemas/auth.py
- RegisterRequest — app/schemas/auth.py
- TokenPairResponse — app/schemas/auth.py
- CoachingMessageResponse — app/schemas/coaching.py
- FirstMessageConflictResponse — app/schemas/coaching.py
- MessagesListResponse — app/schemas/coaching.py
- AthletePreferencesPatchIn — app/schemas/onboarding.py
- AthletePreferencesResponse — app/schemas/onboarding.py
- AthleteProfilePatchIn — app/schemas/onboarding.py
- AthleteProfileResponse — app/schemas/onboarding.py
- OnboardingPreferencesIn — app/schemas/onboarding.py
- OnboardingProfileIn — app/schemas/onboarding.py
- OnboardingRequest — app/schemas/onboarding.py
- OnboardingResponse — app/schemas/onboarding.py
- OnboardingStatusResponse — app/schemas/onboarding.py
- OnboardingTrainingGoalIn — app/schemas/onboarding.py
- TwinStateHistoryResponse — app/schemas/onboarding.py
- TwinStateResponse — app/schemas/onboarding.py
- WeeklyScheduleDayIn — app/schemas/onboarding.py
- WeeklyScheduleDayOut — app/schemas/onboarding.py
- WeeklyScheduleDayPatchIn — app/schemas/onboarding.py
- CheckpointResponse — app/schemas/plan.py
- PhaseDescriptorResponse — app/schemas/plan.py
- PlannedSessionResponse — app/schemas/plan.py
- TrainingPlanResponse — app/schemas/plan.py
- UpcomingSessionsResponse — app/schemas/plan.py
- GenerateWorkoutResponse — app/schemas/workout.py
- GeneratedWorkoutResponse — app/schemas/workout.py
- TargetSetResponse — app/schemas/workout.py
- TodayResponse — app/schemas/workout.py
- WorkoutAlreadyGeneratedConflictResponse — app/schemas/workout.py
- WorkoutStepResponse — app/schemas/workout.py
- WorkoutTargetPrimaryResponse — app/schemas/workout.py
- WorkoutTargetResponse — app/schemas/workout.py

### Registrations

- app/models/__init__.py
- Imports: Activity, ActivitySource, Athlete, AthleteAuth, AthleteFitness, AthletePhysiology, AthletePreferences, AthleteProfile, AuthProvider, Checkpoint, CheckpointStatus, CheckpointType, CoachingMessage, DataTier, EventPublicationStatus, GeneratedWorkout, GenerationEvent, GoalEventType, GoalType, GpsSource, HrSource, InjurySeverity, MeasurementSource, MessageType, ObjectiveCategory, PhaseLabel, PhysiologicalIntent, PlannedSession, PlannedSessionStatus, PowerSource, PrimaryTrainingPlatform, RecoveryModifierLevel, RefreshToken, RegenerationTask, SecondaryEvent, SecondaryEventPriority, SessionPriority, SessionPurpose, SessionSlot, SessionType, Sex, SignalType, SportBackground, StepType, SystemEvent, SystemEventOutbox, TrainingGoal, TrainingGoalStatus, TrainingPlan, TrainingPlanStatus, TrainingTimeOfDay, TwinConfidenceLevel, TwinState, TwinTrigger, WeeklyPlan, WeeklyPlanStatus, WeeklySession, WellnessTrend, WorkoutStep, infer_data_tier

- app/schemas/__init__.py
- Imports: AthletePreferencesPatchIn, AthletePreferencesResponse, AthleteProfilePatchIn, AthleteProfileResponse, AthleteResponse, AuthResponse, CheckpointResponse, CoachingMessageResponse, FirstMessageConflictResponse, GenerateWorkoutResponse, GeneratedWorkoutResponse, LoginRequest, MessagesListResponse, OnboardingPreferencesIn, OnboardingProfileIn, OnboardingRequest, OnboardingResponse, OnboardingStatusResponse, OnboardingTrainingGoalIn, PhaseDescriptorResponse, PlannedSessionResponse, RefreshRequest, RefreshResponse, RegisterProfileIn, RegisterRequest, TargetSetResponse, TodayResponse, TokenPairResponse, TrainingPlanResponse, TwinStateHistoryResponse, TwinStateResponse, UpcomingSessionsResponse, WeeklyScheduleDayIn, WeeklyScheduleDayOut, WeeklyScheduleDayPatchIn, WorkoutAlreadyGeneratedConflictResponse, WorkoutStepResponse, WorkoutTargetPrimaryResponse, WorkoutTargetResponse

- app/repositories/__init__.py
- Imports: AthleteAuthRepository, AthleteFitnessRepository, AthletePhysiologyRepository, AthletePreferencesRepository, AthleteProfileRepository, AthleteRepository, CheckpointRepository, CoachingMessageRepository, GeneratedWorkoutRepository, GenerationEventRepository, PlannedSessionRepository, RefreshTokenRepository, SystemEventOutboxRepository, SystemEventRepository, TrainingGoalRepository, TrainingPlanRepository, TwinStateRepository, WeeklyPlanRepository, WeeklySessionRepository, WorkoutStepRepository

- app/services/__init__.py
- Imports: ActivityIngestionError, ActivityIngestionResult, ActivityIngestionService, AthleteNotFoundError, AthleteNotFoundForIngestionError, AthleteTwinContext, AuthError, AuthResult, AuthService, BanisterUpdateResult, CalibrationEligibilityService, ComplianceError, ComplianceFindings, ComplianceService, ComputedObservations, ContextBudgetService, CrossAthleteAccessError, DATA_TIER_TARGET_TYPE, DuplicateEmailError, EventPublisher, FirstMessageAgent, FirstMessageAlreadyExistsError, FitParseEmptyError, FitParseError, FitParserService, InvalidCredentialsError, InvalidGoalTypeError, InvalidRefreshTokenError, IssuedTokens, LLMServiceUnavailableError, LoadComputationError, LoadComputationInputs, LoadComputationService, LoadScores, MissingAthleteFitnessError, MissingHeartRateError, MissingTrainingGoalError, ObjectStorageClient, ObjectStorageConflictError, ObjectStorageError, ObjectStorageFailureError, ObjectStorageNotConfiguredError, ObjectStorageUploadError, OnboardingAlreadyCompleteError, OnboardingError, OnboardingIncompleteError, OnboardingResult, OnboardingService, OnboardingStatus, OutboxEvent, ParsedFitData, PlanGenerationError, PlanGenerationResult, PlanGenerationService, PlannedSessionNotFoundError, PreferencesSnapshot, ProfileSnapshot, PromptNotFoundError, PromptRegistry, RecalibrationResult, SESSION_INTENT_MAP, SessionDayAssignment, StoredFitObject, TrainingGoalConflictError, TrainingLengthGateError, TwinContextAssembler, TwinContextSummary, TwinRecalibrationError, TwinRecalibrationFailureError, TwinRecalibrationService, UnauthenticatedError, WorkoutAlreadyGeneratedError, WorkoutGenerationAgent, WorkoutGenerationContractError, WorkoutGenerationError, WorkoutLLMServiceUnavailableError, _BytesReader, _GoalInput, _PreferencesInput, _ProfileInput, estimate_max_hr_from_age, get_object_storage_client, get_step_physiological_intent, reset_object_storage_client

- app/api/__init__.py
- Imports: build_auth_service, build_onboarding_service, get_current_athlete_id, get_db, require_self

- app/api/v1/__init__.py
- Imports: APIRouter, activity_router, auth_router, coach_router, health_router, onboarding_router, plan_router, workout_router
- Includes: activity_router, auth_router, coach_router, health_router, onboarding_router, plan_router, workout_router

---

## Derived Signals

### Dependency Changes

requirements.txt
No changes detected

### Service Wiring

ActivityIngestionService
 ├── ActivityRepository
 ├── CalibrationEligibilityService
 ├── FitParserService
 ├── LoadComputationService
 ├── Optional[CalibrationEligibilityService]
 ├── Optional[EventPublisher]
 ├── Optional[FitParserService]
 ├── Optional[LoadComputationService]
 ├── Optional[ObjectStorageClient]
 ├── Optional[TwinRecalibrationService]
 ... +3 more

AuthService
 ├── AthleteAuthRepository
 ├── AthleteProfileRepository
 ├── AthleteRepository
 ├── RefreshTokenRepository
 ├── SystemEventOutboxRepository
 ├── SystemEventRepository
 └── TokenService

ContextBudgetService
 ├── 'AthletePreferencesRepository'
 ├── 'AthleteProfileRepository'
 ├── 'TrainingGoalRepository'
 ├── 'TrainingPlanRepository'
 ├── 'TwinStateRepository'
 └── Optional['PlannedSessionRepository']

EventPublisher
 ├── SystemEventOutboxRepository
 └── SystemEventRepository

FirstMessageAgent
 ├── 'TrainingGoalRepository'
 ├── 'TrainingPlanRepository'
 ├── 'TwinStateRepository'
 ├── CoachingMessageRepository
 ├── ContextBudgetService
 ├── GenerationEventRepository
 ├── Optional[EventPublisher]
 ├── PromptRegistry
 ├── SystemEventOutboxRepository
 └── SystemEventRepository

FirstMessageAlreadyExistsError
 └── uuid.UUID

ObjectStorageClient
 └── none

OnboardingService
 ├── AthleteFitnessRepository
 ├── AthletePhysiologyRepository
 ├── AthletePreferencesRepository
 ├── AthleteProfileRepository
 ├── AthleteRepository
 ├── Optional['PlanGenerationService']
 ├── Optional[EventPublisher]
 ├── SystemEventOutboxRepository
 ├── SystemEventRepository
 ├── TrainingGoalRepository
 ... +1 more

PlanGenerationService
 ├── AthletePreferencesRepository
 ├── AthleteRepository
 ├── CheckpointRepository
 ├── Optional[EventPublisher]
 ├── SystemEventOutboxRepository
 ├── SystemEventRepository
 ├── TrainingGoalRepository
 ├── TrainingPlanRepository
 ├── TwinStateRepository
 ├── WeeklyPlanRepository
 ... +1 more

PlannedSessionNotFoundError
 └── uuid.UUID

TrainingLengthGateError
 └── none

TwinRecalibrationService
 ├── AthleteFitnessRepository
 ├── AthletePhysiologyRepository
 ├── TrainingGoalRepository
 └── TwinStateRepository

WorkoutAlreadyGeneratedError
 └── uuid.UUID

WorkoutGenerationAgent
 ├── ContextBudgetService
 ├── GeneratedWorkoutRepository
 ├── GenerationEventRepository
 ├── Optional[EventPublisher]
 ├── PlannedSessionRepository
 ├── PromptRegistry
 ├── SystemEventOutboxRepository
 ├── SystemEventRepository
 ├── TwinStateRepository
 └── WorkoutStepRepository

_BytesReader
 └── bytes

_GoalInput
 ├── Any
 ├── GoalType
 ├── Optional[date]
 ├── Optional[float]
 ├── Optional[int]
 └── Optional[str]

_PreferencesInput
 └── SportBackground

_ProfileInput
 ├── Optional[dict]
 └── Optional[float]

### Registration Status

api dependencies: partial
models: complete
repositories: partial
routers: complete
schemas: partial
services: complete

### Event Producers

- app/agents/post_workout_agent.py:380 PostWorkoutAgent.generate publish -> coaching_message_generated [uncommitted]
- app/services/activity_ingestion_service.py:363 ActivityIngestionService.ingest publish -> activity_ingested [uncommitted]
- app/services/activity_ingestion_service.py:445 ActivityIngestionService.ingest_async publish -> activity_ingested [uncommitted]
- app/services/auth_service.py:171 AuthService.register publish -> athlete_registered [after_commit]
- app/services/auth_service.py:275 AuthService.login publish -> athlete_logged_in [after_commit]
- app/services/auth_service.py:368 AuthService.rotate_refresh_token publish -> athlete_logged_in [after_commit]
- app/services/first_message_agent.py:303 FirstMessageAgent.generate publish -> coaching_message_generated [uncommitted]
- app/services/onboarding_service.py:484 OnboardingService.complete_onboarding publish -> onboarding_completed [after_commit]
- app/services/plan_generation_service.py:750 PlanGenerationService._persist_full_plan publish -> training_plan_generated [after_commit]
- app/services/workout_generation_agent.py:437 WorkoutGenerationAgent.generate publish -> workout_generated [uncommitted]

### Transaction Boundaries

Commits:
- app/api/v1/activity.py:233 post_upload_activity session.commit
- app/api/v1/activity.py:346 post_analyse_activity session.commit
- app/api/v1/coach.py:126 post_first_message session.commit
- app/api/v1/workout.py:174 get_today session.commit
- app/api/v1/workout.py:262 post_generate_workout session.commit
- app/services/auth_service.py:181 AuthService.register self.session.commit
- app/services/auth_service.py:286 AuthService.login self.session.commit
- app/services/auth_service.py:379 AuthService.rotate_refresh_token self.session.commit
- app/services/onboarding_service.py:515 OnboardingService.complete_onboarding self.session.commit
- app/services/onboarding_service.py:605 OnboardingService.update_profile self.session.commit
- app/services/onboarding_service.py:671 OnboardingService.update_preferences self.session.commit
- app/services/plan_generation_service.py:766 PlanGenerationService._persist_full_plan self.session.commit
- app/tasks/discard_refresh_token_ips.py:48 discard_refresh_token_ips session.commit
- app/worker/app.py:133 fit_ingest session.commit
- app/worker/app.py:189 recalibrate_twin session.commit

Flushes:
- app/repositories/activity_repository.py:62 ActivityRepository.add self.session.flush
- app/repositories/activity_repository.py:88 ActivityRepository.update_load_scores self.session.flush
- app/repositories/activity_repository.py:109 ActivityRepository.update_calibration_eligibility self.session.flush
- app/repositories/athlete_auth_repository.py:57 AthleteAuthRepository.add self.session.flush
- app/repositories/athlete_auth_repository.py:64 AthleteAuthRepository.touch_last_login self.session.flush
- app/repositories/athlete_fitness_repository.py:42 AthleteFitnessRepository.add self.session.flush
- app/repositories/athlete_physiology_repository.py:42 AthletePhysiologyRepository.add self.session.flush
- app/repositories/athlete_preferences_repository.py:33 AthletePreferencesRepository.add self.session.flush
- app/repositories/athlete_profile_repository.py:31 AthleteProfileRepository.add self.session.flush
- app/repositories/athlete_repository.py:45 AthleteRepository.add self.session.flush
- app/repositories/checkpoint_repository.py:41 CheckpointRepository.add_many self.session.flush
- app/repositories/coaching_message_repository.py:43 CoachingMessageRepository.insert self.session.flush
- app/repositories/generated_workout_repository.py:62 GeneratedWorkoutRepository.insert self.session.flush
- app/repositories/generation_event_repository.py:38 GenerationEventRepository.insert self.session.flush
- app/repositories/refresh_token_repository.py:42 RefreshTokenRepository.add self.session.flush
- app/repositories/system_event_outbox_repository.py:44 SystemEventOutboxRepository.add self.session.flush
- app/repositories/system_event_outbox_repository.py:60 SystemEventOutboxRepository.mark_published self.session.flush
- app/repositories/system_event_repository.py:57 SystemEventRepository.add self.session.flush
- app/repositories/training_goal_repository.py:55 TrainingGoalRepository.add self.session.flush
- app/repositories/training_plan_repository.py:105 TrainingPlanRepository.add self.session.flush
- app/repositories/training_plan_repository.py:121 TrainingPlanRepository.supersede self.session.flush
- app/repositories/twin_state_repository.py:90 TwinStateRepository.insert self.session.flush
- app/repositories/weekly_plan_repository.py:44 WeeklyPlanRepository.add_many self.session.flush
- app/repositories/weekly_plan_repository.py:102 WeeklySessionRepository.add_many self.session.flush
- app/repositories/workout_step_repository.py:64 WorkoutStepRepository.insert_many self.session.flush
- app/services/activity_ingestion_service.py:549 ActivityIngestionService._run_ingestion_pipeline self.session.flush
- app/services/auth_service.py:362 AuthService.rotate_refresh_token self.session.flush
- app/services/onboarding_service.py:351 OnboardingService.complete_onboarding self.session.flush
- app/services/onboarding_service.py:481 OnboardingService.complete_onboarding self.session.flush
- app/services/onboarding_service.py:604 OnboardingService.update_profile self.session.flush
- app/services/onboarding_service.py:670 OnboardingService.update_preferences self.session.flush
- app/services/plan_generation_service.py:651 PlanGenerationService._persist_full_plan self.session.flush
- app/services/plan_generation_service.py:704 PlanGenerationService._persist_full_plan self.session.flush
- app/services/plan_generation_service.py:745 PlanGenerationService._persist_full_plan self.session.flush

### Observed Runtime Structure

AsyncSession imports:
- app/api/deps.py
- app/api/v1/activity.py
- app/api/v1/coach.py
- app/api/v1/health.py
- app/api/v1/plan.py
- app/api/v1/workout.py
- app/db/session.py
- app/repositories/activity_repository.py
- app/repositories/athlete_auth_repository.py
- app/repositories/athlete_fitness_repository.py
- app/repositories/athlete_physiology_repository.py
- app/repositories/athlete_preferences_repository.py
- app/repositories/athlete_profile_repository.py
- app/repositories/athlete_repository.py
- app/repositories/checkpoint_repository.py
- app/repositories/coaching_message_repository.py
- app/repositories/generated_workout_repository.py
- app/repositories/generation_event_repository.py
- app/repositories/planned_session_repository.py
- app/repositories/refresh_token_repository.py
- app/repositories/system_event_outbox_repository.py
- app/repositories/system_event_repository.py
- app/repositories/training_goal_repository.py
- app/repositories/training_plan_repository.py
- app/repositories/twin_state_repository.py
- app/repositories/weekly_plan_repository.py
- app/repositories/workout_step_repository.py
- app/services/activity_ingestion_service.py
- app/services/auth_service.py
- app/services/health_service.py
- app/services/onboarding_service.py
- app/services/plan_generation_service.py
- app/services/twin_recalibration_service.py

Repository dependencies:
- app/agents/post_workout_agent.py: SystemEventOutboxRepository
- app/agents/post_workout_agent.py: SystemEventRepository
- app/api/v1/activity.py: ActivityRepository
- app/api/v1/activity.py: CoachingMessageRepository
- app/api/v1/activity.py: GenerationEventRepository
- app/api/v1/activity.py: PlannedSessionRepository
- app/api/v1/activity.py: TwinStateRepository
- app/api/v1/coach.py: AthletePreferencesRepository
- app/api/v1/coach.py: AthleteProfileRepository
- app/api/v1/coach.py: CoachingMessageRepository
- app/api/v1/coach.py: GenerationEventRepository
- app/api/v1/coach.py: TrainingGoalRepository
- app/api/v1/coach.py: TrainingPlanRepository
- app/api/v1/coach.py: TwinStateRepository
- app/api/v1/plan.py: TrainingPlanRepository
- app/api/v1/workout.py: AthletePreferencesRepository
- app/api/v1/workout.py: AthleteProfileRepository
- app/api/v1/workout.py: GeneratedWorkoutRepository
- app/api/v1/workout.py: GenerationEventRepository
- app/api/v1/workout.py: PlannedSessionRepository
- app/api/v1/workout.py: TrainingGoalRepository
- app/api/v1/workout.py: TrainingPlanRepository
- app/api/v1/workout.py: TwinStateRepository
- app/api/v1/workout.py: WorkoutStepRepository
- app/services/activity_ingestion_service.py: ActivityRepository
- app/services/activity_ingestion_service.py: SystemEventOutboxRepository
- app/services/activity_ingestion_service.py: SystemEventRepository
- app/services/auth_service.py: AthleteAuthRepository
- app/services/auth_service.py: AthleteProfileRepository
- app/services/auth_service.py: AthleteRepository
- app/services/auth_service.py: RefreshTokenRepository
- app/services/auth_service.py: SystemEventOutboxRepository
- app/services/auth_service.py: SystemEventRepository
- app/services/first_message_agent.py: SystemEventOutboxRepository
- app/services/first_message_agent.py: SystemEventRepository
- app/services/onboarding_service.py: AthleteFitnessRepository
- app/services/onboarding_service.py: AthletePhysiologyRepository
- app/services/onboarding_service.py: AthletePreferencesRepository
- app/services/onboarding_service.py: AthleteProfileRepository
- app/services/onboarding_service.py: AthleteRepository
- app/services/onboarding_service.py: SystemEventOutboxRepository
- app/services/onboarding_service.py: SystemEventRepository
- app/services/onboarding_service.py: TrainingGoalRepository
- app/services/onboarding_service.py: TwinStateRepository
- app/services/plan_generation_service.py: AthletePreferencesRepository
- app/services/plan_generation_service.py: AthleteRepository
- app/services/plan_generation_service.py: CheckpointRepository
- app/services/plan_generation_service.py: SystemEventOutboxRepository
- app/services/plan_generation_service.py: SystemEventRepository
- app/services/plan_generation_service.py: TrainingGoalRepository
- app/services/plan_generation_service.py: TrainingPlanRepository
- app/services/plan_generation_service.py: TwinStateRepository
- app/services/plan_generation_service.py: WeeklyPlanRepository
- app/services/plan_generation_service.py: WeeklySessionRepository
- app/services/twin_recalibration_service.py: AthleteFitnessRepository
- app/services/twin_recalibration_service.py: AthletePhysiologyRepository
- app/services/twin_recalibration_service.py: TrainingGoalRepository
- app/services/twin_recalibration_service.py: TwinStateRepository
- app/services/workout_generation_agent.py: SystemEventOutboxRepository
- app/services/workout_generation_agent.py: SystemEventRepository
- app/tasks/discard_refresh_token_ips.py: RefreshTokenRepository
- app/worker/app.py: ActivityRepository

### Execution Readiness

Current Revision:
d1579f4430e7 (head)

Migration Pending:
yes

Missing Exports:
- app/api/__init__.py: Missing [build_onboarding_service_with_plan, build_plan_service]
- app/repositories/__init__.py: Missing [ActivityRepository]
- app/schemas/__init__.py: Missing [ActivityListResponse, ActivityNotFoundResponse, ActivityResponse, ActivityUploadResponse, CoachingMessageSummary, FitParseErrorResponse, PostWorkoutAnalysisResponse]

### Snapshot Reliability

Overall Confidence: HIGH

| Section | Confidence | Coverage | Limitations |
|---------|-----------|----------|-------------|
| Models | HIGH | All .py files in app/models | — |
| Enums | HIGH | All .py files in app/models | — |
| Schemas | HIGH | All .py files in app/schemas | — |
| Repositories | HIGH | All .py files in app/repositories | — |
| Services | MEDIUM | Constructor + instantiation scanning | Does not detect injected dependencies |
| Routes | MEDIUM | Static APIRouter decorators only | Dynamic routers not detected |
| Events | MEDIUM | AST publish detection | Same-function tracking only |
| Transaction Boundaries | MEDIUM | AST commit/flush detection | Same-function tracking only |
| Registrations | HIGH | __init__.py import analysis | Does not verify runtime usage |
| Migrations | HIGH | Migration file parsing | Does not verify database state |
| Dependency Drift | HIGH | requirements.txt diff | Does not check transitive dependencies |
