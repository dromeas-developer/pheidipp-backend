# Test Pack — Phase-1.3-P1 Onboarding & Twin Bootstrap

**Plan:** `docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md`  
**Generated:** 2026-06-27  
**Test Architect:** p-test-architect  
**DevOps Report:** `reports/phase-1-3-p1_devops.md`  
**Result:** PASS (168 tests)

---

## Executive Summary

This test pack delivers complete coverage for the onboarding flow and twin bootstrap functionality. All 168 tests pass, covering:

- **37 unit tests** for `OnboardingService` helper functions and domain logic
- **29 unit tests** for onboarding error mappings
- **32 integration tests** for service-layer repository interactions
- **64 API tests** for the eight onboarding endpoints
- **6 end-to-end behaviour tests** for the complete onboarding user journey

One test assertion was updated during generation: `test_last_observation_date_is_the_supplied_datetime` now expects ISO string format (required for JSONB serialization) instead of raw datetime object. This aligns with the implementation fix in `_bootstrap_signal` that calls `.isoformat()` on the observation date.

---

## Test Files Generated

| File | Type | Count | Purpose |
|---|---|---|---|
| `tests/unit/test_onboarding_service.py` | Unit | 37 | Bootstrap helpers, service logic, error mapping |
| `tests/unit/test_onboarding_errors.py` | Unit | 29 | Domain error → HTTP status mappings |
| `tests/integration/test_onboarding_service.py` | Integration | 32 | Repository interactions, atomic transaction, event persistence |
| `tests/api/test_onboarding_endpoints.py` | API | 64 | HTTP endpoint behaviour, auth, input validation |
| `tests/behaviour/test_onboarding_user_journey.py` | Behaviour | 6 | End-to-end onboarding flow |

---

## Coverage Summary

### Routes Covered (8/8 — 100%)

- `POST /api/v1/athletes/{athlete_id}/onboarding` — atomic seven-entity bootstrap
- `GET /api/v1/athletes/{athlete_id}/onboarding` — status check
- `GET /api/v1/athletes/{athlete_id}/profile` — profile read
- `PATCH /api/v1/athletes/{athlete_id}/profile` — mutable field updates only
- `GET /api/v1/athletes/{athlete_id}/preferences` — preferences read (404 before onboarding)
- `PATCH /api/v1/athletes/{athlete_id}/preferences` — day-level weekly_schedule merge
- `GET /api/v1/athletes/{athlete_id}/twin` — latest TwinState snapshot
- `GET /api/v1/athletes/{athlete_id}/twin/history` — ordered history with limit

### Events Covered (1/1 — 100%)

- `onboarding_completed` — persisted via transactional outbox with correct payload shape

### Invariants Covered (26/26 — 100%)

- Atomic onboarding transaction (all-or-nothing semantics)
- Re-onboarding blocked (409 when `onboarding_complete=true`)
- Single active TrainingGoal per athlete (partial unique index)
- Goal-type whitelist (race_event | target_performance only)
- Timezone IANA validation
- TwinState append-only (no update/delete methods)
- Threshold bootstrap formulas (max_hr, lt1, lt2)
- cp/vo2max/power/pace NULL at bootstrap
- AthleteFitness zero-initialization with population time constants
- TwinState confidence_level=low, trigger=questionnaire
- structural_risk_flag computed server-side
- Data tier inference wiring
- onboarding_completed event payload shape
- ADR-006 explicit rollback on caught IntegrityError
- require_self returns 403 (never 404) on athlete mismatch
- PATCH immutability guards (date_of_birth, sex, timezone rejected)
- PATCH weekly_schedule day-level merge
- Idempotent PATCH operations
- GET returns 404 before onboarding, 200 after
- History limit bounds (ge=1, le=100)

---

## Key Test Scenarios

### Atomic Success (`test_complete_onboarding_atomic_success`)

Verifies that a complete onboarding request with `race_event` goal creates exactly:
- 1 × `TrainingGoal` (status = `active`)
- 1 × `AthletePhysiology` (bootstrap posterior states)
- 1 × `AthleteFitness` (zero fitness/fatigue/form)
- 1 × `TwinState` (confidence_level=low, trigger=questionnaire)
- 1 × `AthletePreferences` (full field set)
- 1 × `AthleteProfile` update (timezone, structural_risk_flag)
- `athlete.onboarding_complete = true`
- 1 × `SystemEvent` (onboarding_completed)
- 1 × `SystemEventOutbox` (status = `pending`)

All within a single committed transaction.

### Mid-Transaction Rollback (`test_complete_onboarding_rolls_back_on_failure`)

Forces a failure at the `AthleteFitness` creation step and asserts:
- No `AthletePreferences` row exists
- No `TrainingGoal` row exists
- No `AthletePhysiology` row exists
- No `AthleteFitness` row exists
- No `TwinState` row exists
- `onboarding_complete` remains `false`
- No `onboarding_completed` event row exists

