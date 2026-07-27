# tests/utils/

## Purpose
Shared test infrastructure — async factories and helpers used across unit and integration
test suites. Factories create real ORM model rows via the `db_session` fixture; no
additional mocking is required at this level.

## Contents
### Factories
| File | Covers |
|---|---|
| `factories.py` | `make_athlete` async factory: creates an Athlete row with a unique email (or caller-supplied email) |

## Mock Boundaries
- Factories use the real `db_session` fixture (function-scoped, auto-rollback) from `tests/conftest.py` — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- No mocks at this level; factories produce real ORM instances for test setup
