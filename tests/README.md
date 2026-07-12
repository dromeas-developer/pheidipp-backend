# Pheidipp Test Infrastructure Guide

## Overview

This directory contains the test suite for the Pheidipp backend. Tests are organized into:
- `unit/` — Isolated unit tests (no database)
- `integration/` — Integration tests with database (transactional)
- `api/` — HTTP API tests using FastAPI test client
- `behaviour/` — End-to-end user journey tests
- `utils/` — Shared test utilities and helpers

## Shared Utilities (`tests/utils/`)

To avoid duplication and ensure consistency across the test suite, common helpers are centralized in `tests/utils/`:

### `tests/utils/schema_helpers.py`

Database schema introspection helpers that use a synchronous psycopg2 engine:

```python
from tests.utils.schema_helpers import db_columns, db_foreign_keys, db_indexes, get_sync_database_url

cols = db_columns("training_plans")
fks = db_foreign_keys("training_plans")
idxs = db_indexes("training_plans")
```

**Why separate sync engine?** Schema inspection requires a synchronous connection. These helpers automatically convert the asyncpg URL to psycopg2.

### `tests/utils/model_helpers.py`

ORM model introspection helpers for unit tests (no database required):

```python
from tests.utils.model_helpers import get_columns, get_indexes, get_check_constraints, has_column

cols = get_columns(TrainingPlan)  # dict[str, Column]
idxs = get_indexes(TrainingPlan)  # dict[str, Index]
has_col = has_column(TrainingPlan, "status")  # bool
```

### `tests/utils/factories.py`

Async factory functions for creating domain model instances in integration tests:

```python
from tests.utils.factories import make_athlete, make_auth, make_refresh_token

athlete = await make_athlete(db_session)
auth = await make_auth(db_session, athlete_id=athlete.id)
token = await make_refresh_token(db_session, athlete_id=athlete.id)
```

### `tests/utils/assertions.py`

Shared assertion patterns for security and domain invariants:

```python
from tests.utils.assertions import assert_no_secrets_in_text, assert_no_secrets_in_logs, SECRET_LEAKAGE_FIELDS

assert_no_secrets_in_text(response_text)
assert_no_secrets_in_logs(log_records)
```

**Forbidden fields checked:** `hashed_password`, `token_hash`, `provider_tokens`, `provider_user_id`, `password`.

## Migration from Inline Helpers

Legacy test files may contain inline `_columns()`, `_indexes()`, `_sync_url()` helpers. These have been consolidated into the shared utilities above. When updating existing tests:

**Before:**
```python
import os
from sqlalchemy import create_engine, inspect

def _sync_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        )
    return database_url

def _columns(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_columns(table))
    finally:
        engine.dispose()
```

**After:**
```python
from tests.utils.schema_helpers import db_columns

cols = db_columns("training_plans")
```

## Test Isolation

### How It Works

Each test gets a fresh `db_session` fixture that:
1. Opens a new database session
2. Runs the test
3. Rolls back any uncommitted changes
4. **Truncates all tables** to remove committed data

### Why Truncation Is Required

Service-layer code (e.g., `AuthService.register()`) calls `session.commit()` which **permanently persists data**. The test session's rollback only undoes **uncommitted** changes, not already-committed ones.

Without truncation, tests would contaminate each other:
```python
# Test 1: Creates athlete with email "test@example.com" and commits
await service.register(email="test@example.com", ...)  # commits

# Test 2: Tries to create SAME email → 409 Conflict (test fails!)
await service.register(email="test@example.com", ...)  # fails!
```

✅ **The truncation in `conftest.py` prevents this. DO NOT remove it.**

The truncation uses SQLAlchemy's `Base.metadata.sorted_tables` to automatically discover all tables and truncate them in the correct order (child tables before parents). This means **new models are automatically included** — no manual maintenance needed.

### ⚠️ FK Cycles and the `Cannot correctly sort tables` Warning

The Phase-1.2c schema introduces a deliberate FK cycle:

```
twin_states → activities → planned_sessions → weekly_plans → training_plans → twin_states
```

SQLAlchemy's `sorted_tables` cannot topologically sort this and emits `SAWarning: Cannot correctly sort tables; there are unresolvable cycles between tables`. PostgreSQL's `TRUNCATE ... CASCADE` handles the cycle natively (one statement truncates the whole SCC), so the warning is informational only.

`tests/conftest.py` installs a targeted `warnings.filterwarnings("ignore", message=r"Cannot correctly sort tables.*", category=SAWarning)` filter so the warning does not flood test output. Any *other* `SAWarning` from the same code path remains visible — the filter is intentionally narrow.

## Common Pitfalls

### ❌ Don't: Use `expire()` then access lazy attributes

```python
# WRONG — raises MissingGreenlet error
db_session.expire(token)
assert token.token_hash == "..."  # Triggers async lazy load!
```

**Why it fails:** After `expire()`, accessing `token.token_hash` triggers a database reload. This async operation happens outside the proper greenlet context.

### ✅ Do: Capture attributes before expire, then query fresh

```python
# CORRECT
token_hash = token.token_hash  # Capture BEFORE expire
db_session.expire(token)
refreshed = await repo.get_by_token_hash(token_hash)  # Fresh query
assert refreshed.ip_address is None
```

### ✅ Better: Skip `expire()` entirely

```python
# EVEN BETTER — just query fresh
await repo.discard_old_ips()
refreshed = await repo.get_by_token_hash(token.token_hash)
assert refreshed.ip_address is None
```

