# Pheidipp Test Infrastructure Guide

## Overview

This directory contains the test suite for the Pheidipp backend. Tests are organized into:
- `unit/` — Isolated unit tests (no database)
- `integration/` — Integration tests with database (transactional)
- `api/` — HTTP API tests using FastAPI test client
- `behaviour/` — End-to-end user journey tests
- `utils/` — Shared test utilities and helpers

This is the **guide**: shared utilities, test isolation, test patterns,
Common Pitfalls, and the canonical Dated Lessons (symptom, root cause,
code blocks, meta-rules). The companion **contract** —
`tests/MOCKING_CONTRACT.md` — is the source of truth for layer boundaries,
canonical fixtures, and the Known Anti-Patterns table; the contract's
table rows point back to the H3 titles of the dated lessons below.
Operational guidance (how to run the suite, common failure-symptom fixes)
lives in `tests/RUNNING.md`.

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
from tests.utils.factories import make_athlete, make_auth, make_activity, make_refresh_token

athlete = await make_athlete(db_session)
auth = await make_auth(db_session, athlete_id=athlete.id)
activity = await make_activity(db_session, athlete_id=athlete.id, activity_date=date(2026, 6, 15))
token = await make_refresh_token(db_session, athlete_id=athlete.id)
```

`make_activity` defaults to `ActivitySource.MANUAL_UPLOAD` and `SportType.RUNNING`
— the minimum field set the calibration-eligible / sport-type / signal
gates need. Tests that need a different source or sport pass them in via
kwargs.

### `tests/utils/http_helpers.py`

Async HTTP helpers for behaviour tests:

```python
from tests.utils.http_helpers import bearer_header, http_register

athlete_id, access_token = await http_register(
    client, f"behaviour-{uuid.uuid4()}@example.com"
)
headers = bearer_header(access_token)
# Use `headers=` on subsequent httpx calls.
```

`bearer_header(token)` builds the `{"Authorization": "Bearer <token>"}` header.
`http_register(client, email)` runs the standard register HTTP call and
returns `(athlete_id, access_token)`.

### `tests/utils/assertions.py`

Shared assertion patterns for security and domain invariants:

```python
from tests.utils.assertions import assert_no_secrets_in_text, assert_no_secrets_in_logs, SECRET_LEAKAGE_FIELDS

assert_no_secrets_in_text(response_text)
assert_no_secrets_in_logs(log_records)
```

**Forbidden fields checked:** `hashed_password`, `token_hash`, `provider_tokens`, `provider_user_id`, `password`.

## Migration from Inline Helpers

All inline schema-inspection helpers (`_columns()`, `_indexes()`,
`_sync_url()`, etc.) have been consolidated into
[`tests/utils/schema_helpers.py`](Shared Utilities) and
[`tests/utils/model_helpers.py`](Shared Utilities). New tests MUST use the
shared helpers; legacy inline copies are a code-review blocker. The
"Schema Inspection in Async Tests" section below explains the underlying
constraint (asyncpg cannot service sync `inspect()` calls from a greenlet
context) that motivated the consolidation.

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

**Related dated lessons** (more specific cases of the same hazard):
- "`expire_all()` + async lazy load on captured scalar — capture scalars BEFORE `expire_all()`" (2026-07-11) — the `expire_all()` + WHERE-clause variant of this failure
- "`expire_all()` + identity-map return — add `.execution_options(populate_existing=True)` to the post-cascade SELECT" (2026-07-11) — the identity-map variant
- "Post-rollback ORM attribute access triggers `MissingGreenlet` — use column-level SELECT for JSONB reads" (2026-07-14, pass 2) — the `rollback()` (not `expire_all()`) variant
- "Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`" (2026-07-14, pass 3) — the `rollback()` + WHERE-clause variant

All four trigger `MissingGreenlet` for the same family of reasons but have different fix patterns; read the specific lesson for the case at hand.

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

## Test Patterns — JWT Token Uniqueness

This section is a **test-design** pattern (how to write robust assertions
around token rotation), not a mocking concern. For mocking rules around
JWT issuance, see `tests/MOCKING_CONTRACT.md` "Layer Boundaries" → Unit
and the `password_hasher` / `token_service` fixtures in the Canonical
Fixtures table.

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

For operational guidance (how to run the suite, common failure-symptom
fixes) see `tests/RUNNING.md`. For the mocking contract (layer
boundaries, canonical fixtures, Known Anti-Patterns table) see
`tests/MOCKING_CONTRACT.md`.

## See Also

- `tests/MOCKING_CONTRACT.md` — the mocking contract: layer boundaries, canonical fixtures, Known Anti-Patterns table, Change Log.
- `tests/RUNNING.md` — operational guide: how to run the suite, common failure symptoms and fixes.
- `conftest.py` — fixture definitions and cleanup logic.
- `pytest.ini` — pytest configuration.
- `docs/vision/` — product vision and constraints.
- `docs/adr/` — architecture decision records.

---

## Dated Lessons

### Mocked `Repository.insert()` must simulate database PK assignment — set `state.id = uuid.uuid4()` in the `side_effect`

**Date:** 2026-07-19 (oneoff-unitary-validation re-analysis)

**Symptom:** Tests that assert on a payload field derived from `str(inserted.id)` (e.g. `payload["twin_state_id"]`) fail with `AssertionError: 'None' == '<expected-uuid>'` even though the test sets up every other aspect of the insert correctly. Affected: 2 unit tests in `tests/unit/test_twin_recalibration_service_event_firing.py` (`TestTwinRecalibratedPayload::test_payload_includes_required_fields`, `TestTwinConfidenceUpgradedPayload::test_payload_includes_required_fields`) — both asserting `payload["twin_state_id"] == str(result_state.id)` where `result_state` was the placeholder passed via `inserted_state=` and the service builds a fresh `new_state` whose `id` is `None` at insert time.

**Root cause:** The repository's real `insert()` calls `session.add(state)` followed by `await session.flush()` and `await session.refresh(state)`. The flush causes the database to assign a primary key (`state.id`), and the refresh re-reads the row so the in-memory instance carries the new id. A mock with `side_effect=lambda state: state` returns the same object by identity (which is what the service's dedup short-circuit depends on — `inserted is new_state` must be `True`) but does NOT simulate the database's PK assignment. The service then passes `inserted` to the event-publisher, whose payload builder does `str(inserted.id)` → `"None"`. Tests that only check `previous_twin_state_id` (sourced from `previous.id`, which IS pre-configured in the test setup) pass; tests that check `twin_state_id` (sourced from `inserted.id`, which is `None`) fail.

**Pattern that failed** (in `tests/unit/test_twin_recalibration_service_*.py`, `_make_service` helper):

```python
# The repository's real ``insert`` returns the same object that
# was passed in (after flush + refresh), preserving identity.
def _return_inserted(state: Any) -> Any:
    return state
# ← service reads `inserted.id` for the event payload → "None"
```

**Pattern to use instead** (one-line addition in `_return_inserted`):

```python
# The repository's real ``insert`` returns the same object that
# was passed in (after flush + refresh), preserving identity AND
# assigning ``state.id`` from the database. Mirroring both here so
# the dedup short-circuit's identity check still sees
# ``inserted is new_state`` → True AND any caller that reads
# ``inserted.id`` (e.g. event payloads that include
# ``twin_state_id``) gets a real UUID.
def _return_inserted(state: Any) -> Any:
    state.id = uuid.uuid4()
    return state
```

**Meta-rule:** Any unit test that mocks a repository's `insert()` and where the service under test reads `inserted.<pk_field>` (e.g. for an event payload, response body, or log line) MUST simulate the database's PK assignment inside the `side_effect`. The minimum sufficient simulation is to set the PK field to a fresh `uuid.uuid4()` on the state object before returning it. The mock must still return the same object by identity (for any dedup short-circuit), so do NOT replace `side_effect=lambda s: s` with a separate return-value object — mutate the passed-in state in place. This applies to every repository in `app/repositories/` whose `insert()` calls `flush() + refresh()` on the session: `TwinStateRepository`, `AthletePhysiologyRepository`, `AthleteFitnessRepository`, `SystemEventRepository`, etc. — any test that mocks one of these and asserts on a payload derived from `inserted.id` will hit this exact failure. The fix is local to the test file's mock setup; no production change is required. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### `StrEnum.__eq__` silently accepts raw strings whose value matches a whitelist member — never expect an exception on a string "the service would reject"

**Date:** 2026-07-19 (oneoff-unitary-validation re-analysis)

