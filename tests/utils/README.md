# tests/utils/

Shared test infrastructure — async factories and helpers used across unit and integration
test suites. Factories create real ORM model rows via the `db_session` fixture; no
additional mocking is required at this level.

## Contents
### Factories
| File | Covers |
|---|---|
| `factories.py` | `make_athlete` (creates Athlete row with unique email); `make_athlete_with_profile` (creates Athlete + matching AthleteProfile row) |
| `onboarding_builders.py` | `make_profile_input`, `make_preferences_input`, `make_goal_input` — typed-input constructors for `OnboardingService.complete_onboarding` |

## Mock Boundaries
- Factories use the real `db_session` fixture (function-scoped, auto-rollback) from `tests/conftest.py` — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- No mocks at this level; factories produce real ORM instances for test setup