# implemented-state

Commit:
9cee56c

## Change Set

Base Commit:
9cee56c

Current Commit:
9cee56c

Files Added:
- app/api/v1/plan.py
- app/repositories/checkpoint_repository.py
- app/repositories/training_plan_repository.py
- app/repositories/weekly_plan_repository.py
- app/schemas/plan.py
- app/services/plan_generation_errors.py
- app/services/plan_generation_service.py
- app/services/plan_generation_templates.py
- reports/phase-1-4_devops.md
- tests/api/test_plan_endpoints.py
- tests/behaviour/test_plan_user_journey.py
- tests/integration/test_plan_generation_service.py
- tests/integration/test_plan_repositories.py
- tests/test-manifest/phase-1-4.yaml
- tests/unit/test_plan_generation_errors.py
- tests/unit/test_plan_generation_templates.py

Files Modified:
- app/api/deps.py
- app/api/v1/__init__.py
- app/api/v1/onboarding.py
- app/models/enums.py
- app/models/system_event.py
- app/repositories/__init__.py
- app/schemas/__init__.py
- app/services/__init__.py
- app/services/onboarding_service.py
- reports/test_history/latest.md
- tests/test-manifest/index.yaml
- tests/test-manifest/phase-1-2b.yaml
- tests/unit/test_enum_values.py

Files Deleted:
- none

Touched Areas:
- models
- repositories
- services
- api
- app
- other

Generated:
2026-06-28T01:31:43.916120+00:00 UTC

Current DB Revision:
d1579f4430e7 (head)

Python Files Scanned:
79

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
- AthleteAuthRepository -> AthleteAuth (app/repositories/athlete_auth_repository.py)
- AthleteFitnessRepository -> AthleteFitness (app/repositories/athlete_fitness_repository.py)
- AthletePhysiologyRepository -> AthletePhysiology (app/repositories/athlete_physiology_repository.py)
- AthletePreferencesRepository -> AthletePreferences (app/repositories/athlete_preferences_repository.py)
- AthleteProfileRepository -> AthleteProfile (app/repositories/athlete_profile_repository.py)
- AthleteRepository -> Athlete (app/repositories/athlete_repository.py)
- CheckpointRepository -> Checkpoint (app/repositories/checkpoint_repository.py)
- RefreshTokenRepository -> RefreshToken (app/repositories/refresh_token_repository.py)
- SystemEventOutboxRepository -> SystemEventOutbox (app/repositories/system_event_outbox_repository.py)
- SystemEventRepository -> SystemEvent (app/repositories/system_event_repository.py)
- TrainingGoalRepository -> TrainingGoal (app/repositories/training_goal_repository.py)
- TrainingPlanRepository -> TrainingPlan (app/repositories/training_plan_repository.py)
- TwinStateRepository -> TwinState (app/repositories/twin_state_repository.py)
- WeeklyPlanRepository -> WeeklyPlan (app/repositories/weekly_plan_repository.py)
- WeeklySessionRepository -> WeeklySession (app/repositories/weekly_plan_repository.py)

Migrations:
- 1b9e9026db1e (down: e7ffc8764335) — alembic/versions/1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py
- 79dc97d4e433 (down: 1b9e9026db1e) — alembic/versions/79dc97d4e433_phase_1_2c_twin_fitness_coaching_.py
- 8265efd46112 (down: fd373abd4b9e) — alembic/versions/8265efd46112_phase_1_1_p3_single_primary_auth_.py
- d1579f4430e7 (down: 79dc97d4e433) — alembic/versions/d1579f4430e7_add_training_plans_twin_state_fk.py
- e7ffc8764335 (down: 8265efd46112) — alembic/versions/e7ffc8764335_phase_1_2a_profile_preferences_activity.py
- fd373abd4b9e (down: none) — alembic/versions/fd373abd4b9e_phase_1_1_email_password_auth.py

### Service Layer

Services:
- AuthService — app/services/auth_service.py
- EventPublisher — app/services/event_publisher.py
- OnboardingService — app/services/onboarding_service.py
- _GoalInput — app/services/onboarding_service.py
- _PreferencesInput — app/services/onboarding_service.py
- _ProfileInput — app/services/onboarding_service.py
- TrainingLengthGateError — app/services/plan_generation_errors.py
- PlanGenerationService — app/services/plan_generation_service.py

### API Surface

Public API:
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
- GET /api/v1/athletes/{athlete_id}/twin (app/api/v1/onboarding.py:317 get_twin_state, router=onboarding_router)
- GET /api/v1/athletes/{athlete_id}/twin/history (app/api/v1/onboarding.py:339 get_twin_history, router=onboarding_router)
- POST /api/v1/auth/login (app/api/v1/auth.py:116 login, router=auth_router)
- POST /api/v1/auth/refresh (app/api/v1/auth.py:137 refresh, router=auth_router)
- POST /api/v1/auth/register (app/api/v1/auth.py:91 register, router=auth_router)
- GET /api/v1/health/live (app/api/v1/health.py:11 live, router=health_router)
- GET /api/v1/health/ready (app/api/v1/health.py:19 ready, router=health_router)

