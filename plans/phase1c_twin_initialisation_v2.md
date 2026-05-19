# Phase 1c Implementation Plan: Simplified Twin Initialisation (Tier 3) — v2

> Generated from `plans/phase1c-draft-plan.md` with codebase alignment corrections.
> v2: Fixed `set_onboarding_complete_uow` to avoid internal `BaseRepository.update()` commit;
> added technical debt note on repository flush-vs-commit; clarified existing-vs-new service framing.

---

## Codebase Alignment Notes

The draft plan contained several assumptions that do not match the actual codebase.
These are corrected in the plan below:

| Draft Assumption | Actual Codebase | Resolution |
|---|---|---|
| `Gender` enum needs creation | Already exists with `MALE`, `FEMALE`, `NON_BINARY`, `PREFER_NOT_TO_SAY` | Use existing enum; `NON_BINARY` replaces draft's `OTHER` |
| `AthleteProfile.gender` needs adding | Already exists | Skip model change |
| `SportBackground`, `HrSource`, `PowerSource` need creation | Already exist | Only add `TwinTrigger`, `ConfidenceLevel`, `DataTier` |
| `AthleteProfileRepository` needs creation | Already exists with `get_by_athlete_id` | Use existing repository |
| `AthleteService` lacks `get_profile`, `set_onboarding_complete` | Both already exist | Add UoW-compatible overloads that accept `uow` parameter |
| `Base` in `app.models.base` | `Base` in `app.db.base` | Use correct import path |
| `async_session_maker` | `AsyncSessionLocal` in `app.db.session` | Use correct name |
| `OnboardingService` exists | Does not exist; logic is inline in route | Create new service, extract from route |
| Routers via `app/api/routes/__init__.py` | Routers registered directly in `app/main.py` | Add twin router to `app/main.py` |
| `BaseRepository.create()` is flush-only | Commits internally | UoW wrappers use `session.add()` + `session.flush()` directly |
| `BaseRepository.update()` is safe for UoW | Commits internally | UoW wrappers use direct attribute set + `flush()`, never `repo.update()` |

---

## Scope

### In Scope
- `UnitOfWork` abstraction for transaction management.
- `TwinState` model, schemas, repository, and service.
- `TwinInitialisationService` in `app/services/` (pure Python, no LLM).
- Atomic twin creation during onboarding via `UnitOfWork`.
- API endpoints:
  - `GET /athletes/{athlete_id}/twin` (current twin state).
  - `GET /athletes/{athlete_id}/twin/history` (all twin states for an athlete, **paginated**).
- Alembic migration for `TwinState` table.
- Updates to **existing** services: `AthletePreferencesService`, `TrainingBlockService`, `AthleteService` (UoW-compatible methods added — existing methods untouched).
- **New** service: `TwinInitialisationService` in `app/services/`.
- **New** service: `TwinStateService` in `app/services/`.
- **New** service: `OnboardingService` in `app/services/` (extracts orchestration from route handler).

### Out of Scope
- LLM integration (Phase 1d+).
- Pace estimates (`lt1_pace_estimate`, `lt2_pace_estimate`) — deferred to Phase 2.
- Dynamic threshold updates from real data — deferred to Phase 2.
- Three-dimensional load model — deferred to Phase 4.
- Refactoring `BaseRepository` to flush-only (see Technical Debt note below).
- Refactoring existing `goal_*` fields in `TrainingBlock` (track separately).

---

## Technical Debt: Repository Commit Semantics

`BaseRepository.create()` and `BaseRepository.update()` both call `session.commit()` internally.
This forces UoW-compatible wrappers in this phase to bypass repository persistence methods
and manipulate the session directly (`session.add()` + `session.flush()` for creates;
direct attribute set + `session.flush()` for updates).

**Long-term fix (tracked for pre-Phase 2):**
- Refactor `BaseRepository.create()` to `session.flush()` only.
- Refactor `BaseRepository.update()` to `session.flush()` only.
- Let `UnitOfWork.__aexit__` own the single `session.commit()`.
- Remove all UoW wrapper methods from services; services use repositories normally.
- This eliminates the parallel persistence paths introduced in Phase 1c.

**Phase 1c constraint:** We do NOT refactor `BaseRepository` now because every existing
service and route depends on its current commit semantics. Changing it would require
auditing and updating every caller. This is tracked as a dedicated refactoring task.

