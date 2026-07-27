---
name: test-infrastructure
description: >
  Load this when creating or modifying conftest.py files, shared test
  utilities under tests/utils/, or when the agent needs to understand
  the test directory structure and fixture hierarchy. Contains the
  canonical conftest patterns (db_session, client, engine lifecycle),
  directory structure rules, per-directory conftest conventions, and
  factory/builder conventions. Loaded by p-test-architect.
---

# Test Infrastructure

---

## Directory Structure

```
tests/
├── conftest.py               # Root: fixtures shared across ALL test layers
├── MOCKING_CONTRACT.md        # Contract: layer boundaries, canonical fixtures, anti-patterns
├── README.md                  # Accumulated do/don't lessons from DevOps failures
├── unit/
│   └── conftest.py            # Unit-specific: mock helpers
├── integration/
│   └── conftest.py            # Integration-specific: factory imports
├── api/
│   └── conftest.py            # API-specific: auth header builder
├── behaviour/
│   └── conftest.py            # Behaviour-specific: journey helpers
├── smoke/
│   └── conftest.py            # Smoke-specific
├── utils/
│   ├── factories.py           # Async model factories
│   ├── assertions.py          # Reusable assertion functions
│   ├── model_helpers.py       # ORM introspection
│   ├── schema_helpers.py      # DB schema introspection (sync psycopg2)
│   └── http_helpers.py        # HTTP helpers
└── test-manifest/
```

---

## conftest.py Hierarchy

### Root conftest.py (`tests/conftest.py`)

**Four canonical root fixtures:**

1. **`test_engine`** (function scope) — AsyncEngine per test, `poolclass=NullPool`
2. **`test_session_local`** (function scope) — `async_sessionmaker[AsyncSession]` bound to `test_engine`
3. **`db_session`** (function scope) — Single AsyncSession per test, rolled back at teardown, all tables truncated via `TRUNCATE TABLE <all> CASCADE`
4. **`client`** (function scope) — `httpx.AsyncClient` wired to FastAPI app via `ASGITransport`

**Pattern for `db_session` fixture (canonical sequence):**
1. Create session from session_local
2. Yield session to test
3. In finally: rollback, close, open cleanup session, TRUNCATE ALL CASCADE, close cleanup

**Critical: `NullPool` is mandatory** on every `create_async_engine` call in test infrastructure.

### Per-Directory conftest.py

A fixture is promoted to directory `conftest.py` when 2+ test files need it.
Promoted to root conftest when 2+ directories need it.

| Directory | What lives in its conftest.py |
|---|---|
| `tests/unit/` | Mock helpers, MagicMock/AsyncMock patterns |
| `tests/integration/` | Factory imports, schema helper imports |
| `tests/api/` | Auth header builders, client config |
| `tests/behaviour/` | Journey helpers, multi-step setup |

---

## tests/utils/ — Shared Helpers

### factories.py

- Named `make_<model>` (e.g., `make_user`)
- Signature: `async def make_<model>(db_session: AsyncSession, **kwargs) -> <ModelClass>`
- Each factory handles its own commit
- Factories set sensible defaults for all NOT NULL columns
- Every new factory registered in `MOCKING_CONTRACT.md` Canonical Fixtures

### assertions.py

Reusable assertion functions for cross-cutting invariants.

### model_helpers.py

ORM model introspection — no database required:
- `get_columns(Model)`, `get_indexes(Model)`, `get_check_constraints(Model)`
- `get_unique_constraints(Model)`, `get_foreign_keys_referencing(Model, table_name)`
- `get_enum_values(Model, column_name)`

### schema_helpers.py

DB schema introspection — requires sync psycopg2 engine because asyncpg
cannot service `inspect()` calls from greenlet context.
- `get_sync_database_url()`, `db_columns(table_name)`, `db_unique_constraints(table_name)`
- `db_check_constraints(table_name)`, `db_indexes(table_name)`, `db_foreign_keys(table_name)`

### http_helpers.py

- `auth_header(token: str) -> dict`
- `journey_setup(client, ...) -> tuple[UUID, str]`

---

## Factory Conventions

**When to create a factory:** object has NOT NULL columns the test doesn't care about,
same object shape needed by 2+ test files, multi-step construction sequence.

**When NOT to:** used once in one test (inline is clearer), would need 10+ kwargs
(split into focused factories instead).

---

## MOCKING_CONTRACT.md Registration

Every new fixture or factory must be registered in `tests/MOCKING_CONTRACT.md`'s
Canonical Fixtures table in the same session it is created.
