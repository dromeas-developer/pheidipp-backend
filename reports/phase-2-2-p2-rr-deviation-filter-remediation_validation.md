# Validation Report — Phase-2.2-P2
Date: 2026-07-09
Plan: docs/implementation/phase-2/phase-2-2-p2-rr-deviation-filter-remediation.md

## Result: PASS WITH MINORS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | Add `RR_ROLLING_WINDOW_S` and `RR_DEVIATION_THRESHOLD` frozen module constants with docstrings | ✅ | Constants defined at lines 122-124 with docstrings referencing `02-computations/signal-cleaning.md` Step 1 and `threshold-detection.md` Algorithm 2. Values match spec: `RR_ROLLING_WINDOW_S: int = 30`, `RR_DEVIATION_THRESHOLD: float = 0.20`. |
| 2 | Extend `_remove_artifacts` with follow-on RR deviation pass after hard-bound and power passes | ✅ | Third pass implemented at lines 729-766. Runs AFTER hard-bound pass (695-707) and power pass (710-727). Operates on `artifact_free.rr`. Window excludes candidate (`artifact_free.rr[window_start:t]` half-open slice). Skips windows with `< 2` non-null samples. Nulls when `abs(rr - median) > RR_DEVIATION_THRESHOLD * median`. Null-propagation preserved (`if rr is None: continue`). Only RR — HR/power/speed/elevation untouched. |
| 3 | Update `_remove_artifacts` docstring to document two-stage RR removal | ✅ | Docstring (lines 668-688) lists all four artifact rules and explicitly states the RR two-stage removal with window=30s, threshold=0.20, referencing both signal-cleaning.md Step 1 and threshold-detection.md Algorithm 2. |
| 4 | Remove `self._session = session` from `__init__`; retain constructor `session` param | ✅ | No `self._session = session` assignment exists. Grep for `self._session` returns a single match inside an explanatory comment (line 368), not an assignment or read site. Constructor `session` parameter retained (line 357); worker still calls `SignalCleaningService(session=session, ...)` (app/worker/app.py:272). |
| 5 | Update `tests/test-manifest/phase-2-2.yaml` with RR deviation filter entry (Test Architect scope) | MINOR | `tests/test-manifest/phase-2-2.yaml` exists and its `signal_cleaning_pipeline_integration` feature `protects` field includes "Cleaned RR values that deviate more than ±20% from the rolling median are filtered out." However, the manifest's `plan_id` and `owned_by_plan` attribute to `phase-2-2-p1-signal-cleaning`, not `phase-2-2-p2`. No dedicated P2 entry was added. This step was explicitly Test Architect scope (skipped by coder per "Coder Scope"), so it is outside the coder's batch — noted for routing only. |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: Steps run in fixed order 1→7, no skip/reorder | ✅ | | Call sequence in `clean()` (lines 479-483): `_resample_to_1hz` → `_remove_artifacts` → `_smooth` → `_compute_derived_metrics` → `_compute_rolling_features`. The RR deviation pass is the third sub-pass inside `_remove_artifacts`, ordered after hard-bound and power passes. |
| Invariant: Null propagation — > 80% null after artifact removal → unavailable | ✅ | | `_available_channels(artifact_free)` called at line 487, AFTER `_remove_artifacts` returns. `rr_available = _available(resampled.rr)` reads the post-deviation-filter array. The > 80% null rule enforced via `NULL_FRACTION_UNAVAILABLE_THRESHOLD = 0.80`. |
| Invariant: One RawSensorStream per Activity, created atomically with cleaned stream upload | ✅ | | Unchanged by this plan — persistence path (lines 507+) not modified. |
| Invariant: Cleaning failure → no RawSensorStream, null cleaning_pipeline_version, segmentation skipped | ✅ | | Short-stream gate (lines 491-505) returns `created=False, reason="short_stream"` before any row write. Unchanged. |
| Invariant: available_channels reflects what survived artifact removal | ✅ | | Confirmed: `_available_channels` receives `artifact_free` (post-hard-bound AND post-deviation-filter). RR availability now correctly reflects deviation-filtered samples. |
| Invariant: < 5 min non-null HR → no RawSensorStream, segmentation skipped | ✅ | | Gate at lines 491-505 reads `artifact_free.hr` (not RR). RR deviation change does not touch HR array. Regression guard intact. |
| Invariant: Cleaned RR values deviating > ±20% from rolling median are filtered out (Exit Gate) | ✅ | | Deviation pass at lines 729-766 nulls samples where `abs(rr - median) > 0.20 * median`. Window excludes candidate. Implements the Exit Gate bullet verbatim. |
| Event Contracts: None | ✅ | | Plan produces/consumes no events. Confirmed — no event emission in `_remove_artifacts`. |
| PLAN GAP: None | ✅ | | All contracts the implementation depends on are present in the plan's Invariants and Architecture Contracts sections. |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| None | No files created or modified beyond plan scope | — | Coder Scope confined changes to `app/services/signal_cleaning_service.py`. Verified `app/worker/app.py` (signal_clean task) and `app/services/activity_ingestion_service.py` (enqueue hook) are untouched — worker still constructs `SignalCleaningService(session=session, ...)`; constructor signature unchanged. |

