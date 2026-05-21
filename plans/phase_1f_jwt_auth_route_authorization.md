# Phase 1f — JWT Authentication & Route Authorization

## Models

### 1. Add TokenType enum
- Objective: Add `TokenType` string enum for refresh token type field.
- File: `app/models/enums.py` [MODIFY]
- Actions:
  - Add `TokenType` string enum with single value: `refresh`.

### 2. Create RefreshToken model
- Objective: Stored refresh token supporting multi-device sessions with revocation.
- File: `app/models/refresh_token.py` [CREATE]
- Actions:
  - Create `RefreshToken` model inheriting from `Base`. Table name: `refresh_tokens`.
  - Columns:
    - `id`: UUID PK, `server_default=text("gen_random_uuid()")`.
    - `athlete_id`: UUID, `ForeignKey("athletes.id", ondelete="CASCADE")`, `nullable=False`, `index=True`.
    - `token_hash`: `String(128)`, `nullable=False`. SHA-256 hex digest of raw token.
    - `expires_at`: `DateTime(timezone=True)`, `nullable=False`.
    - `revoked_at`: `DateTime(timezone=True)`, `nullable=True`. Null means active.
    - `device_hint`: `String(200)`, `nullable=True`. Optional user-agent/device label.
    - `last_used_at`: `DateTime(timezone=True)`, `nullable=True`. Updated on successful refresh.
    - `created_at`: `DateTime(timezone=True)`, `server_default=func.now()`, `nullable=False`.
  - Relationship: `athlete: Mapped["Athlete"]`, `back_populates="refresh_tokens"`.
  - Table args:
    - `Index("ix_refresh_tokens_athlete_id", "athlete_id")`.
    - `Index("ix_refresh_tokens_token_hash", "token_hash", unique=True)`.
  - No partial unique constraint on `(athlete_id) WHERE revoked_at IS NULL` — multi-device model.

### 3. Wire refresh_tokens on Athlete
- Objective: Add `refresh_tokens` back-reference relationship on Athlete model.
- File: `app/models/athlete.py` [MODIFY]
- Actions:
  - In `TYPE_CHECKING` block, add `from app.models.refresh_token import RefreshToken`.
  - Add `refresh_tokens: Mapped[list["RefreshToken"]]` with `back_populates="athlete"`, `cascade="all, delete-orphan"`, `passive_deletes=True`.

### 4. Export new model and enum
- Objective: Register RefreshToken and TokenType in models package.
- File: `app/models/__init__.py` [MODIFY]
- Actions:
  - Add `from app.models.refresh_token import RefreshToken`.
  - Add `TokenType` to the `from app.models.enums import (...)` line.
  - Add `RefreshToken` and `TokenType` to `__all__` list.

---

## Schemas

### 5. Create auth schemas
- Objective: Request and response schemas for all auth endpoints.
- File: `app/schemas/auth.py` [CREATE]
- Actions:
  - Create `RegisterRequest(BaseModel)` with fields:
    - `email: EmailStr` with `@field_validator("email")` normalising to `.strip().lower()`.
    - `password: str = Field(min_length=12)`.
    - Optional profile fields: `first_name: Optional[str] = None`, `last_name: Optional[str] = None`, `date_of_birth: Optional[date] = None`, `gender: Optional[Gender] = None`, `unit_preference: Optional[UnitPreference] = UnitPreference.METRIC`.
  - Create `LoginRequest(BaseModel)` with `email: EmailStr` (same normalising validator), `password: str`, `device_hint: Optional[str] = None`.
  - Create `TokenResponse(BaseModel)` with `access_token: str`, `refresh_token: str`, `token_type: str = "bearer"`, `expires_in: int`, `athlete_id: uuid.UUID`.
  - Create `RefreshRequest(BaseModel)` with `refresh_token: str`.
  - Create `LogoutRequest(BaseModel)` with `refresh_token: str`.

### 6. Export auth schemas
- Objective: Register auth schemas in schemas package.
- File: `app/schemas/__init__.py` [MODIFY]
- Actions:
  - Add `from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, LogoutRequest`.
  - Add all five to `__all__` list.

---

## Core

