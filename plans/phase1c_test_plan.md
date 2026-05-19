# Phase 1c Test Plan

> Comprehensive test coverage for the Phase 1c twin initialisation implementation.
> Follows existing test conventions: unit tests with mocks in `tests/unit/`,
> integration tests with real DB in `tests/integration/`, factories in `tests/factories/`.

---

## Test File Inventory

### Unit Tests (new files)
- `tests/unit/test_twin_state_model.py` — TwinState model and enum validation
- `tests/unit/test_twin_state_schemas.py` — TwinState Pydantic schemas
- `tests/unit/test_unit_of_work.py` — UnitOfWork lifecycle and repository access
- `tests/unit/test_twin_state_repository.py` — TwinStateRepository queries
- `tests/unit/test_twin_state_service.py` — TwinStateService response serialization
- `tests/unit/test_twin_initialisation_service.py` — TwinInitialisationService computation logic
- `tests/unit/test_onboarding_service.py` — OnboardingService orchestration and ordering
- `tests/unit/test_athlete_service_uow.py` — AthleteService UoW-compatible methods
- `tests/unit/test_athlete_preferences_service_uow.py` — AthletePreferencesService UoW method
- `tests/unit/test_training_block_service_uow.py` — TrainingBlockService UoW method

### Integration Tests (new file)
- `tests/integration/test_twin_state_api.py` — Twin state endpoints + onboarding with twin

### Factories (new file)
- `tests/factories/twin_state_factory.py` — TwinState test data factories

---

## Unit Tests

### 1. TwinState Model and Enum Tests
- File: `tests/unit/test_twin_state_model.py` [CREATE]
- Tests:
  - Verify `TwinTrigger` enum has values: `questionnaire`, `calibration`, `wellness_update`
  - Verify `ConfidenceLevel` enum has values: `low`, `medium`, `high`
  - Verify `DataTier` enum has values: `tier1`, `tier2`, `tier3`, `tier4`, `tier5`
  - Verify `TwinState.__tablename__` is `twin_states`
  - Verify `TwinState` model has all expected columns: `id`, `athlete_id`, `athlete_preferences_id`, `trigger`, `confidence_level`, `data_tier`, `fitness_score`, `fatigue_score`, `max_hr_estimate`, `lt1_hr_estimate`, `lt2_hr_estimate`, `lt1_pace_estimate`, `lt2_pace_estimate`, `structural_capacity_score`, `fitness_time_constant`, `fatigue_time_constant`, `computation_summary`, `computation_metadata`, `created_at`
  - Verify `TwinState` has `athlete` and `preferences` relationships defined
  - Verify `TwinState.__table_args__` contains all four CheckConstraints: `ck_twin_states_fitness_score_range`, `ck_twin_states_max_hr_range`, `ck_twin_states_fatigue_non_negative`, `ck_twin_states_structural_capacity_range`

### 2. TwinState Schema Tests
- File: `tests/unit/test_twin_state_schemas.py` [CREATE]
- Tests:
  - Verify `TwinStateBase` accepts all required fields and validates `fitness_score` range (0–100)
  - Verify `TwinStateBase` rejects `fitness_score` below 0 or above 100
  - Verify `TwinStateBase` rejects `fatigue_score` below 0
  - Verify `TwinStateBase` rejects `structural_capacity_score` below 0 or above 1
  - Verify `TwinStateBase` defaults `confidence_level` to `ConfidenceLevel.LOW`
  - Verify `TwinStateBase` defaults `fatigue_score` to 0.0
  - Verify `TwinStateBase` defaults `lt1_pace_estimate` and `lt2_pace_estimate` to None
  - Verify `TwinStateBase` defaults `fitness_time_constant` to 42.0 and `fatigue_time_constant` to 7.0
  - Verify `TwinStateCreate` inherits all fields from `TwinStateBase` with no additions
  - Verify `TwinStateResponse` includes `id` (UUID) and `created_at` (datetime) in addition to base fields
  - Verify `TwinStateResponse.model_validate()` correctly serializes a `TwinState` ORM instance
  - Verify `TwinStateBase` accepts enum values as both enum members and string values

