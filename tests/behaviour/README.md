# tests/behaviour/

## Purpose
Verifies end-to-end user journeys across the full HTTP stack — from
authenticated HTTP requests through services, repositories, and the real
test database. External APIs, the message bus, and agents are mocked, but
every layer from FastAPI route handler down to ORM persistence is exercised
in sequence.

## Contents
### Onboarding
| File | Covers |
|---|---|
| `test_onboarding_journey.py` | TestOnboardingJourney: full journey pre-onboarding (status false, profile populated, prefs 404, twin 404) → POST /onboarding → post-onboarding (status true, profile enriched, prefs populated, twin bootstrap values, twin history count=1) → duplicate POST returns 409; cross-athlete 403 blocks all 5 GET endpoints |

## Mock Boundaries
- External APIs, message bus, and agents are mocked; DB (test_pheidipp), services, repositories, and the full FastAPI app are real — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Uses the `client` fixture from `tests/conftest.py` (wraps `db_session`, wires `app.dependency_overrides[getDb]`)
- No shared conftest.py at this level; fixtures are defined per-file