### 7. Add JWT settings
- Objective: Add JWT configuration fields to Settings.
- File: `app/config.py` [MODIFY]
- Actions:
  - Add `JWT_SECRET_KEY: str = Field(..., env="JWT_SECRET_KEY")` — required, no default.
  - Add `JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")`.
  - Add `JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")`.
  - Add `JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")`.
  - Add `JWT_ISSUER: str = Field(default="pheidipp-api", env="JWT_ISSUER")`.

### 8. Create JWT utilities
- Objective: Stateless JWT encode/decode and token hash functions. No DB access.
- File: `app/core/jwt.py` [CREATE]
- Actions:
  - Import `jose.jwt`, `jose.JWTError`; `hashlib`, `secrets`, `uuid`, `datetime`, `timezone`, `timedelta` from stdlib; `settings` from `app.config`.
  - Define `create_access_token(athlete_id: uuid.UUID) -> str`:
    - Build payload with `sub` (str athlete_id), `type` ("access"), `jti` (uuid4), `iss` (settings.JWT_ISSUER), `iat` (now unix), `exp` (now + access expiry seconds).
    - Encode with `settings.JWT_SECRET_KEY` and `settings.JWT_ALGORITHM`. Return encoded string.
  - Define `create_refresh_token() -> tuple[str, str]`:
    - Generate `raw = secrets.token_urlsafe(64)`.
    - Hash with SHA-256: `hashlib.sha256(raw.encode()).hexdigest()`.
    - Return `(raw, token_hash)`. Raw to client, hash to DB.
  - Define `decode_access_token(token: str) -> uuid.UUID`:
    - Decode with `jose.jwt.decode`, verifying signature and expiry.
    - After decode, validate `sub`, `type`, `jti`, `iss`, `exp` are all present. If any missing, raise `JWTError`.
    - Validate `payload["type"] == "access"`.
    - Validate `payload["iss"] == settings.JWT_ISSUER`.
    - Parse `UUID(payload["sub"])`. On `ValueError`, raise `JWTError`.
    - Return the UUID. Raise `JWTError` on any failure.
  - Define `hash_token(raw: str) -> str`:
    - Return `hashlib.sha256(raw.encode()).hexdigest()`.

---

## Repositories

### 9. Create RefreshTokenRepository
- Objective: Refresh token data access. Narrow, specialised interface.
- File: `app/repositories/refresh_token_repository.py` [CREATE]
- Actions:
  - `__init__(self, session: AsyncSession)` — stores session. Does not extend `BaseRepository`.
  - `async create(self, athlete_id, token_hash, expires_at, device_hint=None) -> RefreshToken`:
    - Construct and add `RefreshToken` instance. `flush()` only — UoW owns commit. Return instance.
  - `async get_active_by_hash(self, token_hash: str) -> Optional[RefreshToken]`:
    - Select where `token_hash == token_hash` AND `revoked_at IS NULL` AND `expires_at > func.now()`.
    - Apply `.with_for_update()` for row-level lock. Return row or None.
  - `async revoke(self, token_id: uuid.UUID) -> None`:
    - Fetch by id. Set `revoked_at = datetime.now(timezone.utc)`. Flush.
  - `async touch(self, token_id: uuid.UUID) -> None`:
    - Set `last_used_at = datetime.now(timezone.utc)` on an active token.
  - `async revoke_all_for_athlete(self, athlete_id: uuid.UUID) -> None`:
    - Bulk update: set `revoked_at = now()` where `athlete_id = athlete_id` AND `revoked_at IS NULL`.
  - `async count_active_for_athlete(self, athlete_id: uuid.UUID) -> int`:
    - Count active tokens for an athlete.

### 10. Export RefreshTokenRepository
- Objective: Register repository in package.
- File: `app/repositories/__init__.py` [MODIFY]
- Actions:
  - Add `from app.repositories.refresh_token_repository import RefreshTokenRepository`.
  - Add `RefreshTokenRepository` to `__all__` list.

---

## Unit of Work

### 11. Register refresh_tokens repo in UoW
- Objective: Make RefreshTokenRepository available via UnitOfWork.
- File: `app/core/unit_of_work.py` [MODIFY]
- Actions:
  - Add `from app.repositories.refresh_token_repository import RefreshTokenRepository` to imports.
  - In `__aenter__`, add `"refresh_tokens": RefreshTokenRepository(self.session)` to `_repos` dict.

