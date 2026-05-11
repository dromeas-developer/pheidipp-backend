# Plan: Fix Test Database to Use Alembic Migrations

## Problem Statement

The test database (`test_pheidipp`) is currently initialized using SQLAlchemy's `Base.metadata.create_all()` instead of Alembic migrations. This causes:

1. **Missing extensions** — TimescaleDB and Vector extensions are never created in the test DB
2. **Missing hypertable configuration** — `create_hypertable()` calls in migrations are skipped
3. **Schema drift** — Test DB schema differs from production DB schema
4. **Potential runtime errors** — Tests may pass but fail in production due to missing features

## Goal

Ensure the test database uses Alembic migrations so both test and production databases are identically configured.

---

## Implementation Steps

### Step 1: Analyze Current Migration Dependencies

**Task**: Review all existing migrations to identify:
- Extension creation statements (`CREATE EXTENSION`)
- Hypertable creation statements (`SELECT create_hypertable`)
- Any custom SQL that must run before/after table creation

**Files to review**:
- `alembic/versions/*.py` — All migration files

---

### Step 2: Modify Test DB Initialization in `tests/conftest.py`

**Task**: Replace `Base.metadata.create_all()` with Alembic migration execution.

**Current code (remove)**:
```python
async def _init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

**New code (add)**:
```python
async def _init_db():
    # Use Alembic for test DB to match production schema
    import subprocess
    subprocess.run(
        ["alembic", "upgrade", "head"],
        env={**os.environ, "DATABASE_URL": test_db_connection_url},
        check=True,
    )
```

**Alternative (more direct approach)**:
For faster test initialization, create a custom Alembic run function that:
1. Connects to test DB with sync driver
2. Runs `context.run_migrations()` with test DB URL

---

### Step 3: Ensure Extensions Exist Before Migrations

**Task**: Add extension creation before running Alembic migrations in test context.

**Approach A**: Create a `alembic/pre_test_env.py` script that:
```python
# 1. Connect to test DB
# 2. Run: CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
# 3. Run: CREATE EXTENSION IF NOT EXISTS vector;
# 4. Continue with alembic upgrade head
```

**Approach B**: Create a test-specific migration prefix that handles extensions.

---

### Step 4: Verify Test Initialization Works

**Task**: Run tests and verify:
1. Test DB tables are created correctly
2. Extensions are present (`timescaledb`, `vector`)
3. Hypertable tables are configured
4. All tests pass

**Commands**:
```bash
bash scripts/docker-build.sh
bash scripts/run-tests.sh
```

---

### Step 5: Document the Configuration

**Task**: Update documentation to explain:
- Why Alembic is used for test DB
- How to add new migrations (must work for both DBs)
- Troubleshooting guide

---

## Files to Modify

| File | Change |
|------|--------|
| `tests/conftest.py` | Replace `create_all` with Alembic migration runner |
| `tests/conftest.py` | Add extension setup before migrations |

## Files to Create (optional)

| File | Purpose |
|------|---------|
| `scripts/test-db-init.sh` | Standalone script to initialize test DB with migrations |

---

## Acceptance Criteria

- [ ] Tests run against `test_pheidipp` database
- [ ] Test DB schema matches production DB schema
- [ ] TimescaleDB extension exists in test DB
- [ ] Vector extension exists in test DB
- [ ] Hypertable tables are properly configured in test DB
- [ ] All existing tests pass
- [ ] New migrations automatically apply to both DBs

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Test DB initialization is slow | Use session-scoped initialization (already done), consider caching |
| Extensions fail to create | Add pre-check to verify DB user has extension creation rights |
| Migration conflicts | Ensure clean DB state before each test run |

---

## Timeline

- Step 1: Analyze migrations — 15 min
- Step 2: Modify conftest.py — 30 min
- Step 3: Add extension setup — 15 min
- Step 4: Verify tests pass — 15 min
- Step 5: Document — 15 min

**Total estimate**: 1.5 hours