---

## Models

### 1. Add TwinTrigger, ConfidenceLevel, DataTier enums
- Objective: Add three new string enums required by TwinState model
- File: `app/models/enums.py` [MODIFY]
- Actions:
  - Add `TwinTrigger` string enum with values: `questionnaire`, `calibration`, `wellness_update`
  - Add `ConfidenceLevel` string enum with values: `low`, `medium`, `high`
  - Add `DataTier` string enum with values: `tier1`, `tier2`, `tier3`, `tier4`, `tier5`
  - Do NOT modify any existing enums (`Gender`, `SportBackground`, `HrSource`, `PowerSource` are already present)

### 2. Create TwinState model
- Objective: Append-only model storing digital twin state snapshots
- File: `app/models/twin_state.py` [CREATE]
- Actions:
  - Create `TwinState` class inheriting from `app.db.base.Base`
  - Table name: `twin_states`
  - Add column `id` (UUID, primary key, server default `gen_random_uuid()`)
  - Add column `athlete_id` (UUID, ForeignKey to `athletes.id` with `ondelete="CASCADE"`, nullable=False, indexed)
  - Add column `athlete_preferences_id` (UUID, ForeignKey to `athlete_preferences.id` with `ondelete="CASCADE"`, nullable=False)
  - Add column `trigger` (SAEnum of `TwinTrigger`, native_enum=False, length=30, nullable=False)
  - Add column `confidence_level` (SAEnum of `ConfidenceLevel`, native_enum=False, length=10, nullable=False, default=`ConfidenceLevel.LOW`)
  - Add column `data_tier` (SAEnum of `DataTier`, native_enum=False, length=10, nullable=False)
  - Add column `fitness_score` (Float, nullable=False)
  - Add column `fatigue_score` (Float, nullable=False, default=0.0)
  - Add column `max_hr_estimate` (Float, nullable=False)
  - Add column `lt1_hr_estimate` (Float, nullable=False)
  - Add column `lt2_hr_estimate` (Float, nullable=False)
  - Add column `lt1_pace_estimate` (Float, nullable=True)
  - Add column `lt2_pace_estimate` (Float, nullable=True)
  - Add column `structural_capacity_score` (Float, nullable=False)
  - Add column `fitness_time_constant` (Float, nullable=False, default=42.0)
  - Add column `fatigue_time_constant` (Float, nullable=False, default=7.0)
  - Add column `computation_summary` (Text, nullable=False)
  - Add column `computation_metadata` (JSONB, nullable=False)
  - Add column `created_at` (DateTime timezone=True, server_default=func.now(), nullable=False)
  - Add relationship `athlete` back-populating to `Athlete.twin_states`
  - Add relationship `preferences` back-populating to `AthletePreferences.twin_states`
  - Add `__table_args__` with CheckConstraints:
    - `fitness_score >= 0 AND fitness_score <= 100` named `ck_twin_states_fitness_score_range`
    - `max_hr_estimate >= 140 AND max_hr_estimate <= 220` named `ck_twin_states_max_hr_range`
    - `fatigue_score >= 0` named `ck_twin_states_fatigue_non_negative`
    - `structural_capacity_score >= 0 AND structural_capacity_score <= 1` named `ck_twin_states_structural_capacity_range`

### 3. Update Athlete model — add twin_states relationship
- Objective: Wire reverse relationship from Athlete to TwinState
- File: `app/models/athlete.py` [MODIFY]
- Actions:
  - Add `TwinState` to TYPE_CHECKING import block: `from app.models.twin_state import TwinState`
  - Add relationship: `twin_states: Mapped[list["TwinState"]]` with `back_populates="athlete"`, `cascade="all, delete-orphan"`, `order_by="TwinState.created_at.desc()"`

### 4. Update AthletePreferences model — add twin_states relationship
- Objective: Wire reverse relationship from AthletePreferences to TwinState
- File: `app/models/athlete_preferences.py` [MODIFY]
- Actions:
  - Add `TwinState` to TYPE_CHECKING import block
  - Add relationship: `twin_states: Mapped[list["TwinState"]]` with `back_populates="preferences"`

