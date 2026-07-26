# DevOps Report — GAP-PHASE-1-TESTS
Date: 2026-07-25
Validator report: n/a (test-only plan — no production code changes)
Test execution group: feature

## Implementation State
- **Base commit:** `3e91bb4`
- **Current commit:** `007953d`
- **Touched areas:** app (models, services, schemas, api), tests, alembic, opencode, reports
- **Plan scope:** test-only — gap analysis phase 1, batch 1: auth & identity tests
- **Session delta note:** The committed delta contains a wider type-enforcement-audit session plus opencode agent changes. The test files relevant to this plan (`tests/unit/test_auth_service.py`, `tests/unit/test_auth_schemas.py`, `tests/unit/test_ip_utils.py`, `tests/unit/test_token_security.py`, `tests/integration/test_auth_db.py`, `tests/api/test_require_self.py`) are untracked/new files. The plan implements test code only — no migration or model changes are needed.

## Result: FAIL

Tests: 30 passed / 2 failed / 0 skipped
Root causes identified: 1

## Checks

| Check | Status | Notes |
|---|---|---|
| Idempotency (no prior PASS) | ✅ N/A | No prior devops report found |
| Implementation state read | ✅ | git-session-delta recovered |
| Validator pre-flight | ⏭️ Skipped | Test-only plan — no production code changes to validate |
| Test manifest present | ✅ | `tests/test-manifest/phase-1-1.yaml` |
| Services healthy | ✅ | api, db, minio, litellm all healthy |
| Migration file present (coder-generated) | ⏭️ Skipped | `prerequisites.migrations: false` |
| Migration drift reviewed | ⏭️ Skipped | No migrations in scope |
| TimescaleDB augmentation | ⏭️ N/A | No migrations in scope |
| Test DB upgrade clean | ⏭️ Skipped | No migrations in scope |
| No pending model changes (test DB) | ⏭️ Skipped | No migrations in scope |
| Test suite | ❌ | 30 passed, 2 failed, 0 skipped |
| Manifest updated (executable + passed) | ✅ | 30 functions set to `passed: true`, 2 set to `passed: false`; 5 files promoted |
| Prod DB upgrade clean | ⏭️ Skipped | No migrations in scope |
| Application build clean | ⏭️ Skipped | No code changes to verify |

## Test Execution

Execution group: feature
Tests run: 32 selectors across 6 test files (all functions with `passed: false`)

### Files executed & results
| File | Type | Passed | Failed | Status |
|---|---|---|---|---|
| `tests/unit/test_auth_service.py` | unit | 8 | 2 | generated |
| `tests/unit/test_auth_schemas.py` | unit | 3 | 0 | ✅ promoted |
| `tests/unit/test_ip_utils.py` | unit | 7 | 0 | ✅ promoted |
| `tests/unit/test_token_security.py` | unit | 6 | 0 | ✅ promoted |
| `tests/integration/test_auth_db.py` | integration | 2 | 0 | ✅ promoted |
| `tests/api/test_require_self.py` | api | 4 | 0 | ✅ promoted |

## Infrastructure Fixes

| File | Change | Reason |
|---|---|---|
| `pytest.ini` | Added `pythonpath = .` | `ModuleNotFoundError: No module named 'app'` when pytest runs inside Docker container — `/app` was not on `sys.path`. This is a test framework configuration fix. No existing MOCKING_CONTRACT.md entry matches this pattern (new pattern). |

## Root Cause Analysis

### RC1 — Test mock doesn't simulate `add()` repository side-effect (set `id` in-place)

- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** Confirmed
- **Evidence:**
  - Both failing tests mock `auth_service.<repository>.add` as a simple return-value mock that returns a separate MagicMock, but the real `AthleteRepository.add()` and `RefreshTokenRepository.add()` call `session.add(obj)`, `session.flush()`, and `session.refresh(obj)` — which populates `id` on the original object **in-place**.
  - **Failure 1** (`test_register_creates_athlete_auth_profile_token_atomically`): The mock sets `auth_service.athletes.add.return_value = mock_athlete` (a separate MagicMock with `id` set). But the service reads `athlete.id` from the **original** `Athlete(email=..., onboarding_complete=False)` instance passed to `add()`, not from the return value. Since the mock doesn't mutate the argument in-place, `athlete.id` remains `None`, and `AuthResult(athlete_id=None, ...)` fails the assertion.
  - **Failure 2** (`test_refresh_valid_token_rotates_atomically`): The mock `auth_service.refresh_tokens.add` returns a default MagicMock (no `return_value` set). The service creates a new `RefreshToken(...)` instance, calls `await self.refresh_tokens.add(replacement)`, then reads `replacement.id`. Since the mock doesn't flush/refresh the original object, `replacement.id` is `None`, and `existing.replaced_by_refresh_token_id` is set to `None`, failing the assertion.
  - Inspected `app/repositories/athlete_repository.py:add()` and `app/repositories/refresh_token_repository.py:add()` — both call `self.session.add(obj)`, `await self.session.flush()`, `await self.session.refresh(obj)` then return `obj`.
  - Inspected `app/services/auth_service.py:register()` (lines ~108-111) and `rotate_refresh_token()` (lines ~260-263) — both read `athlete.id` / `replacement.id` from the original instance passed to `add()`, which is correct for the real repository but incompatible with the current mock setup.
  - Inspected test setup at `tests/unit/test_auth_service.py` lines 52-68 (`_mock_repositories`) and the individual test arrangements.

- **Files:**
  - **app:** none (app code is correct — it reads `id` from the original instance after `add()`, which is the standard SQLAlchemy pattern)
  - **test:** `tests/unit/test_auth_service.py` — both failing tests need mock `side_effect` (or equivalent) to simulate the in-place `id` population that `session.flush()` + `session.refresh()` performs

- **Affected failures:**
  1. `TestRegister::test_register_creates_athlete_auth_profile_token_atomically`
  2. `TestRefreshToken::test_refresh_valid_token_rotates_atomically`

- **Suggested fix:**
  Replace the return-value mock for `auth_service.athletes.add` and `auth_service.refresh_tokens.add` with a `side_effect` function that sets `id` on the argument:
  ```python
  # For Failure 1 — athletes.add
  async def _mock_add(athlete):
      athlete.id = uuid.uuid4()
      return athlete
  auth_service.athletes.add = AsyncMock(side_effect=_mock_add)

  # For Failure 2 — refresh_tokens.add
  async def _mock_add(token):
      token.id = uuid.uuid4()
      return token
  auth_service.refresh_tokens.add = AsyncMock(side_effect=_mock_add)
  ```
  This simulates what the real repository does: flushes and refreshes the ORM instance, which populates `id` in-place. The alternative — modifying the service to read return values instead — would couple the service to mock behaviour and deviate from standard SQLAlchemy patterns.

## Routing Summary

| Owner | Root Causes | Failures |
|---|---|---|
| p-coder | — | — |
| p-test-architect | RC1 | 2 |
| p-devops | — | — |
| p-implementation-architect | — | — |
| Unassigned | — | — |

## Recommended Execution Order

Only one RC identified. No ordering dependency.

1. **RC1** — Fix the mock `add()` in `tests/unit/test_auth_service.py` to use `side_effect` instead of `return_value` for both `auth_service.athletes.add` and `auth_service.refresh_tokens.add`, then re-run the 2 failing tests.

## Full Failure Detail

### RC1 — Test mock doesn't simulate `add()` repository side-effect (2 failures)

### TestRegister::test_register_creates_athlete_auth_profile_token_atomically [RC1]
```python
AssertionError: assert None == UUID('1226bbb5-bf7f-400b-b6ed-5b751dc0e80b')
 +  where None = AuthResult(athlete_id=None, ...).athlete_id
 +  and   UUID('1226bbb5-...') = <MagicMock name='mock.add()' id='...'>.id
```
**Root cause:** `auth_service.athletes.add` is mocked with `return_value = mock_athlete` (separate object). Service reads `athlete.id` from the original `Athlete` instance that was passed to `add()` — but the mock never set `id` on it. Result: `athlete_id=None`.

### TestRefreshToken::test_refresh_valid_token_rotates_atomically [RC1]
```python
AssertionError: assert None is not None
 +  where None = <MagicMock name='mock.get_by_token_hash()' id='...'>.replaced_by_refresh_token_id
```
**Root cause:** `auth_service.refresh_tokens.add` returns a default MagicMock (no return_value set). Service creates a new `RefreshToken(...)`, calls `add()`, then reads `replacement.id` — which is `None`. Sets `existing.replaced_by_refresh_token_id = None`. Assertion fails.

## Next Step
→ FAIL: 2 tests have unresolved mocks. Route RC1 to `p-test-architect` for mock fix. After fix, run a Test Pack re-verification (or full Feature scope if preferred) before final promotion of `tests/unit/test_auth_service.py`.
