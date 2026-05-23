# Test Auth Integration Fixes

Fix all integration tests to register via `POST /auth/register` and send `Authorization: Bearer <token>` headers, per the findings in `reports/phase_1f_jwt_auth_route_authorization_devops.md`.

---

## 1. Add JWT env vars to test config

- Objective: Ensure tests can generate and validate JWTs.
- File: `.env.test` [MODIFY]
- Actions:
  - Add `JWT_SECRET_KEY=test-secret-key-not-for-production`
  - Add `JWT_ALGORITHM=HS256`
  - Add `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`
  - Add `JWT_REFRESH_TOKEN_EXPIRE_DAYS=30`
  - Add `JWT_ISSUER=pheidipp-test`

## 2. Add auth fixtures to conftest.py

- Objective: Provide reusable fixtures that register an athlete and return auth headers.
- File: `tests/conftest.py` [MODIFY]
- Actions:
  - Add `registered_athlete` fixture:
    - Async function registering via `POST /auth/register` with email and password.
    - Returns a dict: `{"athlete_id": UUID, "access_token": str, "refresh_token": str, "headers": {"Authorization": "Bearer <token>"}}`.
    - Uses `client` fixture.
    - Password must be ≥12 chars per `RegisterRequest` schema.
  - Add `auth_headers` fixture:
    - Depends on `registered_athlete`.
    - Returns `{"Authorization": f"Bearer {registered_athlete['access_token']}"}`.
  - Keep the existing `test_athlete` fixture (some tests use it for direct DB access), but note it's deprecated for API-calling tests.

## 3. Fix `test_athletes_api.py`

- Objective: Replace `POST /athletes/` with `POST /auth/register`; add auth headers to all requests.
- File: `tests/integration/test_athletes_api.py` [MODIFY]
- Actions:
  - Import `registered_athlete` fixture usage.
  - `TestCreateAthleteEndpoint`: Rewrite to test `POST /auth/register`:
    - `test_register_athlete_endpoint`: Register via `/auth/register`, assert 201, assert `TokenResponse` shape.
    - `test_register_athlete_duplicate_email`: Register same email twice, assert 409.
    - `test_register_athlete_invalid_email`: Send invalid email, assert 422.
    - `test_register_athlete_short_password`: Password less than 12 chars, assert 422.
  - `TestGetAthleteEndpoint`, `TestUpdateAthleteEndpoint`, etc.: Use `registered_athlete` fixture, pass `**headers` on all requests.
  - Remove all `POST /athletes/` calls that created athletes; replace with the registered athlete fixture.
  - All PATCH, PUT, GET, DELETE requests on `/athletes/{athlete_id}` routes must include `headers=registered_athlete["headers"]`.

## 4. Fix `test_wellness_api.py`

- Objective: Register athlete via auth API instead of direct DB creation; add auth headers.
- File: `tests/integration/test_wellness_api.py` [MODIFY]
- Actions:
  - Remove `athlete_in_db` fixture that uses `AthleteRepository`.
  - Add `registered_athlete` fixture.
  - All `POST /wellness/`, `GET /wellness/{id}`, `PATCH /wellness/{id}`, `DELETE /wellness/{id}`, and `GET /athletes/{id}/wellness` calls must include `headers=registered_athlete["headers"]`.
  - Use `registered_athlete["athlete_id"]` for athlete_id in payloads.

## 5. Fix `test_fitness_api.py`

- Objective: Same pattern as wellness.
- File: `tests/integration/test_fitness_api.py` [MODIFY]
- Actions:
  - Remove `athlete_in_db` fixture.
  - Use `registered_athlete` fixture for athlete_id and auth headers.
  - All fitness API calls include auth headers.
  - Remove `AthleteRepository` import if no longer needed.

## 6. Fix `test_activities_api.py`

- Objective: Same pattern.
- File: `tests/integration/test_activities_api.py` [MODIFY]
- Actions:
  - Remove `athlete_in_db` fixture.
  - Use `registered_athlete` fixture for athlete_id and auth headers.
  - All activity API calls include auth headers.
  - The `test_create_activity_endpoint_returns_created_activity` and similar tests must include headers.

## 7. Fix `test_athlete_preferences_api.py`