### 5. Update models __init__.py
- Objective: Export new model and enums
- File: `app/models/__init__.py` [MODIFY]
- Actions:
  - Add import: `from app.models.twin_state import TwinState`
  - Add imports from `app.models.enums`: `TwinTrigger`, `ConfidenceLevel`, `DataTier`
  - Add `TwinState`, `TwinTrigger`, `ConfidenceLevel`, `DataTier` to `__all__`

---

## Schemas

### 6. Create TwinState schemas
- Objective: Pydantic schemas for twin state CRUD
- File: `app/schemas/twin_state.py` [CREATE]
- Actions:
  - Create `TwinStateBase` (BaseModel) with `model_config = ConfigDict(from_attributes=True)` and fields:
    - `athlete_id: uuid.UUID`
    - `athlete_preferences_id: uuid.UUID`
    - `trigger: TwinTrigger`
    - `confidence_level: ConfidenceLevel` default `ConfidenceLevel.LOW`
    - `data_tier: DataTier`
    - `fitness_score: float` with `Field(ge=0, le=100)`
    - `fatigue_score: float` with `Field(ge=0, default=0.0)`
    - `max_hr_estimate: float`
    - `lt1_hr_estimate: float`
    - `lt2_hr_estimate: float`
    - `lt1_pace_estimate: Optional[float]` default None
    - `lt2_pace_estimate: Optional[float]` default None
    - `structural_capacity_score: float` with `Field(ge=0, le=1)`
    - `fitness_time_constant: float` default 42.0
    - `fatigue_time_constant: float` default 7.0
    - `computation_summary: str`
    - `computation_metadata: dict`
  - Create `TwinStateCreate(TwinStateBase)` — inherits all fields, no additions
  - Create `TwinStateResponse(TwinStateBase)` — adds `id: uuid.UUID` and `created_at: datetime`

### 7. Update OnboardingResponse and OnboardingStatusResponse — twin_state type
- Objective: Replace `Optional[dict]` stub with `Optional[TwinStateResponse]`
- File: `app/schemas/onboarding.py` [MODIFY]
- Actions:
  - Add import: `from app.schemas.twin_state import TwinStateResponse`
  - In `OnboardingResponse`: change `twin_state` field type from `Optional[dict]` to `Optional[TwinStateResponse]`
  - In `OnboardingStatusResponse`: change `twin_state` field type from `Optional[dict]` to `Optional[TwinStateResponse]`

### 8. Update schemas __init__.py
- Objective: Export new twin state schemas
- File: `app/schemas/__init__.py` [MODIFY]
- Actions:
  - Add import block for `TwinStateBase`, `TwinStateCreate`, `TwinStateResponse` from `app.schemas.twin_state`
  - Add all three to `__all__`

---

## Core

### 9. Create UnitOfWork
- Objective: Centralized transaction management with repository access
- File: `app/core/unit_of_work.py` [CREATE]
- Actions:
  - Create `UnitOfWork` class with:
    - `__init__(self, session: AsyncSession)` — stores session, initializes empty `_repos` dict
    - `async __aenter__(self)` — calls `await self.session.begin()`, then lazily imports and instantiates all repositories: `AthleteRepository`, `AthletePreferencesRepository`, `TrainingBlockRepository`, `TwinStateRepository`, `AthleteProfileRepository`, each constructed with `self.session`. Stores them in `_repos` dict keyed by short name: `athletes`, `preferences`, `blocks`, `twin_states`, `profiles`. Returns `self`.
    - `async __aexit__(self, exc_type, exc_val, exc_tb)` — if exception, calls `await self.session.rollback()`; otherwise `await self.session.commit()`
    - `__getattr__(self, name)` — if `_repos` is empty, raises `RuntimeError` instructing to use `async with`; if `name` in `_repos`, returns that repo; otherwise raises `AttributeError` listing available keys

---

## Repositories

