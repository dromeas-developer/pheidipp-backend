# tests/api/

## Purpose

API tests exercise FastAPI route handlers through `httpx.AsyncClient` against the real application, with the DB session overridden to share the per-test transaction. The full service and repository layers are wired — no external services are mocked at this level. These tests assert HTTP status codes, response shapes, auth guards, and the public contract visible to frontend consumers.

## Contents

### Authentication
| File | Covers |
|---|---|
| `test_auth_endpoints.py` | Auth API: register, login, refresh — happy path, duplicate email, validation, cross-athlete 403, missing bearer 401 |

### Onboarding
| File | Covers |
|---|---|
| `test_onboarding_endpoints.py` | Onboarding API: POST/GET/PATCH endpoints — 201 happy path, 409 idempotency, 422 invalid, 403 cross-athlete |
| `test_onboarding_endpoints_async_plan.py` | Onboarding API: async plan-generation contract — 201 before worker task, GET /plan 404 in the window, no plan fields in response |

### Plans
| File | Covers |
|---|---|
| `test_plan_endpoints.py` | Plan API: GET /plan, /sessions, /upcoming, /checkpoints — 200 happy path, plans after async generate_plan task, 404 no-plan, 403 cross-athlete, 401 missing bearer |
| `test_plan_endpoints_async.py` | Plan API: GET /plan 200 after generate_plan worker task completes; sub-endpoint response shapes after PlanQueryService refactor |

### Coaching
| File | Covers |
|---|---|
| `test_coach_endpoints_async.py` | Coach API: GET /coach/messages after async generation; POST /coach/first-message 409/201 fallback contract |

## Mock Boundaries

- None — API tests are fully integrated against the real FastAPI app, real DB, and real services. See `tests/MOCKING_CONTRACT.md` for the authoritative per-layer table.
- HTTP client is `httpx.AsyncClient` with `base_url="http://testserver/api/v1"`.