### 3. UnitOfWork Tests
- File: `tests/unit/test_unit_of_work.py` [CREATE]
- Tests:
  - Verify `UnitOfWork.__aenter__` starts a transaction when session is not already in one
  - Verify `UnitOfWork.__aenter__` does NOT start a new transaction when session is already in one (nested UoW scenario)
  - Verify `UnitOfWork.__aexit__` commits on successful exit
  - Verify `UnitOfWork.__aexit__` rolls back when an exception is raised
  - Verify `UnitOfWork` exposes all five repositories via attribute access: `athletes`, `preferences`, `blocks`, `twin_states`, `profiles`
  - Verify accessing a repository outside of `async with` raises `RuntimeError`
  - Verify accessing an unknown attribute raises `AttributeError` listing available keys
  - Verify each repository is constructed with the UoW's session (not a separate session)

### 4. TwinStateRepository Tests
- File: `tests/unit/test_twin_state_repository.py` [CREATE]
- Tests:
  - Verify `create()` constructs a `TwinState` from `TwinStateCreate`, calls `session.add()` and `session.flush()`, and returns the object
  - Verify `get_by_athlete_id()` queries by `athlete_id`, orders by `created_at DESC`, limits to 1, and returns the most recent twin state
  - Verify `get_by_athlete_id()` returns `None` when no twin states exist for the athlete
  - Verify `get_history_by_athlete_id()` returns a tuple of (items list, total count)
  - Verify `get_history_by_athlete_id()` applies `limit` and `offset` correctly
  - Verify `get_history_by_athlete_id()` orders results by `created_at DESC`
  - Verify `count_by_athlete_id()` returns the correct count of twin states for an athlete
  - Verify `count_by_athlete_id()` returns 0 when no twin states exist

### 5. TwinStateService Tests
- File: `tests/unit/test_twin_state_service.py` [CREATE]
- Tests:
  - Verify `get_current_twin_state()` returns `TwinStateResponse` when a twin state exists
  - Verify `get_current_twin_state()` returns `None` when no twin state exists
  - Verify `get_current_twin_state()` delegates to `uow.twin_states.get_by_athlete_id()`
  - Verify `get_twin_state_history()` returns a tuple of (list of `TwinStateResponse`, total count)
  - Verify `get_twin_state_history()` passes `limit` and `offset` to the repository
  - Verify `get_twin_state_history()` returns empty list and zero total when no history exists

