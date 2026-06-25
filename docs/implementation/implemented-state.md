# implemented-state

Commit:
7d11c76

## Change Set

Base Commit:
7d11c76

Current Commit:
7d11c76

Files Added:
- alembic/versions/79dc97d4e433_phase_1_2c_twin_fitness_coaching_.py
- alembic/versions/d1579f4430e7_add_training_plans_twin_state_fk.py
- app/models/athlete_fitness.py
- app/models/athlete_physiology.py
- app/models/coaching_message.py
- app/models/generated_workout.py
- app/models/generation_event.py
- app/models/twin_state.py
- app/models/workout_step.py
- reports/Phase-1.2c-P1_validation.md
- reports/phase-1-2b-p1-plan-sessions_validation.md
- reports/phase-1-2b-p2-test-contract-alignment_validation.md
- reports/phase-1-2c-P1_devops.md
- tests/integration/test_athlete_fitness_schema.py
- tests/integration/test_athlete_physiology_schema.py
- tests/integration/test_coaching_message_schema.py
- tests/integration/test_generated_workout_schema.py
- tests/integration/test_generation_event_schema.py
- tests/integration/test_migration_phase_1_2c.py
- tests/integration/test_twin_state_schema.py
- tests/integration/test_workout_step_schema.py
- tests/test-manifest/phase-1-2c.yaml
- tests/unit/test_athlete_fitness_columns.py
- tests/unit/test_athlete_physiology_columns.py
- tests/unit/test_coaching_message_columns.py
- tests/unit/test_generated_workout_columns.py
- tests/unit/test_generation_event_columns.py
- tests/unit/test_twin_state_columns.py
- tests/unit/test_workout_step_columns.py

Files Modified:
- app/models/__init__.py
- app/models/enums.py
- app/models/training_plan.py
- reports/test_history/latest.md
- tests/README.md
- tests/conftest.py
- tests/integration/test_migration_phase_1_2b.py
- tests/integration/test_training_plan_schema.py
- tests/test-manifest/index.yaml
- tests/test-manifest/phase-1-2b.yaml
- tests/unit/test_enum_values.py
- tests/unit/test_training_plan_columns.py

Files Deleted:
- none

Touched Areas:
- models
- migrations
- other

Generated:
2026-06-25T02:43:19.116945+00:00 UTC

Current DB Revision:
d1579f4430e7 (head)

Python Files Scanned:
61

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
- AthleteProfileRepository -> AthleteProfile (app/repositories/athlete_profile_repository.py)
- AthleteRepository -> Athlete (app/repositories/athlete_repository.py)
- RefreshTokenRepository -> RefreshToken (app/repositories/refresh_token_repository.py)
- SystemEventOutboxRepository -> SystemEventOutbox (app/repositories/system_event_outbox_repository.py)
- SystemEventRepository -> SystemEvent (app/repositories/system_event_repository.py)

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

### API Surface

Public API:
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

### Registrations

- app/models/__init__.py
- Imports: Activity, ActivitySource, Athlete, AthleteAuth, AthleteFitness, AthletePhysiology, AthletePreferences, AthleteProfile, AuthProvider, Checkpoint, CheckpointStatus, CheckpointType, CoachingMessage, DataTier, EventPublicationStatus, GeneratedWorkout, GenerationEvent, GoalEventType, GoalType, GpsSource, HrSource, InjurySeverity, MeasurementSource, MessageType, ObjectiveCategory, PhaseLabel, PhysiologicalIntent, PlannedSession, PlannedSessionStatus, PowerSource, PrimaryTrainingPlatform, RecoveryModifierLevel, RefreshToken, RegenerationTask, SecondaryEvent, SecondaryEventPriority, SessionPriority, SessionPurpose, SessionSlot, SessionType, Sex, SignalType, SportBackground, StepType, SystemEvent, SystemEventOutbox, TrainingGoal, TrainingGoalStatus, TrainingPlan, TrainingPlanStatus, TrainingTimeOfDay, TwinConfidenceLevel, TwinState, TwinTrigger, WeeklyPlan, WeeklyPlanStatus, WeeklySession, WellnessTrend, WorkoutStep, infer_data_tier

