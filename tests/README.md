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
