# Validation Report — Phase-2.3-P1
Date: 2026-07-10
Plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md

## Result: PASS WITH MINORS

---

## Revalidation Summary

This report revalidates the implementation after the issues identified in the
previous validation report (same plan ID, dated 2026-07-10) were addressed.
All four prior findings have been resolved. One new minor finding was
identified during revalidation (stale dynamic state file).

### Previous Findings — Resolution Status

| # | Previous Finding | Severity | Status | Resolution |
|---|-----------------|----------|--------|------------|
| 1 | Migration `862601a038c6` drops procrastinate tables in `upgrade()` | CRITICAL | RESOLVED | Old migration deleted. New migration `8413e6547a40_phase_2_3_p1_physiology_measurement.py` creates only the `physiology_measurements` table and its two indexes. `alembic/env.py` now has an `include_object` filter excluding `procrastinate_*` objects from autogenerate, preventing this class of artifact in future migrations. |
| 2 | `ThresholdDetectionService` not exported in `app/services/__init__.py` | MINOR | RESOLVED | `ThresholdDetectionService` and `ThresholdObservation` are now imported and listed in `__all__` in `app/services/__init__.py`. |
| 3 | `PlannedSessionRepository` as optional constructor parameter | DEVIATION | RESOLVED (plan updated) | Plan Step 6 now explicitly documents the optional `PlannedSessionRepository` parameter. Implementation Clarifications section explains the `session_type` rationale. No longer a deviation. |
| 4 | `measurement_date` source not specified in plan | PLAN GAP | RESOLVED (plan updated) | Plan Notes section now explicitly states `measurement_date` MUST be set to `activity.activity_date`. Implementation correctly uses `activity.activity_date` in all six observation-producing methods. |
| 5 | Migration naming typo ("physics" vs "physiology") | MINOR | RESOLVED | New migration file named `phase_2_3_p1_physiology_measurement.py` (correct spelling). |

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | `PhysiologyParameter` enum with all 10 values | ✅ | Enum exists in `app/models/enums.py` with all 10 values (LT1_HR, LT1_POWER, LT1_PACE, LT2_HR, LT2_POWER, LT2_PACE, CP, VO2MAX_ML_KG_MIN, VO2MAX_POWER, MAX_HR). Follows `str, Enum` pattern. Registered in `app/models/__init__.py` (both import and `__all__`). |
| 2 | `PhysiologyMeasurement` model — append-only table | ✅ | Model exists in `app/models/physiology_measurement.py` with all specified columns (id, athlete_id, activity_id, parameter, observed_value, source, measurement_date, algorithm_used, confidence_weight, raw_data_reference, notes, created_at). FK CASCADE on athlete_id, SET NULL on activity_id. Both indexes present. No UPDATE/DELETE methods. Registered in `app/models/__init__.py`. |
| 3 | Alembic migration for `physiology_measurements` table | ✅ | Migration `8413e6547a40_phase_2_3_p1_physiology_measurement.py` creates the table with correct columns, FK constraints, and both indexes. `upgrade()` creates only the `physiology_measurements` table — no procrastinate table operations. `downgrade()` drops only this table and its indexes. `alembic/env.py` has `include_object` filter excluding `procrastinate_*` objects from autogenerate. |
| 4 | `PhysiologyMeasurementRepository` with insert and query methods | ✅ | Repository exists in `app/repositories/physiology_measurement_repository.py` with `insert` (flush, no commit), `get_by_athlete`, `get_by_athlete_and_parameter`, `get_recent_for_parameter`. No update/delete methods. Registered in `app/repositories/__init__.py`. |
| 5 | `ThresholdObservation` dataclass | ✅ | Frozen dataclass exists in `app/services/threshold_detection_service.py` with all specified fields: parameter, observed_value, source, weight, activity_id, measurement_date, algorithm_used, confidence_weight. |
| 6 | `ThresholdDetectionService.detect()` entry point | ✅ | Service exists with constructor accepting AsyncSession, ObjectStorageClient, RawSensorStreamRepository, ActivityRepository, AthletePhysiologyRepository, PhysiologyMeasurementRepository, and optional PlannedSessionRepository (defaults to None). `detect(athlete_id, activity_id)` returns `list[ThresholdObservation]`. Guards: missing activity → [], calibration_eligible=false → [], sport_type != RUNNING → [], missing RawSensorStream → []. Downloads and deserialises cleaned stream. Does NOT write to PhysiologyMeasurement or mutate AthletePhysiology. |
| 7 | HR deflection algorithm | ✅ | `_hr_deflection()` segments into intensity bins, computes mean HR/intensity per bin, fits linear regression, checks R² ≥ 0.80 and ≥3 intensity steps. Produces LT1_HR and LT2_HR observations with source TRAINING_HR_DEFLECTION and weight 1.0. Confidence weight derived from R². Skips bins with >80% null HR. |
| 8 | RR inflection algorithm | ✅ | `_rr_inflection()` extracts RR series, computes RMSSD in 60s rolling windows, aligns with intensity, checks ≥8 min per intensity level (480s). Produces LT1_HR and LT2_HR observations with source TRAINING_RR_INFLECTION and weight 2.5. Returns null for LT2 when ambiguous. |
| 9 | Power-to-HR ratio algorithm | ✅ | `_power_hr_ratio()` computes power/HR ratio, segments into power bins, detects sustained decline, estimates CP from breakpoint. Produces CP observation with source TRAINING_POWER_HR_RATIO and weight 1.5. Only runs when power data available. |
| 10 | Signal selection logic | ✅ | Signal selection in `detect()` correctly routes: if has_rr_intervals and channel available → RR inflection; if has_hr → HR deflection + (if has_power → power-to-HR ratio). RR inflection runs alongside HR deflection (both may run). Matches plan pseudocode. |
| 11 | LT1 passive inference methods | ✅ | Three methods implemented: `_natural_training_analysis()` (cross-session, ≥3 easy runs, ±5 bpm consistency, weight 0.5, skips silently when PlannedSessionRepository is None), `_hr_drift()` (per-session, ≥20 min steady-state, weight 1.0), `_hr_recovery()` (per-session, hard effort + ≥2 min recovery, weight 0.5). All produce LT1_HR observations with source TRAINING_HR_DEFLECTION. Run as supplementary analysis after per-session algorithms. |
| 12 | Test files and test manifest | — | Step 12 is [OWNER: Test Architect] — explicitly excluded from Coder Scope. Not a coder responsibility. |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: Threshold detection only runs for `calibration_eligible = true` | ✅ | | Enforced in `detect()` at line ~355: `if not activity.calibration_eligible: return []`. Correct layer (service). |
| Invariant: Easy runs do NOT provide threshold detection evidence | ✅ | | The algorithms require ≥3 intensity steps (HR deflection) or ≥8 min per intensity level (RR inflection). Easy runs would not meet these thresholds. Natural training analysis explicitly queries easy runs separately with lower weight (0.5). |
| Invariant: `PhysiologyMeasurement` is append-only | ✅ | | Model has no `updated_at` column. Repository exposes only `insert` and read methods — no update/delete. Enforced at repository layer. |
| Invariant: Per-metric evidence accumulation | ✅ | | Each `ThresholdObservation` carries a specific `parameter` (LT1_HR, LT2_HR, CP). The service does not mix parameters — each algorithm produces observations for specific parameters only. |
| Invariant: Evidence weight thresholds (4.0/8.0) | — | | These thresholds are for `PhysiologyUpdateService` (Plan P2), not this plan. The `ThresholdObservation.weight` field carries the source-specific weight correctly. |
| Invariant: `training_rr_inflection` weight 2.5 vs 1.0 | ✅ | | `WEIGHT_RR_INFLECTION = 2.5`, `WEIGHT_HR_DEFLECTION = 1.0`. Correct values applied in `_rr_inflection()` and `_hr_deflection()` respectively. |
| Invariant: `training_power_hr_ratio` contributes to CP | ✅ | | `_power_hr_ratio()` produces observation with `parameter=PhysiologyParameter.CP` and `source=TRAINING_POWER_HR_RATIO`. |
| Invariant: `measurement_date` = `activity.activity_date` | ✅ | | Plan Notes section now explicitly constrains this. All six observation-producing methods (`_hr_deflection`, `_rr_inflection`, `_power_hr_ratio`, `_natural_training_analysis`, `_hr_drift`, `_hr_recovery`) set `measurement_date=activity.activity_date`. |
| Event Contracts: This plan does not produce or consume events | ✅ | | No events fired in the service. Confirmed — the service only produces `ThresholdObservation` data structures. |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `ThresholdDetectionError` exception class | A `ThresholdDetectionError` base exception class was added to the service module. The plan does not mention this exception class. | Acceptable | Routine implementation detail — the service needs to signal deserialisation failures so the worker can retry. No action needed. |
| `get_recent_activities_for_athlete` method on `ActivityRepository` | The plan's Notes section says "add a `get_recent_activities_for_athlete(athlete_id, sport_type, limit)` method" to `ActivityRepository`. This was implemented with the correct `calibration_eligible = true` filter. | Acceptable | Explicitly requested in the plan's Implementation Clarifications section. No action needed. |
| Algorithm version string constants | Module-level constants for algorithm version strings and threshold constants. | Acceptable | Routine implementation detail — the plan specifies algorithm version strings in the pseudocode. No action needed. |
| `_parse_cleaned_stream` helper function | The plan says "Extract a shared `parse_cleaned_stream(raw_bytes) -> CleanedStream` helper if `SignalCleaningService` already has deserialisation logic; otherwise implement it in the threshold detection service." The coder implemented it inline in the threshold detection service. | Acceptable | The plan explicitly allows this fallback. No action needed. |
| `alembic/env.py` `include_object` filter | An `include_object` function was added to `alembic/env.py` to exclude `procrastinate_*` tables, indexes, and types from autogenerate. This was not in the plan's scope. | Acceptable | This is the root-cause fix for the CRITICAL migration artifact found in the previous validation. It prevents future migrations from generating phantom drop/create operations for procrastinate-managed objects. No action needed. |