### 6. TwinInitialisationService Tests
- File: `tests/unit/test_twin_initialisation_service.py` [CREATE]
- Tests:

  **`initialise()` orchestration:**
  - Verify `initialise()` raises `ValueError` when `profile.date_of_birth` is None
  - Verify `initialise()` computes all fields and returns a `TwinState` ORM object
  - Verify `initialise()` calls `session.add()` and `session.flush()` on the UoW's twin_states session
  - Verify the returned `TwinState` has `trigger=TwinTrigger.QUESTIONNAIRE`
  - Verify the returned `TwinState` has `confidence_level=ConfidenceLevel.LOW`
  - Verify the returned `TwinState` has `fatigue_score=0.0`
  - Verify the returned `TwinState` has `fitness_time_constant=42.0` and `fatigue_time_constant=7.0`
  - Verify the returned `TwinState` has `lt1_pace_estimate=None` and `lt2_pace_estimate=None`

  **`_compute_age()`:**
  - Verify correct age for a birthday that has already passed this year
  - Verify correct age for a birthday that has not yet passed this year
  - Verify correct age for a birthday exactly on today's date

  **`_max_hr()`:**
  - Verify Gulati formula for female: `206 - (0.88 * age)` — test with age 30 → 179.6
  - Verify Tanaka formula for male: `208 - (0.7 * age)` — test with age 30 → 187.0
  - Verify Tanaka formula for `None` gender (defaults to male formula)
  - Verify Tanaka formula for `"non_binary"` gender

  **`_calculate_fitness_score()`:**
  - Verify base calculation: `(weekly_volume_hours * 2) + (years_structured_training * 5)`
  - Verify crossover adjustment (×0.8) for `CYCLING_CROSSOVER`
  - Verify crossover adjustment (×0.8) for `SWIMMING_CROSSOVER`
  - Verify no adjustment for `RUNNING_PRIMARY`
  - Verify clamping to 0 when inputs produce negative score
  - Verify clamping to 100 when inputs exceed 100
  - Verify exact computation for 30-year-old male, `fitness_score=52` scenario: weekly_volume_hours=6, years=5, background=RUNNING_PRIMARY → (6*2)+(5*5) = 37 — adjust test inputs to produce 52: weekly_volume_hours=11, years=6 → (11*2)+(6*5) = 52

  **`_calculate_thresholds()`:**
  - Verify beginner band (0–20): LT1=0.65, LT2=0.80
  - Verify intermediate band (21–50): LT1=0.70, LT2=0.83
  - Verify advanced band (51–80): LT1=0.73, LT2=0.85
  - Verify elite band (81–100): LT1=0.76, LT2=0.88
  - Verify exact values for fitness_score=52, max_hr=187: LT1≈136.5, LT2≈158.9
  - Verify exact values for fitness_score=52, max_hr=179.6: LT1≈131.1, LT2≈152.7

  **`_infer_data_tier()`:**
  - Verify TIER1: `power_source=RUNNING_POWER` AND `hr_source=CHEST_STRAP`
  - Verify TIER2: `power_source=RUNNING_POWER` AND `hr_source=WRIST_OPTICAL`
  - Verify TIER3: `power_source=NONE` AND `hr_source=CHEST_STRAP`
  - Verify TIER4: `power_source=NONE` AND `hr_source=WRIST_OPTICAL`
  - Verify TIER5: `power_source=NONE` AND `hr_source=NONE`
  - Verify TIER5: `power_source=RUNNING_POWER` AND `hr_source=NONE`

  **`_structural_capacity_score()`:**
  - Verify `RUNNING_PRIMARY` → 0.7
  - Verify `MULTI_SPORT` → 0.5
  - Verify `CYCLING_CROSSOVER` → 0.2
  - Verify `SWIMMING_CROSSOVER` → 0.2
  - Verify `OTHER` → 0.5
  - Verify unknown/None background defaults to 0.5

  **`_build_summary()` and `_build_metadata()`:**
  - Verify summary string contains age, gender, fitness score, data tier, structural capacity, and max HR formula name
  - Verify summary uses "not specified" when gender is None
  - Verify metadata dict contains all required keys: `age`, `fitness_score`, `data_tier`, `structural_capacity_score`, `gender`, `max_hr_formula`
  - Verify `max_hr_formula` is "Gulati" for female, "Tanaka" for all others

### 7. OnboardingService Tests
- File: `tests/unit/test_onboarding_service.py` [CREATE]
- Tests:
  - Verify `complete_onboarding()` calls `athlete_preferences_service.create_for_athlete_uow()` with correct arguments (step 1)
  - Verify `complete_onboarding()` calls `training_block_service.create_for_athlete_uow()` with correct arguments (step 2)
  - Verify `complete_onboarding()` calls `athlete_service.get_profile_uow()` (step 3)
  - Verify `complete_onboarding()` raises `ValueError` when profile is None (step 4 guard)
  - Verify `complete_onboarding()` raises `ValueError` when `profile.date_of_birth` is None (step 4 guard)
  - Verify `complete_onboarding()` calls `twin_initialisation_service.initialise()` with preferences, training_block, and profile (step 5)
  - Verify `complete_onboarding()` calls `athlete_service.set_onboarding_complete_uow()` LAST, after twin initialization (step 6)
  - Verify `complete_onboarding()` returns tuple of (preferences, training_block, twin_state)
  - Verify ordering guarantee: if `twin_initialisation_service.initialise()` raises, `set_onboarding_complete_uow()` is NOT called (use mock that raises on step 5)
  - Verify ordering guarantee: if `training_block_service.create_for_athlete_uow()` raises HTTPException 409, subsequent steps are NOT called

### 8. AthleteService UoW Methods Tests
- File: `tests/unit/test_athlete_service_uow.py` [CREATE]
- Tests:
  - Verify `set_onboarding_complete_uow()` fetches athlete via `uow.athletes.get_by_id()`
  - Verify `set_onboarding_complete_uow()` sets `athlete.onboarding_complete = True`
  - Verify `set_onboarding_complete_uow()` calls `session.flush()`
  - Verify `set_onboarding_complete_uow()` raises `ValueError` when athlete not found
  - Verify `get_profile_uow()` delegates to `uow.profiles.get_by_athlete_id()`
  - Verify `get_profile_uow()` returns `None` when profile not found

