# tests/integration/

## Purpose
Verifies that services, repositories, and ORM models interact correctly against a real
PostgreSQL test database. External APIs and the message bus are mocked, but the database
session, transaction boundaries, and constraint enforcement are exercised end-to-end through
the `db_session` fixture.

## Contents
### Authentication
| File | Covers |
|---|---|
| `test_auth_db.py` | Athlete email uniqueness (duplicate email IntegrityError pgcode 23505, case-insensitive matching via normalize_email before the functional lower(email) index fires) |

## Mock Boundaries
- External APIs and message bus are mocked; DB (test_pheidipp) is real — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Uses the `db_session` fixture from `tests/conftest.py` (function-scoped, auto-rollback + post-test truncation)
- No shared conftest.py at this level; fixtures are defined per-file