---

## Services

### 12. Create AuthService
- Objective: All authentication business logic. No constructor-injected repositories — all data access via `uow` argument.
- File: `app/services/auth_service.py` [CREATE]
- Actions:
  - Import `logging`; define `logger = logging.getLogger("pheidipp.auth")`.
  - Import `hashlib`, `uuid`, `datetime`, `timezone`, `timedelta`; `IntegrityError` from `sqlalchemy.exc`; `UnitOfWork`; `Athlete`, `AthleteProfile`, `AthleteStatus`; `hash_password`, `verify_password` from `app.core.security`; `create_access_token`, `create_refresh_token`, `hash_token` from `app.core.jwt`; settings; request/response schemas.
  - Define `AuthService` class with empty `__init__`.
  - `async register(self, data: RegisterRequest, uow: UnitOfWork) -> tuple[Athlete, TokenResponse]`:
    - Normalise email: `data.email.strip().lower()`.
    - Check `await uow.athletes.get_by_email(email)`. If found, log warning with SHA-256 truncated hash of email (16 hex chars) and raise `ValueError("Email already registered")`.
    - Wrap athlete creation in `try/except IntegrityError` — re-raise as `ValueError("Email already registered")` for concurrent race condition.
    - Create `Athlete` with email, hashed password, `status=AthleteStatus.ACTIVE`. Add to `uow.session`. Flush.
    - If any profile fields present, create and flush `AthleteProfile`.
    - Call `_issue_token_pair(athlete.id, device_hint=None, uow)`.
    - Log info with `athlete_id`. Return `(athlete, token_response)`.
  - `async login(self, data: LoginRequest, uow: UnitOfWork) -> TokenResponse`:
    - Normalise email. Fetch athlete by email. If not found, raise `ValueError("Invalid credentials")`.
    - Verify password. On failure, log warning with `athlete_id` and raise `ValueError("Invalid credentials")`. Same message as email-not-found.
    - If `athlete.status != AthleteStatus.ACTIVE`, raise `ValueError("Account is not active")`.
    - Call `_issue_token_pair(athlete.id, device_hint=data.device_hint, uow)`.
    - Log info. Return `TokenResponse`.
  - `async refresh(self, raw_refresh_token: str, uow: UnitOfWork) -> TokenResponse`:
    - Hash token. Fetch active by hash (uses `FOR UPDATE`). If None, log warning and raise `ValueError("Invalid or expired refresh token")`.
    - Revoke existing token. Issue new pair.
    - Log info. Return `TokenResponse`.
  - `async logout(self, raw_refresh_token: str, uow: UnitOfWork) -> None`:
    - Hash token. Fetch active by hash. If None, return silently (idempotent).
    - Revoke token. Log info.
  - `async _issue_token_pair(self, athlete_id: uuid.UUID, device_hint: Optional[str], uow: UnitOfWork) -> TokenResponse` (private):
    - Create access token, refresh token pair. Calculate `expires_at`. Create refresh token in DB.
    - Return `TokenResponse` with `expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60`.

### 13. Export AuthService
- Objective: Register service in package.
- File: `app/services/__init__.py` [MODIFY]
- Actions:
  - Add `from app.services.auth_service import AuthService`.
  - Add `AuthService` to `__all__` list.

---

## API Dependencies

### 14. Create auth dependencies
- Objective: FastAPI dependencies for token extraction and athlete-level ownership checks.
- File: `app/api/dependencies/auth.py` [CREATE]
- Actions:
  - Import `HTTPBearer`, `HTTPAuthorizationCredentials` from `fastapi.security`; `Depends`, `HTTPException` from `fastapi`; `decode_access_token` from `app.core.jwt`; `JWTError` from `jose`; `logging`, `Optional`, `uuid`.
  - Define `logger = logging.getLogger("pheidipp.auth")`.
  - Define `bearer_scheme = HTTPBearer(auto_error=False)`.
  - Define `async get_current_athlete_id(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> uuid.UUID`:
    - If `credentials is None`, log warning "auth.token.missing", raise `HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})`.
    - Call `decode_access_token(credentials.credentials)`. On `JWTError`, log warning "auth.token.invalid", raise `HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})`.
    - Return decoded athlete_id UUID.
  - Define `async require_self(athlete_id: uuid.UUID, current_athlete_id: uuid.UUID = Depends(get_current_athlete_id)) -> uuid.UUID`:
    - If `athlete_id != current_athlete_id`, log warning "auth.access.denied" with both IDs, raise `HTTPException(403, "Access denied")`.
    - Return `current_athlete_id`.

