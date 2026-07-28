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

### Onboarding
| File | Covers |
|---|---|
| `test_onboarding_endpoints.py` | TestPostOnboardingEndpoint (201 happy path, 409 re-onboarding, 422 invalid goal_type, 404 missing athlete, 403 cross-athlete, 422 invalid timezone), TestGetOnboardingStatusEndpoint (status before/after onboarding), TestGetProfileEndpoint (returns registered profile, 403 cross-athlete), TestPatchProfileEndpoint (height_cm update, immutable fields rejected, unknown field rejected), TestGetPreferencesEndpoint (404 before onboarding, populated after), TestPatchPreferencesEndpoint (day-level merge, top-level overwrite, unknown field rejected), TestGetTwinEndpoints (404 before, bootstrap state after lt1<lt2 fitness/fatigue/form=0, twin history returns bootstrap entry) |

## Mock Boundaries
- External APIs, message bus, and agents are mocked; DB (test_pheidipp), services, repositories, and the FastAPI app are real — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Uses the `client` fixture from `tests/conftest.py` (wraps `db_session`, wires `app.dependency_overrides[get_db]`)
- No shared conftest.py at this level; fixtures are defined per-file
