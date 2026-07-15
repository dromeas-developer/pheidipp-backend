# DevOps Test Pack Report — phase-2-3-p2 (pass 2)
Date: 2026-07-14
Re-verifying: reports/phase-2-3-p2_devops.md (dated 2026-07-14) — RC1 (source_value), RC2 (accumulation / test expectations), RC3 (fixture isolation)
Test execution group / scope: feature (same 10 test files as prior runs)

## Result: FAIL

Tests: 185 passed / 8 failed / 0 skipped
Root causes resolved: 1 of 3 from the prior report (RC1 — source_value resolved in pass 1, confirmed still resolved)
Root causes still open: 2 (see Root Cause Analysis below)

### Changes from prior test-pack run (pass 1)

| Metric | Pass 1 | Pass 2 | Delta |
|---|---|---|---|
| Total tests | 193 | 193 | 0 |
| Passed | 170 | 185 | +15 |
| Failed | 23 | 8 | -15 |
| Skipped | 0 | 0 | 0 |

### What p-test-architect fixed (15 additional tests now passing)

The `_state()` helper's default `last_observation_date` was changed from `"2026-05-01"` to `"2026-06-15"` in all integration test files, matching the default `measurement_date=date(2026, 6, 15)` of the `_observation()` helper. This eliminated the 45-day decay gap that was causing test expectations to be off, fixing tests that used `_state()` without an explicit `last_observation_date`.

Specifically, these 15 tests now pass that were failing in pass 1:
- All 3 behaviour journey tests (threshold detection, duplicate observation, confidence transitions, first observation, small shift)
- `test_different_observed_value_is_not_a_duplicate`, `test_different_activity_id_is_not_a_duplicate`, `test_different_source_is_not_a_duplicate`
- `test_four_observations_trigger_low_to_medium_transition`
- `test_two_rr_observations_reach_medium_confidence`
- `test_lt2_hr_posterior_persists_after_commit`, `test_existing_lt2_hr_value_persists_when_only_lt1_updated`
- `test_journey_*` journey tests (all of them)

## Infrastructure Fixes

No infrastructure changes were made. All 8 failures are test content issues (assertion mismatches or post-rollback ORM access pattern), not framework, connection, fixture, or environment errors.

The MOCKING_CONTRACT.md was consulted. The `expire_all()` + async lazy load anti-pattern (entry dated 2026-07-11) partially describes the MissingGreenlet in RC3 — after `rollback()`, accessing `fresh.lt2` on a newly-loaded ORM instance triggers lazy loading outside the greenlet context. The remaining 7 failures have no matching anti-pattern entry — "no existing contract entry — new pattern" applies; the common root cause is test expectations calibrated for linear accumulation instead of decaying accumulation.

## Root Cause Analysis

### RC1 — `_source_value()` returns `source.value` instead of `str(source)` [RESOLVED]

All 7 tests that formerly failed due to `str(MeasurementSource.MEMBER)` — confirmed still resolved. No new source_value failures appeared. There are 0 remaining failures in RC1's original member set.

---

### RC2 — Test expectations need re-calibration for 1-day inter-observation decay (7 tests, reduced from 23 in pass 1)

- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** Confirmed
- **Evidence:**
  - The `_state()` default `last_observation_date` was fixed from `"2026-05-01"` to `"2026-06-15"` (matching `_observation()`'s `measurement_date`), which resolved same-day decay issues. However, 7 tests that add observations at 1-day intervals (`measurement_date=date(2026, 6, 15 + i)`) still assert values assuming no decay between consecutive days.
  - Every `apply_observations` call for a new observation at date `D+1` correctly decays the prior via `exp(-1/42) ≈ 0.9765` before adding the observation weight. The test expectations assume linear accumulation: `prior + weight = expected`.
  - Specific numerical breakdown:

    | Test | Expected | Actual | Delta | Cause |
    |---|---|---|---|---|
    | `test_four_observations_reach_prior_weight_4_point_5` | 4.5 | 4.3265 | -0.1735 | 3× 1-day decays reduce 0.5→0.4883, 1.4883→1.4538, etc. |
    | `test_eight_observations_reach_prior_weight_8_point_5` | 8.5 | 7.7945 | -0.7055 | 7× 1-day decays compound |
    | `test_eighth_observation_triggers_medium_to_high_transition` | 'high' | 'medium' | threshold miss | prior_weight 7.79 < 8.0 threshold |
    | `test_four_rr_observations_reach_high_confidence` | `('low','high')` | `('medium','high')` | from_level wrong | 2nd RR obs reaches MEDIUM → 4th call `from_level='medium'` |
    | `test_three_calls_each_with_one_observation` | 2.5 (i=1) | 2.4647 | -0.0353 | 1-day decay on the second iteration |
    | `test_second_observation_grows_prior_weight` | 2.0 | 1.9765 | -0.0235 | 1-day decay: `cp prior=1.0`, decay to 0.9765, +1.0 = 1.9765 |
    | `test_second_observation_fires_event_when_shift_exceeds_one` | 2.0 | 1.9765 | -0.0235 | same decay pattern |

  - The 7 tests assert `pytest.approx(expected)` where `expected` = linear accumulation without any decay between the multi-day observation sequence.
  - The implementation's decay behavior is architecturally correct as confirmed by the passing unit tests (all `TestBayesianUpdatePriorDecay` tests pass).
- **Affected failures:** 7 tests total — see list in Full Failure Detail below.
- **Suggested fix for p-test-architect:** For each test, recalculate expected values using the actual decay formula. Two approaches:
  1. **Replace expected values** with correctly-decayed totals (e.g., `test_four_observations_reach_prior_weight_4_point_5`: change expected from 4.5 to `pytest.approx(4.3265, rel=1e-4)` or compute dynamically with `exp(-1/42)`).
  2. **Use same-day observations** (all `measurement_date=date(2026, 6, 15)`) so no decay occurs between observations, keeping expected = linear accumulation. For `test_second_observation_grows_prior_weight` the bootstrapped state already has `last_observation_date=2026-06-15`, so a same-day second observation would not be deduped because `observed_value` differs (250 vs 260).

---

### RC3 — `test_event_atomicity_rolls_back_when_later_step_fails`: MissingGreenlet after rollback (previously IndexError, re-emerged as new failure after incomplete fix)

- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** Confirmed
- **Evidence:**
  - The test was modified by p-test-architect (per pass 1's RC3 suggested fix) to commit the fixture row before calling `apply_observations` + `rollback`, which correctly resolved the IndexError (the fixture row now survives rollback).
  - However, the post-rollback assertion `fresh.lt2["hr"]["value"]` triggers SQLAlchemy lazy loading on the freshly-loaded `AthletePhysiology` ORM instance. After `rollback()`, the session's internal connection management enters a state where lazy attribute access attempts async IO outside the proper greenlet context, raising `MissingGreenlet`.
  - The fix for RC3 was incomplete — committing the fixture row solved the IndexError but introduced a MissingGreenlet at the next assertion.
  - This matches the known anti-pattern in MOCKING_CONTRACT.md (entry dated 2026-07-11): "Accessing an attribute of an in-memory instance AFTER `expire_all()` — triggers async lazy load outside the greenlet". However, in this case the instance was loaded AFTER the rollback but `rollback()` puts the session's connection lifecycle in a state that prevents subsequent lazy loads.
  - The `lt2` column is a standard non-deferred JSONB column on `AthletePhysiology`. The lazy load is triggered by SQLAlchemy's internal attribute-expiration mechanism, not by any deferred-column configuration.
- **Affected failures:** 1 test — `test_event_atomicity_rolls_back_when_later_step_fails`
- **Suggested fix for p-test-architect:** Avoid ORM attribute access after `rollback()` on the same session. Use one of these patterns:
  1. **Column-level SELECT** — read the JSONB value directly without loading an ORM instance:
     ```python
     fresh_lt2 = (await db_session.execute(
         select(AthletePhysiology.lt2).where(
             AthletePhysiology.athlete_id == athlete.id
         )
     )).scalar_one()
     assert fresh_lt2["hr"]["value"] == pytest.approx(160.0)
     ```
  2. **Separate session for post-rollback reads** — open a new session for the verification queries.
  3. **Capture values before rollback** — access `physiology.lt2` before the rollback and assert on the captured dict after rollback (the in-memory Python dict survives regardless of DB state).

## Routing Summary

| Owner | Root Causes |
|---|---|
| p-coder | — (RC1 fully resolved in pass 1) |
| p-test-architect | RC2 (7 tests: decay-calibrated expectations), RC3 (1 test: post-rollback ORM access) |
| p-devops | — |
| p-architect | — |
| Unassigned | — |

## Recommended Execution Order

1. **RC3 first** (1 test, `test_event_atomicity_rolls_back_when_later_step_fails`) — quick fix, high-confidence diagnosis, blocks no other tests. Use column-level SELECT or capture values before rollback.
2. **RC2** (7 tests, decay expectations) — requires per-test recalculation of expected values. The pattern is uniform (1-day inter-observation decay), so these can be fixed in one batch.

## Full Failure Detail

### TestPhysiologyUpdatedEvent::test_event_atomicity_rolls_back_when_later_step_fails [RC3]
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here.
```
Post-rollback access to `fresh.lt2["hr"]["value"]` triggers lazy load outside greenlet context. The traceback shows the ORM attempting `_load_expired` → `load_on_pk_identity` → `session.execute` → pool `_create_connection` → `asyncpg.connect` → `await_only()` fails because no greenlet_spawn context exists.

### TestLowToMediumTransition::test_four_observations_reach_prior_weight_4_point_5 [RC2]
```
E   assert 4.326562811041755 == 4.5 ± 4.5e-06
```
4 observations at 1-day intervals starting from prior=0.5 at 2026-06-15. Decay reduces each step: 0.5→1.5→2.4648→3.4073→4.3275 vs expected linear 0.5+4×1.0=4.5.

### TestMediumToHighTransition::test_eight_observations_reach_prior_weight_8_point_5 [RC2]
```
E   assert 7.794553876359138 == 8.5 ± 8.5e-06
```
8 observations at 1-day intervals. Compound decay over 7 days reduces total from expected 8.5 to actual 7.79.

### TestMediumToHighTransition::test_eighth_observation_triggers_medium_to_high_transition [RC2]
```
E   AssertionError: assert 'medium' == 'high'
```
Prior_weight ~7.79 < 8.0 threshold → confidence stays MEDIUM instead of HIGH.

### TestHighWeightSourceCrossesThresholdFaster::test_four_rr_observations_reach_high_confidence [RC2]
```
E   AssertionError: assert 'medium' == 'low'
```
After 2 RR observations (weight=2.5 each), prior_weight reaches ~5.44 (MEDIUM). The 4th observation's `from_level` is 'medium', not 'low' as the test expects.

### TestSubsequentCallsAccumulateAgainstPersistedState::test_three_calls_each_with_one_observation [RC2]
```
E   assert 2.464707529978365 == 2.5 ± 2.5e-06
```
Second observation (i=1) at 1-day gap: prior decays from 1.5 to 1.4648, +1.0 = 2.4648 vs expected 2.5.

### TestSecondCpObservation::test_second_observation_grows_prior_weight [RC2]
```
E   assert 1.9764716866522432 == 2.0 ± 2.0e-06
```
First CP observation at 2026-06-15 bootstraps prior_weight=1.0, second at 2026-06-16: 1.0×exp(-1/42) + 1.0 = 1.9765 vs expected 2.0.

### TestSecondCpObservation::test_second_observation_fires_event_when_shift_exceeds_one [RC2]
```
E   assert 1.9764716866522432 == 2.0 ± 2.0e-06
```
Same decay pattern as above — event payload `prior_weights["cp"]` is 1.9765 vs expected 2.0.

## Next Step
→ FAIL (test failures, all Test Suite): route to p-test-architect with this report.
  - RC1 (source_value) — resolved permanently.
  - RC2 (7 tests) — update expected values to account for 1-day inter-observation decay. All 7 share the identical root cause.
  - RC3 (1 test) — use column-level SELECT or capture values before rollback instead of accessing ORM attributes after `rollback()`.
  - After p-test-architect resolves RC2 and RC3, recommend a Test Pack Mode re-run (pass 3) followed by a Full Pipeline Mode run before promotion (Test Pack Mode does not gate the manifest/migration/build promotion path).
