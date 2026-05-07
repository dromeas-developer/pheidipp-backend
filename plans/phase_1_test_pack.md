# Phase 1 Test Pack Plan

## Objective
Create a foundational pytest test suite for Pheidipp backend, covering repositories, API endpoints, and async behavior. This phase establishes testing patterns and ensures core infrastructure reliability.

---

## Requirements

### 1. Directory Structure
```
tests/
├── conftest.py
├── unit/
│   ├── test_repositories/
│   └── test_services/
└── integration/
    ├── test_api/
    └── test_async/
```

### 2. Fixtures (`tests/conftest.py`)
- **`db_session`**: Async SQLite in-memory session for unit tests
- **`postgres_session`**: Async Postgres container session for integration tests
- **`client`**: FastAPI `TestClient` for API testing
- **`mock_redis`**: Mock for Redis dependency
- **`mock_minio`**: Mock for MinIO dependency

### 3. Test Coverage

#### Unit Tests (`tests/unit/`)
- **Repositories**: CRUD operations for all existing models (`Athlete`, `Activity`, `AthletePhysiology`, `AthleteWellness`, `AthleteFitness`)
- **Model Constraints**: Validate unique constraints, date ranges, and required fields
- **Async Session Management**: Ensure no session leaks, proper rollbacks on errors
- **Services**: Pure business logic (if any exists)

#### Integration Tests (`tests/integration/`)
- **API Endpoints**: Test all existing endpoints (success and error cases)
- **Pydantic Validation**: Ensure invalid payloads return `422 Unprocessable Entity`
- **Auth**: If implemented, test authentication and authorization
- **Async Behavior**: Verify `asyncio.to_thread()` is used for CPU-bound tasks

### 4. CI/CD
- **File**: `.github/workflows/test.yml`
- **Jobs**:
  1. **Unit Tests**: Run with SQLite (fast, isolated)
  2. **Integration Tests**: Run with Postgres container (realistic environment)
- **Triggers**: Pull requests and pushes to `main`
- **Runner**: Ubuntu latest
- **Services**: Postgres container for integration tests

### 5. Acceptance Criteria
- All tests pass
- 100% of existing endpoints tested
- 100% of existing repositories tested
- No test code outside the `tests/` directory

---

## Dependencies
Add the following to `pyproject.toml` or `requirements-dev.txt`:
- `pytest`
- `pytest-asyncio`
- `pytest-postgresql` (or equivalent for Postgres container management)
- `httpx` (for FastAPI `TestClient`)

---

## Assumptions
- Models exist: `Athlete`, `Activity`, `AthletePhysiology`, `AthleteWellness`, `AthleteFitness`
- Basic CRUD endpoints exist for these models
- Use `pytest.mark.asyncio` for async test functions
- Postgres in CI: Use GitHub Actions service container

---

## Out of Scope
- FIT file parsing tests
- TimescaleDB hypertable tests
- Performance/load tests

---

## Handoff Notes
- **Agent**: p-tester
- **Priority**: High
- **Phase**: 1 of 4 (Foundation)