### 15. Add auth service factory
- Objective: Provide `AuthService` dependency factory.
- File: `app/api/dependencies/services.py` [MODIFY]
- Actions:
  - Add `from app.services.auth_service import AuthService`.
  - Add `def get_auth_service() -> AuthService:` — returns `AuthService()`. No constructor args, no `Depends(get_db)`.

### 16. Export new dependencies
- Objective: Register auth dependencies in package.
- File: `app/api/dependencies/__init__.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id, require_self`.
  - Add `get_auth_service` to the existing import from `services`.
  - Add `get_current_athlete_id, require_self, get_auth_service` to `__all__` list.

---

## API Routes

### 17. Create auth routes
- Objective: Unprotected auth endpoints. No business logic.
- File: `app/api/routes/auth.py` [CREATE]
- Actions:
  - `router = APIRouter(prefix="/auth", tags=["auth"])`.
  - `POST /register` (`response_model=TokenResponse`, `status_code=201`):
    - `async with UnitOfWork(db) as uow`, call `auth_service.register(payload, uow)`.
    - Catch `ValueError("Email already registered")` → `HTTPException(409)`.
    - Catch other `ValueError` → `HTTPException(422)`.
  - `POST /login` (`response_model=TokenResponse`):
    - `async with UnitOfWork(db) as uow`, call `auth_service.login(payload, uow)`.
    - Catch `ValueError` → `HTTPException(401, "Invalid email or password")`.
  - `POST /refresh` (`response_model=TokenResponse`):
    - `async with UnitOfWork(db) as uow`, call `auth_service.refresh(payload.refresh_token, uow)`.
    - Catch `ValueError` → `HTTPException(401, "Invalid or expired refresh token")`.
  - `POST /logout` (`status_code=204`):
    - `async with UnitOfWork(db) as uow`, call `auth_service.logout(payload.refresh_token, uow)`.
    - Returns nothing. Never raises 4xx — idempotent.

### 18. Protect athletes routes
- Objective: Add auth guards; remove bare athlete creation.
- File: `app/api/routes/athletes.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import require_self` to imports.
  - Add `_: UUID = Depends(require_self)` as first parameter to every route handler that has an `athlete_id` path parameter: `get_athlete`, `update_athlete`, `upsert_profile`, `get_profile`, `list_athlete_activities`, `list_athlete_wellness`, `list_athlete_fitness`, `list_athlete_physiology`, `get_effective_physiology`, `get_athlete_preferences`, `list_training_blocks`, `get_active_training_block`, `onboard_athlete`, `get_onboarding_status`.
  - Remove `create_athlete` handler and `POST /` decorator entirely.
  - Remove `AthleteCreate` from imports.

### 19. Protect activities routes
- Objective: Add auth guards to standalone activity routes.
- File: `app/api/routes/activities.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id` and `from uuid import UUID` imports.
  - `create_activity`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. Assert `payload.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `get_activity`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. After fetching activity, assert `activity.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `update_activity`: Same as `get_activity`.
  - `delete_activity`: Same as `get_activity`.

### 20. Protect wellness routes
- Objective: Add auth guards to standalone wellness routes.
- File: `app/api/routes/wellness.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id` and `from uuid import UUID` imports.
  - `create_wellness`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. Assert `payload.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `get_wellness`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. After fetching wellness, assert `wellness.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `update_wellness`: Same as `get_wellness`.
  - `delete_wellness`: Same as `get_wellness`.