### 10. Create TwinStateRepository
- Objective: Repository for append-only TwinState queries
- File: `app/repositories/twin_state_repository.py` [CREATE]
- Actions:
  - Create `TwinStateRepository` class with:
    - `__init__(self, session: AsyncSession)` — stores session and sets `self.model = TwinState`
    - `async create(self, data: TwinStateCreate) -> TwinState` — constructs `TwinState(**data.model_dump())`, calls `self.session.add(db_obj)`, `await self.session.flush()`, returns `db_obj`. Note: flush-only, no commit (UoW owns the transaction).
    - `async get_by_athlete_id(self, athlete_id: uuid.UUID) -> Optional[TwinState]` — selects by `athlete_id`, orders by `created_at DESC`, limits 1, returns scalar or None
    - `async get_history_by_athlete_id(self, athlete_id: uuid.UUID, limit: int = 100, offset: int = 0) -> tuple[list[TwinState], int]` — runs count query for total, then select with limit/offset ordered by `created_at DESC`, returns tuple of (items list, total count)
    - `async count_by_athlete_id(self, athlete_id: uuid.UUID) -> int` — returns count of twin states for athlete

### 11. Update repositories __init__.py
- Objective: Export TwinStateRepository
- File: `app/repositories/__init__.py` [MODIFY]
- Actions:
  - Add import: `from app.repositories.twin_state_repository import TwinStateRepository`
  - Add `TwinStateRepository` to `__all__`

---

## Services

### 12. Add UoW-compatible wrapper to AthletePreferencesService (existing service)
- Objective: Add method that creates preferences within a UoW-managed transaction (flush, not commit). Existing methods are untouched.
- File: `app/services/athlete_preferences_service.py` [MODIFY]
- Actions:
  - Add import: `from app.core.unit_of_work import UnitOfWork`
  - Add import: `from app.models.athlete_preferences import AthletePreferences`
  - Add method `async create_for_athlete_uow(self, athlete_id: uuid.UUID, data: AthletePreferencesCreate, uow: UnitOfWork) -> AthletePreferences`:
    - Builds payload dict from `data.model_dump(exclude_unset=True)`, adds `athlete_id`
    - Constructs `AthletePreferences(**payload)`
    - Calls `uow.preferences.session.add(obj)` then `await uow.preferences.session.flush()`
    - Returns the ORM object
    - Does NOT call `self.repo` — uses UoW session directly (see Technical Debt note)

### 13. Add UoW-compatible wrapper to TrainingBlockService (existing service)
- Objective: Add method that creates training block within a UoW-managed transaction, preserving the 409-duplicate business rule. Existing methods are untouched.
- File: `app/services/training_block_service.py` [MODIFY]
- Actions:
  - Add import: `from app.core.unit_of_work import UnitOfWork`
  - Add import: `from app.models.training_block import TrainingBlock`
  - Add method `async create_for_athlete_uow(self, athlete_id: uuid.UUID, data: TrainingBlockCreate, uow: UnitOfWork) -> TrainingBlock`:
    - Calls `existing = await uow.blocks.get_active_by_athlete(athlete_id)`
    - If existing, raises `HTTPException(status_code=409, detail="Active training block already exists")`
    - Builds payload dict from `data.model_dump(exclude_unset=True)`, adds `athlete_id` and `status=GoalStatus.ACTIVE`
    - Constructs `TrainingBlock(**payload)`
    - Calls `uow.blocks.session.add(obj)` then `await uow.blocks.session.flush()`
    - Returns the ORM object
    - Does NOT call `self.repo` — uses UoW session directly (see Technical Debt note)

### 14. Add UoW-compatible methods to AthleteService (existing service)
- Objective: Add methods that operate within a UoW transaction for onboarding orchestration. Existing methods are untouched.
- File: `app/services/athlete_service.py` [MODIFY]
- Actions:
  - Add import: `from app.core.unit_of_work import UnitOfWork`
  - Add method `async set_onboarding_complete_uow(self, athlete_id: uuid.UUID, uow: UnitOfWork) -> None`:
    - Fetches athlete via `athlete = await uow.athletes.get_by_id(athlete_id)`
    - If athlete is None, raises `ValueError(f"Athlete {athlete_id} not found")`
    - Sets `athlete.onboarding_complete = True`
    - Calls `await uow.athletes.session.flush()`
    - Does NOT call `self.athlete_repo.update()` — that method commits internally, which would break UoW transaction boundaries
  - Add method `async get_profile_uow(self, athlete_id: uuid.UUID, uow: UnitOfWork) -> Optional[AthleteProfile]`:
    - Returns `await uow.profiles.get_by_athlete_id(athlete_id)`