### Idempotency Guard (`test_onboarding_rejected_when_already_complete`)

Calls `POST /onboarding` a second time and asserts:
- HTTP 409 returned
- No new rows written
- No new outbox row added

### TwinState Bootstrap Correctness (`test_twin_state_bootstrap_values`)

After onboarding, `GET /twin` returns:
- `confidence_level = "low"`
- `trigger = "questionnaire"`
- `fitness = 0.0`, `fatigue = 0.0`, `form = 0.0`
- `lt1_hr_bpm` and `lt2_hr_bpm` derived from DOB via `220-age` formula
- `readiness_level = "green"`
- `data_tier` matches `infer_data_tier(hr_source, power_source)`
- `activity_id = null`
- `metric_confidence = {lt1_hr: "low", lt2_hr: "low", others: null}`

### Goal-Type Restriction (`test_invalid_goal_type_rejected_422`)

Submits `goal_type = "fitness_improvement"` and asserts:
- HTTP 422 returned
- `InvalidGoalTypeError` raised at service layer

### Profile PATCH Immutability (`test_patch_profile_rejects_immutable_fields`)

PATCHes `date_of_birth` and asserts:
- HTTP 422 returned
- Stored `date_of_birth` unchanged
- `updated_at` unchanged

### Preferences PATCH Merge (`test_patch_preferences_merges_weekly_schedule`)

PATCHes `{weekly_schedule: {saturday: {available: false}}}` and asserts:
- Only Saturday's `available` flag changes
- Other days preserved
- HTTP 200 returned

---

## Infrastructure Notes

No infrastructure fixes were required during this generation cycle. The test suite runs cleanly with the existing:

- `tests/conftest.py` fixtures
- `tests/payloads.py` helpers
- `pytest.ini` configuration
- `tests/*/__init__.py` module initializers

---

## Known Gaps

None. All routes, events, and invariants from the implementation plan are fully covered.

---

## Promotion Recommendation

**All tests are promoted to `regression` and `release` groups.**

The test suite exercises:
- Pure function unit tests (smoke group)
- Service-layer integration tests (feature group)
- HTTP endpoint tests (feature group)
- End-to-end user journey tests (feature group)

All 168 tests pass with no infrastructure issues, no assertion failures, and no skipped tests. The implementation is stable and ready for regression protection.

---

## Next Steps

1. DevOps will execute the `feature` selection group for ongoing development
2. DevOps will execute the `regression` selection group on each commit
3. Test Architect will review the next DevOps report and update `validation.passed` fields in the sub-phase manifest
4. Test Architect will maintain the `index.yaml` cross-phase coverage summary as subsequent sub-phases are delivered

---

## Manifest Updates

**Created:** `tests/test-manifest/phase-1-3-p1.yaml` — full feature definitions, test references, coverage, and history for this sub-phase.

**Updated:** `tests/test-manifest/index.yaml`:
- Added Phase-1.3 unit tests to `smoke` group
- Updated `feature` group to Phase-1.3 tests only (current active sub-phase)
- Added all Phase-1.3 tests to `regression` and `release` groups
- Updated `coverage.routes` with 8 new onboarding endpoints
- Updated `coverage.events` to mark `onboarding_completed` as covered
- Updated `coverage.invariants` with 26 new invariant assertions
- Updated `last_reviewed_at` to `2026-06-27T00:00:00+00:00`

**Fixed:** `tests/unit/test_onboarding_service.py::TestBootstrapSignal::test_last_observation_date_is_the_supplied_datetime` — assertion updated to expect ISO string format.

---

## Test Author Notes

### Bootstrap Signal ISO Format

The `_bootstrap_signal` helper returns `last_observation_date` as an ISO-format string (via `.isoformat()`). This is required because the value is stored inside a JSONB column (`AthletePhysiology.lt1`, `lt2`, `max_hr`), and SQLAlchemy's default JSON serializer cannot handle raw `datetime` objects.

The test assertion was updated to:
```python
assert sig["last_observation_date"] == observation.isoformat()
```

This matches the implementation contract and prevents `TypeError: Object of type datetime is not JSON serializable` during persistence.

### Transactional Outbox Verification

The integration tests verify both the `SystemEvent` and `SystemEventOutbox` rows are created in the same transaction as the domain state. This is critical for the ADR-004 event sourcing pattern — consumers must never observe state changes without the corresponding event.

### Append-Only TwinState

The `TwinStateRepository` intentionally exposes no `update()` or `delete()` methods. The integration tests verify this by asserting that only `insert`, `get_latest`, and `get_history` are available on the repository interface.

---

**End of Test Pack**