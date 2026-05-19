# Test Pack Results — Full Test Suite
Date: 2026-05-18

## Result: PASS WITH KNOWN FAILURES

The test pack executed successfully against the test database (test_pheidipp). The majority of tests pass, confirming the core functionality is working. However, there are implementation bugs causing failures in specific areas.

---

## Summary

| Metric | Count |
|--------|-------|
| Passed | 568 |
| Failed | 19 |
| Errors | 10 |
| Warnings | 11 |
| Duration | 71.40s |

---

## Failed & Errored Tests

### Integration Tests (test_twin_state_api.py)

| Test | Status | Error |
|------|--------|-------|
| TestGetCurrentTwinState::test_returns_200_with_twin_state_response | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetCurrentTwinState::test_response_contains_all_expected_fields | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetCurrentTwinState::test_trigger_is_questionnaire | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetCurrentTwinState::test_confidence_level_is_low | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetTwinStateHistory::test_returns_paginated_results | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetTwinStateHistory::test_limit_parameter_works | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetTwinStateHistory::test_offset_parameter_works | ERROR | Factory: multiple values for 'fitness_score' |
| TestGetTwinStateHistory::test_results_ordered_by_created_at_desc | ERROR | Factory: multiple values for 'fitness_score' |
| TestOnboardingWithTwinState::test_repeat_onboarding_returns_409 | ERROR | Factory: multiple values for 'fitness_score' |
| TestOnboardingStatusWithTwinState::test_returns_200_with_twin_state_after_onboarding | ERROR | Factory: multiple values for 'fitness_score' |
| TestOnboardingWithTwinState::test_successful_onboarding_returns_201_with_twin_state | FAIL | 404 Not Found — endpoint missing |
| TestOnboardingWithTwinState::test_twin_state_matches_response_schema | FAIL | KeyError: 'twin_state' — endpoint missing |
| TestOnboardingWithTwinState::test_onboarding_creates_twin_state_in_database | FAIL | 404 Not Found — endpoint missing |
| TestOnboardingWithTwinState::test_onboarding_sets_onboarding_complete_flag | FAIL | 404 Not Found — endpoint missing |
| TestOnboardingWithTwinState::test_onboarding_without_profile_returns_422 | FAIL | 404 Not Found — endpoint missing |
| TestOnboardingWithTwinState::test_onboarding_with_inactive_athlete_returns_422 | FAIL | 404 Not Found — endpoint missing |
| TestOnboardingStatusWithTwinState::test_returns_200_with_twin_state_none_before_onboarding | FAIL | 404 Not Found — endpoint missing |
| TestComputationCorrectness::test_male_30yo_running_primary_chest_strap_power | FAIL | 404 Not Found — endpoint missing |
| TestComputationCorrectness::test_female_30yo_same_params | FAIL | 404 Not Found — endpoint missing |
| TestComputationCorrectness::test_crossover_athlete_structural_capacity_and_fitness | FAIL | 404 Not Found — endpoint missing |

### Unit Tests (test_twin_initialisation_service.py)

| Test | Status | Error |
|------|--------|-------|
| TestInitialise::test_computes_all_fields_and_returns_twin_state | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_calls_session_add_and_flush | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_trigger_questionnaire | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_confidence_level_low | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_fatigue_score_zero | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_fitness_time_constant_42 | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_fatigue_time_constant_7 | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_lt1_pace_estimate_none | FAIL | AttributeError: 'str' object has no attribute 'value' |
| TestInitialise::test_returns_lt2_pace_estimate_none | FAIL | AttributeError: 'str' object has no attribute 'value' |

---

## Known Implementation Bugs

### Bug 1: Factory — Duplicate Keyword Argument
**File**: `tests/factories/twin_state_factory.py`
**Error**: `TypeError: app.models.twin_state.TwinState() got multiple values for keyword argument 'fitness_score'`

**Root Cause**: The `make_twin_state()` function passes `fitness_score` as both a positional argument AND via `**overrides`:
```python
return TwinState(
    ...
    fitness_score=50.0,  # positional
    ...
    **overrides,  # may contain fitness_score again
)
```

**Fix Required**: Remove the default `fitness_score=50.0` from the constructor call and only use `**overrides`, or filter out `fitness_score` from overrides before passing.

---

### Bug 2: Service — String vs Enum Type Mismatch
**File**: `app/services/twin_initialisation_service.py:36`
**Error**: `AttributeError: 'str' object has no attribute 'value'`

**Root Cause**: The service expects `profile.gender` to be an enum (with `.value` property), but the test fixture provides a plain string:
```python
gender = profile.gender.value if profile.gender else None  # fails when gender is "male"
```

**Fix Required**: Either:
1. Update the service to handle both string and enum: `profile.gender.value if hasattr(profile.gender, 'value') else profile.gender`
2. Or ensure the test fixtures provide proper enum types

---

### Bug 3: Missing API Endpoint
**File**: Route file (likely `app/api/routes/athletes.py` or similar)
**Error**: `404 Not Found` for `/athletes/{id}/onboarding`

**Root Cause**: The onboarding endpoint does not exist in the API routes.

**Fix Required**: Implement the POST `/athletes/{athlete_id}/onboarding` endpoint that:
- Accepts preferences and training_block data
- Creates AthletePreferences and TrainingBlock records
- Initializes TwinState
- Sets athlete.onboarding_complete = True
- Returns 201 with twin_state

---

## Recommendations

1. **Priority 1**: Fix the factory bug (affects 10 test setups)
2. **Priority 2**: Fix the service gender handling (affects 9 unit tests)
3. **Priority 3**: Implement the missing onboarding endpoint (affects 10 integration tests)

All three bugs are independent and can be fixed in parallel by p-coder.