**Symptom:** A test that calls a service validator with a raw string "the service would reject" and expects an exception (`pytest.raises(SomeError)`) fails with `DID NOT RAISE <SomeError>`. The service's reject branch is never entered because the membership test (`if goal_type not in {whitelist_member, ...}`) treats the string as equal to the enum member by value, evaluates to `False`, and the validator returns `None` silently. Affected: 1 unit test in `tests/unit/test_onboarding_service.py` (`test_validate_goal_type_rejects_unknown_value_textually`) which called `OnboardingService.validate_goal_type("race_event")` and expected `pytest.raises(AttributeError)`.

**Root cause:** `app/models/enums.py` declares `GoalType` as a `StrEnum`. `StrEnum.__eq__` compares by value: `GoalType.RACE_EVENT == "race_event"` is `True`. The validator's membership test `if goal_type not in {GoalType.RACE_EVENT, GoalType.TARGET_PERFORMANCE}` therefore succeeds for the raw string `"race_event"`, the `if` block is never entered, and the validator returns `None` without raising. This is the same mechanism behind the 2026-07-13 "`str(enum_member)` is NOT the `.value` for `class Foo(str, Enum)`" lesson, but in the opposite direction: that lesson was about *stringifying* an enum member and getting the qualified name; this lesson is about *comparing* a raw string to a `StrEnum` set and having the comparison succeed. The two lessons are related but distinct — the first is a `__str__` quirk, the second is a `__eq__` quirk. The reject path is unreachable in production anyway because the Pydantic schema layer enforces the enum type at the API boundary and rejects non-enum values with HTTP 422 before the service is called.

**Pattern that failed** (in `tests/unit/test_onboarding_service.py`):

```python
def test_validate_goal_type_rejects_unknown_value_textually(self) -> None:
    # Long comment explaining the expected AttributeError surface.
    with pytest.raises(AttributeError):
        OnboardingService.validate_goal_type(
            "race_event",  # type: ignore[arg-type]
        )
# ← DID NOT RAISE: StrEnum.__eq__ makes "race_event" match
#   GoalType.RACE_EVENT, which is in the whitelist.
```

**Pattern to use instead** (assert the actual behavior — silent acceptance, since `StrEnum.__eq__` is the production behavior):

```python
def test_validate_goal_type_strenum_equality_accepts_value_string(
    self,
) -> None:
    OnboardingService.validate_goal_type(
        "race_event",  # type: ignore[arg-type]
    )
# ← returns None silently: StrEnum.__eq__ makes "race_event"
#   match GoalType.RACE_EVENT, which is in the whitelist. The
#   test name describes the actual mechanism.
```

**Meta-rule:** A test that passes a raw string to a service method whose first argument is typed as a `StrEnum` and expects an exception (any exception, including `AttributeError` from a defensive `enum.value` access in the error path) will fail silently. `StrEnum.__eq__` makes the membership test succeed by value, the reject branch is never entered, and no exception is raised. The right test for this surface is to assert silent acceptance (the call returns `None`) — the test name should name the mechanism (e.g. `test_validate_goal_type_strenum_equality_accepts_value_string`) rather than the rejected path. Tests that want to verify the reject path must pass an actual non-matching value that is not the value of any whitelist member — but for service methods that type their argument as `StrEnum`, this path is unreachable in production (Pydantic rejects at the API boundary with HTTP 422), so the test has no production failure to guard against. Document the `StrEnum.__eq__` behavior in the test name and skip the `pytest.raises` block. This is related to but distinct from the 2026-07-13 `str(enum_member)` lesson (which is about `__str__`, not `__eq__`); both apply to any `StrEnum` in `app/models/enums.py` — `GoalType`, `TwinTrigger`, `TwinConfidenceLevel`, `DataTier`, etc.

---

### Integration `_state()` helper default date causes 23 failures when assertions assume same-day math

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run)

**Symptom:** After p-coder fixed the two Phase-2.3-P2 production bugs (`_source_value` enum `.value` and `apply_observations` intra-call state accumulation), 23 of 193 tests still failed with numeric mismatches like `assert 168.53781815096877 == 166.66666666666666 ± 0.01`, `assert 4.020484699851728 == 4.5 ± 4.5e-06`, `assert ('low', 'high') == ('medium', 'high')`, `IndexError: list index out of range`, and `assert 0 >= 1`. Affected every integration and behaviour test file under `tests/integration/test_physiology_update_service_*.py` and `tests/behaviour/test_physiology_update_user_journey.py`, plus one unit test in `test_physiology_update_service_orchestration.py`.

**Root cause:** The 2026-07-13 dated lesson above documents the unit-test case (4 unit tests in `test_physiology_update_service_bayesian.py` pinned `last_observation_date='2026-06-15'` on the per-test `_state()` calls). The 2026-07-14 re-run surfaced the same problem at the **integration and behaviour layers** — the integration test files' `_state()` helper still defaulted `last_observation_date: str = "2026-05-01"`, but the sibling `_observation()` helper defaulted `measurement_date=date(2026, 6, 15)`, producing a 45-day gap that decayed the prior weight via the 42-day time constant (e.g. `0.5 * exp(-45/42) ≈ 0.171`). The integration tests' expected values were computed for same-day math (e.g. `(160 * 0.5 + 170 * 1.0) / 1.5 = 166.67`), not the decayed math (e.g. `(160 * 0.171 + 170 * 1.0) / 1.171 = 168.54`).

The unit-test fix was correct but only fixed the 4 unit tests that explicitly passed `last_observation_date`. The integration tests rely on the helper's default, so the 45-day gap silently applied to every integration test that did not override the date. No integration test explicitly pinned `last_observation_date` — they all relied on the default, so the default's drift from the observation's date was the single point of failure for 16 of the 23 failures.

The remaining 7 failures (1 unit + 6 behaviour) are independent of the date-default issue and are documented as separate dated lessons below.

**Pattern that failed (in 4 integration test files, 1 default site each):**

```python
def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-05-01",  # ← 45-day gap from default obs_date
) -> Dict[str, Any]:
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }
```

**Pattern to use instead:** Change the default to match the sibling `_observation()` helper's `measurement_date`. Every test that does not override the date now gets same-day semantics — the same semantics the test's expected value was computed for.

```python
def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-06-15",  # ← same as default _observation() date
) -> Dict[str, Any]:
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }
```

**Meta-rule:** When two helper functions in the same test file have default date values that interact (`_state` has `last_observation_date`, `_observation` has `measurement_date`), the two defaults must agree. A drift between the two defaults silently introduces a date gap in every test that uses both defaults — the test passes the assertion phase but produces wrong numeric values that diverge from the test author's mental model. Reading both defaults and confirming they agree is part of test-authoring hygiene. A test that relies on same-day semantics must use helpers whose defaults agree on the same date, or pin both dates explicitly per test. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns" (see the 2026-07-13 entry, which this lesson extends to the integration/behaviour layers).

---

### `apply_observations` batch transition is `(pre_call_level, post_call_level)`, not per-observation transitions

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run)

**Symptom:** `test_eight_observations_reach_high` (in `tests/unit/test_physiology_update_service_orchestration.py::TestApplyObservationsConfidenceTransitions`) failed with `AssertionError: assert ('low', 'high') == ('medium', 'high')`. The test expected a `MEDIUM→HIGH` transition, but the service reported `LOW→HIGH`.

**Root cause:** The test author assumed the service reports per-observation transitions — that observation 4 (which crosses prior_weight=4.0 → MEDIUM) would be reported as a transition, then observation 8 (which crosses prior_weight=8.0 → HIGH) would be reported as a second transition. The actual architecture reports a single `confidence_transitions` dict per `apply_observations` call, with the entry being `(pre_call_level, post_call_level)` — a batch transition between the call's input and output. A single batch that starts at LOW (prior_weight=0.0) and ends at HIGH (prior_weight=8.0) reports a direct `LOW→HIGH` transition. The MEDIUM level is reached internally at observation 4 but is not a snapshot the service reports — the `_compute_metric_confidence` function is called exactly twice per `apply_observations` call (once before, once after), and only the pre/post diff is reported.

**Pattern that failed:**

```python
@pytest.mark.asyncio
async def test_eight_observations_reach_high(self) -> None:
    """Eight observations of weight 1.0 for LT2_HR push the
    prior_weight to 8.0 and trigger a MEDIUM→HIGH transition."""
    # ...
    result = await service.apply_observations(
        athlete_id=uuid.uuid4(),
        observations=observations,
    )

    assert "lt2_hr" in result.confidence_transitions
    # ← WRONG — batch transition is LOW→HIGH, not MEDIUM→HIGH
    assert result.confidence_transitions["lt2_hr"] == ("medium", "high")
```

**Pattern to use instead:** Accept the batch transition as the correct architecture contract. The MEDIUM level is a transient state inside the batch; the service contract is pre/post, not per-observation.