### 21. Protect fitness routes
- Objective: Add auth guards to standalone fitness routes.
- File: `app/api/routes/fitness.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id` and `from uuid import UUID` imports.
  - `create_fitness`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. Assert `payload.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `get_fitness`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. After fetching fitness, assert `fitness.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `update_fitness`: Same as `get_fitness`.
  - `delete_fitness`: Same as `get_fitness`.

### 22. Protect physiology routes
- Objective: Add auth guards to standalone physiology routes.
- File: `app/api/routes/physiology.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id` and `from uuid import UUID` imports.
  - `create_physiology`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. Assert `payload.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `get_physiology`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. After fetching physiology, assert `physiology.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `update_physiology`: Same as `get_physiology`.
  - `delete_physiology`: Same as `get_physiology`.

### 23. Protect training blocks routes
- Objective: Add auth guards to standalone training block routes.
- File: `app/api/routes/training_blocks.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id` and `from uuid import UUID` imports.
  - `get_block`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. After fetching block, assert `block.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `update_block`: Same as `get_block`.

### 24. Protect athlete preferences routes
- Objective: Add auth guards to standalone preferences routes.
- File: `app/api/routes/athlete_preferences.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import get_current_athlete_id` and `from uuid import UUID` imports.
  - `get_preferences`: Add `current_athlete_id: UUID = Depends(get_current_athlete_id)`. After fetching preferences, assert `preferences.athlete_id == current_athlete_id`; raise `HTTPException(403)` on mismatch.
  - `update_preferences`: Same as `get_preferences`.

### 25. Protect twin state routes
- Objective: Add auth guards to twin routes (nested under `/{athlete_id}/`).
- File: `app/api/routes/twin_state.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import require_self`.
  - `get_current_twin_state`: Add `_: UUID = Depends(require_self)` as first parameter.
  - `get_twin_state_history`: Same.

### 26. Protect coach messages routes
- Objective: Add auth guards to coach message routes (nested under `/{athlete_id}/`).
- File: `app/api/routes/coach_messages.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import require_self`.
  - `list_coach_messages`: Add `_: UUID = Depends(require_self)` as first parameter.
  - `get_latest_coach_message`: Same.
  - `get_first_coach_message`: Same.

### 27. Protect training plans routes
- Objective: Add auth guards to training plan routes (nested under `/{athlete_id}/`).
- File: `app/api/routes/training_plans.py` [MODIFY]
- Actions:
  - Add `from app.api.dependencies.auth import require_self`.
  - `get_active_training_plan`: Add `_: UUID = Depends(require_self)` as first parameter.
  - `get_training_plan`: Add `_: UUID = Depends(require_self)` as first parameter. Remove the manual `athlete_id` ownership assertion at line `result.training_plan.athlete_id != athlete_id` — `require_self` handles it centrally.

### 28. Register auth router
- Objective: Add auth router to FastAPI app before all resource routers.
- File: `app/main.py` [MODIFY]
- Actions:
  - Add `from app.api.routes.auth import router as auth_router`.
  - Add `app.include_router(auth_router)` immediately after `app = FastAPI(...)` line and before the `health_router`.

---

## Requirements

### 29. Add JWT library
- Objective: Add `python-jose` with cryptography support.
- File: `requirements.txt` [MODIFY]
- Actions:
  - Add `python-jose[cryptography]>=3.3.0`.

---

## Migration

### 30. Create refresh_tokens table
- Objective: Alembic migration adding the `refresh_tokens` table and verifying email unique index on `athletes`.
- Actions:
  - Run `bash scripts/db-revision.sh "add_refresh_tokens_table"` to generate the migration skeleton.
  - `upgrade()`:
    - `op.create_table("refresh_tokens", ...)` with all columns matching the `RefreshToken` ORM model.
    - `op.create_index("ix_refresh_tokens_athlete_id", "refresh_tokens", ["athlete_id"])`.
    - `op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)`.
    - Verify `athletes.email` unique index exists. If absent, add `op.create_index("ix_athletes_email", "athletes", ["email"], unique=True)`.
  - `downgrade()`:
    - `op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")`.
    - `op.drop_index("ix_refresh_tokens_athlete_id", table_name="refresh_tokens")`.
    - `op.drop_table("refresh_tokens")`.
    - Do NOT drop `ix_athletes_email` (may have pre-existed).