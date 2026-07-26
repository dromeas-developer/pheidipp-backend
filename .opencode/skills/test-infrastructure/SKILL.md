---
name: test-infrastructure
description: >
  Load this when creating or modifying conftest.py files, shared test
  utilities under tests/utils/, or when the agent needs to understand
  the test directory structure and fixture hierarchy. Contains the
  canonical conftest patterns (db_session, client, engine lifecycle),
  directory structure rules, per-directory conftest conventions, and
  factory/builder conventions. Does NOT contain domain-specific fixtures
  or production code imports — those are resolved at generation time via
  p-code-explorer. Loaded by p-test-architect (primary) when
  tests/conftest.py does not exist or when adding shared infrastructure.
  Also referenced by manifest-bootstrap for initial conftest.py creation.
location: .opencode/skills/test-infrastructure/SKILL.md
---

# Test Infrastructure

Load this skill when the agent needs to create, modify, or understand
`conftest.py` files, `tests/utils/` helpers, or the test directory
structure. This skill teaches **patterns and structure**, not
domain-specific code — production imports are resolved at generation time
by `p-code-explorer`.

---

## Directory Structure

```
tests/
├── conftest.py               # Root: fixtures shared across ALL test layers
├── MOCKING_CONTRACT.md        # Contract: layer boundaries, canonical fixtures, anti-patterns
├── README.md                  # Accumulated do/don't lessons from DevOps failures
├── unit/
│   └── conftest.py            # Unit-specific: mock helpers, MagicMock/AsyncMock patterns
├── integration/
│   └── conftest.py            # Integration-specific: factory imports, schema helpers
├── api/
│   └── conftest.py            # API-specific: client config, auth header builder
├── behaviour/
│   └── conftest.py            # Behaviour-specific: journey helpers, multi-step setup
├── smoke/
│   └── conftest.py            # Smoke-specific (if needed)
├── utils/                     # Shared helpers imported directly by test files
│   ├── factories.py           # Async model factories (make_<model>, ...)
│   ├── assertions.py          # Reusable assertion functions
│   ├── model_helpers.py       # ORM introspection (get_columns, get_indexes, ...)
│   ├── schema_helpers.py      # DB schema introspection (sync psycopg2 engine)
│   └── http_helpers.py        # HTTP helpers (auth_header, journey_setup, ...)
└── test-manifest/             # Manifest system (owned by p-test-architect + p-devops)
```

---

## conftest.py Hierarchy

### Root conftest.py (`tests/conftest.py`)

Holds fixtures shared across **multiple test layers** — the DB engine,
transactional session, and FastAPI test client. These are needed by
integration, API, and behaviour tests.

**Four canonical root fixtures:**

1. **`test_engine`** (function scope) — AsyncEngine per test, `poolclass=NullPool`.
   Creating a fresh engine per test avoids "Future attached to a different loop"
   errors because each test runs in its own event loop.

2. **`test_session_local`** (function scope) — `async_sessionmaker[AsyncSession]`
   bound to `test_engine`. Uses `expire_on_commit=False`, `autoflush=False`.

3. **`db_session`** (function scope) — Single AsyncSession per test.
   Rolled back at teardown, then **all tables truncated** via
   `TRUNCATE TABLE <all> CASCADE`. The truncation is non-negotiable:
   service-layer code calls `session.commit()`, and rollback only undoes
   uncommitted changes. Without truncation, committed data from one test
   contaminates the next. Truncation order: `reversed(Base.metadata.sorted_tables)`
   so child tables are truncated before parents. This is automatic — every
   table in the metadata is included, no manual maintenance.

4. **`client`** (function scope) — `httpx.AsyncClient` wired to the FastAPI
   app via `ASGITransport`, with `get_db` dependency-overridden to use
   `db_session`. Uses `base_url="http://testserver/api/v1"` so test paths
   resolve correctly.

**Root conftest.py also holds session-scoped schema setup:**

5. **`_prepare_database`** (session scope, autouse) — Creates all tables once
   at the start of the test session, truncates existing data first. Uses a
   temporary engine that is immediately disposed, so the per-test function-scoped
   engines are unaffected. `Base.metadata.create_all` has `IF NOT EXISTS`
   semantics — safe against an existing test database.