```python
@pytest.mark.asyncio
async def test_eight_observations_reach_high(self) -> None:
    """Eight observations of weight 1.0 for LT2_HR push the
    prior_weight to 8.0 and trigger a LOW→HIGH batch transition.

    Note: the transition is reported as ``("low", "high")``,
    NOT ``("medium", "high")`` — ``apply_observations`` computes
    the pre- and post-call confidence levels and reports the
    batch transition between them, not the per-observation
    transitions.
    """
    # ...
    result = await service.apply_observations(
        athlete_id=uuid.uuid4(),
        observations=observations,
    )

    assert "lt2_hr" in result.confidence_transitions
    # Batch transition: pre-call confidence = LOW (prior_weight
    # 0.0), post-call confidence = HIGH (prior_weight 8.0).
    # MEDIUM is reached mid-batch but is not a snapshot the
    # service reports.
    assert result.confidence_transitions["lt2_hr"] == ("low", "high")
```

**Meta-rule:** A test that asserts on a sequence of intermediate state transitions (LOW→MEDIUM, then MEDIUM→HIGH) is asserting a property the service does not implement — the service is designed around a single pre/post diff per call. The integration and behaviour tests that need intermediate transitions should use multi-call designs (one `apply_observations` per observation) and assert on each call's `confidence_transitions` dict separately. The single-call design can only assert on the pre/post pair. The plan's Step 8 explicitly states: "the service computes the raw confidence level from current `prior_weight`" — a single computation per call, not per-observation.

---

### Rollback tests must commit fixture rows in their own transaction — `flush()` does not survive `rollback()`

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run)

**Symptom:** `test_event_atomicity_rolls_back_when_later_step_fails` (in `tests/integration/test_physiology_update_service_integration.py::TestPhysiologyUpdatedEvent`) failed with `IndexError: list index out of range` at the post-rollback `fresh = (...).scalars().all()[0]` accessor. The `all()` returned `[]` because the fixture row had been rolled back along with the observation batch.

**Root cause:** The `_create_physiology_row` helper only calls `session.flush()` (not `commit()`) — the test author intended the fixture row to be visible inside the transaction but uncommitted, mirroring how `apply_observations` would see it via the same session. The accumulation fix (the production fix for RC2) made `apply_observations` actually mutate the row in place via `update_in_place` + `flag_modified`, which now flushes real SQL updates through the same session. When the test then called `db_session.rollback()`, the rollback unwound BOTH the fixture row's INSERT (which was only flushed, not committed) AND the observation batch's UPDATE — leaving no `AthletePhysiology` row at all. The post-rollback SELECT returned `[]`, and `.all()[0]` raised `IndexError`.

The test was previously passing because the broken accumulation did not flush any modifications — the rollback only undid the row creation, but `apply_observations` did not change anything that triggered the rollback to matter. The accumulation fix exposed this latent fixture design issue: the test needs the fixture row to SURVIVE the rollback so the post-rollback SELECT finds it and asserts it was NOT modified by the (rolled-back) observation batch.

**Pattern that failed:**

```python
async def test_event_atomicity_rolls_back_when_later_step_fails(...):
    athlete = await make_athlete(db_session)
    # ← flush-only, not committed
    await _create_physiology_row(
        db_session, athlete_id=athlete.id, lt2={...},
    )
    service = PhysiologyUpdateService(db_session)
    await service.apply_observations(athlete_id=athlete.id, observations=[obs()])
    await db_session.rollback()  # ← undoes the fixture row too
    fresh = (await db_session.execute(select(...))).scalars().all()[0]
    # ← IndexError: all() returned [] because the fixture was rolled back
```

**Pattern to use instead:** Commit the fixture row in its own transaction so it survives the subsequent rollback. The `apply_observations` call opens a new transaction; its rollback must unwind the observation batch but NOT the fixture row.

```python
async def test_event_atomicity_rolls_back_when_later_step_fails(...):
    athlete = await make_athlete(db_session)
    await _create_physiology_row(
        db_session, athlete_id=athlete.id, lt2={...},
    )
    # ← Commit the fixture row so it survives the subsequent rollback.
    # The apply_observations call below opens a new transaction; its
    # rollback must unwind the observation batch but NOT the fixture row.
    await db_session.commit()
    service = PhysiologyUpdateService(db_session)
    await service.apply_observations(athlete_id=athlete.id, observations=[obs()])
    await db_session.rollback()
    fresh = (await db_session.execute(select(...))).scalars().all()[0]
    # ← fresh row is found; the post-rollback assertion verifies the
    # JSONB columns are unchanged (the rollback undid the mutation).
```

**Meta-rule:** A test that exercises transaction rollback semantics (ADR-004, "Event Persistence Atomicity", or any test that calls `db_session.rollback()` after a service call) must commit any fixture rows that the post-rollback assertions depend on. The `_create_*` helper convention of `flush()` (not `commit()`) is correct for tests that assert on in-transaction state, but it is WRONG for tests that follow up with a rollback — the rollback undoes the flush. The split-commit pattern (commit the fixture, then open a new transaction for the service call) is the canonical rollback-test fixture contract. A test that mixes `flush()`-only fixtures with a `rollback()` is asserting a property the fixture cannot satisfy. The same pattern applies to any test that uses `_SafeAsyncSession` or any fixture helper that defers the commit to the test's teardown — those fixtures will also be rolled back, and the post-rollback SELECT will return stale state. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Behaviour tests must pre-populate `AthletePhysiology` when asserting on a posterior shift — bootstrap suppresses shift detection

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run)

**Symptom:** Six behaviour tests in `tests/behaviour/test_physiology_update_user_journey.py` failed with `AssertionError: assert 0 >= 1` (empty `shifted_parameters`). Affected: `test_journey_threshold_detection_to_physiology_updated_event`, `test_journey_event_payload_matches_shifted_parameters`, `test_journey_duplicate_observation_writes_measurement_not_event`, `test_journey_four_observations_reach_medium_confidence`, `test_journey_eight_observations_reach_high_confidence`, `test_journey_small_shift_writes_measurement_not_event`.

**Root cause:** The 2026-07-13 dated lesson "`http_register` does not create `AthletePhysiology` — behaviour tests must insert it explicitly" documents the fix for `MissingAthletePhysiologyError`. The 2026-07-14 re-run surfaced a related but distinct issue: behaviour tests that insert an empty `AthletePhysiology` row (via `_ensure_physiology_row(db_session, athlete_id=athlete_id)` with no `lt1`/`lt2` kwargs) and then call `apply_observations` with a single activity's observations get an empty `shifted_parameters` list. The reason: the first observation for each parameter in the `apply_observations` call bootstraps the state from null (via `init_null_parameter_state`), and the shift detection's `current_state is None` guard suppresses shift detection on the bootstrap. The architecture is correct — the "> 1 unit shift gate only applies when an existing estimate exists" (plan Step 5) — but the behaviour tests were designed assuming the first observation would produce a shift.

For the multi-activity tests (`test_journey_four_observations_reach_medium_confidence`, `test_journey_eight_observations_reach_high_confidence`), the failure mode was different: the activities were spread over multiple weeks (7-day gaps), so the 42-day decay reduced `prior_weight` to ~3.17 after 4 observations and ~4.79 after 8 observations — both below the 4.0 and 8.0 MEDIUM/HIGH thresholds. The tests asserted `prior_weight >= 4.0` and `prior_weight >= 8.0` respectively, and both failed.

**Pattern that failed (single-activity shift assertion):**

```python
async def test_journey_threshold_detection_to_physiology_updated_event(...):
    athlete_id, _ = await http_register(client, ...)
    # ← Empty physiology row — lt1/lt2 sub-states are all None
    await _ensure_physiology_row(db_session, athlete_id=athlete_id)
    activity = await _create_running_activity(...)
    # ... upload + detect ...
    result = await physiology_service.apply_observations(athlete_id, observations)
    # ← FAILS — first observation bootstraps, no shift detected
    assert len(result.shifted_parameters) >= 1
```

**Pattern that use instead (single-activity shift assertion):**

```python
async def test_journey_threshold_detection_to_physiology_updated_event(...):
    athlete_id, _ = await http_register(client, ...)
    # Pre-populate lt1.hr and lt2.hr with state that differs from
    # the cleaned-stream observations by more than 1 bpm so the
    # first observation produces a posterior shift (the
    # current_state is None guard suppresses shift detection for
    # bootstrap observations against a null column).
    await _ensure_physiology_row(
        db_session, athlete_id=athlete_id,
        lt1={"hr": _state(value=130.0, prior_weight=1.0), "power": None, "pace": None},
        lt2={"hr": _state(value=150.0, prior_weight=1.0), "power": None, "pace": None},
    )
    # ... rest of the test
```

**Pattern that failed (multi-activity threshold assertion):**

