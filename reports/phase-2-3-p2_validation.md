# Validation Report — Phase-2.3-P2
Date: 2026-07-13
Plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md

## Result: PASS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | `AthletePhysiologyRepository.update_in_place` method | ✅ | Method exists at `app/repositories/athlete_physiology_repository.py:54-121`. Takes `athlete_id` plus `lt1`, `lt2`, `cp`, `max_hr` as keyword-only args. Flushes without committing (caller owns commit boundary). Does NOT create a new row — fetches existing via `get_by_athlete_id` and raises `RuntimeError` if missing. Uses `_UNSET` sentinel (exported as `UNSET_SENTINEL`) to distinguish "not passed" from "passed as None" for nullable `cp`/`max_hr` columns. Follows the existing `add` method's flush pattern. |
| 2 | `PhysiologyUpdateService` created with `apply_observations` entry point | ✅ | Service at `app/services/physiology_update_service.py:395-707`. Constructed with `AsyncSession`, optional `AthletePhysiologyRepository`, optional `PhysiologyMeasurementRepository`, optional `EventPublisher` (defaults built from session). `apply_observations(athlete_id, observations)` loads physiology, applies Bayesian update per observation, writes measurements, updates physiology in place, fires event if shifted, returns `PhysiologyUpdateResult`. |
| 3 | Bayesian update pure function | ✅ | `bayesian_update()` at line 96-167. Pure function (no I/O, no mutation). Implements all formula steps: `days_since_last`, `decay_factor = exp(-days_since_last / 42)`, `decayed_weight`, `new_total_weight`, `posterior_mean`, `posterior_uncertainty = max(uncertainty * sqrt(decayed_weight / new_total_weight), 0.5)`, `dominant_source` (observation wins if weight > decayed_weight), `last_observation_date`. Returns new dict in `PhysiologyParameterState` shape. Module-level for unit-test access. |
| 4 | `PhysiologyMeasurement` record writing | ✅ | `_write_measurement()` at line 780-807. Creates `PhysiologyMeasurement` with `athlete_id`, `activity_id`, `parameter`, `observed_value`, `source`, `measurement_date`, `algorithm_used`, `confidence_weight`, `raw_data_reference=None`, `notes=None`. Inserts via `PhysiologyMeasurementRepository.insert`. Always written — called unconditionally for every observation including duplicates. |
| 5 | Posterior shift detection | ✅ | Lines 603-614. Compares `abs(new_state["value"] - current_state["value"])` against `> 1.0` threshold. Shifted parameters tracked in ordered list (`shifted_parameters`) plus set for O(1) membership. Previously-null parameters (first observation) are correctly NOT counted as shifts (suppressed by `current_state is None` check). |
| 6 | `AthletePhysiology` in-place update | ✅ | `_apply_updated_states()` at line 718-776 correctly writes JSONB columns with `flag_modified` for dirty tracking. The `update_in_place` call at line 614-636 now passes ONLY the columns that were actually touched in the batch — `touched_columns` is computed from `working_state` and each column is passed only if present, else `None` (for `lt1`/`lt2`) or `UNSET_SENTINEL` (for `cp`/`max_hr`) to signal "do not touch". This satisfies Plan Step 6's "Only update columns that have changed — leave unchanged columns untouched to minimise write amplification." |
| 7 | `physiology_updated` event firing | ✅ | Lines 651-701. Fires via `EventPublisher.publish()` only when `shifted_parameters` is non-empty. Payload contains `athlete_id` (str), `parameters_updated` (list of `.value` strings), `dominant_sources` (dict param→source), `prior_weights` (dict param→weight). Written to transactional outbox in same transaction as physiology update (EventPublisher uses same session). Does NOT fire when no parameters shifted. |
| 8 | Confidence transition detection | ✅ | `_compute_metric_confidence()` at line 974-1007 computes per-metric levels from `prior_weight` using thresholds 4.0 (MEDIUM) and 8.0 (HIGH). `_detect_confidence_transitions()` at line 928-961 reports only upward transitions (LOW→MEDIUM, MEDIUM→HIGH) using `_CONFIDENCE_LEVEL_ORDER` ranking. The service computes `metric_confidence` purely from current `prior_weight` and does NOT enforce the monotonicity ratchet — exactly as the plan requires (Step 8: "This service computes the raw confidence level from current `prior_weight` — it does NOT enforce the monotonicity ratchet"; Notes: "P2 computes `metric_confidence` purely from current `prior_weight`... the monotonicity ratchet is enforced in P3's `TwinRecalibrationService`"; ADR-011). No `TwinStateRepository` dependency is added — the ownership boundary is respected. |
| 9 | Idempotency for duplicate observations | ✅ | `_is_duplicate()` at line 851-880 checks for existing `PhysiologyMeasurement` matching `(athlete_id, activity_id, parameter, source, measurement_date, observed_value)`. Uses `get_recent_for_parameter` with `from_date=obs.measurement_date` and Python-side filter on `observed_value` and `activity_id`. Duplicates still write the measurement (line 575-577) but skip Bayesian update and event contribution (line 578 `continue`). |
| 10 | `PhysiologyUpdateResult` dataclass | ✅ | At line 248-273. Carries `physiology: AthletePhysiology`, `shifted_parameters: list[PhysiologyParameter]`, `metric_confidence: Dict[str, Optional[str]]`, `confidence_transitions: Dict[str, tuple[Optional[str], Optional[str]]]`, `measurements_written: int`. All fields present with correct types. |
| 11 | Registration in `app/services/__init__.py` | ✅ | `app/services/__init__.py:103-107` imports `MissingAthletePhysiologyError`, `PhysiologyUpdateResult`, `PhysiologyUpdateService`. All three are in `__all__` (lines 142, 179, 180). |
| 12 | Test files and manifest | N/A | Step 12 is [OWNER: Test Architect] — Coder Handoff Notes say "Skip: Step 12". Not validated. |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: One `AthletePhysiology` per athlete, mutable in place | ✅ | | `update_in_place` fetches existing row and mutates it; never creates new row. |
| Invariant: `physiology_updated` fires only when posterior shifts > 1 bpm | ✅ | | Event fires only when `shifted_parameters` is non-empty; shift threshold is `> 1.0` at line 609. |
| Invariant: Bayesian update with 42-day prior decay | ✅ | | `DECAY_TIME_CONSTANT_DAYS = 42.0` at line 80; `decay_factor = math.exp(-days_since_last / 42)` at line 137. |
| Invariant: Confidence is monotonic (only increases, never decreases) | ✅ | | The plan explicitly states (Step 8, Notes, ADR-011) that P2 does NOT enforce the monotonicity ratchet — it computes `metric_confidence` purely from current `prior_weight`, and the ratchet (`max(stored_level, computed_level)`) is enforced in P3's `TwinRecalibrationService`. The implementation correctly computes raw confidence from `prior_weight` without adding a `TwinStateRepository` dependency. The `_detect_confidence_transitions` function correctly reports only upward transitions within a single `apply_observations` call. The "confidence is monotonic" invariant is preserved at the P3 boundary, not here — this is the plan's explicit design. |
| Invariant: Observation thresholds 4.0 (LOW→MEDIUM), 8.0 (MEDIUM→HIGH) | ✅ | | `_confidence_level()` at line 878-891: `>= 8.0` → HIGH, `>= 4.0` → MEDIUM, else LOW. |
| Invariant: Per-metric evidence accumulation | ✅ | | Each observation routes to its specific parameter via `_PARAMETER_PATH`; parameters are independent. |
| Invariant: `PhysiologyMeasurement` always written regardless | ✅ | | `_write_measurement` called unconditionally for every observation, including duplicates (line 576) and non-shifting observations (line 595). |
| Invariant: `cp` null until qualifying observation, never bootstrapped from questionnaire | ✅ | | `init_null_parameter_state` bootstraps `cp` only on first qualifying observation; onboarding bootstrap sets `cp=None`. |
| Invariant: `prior_weight` decays over time (~3 years → zero) | ✅ | | `bayesian_update` applies `decay_factor = exp(-days_since_last / 42)` to existing `prior_weight` before adding new weight. |
| Event: `physiology_updated` — payload `athlete_id` | ✅ | | `payload["athlete_id"] = str(athlete_id)` at line 654. |
| Event: `physiology_updated` — payload `parameters_updated` | ✅ | | List of `param.value` strings at line 656. |
| Event: `physiology_updated` — payload `dominant_sources` | ✅ | | Dict `param.value → source` at line 660. |
| Event: `physiology_updated` — payload `prior_weights` | ✅ | | Dict `param.value → weight` at line 664. |
| Event: `physiology_updated` — ordering (after update, same transaction) | ✅ | | Event published at line 667 AFTER `update_in_place` at line 614. Both use the same `AsyncSession` — `EventPublisher` writes `SystemEvent` + `SystemEventOutbox` in the caller's transaction. No commit in between (service does not commit). |
| Event: `physiology_updated` — fires only when ≥ 1 parameter shifted > 1 unit | ✅ | | `if shifted_parameters:` guard at line 651. |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `init_null_parameter_state()` helper | Module-level pure function to bootstrap a `PhysiologyParameterState` from the first observation against a null parameter column | Acceptable | Implied by Step 3's clarification ("First observation for CP: `physiology.cp` starts as null..."). Routine implementation detail. |
| `_PARAMETER_PATH` includes VO2MAX_ML_KG_MIN, VO2MAX_POWER, MAX_HR | Parameter→JSONB path mapping extended beyond the plan's explicit mention of LT1_HR, LT2_HR, CP, MAX_HR to also cover VO2MAX sub-states | Acceptable | Forward-looking wiring that does not change behaviour — no algorithm produces VO2MAX observations in this phase. Harmless. |
| `MissingAthletePhysiologyError` exception class | New error class raised when no `AthletePhysiology` row exists | Acceptable | Implied by the pseudocode (`raise MissingAthletePhysiologyError(athlete_id)`). Registered in `__init__.py` per Step 11. |
| `_build_default_publisher()` static method | Default `EventPublisher` construction from session when not injected | Acceptable | Follows the existing `ActivityIngestionService` pattern referenced in the plan. |
| `UNSET_SENTINEL` exported from repository | The `_UNSET` sentinel is publicly aliased as `UNSET_SENTINEL` and imported by the service | Acceptable | Required for the service to pass "do not touch" signals to `update_in_place` for nullable columns. Routine implementation detail. |

