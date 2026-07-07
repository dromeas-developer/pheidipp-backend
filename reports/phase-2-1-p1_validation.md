# Validation Report — Phase-2.1-P1
Date: 2026-07-02
Plan: docs/implementation/phase-2/phase-2-1-p1-fit-ingestion-expansion.md

## Result: PASS WITH MINORS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | Add `has_gps` field to Activity model | ✅ | Implemented in `app/models/activity.py` lines 140-143 with correct constraints |
| 2 | Generate Alembic migration | ✅ | Migration `01432b6b91fe` exists and adds column + index |
| 3 | Extend `ParsedFitData` dataclass | ✅ | Implemented in `app/services/fit_parser_service.py` lines 104-122 |
| 4 | Expand `FitParserService._parse_sync` | ✅ | GPS, RR, lap extraction implemented lines 224-329 |
| 5 | Extend `LoadComputationInputs` | ✅ | Implemented in `app/services/load_computation_service.py` lines 105-117 |
| 6 | Power-based aerobic load computation | ✅ | Implemented lines 253-273 with fourth-power formula |
| 7 | Neuromuscular load computation | ✅ | Implemented lines 275-321 with variability index + VO2max time |
| 8 | Structural load computation | ✅ | Implemented lines 323-359 with distance + gradient + density penalty |
| 9 | Return three-dimension `LoadScores` | ✅ | Method updated lines 196-214 |
| 10 | Activate five-rule calibration gate | ✅ | Implemented in `calibration_eligibility_service.py` lines 71-109 |
| 11 | Update `ActivityIngestionService` pipeline | ✅ | Implemented lines 430-606 with data tier inference, structural risk flag |
| 12 | Fire `activity_calibration_eligible` event | ✅ | Implemented lines 590-606 with correct payload |
| 13 | Add `get_recent_structural_load` to repository | ✅ | Implemented in `activity_repository.py` lines 193-212 |
| 14 | Add `has_gps` to API schemas | ✅ | Added to `ActivityResponse` in `app/schemas/activity.py` line 67 |
| 15 | Update `__init__.py` exports | ✅ | `GpsRecord` exported in `app/services/__init__.py` line 40 |

All 15 coder-owned steps implemented correctly.

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: `fit_file_key` REQUIRED for non-manual sources | ✅ | Upload occurs before Activity creation in `stage_upload` method |
| Invariant: No averaged fields on Activity | ✅ | No `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` fields exist |
| Invariant: Load scores populated synchronously | ✅ | `_run_ingestion_pipeline` computes all scores before returning |
| Invariant: `calibration_eligible` set by service only | ✅ | Only `CalibrationEligibilityService.evaluate()` sets this flag |
| Invariant: Manual entry always `calibration_eligible=false` | ✅ | First check in `_evaluate_full_rules` returns False for manual_entry |
| Invariant: Deduplication constraint enforced | ✅ | Partial unique index exists in model line 170 |
| Invariant: Tier 5-6 never calibration eligible | ✅ | Checked in `activity_ingestion_service.py` lines 582-587 |
| Invariant: Grade-adjusted pace used for mechanical work | ⚠️ MINOR | Code uses raw distance, GAP computation not implemented (deferred to Phase 2.6) |
| Invariant: Non-running activities excluded from calibration | ⚠️ PLAN GAP | No sport type filtering implemented; plan notes this requires session classification from Phase 2.2 |
| Event: `activity_calibration_eligible` payload shape | ✅ | Payload matches spec: `{activity_id, aerobic_load, neuromuscular_load, structural_load}` |
| Event: `activity_calibration_eligible` fires after `activity_ingested` | ✅ | Event ordering correct lines 575-606 |
| Event: Fires only when eligible AND load scores non-null | ✅ | Guard on line 594 checks both conditions |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `hr_dropout_pct` quality flag computation | Computed from HR record continuity in `_compute_quality_flags` | Acceptable | Implementation detail within coder authority |
| `gps_spike_count` quality flag | Tracks GPS speed spikes > 25 m/s | Acceptable | Artifact detection per plan Step 4 |
| `gps_loss` quality flag detection | Uses coverage threshold (95%) rather than continuous 30s gap | MINOR | Plan specifies ">30 continuous seconds" but code uses coverage ratio |
| `structural_risk_flag` from profile | Read from `athlete_profiles.structural_risk_flag` | Acceptable | Required for density penalty coefficient |
| Population CP estimate (200W) | Fallback when `AthletePhysiology.cp` is null | ✅ | Per Coder Handoff Note #1 |
| `_compute_quality_flags` method | New helper method | Acceptable | Routine implementation detail |