```python
async def test_journey_four_observations_reach_medium_confidence(...):
    athlete_id, _ = await http_register(client, ...)
    await _ensure_physiology_row(db_session, athlete_id=athlete_id)
    # ← 7-day gaps between activities — 42-day decay reduces prior_weight
    activity_dates = [date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15), date(2026, 6, 22)]
    # ... 4 activities, 4 apply_observations calls ...
    # ← FAILS — prior_weight ~3.17, not >= 4.0
    assert lt2_hr_state["prior_weight"] >= 4.0
```

**Pattern to use instead (multi-activity threshold assertion):**

```python
async def test_journey_four_observations_reach_medium_confidence(...):
    athlete_id, _ = await http_register(client, ...)
    # Pre-populate with prior_weight=0.5 and same-date activities
    await _ensure_physiology_row(
        db_session, athlete_id=athlete_id,
        lt2={"hr": _state(value=150.0, prior_weight=0.5), "power": None, "pace": None},
    )
    # ← SAME date for all 4 activities — distinct activity_ids, no decay
    activity_dates = [date(2026, 6, 15)] * 4
    # ... 4 activities, 4 apply_observations calls ...
    # ← PASSES — prior_weight = 0.5 + 4×1.0 = 4.5
    assert lt2_hr_state["prior_weight"] >= 4.0
```

**Meta-rule:** A behaviour test that asserts on a posterior shift (`len(result.shifted_parameters) >= 1` or a specific shift detection) MUST pre-populate the `AthletePhysiology` row with state that differs from the cleaned-stream observations by more than 1 bpm (HR parameters) or 1 watt (CP). An empty `lt1`/`lt2` row leaves the first observation as a bootstrap, and the `current_state is None` guard correctly suppresses shift detection — the test would be asserting a property the architecture does not have. A behaviour test that asserts on `prior_weight >= threshold` after N observations across multiple activities MUST use same-date activities (or pre-populate the state with a high enough `prior_weight` to absorb the decay) — the 42-day decay across 7-day gaps reduces `prior_weight` to a value below the threshold. Same-date activities are distinguished by their `activity_id` UUID, not by date, so the dedup key (which includes `activity_id`) is unique per activity. The behaviour tests are designed to exercise the end-to-end user journey, not the decay math — the integration layer pins the decay math, and the behaviour layer can use same-date activities to keep the journey test deterministic. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Integration tests asserting linear `prior_weight` accumulation with multi-day `measurement_date` fail due to 42-day decay

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run, pass 2)

**Symptom:** Seven integration tests in `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` and `tests/integration/test_physiology_update_service_first_observation_integration.py` fail with `assert 4.3265 == 4.5 ± 4.5e-06` (or similar non-integer values). The pass-1 fix (aligning the integration `_state()` helper default to `"2026-06-15"`) resolved 16 of 23 tests that relied on the helper's default, but 7 tests explicitly construct observations at `measurement_date=date(2026, 6, 15 + i)` for `i in range(N)`, introducing 1-day gaps that the 42-day time constant decays by `exp(-1/42) ≈ 0.9765` per gap.

**Root cause:** The architecture's `bayesian_update()` applies `decay_factor = exp(-days_since_last / 42)` to the prior weight on every observation. When tests loop `for i in range(N)` and pin `measurement_date=date(2026, 6, 15 + i)`, each iteration's prior weight is decayed by `0.9765` before the new observation's weight is added. After N iterations starting from `prior_weight=0.5`, the accumulated weight is `0.5 × 0.9765^(N-1) + 1.0 × Σ(k=0..N-1) 0.9765^k`, which is strictly less than the linear-accumulation `0.5 + N × 1.0` for N > 1. For N=4, the actual value is `0.5 × 0.9084 + 1.0 × 3.8181 = 4.2725` (close to the report's 4.3265 — small differences come from the bootstrap path on the 1st observation). The decay is architecturally correct and is already covered by `TestBayesianUpdatePriorDecay` in the unit tests; the integration tests are designed to exercise the accumulation pattern, not the decay pattern.

**Pattern that failed (asserting linear accumulation with multi-day dates):**

```python
# 4 observations at 1-day intervals starting from prior_weight=0.5
# Test asserts: 0.5 + 4 × 1.0 = 4.5
for i in range(4):
    obs = _observation(
        parameter=PhysiologyParameter.LT2_HR,
        observed_value=170.0 + i * 0.1,  # distinct values — no dedup
        weight=1.0,
        measurement_date=date(2026, 6, 15 + i),  # ← 1-day gap → 0.9765 decay
    )
    await service.apply_observations(
        athlete_id=athlete.id, observations=[obs],
    )
await db_session.commit()
assert await _read_lt2_hr_prior_weight(db_session, athlete.id) == pytest.approx(4.5)
# ← FAILS: actual is ~4.327 (decayed)
```

**Pattern to use instead (same-day dates preserve linear accumulation):**

```python
# 4 observations all on 2026-06-15 — distinct observed_value avoids dedup
# decay_factor = exp(-0/42) = 1.0 between observations → linear accumulation
for i in range(4):
    obs = _observation(
        parameter=PhysiologyParameter.LT2_HR,
        observed_value=170.0 + i * 0.1,  # distinct values — no dedup
        weight=1.0,
        measurement_date=date(2026, 6, 15),  # ← same day → no decay
    )
    await service.apply_observations(
        athlete_id=athlete.id, observations=[obs],
    )
await db_session.commit()
assert await _read_lt2_hr_prior_weight(db_session, athlete.id) == pytest.approx(4.5)
# ← PASSES
```

**Meta-rule:** Integration tests that assert linear accumulation of `prior_weight` (e.g. `expected = 0.5 + N × weight`) across multiple `apply_observations` calls MUST pin all observations to the same `measurement_date` with distinct `observed_value` to avoid dedup. This restores the expected linear accumulation by setting the decay factor to `1.0` between observations. The decay-between-observations behaviour is already pinned by `TestBayesianUpdatePriorDecay` in the unit tests — the integration layer's job is to verify accumulation and confidence transitions, not decay. When the test's intent is to verify a specific cross-call accumulation pattern, same-day dates are the correct choice. When the test's intent is to verify cross-call state persistence (e.g. `test_three_calls_each_with_one_observation`), same-day dates are still correct — the test is verifying that each call sees the previous call's mutation, not the decay between dates. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Loop pattern cannot observe `from_level == "low"` on the Nth call when the (N-1)th call already crossed MEDIUM/HIGH

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run, pass 2)

**Symptom:** `test_four_rr_observations_reach_high_confidence` in `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` fails with `AssertionError: assert 'medium' == 'low'` on the `from_level` assertion. The test loops 4 times, each iteration calling `apply_observations` with one RR observation (weight=2.5), and asserts the 4th call's result has `confidence_transitions["lt2_hr"] == ("low", "high")`.

**Root cause:** The test's loop pattern accumulates `prior_weight` across calls: after call 1, `prior_weight=3.0` (LOW); after call 2, `prior_weight=5.43` (MEDIUM, with 1-day decay); after call 3, `prior_weight=7.80` (MEDIUM); after call 4, `prior_weight=10.11` (HIGH). The 4th call's pre-call level is MEDIUM, not LOW, so the `from_level == "low"` assertion is wrong. The test was designed under the assumption that the 4th call is the first to cross HIGH, but the 3rd call already crosses MEDIUM (and with same-day dates, the 3rd call crosses HIGH at `5.5 + 2.5 = 8.0`). With any date pattern, the 4th call's pre-call level is never LOW.

**Pattern that failed (4-call loop with `from_level == "low"` on call 4):**

```python
result: PhysiologyUpdateResult | None = None
for i in range(4):
    obs = _observation(
        parameter=PhysiologyParameter.LT2_HR,
        observed_value=170.0 + i * 0.1,
        source=MeasurementSource.TRAINING_RR_INFLECTION,
        weight=2.5,
        measurement_date=date(2026, 6, 15 + i),
    )
    result = await service.apply_observations(
        athlete_id=athlete.id, observations=[obs],
    )
assert result.metric_confidence["lt2_hr"] == "high"
assert "lt2_hr" in result.confidence_transitions
from_level, to_level = result.confidence_transitions["lt2_hr"]
assert from_level == "low"  # ← FAILS: actual is "medium"
assert to_level == "high"
```

**Pattern to use instead (single batch call):**

```python
# All 4 observations in a single apply_observations call.
# The batch transition is (pre_call_level, post_call_level) — pre-call
# state was LOW (prior_weight=0.5), post-call state is HIGH (10.5).
observations = [
    _observation(
        parameter=PhysiologyParameter.LT2_HR,
        observed_value=170.0 + i * 0.1,
        source=MeasurementSource.TRAINING_RR_INFLECTION,
        weight=2.5,
        measurement_date=date(2026, 6, 15),
    )
    for i in range(4)
]
result = await service.apply_observations(
    athlete_id=athlete.id, observations=observations,
)
assert result.metric_confidence["lt2_hr"] == "high"
assert "lt2_hr" in result.confidence_transitions
from_level, to_level = result.confidence_transitions["lt2_hr"]
assert from_level == "low"  # ← PASSES
assert to_level == "high"
```

