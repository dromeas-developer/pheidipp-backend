# DevOps Test Pack Report — phase-2-3-p2 (pass 3)
Date: 2026-07-15
Re-verifying: reports/phase-2-3-p2_devops.md (dated 2026-07-14) — RC1 (source_value), RC2 (decay expectations / accumulation), RC3 (post-rollback ORM access)
Test execution group / scope: feature (same 10 test files as prior runs)

## Result: FAIL

Tests: 192 passed / 1 failed / 0 skipped
Root causes resolved: 2 of 3 from the prior report (RC1 — source_value; RC2 — decay expectations)
Root causes still open: 1 (see Root Cause Analysis below)

### Changes from prior test-pack run (pass 2)

| Metric | Pass 2 | Pass 3 | Delta |
|---|---|---|---|
| Total tests | 193 | 193 | 0 |
| Passed | 185 | 192 | +7 |
| Failed | 8 | 1 | -7 |
| Skipped | 0 | 0 | 0 |

### What p-test-architect fixed (7 additional tests now passing)

The 7 RC2 tests from pass 2 have been resolved — all confidence-transition and accumulation integration tests now pass:

| Test | Pass 2 | Pass 3 |
|---|---|---|
| `test_four_observations_reach_prior_weight_4_point_5` | FAIL | PASS |
| `test_eight_observations_reach_prior_weight_8_point_5` | FAIL | PASS |
| `test_eighth_observation_triggers_medium_to_high_transition` | FAIL | PASS |
| `test_four_rr_observations_reach_high_confidence` | FAIL | PASS |
| `test_three_calls_each_with_one_observation` | FAIL | PASS |
| `test_second_observation_grows_prior_weight` | FAIL | PASS |
| `test_second_observation_fires_event_when_shift_exceeds_one` | FAIL | PASS |

These 7 tests were fixed per the pass 2 routing (RC2, p-test-architect) by pinning all observations in accumulation-asserting tests to the same `measurement_date=date(2026, 6, 15)` with distinct `observed_value` to avoid dedup, and restructuring the `test_four_rr_observations_reach_high_confidence` test to use a single batch call (since the loop pattern's pre-call level on the 4th call is MEDIUM, not LOW). The fixes are documented in MOCKING_CONTRACT.md dated 2026-07-14 (pass 2).

## Infrastructure Fixes

No infrastructure changes were made in this session — the attempted `expire_on_rollback=False` fix in `tests/conftest.py` was reverted because SQLAlchemy 2.x does not support that parameter (raises `TypeError`). The fix remains a test content change.

## Root Cause Analysis

### RC1 — `_source_value()` returns `source.value` instead of `str(source)` [RESOLVED]

All 7 tests that formerly failed due to `str(MeasurementSource.MEMBER)` — confirmed resolved in pass 1 and still resolved in this pass. No source_value failures remain.

---

### RC2 — Test expectations need re-calibration for 1-day inter-observation decay [RESOLVED]

All 7 tests from pass 2 now pass. The MOCKING_CONTRACT.md entries dated 2026-07-14 (pass 2) captured the pattern correctly and the fixes were applied by p-test-architect. No further action needed.

---

### RC3 — `test_event_atomicity_rolls_back_when_later_step_fails`: MissingGreenlet after rollback (refined diagnosis)

- **Category:** Test Suite
- **Owner:** p-test-architect
- **Confidence:** High (traceback directly identifies the cause)

- **Evidence:**
  - The column-level SELECT fix applied in pass 2 (replacing `fresh.lt2` access with `select(AthletePhysiology.lt2)`) was **necessary but not sufficient**.
  - The error now occurs at line **878** of `test_physiology_update_service_integration.py`, which is the **first assertion query** after `db_session.rollback()` at line ~871:
    ```python
    events = (await db_session.execute(
        select(SystemEvent).where(
            SystemEvent.event_type == "physiology_updated",
            SystemEvent.athlete_id == athlete.id,  # <-- LINE 878: athlete.id triggers lazy load!
        )
    )).scalars().all()
    ```
  - After `db_session.rollback()`, SQLAlchemy expires **ALL** ORM instances tracked by the session, including the `athlete` object loaded at line 835.
  - Accessing `athlete.id` (line 878) on an expired instance triggers a lazy-load attempt. In async mode with asyncpg, this requires a `greenlet_spawn` context, which is not available in the middle of an `await` chain — hence `MissingGreenlet`.
  - The column-level SELECT for `fresh_lt2` at lines 903-918 is never reached because the error fires first at line 878.
  - Attempted infrastructure fix (adding `expire_on_rollback=False` to `conftest.py`'s `async_sessionmaker`) failed because **SQLAlchemy 2.x does not support the `expire_on_rollback` parameter** — it was removed/never existed in this version.

- **Root cause:** The test accesses `athlete.id` (an ORM-mapped attribute) after `db_session.rollback()` has expired all loaded instances. This triggers async lazy-load outside the greenlet context.

- **Affected failures:** 1 test — `test_event_atomicity_rolls_back_when_later_step_fails`

- **Suggested fix for p-test-architect:** Capture `athlete_id` as a local variable **before** the rollback call, then use the plain Python value in all subsequent WHERE clauses. This is a one-line addition:

  ```python
  athlete_id = athlete.id  # Capture PK before rollback expires the instance
  await db_session.rollback()
  ```
  
  Then replace `athlete.id` with `athlete_id` in all subsequent filter expressions. This avoids accessing any ORM attribute on an expired instance. The column-level SELECT for `fresh_lt2` (already in place) remains correct and should continue to work once the `athlete.id` access is resolved.

## Routing Summary

| Owner | Root Causes |
|---|---|
| p-coder | — (RC1 resolved in pass 1) |
| p-test-architect | RC3 (1 test: post-rollback `athlete.id` access in WHERE clause) |
| p-devops | — |
| p-architect | — |
| Unassigned | — |

## Recommended Execution Order

Single RC — fix RC3 (capture `athlete_id` before rollback), then re-run.

## Full Failure Detail

### TestPhysiologyUpdatedEvent::test_event_atomicity_rolls_back_when_later_step_fails [RC3]

```
>           raise exc.MissingGreenlet(
                "greenlet_spawn has not been called; can't call await_only() "
                "here. Was IO attempted in an unexpected place?"
            )
E           sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
            can't call await_only() here. (Background on this error at:
            https://sqlalche.me/e/20/xd2s)
```

Traceback chain:
1. `test_physiology_update_service_integration.py:878` — `athlete.id` access in `select(SystemEvent).where(SystemEvent.athlete_id == athlete.id)`
2. → `orm/attributes.py:569` — ORM descriptor `__get__` on expired instance
3. → `state._load_expired()` — triggers lazy load
4. → `session.execute()` → pool connect → asyncpg.connect → `await_only()` fails (no greenlet context)

## Next Step
→ One RC still open (RC3, Test Suite, p-test-architect). 
→ After p-test-architect applies the fix (capture `athlete_id` before rollback), recommend a Test Pack Mode re-run (pass 4) followed by a **Full Pipeline Mode** run before promotion (Test Pack Mode does not gate the manifest/migration/build promotion path — only Full Pipeline Mode verifies the full stack).
