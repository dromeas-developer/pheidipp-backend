---
name: manifest-bootstrap
description: >
  Load this when the test manifest does not exist (index.yaml is missing).
  Contains the initial file creation logic for the test manifest system:
  conftest.py, MOCKING_CONTRACT.md template, creation order, and initial
  values. Loaded by p-test-architect only when
  tests/test-manifest/index.yaml is absent.
---

# Manifest Bootstrap

Load this skill only when `tests/test-manifest/index.yaml` does not exist.

The manifest structure is defined in `tests/test-manifest/SCHEMA.md`.
Read that file via `get_files` before creating anything.

---

## What Gets Created

1. **`tests/conftest.py`** — Root conftest with canonical fixtures
   (`test_engine`, `test_session_local`, `db_session`, `client`).
   Load `test-infrastructure` skill for patterns, use `p-code-explorer`
   to resolve production imports.
2. **`tests/MOCKING_CONTRACT.md`** — The fixture and mock-boundary contract
3. **`tests/test-manifest/index.yaml`** — Cross-phase registry with empty selection groups
4. **`tests/test-manifest/phase-N-Mx.yaml`** — First sub-phase file

---

## Creation Order

1. Create `tests/conftest.py` — must exist before any test file
2. Create `tests/MOCKING_CONTRACT.md` — must exist before any test file
3. Create `tests/test-manifest/index.yaml`
4. Create `tests/test-manifest/phase-N-Mx.yaml`

---

## MOCKING_CONTRACT.md Template

### Layer Boundaries

| Test Directory | What is Mocked | What is Real |
|---|---|---|
| `tests/unit/` | External APIs, DB, message bus | The unit under test |
| `tests/integration/` | External APIs, message bus | DB, services, repositories |
| `tests/api/` | External APIs, message bus, agent | DB, services, FastAPI app |
| `tests/behaviour/` | External APIs, message bus | Full stack |

### Canonical Fixtures

| Fixture Name | Location | Scope | What it is for |
|---|---|---|---|
| `test_engine` | `tests/conftest.py` | function | Per-test AsyncEngine with NullPool |
| `test_session_local` | `tests/conftest.py` | function | async_sessionmaker bound to test_engine |
| `db_session` | `tests/conftest.py` | function | Isolated AsyncSession with truncation |
| `client` | `tests/conftest.py` | function | httpx.AsyncClient wired to FastAPI app |

### Known Anti-Patterns

| Pattern | Symptom | Correct Approach |
|---|---|---|
| Opening a second AsyncSession | `InterfaceError` | Use `db_session` fixture |
| Mocking at wrong boundary | Integration test mocks repository | Mock external APIs only |
| Eager connection at import time | Collection fails | Lazy fixture initialization |
| Missing `poolclass=NullPool` | `MissingGreenlet` | Always use NullPool |
| Duplicated fixture | Same fixture different name | Check Canonical Fixtures first |

---

## Initial Values

**index.yaml:**
- `version: "1.0"`, `last_reviewed_at: <current ISO 8601>`
- All `selection.*` groups: `[]`

**phase-N-Mx.yaml:**
- `version: "1.0"`, `plan_id: <from BRD>`
- `generated_at: <current ISO 8601>`, `last_reviewed_at: <current ISO 8601>`
- `prerequisites.migrations: <bool>`, `files: {}`
- `coverage.events.covered: []`, `coverage.invariants.covered: []`