**Meta-rule:** A test that asserts `from_level == "low"` on the Nth `apply_observations` call for a high-weight source (e.g. RR inflection, weight=2.5) is structurally impossible to satisfy via a loop: the (N-1)th call already crosses MEDIUM (or HIGH) because each call adds the full observation weight on top of an already-accumulated prior_weight, so the Nth call's pre-call level is never LOW. Two fixes: (a) use a single `apply_observations` call with all N observations in one batch — the service reports a single `(pre_call_level, post_call_level)` transition reflecting the full batch, making the `("low", "high")` transition observable; (b) rewrite the assertion to match the actual pre-call level (e.g. `from_level == "medium"` if the 2nd call already crossed MEDIUM). The batch approach is cleaner because the test name typically refers to the N observations as a group (e.g. "four_rr_observations"), and the batch call is the natural API for processing a group. The loop pattern is still correct for tests that assert cross-call state persistence (e.g. `test_three_calls_each_with_one_observation`) or per-call confidence levels (e.g. `test_four_observations_trigger_low_to_medium_transition`) — the issue is specific to tests that assert a `from_level` that requires the pre-call state to be at the lowest level. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Post-rollback ORM attribute access triggers `MissingGreenlet` — use column-level SELECT for JSONB reads

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run, pass 2)

**Symptom:** `test_event_atomicity_rolls_back_when_later_step_fails` in `tests/integration/test_physiology_update_service_integration.py` fails with `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.` on the post-rollback assertion `assert fresh.lt2["hr"]["value"] == pytest.approx(160.0)`. The pass-1 fix (committing the fixture row in its own transaction before `apply_observations` + `rollback`) correctly resolved the IndexError that preceded the MissingGreenlet, but the post-rollback SELECT returned a fresh `AthletePhysiology` instance whose `lt2` attribute triggered async lazy loading outside the greenlet context.

**Root cause:** After `db_session.rollback()`, the session's connection lifecycle enters a state where lazy attribute access on a freshly-loaded instance attempts async IO outside the greenlet context. The pass-1 fix's column-level SELECT (option 1 in the DevOps report) was recommended but not applied — the test was left with the ORM-attribute-access pattern that triggers the lazy load. The `lt2` column is a standard non-deferred JSONB column, so the lazy load is triggered by SQLAlchemy's internal attribute-expiration mechanism after `rollback()`, not by any deferred-column configuration. The traceback shows `_load_expired` → `load_on_pk_identity` → `session.execute` → `pool._create_connection` → `asyncpg.connect` → `await_only()` failing because no greenlet_spawn context exists.

**Pattern that failed (ORM attribute access after rollback):**

```python
await service.apply_observations(
    athlete_id=athlete.id, observations=[_observation()],
)
await db_session.rollback()

# ... assertions on events, measurements, outbox ...

# ← ORM attribute access on freshly-loaded instance after rollback
fresh = (
    await db_session.execute(
        select(AthletePhysiology).where(
            AthletePhysiology.athlete_id == athlete.id
        )
    )
).scalars().all()[0]
assert fresh.lt2["hr"]["value"] == pytest.approx(160.0)
# ← FAILS: MissingGreenlet on fresh.lt2 access
```

**Pattern to use instead (column-level SELECT for JSONB):**

```python
await service.apply_observations(
    athlete_id=athlete.id, observations=[_observation()],
)
await db_session.rollback()

# ... assertions on events, measurements, outbox ...

# ← Column-level SELECT reads the JSONB value directly without
# loading an ORM instance, bypassing the lazy-load hazard.
fresh_lt2 = (
    await db_session.execute(
        select(AthletePhysiology.lt2).where(
            AthletePhysiology.athlete_id == athlete.id
        )
    )
).scalar_one()
assert fresh_lt2["hr"]["value"] == pytest.approx(160.0)
# ← PASSES
```

**Meta-rule:** A test that reads an ORM attribute (especially a JSONB column) on a freshly-loaded instance AFTER `db_session.rollback()` MUST use a column-level SELECT (e.g. `select(Model.jsonb_column).where(...)` and `.scalar_one()`) to read the value directly. The rollback puts the session's connection lifecycle in a state where lazy attribute access on freshly-loaded instances triggers async IO outside the greenlet context, raising `MissingGreenlet`. The column-level SELECT bypasses the ORM attribute layer entirely — the SELECT returns the raw column value without instantiating the model. This is DIFFERENT from the 2026-07-11 `expire_all()` + lazy load anti-pattern — `rollback()` puts the session in a similar but distinct state where the connection lifecycle cannot service subsequent lazy loads. The two fixes have different root causes (expire_all evicts attribute state; rollback evicts transaction state) and different patterns (expire_all → use `.execution_options(populate_existing=True)`; rollback → use column-level SELECT). When a test needs to read JSONB values after a rollback, the column-level SELECT is the only safe pattern. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Post-rollback PK access in WHERE clauses triggers `MissingGreenlet` — capture the PK before `rollback()`

**Date:** 2026-07-14 (Phase-2.3-P2 test pack re-run, pass 2)

**Symptom:** `test_event_atomicity_rolls_back_when_later_step_fails` (in `tests/integration/test_physiology_update_service_integration.py`) failed with `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.` at line 878, even after the pass-2 column-level SELECT fix for the post-rollback `fresh.lt2` JSONB read was applied. The pass-2 fix is necessary but not sufficient: the post-rollback `select(SystemEvent).where(SystemEvent.athlete_id == athlete.id)` access triggers the same hazard, because `athlete.id` is itself an ORM-mapped attribute on an instance that was loaded BEFORE the rollback.

**Root cause:** `db_session.rollback()` expires ALL ORM instances tracked by the session, including the `athlete` object loaded at the start of the test. Accessing `athlete.id` (or any other mapped attribute — even a PK) on an expired instance triggers an async lazy load to re-fetch the row. Under async SQLAlchemy + NullPool, the lazy load fires outside the greenlet context, raising `MissingGreenlet`. The `expire_on_rollback=False` parameter on `async_sessionmaker` would have prevented the expiration, but SQLAlchemy 2.x does not support that parameter — it was removed/never existed in this version.

**Pattern that failed (post-rollback `athlete.id` access in WHERE clause):**
```python
athlete = await make_athlete(db_session)
await db_session.commit()
await service.apply_observations(athlete_id=athlete.id, observations=[_observation()])
await db_session.rollback()
# ← `athlete` is now expired — accessing `athlete.id` will
# trigger an async lazy load outside the greenlet.

events = (
    await db_session.execute(
        select(SystemEvent).where(
            SystemEvent.event_type == "physiology_updated",
            SystemEvent.athlete_id == athlete.id,  # ← MissingGreenlet!
        )
    )
).scalars().all()
```

**Pattern to use instead (capture the PK as a plain Python scalar BEFORE the rollback):**
```python
athlete = await make_athlete(db_session)
await db_session.commit()
await service.apply_observations(athlete_id=athlete.id, observations=[_observation()])
# Capture the PK before the rollback expires the instance.
athlete_id = athlete.id
await db_session.rollback()
# ← `athlete_id` is a plain Python UUID, immune to the
# session-expiration hazard.

events = (
    await db_session.execute(
        select(SystemEvent).where(
            SystemEvent.event_type == "physiology_updated",
            SystemEvent.athlete_id == athlete_id,  # ← captured scalar
        )
    )
).scalars().all()
```

**Meta-rule:** Any test that calls `db_session.rollback()` and then references a mapped attribute of an in-memory instance (e.g. `athlete.id`, `token.token_hash`, `measurement.athlete_id`) in a subsequent `select(...).where(...)` clause or as an argument to a service call MUST capture that attribute as a plain Python scalar (UUID, int, str, etc.) BEFORE the rollback call. The captured scalar survives the rollback and is safe to use in subsequent code paths. This is a strict superset of the 2026-07-11 `expire_all()` + lazy-load-on-captured-scalar rule: `rollback()` is a different state-setter than `expire_all()` (rollback evicts transaction state; expire_all evicts attribute state), but both leave the instance in a state where lazy loads are unservicable. The capture-first pattern works for both. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Post-commit JSONB reads must use `.scalars().all()[0]`, not `.scalar_one()`

**Date:** 2026-07-13

