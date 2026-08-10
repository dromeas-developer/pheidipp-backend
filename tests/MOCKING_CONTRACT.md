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
| `make_training_goal` | `tests/utils/factories.py` | function | Async factory: creates TrainingGoal row with configurable goal_type, event_type, fitness_level (commits) |
| `make_twin_state` | `tests/utils/factories.py` | function | Async factory: creates TwinState row with configurable data_tier, confidence, metric_confidence (commits) |
| `make_athlete_preferences` | `tests/utils/factories.py` | function | Async factory: creates AthletePreferences row with years_structured_training, weekly_schedule (commits) |
| `make_athlete_fitness` | `tests/utils/factories.py` | function | Async factory: creates AthleteFitness row with aggregate + time_constants (commits) |
| `make_athlete_physiology` | `tests/utils/factories.py` | function | Async factory: creates AthletePhysiology row with max_hr/lt1/lt2/cp (commits) |
| `make_activity` | `tests/utils/factories.py` | function | Async factory: creates Activity row with configurable source/duration/has_power/has_hr/has_gps (commits) |
| `WEEKLY_SCHEDULE_TEMPLATE` | `tests/utils/factories.py` | constant | Default weekly schedule dict for AthletePreferences factory |
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
| Async fixture declared as bare `@pytest.fixture` on `async def` (or as `@pytest_asyncio.fixture` without explicit `loop_scope="session"`) while the marker hook binds tests to the session loop | `RuntimeError: got Future attached to a different loop` | The marker hook at `tests/conftest.py:pytest_collection_modifyitems` binds every async test to `loop_scope="session"` (so the procrastinate app's open-context `ContextVar` is set on the session loop). pytest-asyncio's "fixture loop scope is determined by the test" rule *should* propagate the session loop to function-scoped async fixtures, but per-file bare `@pytest.fixture` on `async def` and `@pytest_asyncio.fixture(...)` without explicit `loop_scope` are sensitive to the order in which the marker injection and fixture loop-scope resolution happen — a subtle ordering artefact can leave a Future created under one loop context and awaited in another. **Always declare async fixtures that should run in the session loop as `@pytest_asyncio.fixture(loop_scope="session")`** — see `db_session` and `client` in `tests/conftest.py` and the per-file `athlete_with_profile` fixtures in `tests/api/test_onboarding_endpoints.py` and `tests/api/test_require_self.py` for the canonical pattern |