### 15. Create TwinStateService (new service)
- Objective: Service layer for twin state queries with response serialization
- File: `app/services/twin_state_service.py` [CREATE]
- Actions:
  - Create `TwinStateService` class with no constructor dependencies
  - Add method `async get_current_twin_state(self, athlete_id: uuid.UUID, uow: UnitOfWork) -> Optional[TwinStateResponse]`:
    - Calls `await uow.twin_states.get_by_athlete_id(athlete_id)`
    - Returns `TwinStateResponse.model_validate(twin_state)` if found, else None
  - Add method `async get_twin_state_history(self, athlete_id: uuid.UUID, uow: UnitOfWork, limit: int = 100, offset: int = 0) -> tuple[list[TwinStateResponse], int]`:
    - Calls `await uow.twin_states.get_history_by_athlete_id(athlete_id, limit, offset)`
    - Returns tuple of (list of `TwinStateResponse`, total count)

### 16. Create TwinInitialisationService (new service)
- Objective: Pure-Python deterministic twin initialization from onboarding data (no LLM)
- File: `app/services/twin_initialisation_service.py` [CREATE]
- Actions:
  - Create `TwinInitialisationService` class with no constructor dependencies
  - Add method `async initialise(self, athlete_id: uuid.UUID, preferences: AthletePreferences, training_block: TrainingBlock, profile: AthleteProfile, uow: UnitOfWork) -> TwinState`:
    - Validates `profile.date_of_birth` is not None; raises `ValueError` if missing
    - Computes `age` via `_compute_age(profile.date_of_birth)`
    - Extracts `gender = profile.gender.value if profile.gender else None`
    - Computes `data_tier` via `_infer_data_tier(preferences)`
    - Computes `fitness_score` via `_calculate_fitness_score(training_block.weekly_volume_hours, preferences.years_structured_training, preferences.sport_background)`
    - Computes `max_hr` via `_max_hr(age, gender)`
    - Computes `lt1_hr, lt2_hr` via `_calculate_thresholds(max_hr, fitness_score)`
    - Computes `structural_capacity_score` via `_structural_capacity_score(preferences.sport_background)`
    - Builds `summary` via `_build_summary(age, fitness_score, data_tier, structural_capacity_score, gender)`
    - Builds `metadata` via `_build_metadata(age, fitness_score, data_tier, structural_capacity_score, gender)`
    - Constructs `TwinState` ORM object with all computed fields, `trigger=TwinTrigger.QUESTIONNAIRE`, `confidence_level=ConfidenceLevel.LOW`, `fatigue_score=0.0`, `fitness_time_constant=42.0`, `fatigue_time_constant=7.0`, `lt1_pace_estimate=None`, `lt2_pace_estimate=None`
    - Calls `uow.twin_states.session.add(twin)` then `await uow.twin_states.session.flush()`
    - Returns the `TwinState` ORM object
  - Add static method `_compute_age(date_of_birth: date) -> int`:
    - Computes age as `today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))`
  - Add static method `_max_hr(age: int, gender: Optional[str]) -> float`:
    - If `gender == "female"`: returns `206.0 - (0.88 * age)` (Gulati formula)
    - Otherwise: returns `208.0 - (0.7 * age)` (Tanaka formula)
  - Add static method `_calculate_fitness_score(weekly_volume_hours: float, years_structured_training: int, sport_background: SportBackground) -> float`:
    - Computes `base_score = (weekly_volume_hours * 2) + (years_structured_training * 5)`
    - If `sport_background` is `CYCLING_CROSSOVER` or `SWIMMING_CROSSOVER`: multiplies by 0.8
    - Clamps result between 0 and 100
  - Add static method `_calculate_thresholds(max_hr: float, fitness_score: float) -> tuple[float, float]`:
    - Defines threshold bands: `{0: (0.65, 0.80), 21: (0.70, 0.83), 51: (0.73, 0.85), 81: (0.76, 0.88)}`
    - Iterates bands in descending score order, returns first where `fitness_score >= score`
    - Returns `(round(max_hr * lt1_frac, 1), round(max_hr * lt2_frac, 1))`
  - Add static method `_infer_data_tier(preferences: AthletePreferences) -> DataTier`:
    - TIER1: `power_source == RUNNING_POWER` AND `hr_source == CHEST_STRAP`
    - TIER2: `power_source == RUNNING_POWER` AND `hr_source != CHEST_STRAP`
    - TIER3: `power_source != RUNNING_POWER` AND `hr_source == CHEST_STRAP`
    - TIER4: `power_source != RUNNING_POWER` AND `hr_source == WRIST_OPTICAL`
    - TIER5: all other cases
  - Add static method `_structural_capacity_score(sport_background: SportBackground) -> float`:
    - Returns mapping: `RUNNING_PRIMARY: 0.7`, `MULTI_SPORT: 0.5`, `CYCLING_CROSSOVER: 0.2`, `SWIMMING_CROSSOVER: 0.2`, `OTHER: 0.5`
    - Defaults to 0.5 for unknown values
  - Add static method `_build_summary(age, fitness_score, data_tier, structural_capacity_score, gender) -> str`:
    - Returns formatted string with age, gender (or "not specified"), fitness score, data tier, structural capacity, and max HR formula name
  - Add static method `_build_metadata(age, fitness_score, data_tier, structural_capacity_score, gender) -> dict`:
    - Returns dict with keys: `age`, `fitness_score`, `data_tier`, `structural_capacity_score`, `gender`, `max_hr_formula`