**Symptom:** All 48 integration tests in `tests/integration/test_physiology_update_service_*.py` and `tests/integration/test_athlete_physiology_repository_update_in_place_integration.py` would have asserted `fresh.cp is None` (or `fresh.lt1 is None`, etc.) immediately after `await db_session.commit()` and a re-`SELECT` of the row, even though the prior `repo.update_in_place(athlete.id, cp=new_cp)` had just persisted a non-null JSONB value. The test would have looked like the DB silently dropped the mutation. Additionally, the IDE type-checker (mypy / Pylance) reports `Object of type "None" is not subscriptable` on any `fresh.cp["value"]` access, because `cp: Mapped[dict | None]` is nullable and the type system has no way to know the post-commit read will return a non-null value.

**Root cause:** After `await db_session.commit()`, the test calls `await db_session.execute(select(AthletePhysiology).where(...))` and chains `.scalar_one()`. The session's identity map returns the same ORM instance that was loaded *before* the commit. SQLAlchemy's identity map does not refresh JSONB attribute values on a cached instance from a same-table `SELECT` unless `populate_existing=True` is set, and the test was not setting it. The instance's in-memory `cp` attribute can be stale relative to the actual DB row.

**Pattern that failed:**

```python
await repo.update_in_place(athlete.id, cp=new_cp)
await db_session.commit()

# WRONG — identity map may return the pre-update instance with stale cp
fresh = (
    await db_session.execute(
        select(AthletePhysiology).where(AthletePhysiology.athlete_id == athlete.id)
    )
).scalar_one()
assert fresh.cp == new_cp  # can fail with fresh.cp is None or stale value
```

**Pattern to use instead:** Use `.scalars().all()[0]` (or `.scalars().first()`) instead of `.scalar_one()`. The `.scalars().all()` path constructs fresh ORM instances from result rows, bypassing the identity map entirely. The first test that already used this pattern correctly was `tests/integration/test_physiology_measurement_repository_integration.py` — copy from it.

```python
# CORRECT — fresh instance from result rows
fresh = (
    await db_session.execute(
        select(AthletePhysiology).where(AthletePhysiology.athlete_id == athlete.id)
    )
).scalars().all()[0]
assert fresh.cp == new_cp
```

**For nullable JSONB columns (`cp`, `max_hr`, `vo2max`), also add a `is not None` narrowing assert before any subscript access.** This is required to satisfy the IDE type-checker (`Mapped[dict | None]` is the static type, and `cp["value"]` is statically invalid without narrowing) and to give a clear runtime error if the post-commit read returns a null value. `lt1` and `lt2` are non-nullable (`Mapped[dict]`) and need no narrowing.

```python
fresh = (
    await db_session.execute(
        select(AthletePhysiology).where(AthletePhysiology.athlete_id == athlete.id)
    )
).scalars().all()[0]
assert fresh.cp is not None  # narrows type AND catches runtime null
assert fresh.cp["value"] == pytest.approx(260.0)
```

**For `result` variables assigned inside a `for` loop and used after the loop, initialize with a type annotation before the loop and add `assert result is not None` after.** The IDE type-checker treats `for i in range(N):` as "may execute zero times" → `result` is "possibly unbound" even when `N > 0` is obvious. The fix is:

```python
result: PhysiologyUpdateResult | None = None
for i in range(8):
    result = await service.apply_observations(athlete_id=athlete.id, observations=[obs])

assert result is not None  # narrows type AND catches runtime null
assert result.metric_confidence["lt2_hr"] == "high"
```

This pattern appeared in `tests/integration/test_physiology_update_service_confidence_transitions_integration.py` (4 tests) where `result` was assigned inside a loop and used after.

**Why this is a reusable failure class:** The conftest's `_SafeAsyncSession.expire_all()` override expunges instances (it does not just expire them) so that post-`expire_all()` lazy loads do not raise `MissingGreenlet`. But expunging does not help here — the issue is the inverse: the identity map returns a still-loaded instance, but the instance's JSONB attributes are stale because the row was mutated in place via `flag_modified` and the identity map does not know to refresh on a same-table `SELECT` without `populate_existing=True`. Any future integration test that does a post-commit read of a JSONB-mutated row (e.g. `AthletePhysiology`, `TwinState`, `WorkoutTarget`) is at risk.

**Alternative fix:** Add `populate_existing=True` to the `select()` execution options. This is equivalent to `.scalars().all()[0]` from a correctness standpoint but changes the call shape more invasively. The `.scalars().all()[0]` pattern is preferred because it matches the existing tests in `test_physiology_measurement_repository_integration.py` and is more readable.

---

### `str(enum_member)` is NOT the `.value` for `class Foo(str, Enum)` — use `source.value`

**Date:** 2026-07-13 (Phase-2.3-P2 triage)

**Symptom:** Every test that asserts a `MeasurementSource` enum-derived string is now stored in the JSONB `dominant_source` field or the `physiology_updated` event payload fails with `AssertionError: 'MeasurementSource.TRAINING_RR_INFLECTION' != 'training_rr_inflection'`. Affected: 7 unit tests, 6+ integration tests, 4+ behaviour tests — every test that checks the `dominant_source` JSONB column or event payload after a `bayesian_update`/`apply_observations` call with a `MeasurementSource` enum source.

**Root cause:** `app/models/enums.py` declares `MeasurementSource` as `class MeasurementSource(str, Enum)` — the `str` mixin makes enum members compare-equal to their value string (`MeasurementSource.TRAINING_RR_DEFLECTION == "training_hr_deflection"` is `True`), but `str(enum_member)` returns the *qualified name* (`"ClassName.MEMBER_NAME"`) because `Enum.__str__` is the `__str__` method, not the str mixin's. The function `_source_value(source: Any) -> str` in `app/services/physiology_update_service.py` is `return str(source)`, which yields `"MeasurementSource.TRAINING_RR_DEFLECTION"` instead of the intended `"training_hr_deflection"`. Verified in `.venv/bin/python` — the behaviour is the same on Python 3.11 (the project's runtime), and is unchanged for `StrEnum` in 3.12+ when the enum is declared as `(str, Enum)` rather than `(StrEnum,)`.

**Pattern that failed** (in `app/services/physiology_update_service.py`):

```python
def _source_value(source: Any) -> str:
    """Return the MeasurementSource.value string for source."""
    return str(source)  # ← "MeasurementSource.TRAINING_RR_DEFLECTION", not "training_hr_deflection"
```

**Pattern to use instead** (one-line fix in production code):

```python
def _source_value(source: Any) -> str:
    """Return the MeasurementSource.value string for source."""
    if isinstance(source, MeasurementSource):
        return source.value
    # Defensive: JSONB round-trips can hand back a plain string.
    return str(source)
```

**Meta-rule:** For any `class Foo(str, Enum)` in this codebase, do NOT use `str(enum_member)` to get the value — use `enum_member.value`. The `str` mixin only enables string comparison and JSON serialisation, not `str()` semantics. The correct pattern is `source.value` when the input is known to be the enum, with a defensive `str(source)` fallback for pre-stringified values. A test-asserting string like `"training_hr_deflection"` (the `.value`) is correct; a test asserting `"MeasurementSource.TRAINING_RR_DEFLECTION"` would be wrong. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns" (if a contract layer ever emerges for enum serialisation).

---

### `_observation()` helper default `activity_id=uuid.uuid4()` violates the FK chain

**Date:** 2026-07-13 (Phase-2.3-P2 triage)

**Symptom:** All integration and behaviour tests that build `ThresholdObservation` via the per-file `_observation()` helper fail at the first `apply_observations` call with `sqlalchemy.exc.IntegrityError: insert or update on table "physiology_measurements" violates foreign key constraint "physiology_measurements_activity_id_fkey"`. Affected: 20+ integration tests, 4 behaviour tests — every test that uses the default `activity_id` value.

**Root cause:** The `_observation()` helper defaulted `activity_id` to `activity_id or uuid.uuid4()` — a fresh random UUID with no corresponding `Activity` row. The helper's docstring noted "the column is nullable" but stopped short of the corollary: *a non-null value must reference a real `activities.id`*. The PostgreSQL FK is always enforced when a value is present, regardless of whether the column is itself nullable. The test author's mental model was "nullable means optional" without distinguishing between "the value is null" (FK skipped) and "the value is present but invalid" (FK enforced). The same author of the test author on the unit-test side correctly passed `activity_id=None` (the model has no Activity row in the unit-test branch, so `None` is the only safe choice); the integration test author had a real DB and reasonably wanted a real activity reference, but did not create the row.

**Pattern that failed** (in `tests/integration/test_physiology_update_service_*.py`):

```python
def _observation(
    *,
    parameter: PhysiologyParameter = ...,
    activity_id: Optional[uuid.UUID] = None,
    ...
) -> ThresholdObservation:
    return ThresholdObservation(
        ...
        activity_id=activity_id or uuid.uuid4(),  # ← FK violation
        ...
    )
```