### Contracts

- AthleteResponse — app/schemas/auth.py
- AuthResponse — app/schemas/auth.py
- LoginRequest — app/schemas/auth.py
- RefreshRequest — app/schemas/auth.py
- RefreshResponse — app/schemas/auth.py
- RegisterProfileIn — app/schemas/auth.py
- RegisterRequest — app/schemas/auth.py
- TokenPairResponse — app/schemas/auth.py
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

### Registrations

- app/models/__init__.py
- Imports: Activity, ActivitySource, Athlete, AthleteAuth, AthleteFitness, AthletePhysiology, AthletePreferences, AthleteProfile, AuthProvider, Checkpoint, CheckpointStatus, CheckpointType, CoachingMessage, DataTier, EventPublicationStatus, GeneratedWorkout, GenerationEvent, GoalEventType, GoalType, GpsSource, HrSource, InjurySeverity, MeasurementSource, MessageType, ObjectiveCategory, PhaseLabel, PhysiologicalIntent, PlannedSession, PlannedSessionStatus, PowerSource, PrimaryTrainingPlatform, RecoveryModifierLevel, RefreshToken, RegenerationTask, SecondaryEvent, SecondaryEventPriority, SessionPriority, SessionPurpose, SessionSlot, SessionType, Sex, SignalType, SportBackground, StepType, SystemEvent, SystemEventOutbox, TrainingGoal, TrainingGoalStatus, TrainingPlan, TrainingPlanStatus, TrainingTimeOfDay, TwinConfidenceLevel, TwinState, TwinTrigger, WeeklyPlan, WeeklyPlanStatus, WeeklySession, WellnessTrend, WorkoutStep, infer_data_tier

- app/schemas/__init__.py
- Imports: AthletePreferencesPatchIn, AthletePreferencesResponse, AthleteProfilePatchIn, AthleteProfileResponse, AthleteResponse, AuthResponse, CheckpointResponse, LoginRequest, OnboardingPreferencesIn, OnboardingProfileIn, OnboardingRequest, OnboardingResponse, OnboardingStatusResponse, OnboardingTrainingGoalIn, PhaseDescriptorResponse, PlannedSessionResponse, RefreshRequest, RefreshResponse, RegisterProfileIn, RegisterRequest, TokenPairResponse, TrainingPlanResponse, TwinStateHistoryResponse, TwinStateResponse, UpcomingSessionsResponse, WeeklyScheduleDayIn, WeeklyScheduleDayOut

- app/repositories/__init__.py
- Imports: AthleteAuthRepository, AthleteFitnessRepository, AthletePhysiologyRepository, AthletePreferencesRepository, AthleteProfileRepository, AthleteRepository, CheckpointRepository, RefreshTokenRepository, SystemEventOutboxRepository, SystemEventRepository, TrainingGoalRepository, TrainingPlanRepository, TwinStateRepository, WeeklyPlanRepository, WeeklySessionRepository

- app/services/__init__.py
- Imports: AthleteNotFoundError, AuthError, AuthResult, AuthService, CrossAthleteAccessError, DuplicateEmailError, EventPublisher, InvalidCredentialsError, InvalidGoalTypeError, InvalidRefreshTokenError, IssuedTokens, OnboardingAlreadyCompleteError, OnboardingError, OnboardingIncompleteError, OnboardingResult, OnboardingService, OnboardingStatus, OutboxEvent, PlanGenerationError, PlanGenerationResult, PlanGenerationService, PreferencesSnapshot, ProfileSnapshot, SessionDayAssignment, TrainingGoalConflictError, TrainingLengthGateError, UnauthenticatedError, _GoalInput, _PreferencesInput, _ProfileInput

- app/api/__init__.py
- Imports: build_auth_service, build_onboarding_service, get_current_athlete_id, get_db, require_self

- app/api/v1/__init__.py
- Imports: APIRouter, auth_router, health_router, onboarding_router, plan_router
- Includes: auth_router, health_router, onboarding_router, plan_router

---

## Derived Signals

### Dependency Changes

requirements.txt
No changes detected

### Service Wiring

AuthService
 ├── AthleteAuthRepository
 ├── AthleteProfileRepository
 ├── AthleteRepository
 ├── RefreshTokenRepository
 ├── SystemEventOutboxRepository
 ├── SystemEventRepository
 └── TokenService

EventPublisher
 ├── SystemEventOutboxRepository
 └── SystemEventRepository

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

TrainingLengthGateError
 └── none

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
repositories: complete
routers: complete
schemas: partial
services: complete

### Event Producers

