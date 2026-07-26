# tests/api/

## Purpose
Verifies FastAPI route handlers, dependency injection, and request/response flows against
a real PostgreSQL test database. External APIs, the message bus, and agents are mocked, but
the full stack from HTTP client through services and repositories is exercised via the
`client` fixture.

## Contents
### Authentication
| File | Covers |
|---|---|
| `test_require_self.py` | require_self dependency (own JWT succeeds, different athlete JWT returns 403), get_current_athlete_id (expired JWT returns 401, missing Authorization header returns 401) |

## Mock Boundaries
- External APIs, message bus, and agents are mocked; DB (test_pheidipp), services, repositories, and the FastAPI app are real — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Uses the `client` fixture from `tests/conftest.py` (wraps `db_session`, wires `app.dependency_overrides[get_db]`)
- No shared conftest.py at this level; fixtures are defined per-file