- app/schemas/__init__.py
- Imports: AthleteResponse, AuthResponse, LoginRequest, RefreshRequest, RefreshResponse, RegisterProfileIn, RegisterRequest, TokenPairResponse

- app/repositories/__init__.py
- Imports: AthleteAuthRepository, AthleteProfileRepository, AthleteRepository, RefreshTokenRepository, SystemEventOutboxRepository, SystemEventRepository

- app/services/__init__.py
- Imports: AuthError, AuthResult, AuthService, CrossAthleteAccessError, DuplicateEmailError, EventPublisher, InvalidCredentialsError, InvalidRefreshTokenError, IssuedTokens, OutboxEvent, UnauthenticatedError

- app/api/__init__.py
- Imports: build_auth_service, get_current_athlete_id, get_db, require_self

- app/api/v1/__init__.py
- Imports: APIRouter, auth_router, health_router
- Includes: auth_router, health_router

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

### Registration Status

api dependencies: complete
models: complete
repositories: complete
routers: complete
schemas: complete
services: complete

### Event Producers

- app/services/auth_service.py:170 AuthService.register publish -> athlete_registered [after_commit]
- app/services/auth_service.py:274 AuthService.login publish -> athlete_logged_in [after_commit]
- app/services/auth_service.py:367 AuthService.rotate_refresh_token publish -> athlete_logged_in [after_commit]

### Transaction Boundaries

Commits:
- app/services/auth_service.py:180 AuthService.register self.session.commit
- app/services/auth_service.py:285 AuthService.login self.session.commit
- app/services/auth_service.py:378 AuthService.rotate_refresh_token self.session.commit
- app/tasks/discard_refresh_token_ips.py:48 discard_refresh_token_ips session.commit

Flushes:
- app/repositories/athlete_auth_repository.py:56 AthleteAuthRepository.add self.session.flush
- app/repositories/athlete_auth_repository.py:63 AthleteAuthRepository.touch_last_login self.session.flush
- app/repositories/athlete_profile_repository.py:31 AthleteProfileRepository.add self.session.flush
- app/repositories/athlete_repository.py:44 AthleteRepository.add self.session.flush
- app/repositories/refresh_token_repository.py:41 RefreshTokenRepository.add self.session.flush
- app/repositories/system_event_outbox_repository.py:44 SystemEventOutboxRepository.add self.session.flush
- app/repositories/system_event_outbox_repository.py:60 SystemEventOutboxRepository.mark_published self.session.flush
- app/repositories/system_event_repository.py:57 SystemEventRepository.add self.session.flush
- app/services/auth_service.py:361 AuthService.rotate_refresh_token self.session.flush

### Observed Runtime Structure

AsyncSession imports:
- app/api/deps.py
- app/api/v1/health.py
- app/db/session.py
- app/repositories/athlete_auth_repository.py
- app/repositories/athlete_profile_repository.py
- app/repositories/athlete_repository.py
- app/repositories/refresh_token_repository.py
- app/repositories/system_event_outbox_repository.py
- app/repositories/system_event_repository.py
- app/services/auth_service.py
- app/services/health_service.py

Repository dependencies:
- app/services/auth_service.py: AthleteAuthRepository
- app/services/auth_service.py: AthleteProfileRepository
- app/services/auth_service.py: AthleteRepository
- app/services/auth_service.py: RefreshTokenRepository
- app/services/auth_service.py: SystemEventOutboxRepository
- app/services/auth_service.py: SystemEventRepository
- app/tasks/discard_refresh_token_ips.py: RefreshTokenRepository

### Execution Readiness

Current Revision:
d1579f4430e7 (head)

Migration Pending:
yes

Missing Exports:
- none

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
