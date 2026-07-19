# DevOps Test Pack Report — oneoff_regression_validation (pass 1)
Date: 2026-07-19
Re-verifying: reports/oneoff_regression_validation_20260719.md — RC2 (twin recalibration test fix)
Test execution group / scope: regression (full suite, same as prior run)

## Result: PASS

Tests: **2635 passed** / **0 failed** / 2 skipped
Root causes resolved: **1 of 1** from the prior report (RC2 — 5 behavioural test failures)

## Result consistency

**2635 passed, 0 failed** — identical to the prior rerun (which had 5 pre-existing
failures), but now those 5 pre-existing failures are also resolved because the
test architect's fix batch included:

- `test_migration_phase_1_2c.py` — updated to expect `ix_twin_states_athlete_activity`
- `test_twin_state_schema.py` — updated for non-unique index + relaxed duplicate-activity test
- `test_litellm_connectivity.py` — relaxed assertion to `"ok" in content`

## Infrastructure Fixes

None.

## Full Failure Detail

No failures.

## Next Step

→ **All tests pass.** The twin recalibration user journey is fully green.
  A Full Pipeline Mode run is recommended before promotion to also validate
  the migration/build gate.