### 9. AthletePreferencesService UoW Method Tests
- File: `tests/unit/test_athlete_preferences_service_uow.py` [CREATE]
- Tests:
  - Verify `create_for_athlete_uow()` builds payload from schema data with `athlete_id` added
  - Verify `create_for_athlete_uow()` constructs `AthletePreferences` ORM object
  - Verify `create_for_athlete_uow()` calls `uow.preferences.session.add()` and `session.flush()`
  - Verify `create_for_athlete_uow()` returns the created ORM object
  - Verify `create_for_athlete_uow()` does NOT call `self.repo`

### 10. TrainingBlockService UoW Method Tests
- File: `tests/unit/test_training_block_service_uow.py` [CREATE]
- Tests:
  - Verify `create_for_athlete_uow()` checks for existing active block via `uow.blocks.get_active_by_athlete()`
  - Verify `create_for_athlete_uow()` raises `HTTPException` 409 when active block exists
  - Verify `create_for_athlete_uow()` builds payload with `athlete_id` and `status=GoalStatus.ACTIVE`
  - Verify `create_for_athlete_uow()` constructs `TrainingBlock` ORM object
  - Verify `create_for_athlete_uow()` calls `uow.blocks.session.add()` and `session.flush()`
  - Verify `create_for_athlete_uow()` returns the created ORM object
  - Verify `create_for_athlete_uow()` does NOT call `self.repo`

---

## Integration Tests

