---
name: manifest-bootstrap
description: >
  Load this when the test manifest does not exist (index.yaml is missing).
  Contains the initial file creation logic for the test manifest system:
  conftest.py, MOCKING_CONTRACT.md template, creation order, and initial
  values. The manifest structure (index.yaml and phase file schema) is
  defined in tests/test-manifest/SCHEMA.md — this skill references it
  rather than duplicating it. The conftest.py patterns come from the
  test-infrastructure skill — load that skill before creating conftest.py
  for the canonical fixture patterns, then resolve production imports via
  p-code-explorer. Loaded by p-test-architect only when
  tests/test-manifest/index.yaml is absent.
location: .opencode/skills/manifest-bootstrap/SKILL.md
---

# Manifest Bootstrap

Load this skill only when `tests/test-manifest/index.yaml` does not exist.
This is the initial creation path — everything else (test generation,
phase file updates, diagnostics) proceeds normally per the Generate
protocol. This skill covers only the four infrastructure files that
must exist before any test generation can begin.

The manifest structure (index.yaml schema, phase file schema, ownership
rules, selection group rules) is defined in `tests/test-manifest/SCHEMA.md`.
**Read that file via `get_files` before creating anything** — this skill
provides the creation logic (what files, what order, what initial values)
but not the schema structure itself. Do not duplicate SCHEMA.md content
here; read it and use it as the authoritative reference for the file
structure.

---

## What Gets Created

1. **`tests/conftest.py`** — Root conftest with the four canonical fixtures
   (`test_engine`, `test_session_local`, `db_session`, `client`) and the
   session-scoped `_prepare_database` schema setup. Load the
   `test-infrastructure` skill for the canonical fixture patterns (engine
   lifecycle, NullPool, truncation, client wiring), then use
   `p-code-explorer` to resolve the production imports (model classes, app
   factory, session factory, Base metadata) and write the file.
2. **`tests/MOCKING_CONTRACT.md`** — The fixture and mock-boundary contract
   with the initial layer-boundary table and canonical fixtures table
   (template below)
3. **`tests/test-manifest/index.yaml`** — The cross-phase registry with
   empty selection groups (structure per SCHEMA.md)
4. **`tests/test-manifest/phase-N-Mx.yaml`** — The first sub-phase file
   with the full schema (structure per SCHEMA.md), `files` block empty,
   `prerequisites.migrations` set from the plan

---

## Creation Order

**Before creating anything:** Read `tests/test-manifest/SCHEMA.md` via
`get_files` to get the authoritative schema structure for `index.yaml`
and `phase-N-Mx.yaml`. Load the `test-infrastructure` skill for the
canonical conftest.py patterns. This skill provides the creation logic
only — the schema structure lives in SCHEMA.md and the fixture patterns
live in test-infrastructure.

1. **Create `tests/conftest.py` first** — it must exist before any test
   file is written, as every integration/api/behaviour test depends on
   `db_session` and `client`. Load the `test-infrastructure` skill for the
   canonical fixture patterns (engine lifecycle, NullPool, truncation,
   client wiring), then delegate to `p-code-explorer` to resolve the
   production imports (model classes from `app.models`, app factory from
   `app.main`, session factory from `app.db.session`, Base metadata from
   `app.db.base`). The skill provides the structural patterns; the explorer
   provides the specific import paths. Write the file yourself — the
   explorer does not write code.
2. **Create `tests/MOCKING_CONTRACT.md`** — it must exist before any
   test file is written, as every generated test must conform to it
3. **Create `tests/test-manifest/index.yaml`** — the cross-phase registry
   with empty selection groups (structure from SCHEMA.md)
4. **Create `tests/test-manifest/phase-N-Mx.yaml`** — the first sub-phase
   file with empty `files` block and `prerequisites.migrations` from the
   plan (structure from SCHEMA.md)

After creation, proceed to Step 3 (Build Capability Inventory) and
Step 5a (Update Manifest) as normal.

---

## MOCKING_CONTRACT.md Template

This is the only content this skill provides that is NOT in SCHEMA.md.
The contract structure must be initialised in this exact shape — it is
meant to be scanned in seconds, not read as prose.