- app/services/auth_service.py:170 AuthService.register publish -> athlete_registered [after_commit]
- app/services/auth_service.py:274 AuthService.login publish -> athlete_logged_in [after_commit]
- app/services/auth_service.py:367 AuthService.rotate_refresh_token publish -> athlete_logged_in [after_commit]
- app/services/onboarding_service.py:484 OnboardingService.complete_onboarding publish -> onboarding_completed [after_commit]
- app/services/plan_generation_service.py:750 PlanGenerationService._persist_full_plan publish -> training_plan_generated [after_commit]

### Transaction Boundaries

Commits:
- app/services/auth_service.py:180 AuthService.register self.session.commit
- app/services/auth_service.py:285 AuthService.login self.session.commit
- app/services/auth_service.py:378 AuthService.rotate_refresh_token self.session.commit
- app/services/onboarding_service.py:515 OnboardingService.complete_onboarding self.session.commit
- app/services/onboarding_service.py:605 OnboardingService.update_profile self.session.commit
- app/services/onboarding_service.py:671 OnboardingService.update_preferences self.session.commit
- app/services/plan_generation_service.py:766 PlanGenerationService._persist_full_plan self.session.commit
- app/tasks/discard_refresh_token_ips.py:48 discard_refresh_token_ips session.commit

Flushes:
- app/repositories/athlete_auth_repository.py:56 AthleteAuthRepository.add self.session.flush
- app/repositories/athlete_auth_repository.py:63 AthleteAuthRepository.touch_last_login self.session.flush
- app/repositories/athlete_fitness_repository.py:42 AthleteFitnessRepository.add self.session.flush
- app/repositories/athlete_physiology_repository.py:42 AthletePhysiologyRepository.add self.session.flush
- app/repositories/athlete_preferences_repository.py:33 AthletePreferencesRepository.add self.session.flush
- app/repositories/athlete_profile_repository.py:31 AthleteProfileRepository.add self.session.flush
- app/repositories/athlete_repository.py:44 AthleteRepository.add self.session.flush
- app/repositories/checkpoint_repository.py:41 CheckpointRepository.add_many self.session.flush
- app/repositories/refresh_token_repository.py:41 RefreshTokenRepository.add self.session.flush
- app/repositories/system_event_outbox_repository.py:44 SystemEventOutboxRepository.add self.session.flush
- app/repositories/system_event_outbox_repository.py:60 SystemEventOutboxRepository.mark_published self.session.flush
- app/repositories/system_event_repository.py:57 SystemEventRepository.add self.session.flush
- app/repositories/training_goal_repository.py:55 TrainingGoalRepository.add self.session.flush
- app/repositories/training_plan_repository.py:105 TrainingPlanRepository.add self.session.flush
- app/repositories/training_plan_repository.py:121 TrainingPlanRepository.supersede self.session.flush
- app/repositories/twin_state_repository.py:90 TwinStateRepository.insert self.session.flush
- app/repositories/weekly_plan_repository.py:44 WeeklyPlanRepository.add_many self.session.flush
- app/repositories/weekly_plan_repository.py:102 WeeklySessionRepository.add_many self.session.flush
- app/services/auth_service.py:361 AuthService.rotate_refresh_token self.session.flush
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
- app/api/v1/health.py
- app/api/v1/plan.py
- app/db/session.py
- app/repositories/athlete_auth_repository.py
- app/repositories/athlete_fitness_repository.py
- app/repositories/athlete_physiology_repository.py
- app/repositories/athlete_preferences_repository.py
- app/repositories/athlete_profile_repository.py
- app/repositories/athlete_repository.py
- app/repositories/checkpoint_repository.py
- app/repositories/refresh_token_repository.py
- app/repositories/system_event_outbox_repository.py
- app/repositories/system_event_repository.py
- app/repositories/training_goal_repository.py
- app/repositories/training_plan_repository.py
- app/repositories/twin_state_repository.py
- app/repositories/weekly_plan_repository.py
- app/services/auth_service.py
- app/services/health_service.py
- app/services/onboarding_service.py
- app/services/plan_generation_service.py

Repository dependencies:
- app/api/v1/plan.py: TrainingPlanRepository
- app/services/auth_service.py: AthleteAuthRepository
- app/services/auth_service.py: AthleteProfileRepository
- app/services/auth_service.py: AthleteRepository
- app/services/auth_service.py: RefreshTokenRepository
- app/services/auth_service.py: SystemEventOutboxRepository
- app/services/auth_service.py: SystemEventRepository
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
- app/tasks/discard_refresh_token_ips.py: RefreshTokenRepository

### Execution Readiness

Current Revision:
d1579f4430e7 (head)

Migration Pending:
yes

Missing Exports:
- app/api/__init__.py: Missing [build_onboarding_service_with_plan, build_plan_service]
- app/schemas/__init__.py: Missing [WeeklyScheduleDayPatchIn]

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