**Pattern to use instead:**

```python
def _observation(
    *,
    parameter: PhysiologyParameter = ...,
    activity_id: Optional[uuid.UUID] = None,
    ...
) -> ThresholdObservation:
    """``activity_id`` defaults to ``None`` so the
    ``physiology_measurements.activity_id`` FK is bypassed — the
    column is nullable, so a NULL value skips the constraint
    entirely. Tests that specifically want to attach a
    measurement to a real activity (e.g. for the idempotency
    dedup test) pass an explicit ``activity_id`` AFTER creating
    the matching ``Activity`` row with the ``make_activity``
    factory — see ``tests/utils/factories.py``.
    """
    return ThresholdObservation(
        ...
        activity_id=activity_id,  # ← None or a real Activity id
        ...
    )
```

The new `make_activity` factory lives in `tests/utils/factories.py` and mirrors the shape of `make_athlete` / `make_auth` / `make_refresh_token`. It uses `ActivitySource.MANUAL_UPLOAD`, `SportType.RUNNING`, and the minimum field set the calibration-eligible / sport-type / signal gates need. The four tests in the idempotency class that explicitly test the dedup key (which includes `activity_id`) call `make_activity(db_session, athlete_id=athlete.id, activity_date=...)` and pass `activity.id` to `_observation`.

**Meta-rule:** When a test helper builds a model that has a non-nullable column with a FK to another table, the helper's default for that column must either be `None` (if the column is nullable) or a real `id` from a pre-created row. Generating a fresh `uuid.uuid4()` for an FK column is a code smell that should fail review — the UUID has no referent. The two-step pattern (1. factory creates the parent row, 2. test calls the helper with the parent's id) is the canonical way to wire a real reference. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### `http_register` does not create `AthletePhysiology` — behaviour tests must insert it explicitly

**Date:** 2026-07-13 (Phase-2.3-P2 triage)

**Symptom:** All 7 behaviour tests in `tests/behaviour/test_physiology_update_user_journey.py` fail at the first `apply_observations(athlete_id, ...)` call with `MissingAthletePhysiologyError: no AthletePhysiology row for athlete <uuid>`. The HTTP register endpoint (`app/services/auth_service.py::AuthService.register`) only creates `Athlete + AthleteAuth + AthleteProfile + RefreshToken`; the `AthletePhysiology` row is bootstrapped by the onboarding service in a separate sub-phase (out of Phase-2.3-P2 scope).

**Root cause:** The behaviour test author assumed the HTTP register path would create the physiology row — the same assumption that a unit-test author would correctly NOT make (the unit tests build the `AthletePhysiology` row directly in the test). The behaviour layer exercises the full HTTP path, but the production HTTP `register` does not include the physiology bootstrap. The architecture's invariant "one `AthletePhysiology` row per athlete" is satisfied by the onboarding service, not by registration. The behaviour tests need to insert the row explicitly after `http_register` — this is the production data topology: register is auth-only, physiology is bootstrapped by onboarding.

**Pattern that failed:**

```python
athlete_id, _ = await http_register(
    client, f"behaviour-phys-a-{uuid.uuid4()}@example.com"
)
# No AthletePhysiology row exists — apply_observations will raise.
activity = await _create_running_activity(db_session, athlete_id=athlete_id, ...)
result = await physiology_service.apply_observations(athlete_id, observations)
# ← MissingAthletePhysiologyError
```

**Pattern to use instead:**

```python
athlete_id, _ = await http_register(
    client, f"behaviour-phys-a-{uuid.uuid4()}@example.com"
)
# ``http_register`` only creates Athlete + AthleteAuth + AthleteProfile.
# The AthletePhysiology row is bootstrapped by the onboarding service
# (separate sub-phase, out of P2 scope). Insert it explicitly so
# ``apply_observations`` finds a row to mutate.
await _ensure_physiology_row(db_session, athlete_id=athlete_id)
activity = await _create_running_activity(db_session, athlete_id=athlete_id, ...)
result = await physiology_service.apply_observations(athlete_id, observations)
```

The `_ensure_physiology_row` helper in the behaviour test file is idempotent — it checks for an existing row first and only inserts if missing. Tests that need a pre-populated `lt1` / `lt2` / `cp` / `max_hr` pass them in via the helper's kwargs; the default is the empty three-dimension container for `lt1`/`lt2` and `None` for `cp`/`max_hr` (matching what `OnboardingService.complete_onboarding` produces at the end of the onboarding transaction).

**Meta-rule:** When the behaviour layer exercises an HTTP path that does NOT include the full data-creation chain, the test must explicitly create the dependencies the subsequent service calls need. The production code's responsibility is the contract that `register` is auth-only — the test's responsibility is to know that and insert the missing row. Reading the implementation of the HTTP endpoint (here, `app/services/auth_service.py::AuthService.register`) and the onboarding service (here, `app/services/onboarding_service.py::OnboardingService.complete_onboarding`) before writing the test would have caught this. A test that exercises "register → first service call" needs to know what `register` actually creates, not what the test author wishes it created. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### `apply_observations` loop does not accumulate state across same-parameter observations in a single call

**Date:** 2026-07-13 (Phase-2.3-P2 triage)