### Layer Boundaries

| Test Directory | What is Mocked | What is Real | Async Session Notes |
|---|---|---|---|
| `tests/unit/` | External APIs, DB, message bus | The unit under test (service, repository, model) | N/A — no async session |
| `tests/integration/` | External APIs, message bus | DB (test_pheidipp), services, repositories | One AsyncSession per test via `db_session` fixture |
| `tests/api/` | External APIs, message bus, agent | DB (test_pheidipp), services, repositories, FastAPI app | `client` fixture wraps `db_session` |
| `tests/behaviour/` | External APIs, message bus | Full stack (DB, services, repositories, FastAPI) | `client` fixture wraps `db_session` |

### Canonical Fixtures

| Fixture Name | Location | Scope | What it is for |
|---|---|---|---|
| `test_engine` | `tests/conftest.py` | function | Per-test AsyncEngine with NullPool (avoids loop errors) |
| `test_session_local` | `tests/conftest.py` | function | async_sessionmaker[AsyncSession] bound to test_engine |
| `db_session` | `tests/conftest.py` | function | Isolated AsyncSession with auto-rollback and post-test truncation |
| `client` | `tests/conftest.py` | function | httpx.AsyncClient wired to FastAPI app with db_session override |
| *(per-directory fixtures added here as they are created)* | `tests/<layer>/conftest.py` | varies | Layer-specific fixtures (unit mock helpers, integration factory imports, api auth builders, behaviour journey helpers) |
| *(factory helpers added here as they are created)* | `tests/utils/factories.py` | function | Async model factories — import directly, not through conftest |
| *(assertion helpers added here as they are created)* | `tests/utils/assertions.py` | function | Reusable assertion functions |
| *(model helpers added here as they are created)* | `tests/utils/model_helpers.py` | function | ORM introspection (no DB required) |
| *(schema helpers added here as they are created)* | `tests/utils/schema_helpers.py` | function | DB schema introspection (sync psycopg2 engine) |
| *(HTTP helpers added here as they are created)* | `tests/utils/http_helpers.py` | function | HTTP client helpers for api/behaviour tests |

### Known Anti-Patterns

| Pattern | Symptom | Correct Approach |
|---|---|---|
| Opening a second AsyncSession | `InterfaceError: another operation is in progress` | Use the `db_session` fixture; monkey-patch `AsyncSessionLocal` in worker tests |
| Mocking at the wrong boundary | Integration test mocks a repository | Mock only external APIs at the service boundary; mock the transport (session), not the collaborator (repository) |
| Eager connection at import time | Collection fails with connection error | Use lazy fixture initialization; no database access at import time |
| `create_async_engine` without `poolclass=NullPool` | `MissingGreenlet` at teardown | Always use `poolclass=NullPool` in test engines |
| Schema introspection with async session | `MissingGreenlet` from `inspect()` | Use a sync psycopg2 engine (see `test-infrastructure` skill) |
| Duplicated fixture with different name/scope | Two tests use separate-but-identical fixtures | Check MOCKING_CONTRACT.md Canonical Fixtures before writing; reuse existing fixtures |
| Factory inline in test file when 2+ tests need it | Same object construction repeated across files | Extract to `tests/utils/factories.py`; register in Canonical Fixtures table |

---

## Initial Values

After reading SCHEMA.md for the structure, populate these initial values:

**index.yaml:**
- `version: "1.0"`
- `last_reviewed_at: <current ISO 8601>`
- All `selection.*.unit/integration/behaviour/api` groups: `[]` (empty)

**phase-N-Mx.yaml:**
- `version: "1.0"`
- `plan_id: <from the batch BRD>`
- `generated_at: <current ISO 8601>`
- `last_reviewed_at: <current ISO 8601>`
- `prerequisites.migrations: <bool from plan's stated requirements>`
- `files: {}` (empty — populated by Step 5a)
- `coverage.events.covered: []`
- `coverage.invariants.covered: []`

### Key Rules
- All selection groups start empty — DevOps populates them via promotion
- `files` starts empty — populated by Step 5a after the capability inventory
- Phase files are immutable after sub-phase completion
- This file is NEVER written again by the Test Architect after creation
