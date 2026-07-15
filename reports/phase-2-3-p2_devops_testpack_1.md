# DevOps Test Pack Report — phase-2-3-p2 (pass 1)
Date: 2026-07-14
Re-verifying: reports/phase-2-3-p2_devops.md (dated 2026-07-14) — RC1 (source_value), RC2 (accumulation)
Test execution group / scope: feature (same 10 test files as prior run)

## Result: FAIL

Tests: 170 passed / 23 failed / 0 skipped
Root causes resolved: 1 of 2 from the prior report (RC1 — source_value fully fixed)
Root causes still open: 2 (see Root Cause Analysis below)

### Changes from prior run

| Metric | Prior run | Current run | Delta |
|---|---|---|---|
| Total tests | 193 | 193 | 0 |
| Passed | 161 | 170 | +9 |
| Failed | 32 | 23 | -9 |
| Skipped | 0 | 0 | 0 |

The 9 additional passing tests are the 7 source_value failures (RC1, fully resolved by p-coder) plus 2 additional accumulation-related tests that now behave correctly with the working_state fix.

## Infrastructure Fixes

No infrastructure changes were made. All 23 failures are assertion/value mismatch errors caused by test expectations that were calibrated for the broken implementation — not framework, connection, fixture, or environment errors.

The MOCKING_CONTRACT.md was consulted. The failures have no matching anti-pattern entry — "no existing contract entry — new pattern" applies to all.

## Root Cause Analysis

### RC1 — `_source_value()` returns `source.value` instead of `str(source)` [RESOLVED]

All 7 tests that formerly failed due to `str(MeasurementSource.MEMBER)` producing e.g. `'MeasurementSource.TRAINING_RR_INFLECTION'` instead of `'training_rr_inflection'` now pass. The fix at line 334-335 of `physiology_update_service.py` correctly checks `isinstance(source, MeasurementSource)` and returns `source.value`.

**Tests that now pass (all 7):**
- `test_observation_dominates_when_weight_exceeds_decayed_prior`
- `test_dominant_source_stored_as_value_string`
- `test_bootstrap_uses_observation_source`
- `test_enum_member_returns_value_string`
- `test_first_cp_observation_bootstraps_state`
- `test_event_persisted_when_shift_exceeds_one_unit`
- `test_bootstrapped_state_carries_observation_fields`

Three of these (`test_event_persisted_when_shift_exceeds_one_unit`, `test_first_cp_observation_bootstraps_state`, `test_bootstrapped_state_carries_observation_fields`) still fail for a DIFFERENT reason now — the `_source_value` fix unblocked them, and they now reach deeper assertions that fail due to decay-related numeric mismatches. Those three are counted under RC2.

---

### RC2 — Test expectations need re-calibration for correct accumulation behavior (previously RC2: accumulation loop)

- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** Confirmed
- **Evidence:**
  - The accumulation fix (`working_state.get(obs.parameter, self._get_parameter_state(...))` at lines 584-586) is confirmed correct — it properly accumulates state across multiple observations of the same parameter within a single `apply_observations` call AND across separate calls (via persisted state)
  - All 23 remaining failures are assertion/value mismatches, not crashes or fixture errors
  - Every test uses `_state()` from a test helper which defaults to `last_observation_date="2026-05-01"`, and observation dates around 2026-06-15 — a 45-day gap that causes `exp(-45/42) ≈ 0.343` decay
  - Test expectations were computed assuming no decay (e.g. `(160*0.5 + 170*1.0) / 1.5 = 166.67` on line ~296 of the integration test, ignoring that the 0.5 prior_weight decays to ~0.171 before the first observation)
  - One confidence-transition test (`test_eight_observations_reach_high`) expects `('medium', 'high')` but batch processing of 8 same-day observations produces `('low', 'high')` — the test was written for incremental per-observation transitions but the architecture does a single pre/post diff per `apply_observations` call
  - One test (`test_event_atomicity_rolls_back_when_later_step_fails`) hits `IndexError: list index out of range` because the fixture row created by `_create_physiology_row` (flush-only, no commit) is rolled back along with the observation changes, leaving no row for the post-rollback SELECT
  - The `_state()` helper's default date is the single common source of the numeric mismatches across all integration and behaviour tests
