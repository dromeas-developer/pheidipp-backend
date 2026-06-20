# Pheidipp Test Infrastructure Guide

## Overview

This directory contains the test suite for the Pheidipp backend. Tests are organized into:
- `unit/` — Isolated unit tests (no database)
- `integration/` — Integration tests with database (transactional)
- `api/` — HTTP API tests using FastAPI test client
- `behaviour/` — End-to-end user journey tests

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