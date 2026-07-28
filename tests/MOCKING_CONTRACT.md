# Fixture & Mocking Contract

## Layer Boundaries

| Test Directory | What is Mocked | What is Real | Async Session Notes |
|---|---|---|---|
| `tests/unit/` | DB session (AsyncSession), external APIs | The unit under test (service, repository, model, utility function) | Mock AsyncSession; no `db_session` fixture needed |
| `tests/integration/` | External APIs, message bus | DB (test_pheidipp), services, repositories | One AsyncSession per test via `db_session` fixture |
| `tests/api/` | External APIs, message bus, agents | DB (test_pheidipp), services, repositories, FastAPI app | `client` fixture wraps `db_session` |
| `tests/behaviour/` | External APIs, message bus | Full stack (DB, services, repositories, FastAPI) | `client` fixture wraps `db_session` |

## Canonical Fixtures

| Fixture Name | Location | Scope | What it is for |
|---|---|---|---|
| `test_engine` | `tests/conftest.py` | function | Per-test AsyncEngine with NullPool |
| `test_session_local` | `tests/conftest.py` | function | async_sessionmaker[AsyncSession] bound to test_engine |
| `db_session` | `tests/conftest.py` | function | Isolated AsyncSession with auto-rollback and post-test truncation |
| `client` | `tests/conftest.py` | function | httpx.AsyncClient wired to FastAPI app with db_session override |
| `_prepare_database` | `tests/conftest.py` | session | Creates all tables once at session start |
| *(per-directory fixtures added here as they are created)* | `tests/<layer>/conftest.py` | varies | Layer-specific fixtures |
| `make_athlete` | `tests/utils/factories.py` | function | Async factory: creates Athlete row with unique email (commits) |
| `make_athlete_with_profile` | `tests/utils/factories.py` | function | Async factory: creates Athlete + matching AthleteProfile row (commits) |
| *(assertion helpers added here as they are created)* | `tests/utils/assertions.py` | function | Reusable assertion functions |
| *(model helpers added here as they are created)* | `tests/utils/model_helpers.py` | function | ORM introspection (no DB required) |
| *(schema helpers added here as they are created)* | `tests/utils/schema_helpers.py` | function | DB schema introspection (sync psycopg2 engine) |
| *(HTTP helpers added here as they are created)* | `tests/utils/http_helpers.py` | function | HTTP client helpers for api/behaviour tests |

## Known Anti-Patterns

| Pattern | Symptom | Correct Approach |
|---|---|---|
| Opening a second AsyncSession | `InterfaceError: another operation is in progress` | Use the `db_session` fixture; monkey-patch `AsyncSessionLocal` in worker tests |
| Mocking at the wrong boundary | Integration test mocks a repository | Mock only external APIs at the service boundary; mock the transport (session), not the collaborator (repository) |
| Eager connection at import time | Collection fails with connection error | Use lazy fixture initialization; no database access at import time |
| `create_async_engine` without `poolclass=None` | `MissingGreenlet` at teardown | Always use `poolclass=None` (NullPool) in test engines |
| Schema introspection with async session | `MissingGreenlet` from `inspect()` | Use a sync psycopg2 engine (see `test-infrastructure` skill) |
| Duplicated fixture with different name/scope | Two tests use separate-but-identical fixtures | Check MOCKING_CONTRACT.md Canonical Fixtures before writing; reuse existing fixtures |
| Factory inline in test file when 2+ tests need it | Same object construction repeated across files | Extract to `tests/utils/factories.py`; register in Canonical Fixtures table |
| Monkeypatching repository `add` or `AsyncSession.flush` to raise after `await original` | `MissingGreenlet: greenlet_spawn has not been called; can't await_only() here` | Pre-insert a conflicting row (e.g., `AthletePreferences`) to trigger a natural `IntegrityError` on the unique constraint. **Critical:** capture all ORM PKs (`athlete.id`, `profile.id`) into plain UUID locals before the `pytest.raises(IntegrityError)` block — SQLAlchemy clears ORM `__dict__` on session failure, so any post-error attribute access triggers lazy-load → `MissingGreenlet` |