**Pattern for the `db_session` fixture (canonical sequence):**

```
1. Create session from session_local
2. Yield session to test
3. In finally:
   a. Rollback uncommitted changes
   b. Close session (catch MissingGreenlet — known async lifecycle edge case)
   c. Open a fresh cleanup session
   d. TRUNCATE TABLE <all> CASCADE (dynamically from Base.metadata.sorted_tables, reversed)
   e. Close cleanup session (catch MissingGreenlet)
```

**Critical: `NullPool` is mandatory.** Without `poolclass=NullPool`, the
engine's connection pool defers close to a background task that fires after
the async context is torn down, causing `MissingGreenlet`. This is the single
most common conftest defect and must be present on every `create_async_engine`
call in test infrastructure.

---

### Per-Directory conftest.py

Each test directory has its own `conftest.py` for fixtures scoped to that
layer. Create one when a directory needs shared fixtures — not before.

**Rule:** a fixture is promoted from a test file to the directory's
`conftest.py` when **2+ test files in that directory need it**. A fixture
is promoted to root `conftest.py` when **2+ directories need it**.

| Directory | What lives in its conftest.py |
|---|---|
| `tests/unit/` | AsyncMock/MagicMock helpers, mock fixture factories, patch helpers. Never imports DB or FastAPI. |
| `tests/integration/` | Factory function imports from `tests/utils/factories.py`, schema helper imports, service constructor fixtures. Inherits `db_session` from root. |
| `tests/api/` | Auth header builders, test client configuration helpers. Inherits `client` and `db_session` from root. |
| `tests/behaviour/` | Journey helpers (multi-step setup, domain-specific flow helpers), multi-step setup fixtures. Inherits `client` and `db_session` from root. |
| `tests/smoke/` | Same as behaviour, but for smoke-test-specific fixtures. |

Per-directory conftest.py files **do not redefine** root fixtures —
they inherit them via pytest's conftest discovery chain.

---

## tests/utils/ — Shared Helpers

`tests/utils/` holds shared helpers that test files **import directly**
(not through conftest.py). The distinction: conftest.py holds fixtures
(pytest-managed lifecycle); utils/ holds plain functions and classes.

### factories.py

Async factory functions for creating domain model instances in tests.
Each factory takes a `db_session` and kwargs, creates a row, commits it,
and returns the instance.

**Conventions:**
- Named `make_<model>` (e.g., `make_user`, `make_order`)
- Signature: `async def make_<model>(db_session: AsyncSession, **kwargs) -> <ModelClass>`
- Each factory handles its own commit — callers don't need to
- Factories set sensible defaults for all NOT NULL columns
- Every new factory is immediately registered in `MOCKING_CONTRACT.md` Canonical Fixtures

### assertions.py

Reusable assertion functions for cross-cutting invariants:
- `assert_no_secrets_in_text(text: str)` — assert no PII/credential fields in output
- Domain-specific assertions added as needed

### model_helpers.py

ORM model introspection — no database connection required:
- `get_columns(Model)` — dict of column name → Column object
- `get_indexes(Model)` — dict of index name → Index object
- `get_check_constraints(Model)` — list of CheckConstraint objects
- `get_unique_constraints(Model)` — list of UniqueConstraint objects
- `get_foreign_keys_referencing(Model, table_name)` — list of FKs
- `get_enum_values(Model, column_name)` — list of permitted enum values

### schema_helpers.py

Database schema introspection — **requires a sync psycopg2 engine** because
asyncpg cannot service `inspect()` calls from a greenlet context:

- `get_sync_database_url()` — convert the asyncpg URL to psycopg2
- `db_columns(table_name)` — list column dicts from the live DB
- `db_unique_constraints(table_name)` — list unique constraints
- `db_check_constraints(table_name)` — list check constraints
- `db_indexes(table_name)` — list indexes
- `db_foreign_keys(table_name)` — list foreign keys

**Pattern:** create a sync engine with psycopg2, call `inspect()`, fetch all
data inside the `with engine.connect()` block, dispose the engine. Do NOT
return inspector objects — they're bound to the connection.

### http_helpers.py