---

## Stack-Truth

### CRITICAL
- None

### MAJOR
- None

### MINOR
- Test manifest attribution: `tests/test-manifest/phase-2-2.yaml` references the RR deviation filter in its `protects` field but attributes ownership to `phase-2-2-p1-signal-cleaning` rather than adding a dedicated `phase-2-2-p2` entry. This is Test Architect scope (Step 5, explicitly skipped by the coder) and does not affect code conformance.

---

## Detailed Verification Notes

### RR Deviation Filter — Window Exclusion (Highest-Risk Item)
The plan's Coder Handoff Notes flag the window-exclusion convention as the single highest-risk error: the RR window MUST exclude the candidate sample, unlike the power pass which includes it. Verification:
- **Power pass** (lines 716-717): `resampled.power[window_start : t + 1]` — includes candidate. Correct for 3× threshold.
- **RR deviation pass** (lines 757-760): `artifact_free.rr[window_start:t]` — half-open slice, excludes candidate at `t`. Matches plan pseudocode exactly. ✓

### Pass Ordering (Second-Risk Item)
The plan states ordering is load-bearing: hard-bound → power → RR deviation. Verification (lines 695-766):
1. Hard-bound pass (HR 30-220, speed >25, RR 200-2500) — lines 695-707
2. Power 3× rolling-median pass — lines 710-727
3. RR ±20% deviation pass — lines 729-766
Order matches plan Step 2 spec. The deviation median sees only post-hard-bound samples (hard-bound nulls are already in `artifact_free.rr` and excluded via `if v is not None`). ✓

### Dead Field Removal
`grep "self._session" app/services/signal_cleaning_service.py` returns 1 match — inside a comment at line 368 explaining why the field was removed. Zero assignment sites, zero read sites. Constructor `session` parameter retained (line 357). ✓

### available_channels Post-Deviation Evaluation
`clean()` line 487: `available = self._available_channels(artifact_free)`. The `artifact_free` object is the return value of `_remove_artifacts`, which includes the deviation pass. `_available_channels` line 1086: `rr_available = _available(resampled.rr)` reads the deviation-filtered array. An RR channel where the hard bound left > 80% non-null but the deviation filter pushed null fraction past 80% will correctly yield `rr_intervals: false`. ✓

### Idempotency Guard (Regression)
`exists_for_activity` check at line 437 returns `created=False, reason="already_cleaned"` BEFORE the pipeline runs (line 479). Re-running `signal_clean` against an already-cleaned activity never reaches the deviation filter. ✓

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 1 of 1 listed in scope |
| Release alignment checked | yes |
| Deviation scan complete | yes |
| Dynamic context available | yes |

Confidence is HIGH: all scope files loaded, dynamic state (`implemented-state.md`) available and consulted, contracts fully embedded in the plan, release alignment confirmed (sub-phase `phase-2-2-signal-cleaning` in Phase 2), and deviation scan complete (worker + ingestion service verified untouched).

---

## Routing

| Finding | Route To |
|---------|----------|
| MINOR (test manifest attribution) | p-test-architect + this report — consider adding a dedicated `phase-2-2-p2` ownership entry or updating `owned_by_plan` to reference both P1 and P2 |
| No other findings | p-devops — implementation is conformant; ready for deployment |
