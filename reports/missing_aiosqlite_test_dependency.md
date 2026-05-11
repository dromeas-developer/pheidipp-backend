# Bug Report — Missing Test Dependency: aiosqlite

Date: 2026-05-10
Priority: HIGH
Component: Test Infrastructure

## Summary

17 unit tests in `tests/unit/test_athlete_repository.py` are failing with `ModuleNotFoundError: No module named 'aiosqlite'`. This is a pre-existing test infrastructure issue that prevents proper unit testing of repository layer.

## Root Cause

The test file `tests/unit/test_athlete_repository.py` uses **async in-memory SQLite** for testing:

```python
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
```

This requires the `aiosqlite` package, which is **NOT listed** in `requirements.txt`.

## Affected Tests

All 17 tests in `tests/unit/test_athlete_repository.py`:

1. `test_athlete_create`
2. `test_athlete_get_by_id`
3. `test_athlete_get_by_id_not_found`
4. `test_athlete_get_by_email`
5. `test_athlete_get_by_email_not_found`
6. `test_athlete_update`
7. `test_athlete_update_not_found`
8. `test_athlete_delete`
9. `test_athlete_delete_not_found`
10. `test_athlete_list`
11. `test_profile_create`
12. `test_profile_get_by_athlete_id`
13. `test_profile_get_by_athlete_id_not_found`
14. `test_profile_update`
15. `test_profile_update_not_found`
16. `test_profile_delete`
17. `test_profile_delete_not_found`

## Current Test Results

```
================== 91 passed, 7 warnings, 17 errors in 0.58s ===================
ERROR tests/unit/test_athlete_repository.py::test_athlete_create - ModuleNotFoundError: No module named 'aiosqlite'
... (17 identical errors)
```

## Fix Required

### Option 1: Add aiosqlite to requirements.txt (Recommended)

Add the following to `requirements.txt`:

```
aiosqlite>=0.19.0
```

This is the simplest fix and enables async SQLite testing.

### Option 2: Use PostgreSQL test container

If we want tests to use the same database as production (PostgreSQL):

1. Add `pytest-docker` or similar fixture to spin up a test PostgreSQL container
2. Modify `db_session` fixture to connect to the test PostgreSQL container
3. Remove the SQLite-specific connection string

### Option 3: Mock the repository layer

Use unit tests with mocking (bypasses database entirely):

- Create mock objects for `AsyncSession`
- Test business logic without persistence

## Recommendation

**Option 1** is recommended as it:
- Requires minimal code change
- Maintains existing test structure
- Uses in-memory DB for fast tests
- Aligns with async SQLAlchemy patterns

## Action Items

- [ ] Add `aiosqlite>=0.19.0` to `requirements.txt`
- [ ] Re-run tests to verify all 108 tests pass
- [ ] Consider adding `aiosqlite` to Docker image if tests run in container

## Severity

**MEDIUM** — Tests fail but feature implementation is complete. Unit tests for repository layer cannot run until this is fixed.