---

## Stack-Truth

### CRITICAL
- None.

### MAJOR
- None.

### MINOR
- **Stale dynamic state file**: `docs/implementation/implemented-state.md` — The file still references the old migration `862601a038c6_phase_2_3_p1_physics_measurement.py` in both the "Files Added" list and the "Migrations" section. The actual migration file is now `8413e6547a40_phase_2_3_p1_physiology_measurement.py`. The "Current DB Revision" is still listed as `84d65f756e09` (the parent of the new migration). The dynamic state file should be regenerated to reflect the current commit. This does not affect the implementation itself — only the state tracking document.

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 8 of 8 listed in scope |
| Release alignment checked | yes |
| Deviation scan complete | yes |
| Dynamic context available | yes (but stale — see MINOR finding) |

All scope files were loaded and verified. The dynamic state file (`implemented-state.md`) was available but contains stale migration references (the old migration ID and filename). Release alignment was checked — the plan belongs to Phase 2.3 (Threshold Detection & Physiology Update) and does not exceed the sub-phase scope. Deviation scan was complete, including verification of service registration, migration content, `alembic/env.py` filter, and dependency wiring.

---

## Routing

| Finding | Route To |
|---------|----------|
| MINOR: Stale `implemented-state.md` references old migration | p-devops + this report — regenerate dynamic state file to reflect current commit |
| No other findings | — |