- Objective: Register athlete via auth API; add auth headers.
- File: `tests/integration/test_athlete_preferences_api.py` [MODIFY]
- Actions:
  - Use `registered_athlete` fixture instead of `make_athlete` factory.
  - Athlete preferences are created via factories (they need an athlete_id from the registered athlete).
  - All GET/PATCH on `/athlete-preferences/{id}` must include auth headers.

## 8. Fix `test_training_blocks_api.py`

- Objective: Same pattern.
- File: `tests/integration/test_training_blocks_api.py` [MODIFY]
- Actions:
  - Use `registered_athlete` fixture.
  - All GET/PATCH on `/training-blocks/{id}` must include auth headers.

## 9. Fix `test_twin_state_api.py`

- Objective: Replace `POST /athletes/` helper with `POST /auth/register`; add auth headers.
- File: `tests/integration/test_twin_state_api.py` [MODIFY]
- Actions:
  - `create_athlete_via_api`: Change to register via `POST /auth/register`, return `(athlete_id, token)`.
  - `create_profile_via_api`, `activate_athlete_via_api`, `complete_onboarding_via_api`: All take `headers` param and pass it.
  - All test calls pass `headers={"Authorization": "Bearer <token>"}` from the helper's returned token.

## 10. Fix `test_coach_messages_api.py`

- Objective: Register via auth API; add auth headers.
- File: `tests/integration/test_coach_messages_api.py` [MODIFY]
- Actions:
  - `create_athlete_and_onboard`: Change to register via `/auth/register`, return `(athlete_id, token)`.
  - All requests in tests include auth headers.

## 11. Fix `test_training_plans_api.py`

- Objective: Use `registered_athlete` fixture; add auth headers.
- File: `tests/integration/test_training_plans_api.py` [MODIFY]
- Actions:
  - Use `registered_athlete` fixture instead of `test_athlete`.
  - All requests on `/athletes/{id}/training-plans/*` include auth headers.

## 12. Fix `test_workflows.py`

- Objective: Replace `POST /athletes/` with `POST /auth/register`; add auth headers.
- File: `tests/integration/test_workflows.py` [MODIFY]
- Actions:
  - `test_athlete` fixture: Replace with `registered_athlete` pattern.
  - All API requests include auth headers.
  - `test_athlete_full_lifecycle_creates_all_related_resources`: Replace `POST /athletes/` at start with registration.
  - `test_onboarding_triggers_plan_generation`: Same.
  - `test_plan_retrieval_and_archival_workflow`: Same.

## 13. Fix `test_api_endpoints.py`

- Objective: Register athletes via auth API; add auth headers.
- File: `tests/integration/test_api_endpoints.py` [MODIFY]
- Actions:
  - Replace direct `Athlete(...)` instantiation with `registered_athlete` fixture.
  - All API requests include auth headers.

## 14. Fix `test_route_regression.py`

- Objective: Register athletes via auth API; add auth headers where needed.
- File: `tests/integration/test_route_regression.py` [MODIFY]
- Actions:
  - `athlete_in_db` fixture: Replace with `registered_athlete`.
  - Old route checks (404 tests) don't need auth headers (they're checking 404, not 401).
  - Canonical route tests and Phase 1 regression tests: Include auth headers.

## 15. Fix `test_tenant_isolation.py`

- Objective: Register athletes via auth API; add auth headers.
- File: `tests/integration/test_tenant_isolation.py` [MODIFY]
- Actions:
  - `athlete_a` and `athlete_b` fixtures: Replace with `registered_athlete_a` and `registered_athlete_b` fixtures (or register two athletes in the test body).
  - All API requests include auth headers for the appropriate athlete.

## 16. Fix `test_onboarding_first_message.py`

- Objective: Register athletes via auth API; add auth headers.
- File: `tests/integration/test_onboarding_first_message.py` [MODIFY]
- Actions:
  - Replace `make_athlete` with `registered_athlete` fixture.
  - All API requests include auth headers.

## 17. Fix `test_onboarding_plan_generation.py`

- Objective: Register athletes via auth API; add auth headers.
- File: `tests/integration/test_onboarding_plan_generation.py` [MODIFY]
- Actions:
  - Replace `test_athlete` fixture usage with `registered_athlete`.
  - All API requests include auth headers.