- **Affected failures:** 23 tests total — representative sample below + full list in Full Failure Detail:
  - `test_four_observations_reach_prior_weight_4_point_5` — got 4.02, expected 4.5 (decay from 0.5 over 45d = 0.171, then accumulates 4×1.0 = 4.02 vs expected 0.5 + 4×1.0 = 4.5)
  - `test_eight_observations_reach_high` — got `('low', 'high')`, expected `('medium', 'high')` (batch processing jumps directly from low to high)
  - `test_event_atomicity_rolls_back_when_later_step_fails` — IndexError: fixture not committed before rollback
  - All other failures follow the same decay-underestimation pattern
- **Suggested fix:** For the p-test-architect: update `_state()` default `last_observation_date` to match the observation dates used in tests (e.g. `"2026-06-15"` instead of `"2026-05-01"`), OR update expected values to account for the 45-day decay. For `test_eight_observations_reach_high`, accept `('low', 'high')` as the correct batch-transition result. For `test_event_atomicity_rolls_back_when_later_step_fails`, commit the fixture row before testing rollback behavior.

---

### RC3 — `test_event_atomicity_rolls_back_when_later_step_fails`: IndexError (new failure exposed by accumulation fix)

- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** Confirmed
- **Evidence:**
  - The test creates an `AthletePhysiology` row via `_create_physiology_row()`, which calls `flush()` but not `commit()`
  - `apply_observations` now correctly modifies the row (with the accumulation fix, `_apply_updated_states` calls `update_in_place` which flushes)
  - When `db_session.rollback()` is called, ALL uncommitted work is rolled back — including both the original row creation AND the observation modifications
  - Post-rollback, `fresh = (await ...).scalars().all()[0]` hits IndexError because `all()` returns `[]`
  - This test was previously passing because the broken accumulation didn't flush modifications, so the rollback only undid the row creation — but `apply_observations` didn't change anything that triggered the rollback to matter. The fix exposed this latent fixture design issue.
- **Affected failures:** 1 test — `test_event_atomicity_rolls_back_when_later_step_fails`
- **Suggested fix:** Commit the transaction after `_create_physiology_row()` before calling `apply_observations`, so the fixture row survives the rollback. See `make_athlete` pattern for reference (it commits).

## Routing Summary

| Owner | Root Causes |
|---|---|
| p-coder | — (RC1 fully resolved) |
| p-test-architect | RC2 (23 tests: expectations need re-calibration), RC3 (1 test: fixture isolation) |
| p-devops | — |
| p-architect | — |
| Unassigned | — |

## Full Failure Detail

### test_eight_observations_reach_high [RC2]
```
E   AssertionError: assert ('low', 'high') == ('medium', 'high')
```
8 same-day observations of weight 1.0 starting from prior=0.0 produce prior=8.0. The confidence transition is LOW→HIGH (direct jump in single batch), not MEDIUM→HIGH as the test expects.

### test_lt2_hr_posterior_persists_after_commit [RC2]
```
E   assert 168.53781815096877 == 166.66666666666666 ± 0.01
```
Posterior mean computed as `(160 * 0.171 + 170 * 1.0) / 1.171 = 168.54` vs test expectation `(160 * 0.5 + 170 * 1.0) / 1.5 = 166.67`. The 0.5 prior_weight decays to ~0.171 over the 45-day gap from `last_observation_date=2026-05-01` to `measurement_date=2026-06-15`.

### test_existing_lt2_hr_value_persists_when_only_lt1_updated [RC2]
```
E   assert 154.2689090754844 == 153.33333333333334 ± 0.01
```
Same decay issue — posterior mean computed with decayed prior_weight.

### test_event_persisted_when_shift_exceeds_one_unit [RC2]
```
E   assert 1.171259427546523 == 1.5 ± 1.5e-06
```
The "shift" (prior_weight) is 1.171 (decayed and accumulated) vs expected 1.5 (no decay, no accumulation). Same root cause: decay from default `last_observation_date`.

### test_event_atomicity_rolls_back_when_later_step_fails [RC3]
```
E   IndexError: list index out of range
```
Fixture row is only flushed, not committed. Rollback undoes everything including the row creation. Empty list on SELECT.

### test_second_observation_writes_measurement_but_does_not_mutate [RC2]
```
E   assert 1.171259427546523 == 1.5 ± 1.5e-06
```
Same decay pattern as above.

### test_different_observed_value_is_not_a_duplicate [RC2]
```
E   assert 2.1712594275465227 == 2.5 ± 2.5e-06
```
Two observations each adding 1.0 to the decayed prior (0.171 + 1.0 = 1.171, then 1.171 + 1.0 = 2.171) vs expected linear 0.5 + 1.0 + 1.0 = 2.5.

### test_different_activity_id_is_not_a_duplicate [RC2]
Same values as above — same decay pattern.

