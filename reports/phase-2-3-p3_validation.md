# Validation Report — Phase-2.3-P3
Date: 2026-07-15
Plan: docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md

## Result: PASS WITH MINORS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Route | Finding |
|------|-------------|----------|-------|---------|
| 1 | Alembic migration to drop `uq_twin_states_athlete_activity` unique index | ✅ | | Migration `21f955c743cb_phase_2_3_p3_drop_twin_states_activity_.py` exists, drops the unique index, and creates a non-unique `ix_twin_states_athlete_activity` index on `(athlete_id, activity_id)` with the `WHERE activity_id IS NOT NULL` partial predicate. `down_revision` correctly points to `8413e6547a40` (the P1 head). Downgrade restores the unique index. |
| 2 | Extend `TwinRecalibrationService` with `recalibrate_for_calibration` method | ✅ | | Method exists at `app/services/twin_recalibration_service.py`. Accepts `athlete_id`, `activity_id`, and `PhysiologyUpdateResult`. Reads `AthleteFitness` for inline snapshot, reads active `TrainingGoal` for FK, derives `confidence_level` from `min(lt1.hr.prior_weight, lt2.hr.prior_weight)` with 4.0/8.0 thresholds, applies monotonic ratchet via `max(previous, computed)`, derives per-metric `metric_confidence` with ADR-011 ratchet, builds inline threshold snapshot (`lt1_hr_bpm`, `lt2_hr_bpm`, `cp_watts`), calls `insert_if_not_exists`, fires `twin_recalibrated` and conditionally `twin_confidence_upgraded`, returns `CalibrationRecalibrationResult`. |
| 3 | Implement `insert_if_not_exists` deduplication logic | ✅ | | Method exists on `TwinRecalibrationService`. Uses `get_by_activity_and_trigger` to check for existing calibration TwinState (skips if found). Falls back to `get_by_activity` for duplicate non-calibration check. Calibration supersedes activity_sync (inserts), duplicate calibration is skipped, duplicate non-calibration is skipped. `TwinStateRepository.get_by_activity_and_trigger` added as new method. |
| 4 | Implement `twin_recalibrated` event firing | ✅ | | Event fired via `self.events.publish` with correct payload: `athlete_id`, `twin_state_id`, `previous_twin_state_id` (null if first), `trigger` ("calibration"), `confidence_level`, `fitness_score`, `fatigue_score`. Written to transactional outbox in same transaction. Fires for every new calibration TwinState (no threshold gate). |
| 5 | Implement `twin_confidence_upgraded` event firing | ✅ | | Event fired only when `confidence_level` strictly increased (checked via `_confidence_rank` comparison). Payload: `athlete_id`, `from_level`, `to_level`, `twin_state_id`. Fires in addition to `twin_recalibrated`, same transaction. |
| 6 | Create `threshold_detection` procrastinate worker task | ✅ | | Task registered as `@app.task(name="threshold_detection")` in `app/worker/app.py`. Opens own `AsyncSession`, loads Activity to extract `athlete_id`, constructs `ThresholdDetectionService` with `PlannedSessionRepository` (required for LT1 natural training analysis), constructs `PhysiologyUpdateService` and `TwinRecalibrationService`, calls `detect` → `apply_observations` → `recalibrate_for_calibration`, commits atomically. Early returns on empty observations and empty `shifted_parameters`. Returns correct dict shape. |
| 7 | Wire pipeline: `signal_clean` defers `threshold_detection` after commit | ✅ | | `signal_clean` task extended: after `session.commit()`, if `result.created` is True, defers `threshold_detection` via `app.tasks["threshold_detection"].defer(activity_id=activity_id)`. Defer failures swallowed after `log_event` logging. Defer happens AFTER commit (ADR-009). Only `activity_id` passed (task loads activity to extract `athlete_id`). |
| 8 | Register `CalibrationRecalibrationResult` in `app/services/__init__.py` | ✅ | | `CalibrationRecalibrationResult` imported from `twin_recalibration_service` and listed in `__all__`. `TwinRecalibrationService` already exported. |
| 9 | Test Architect: generate test files and update test manifest | N/A | | Step 9 is `[OWNER: Test Architect]` — explicitly skipped per Coder Scope. No test files for P3-specific methods (`recalibrate_for_calibration`, `insert_if_not_exists`, `twin_recalibrated`, `twin_confidence_upgraded`) exist. Test manifest `tests/test-manifest/phase-2-3.yaml` does not exist. This is expected per the plan's Coder Handoff Notes. |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Route | Finding |
|----------|-------|----------|-------|---------|
| Invariant: No `UPDATE` or `DELETE` at any layer — `TwinStateRepository` exposes only `insert`, `get_latest`, `get_by_activity`, `get_history` | ✅ | | | `TwinStateRepository` exposes `insert`, `get_latest`, `get_by_id`, `get_by_activity`, `get_by_activity_and_trigger`, `get_history`. No `update` or `delete` methods. The new `get_by_activity_and_trigger` is a read method consistent with the append-only contract. |
| Invariant: Multiple TwinStates per day possible, one per `activity_id` (clarified: calibration coexists with activity_sync) | ✅ | | | Unique index dropped (Step 1). `insert_if_not_exists` implements application-level deduplication allowing calibration to coexist with prior activity_sync. |
| Invariant: `confidence_level` recomputed from `min(lt1.hr.prior_weight, lt2.hr.prior_weight)` at each snapshot | ✅ | | | `_derive_confidence_level` computes `min(lt1_hr_weight, lt2_hr_weight)` with `None` treated as 0.0, maps through 4.0/8.0 thresholds. |
| Invariant: Confidence level of a TwinState never changes after creation | ✅ | | | New TwinState is created with the ratcheted `confidence_level` value; the row is append-only (no update). |
| Invariant: A new TwinState record is created when confidence transitions | ✅ | | | `recalibrate_for_calibration` always inserts a new TwinState (via `insert_if_not_exists`) when called. |
| Invariant: Confidence is monotonic (only increases, never decreases) | ✅ | | | Global level: `_max_confidence_level(old_level, computed_level)` keeps the higher. Per-metric: `_max_confidence_level_string(previous, computed)` keeps the higher, with null = "no data" (computed wins). |
| Invariant: Threshold detection only runs for `calibration_eligible = true` activities | ✅ | | | `ThresholdDetectionService.detect` guards on `activity.calibration_eligible` (returns `[]` if false). The `threshold_detection` worker task delegates to this service. |
| Invariant: `physiology_updated` event fires only when posterior shifts by > 1 bpm | ✅ | | | Handled by P2's `PhysiologyUpdateService` (out of scope for P3). The `threshold_detection` task checks `update_result.shifted_parameters` and returns early if empty — does not re-evaluate the threshold. |
| Event: `twin_recalibrated` — payload fields | ✅ | | | Payload contains all required fields: `athlete_id`, `twin_state_id`, `previous_twin_state_id` (null if first), `trigger` ("calibration"), `confidence_level`, `fitness_score`, `fatigue_score`. |
| Event: `twin_recalibrated` — ordering (after `physiology_updated`, same transaction) | ✅ | | | `physiology_updated` is produced by P2's `apply_observations` (called before `recalibrate_for_calibration`). `twin_recalibrated` is produced inside `recalibrate_for_calibration`. Both in the same transaction (worker task commits once). |
| Event: `twin_confidence_upgraded` — payload fields | ✅ | | | Payload contains: `athlete_id`, `from_level`, `to_level`, `twin_state_id`. |
| Event: `twin_confidence_upgraded` — ordering (after `twin_recalibrated`, only on upgrade) | ✅ | | | Fired after `twin_recalibrated` in `recalibrate_for_calibration`. Only fires when `_confidence_rank(inserted.confidence_level) > _confidence_rank(old_level)`. |
| ADR-011: Per-metric confidence ratchet in `TwinRecalibrationService`, NOT in `PhysiologyUpdateService` | ✅ | | | Ratchet applied in `recalibrate_for_calibration` (Step 2) via `_max_confidence_level_string` per metric. P2's `PhysiologyUpdateResult.metric_confidence` is the raw computed level. `TwinStateRepository` is NOT a dependency of `PhysiologyUpdateService`. |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Route | Action |
|------|---------------|----------------|-------|--------|
| `TwinStateRepository.get_by_activity_and_trigger` | New repository method for trigger-specific lookup | Acceptable | — | The plan's Known Risks section explicitly calls out the need to check for existing calibration TwinStates: "Use a query that checks for any existing TwinState with `trigger = 'calibration'` for this activity — if one exists, skip the insert. The `get_by_activity` method should be updated (or a new `get_by_activity_and_trigger` method added) to support this lookup." This is a routine implementation detail explicitly authorized by the plan. |
| `TwinStateRepository.get_by_id` | Repository method not mentioned in plan | Acceptable | — | Pre-existing method (not added by this plan); listed in the repository docstring. Not a deviation introduced by P3. |
| `app/models/twin_state.py` — `ix_twin_states_activity` index | Additional non-unique index on `activity_id` alone | Acceptable | — | Pre-existing index in the model (not added by this plan's migration). Supports the `get_by_activity` lookup. No action needed. |
| `signal_clean` defer uses `app.tasks["threshold_detection"].defer` directly | Direct procrastinate app reference instead of injected dispatcher | Acceptable | — | The `signal_clean` task is a worker task (not a service). Worker tasks defer via `app.tasks[...]` directly — this is the established pattern for worker-to-worker deferral (the `fit_ingest` task follows the same structure). The `_defer_signal_clean` injection pattern is for the service layer's testability, not the worker layer. The plan says "Follow the exact same defer pattern used by `ActivityIngestionService._defer_signal_clean`" referring to the swallow-after-logging behavior, which is correctly implemented. |

---

## Stack-Truth

### CRITICAL
*(none)*

### MAJOR
*(none)*

### MINOR
- **Missing `SignalCleaningService` export**: `app/services/__init__.py` — `SignalCleaningService` is not exported in `__all__` (noted in dynamic state's Missing Exports). This is a pre-existing issue from Phase 2.2, not introduced by P3. The `threshold_detection` worker task imports `SignalCleaningService` directly from its module, so this does not affect P3 functionality. — Route: p-coder
- **`BanisterUpdateResult` exported but not in import block**: `app/services/__init__.py` — `BanisterUpdateResult` is listed in `__all__` but is not explicitly imported at the top of the file (it would fail if `__all__` were used for star-imports). However, the dynamic state shows it in the imports list, so this may be a false positive from the static scan. Pre-existing, not introduced by P3. — Route: p-coder

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 6 of 6 listed in scope (migration, twin_recalibration_service.py, worker/app.py, services/__init__.py, twin_state_repository.py, twin_state.py) |
| Release alignment checked | yes — Phase 2.3 sub-phase "Threshold Detection & Physiology Update" confirmed; P3 scope is Twin Recalibration Extension + Pipeline Integration, within sub-phase |
| Deviation scan complete | yes — grep for P3 symbols in tests confirmed no P3-specific tests exist (expected, Step 9 is Test Architect owned); no out-of-scope files created |
| Dynamic context available | yes — `docs/implementation/implemented-state.md` loaded and used as primary state reference |

---

## Routing Summary

| Owner | Findings |
|---|---|
| p-coder | Stack-Truth MINOR (missing `SignalCleaningService` export — pre-existing, not P3-introduced) |
| p-architect | — |
| p-devops | — |
| p-test-architect | Step 9 (test files + manifest) — explicitly deferred per Coder Scope; not a coder finding |

## Routing — How To Read The Summary Above

| Finding | Route To |
|---------|----------|
| CRITICAL / MAJOR — Resolution Path: Implementation Fix | p-coder + this report |
| CRITICAL / MAJOR — Resolution Path: Architecture Change Required | p-architect + this report |
| MAJOR (plan gap) | p-architect + this report — plan needs updating; always Architecture Change Required, see Step 7 |
| DEVIATION / Layer 3 CRITICAL | p-architect + this report — architect acknowledges or requests ADR |
| MINOR (hygiene) | p-coder + this report |
| Migration incomplete | p-devops + this report |
| No findings | p-devops |

---

## Summary

The Phase-2.3-P3 implementation is a clean, faithful execution of the plan. All 8 coder-owned steps are implemented correctly:

1. **Migration** (`21f955c743cb`) drops the unique index and replaces it with a non-unique partial index — exactly as specified.
2. **`recalibrate_for_calibration`** method implements the full contract: confidence derivation with 4.0/8.0 thresholds, global monotonic ratchet, per-metric ADR-011 ratchet, inline threshold snapshot from updated `AthletePhysiology`, and event firing.
3. **`insert_if_not_exists`** implements the deduplication decision matrix correctly — calibration supersedes activity_sync, duplicate calibration is skipped, duplicate non-calibration is skipped. The new `get_by_activity_and_trigger` repository method supports the calibration-specific lookup as the plan's Known Risks section recommended.
4. **`twin_recalibrated`** event fires with the correct payload for every new calibration TwinState.
5. **`twin_confidence_upgraded`** event fires only on strict confidence increase, with correct `from_level`/`to_level` payload.
6. **`threshold_detection` worker task** orchestrates the full pipeline (detect → apply_observations → recalibrate_for_calibration → commit) with correct early-return paths, `PlannedSessionRepository` wiring for LT1 natural training analysis, and atomic single-commit boundary.
7. **`signal_clean` defer wiring** defers `threshold_detection` after commit when `result.created` is True, swallows defer failures after logging (ADR-009 pattern).
8. **`CalibrationRecalibrationResult`** registered in `app/services/__init__.py`.

No CRITICAL or MAJOR findings. No deviations requiring architect acknowledgement. The only MINOR finding (missing `SignalCleaningService` export) is pre-existing from Phase 2.2 and does not affect P3 functionality. Step 9 (tests) is explicitly Test Architect-owned and was correctly skipped by the coder.