### 17. Create OnboardingService (new service)
- Objective: Extract onboarding orchestration from route handler into a dedicated service using UoW. Ensures twin creation happens BEFORE `onboarding_complete=True`.
- File: `app/services/onboarding_service.py` [CREATE]
- Actions:
  - Create `OnboardingService` class with:
    - `__init__(self, athlete_service: AthleteService, athlete_preferences_service: AthletePreferencesService, training_block_service: TrainingBlockService, twin_initialisation_service: TwinInitialisationService)` — stores all four services
    - `async complete_onboarding(self, athlete_id: uuid.UUID, payload: OnboardingRequest, uow: UnitOfWork) -> tuple[AthletePreferences, TrainingBlock, TwinState]`:
      - Step 1: Calls `self.athlete_preferences_service.create_for_athlete_uow(athlete_id, payload.preferences, uow)` to create preferences
      - Step 2: Calls `self.training_block_service.create_for_athlete_uow(athlete_id, payload.training_block, uow)` to create training block (enforces 409 if duplicate)
      - Step 3: Calls `self.athlete_service.get_profile_uow(athlete_id, uow)` to get profile
      - Step 4: If profile is None or `profile.date_of_birth` is None, raises `ValueError` with message about missing date_of_birth
      - Step 5: Calls `self.twin_initialisation_service.initialise(athlete_id, preferences, training_block, profile, uow)` to create twin state
      - Step 6 (LAST): Calls `self.athlete_service.set_onboarding_complete_uow(athlete_id, uow)`
      - Returns tuple of `(preferences, training_block, twin_state)`
      - Ordering guarantee: if twin initialization fails at step 5, `onboarding_complete` is never set, and the athlete can retry cleanly

### 18. Update services __init__.py
- Objective: Export new services
- File: `app/services/__init__.py` [MODIFY]
- Actions:
  - Add imports: `TwinStateService`, `TwinInitialisationService`, `OnboardingService`
  - Add all three to `__all__`

---

## API Dependencies

### 19. Add dependency factories for new services
- Objective: Provide FastAPI DI factories for TwinStateService, TwinInitialisationService, and OnboardingService
- File: `app/api/dependencies/services.py` [MODIFY]
- Actions:
  - Add import: `from app.services.twin_state_service import TwinStateService`
  - Add import: `from app.services.twin_initialisation_service import TwinInitialisationService`
  - Add import: `from app.services.onboarding_service import OnboardingService`
  - Add import: `from app.repositories.twin_state_repository import TwinStateRepository`
  - Add function `get_twin_state_service() -> TwinStateService` — returns `TwinStateService()` (no dependencies)
  - Add function `get_twin_initialisation_service() -> TwinInitialisationService` — returns `TwinInitialisationService()` (no dependencies)
  - Add async function `get_onboarding_service(db: AsyncSession = Depends(get_db)) -> OnboardingService`:
    - Creates `AthleteService(AthleteRepository(db), AthleteProfileRepository(db))`
    - Creates `AthletePreferencesService(AthletePreferencesRepository(db))`
    - Creates `TrainingBlockService(TrainingBlockRepository(db))`
    - Creates `TwinInitialisationService()`
    - Returns `OnboardingService(athlete_service, ap_service, tb_service, twin_init_service)`
    - Note: sub-services receive a session for construction but their UoW methods use the UoW's session, not their own repos (see Technical Debt note)

