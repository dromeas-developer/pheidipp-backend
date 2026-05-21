# DevOps Report — phase_1e_training_plan_generation
Date: 2026-05-20

## Result: FAIL

## Checks

| Check                        | Status  | Notes                              |
|------------------------------|---------|------------------------------------|
| Services healthy             | ✅ PASS | api, db, redis all healthy         |
| Migration generated          | ✅ PASS | Already existed: `8579bb2791bc_phase_1e_training_plan_generation.py` |
| Migration verified           | ✅ PASS | Creates `training_plans` and `planned_sessions` with correct columns, indexes, FKs |
| Test DB upgrade clean        | ✅ PASS | Clean upgrade, no errors           |
| Test suite                   | ❌ FAIL | 981 passed, 14 failed, 0 skipped   |
| No pending model changes     | ✅ PASS | `*_check.py` was empty (deleted)   |
| Prod DB upgrade clean        | ⏭️ SKIP | Skipped — test suite has failures  |
| Application build clean      | ⏭️ SKIP | Skipped — test suite has failures  |

## Test Suite Failures

**Total: 14 failed, 981 passed, 0 skipped**

### Feature-Related Failures (training plans / onboarding)

| # | Test | Error |
|---|------|-------|
| 1 | `test_completing_onboarding_adds_generate_training_plan_task` | `AttributeError: <module 'app.services.onboarding_service'> does not have the attribute 'BackgroundTasks'` — patch target incorrect |
| 2 | `test_onboarding_triggers_both_coach_message_and_plan_generation` | `422 != (200, 201)` — onboarding endpoint returns validation error |
| 3 | `test_onboarding_response_does_not_include_plan_data` | `422 != (200, 201)` — onboarding endpoint returns validation error |
| 4 | `test_get_active_returns_200_with_plan_when_active_plan_exists` | `404 != 200` — training plans active route returns not found |
| 5 | `test_get_active_response_includes_training_plan_and_sessions` | `404 != 200` — training plans active route returns not found |
| 6 | `test_get_by_id_returns_403_when_plan_belongs_to_different_athlete` | `404 != 403` — returns 404 instead of 403 for cross-athlete access |
| 7 | `test_get_by_id_returns_200_for_correct_athlete` | `404 != 200` — training plans by-id route returns not found |
| 8 | `test_get_by_id_returns_sessions_ordered_by_date` | `404 != 200` — training plans by-id route returns not found |
| 9 | `test_onboarding_triggers_plan_generation` | `422 != (200, 201)` — onboarding endpoint returns validation error |
| 10 | `test_plan_retrieval_and_archival_workflow` | `404 != 200` — training plans active route returns not found |
| 11 | `test_plan_generation_idempotency` | `422 != (200, 201)` — onboarding endpoint returns validation error |

### Pre-Existing Failures (not introduced by this feature)

| # | Test | Error |
|---|------|-------|
| 12 | `test_create_athlete_duplicate_email_returns_error` | `IntegrityError: duplicate key value violates unique constraint "ix_athletes_email"` — exception not caught/handled |
| 13 | `test_athlete_onboarding_transitions_to_active` | `422 != 201` — onboarding endpoint returns validation error |
| 14 | `test_athlete_b_cannot_see_athlete_a_physiology` | `200 != 201` — physiology create returns 200 instead of 201 |

## Failure Analysis

### Training Plans API — 404 on all routes (failures 4-8, 10)
All training plan endpoint tests return 404. This suggests either:
- The route is not being matched (URL pattern issue)
- The athlete lookup in the route dependency is failing
- The service method returns `None` and the route maps that to 404

### Onboarding — 422 validation errors (failures 2-3, 9, 11, 13)
Multiple onboarding tests return 422 Unprocessable Entity. This indicates the onboarding payload schema has changed or validation rules are stricter than the test payloads expect. This appears to be a pre-existing issue (failure 13 predates this feature).

### BackgroundTasks patch (failure 1)
Test patches `app.services.onboarding_service.BackgroundTasks` but the module does not import `BackgroundTasks` directly — it likely imports it from `fastapi` or uses it via a different path.

## Migration Details

**File:** `alembic/versions/8579bb2791bc_phase_1e_training_plan_generation.py`

- Creates `training_plans` table with columns: id, athlete_id, training_block_id, status, created_at, archived_at, generation_metadata, plan_rationale
- Creates `planned_sessions` table with columns: id, training_plan_id, scheduled_date, session_type, dominant_physiological_intent, target_duration_minutes, is_key_session, week_number, phase, generation_metadata, created_at
- All enums use `native_enum=False` (PostgreSQL TEXT columns)
- Partial index on `training_plans` for active plans per athlete
- Foreign keys with CASCADE/SET NULL as specified
- No hypertable required (not time-series data)

## Next Step
→ FAIL: send findings to p-coder with this report. Key issues to address:
1. Training plan routes returning 404 — investigate route registration and athlete lookup
2. Onboarding returning 422 — validate payload schema compatibility
3. BackgroundTasks patch target in test — fix import path
