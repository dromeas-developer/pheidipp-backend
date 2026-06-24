# implemented-state

Commit:
5967870

## Change Set

Base Commit:
5967870

Current Commit:
5967870

Files Added:
- alembic/versions/1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py
- app/models/checkpoint.py
- app/models/planned_session.py
- app/models/regeneration_task.py
- app/models/secondary_event.py
- app/models/training_goal.py
- app/models/training_plan.py
- app/models/weekly_plan.py
- reports/phase-1-2b_devops.md
- reports/phase-1-2b_validation.md
- tests/integration/test_checkpoint_schema.py
- tests/integration/test_migration_phase_1_2b.py
- tests/integration/test_planned_session_schema.py
- tests/integration/test_regeneration_task_schema.py
- tests/integration/test_secondary_event_schema.py
- tests/integration/test_training_goal_schema.py
- tests/integration/test_training_plan_schema.py
- tests/integration/test_weekly_plan_schema.py
- tests/test-manifest/index.yaml
- tests/test-manifest/phase-1-1.yaml
- tests/test-manifest/phase-1-2a.yaml
- tests/test-manifest/phase-1-2b.yaml
- tests/unit/test_checkpoint_columns.py
- tests/unit/test_planned_session_columns.py
- tests/unit/test_regeneration_task_columns.py
- tests/unit/test_secondary_event_columns.py
- tests/unit/test_training_goal_columns.py
- tests/unit/test_training_plan_columns.py
- tests/unit/test_weekly_plan_columns.py

Files Modified:
- app/models/__init__.py
- app/models/activity.py
- app/models/enums.py
- reports/test_history/latest.md
- tests/integration/test_activity_schema.py
- tests/integration/test_migration_phase_1_2a.py
- tests/unit/test_enum_values.py

Files Deleted:
- tests/test_manifest.yaml

Touched Areas:
- models
- migrations
- other

Generated:
2026-06-24T03:54:24.698402+00:00 UTC

Current DB Revision:
1b9e9026db1e (head)

Python Files Scanned:
54

---

## Verified Facts

### Domain Layer

Entities:
- Activity (activities) — app/models/activity.py
- Athlete (athletes) — app/models/athlete.py
- AthleteAuth (athlete_auths) — app/models/athlete_auth.py
- AthletePreferences (athlete_preferences) — app/models/athlete_preferences.py
- AthleteProfile (athlete_profiles) — app/models/athlete_profile.py
- Checkpoint (checkpoints) — app/models/checkpoint.py
- PlannedSession (planned_sessions) — app/models/planned_session.py
- RefreshToken (athlete_refresh_tokens) — app/models/refresh_token.py
- RegenerationTask (regeneration_tasks) — app/models/regeneration_task.py
- SecondaryEvent (secondary_events) — app/models/secondary_event.py
- SystemEvent (system_events) — app/models/system_event.py
- SystemEventOutbox (system_event_outbox) — app/models/system_event.py
- TrainingGoal (training_goals) — app/models/training_goal.py
- TrainingPlan (training_plans) — app/models/training_plan.py
- WeeklyPlan (weekly_plans) — app/models/weekly_plan.py
- WeeklySession (weekly_sessions) — app/models/weekly_plan.py

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
- ObjectiveCategory — app/models/enums.py
- PhaseLabel — app/models/enums.py
- PlannedSessionStatus — app/models/enums.py
- PowerSource — app/models/enums.py
- PrimaryTrainingPlatform — app/models/enums.py
- SecondaryEventPriority — app/models/enums.py
- SessionPriority — app/models/enums.py
- SessionSlot — app/models/enums.py
- SessionType — app/models/enums.py
- Sex — app/models/enums.py
- SportBackground — app/models/enums.py
- TrainingGoalStatus — app/models/enums.py
- TrainingPlanStatus — app/models/enums.py
- TrainingTimeOfDay — app/models/enums.py
- WeeklyPlanStatus — app/models/enums.py

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
- 8265efd46112 (down: fd373abd4b9e) — alembic/versions/8265efd46112_phase_1_1_p3_single_primary_auth_.py
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
- Imports: Activity, ActivitySource, Athlete, AthleteAuth, AthletePreferences, AthleteProfile, AuthProvider, Checkpoint, CheckpointStatus, CheckpointType, DataTier, EventPublicationStatus, GoalEventType, GoalType, GpsSource, HrSource, InjurySeverity, ObjectiveCategory, PhaseLabel, PlannedSession, PlannedSessionStatus, PowerSource, PrimaryTrainingPlatform, RefreshToken, RegenerationTask, SecondaryEvent, SecondaryEventPriority, SessionPriority, SessionSlot, SessionType, Sex, SportBackground, SystemEvent, SystemEventOutbox, TrainingGoal, TrainingGoalStatus, TrainingPlan, TrainingPlanStatus, TrainingTimeOfDay, WeeklyPlan, WeeklyPlanStatus, WeeklySession, infer_data_tier

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
1b9e9026db1e (head)

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