Async HTTP helpers for API and behaviour tests:
- `auth_header(token: str) -> dict` — build `{"Authorization": "Bearer <token>"}`
- `journey_setup(client, ...) -> tuple[UUID, str]` — standard multi-step setup flow for behaviour tests

---

## Fixture Lifecycle Rules

1. **Rollback + Truncate, not DROP/CREATE.** Truncation is faster and
   schema-stable. The `_prepare_database` session fixture creates tables once;
   per-test fixtures only clean data.

2. **Function scope for all data fixtures.** Session-scoped data fixtures
   leak state between tests. Only schema setup fixtures are session-scoped.

3. **Per-test engine with NullPool.** Avoids "Future attached to different
   loop" and prevents connection-pool teardown in the wrong async context.

4. **Commit fixture rows before rollback tests.** A test that calls
   `db_session.rollback()` after a service call must commit any fixture rows
   in their own transaction first. `flush()` doesn't survive rollback.

5. **Lazy initialization only.** Fixtures must not eagerly connect at
   import time. Collection (`--collect-only`) must succeed without a
   live database.

---

## Factory / Builder Conventions

When a test needs to construct a complex domain object, prefer a shared
factory over inline construction:

**Inline (only when the object is trivial and used once):**
```python
obj = SomeModel(id=uuid.uuid4(), name="test-value", ...)
```

**Factory (when 2+ tests need the same object shape):**
```python
# In tests/utils/factories.py
async def make_some_model(db_session: AsyncSession, *, name: str | None = None) -> SomeModel:
    obj = SomeModel(id=uuid.uuid4(), name=name or f"test-{uuid.uuid4()}")
    db_session.add(obj)
    await db_session.commit()
    return obj

# In test files
from tests.utils.factories import make_some_model
obj = await make_some_model(db_session)
```

**When to create a factory:**
- The object has NOT NULL columns the test doesn't care about → factory sets defaults
- The same object shape is needed by 2+ test files
- The object's construction requires a multi-step sequence (e.g., parent → child → grandchild dependency chain)

**When NOT to create a factory:**
- The object is used once, in one test — inline is clearer
- The test needs a specific mutation of a default field — pass it as kwarg to the factory
- The factory would need 10+ keyword arguments to cover all variations — split into focused factories

---

## Schema Introspection Pattern

Tests that verify schema properties (column types, constraints, indexes)
must use a **sync psycopg2 engine**, not the async session:

```python
from sqlalchemy import create_engine, inspect

def get_sync_database_url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

def db_columns(table_name: str) -> list[dict]:
    engine = create_engine(get_sync_database_url())
    try:
        with engine.connect() as conn:
            inspector = inspect(conn)
            return list(inspector.get_columns(table_name))
    finally:
        engine.dispose()
```

**Why this is necessary:** `asyncpg` cannot service synchronous `inspect()`
calls from a greenlet context — it raises `MissingGreenlet`. The psycopg2
engine is fully synchronous and works from any context.

---

## MOCKING_CONTRACT.md Registration

Every new fixture or factory added to the test infrastructure must be
registered in `tests/MOCKING_CONTRACT.md`'s Canonical Fixtures table
**in the same session it is created.** The contract is always checked
before writing any test (p-test-architect Step 6) — if the contract
doesn't know about a fixture, it can't enforce reuse of it.

Registration entries follow this format:

| Fixture/Helper Name | Location | Scope | What it is for |
|---|---|---|---|
| `db_session` | `tests/conftest.py` | function | Isolated AsyncSession with auto-rollback and post-test truncation |
| `client` | `tests/conftest.py` | function | httpx.AsyncClient wired to FastAPI app with db_session override |
| `make_some_model` | `tests/utils/factories.py` | function | Async factory for a domain model row (commits) |

---

## Creation Rules

- `tests/conftest.py` is created by `manifest-bootstrap` (initial) or by
  p-test-architect (if missing). Load this skill for the patterns; use
  `p-code-explorer` to resolve production imports (model classes, app
  factory, session factory, Base metadata).
- Per-directory `conftest.py` files are created by p-test-architect on
  first need — when a fixture is needed by 2+ test files in that directory.
- `tests/utils/*.py` files are created by p-test-architect when a helper
  function is needed by 2+ test files. The first file in each category
  creates the module; subsequent helpers are added to it.