### 11. Twin State API Tests
- File: `tests/integration/test_twin_state_api.py` [CREATE]
- Tests:

  **`GET /athletes/{athlete_id}/twin/`:**
  - Verify returns 404 when athlete has no twin state
  - Verify returns 200 with `TwinStateResponse` after onboarding is complete
  - Verify response contains all expected fields: `id`, `athlete_id`, `athlete_preferences_id`, `trigger`, `confidence_level`, `data_tier`, `fitness_score`, `fatigue_score`, `max_hr_estimate`, `lt1_hr_estimate`, `lt2_hr_estimate`, `lt1_pace_estimate`, `lt2_pace_estimate`, `structural_capacity_score`, `fitness_time_constant`, `fatigue_time_constant`, `computation_summary`, `computation_metadata`, `created_at`
  - Verify `trigger` is `"questionnaire"` in response
  - Verify `confidence_level` is `"low"` in response

  **`GET /athletes/{athlete_id}/twin/history`:**
  - Verify returns 200 with `{"items": [], "total": 0}` when no history exists
  - Verify returns paginated results with correct `items` and `total` after onboarding
  - Verify `limit` parameter works (returns at most `limit` items)
  - Verify `offset` parameter works (skips first `offset` items)
  - Verify results are ordered by `created_at` descending
  - Verify `limit` validation: returns 422 for `limit < 1` or `limit > 1000`
  - Verify `offset` validation: returns 422 for `offset < 0`

  **Onboarding with twin state (`POST /athletes/{athlete_id}/onboarding`):**
  - Verify successful onboarding returns 201 with populated `twin_state` in response
  - Verify `twin_state` in response matches `TwinStateResponse` schema
  - Verify onboarding creates a `TwinState` record in the database (query after request)
  - Verify `onboarding_complete` flag is set to `True` after successful onboarding
  - Verify onboarding without profile returns 422
  - Verify onboarding with inactive athlete returns 422
  - Verify repeat onboarding returns 409

  **Onboarding status with twin state (`GET /athletes/{athlete_id}/onboarding`):**
  - Verify returns 200 with `twin_state` populated after onboarding
  - Verify returns 200 with `twin_state=None` before onboarding
  - Verify returns 404 for nonexistent athlete

  **Atomicity and rollback:**
  - Verify that if twin initialization fails (e.g., missing date_of_birth), `onboarding_complete` stays `False` and no preferences/training_block/twin_state are persisted (use a setup where profile exists but date_of_birth is missing — though the pre-flight check catches this; test the UoW rollback path by verifying partial writes don't leak)

  **Computation correctness (end-to-end):**
  - For a 30-year-old male with `weekly_volume_hours=11`, `years_structured_training=6`, `sport_background=RUNNING_PRIMARY`, `hr_source=CHEST_STRAP`, `power_source=RUNNING_POWER`:
    - Verify `fitness_score=52.0`
    - Verify `max_hr_estimate≈187.0`
    - Verify `lt1_hr_estimate≈136.5`
    - Verify `lt2_hr_estimate≈158.9`
    - Verify `structural_capacity_score=0.7`
    - Verify `data_tier="tier1"`
  - For a 30-year-old female with same training params:
    - Verify `max_hr_estimate≈179.6`
    - Verify `lt1_hr_estimate≈131.1`
    - Verify `lt2_hr_estimate≈152.7`
  - For a crossover athlete (`CYCLING_CROSSOVER`):
    - Verify `structural_capacity_score=0.2`
    - Verify fitness score has 0.8 multiplier applied

---

## Factories

### 12. TwinState Factory
- File: `tests/factories/twin_state_factory.py` [CREATE]
- Functions to create:
  - `make_twin_state(athlete_id, athlete_preferences_id, **overrides)` — minimal valid TwinState instance with default computed values
  - `make_twin_state_full(athlete_id, athlete_preferences_id, **overrides)` — all fields populated with realistic values
  - `make_twin_state_batch(n, athlete_id, athlete_preferences_id, **overrides)` — list of n TwinState instances
  - `make_twin_state_create_schema(athlete_id, athlete_preferences_id, **overrides)` — TwinStateCreate Pydantic schema instance

### 13. Update factories __init__.py
- File: `tests/factories/__init__.py` [MODIFY]
- Actions:
  - Add imports: `make_twin_state`, `make_twin_state_full`, `make_twin_state_batch`, `make_twin_state_create_schema`
  - Add all four to `__all__`

---

## Test Execution Order

1. Run unit tests first (no DB required): `pytest tests/unit/test_twin_state_model.py tests/unit/test_twin_state_schemas.py tests/unit/test_unit_of_work.py tests/unit/test_twin_state_repository.py tests/unit/test_twin_state_service.py tests/unit/test_twin_initialisation_service.py tests/unit/test_onboarding_service.py tests/unit/test_athlete_service_uow.py tests/unit/test_athlete_preferences_service_uow.py tests/unit/test_training_block_service_uow.py`
2. Run integration tests (requires test DB): `pytest tests/integration/test_twin_state_api.py`
3. Run full regression suite to verify no existing tests break: `pytest tests/`

---

## Test Data Requirements

### For TwinInitialisationService unit tests:
- Mock `UnitOfWork` with mock `twin_states` repository exposing `session.add()` and `session.flush()` as AsyncMocks
- `AthletePreferences` instances with varying `sport_background`, `hr_source`, `power_source`
- `AthleteProfile` instances with varying `date_of_birth` and `gender`
- `TrainingBlock` instances with varying `weekly_volume_hours`

### For OnboardingService unit tests:
- Mock all four sub-services: `AthleteService`, `AthletePreferencesService`, `TrainingBlockService`, `TwinInitialisationService`
- Mock `UnitOfWork` with all five repository mocks

### For integration tests:
- Use `client` fixture from `conftest.py` for HTTP requests
- Use `test_db_session` fixture for direct DB verification
- Use `clean_db_tables` fixture (autouse) for test isolation

---

## Coverage Targets

| Component | Target | Rationale |
|---|---|---|
| `TwinInitialisationService` | 100% | Pure computation — every branch must be verified |
| `OnboardingService` | 100% | Orchestration logic — ordering guarantees are critical |
| `UnitOfWork` | 100% | Transaction management — failure here corrupts data |
| `TwinStateRepository` | 90%+ | Query logic — straightforward but pagination edge cases |
| `TwinStateService` | 90%+ | Thin serialization layer |
| UoW service methods | 90%+ | Flush-vs-commit boundary — critical for atomicity |
| Twin state API routes | 80%+ | Thin HTTP layer — integration tests cover the rest |
| TwinState model | N/A | Model definition — schema tests and integration tests cover it |