### 20. Update dependencies __init__.py
- Objective: Export new dependency factories
- File: `app/api/dependencies/__init__.py` [MODIFY]
- Actions:
  - Add imports: `get_twin_state_service`, `get_twin_initialisation_service`, `get_onboarding_service`
  - Add all three to `__all__`

---

## API Routes

### 21. Create twin state routes
- Objective: Endpoints for current twin state and paginated history
- File: `app/api/routes/twin_state.py` [CREATE]
- Actions:
  - Create `router = APIRouter(prefix="/athletes/{athlete_id}/twin", tags=["twin"])`
  - Add `GET /` endpoint returning `TwinStateResponse`:
    - Parameters: `athlete_id: uuid.UUID`, `service: TwinStateService = Depends(get_twin_state_service)`
    - Creates session via `async with AsyncSessionLocal() as session`
    - Creates UoW via `async with UnitOfWork(session) as uow`
    - Calls `await service.get_current_twin_state(athlete_id, uow)`
    - Returns 404 if None, otherwise returns the response
  - Add `GET /history` endpoint returning paginated results:
    - Parameters: `athlete_id: uuid.UUID`, `service: TwinStateService = Depends(get_twin_state_service)`, `limit: int = Query(ge=1, le=1000, default=100)`, `offset: int = Query(ge=0, default=0)`
    - Creates session via `async with AsyncSessionLocal() as session`
    - Creates UoW via `async with UnitOfWork(session) as uow`
    - Returns `await service.get_twin_state_history(athlete_id, uow, limit, offset)`
    - Response model: define a `TwinStateHistoryResponse` pydantic model in the route file with `items: list[TwinStateResponse]` and `total: int`

### 22. Update onboarding route — wire OnboardingService + UoW + twin
- Objective: Replace inline onboarding logic with OnboardingService using UoW, including twin initialization
- File: `app/api/routes/athletes.py` [MODIFY]
- Actions:
  - Add import: `from app.core.unit_of_work import UnitOfWork`
  - Add import: `from app.db.session import AsyncSessionLocal`
  - Add import: `from app.services.onboarding_service import OnboardingService`
  - Add import: `from app.api.dependencies.services import get_onboarding_service`
  - Add import: `from app.schemas.twin_state import TwinStateResponse`
  - In the `onboard_athlete` POST endpoint:
    - Add parameter: `onboarding_service: OnboardingService = Depends(get_onboarding_service)`
    - Remove parameter: `db: AsyncSession = Depends(get_db)` (no longer needed directly)
    - Remove parameters: `ap_service`, `tb_service` (now handled by OnboardingService)
    - Keep parameters: `athlete_service` (still needed for pre-flight validation)
    - Keep all pre-flight validation logic (404, 422, 409 checks) — these use `athlete_service` which has its own session
    - Replace the `async with db.begin():` block with:
      - `async with AsyncSessionLocal() as session:`
      - `async with UnitOfWork(session) as uow:`
      - Inside: idempotency recheck using `uow.athletes.get_by_id(athlete_id)` checking `onboarding_complete`
      - Call `preferences, training_block, twin_state = await onboarding_service.complete_onboarding(athlete_id, payload, uow)`
    - Update return statement to use `TwinStateResponse.model_validate(twin_state)` instead of `twin_state=None`
  - In the `get_onboarding_status` GET endpoint:
    - Add import for `TwinStateService` and `get_twin_state_service`
    - Add parameter: `twin_service: TwinStateService = Depends(get_twin_state_service)`
    - After fetching preferences and training_block, fetch current twin state:
      - `async with AsyncSessionLocal() as session:`
      - `async with UnitOfWork(session) as uow:`
      - `twin_state = await twin_service.get_current_twin_state(athlete_id, uow)`
    - Pass `twin_state` to `OnboardingStatusResponse` instead of `twin_state=None`

### 23. Register twin state router in main.py
- Objective: Include twin state routes in the FastAPI app
- File: `app/main.py` [MODIFY]
- Actions:
  - Add import: `from app.api.routes.twin_state import router as twin_state_router`
  - Add: `app.include_router(twin_state_router)` after the existing router includes

---

## Migration

