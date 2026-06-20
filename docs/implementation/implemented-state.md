# implemented-state

## Change Set

Base Commit:
691a611

Current Commit:
77ee6c8

Files Added:
- alembic/versions/8265efd46112_phase_1_1_p3_single_primary_auth_.py
- alembic/versions/fd373abd4b9e_phase_1_1_email_password_auth.py
- app/api/deps.py
- app/api/v1/__init__.py
- app/api/v1/auth.py
- app/core/logging_utils.py
- app/core/security/__init__.py
- app/core/security/password_hasher.py
- app/core/security/token_service.py
- app/models/athlete.py
- app/models/athlete_auth.py
- app/models/athlete_profile.py
- app/models/enums.py
- app/models/refresh_token.py
- app/models/system_event.py
- app/repositories/athlete_auth_repository.py
- app/repositories/athlete_profile_repository.py
- app/repositories/athlete_repository.py
- app/repositories/refresh_token_repository.py
- app/repositories/system_event_outbox_repository.py
- app/repositories/system_event_repository.py
- app/schemas/auth.py
- app/services/auth_errors.py
- app/services/auth_results.py
- app/services/auth_service.py
- app/services/event_publisher.py
- app/tasks/discard_refresh_token_ips.py
- app/tasks/discard_refresh_token_ips_cli.py
- app/utils/__init__.py
- app/utils/ip_utils.py
- reports/phase-1-1-p1-p2-p3-email-password-auth_devops.md
- reports/test_history/latest.md
- tests/README.md
- tests/__init__.py
- tests/api/test_auth_endpoints.py
- tests/behaviour/test_auth_user_journey.py
- tests/integration/test_athlete_auth_primary_enforcement.py
- tests/integration/test_athlete_repositories.py
- tests/integration/test_auth_service.py
- tests/integration/test_discard_refresh_token_ips.py
- tests/integration/test_refresh_token_repository.py
- tests/payloads.py
- tests/test_manifest.yaml
- tests/unit/test_ip_utils.py
- tests/unit/test_logging_utils.py
- tests/unit/test_password_hasher.py
- tests/unit/test_token_service.py

Files Modified:
- .env.test
- app/api/__init__.py
- app/api/v1/__init__.py
- app/api/v1/health.py
- app/core/__init__.py
- app/main.py
- app/models/__init__.py
- app/repositories/__init__.py
- app/schemas/__init__.py
- app/services/__init__.py
- pytest.ini
- requirements.txt
- tests/conftest.py

Files Deleted:
- none

Touched Areas:
- models
- repositories
- services
- api
- app
- migrations
- requirements
- root
- other

Generated:
2026-06-19T23:32:14.260446+00:00 UTC

Current DB Revision:
8265efd46112 (head)

Python Files Scanned:
45

---

## Verified Facts

### Domain Layer

Entities:
- Athlete (athletes) — app/models/athlete.py
- AthleteAuth (athlete_auths) — app/models/athlete_auth.py
- AthleteProfile (athlete_profiles) — app/models/athlete_profile.py
- RefreshToken (athlete_refresh_tokens) — app/models/refresh_token.py
- SystemEvent (system_events) — app/models/system_event.py
- SystemEventOutbox (system_event_outbox) — app/models/system_event.py

Enums:
- AuthProvider — app/models/enums.py
- EventPublicationStatus — app/models/system_event.py
- Sex — app/models/enums.py

### Persistence Layer

Repositories:
- AthleteAuthRepository -> AthleteAuth (app/repositories/athlete_auth_repository.py)
- AthleteProfileRepository -> AthleteProfile (app/repositories/athlete_profile_repository.py)
- AthleteRepository -> Athlete (app/repositories/athlete_repository.py)
- RefreshTokenRepository -> RefreshToken (app/repositories/refresh_token_repository.py)
- SystemEventOutboxRepository -> SystemEventOutbox (app/repositories/system_event_outbox_repository.py)
- SystemEventRepository -> SystemEvent (app/repositories/system_event_repository.py)

Migrations:
- 8265efd46112 (down: fd373abd4b9e) — alembic/versions/8265efd46112_phase_1_1_p3_single_primary_auth_.py
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
- Imports: Athlete, AthleteAuth, AthleteProfile, AuthProvider, EventPublicationStatus, RefreshToken, Sex, SystemEvent, SystemEventOutbox

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
Added:
- bcrypt>=4.0.0
- pyjwt>=2.8.0

Updated:
- none

Removed:
- none

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
8265efd46112 (head)

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