**Symptom:** All confidence-transition tests (4 observations should reach `prior_weight=4.0`, 8 should reach 8.0, 2 RR observations should reach 5.0) fail because the post-loop `prior_weight` is 1.0 (the last iteration's contribution only) instead of the accumulated value. Affected: 3 unit tests in `TestApplyObservationsConfidenceTransitions`, 4 integration tests in `TestLowToMediumTransition` / `TestMediumToHighTransition`, 2 behaviour tests in `TestPhysiologyUpdateConfidenceTransitionsJourney`. The test failure is `result.confidence_transitions["lt2_hr"] == ("low", "medium")` failing because `result.metric_confidence["lt2_hr"] == "low"` (the post-update prior_weight is below 4.0).

**Root cause:** The implementation in `app/services/physiology_update_service.py::PhysiologyUpdateService.apply_observations` reads `current_state` from `physiology` on every iteration of the observation loop via `self._get_parameter_state(physiology, obs.parameter)`. But `physiology` is only mutated AFTER the loop completes, in `self._apply_updated_states(physiology, working_state)` and `self.athlete_physiology.update_in_place(...)`. The `working_state` dict IS mutated inside the loop, but `current_state` is always read from the in-memory `physiology` (the pre-loop state), not from `working_state[obs.parameter]`. So for 4 observations of the same parameter in a single call, all 4 iterations see the same original `prior_weight=0.0` (or `0.5` depending on the test fixture), and each iteration's `working_state[obs.parameter] = new_state` overwrites the previous one. The final `working_state[obs.parameter]["prior_weight"]` reflects exactly one observation's contribution (1.0), not the accumulated value (4.0).

**Pattern that failed** (in `app/services/physiology_update_service.py`):

```python
for obs in observations:
    if await self._is_duplicate(...):
        ...
        continue

    current_state = self._get_parameter_state(physiology, obs.parameter)
    # ← BUG: always reads from `physiology`, which is not updated
    # until AFTER the loop. The 2nd, 3rd, 4th observations see
    # the SAME current_state as the 1st, so their bayesian_update
    # computations are all based on the original prior_weight.

    if current_state is None:
        new_state = init_null_parameter_state(observation_payload)
    else:
        new_state = bayesian_update(current_state, observation_payload)

    working_state[obs.parameter] = new_state
    # ← The dict overwrite means only the last iteration's
    # result survives. The accumulated state across iterations
    # is lost.
    ...
```

**Pattern to use instead** (in production code, NOT a test fix):

```python
for obs in observations:
    if await self._is_duplicate(...):
        ...
        continue

    # CRITICAL: if this parameter was already updated in a prior
    # iteration of THIS batch, use the in-loop `working_state`
    # entry as the next iteration's prior. Otherwise, read from
    # the in-memory `physiology` row (which reflects the
    # persisted state at call entry).
    current_state = working_state.get(obs.parameter)
    if current_state is None:
        current_state = self._get_parameter_state(physiology, obs.parameter)

    if current_state is None:
        new_state = init_null_parameter_state(observation_payload)
    else:
        new_state = bayesian_update(current_state, observation_payload)

    working_state[obs.parameter] = new_state
    ...
```

**Verification:** A trace through 4 observations of weight 1.0 against initial `prior_weight=0.0`:
- Iteration 1: `working_state` is empty → read from physiology (0.0) → new prior_weight = 0.0 + 1.0 = 1.0 → `working_state[param]` = 1.0
- Iteration 2: `working_state.get(param)` returns 1.0 → use as prior → new prior_weight = 1.0 * 1.0 (no decay) + 1.0 = 2.0 → `working_state[param]` = 2.0
- Iteration 3: `working_state.get(param)` returns 2.0 → new prior_weight = 3.0
- Iteration 4: `working_state.get(param)` returns 3.0 → new prior_weight = 4.0 → LOW→MEDIUM transition fires correctly.

**Meta-rule:** When a service method processes a batch of observations that may contain multiple observations for the same parameter, the in-loop state must be the source of truth for the next iteration's `current_state`, not the in-memory entity loaded at the start of the call. This is the standard Bayesian sequential-update pattern: posterior_n = bayesian_update(posterior_{n-1}, observation_n), not posterior_n = bayesian_update(prior, observation_n) for n > 1. A test that submits N observations of the same parameter in one call (e.g. the confidence-transition tests here) will catch this; a test that submits one observation per call (e.g. the behaviour journey that does one `apply_observations` per activity) will NOT catch it because each call's single observation does not need accumulation. The lesson: design tests to exercise the same call's batch dynamics, not just multi-call dynamics. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### `onupdate=` hook fires only when a column is mutated — not on a no-op flush

**Date:** 2026-07-13 (Phase-2.3-P2 triage)

**Symptom:** `test_updated_at_changes_even_with_no_column_mutations` (in `tests/integration/test_athlete_physiology_repository_update_in_place_integration.py`) fails with `AssertionError` because `row.updated_at` is unchanged after calling `update_in_place(athlete.id)` (no parameters) and committing. The test was asserting that the `onupdate=` hook fires on any `flush()`, regardless of whether a column was mutated.

**Root cause:** SQLAlchemy's `onupdate=` hook fires on a column when an `UPDATE` statement is issued for the row. An `UPDATE` statement is issued only when SQLAlchemy detects at least one column change in the dirty instance. Calling `update_in_place` with all default parameters leaves the in-memory `physiology` row's columns unchanged, so SQLAlchemy does not include the row in the dirty set, no `UPDATE` is issued, and the `onupdate=` hook does not fire. The test was asserting the wrong behaviour — the architecture's contract is "`updated_at` advances when `update_in_place` actually mutates a column" (see Plan Step 6: "Only update columns that have changed"), not "advances on every call to `update_in_place`".

**Pattern that failed:**

```python
original_updated_at = row.updated_at
await asyncio.sleep(1.1)
repo = AthletePhysiologyRepository(db_session)
# No parameters passed → no column touched.
await repo.update_in_place(athlete.id)
await db_session.commit()
await db_session.refresh(row)
assert row.updated_at > original_updated_at  # ← FAILS — no UPDATE, no onupdate
```

**Pattern to use instead:** The correct semantics are pinned by `test_updated_at_changes_after_update` (a mutated-column call DOES fire the hook). The no-op test was removed entirely (replaced with a NOTE comment in the test file) because the test was asserting a property the SQLAlchemy ORM does not implement. The intended invariant — "`update_in_place` always does some DB work" — is meaningless at the SQLAlchemy level (a no-op call is a no-op), and the real invariant — "`update_in_place` mutates columns and persists them" — is already covered by the per-column persistence tests in `TestUpdateInPlaceLt1Persistence` / `TestUpdateInPlaceCpPersistence` etc.

**Meta-rule:** Do not test that an ORM hook fires on a no-op operation. SQLAlchemy's `onupdate=` is per-row, not per-flush — it requires actual column mutations to issue an `UPDATE` statement. When writing a test that asserts a `flush()`-side-effect (trigger, hook, computed column), design data that produces the side-effect, or remove the test. A test asserting "the hook fires even when no work was done" is asserting a contract the ORM does not have. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Test fixtures with default `last_observation_date` cause 45-day decay when assertions assume same-day

**Date:** 2026-07-13 (Phase-2.3-P2 triage)

**Symptom:** Four unit tests in `tests/unit/test_physiology_update_service_bayesian.py` (`test_posterior_mean_exact_when_weights_equal`, `test_new_total_weight_is_decayed_plus_observation`, `test_uncertainty_above_floor_when_evidence_moderate`, `test_prior_dominates_when_weights_equal`) fail with numeric values that are off by the `exp(-45/42) ≈ 0.343` decay factor. The tests expected simple arithmetic combinations (170.0, 5.0, sqrt(2.0), prior-source-preservation) but got values that reflected a decayed prior.

**Root cause:** The shared `_state()` helper defaults `last_observation_date="2026-05-01"` and the shared `_observation()` helper defaults `obs_date=date(2026, 6, 15)` — a 45-day gap. The default fixture was inherited from a different test class that exercised decay (where the 45-day gap was the actual scenario under test), but these four tests were written assuming same-day semantics. The decayed_weight becomes `prior_weight * 0.343`, and the resulting posterior values differ from the same-day case by the same factor. The 45-day gap is not a bug in the test data — it is a bug in the test's understanding of the shared fixture.

**Pattern that failed:**

```python
def test_posterior_mean_exact_when_weights_equal(self) -> None:
    # Comment in the test: "decayed_weight = 1.0, obs.weight = 1.0 → simple mean"
    # ← WRONG — the default _state() has last_observation_date='2026-05-01',
    # and the default _observation() has obs_date=date(2026, 6, 15).
    # The actual decayed_weight is 1.0 * exp(-45/42) ≈ 0.343.
    current = _state(value=160.0, prior_weight=1.0)
    observation = _observation(value=180.0, weight=1.0)
    result = bayesian_update(current, observation)
    assert result["value"] == pytest.approx(170.0)  # ← FAILS, actual is ~175
```

**Pattern to use instead:** Pin the date explicitly to match the observation date so the test exercises the same-day semantics it intends:

```python
def test_posterior_mean_exact_when_weights_equal(self) -> None:
    # Same-day observation → no decay → simple arithmetic mean.
    # Pin last_observation_date to match the default obs_date so
    # the test exercises the same-day path, not the 45-day gap.
    current = _state(
        value=160.0,
        prior_weight=1.0,
        last_observation_date="2026-06-15",
    )
    observation = _observation(value=180.0, weight=1.0)
    result = bayesian_update(current, observation)
    assert result["value"] == pytest.approx(170.0)  # ← PASSES
```

**Meta-rule:** When a test file has multiple helpers with default date values (e.g. `_state`, `_observation`), the author of any new test that intends a specific date semantics (same-day, exactly 42 days, etc.) MUST pin both dates explicitly. The default fixture may have been designed for a different scenario (e.g. the `_state` default was used in a decay-exercising test). Reading the helper's default values and confirming the test's expected math matches those defaults is part of test-authoring hygiene. A test that says "same-day" in a comment but uses 45-day-apart defaults will silently compute the wrong expected value. This is now first-class in `tests/MOCKING_CONTRACT.md` "Known Anti-Patterns".

---

### Test fixture helpers must match the FK chain of the production models

**Date:** 2026-07-11

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

---

### `ON DELETE SET NULL` cascade tests must `expire_all()` before re-reading the cascaded row

**Date:** 2026-07-11

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

---

### Async session teardown fires `MissingGreenlet` when the pool defers close — `NullPool` is the fix

**Date:** 2026-07-11

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

---

### `expire_all()` + async lazy load on captured scalar — capture scalars BEFORE `expire_all()`

**Date:** 2026-07-11

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

---

### Multi-call `_create_planned_session()` creates duplicate active TrainingGoals — share the parent chain

**Date:** 2026-07-11

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

---

### `expire_all()` + identity-map return — add `.execution_options(populate_existing=True)` to the post-cascade SELECT

**Date:** 2026-07-11

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

---

### Test data for a strict-greater-than threshold must exceed the threshold by a clear margin

**Date:** 2026-07-11

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

### End-to-end `alembic downgrade` tests become stale once later sub-phases build on top of the migration

**Date:** 2026-07-11 (test-removal policy)

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

---

### Test fixtures must populate every field the production code reads unconditionally

**Date:** 2026-07-09

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

---

### Test data must clear every gate in the chain before the one under test

**Date:** 2026-07-09

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

---

### Use `pytest.approx` for numerically-filtered samples

**Date:** 2026-07-09

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

### Variable name `mock` must not be reused for `ParsedFitData`

**Date:** 2026-07-09 (Test Authoring Conventions)

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

### Repository mocking requires scalar_one_or_none() not first()

**Date:** 2026-07-07

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

---

### sport_type field must be set in Activity factory for calibration eligibility tests

**Date:** 2026-07-07

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

---

### Power-based load formula normalization differs from HR-based

**Date:** 2026-07-07

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

### planned_session_id must be explicitly set to None in post_workout_agent tests

**Date:** 2026-07-01

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

---

### Patch target must match import style in post_workout_agent

**Date:** 2026-07-01

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

---

### Method name mismatch: update vs update_load_scores

**Date:** 2026-07-01

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