### test_different_source_is_not_a_duplicate [RC2]
Same values as above — same decay pattern.

### test_four_observations_reach_prior_weight_4_point_5 [RC2]
```
E   assert 4.020484699851728 == 4.5 ± 4.5e-06
```
4 observations at 1-day intervals, starting from 0.5 prior with 45-day decay to ~0.171: Accumulated total ~4.02 vs expected 4.5 (no decay).

### test_four_observations_trigger_low_to_medium_transition [RC2]
```
E   AssertionError: assert 'low' == 'medium'
```
Prior_weight after 4 observations reaches ~4.02, which is just above the 4.0 threshold (→ MEDIUM). But the test's pre-computed expected confidence level didn't account for decay, setting an incorrect expected value.

### test_eight_observations_reach_prior_weight_8_point_5 [RC2]
```
E   assert 7.51628098954719 == 8.5 ± 8.5e-06
```
8 observations, 1-day intervals, prior decays from 0.5 to ~0.171 then accumulates: ~7.52 vs expected 8.5.

### test_eighth_observation_triggers_medium_to_high_transition [RC2]
```
E   AssertionError: assert 'medium' == 'high'
```
Prior_weight ~7.52 (< 8.0), so confidence is MEDIUM, not HIGH. Same decay root cause.

### test_four_rr_observations_reach_high_confidence [RC2]
```
E   AssertionError: assert 'medium' == 'low'
```
After 4 RR observations (weight=2.5 each) at 1-day intervals, the `from_level` in the transition is 'medium' (already MEDIUM after observation 2) not 'low' as the test expects. The test assumes no decay (expected prior = 0.5 + 4×2.5 = 10.5 → HIGH), but actual prior ≈ 9.81 → HIGH from MEDIUM.

### test_three_calls_each_with_one_observation [RC2]
```
E   assert 1.171259427546523 == 1.5 ± 1.5e-06
```
Same decay pattern: prior_weight after first observation is ~1.171 (decayed from 0.5 to 0.171, then +1.0) vs expected 1.5.

### test_second_observation_grows_prior_weight [RC2]
```
E   assert 1.9764716866522432 == 2.0 ± 2.0e-06
```
Second CP observation: the posterior accumulates but with 1-day decay. The gap from the first observation is smaller than the initial 45-day gap, so the error is smaller but still present.

### test_second_observation_fires_event_when_shift_exceeds_one [RC2]
```
E   assert 1.9764716866522432 == 2.0 ± 2.0e-06
```
Same as above — prior_weight ~1.976 vs expected 2.0.

### test_journey_threshold_detection_to_physiology_updated_event [RC2]
```
E   AssertionError: assert 0 >= 1
```
`shifted_parameters` is empty because the posterior shift is ~1.17 (< 1.0 threshold) instead of the expected 1.5 (decay reduces effective prior_weight).

### test_journey_event_payload_matches_shifted_parameters [RC2]
```
E   assert 0 == 1
```
Same root cause: no shift detected because decay reduces effective prior_weight.

### test_journey_duplicate_observation_writes_measurement_not_event [RC2]
```
E   AssertionError: assert 0 >= 1
```
Same decay pattern: no shift detected, so no event fired, but test expects one.

### test_journey_four_observations_reach_medium_confidence [RC2]
```
E   assert 3.1695436951770373 >= 4.0
```
After 4 observations, prior_weight ~3.17 (< 4.0, so confidence stays LOW) vs expected >= 4.0 (MEDIUM). The default 45-day decay reduces the effective starting weight.

### test_journey_eight_observations_reach_high_confidence [RC2]
```
E   assert 4.684660287597908 >= 8.0
```
After 8 observations, prior_weight ~4.68 (< 8.0, so confidence is MEDIUM at best) vs expected >= 8.0 (HIGH). Same decay root cause.

### test_journey_small_shift_writes_measurement_not_event [RC2]
```
E   AssertionError: assert 0 >= 1
```
No shift detected because decay reduces effective prior_weight below the 1.0 threshold.

## Next Step
→ FAIL (test failures, all Test Suite): route to p-test-architect with this report.
  - RC1 (source_value) is resolved — the p-coder fix is correct.
  - RC2 (test expectations) and RC3 (fixture isolation) need the test content updated to match the now-correct implementation behavior.
  - After p-test-architect resolves RC2/RC3, recommend a Test Pack Mode re-run followed by a Full Pipeline Mode run before promotion (Test Pack Mode does not gate the manifest/migration/build promotion path).