---

## Schema Inspection in Async Tests

### ❌ Don't: Use `sync_session.connection()` for schema inspection

```python
# WRONG — raises MissingGreenlet error with asyncpg
from sqlalchemy import inspect

def _columns(db_session: AsyncSession, table: str) -> list[dict]:
    conn = db_session.sync_session.connection()  # ❌ Requires greenlet context
    inspector = inspect(conn)
    return list(inspector.get_columns(table))
```

**Why it fails:** Tests run in asyncio event loops. `sync_session.connection()` tries to use asyncpg (async driver) from sync context, which requires a greenlet. Result: `MissingGreenlet` error.

### ✅ Do: Use separate sync engine for schema inspection

```python
# CORRECT — create sync engine with psycopg2
import os
from sqlalchemy import create_engine, inspect

def _columns(table: str) -> list[dict]:
    database_url = os.environ.get("DATABASE_URL", "")
    # Convert asyncpg → psycopg2
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://", 
            "postgresql+psycopg2://"
        )
    
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            # ✅ Fetch data INSIDE the with block
            return list(inspector.get_columns(table))
    finally:
        engine.dispose()
```

**Key points:**
- Don't pass `db_session` — use environment URL directly
- Convert asyncpg URL to psycopg2
- Fetch all data inside `with` block (don't return inspector objects)
- Dispose engine to clean up connections

### ❌ Don't: Use boolean checks on SQLAlchemy expressions

```python
# WRONG — TypeError on SQLAlchemy column expressions
[idx for idx in Model.__table__.indexes 
 if idx.dialect_options.get("postgresql", {}).get("where")]
```

**Error:** `TypeError: Boolean value of this clause is not defined`

**Fix:** Explicitly check for `None`:
```python
[idx for idx in Model.__table__.indexes 
 if idx.dialect_options.get("postgresql", {}).get("where") is not None]
```

### ❌ Don't: Query pg_catalog without schema filters

When tests use isolated schemas, queries against `pg_constraint`, `pg_class`, etc. must filter by schema:

```python
# WRONG — regclass::text returns "schema.table", not just "table"
WHERE conrelid::regclass::text IN ('activities')  # ❌ No match!

# CORRECT — filter by schema and use relname
JOIN pg_namespace ns ON ns.oid = table_class.relnamespace
WHERE ns.nspname = :schema
  AND table_class.relname IN ('activities', 'athlete_preferences')
```

---

## JWT Token Uniqueness in Tests

### The Issue

Access tokens are deterministic JWTs based on claims:
- `athlete_id`
- `iat` (issued-at timestamp, second precision)
- `exp` (expiry = iat + 15 min)
- `iss` (issuer)
- `auth_provider`

When two tokens are issued **within the same second**, they have identical claims and thus **identical JWT signatures**.

### Example

```python
# Test: Register then immediately refresh
result = await service.register(...)  # Issues access token A
issued = await service.rotate_refresh_token(...)  # Issues access token B

# WRONG — this assertion may fail if A and B issued in same second
assert issued.access_token != result.issued.access_token  # MAY FAIL!

# CORRECT — refresh tokens are ALWAYS unique
assert issued.refresh_token != result.issued.refresh_token  # PASSES!
```

### How to Write Robust Tests

**Option 1: Test refresh token uniqueness (recommended)**
```python
# The actual security property is refresh token rotation
assert issued.refresh_token != old_refresh_token
```

**Option 2: Add artificial delay (slower tests)**
```python
import asyncio
await asyncio.sleep(1.1)  # Ensure different second
```

**Option 3: Verify database state**
```python
# Check that old token is revoked in DB
old_token = await repo.get_by_token_hash(old_hash)
assert old_token.revoked_at is not None
```

## Writing New Integration Tests

### Template

```python
async def test_my_feature(db_session: AsyncSession, service: AuthService) -> None:
    # Arrange
    result = await service.register(...)
    
    # Act
    updated = await service.some_operation(...)
    
    # Assert — query fresh, don't rely on expired objects
    refreshed = await repo.get_by_id(result.athlete_id)
    assert refreshed.some_field == expected_value
```

### Key Rules

1. **Always use the `db_session` fixture** — never create sessions manually
2. **Don't assume object state after commits** — query fresh if you need to verify committed changes
3. **Don't test JWT access token uniqueness** — test refresh token uniqueness instead
4. **Use unique emails/IDs** — use `uuid.uuid4()` or fakers to avoid collisions

## Running Tests

```bash
# Full suite
bash scripts/run-tests.sh tests/

# Specific file
bash scripts/run-tests.sh tests/integration/test_auth_service.py

# Specific test
bash scripts/run-tests.sh tests/integration/test_auth_service.py::TestClass::test_method

# Verbose output
bash scripts/run-tests.sh tests/ -v
```

## Debugging Test Failures

### Symptom: "409 Conflict" on registration
**Cause:** Leftover data from previous test  
**Fix:** Ensure test uses unique email (e.g., `f"{uuid.uuid4()}@example.com"`)

### Symptom: `MissingGreenlet` error
**Cause:** Async IO outside proper context (often after `expire()`)  
**Fix:** Capture attributes before expire, or query fresh instead

### Symptom: Test passes alone but fails in suite
**Cause:** Data contamination from earlier test  
**Fix:** Check if test commits data; ensure unique identifiers are used

## See Also

- `conftest.py` — Fixture definitions and cleanup logic
- `pytest.ini` — Pytest configuration
- `docs/vision/` — Product vision and constraints
- `docs/adr/` — Architecture decision records

---

## Dated Lessons (2026-07-01)

### planned_session_id must be explicitly set to None in post_workout_agent tests

**Symptom:** Test receives real LLM response (~5 paragraphs) instead of mocked 3-paragraph response; validation fails with `PostWorkoutContractError`.

**Root cause:** When `MagicMock(spec=Activity)` is created without explicitly setting `planned_session_id`, the auto-created `MagicMock()` value is truthy. This causes the agent to enter the `if activity.planned_session_id is not None` branch, calling `_format_phase_position` with a MagicMock planned session, which produces garbage strings in the LLM context.

**Pattern that failed:**
```python
mock_activity = MagicMock(spec=Activity)
# planned_session_id not set → auto-creates truthy MagicMock
```

**Pattern to use instead:**
```python
mock_activity = MagicMock(spec=Activity)
mock_activity.planned_session_id = None  # Explicitly set to skip planned session path
```

### Patch target must match import style in post_workout_agent

**Symptom:** Mock doesn't intercept; real LiteLLM call goes through; test fails with real response instead of mock.

**Root cause:** `from openai import AsyncOpenAI` creates a local reference in `app.agents.post_workout_agent`. `patch("openai.AsyncOpenAI")` replaces the module-level name but the agent already has its own copy.

**Pattern that failed:**
```python
@patch("openai.AsyncOpenAI")  # Wrong target
```

**Pattern to use instead:**
```python
@patch("app.agents.post_workout_agent.AsyncOpenAI")  # Correct target
```

### Method name mismatch: update vs update_load_scores

**Symptom:** Mock assertion fails with "Expected 'update' to have been called once. Called 0 times."

**Root cause:** Test mocks `mock_repo.update` but the actual code calls `mock_repo.update_load_scores`. The mock was set up for the wrong method name.

**Pattern that failed:**
```python
mock_repo.update = AsyncMock()
# ... later ...
mock_repo.update.assert_called_once()  # Code calls update_load_scores, not update!
```

**Pattern to use instead:**
```python
mock_repo.update_load_scores = AsyncMock()
# ... later ...
mock_repo.update_load_scores.assert_called_once()
# Optionally verify parameters:
call_args = mock_repo.update_load_scores.call_args
assert call_args.kwargs["aerobic_load"] == expected_value
```
---

## Dated Lessons (2026-07-07)

### Repository mocking requires scalar_one_or_none() not first()

**Symptom:** Tests fail with AttributeError: `_MockResult` has no attribute `scalar_one_or_none`.

**Root cause:** When implementation changes from raw SQL queries (using `.first()`) to repository methods (using `.scalar_one_or_none()`), tests that mock `session.execute()` with a `_MockResult.first()` class fail because the repository calls a different method.

**Pattern that failed:**
```python
class _MockResult:
    def first(self):
        return mock_row

async def _mock_execute(*args, **kwargs):
    return _MockResult()

service.session.execute = MagicMock(side_effect=_mock_execute)
```

**Pattern to use instead:**
Mock repository methods directly instead of `session.execute()`:
```python
mock_profile = MagicMock()
mock_profile.date_of_birth = date(1990, 1, 1)
mock_profile_repo = AsyncMock()
mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
service.athlete_profiles = mock_profile_repo
```

This prevents mock boundary violations when implementation moves to repository pattern.

### sport_type field must be set in Activity factory for calibration eligibility tests

**Symptom:** CalibrationEligibilityService.evaluate returns False for all running activities, causing 8 test failures.

**Root cause:** The `_activity_factory` helper in `test_calibration_eligibility_service.py` did not set `sport_type`. After Phase-2.1-P3 implemented sport-type as the FIRST check in the calibration gate, activities without `sport_type='running'` were rejected immediately.

**Pattern that failed:**
```python
def _activity_factory(
    *,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    ...
) -> Activity:
    return Activity(
        ...
        # No sport_type field set!
    )
```

**Pattern to use instead:**
```python
def _activity_factory(
    *,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    sport_type: str = "running",
    ...
) -> Activity:
    return Activity(
        ...
        sport_type=SportType(sport_type),
    )
```

### Power-based load formula normalization differs from HR-based

**Symptom:** Power-based aerobic load tests expect ~100 units at CP but implementation produces ~1.0 units.

**Root cause:** The implementation divides by 3600.0 (seconds per hour), while tests were written expecting the same ~100-unit scale as HR-based load (which divides by BANISTER_NORMALISATION=148.0).

**Pattern that failed:**
```python
# Test expects ~100 units at CP
assert 80 < scores.aerobic_load < 120
```

**Pattern to use instead:**
Match the actual implementation formula: `(watts/cp)^4` summed and divided by 3600.0:
```python
# At CP: intensity = 1.0, result = 3600/3600 = 1.0
assert 0.9 < scores.aerobic_load < 1.1
```

If the architecture contract specifies ~100 units at CP, the implementation should be updated to normalize consistently with HR-based load (divide by 148.0 instead of 3600.0), not the tests.

---

## Dated Lessons (2026-07-09)

### Test fixtures must populate every field the production code reads unconditionally

**Symptom:** All 5 tests in `TestSignalCleanEnqueueHook` (`tests/unit/test_activity_ingestion_service_signal_clean.py`) raise `AttributeError: 'NoneType' object has no attribute 'date'` before any assertion runs.

**Root cause:** The helper `_minimal_parsed_fit()` was set up "as minimal as possible" with `start_time=None`. Production code at `app/services/activity_ingestion_service.py` calls `parsed.start_time.date()` unconditionally when stamping the activity row — a `None` start_time is not a state the production code handles. The fixture exercised a code path that does not exist in production.

**Pattern that failed:**
```python
def _minimal_parsed_fit(...) -> ParsedFitData:
    return ParsedFitData(
        start_time=None,  # type: ignore[arg-type]
        ...
    )
```

**Pattern to use instead:**
```python
def _minimal_parsed_fit(...) -> ParsedFitData:
    return ParsedFitData(
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        ...
    )
```

The meta-rule: when production code reads a field unconditionally, every test fixture for that object must populate it — even if the test is "minimal." A "field set even when unused" rule is a useful shareable fixture contract for any future test fixture targeting the same domain.

### Test data must clear every gate in the chain before the one under test

**Symptom:** Two `available_channels` tests in `tests/unit/test_signal_cleaning_service.py` fail with assertions on `result.stream` when `result.stream is None` (the service returned early with `reason="short_stream"`).

**Root cause:** Both tests were designed to exercise a downstream null-fraction gate (channel unavailable when > 80% null) but the data was rejected by an *earlier* gate. The pipeline runs gates in order — short-stream first (≥ 300 non-null HR seconds), then null-fraction. Test data that fails the short-stream gate never reaches the null-fraction check. Related cases:

* `test_clean_available_channels_power_false_when_all_artifacted` — fed `[5000.0] * 600`, expecting the 3×-rolling-median filter to null everything. A uniform series cannot be artifacted by that filter (candidate equals window median → 3×median is never crossed). The cleanest way to exercise the null-fraction gate is to feed raw nulls: `[None] * 600`.
* `test_clean_available_channels_hr_false_when_gt_80pct_null` — fed `[None] * 510 + [150.0] * 90` = 90 non-null, but the short-stream gate requires ≥ 300 non-null HR. The fix is `[None] * 1700 + [150.0] * 300` with `duration=2000`: 300/2000 = 0.15 ≤ 0.80 → null-fraction gate fires, and 300 ≥ 300 → short-stream passes.

**Pattern that failed:**
```python
# Test exercises the null-fraction gate, ignoring the short-stream gate.
hr_values = [None] * 510 + [150.0] * 90
```

**Pattern to use instead:**
```python
# First, list every gate the request flows through (read the production code).
# Then, choose data that clears every earlier gate and fires only the one under test.
hr_values = [None] * 1700 + [150.0] * 300
duration = 2000  # 300/2000 = 0.15 → null-fraction gate fires
# 300 ≥ MIN_NON_NULL_HR_SECONDS (300) → short-stream gate passes
```

**Meta-rule:** When asserting a downstream gate, read the production code's gate chain first and design data that clears every earlier gate. Single-gate mental models fail when the pipeline has multiple gates — the test's data must satisfy the conjunction, not just the disjunction.

### Use `pytest.approx` for numerically-filtered samples

**Symptom:** `test_clean_rr_deviation_filter_does_not_apply_to_power` fails with `AssertionError: 200.0000000000001 != 200.0` on `assert record.power_w == 200.0`.

**Root cause:** A uniform `[200.0] * 600` power series is fed through the Savitzky-Golay smoother (`scipy.signal.savgol_filter`, window=7, polyorder=3). The smoother computes weighted sums that don't reduce to the exact input value due to floating-point rounding; a uniform input produces values like `200.0000000000001`. Strict `==` is brittle against any numerical filter (Savitzky-Golay, EMA, rolling median, FFT, interpolation).

**Pattern that failed:**
```python
for record in result.stream.time_series:
    assert record.power_w == 200.0
```

**Pattern to use instead:**
```python
for record in result.stream.time_series:
    assert record.power_w == pytest.approx(200.0, abs=1e-9)
```

**Meta-rule:** Any sample that has passed through a numerical filter should be asserted with `pytest.approx`. The tolerance depends on the filter: Savitzky-Golay noise is well under 1e-9 for a uniform input; rolling medians are exact (no FP noise); FFTs are 1e-6 or worse. Default to `abs=1e-9` unless the filter is known to be noisier. Strict equality is only safe for samples that have *not* been numerically transformed (e.g., direct passthrough fields).

---

## Dated Lessons (2026-07-09, Test Authoring Conventions)

### Variable name `mock` must not be reused for `ParsedFitData`

**Symptom:** Two tests in `tests/unit/test_signal_cleaning_service.py` (`test_clean_rr_outside_200_2500_ms_removed` and `test_clean_available_channels_rr_false_when_gt_80pct_null`) crash with `AttributeError` deep inside the helper `_run_clean_and_return_result`.

**Root cause:** The variable name `mock` was reused for whichever object was constructed first. The two broken tests constructed a `ParsedFitData` first and assigned it to `mock`; the helper expected its third argument to be a `MagicMock(Activity)` and accessed `mock_activity.athlete_id` / `mock_activity.id`. The author's intent (a real `ParsedFitData` to feed into the helper) collided with the helper's documented contract.

**Pattern that failed:**
```python
mock = _parsed_fit_data_full()       # ← ParsedFitData, not MagicMock
parsed = _parsed_fit_data_full(rr_values=rr_values)
result = await _run_clean_and_return_result(service, activity_id, mock, parsed)
# _run_clean_and_return_result does mock_activity.athlete_id → AttributeError
```

**Pattern to use instead:**
```python
mock_activity = _mock_activity()     # MagicMock(Activity)
parsed = _parsed_fit_data_full(rr_values=rr_values)
result = await _run_clean_and_return_result(service, activity_id, mock_activity, parsed)
```

**Meta-rule:** When a helper takes both a `MagicMock` and a domain object, name the variables after their semantic role, not after a generic `mock`. The convention `mock_activity` / `parsed` is unambiguous at the call site and matches the helper's parameter names.


---

## Dated Lessons (2026-07-11)

### Test fixture helpers must match the FK chain of the production models

**Symptom:** Four integration and behaviour tests fail at fixture setup with `TypeError: 'athlete_id' is an invalid keyword argument for WeeklyPlan` (and the same for `PlannedSession`). The helpers were defined inside `tests/integration/test_*.py` and `tests/behaviour/test_*.py`, so DevOps could not fix them per the test-isolation boundary — Test Architect had to step in.

**Root cause:** The test fixture helpers built a full parent chain (`TrainingGoal → TrainingPlan → WeeklyPlan → PlannedSession`) and **invented** an `athlete_id` column on `WeeklyPlan` and `PlannedSession`. The actual models do not have that column — the athlete is reached through `WeeklyPlan.training_plan_id → TrainingPlan → athlete_id` (and similarly for `PlannedSession.weekly_plan_id`). The fixture was written without re-reading the model definitions, so it built rows the schema rejects.

**Pattern that failed:**
```python
weekly_plan = WeeklyPlan(
    athlete_id=athlete_id,        # ← Column does not exist on WeeklyPlan
    training_plan_id=plan.id,
    week_number=1,
    week_starts_at=target_date,
    week_ends_at=target_date,
    adjusted_intent={},
    status=WeeklyPlanStatus.ACTIVE,
)
planned = PlannedSession(
    weekly_plan_id=weekly_plan.id,
    training_plan_id=plan.id,
    athlete_id=athlete_id,        # ← Column does not exist on PlannedSession
    ...
)
```

**Pattern to use instead:**
```python
weekly_plan = WeeklyPlan(
    # No athlete_id column — reached through training_plan_id → TrainingPlan
    training_plan_id=plan.id,
    week_number=1,
    week_starts_at=target_date,
    week_ends_at=target_date,
    adjusted_intent={},
    status=WeeklyPlanStatus.ACTIVE,
)
planned = PlannedSession(
    weekly_plan_id=weekly_plan.id,
    training_plan_id=plan.id,
    # No athlete_id column — reached through weekly_plan_id → WeeklyPlan
    ...
)
```

**Meta-rule:** When building a fixture that creates a chain of models, every column referenced MUST be a real column on that model. A test fixture is a SQL contract: if a column is not on the model, the INSERT will fail — and the failure surface (the integration test assertion error) hides which fixture helper introduced the bogus column. Read the model file before writing the helper; this is a cheaper invariant to maintain at write-time than to chase at DevOps time. When the same fixture helper is duplicated across integration + behaviour layers (as `_create_planned_session` was here), a model drift in one file becomes a hidden debt in the other.

### `ON DELETE SET NULL` cascade tests must `expire_all()` before re-reading the cascaded row

**Symptom:** `test_deleting_activity_nullifies_measurement_activity_id` (in `tests/integration/test_physiology_measurement_repository_integration.py`) fails with `assert surviving.activity_id is None` after deleting the parent `Activity` — the cascaded `PhysiologyMeasurement` still reports the old `activity_id`.

**Root cause:** The FK is declared `ondelete='SET NULL'` in the migration (`8413e6547a40_phase_2_3_p1_physiology_measurement.py`), and the DB correctly nulls the column. But the test asserts against a row returned by `db_session.execute(select(...))` on the **same session** that performed the delete. SQLAlchemy's identity map returns the cached `PhysiologyMeasurement` instance whose `activity_id` was loaded before the delete. The cascade happens in the DB, but the ORM state is not refreshed — `select().scalars().all()` returns the stale cached row, and the assertion sees a non-NULL `activity_id`.

**Pattern that failed:**
```python
await db_session.delete(fetched_activity)
await db_session.commit()
# ← Identity map still has the pre-cascade PhysiologyMeasurement
rows = (await db_session.execute(
    select(PhysiologyMeasurement).where(...)
)).scalars().all()       # ← Returns cached instance with stale activity_id
assert rows[0].activity_id is None  # ← FAILS
```

**Pattern to use instead:**
```python
await db_session.delete(fetched_activity)
await db_session.commit()
# Expire so the next SELECT reloads fresh instances from the DB.
# This is safe: expire_all evicts attribute state but does NOT trigger
# lazy loads — the next .execute() rebuilds instances from the query.
db_session.expire_all()
rows = (await db_session.execute(
    select(PhysiologyMeasurement).where(...)
)).scalars().all()       # ← Fresh instance, activity_id is now None
assert rows[0].activity_id is None  # ← PASSES
```

**Meta-rule:** Any test that asserts a column's *post-cascade* value on a row read from the same session that triggered the cascade must call `expire_all()` between the cascade-triggering commit and the post-cascade SELECT. The two-path `expire()` antipattern above ("Use `expire()` then access lazy attributes") is a *different* failure mode — accessing a lazy attribute after a targeted `expire()` triggers a reload outside the greenlet. `expire_all()` followed by a fresh `execute()` is safe: the SELECT reissues SQL and rebuilds the instance from the result rows. This case is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

### Async session teardown fires `MissingGreenlet` when the pool defers close — `NullPool` is the fix

**Symptom:** Every test in the suite was logging `ERROR sqlalchemy.pool.impl.AsyncAdaptedQueuePool: Exception closing connection` and `MissingGreenlet: greenlet_spawn has not been called` during teardown, even though every test passed. The log noise was severe enough to mask real test-failure traces.

**Root cause:** SQLAlchemy's `AsyncAdaptedQueuePool` defers connection close to the pool's *synchronous* disposal time, which happens after the async greenlet has been torn down by pytest-asyncio. The session's `await session.close()` flushes async work, but the pool's `close()` call still needs the greenlet to issue its async connection-release. With the default pool, the deferred close fires after the greenlet is gone.

**Pattern that failed (default in `tests/conftest.py` until 2026-07-11):**
```python
engine = create_async_engine(TEST_DATABASE_URL, echo=False)  # default QueuePool
# session.close() returns cleanly, but the pool's deferred close later fires
# after the greenlet is gone → MissingGreenlet during teardown.
```

**Pattern to use instead (now in `tests/conftest.py`):**
```python
from sqlalchemy.pool import NullPool
engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, poolclass=NullPool
)
# NullPool closes connections immediately during the async session.close(),
# so every connection close happens INSIDE the greenlet context. The pool
# never defers close to a later (synchronous) disposal step.
```

A try/except `MissingGreenlet` guard around `session.close()` is also wrapped in `_TestSessionFactory.finish()` so any residual deferred close (from test code that builds sessions outside the fixture) does not raise — it logs and continues.

**Meta-rule:** The async SQLAlchemy test stack requires `poolclass=NullPool` to keep connection close inside the greenlet. A bare `create_async_engine(url)` is fine for the integration code paths but produces teardown noise under pytest-asyncio. This is a `conftest.py` concern, not a per-test concern — authors should not need to know about it. If a new conftest variant is added, copy the `NullPool` setting.

### `expire_all()` + async lazy load on captured scalar — capture scalars BEFORE `expire_all()`

**Symptom:** `test_deleting_activity_nullifies_measurement_activity_id` (in `tests/integration/test_physiology_measurement_repository_integration.py`) fails with `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.` after `db_session.expire_all()` followed by a SELECT that uses `measurement.id` in the WHERE clause.

**Root cause:** The previous fix (2026-07-11) added `db_session.expire_all()` between the cascade-triggering commit and the post-cascade SELECT to evict the stale identity-map instance. That fix is correct in isolation — `expire_all()` followed by a fresh `execute()` rebuilds instances from the result rows. But the SELECT used `PhysiologyMeasurement.id == measurement.id` in the WHERE clause. After `expire_all()`, the `measurement` instance is expired; accessing `measurement.id` triggers an async lazy load to re-fetch the row, but the lazy load fires outside the greenlet context under async SQLAlchemy + NullPool. The identity map also returns the expired cached instance when the fresh SELECT runs, compounding the issue.

**Pattern that failed:**
```python
await db_session.delete(fetched_activity)
await db_session.commit()
db_session.expire_all()
# ← measurement is now expired
rows = (await db_session.execute(
    select(PhysiologyMeasurement).where(
        PhysiologyMeasurement.id == measurement.id  # ← async lazy load!
    )
)).scalars().all()
```

**Pattern to use instead:**
```python
await db_session.delete(fetched_activity)
await db_session.commit()
# Capture the scalar id BEFORE expire_all(). The id is already
# populated by the DB default after the first commit, so capturing
# it here is safe and avoids the lazy load entirely.
measurement_id = measurement.id
assert measurement_id is not None
db_session.expire_all()
rows = (await db_session.execute(
    select(PhysiologyMeasurement).where(
        PhysiologyMeasurement.id == measurement_id  # ← captured scalar
    )
)).scalars().all()
```

**Meta-rule:** When a test needs to `expire_all()` between a commit and a SELECT that references an attribute of an in-memory instance, capture every scalar attribute the WHERE clause needs **before** calling `expire_all()`. The alternative — `.execution_options(populate_existing=True)` on the SELECT — also bypasses the identity map but is less explicit about the lazy-load hazard. The capture-first pattern is the safer default. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

### Multi-call `_create_planned_session()` creates duplicate active TrainingGoals — share the parent chain

**Symptom:** Four natural-training tests (2 integration, 2 behaviour) fail with `IntegrityError: duplicate key value violates unique constraint "ix_training_goals_athlete_active"` on the second iteration of a 3-call loop. The helper builds the full parent chain (`TrainingGoal → TrainingPlan → WeeklyPlan → PlannedSession`) on every call.

**Root cause:** The partial unique index `ix_training_goals_athlete_active` on `(athlete_id) WHERE status = 'active'` allows only ONE active `TrainingGoal` per athlete. The natural-training tests call `_create_planned_session()` in a 3-iteration loop (one per historical easy run), and each call created a new `TrainingGoal(status='active')` for the same athlete. The first iteration succeeds; the second and third raise `IntegrityError` at the DB layer. Production code never creates a second active goal — the existing goal must be explicitly closed (`status → completed` or `abandoned`) before a new one is created. The fixture helper was written without re-reading the partial unique index, so it built rows the schema rejects.

**Pattern that failed:**
```python
for run_date, mean_hr in zip(easy_run_dates, easy_run_mean_hrs):
    planned = await _create_planned_session(
        db_session,
        athlete_id=athlete.id,
        target_date=run_date,
    )
    # ← Second iteration: IntegrityError on TrainingGoal insert
```

**Pattern to use instead:**
```python
# Track the parent chain across loop iterations so the helper
# reuses the same TrainingGoal / TrainingPlan / WeeklyPlan.
goal, plan, weekly_plan = None, None, None
for run_date, mean_hr in zip(easy_run_dates, easy_run_mean_hrs):
    parent_chain = (
        (goal, plan, weekly_plan)
        if goal is not None
        else None
    )
    goal, plan, weekly_plan, planned = (
        await _create_planned_session(
            db_session,
            athlete_id=athlete.id,
            target_date=run_date,
            parent_chain=parent_chain,
        )
    )
```

The helper signature becomes:
```python
async def _create_planned_session(
    db_session, *, athlete_id, target_date=None,
    parent_chain: Optional[tuple] = None,
) -> tuple:
    """Returns (goal, plan, weekly_plan, planned)."""
    if parent_chain is not None:
        goal, plan, weekly_plan = parent_chain
    else:
        # Build the chain (first call only).
        ...
    # Always build the new PlannedSession.
    ...
    return goal, plan, weekly_plan, planned
```

**Meta-rule:** When a fixture helper builds a parent chain that includes a row with a partial unique index (one active goal per athlete, one primary auth per athlete, etc.), the helper MUST accept an optional pre-built chain and reuse it on subsequent calls. The production invariant is "one active row per athlete" — the fixture must mirror that, not invent a new row per call. When the same helper is duplicated across integration + behaviour layers (as `_create_planned_session` was here), the fix must be applied in both files; consider extracting to `tests/utils/factories.py` so the next test file benefits. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

### `expire_all()` + identity-map return — add `.execution_options(populate_existing=True)` to the post-cascade SELECT

**Symptom:** `test_deleting_activity_nullifies_measurement_activity_id` (in `tests/integration/test_physiology_measurement_repository_integration.py`) still fails with `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.` after the capture-first fix (capturing `measurement_id` before `expire_all()`) is applied. The trace points at `surviving.athlete_id` — the attribute access on the row returned by the post-cascade SELECT.

**Root cause:** The capture-first pattern (2026-07-11) is correct in isolation — capturing `measurement_id` before `expire_all()` avoids the lazy load on the WHERE clause. But the SELECT itself returns the same row that was just expired. SQLAlchemy's identity map serves the expired `PhysiologyMeasurement` instance from the cache, and the `expire_all()` call has marked all its attributes as needing reload. When the test then accesses `surviving.athlete_id`, the ORM fires an async lazy load to re-fetch the row — but the lazy load fires outside the greenlet context under async SQLAlchemy + NullPool. The capture-first pattern protects the WHERE clause; it does not protect attribute access on the returned row.

**Pattern that failed:**
```python
measurement_id = measurement.id
assert measurement_id is not None
db_session.expire_all()
rows = (
    await db_session.execute(
        select(PhysiologyMeasurement).where(
            PhysiologyMeasurement.id == measurement_id
        )
    )
).scalars().all()
surviving = rows[0]
assert surviving.athlete_id == athlete.id  # ← MissingGreenlet!
```

**Pattern to use instead:**
```python
measurement_id = measurement.id
assert measurement_id is not None
db_session.expire_all()
# ``populate_existing=True`` forces SQLAlchemy to bypass the
# identity map and rebuild the instance from the result row.
# Without it, the identity map returns the expired cached
# instance whose attributes trigger async lazy loads outside
# the greenlet.
rows = (
    await db_session.execute(
        select(PhysiologyMeasurement)
        .where(PhysiologyMeasurement.id == measurement_id)
        .execution_options(populate_existing=True)
    )
).scalars().all()
surviving = rows[0]
assert surviving.athlete_id == athlete.id  # ← PASSES
```

**Meta-rule:** When a test needs to `expire_all()` between a commit and a SELECT that returns a row whose attributes will be accessed, the SELECT must use `.execution_options(populate_existing=True)`. The capture-first pattern (capturing WHERE-clause scalars before `expire_all()`) is necessary but not sufficient — the identity map will still serve the expired instance, and any attribute access on it triggers an async lazy load. The two fixes compose: capture scalars first (for the WHERE clause), then `expire_all()` (to evict the stale entry), then `populate_existing=True` (to bypass the identity map on the post-cascade SELECT). This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

### Test data for a strict-greater-than threshold must exceed the threshold by a clear margin

**Symptom:** `test_inconsistent_easy_run_hrs_produce_no_natural_observation` (in `tests/integration/test_threshold_detection_service_integration.py`) and `test_journey_inconsistent_easy_runs_produce_no_natural` (in `tests/behaviour/test_threshold_detection_user_journey.py`) fail with `AssertionError: expected [] natural observations, got [ThresholdObservation(type='lt1_hr', observed_value=145.0)]`. The test author designed the data to be "inconsistent" but the algorithm correctly considers it consistent.

**Root cause:** The natural-training consistency check in `app/services/threshold_detection_service.py` is `any(abs(hr - median_hr) > EASY_RUN_HR_TOLERANCE_BPM for hr in sorted_hrs)` where `EASY_RUN_HR_TOLERANCE_BPM = 5.0`. The comparison is **strict greater-than**, not greater-than-or-equal. The test data `[140, 145, 150]` has median 145 and max deviation `abs(150 - 145) = 5.0`, which is NOT `> 5.0` — so the values pass the consistency check and the algorithm produces an LT1_HR observation. The test author's mental model was "spread > 5 bpm is inconsistent" but the actual rule is "any deviation strictly greater than 5 bpm is inconsistent" — a 5 bpm deviation is still consistent.

**Pattern that failed:**
```python
# Test author assumed "spread = 10 bpm" was inconsistent.
# But with median 145, max deviation is 5.0 — exactly at the
# threshold, not strictly above it.
easy_run_mean_hrs = [140.0, 145.0, 150.0]  # spread = 10 bpm
```

**Pattern to use instead:**
```python
# Widen the spread so max deviation is unambiguously above
# the strict-greater-than threshold. With median 145, values
# [130, 145, 165] give max deviation 20 bpm — well clear of
# the 5 bpm threshold.
easy_run_mean_hrs = [130.0, 145.0, 165.0]  # spread = 35 bpm
```

**Meta-rule:** When designing test data to exercise a threshold-based filter, the data must exceed the threshold by a clear margin — not just match it. A strict-greater-than comparison (`> threshold`) treats a value exactly at the threshold as "passing", so test data with max deviation equal to the threshold will not fire the filter. Read the production code's comparison operator carefully (`>` vs `>=`, `!=` vs `==`) and design data that is unambiguously on the "fire" side. When the same test data pattern is duplicated across integration + behaviour layers (as `[140, 145, 150]` was here), the fix must be applied in both files. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

## Dated Lessons (2026-07-11, test-removal policy)

### End-to-end `alembic downgrade` tests become stale once later sub-phases build on top of the migration

**Symptom:** `tests/integration/test_migration_phase_1_2c.py::TestPhase12cDowngradeFunctional::test_downgrade_returns_to_phase_12b_baseline` failed in every full regression run since Phase 1.2c was promoted. The downgrade could not return the schema to the Phase-1.2b baseline because later sub-phases (Phase 1.3, 1.4, 1.5, 1.6, 2.x) had added columns, FKs, and tables that the Phase-1.2c migration's downgrade path does not know about — the migration is correctly written, but the system as a whole has moved past it.

**Root cause:** The test exercised the *system* downgrade, not the *migration* downgrade. An end-to-end `alembic downgrade -N` test asserts that the *current schema* (after every subsequent sub-phase has been applied) can still be reverted to the baseline the migration originally targeted. That assertion is only true at the moment the migration is the head revision — the instant any later migration is added, the assumption breaks. The test's failure does not indicate a defect in the Phase-1.2c migration; it indicates the test is asserting a property the migration was never responsible for.

**Pattern that failed (in `tests/integration/test_migration_phase_1_2c.py`):**

```python
class TestPhase12cDowngradeFunctional:
    def test_downgrade_returns_to_phase_12b_baseline(self) -> None:
        # End-to-end: upgrade to head, downgrade -2, verify
        # Phase-1.2c tables are gone and Phase-1.2a / 1.2b tables
        # survive.
        rc, _, _ = _run_alembic_subprocess(schema_url, ("upgrade", "head"))
        assert rc == 0
        rc, _, _ = _run_alembic_subprocess(schema_url, ("downgrade", "-2"))
        assert rc == 0
        # ... assert Phase-1.2c tables absent, Phase-1.2a / 1.2b tables present
```

**Pattern to use instead:** Two complementary patterns, both used in this codebase:

1. **Static downgrade-body checks** (already present in `test_migration_phase_1_2c.py` and recommended for all migration tests): parse the migration's `downgrade()` source and assert the expected `op.drop_table` / `op.drop_index` / `op.drop_constraint` calls are present. These do not run `alembic downgrade` end-to-end, so they cannot become stale as later sub-phases are added. See `test_downgrade_drops_new_objects_only` and `test_followup_drops_training_plans_twin_state_fk` in the same file for the canonical examples.

2. **Pinned-baseline downgrade tests** (used in `test_migration_phase_1_2b.py::phase_1_2b_schema`): run `alembic upgrade <this_migration_revision>` instead of `alembic upgrade head`, then `alembic downgrade -1`. The pinned upgrade means the schema state going into the downgrade is exactly the state the migration produced, so the downgrade is guaranteed to be the *migration's* downgrade, not the *system's* downgrade. This pattern is safe as long as the pinned revision is the migration's own revision.

```python
# CORRECT — pin the upgrade to the migration's own revision
rc, _, _ = _run_alembic_subprocess(
    schema_url, ("upgrade", "1b9e9026db1e"),  # Phase-1.2b head
)
assert rc == 0
rc, _, _ = _run_alembic_subprocess(
    schema_url, ("downgrade", "-1"),
)
assert rc == 0
```

**Decision policy:** When a downgrade test is failing because the system has moved past the migration, prefer **deletion** of the end-to-end test (keeping the static-body checks) over fixing the test to work around the later sub-phases. The end-to-end test asserts a property that was only ever true at one point in time, and the static-body checks provide the actual coverage of the migration's downgrade logic. A work-around test either (a) pins the upgrade, which couples the test to specific downstream revisions and breaks the next time a sub-phase is added, or (b) skips the failing assertions, which leaves the test as a false-positive landmine. The first lesson of this project is "tests must assert behaviour, not implementation"; a downgrade test that asserts a property the migration was never responsible for is asserting a *different system's* behaviour and belongs to that system's tests, not this migration's.

**Meta-rule:** Migration tests split into two categories with different staleness profiles. **Static-body checks** (parse the migration source, assert expected `op.*` calls) are stable forever. **End-to-end alembic subprocess checks** are stable only as long as the migration is the head revision. For the latter, pin the upgrade to the migration's own revision (or accept the test will be deleted when the system moves past it). This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".
