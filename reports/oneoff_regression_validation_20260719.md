# DevOps Report — oneoff_regression_validation (ad-hoc, rerun)
Date: 2026-07-19
Validator report: N/A (ad-hoc run)
Test execution group: regression

## Implementation State
base_commit: f7593c4
current_commit: ab20925
db_revision: 21f955c743cb

## Result: FAIL

Tests: 713 passed / 5 failed / 2 skipped
Root causes identified: 1 (after re-run — 2 infra issues were resolved by the fix)

## Checks

| Check | Status | Notes |
|---|---|---|
| Services healthy | ✅ | |
| Test DB upgrade clean | ✅ | |
| No pending model changes (test DB) | ✅ | |
| Test suite | ❌ | 713 passed, 5 failed, 2 skipped |

## Infrastructure Fixes (from prior run — already applied)

The `athlete_id=athlete_id` was removed from `RawSensorStream()` constructor in
the test file. This was already present in the test architect's fix batch.

## Changes since prior run

The test architect applied the following fixes to `test_twin_recalibration_calibration_user_journey.py`:

1. **`_build_hr_deflection_stream(hr_offset)`** — added `hr_offset` parameter so
   consecutive sessions can produce different HR observations, triggering
   posterior shifts > 1 bpm and registering as `shifted_parameters`.

2. **`_ensure_physiology_row`** — now normalises missing JSONB containers
   (`lt1`/`lt2`) when returning an existing row from onboarding.

3. **Warmup-session pattern** — `test_full_pipeline_writes_calibration_twin_state`,
   `test_confidence_is_monotonic`, and `test_twin_recalibrated_event_fires` now
   use a warmup session (bootstraps physiology, early-returns) followed by a
   second session with `hr_offset` (shifts posterior > 1, creates TwinState).

4. **Not updated:** `test_metric_confidence_lt2_hr_has_prior_weight_greater_than_zero`
   was NOT migrated to the warmup+offset pattern.

## Root Cause Analysis

### RC2 (updated) — Test setup missing TrainingGoal + AthleteFitness preconditions (5 failures)
- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** Confirmed
- **Evidence:**

  All 5 failures now occur because the pipeline reaches
  `TwinRecalibrationService.recalibrate_for_calibration()` (the warmup+offset
  strategy successfully produces `shifted_parameters > 1`), but the athlete
  has no active `TrainingGoal` and/or no `AthleteFitness` row:

  ```
  app/services/twin_recalibration_service.py:286
  MissingTrainingGoalError: no active training goal for athlete ...
  ```

  `recalibrate_for_calibration()` requires (lines 281-298 of
  `twin_recalibration_service.py`):
  - An active `TrainingGoal` — raises `MissingTrainingGoalError`
  - An `AthleteFitness` row — raises `MissingAthleteFitnessError`

  The reference setup at `tests/integration/test_threshold_detection_task_integration.py:189-211`
  shows exactly what's needed: a `TrainingGoal` row with `status=ACTIVE`
  and an `AthleteFitness` row with `fitness=0.0`, `fatigue=0.0`.

  Additionally, `test_metric_confidence_lt2_hr_has_prior_weight_greater_than_zero`
  (line 420) was not updated to the warmup+offset pattern and still tries to
  verify against a single session where `shifted_parameters` is empty (first
  observation bootstraps from null). The `_ensure_physiology_row` fix may not
  fully resolve the `lt2 is None` issue because the session rolls back when
  the pipeline's `recalibrate_for_calibration()` raises.

- **Files:**
  - app: none — production code is correct
  - test: `tests/behaviour/test_twin_recalibration_calibration_user_journey.py`
    — needs `TrainingGoal` + `AthleteFitness` setup and warmup pattern for
    the remaining test

- **Affected failures:** 5 tests
  1. `test_full_pipeline_writes_calibration_twin_state` — MissingTrainingGoalError
  2. `test_metric_confidence_lt2_hr_has_prior_weight_greater_than_zero` — AttributeError (lt2 is None, not migrated to warmup)
  3. `test_metric_confidence_transitions_to_medium` — MissingTrainingGoalError
  4. `test_confidence_level_never_decreases` — MissingTrainingGoalError
  5. `test_twin_recalibrated_event_fires` — MissingTrainingGoalError

- **Suggested fix:**
  - Add a helper (e.g. `_create_onboarding_context`) that creates both
    `TrainingGoal` and `AthleteFitness` for the athlete, similar to
    `tests/integration/test_threshold_detection_task_integration.py:189-211`
    but in the behaviour test's helper pattern.
  - Call it in every test before running `_run_full_pipeline`.
  - Migrate `test_metric_confidence_lt2_hr_has_prior_weight_greater_than_zero`
    to the warmup+offset pattern used by the other tests in the same class.

## Routing Summary

| Owner | Root Causes | Failures |
|---|---|---|
| p-coder | — | — |
| p-test-architect | RC2 (updated) | 5 |
| p-devops | — | — |
| p-implementation-architect | — | — |
| Unassigned | — | — |

## Full Failure Detail

### RC2 — Missing TrainingGoal/AthleteFitness preconditions (5 failures)

```
FAILED test_full_pipeline_writes_calibration_twin_state
  File "app/services/twin_recalibration_service.py", line 286,
  in recalibrate_for_calibration
    raise MissingTrainingGoalError(...)
  Pipeline reached recalibrate_for_calibration (warmup created shifted_parameters)
  but athlete has no active TrainingGoal.

FAILED test_metric_confidence_lt2_hr_has_prior_weight_greater_than_zero
  AttributeError: 'NoneType' object has no attribute 'get' at line 452
  physio_before.lt2 is None. Test wasn't migrated to warmup pattern.

FAILED test_metric_confidence_transitions_to_medium
  File "app/services/twin_recalibration_service.py", line 286,
  in recalibrate_for_calibration
    raise MissingTrainingGoalError(...)

FAILED test_confidence_level_never_decreases
  File "app/services/twin_recalibration_service.py", line 286,
  in recalibrate_for_calibration
    raise MissingTrainingGoalError(...)

FAILED test_twin_recalibrated_event_fires
  File "app/services/twin_recalibration_service.py", line 286,
  in recalibrate_for_calibration
    raise MissingTrainingGoalError(...)
```

## Next Step
→ FAIL: 5 failures still open, all in the same test file. The pipeline fix
  (warmup+hr_offset) correctly unlocks `shifted_parameters` and the target
  `recalibrate_for_calibration()` call, but the tests lack the precondition
  setup (TrainingGoal + AthleteFitness) that `recalibrate_for_calibration()`
  requires. Route to p-test-architect for the remaining setup wiring.