---

## Stack-Truth

### CRITICAL
- (none)

### MAJOR
- (none)

### MINOR
- (none)

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 3 of 3 listed in scope |
| Release alignment checked | yes — plan belongs to Phase 2.3 (Threshold Detection & Physiology Update), part of Phase 2 |
| Deviation scan complete | yes — no files created beyond plan scope; no new dependencies; no layer violations |
| Dynamic context available | yes — `docs/implementation/implemented-state.md` loaded and used as primary source of truth |

---

## Routing

| Finding | Route To |
|---------|----------|
| No findings | p-devops — migration is already at head `8413e6547a40` per dynamic state; no new migration needed for this plan. Implementation is clean and ready for P3 handoff. |

---

## Re-Validation Summary

This re-validation confirms that both findings from the previous validation run (2026-07-12) have been resolved:

1. **Previous MAJOR (confidence monotonicity ratchet not implemented)**: On re-reading the plan, this finding was a misreading. The plan explicitly states in Step 8, the Notes section, and the Architecture Contracts (ADR-011 reference) that P2 must NOT enforce the monotonicity ratchet — it computes `metric_confidence` purely from current `prior_weight`, and the ratchet is enforced in P3's `TwinRecalibrationService`. The implementation correctly follows this design: `_compute_metric_confidence` computes from `prior_weight` only, no `TwinStateRepository` dependency is added, and the ownership boundary is respected. **No fix was needed — the implementation was already correct.**

2. **Previous MINOR (write amplification on `update_in_place`)**: Fixed. The service now computes `touched_columns` from `working_state` and passes only the touched JSONB columns to `update_in_place`. Untouched columns are passed as `None` (for non-nullable `lt1`/`lt2`, meaning "do not touch") or `UNSET_SENTINEL` (for nullable `cp`/`max_hr`, meaning "do not touch"). This satisfies Plan Step 6's "minimise write amplification" requirement.