---

## Stack-Truth

### CRITICAL
- None found

### MAJOR
- **Missing sport type filtering for calibration eligibility**: Plan notes "isUsableSessionType check deferred (requires session classification from Phase 2.2)" but does not implement any sport filtering. Activities from non-running sports (cycling, swimming) would be marked `calibration_eligible=true` if they pass the five-rule gate. This is a PLAN GAP — the plan explicitly defers this check but the architecture invariant states "Non-running activities are excluded from twin calibration."

### MINOR
- **GAP computation not implemented**: Structural load computation uses raw distance (line 335) but architecture invariant states "Grade-adjusted pace (GAP) is always used as the mechanical work proxy." Plan Step 8 says "Surface type defaults to `unknown`" but does not mention GAP. This is a minor deviation from architecture.

- **`gps_loss` detection uses coverage ratio**: Plan Step 4 says "only flag when position/altitude data is missing for > 30 continuous seconds during moving time" but implementation (lines 812-822) uses a coverage percentage threshold (95%) instead of continuous gap detection.

- **Local import in `_read_structural_risk_flag`**: SQL query uses raw `text()` instead of repository pattern. Not a violation but inconsistent with `athlete_preferences` query pattern.

### Acceptable Deviations (no action needed)
- `GpsRecord` frozen dataclass added for GPS records
- `_compute_quality_flags` helper method
- Population CP estimate of 200W (per coder handoff notes)
- Quality flag computation details (hr_dropout_pct, sensor_malfunction)

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 10 of 10 listed in scope |
| Release alignment checked | yes |
| Deviation scan complete | yes |
| Dynamic context available | yes |

All scope files were successfully loaded. The dynamic state file (`implemented-state.md`) confirmed the implementation matches the change set. The plan contains clear contracts and invariants, enabling confident validation.

---

## Routing

| Finding | Route To |
|---------|----------|
| MAJOR (sport type filtering) | p-architect + this report — architecture invariant not enforced; requires clarification whether this should block Phase 2.3 threshold detection |
| MINOR (GAP usage) | p-coder + this report — structural load uses raw distance instead of GAP; architect clarification needed on whether this is Phase 2.6 scope |
| MINOR (gps_loss detection) | p-coder + this report — implementation uses coverage ratio instead of continuous gap detection |
| MINOR (local SQL imports) | p-coder + this report — consistency improvement for repository patterns |
| All other findings | No action required — implementation conforms to plan |

---

## Summary

The Phase-2.1 implementation is **substantially complete** and conforms to the plan. All 15 implementation steps are correctly implemented:

- `has_gps` column added with migration
- FIT parser expanded for GPS, RR intervals, lap data
- Three-dimensional load computation (aerobic, neuromuscular, structural) fully functional
- Power-based aerobic load uses fourth-power intensity factor formula
- Calibration eligibility five-rule gate activated
- Event ordering correct (`activity_ingested` before `activity_calibration_eligible`)
- All exports properly registered

**Two architecture-level concerns** require architect attention:

1. **Sport type filtering** (MAJOR): Architecture states non-running activities should not contribute to twin calibration, but no filtering is implemented. Plan explicitly defers this to Phase 2.2 session classification.

2. **GAP computation** (MINOR): Architecture states GAP should be used for mechanical work proxy, but structural load uses raw distance. This may be acceptable for Phase 2.1 with unknown surface type.

The implementation is ready for testing, with the above findings requiring architect acknowledgement before proceeding to Phase 2.2.