# Implementation Plan — PostgreSQL Test Container for Repository Tests

## Objective
Replace async in-memory SQLite with PostgreSQL test container for repository unit tests to align with production database and eliminate `aiosqlite` dependency.

---

## Requirements

### requirements.txt [MODIFY]
- **Objective**: Add pytest-docker dependency for test container management
- **Actions**:
  - Add `pytest-docker>=3.0.0` to the test dependencies section

---

## Test Infrastructure

### tests/conftest.py [MODIFY]
- **Objective**: Add PostgreSQL test container fixture for database testing
- **Actions**:
  - Import `pytest_docker` fixtures
  - Add `postgres_container` fixture that configures a PostgreSQL test container with:
    - Image: `timescale/timescaledb:latest-pg16` (matching production)
    - Database name: `test_pheidipp`
    - User: `postgres`
    - Password: `postgres`
    - Port mapping to avoid conflicts
  - Add `test_db_session` fixture that:
    - Uses the `postgres_container` fixture
    - Creates an async SQLAlchemy engine connecting to the test container
    - Runs `Base.metadata.create_all` on the test database
    - Yields an `AsyncSession` for test use
    - Disposes the engine and cleans up after tests

---

## Test File Updates

### tests/unit/test_athlete_repository.py [MODIFY]
- **Objective**: Replace SQLite fixture with PostgreSQL test container fixture
- **Actions**:
  - Remove the existing `db_session` fixture (lines 15-35)
  - Remove imports: `create_async_engine`, `StaticPool`, `sessionmaker` from SQLAlchemy
  - Import `test_db_session` from `tests.conftest`
  - Rename all references from `db_session` to `test_db_session` in:
    - `athlete_repo` fixture
    - `profile_repo` fixture
    - All 17 test functions

---

## Verification

After implementation:
1. Run `pytest tests/unit/test_athlete_repository.py -v` to verify all 17 tests pass
2. Run full test suite to ensure no regressions in other tests
3. Verify test container is properly created and destroyed between test runs

---

## Notes

- The PostgreSQL test container approach ensures tests run against the same database engine as production
- Test isolation is maintained through database cleanup between tests
- Container lifecycle is managed by pytest-docker fixtures
- No changes to production code or database schema required