### 24. Create Alembic migration for twin_states table
- Objective: Add twin_states table to database
- File: `alembic/versions/<timestamp>_create_twin_states.py` [CREATE]
- Actions:
  - `upgrade()`:
    - `op.create_table("twin_states", ...)` with all columns matching the `TwinState` ORM model
    - `op.create_index("ix_twin_states_athlete_id", "twin_states", ["athlete_id"])`
  - `downgrade()`:
    - `op.drop_index("ix_twin_states_athlete_id", table_name="twin_states")`
    - `op.drop_table("twin_states")`
  - Note: `AthleteProfile.gender` column already exists — no ALTER needed
  - Note: This migration is autogenerated by Alembic; p-devops handles the `revision --autogenerate` command

---

## Computation Design (reference for coder)

### Fitness Score
```
fitness_score = (weekly_volume_hours * 2) + (years_structured_training * 5)
```
- Crossover adjustment: ×0.8 for cycling/swimming backgrounds
- Clamped to 0–100

### Max HR Estimate
- Female: `206 - (0.88 * age)` (Gulati et al. 2010)
- Male/Other/None: `208 - (0.7 * age)` (Tanaka et al. 2001)

### Threshold Estimates
| Fitness Score Range | LT1 % | LT2 % |
|---------------------|-------|-------|
| 0–20 (Beginner)      | 0.65  | 0.80  |
| 21–50 (Intermediate) | 0.70  | 0.83  |
| 51–80 (Advanced)     | 0.73  | 0.85  |
| 81–100 (Elite)       | 0.76  | 0.88  |

### Data Tier
- TIER1: Running power + chest strap HR
- TIER2: Running power + optical HR
- TIER3: Chest strap HR only
- TIER4: Optical HR only
- TIER5: No HR

### Structural Capacity
- Running primary: 0.7
- Multi-sport: 0.5
- Cycling/swimming crossover: 0.2
- Other: 0.5

---

## Onboarding Orchestration Order (canonical)

```
1. Create AthletePreferences     (flush)
2. Create TrainingBlock           (flush, enforces 409 if duplicate)
3. Fetch AthleteProfile           (read)
4. Validate date_of_birth         (guard)
5. Create TwinState               (flush, deterministic computation)
6. Set onboarding_complete=True   (flush, LAST — only after all writes succeed)
7. UoW.__aexit__ commits          (single commit for entire transaction)
```

If any step 1–6 raises, `UoW.__aexit__` calls `rollback()`. `onboarding_complete` is only
set to `True` if every prior step succeeded. If twin initialization fails, the flag stays
`False` and the athlete can retry cleanly.

---

## Validation Rules

### Model-Level Constraints (DB CheckConstraints)
- `fitness_score`: 0–100
- `fatigue_score`: ≥ 0
- `max_hr_estimate`: 140–220 bpm
- `structural_capacity_score`: 0.0–1.0

### Service-Level Rules
- Missing `AthleteProfile.date_of_birth`: raises `ValueError`
- Missing `AthleteProfile.gender`: defaults to Tanaka formula
- Invalid `sport_background`: defaults to `OTHER` (0.5 structural capacity)

---

## Done Criteria

### Functional
- [ ] `POST /onboarding` returns populated `twin_state` as `TwinStateResponse`
- [ ] `TwinState` created atomically with `AthletePreferences` and `TrainingBlock`
- [ ] `onboarding_complete` is set **after** `TwinState` is written — if twin init fails, flag stays false
- [ ] `GET /twin` returns current state after onboarding
- [ ] `GET /twin/history` returns paginated results with `items` and `total`
- [ ] For 30-year-old male, `fitness_score=52`: `max_hr≈187`, `lt1≈137`, `lt2≈159`
- [ ] For 30-year-old female, `fitness_score=52`: `max_hr≈179`, `lt1≈131`, `lt2≈152`
- [ ] Crossover athletes have `structural_capacity_score=0.2`
- [ ] `computation_metadata` contains all required fields
- [ ] All `UnitOfWork` usage via `async with`

### Non-Functional
- [ ] Migration applies and rolls back cleanly
- [ ] No regressions on existing endpoints
- [ ] All DB access uses `AsyncSession`
- [ ] No business logic in API routes (orchestration in OnboardingService)
- [ ] Pagination on `/twin/history` returns structured response with `items` + `total`
