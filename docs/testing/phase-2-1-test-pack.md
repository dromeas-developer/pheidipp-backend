# Phase 2.1 — FIT Ingestion Pipeline Expansion & Calibration Eligibility

## Test Pack

**Plan:** `docs/release-plan/phase-2/phase-2-1-fit-ingestion-pipeline-expansion.md`
**Sub-Phase Reference:** Phase-2.1
**Generated:** 2026-07-02
**Last Updated:** 2026-07-06
**Status:** Generated — covering Phase-2.1-P1, P2, and P3 — awaiting DevOps execution

---

## Overview

Phase 2.1 expands the FIT ingestion pipeline to process full sensor signals (power, GPS, RR intervals) and evaluates calibration eligibility per the six-rule gate (sport-type as first rule, then five signal-quality rules). This is the foundation for threshold detection and comparable sessions in later phases.

Sub-phases:
- **Phase-2.1-P1**: Core FIT ingestion pipeline expansion (power/GPS/RR extraction, five-rule calibration gate, three-dimensional load computation)
- **Phase-2.1-P2**: Validation remediation (GPS loss continuous-gap detection, AthleteProfileRepository for structural_risk_flag)
- **Phase-2.1-P3**: Sport type filtering (FIT sport extraction, sport-type calibration gate, sport_type_detected event, API response fields)

---

## Exit Gate Criteria (from plan)

| # | Exit Gate Criterion | Test Coverage |
|---|---------------------|---------------|
| 1 | Uploading FIT with power data → `Activity` with `has_power=true`, proper load scores, `calibration_eligible=true` when meets six-rule gate | `TestPowerBasedAerobicLoad`, `TestSignalFlagsPopulation`, `TestCalibrationEligibilityFiveRuleGate` |
| 2 | Uploading FIT without power but with RR intervals → `Activity` with `has_rr_intervals=true` and `calibration_eligible=true` when eligible | `TestCalibrationEligibilityFiveRuleGate`, `TestSignalFlagsPopulation` |
| 3 | Uploading FIT with optical HR only → `has_rr_intervals=false`, `calibration_eligible=true` only if HR deflection-eligible (≥3 intensity steps) | `TestCalibrationEligibilityFiveRuleGate` |
| 4 | FIT file failing six-rule gate → `calibration_eligible=false` and null load scores | `TestCalibrationEligibilityFiveRuleGate`, `TestCalibrationEligibilitySportTypeGate` |
| 5 | `GET /athletes/{id}/activities/{aid}` shows all signal availability flags correctly | `TestSignalAvailabilityFlags` |
| 6 | **P3**: Non-running FIT file → `calibration_eligible=false` regardless of signal quality | `TestCalibrationEligibilitySportTypeGate`, `TestSportTypePipeline` |

---

## What Was Generated

### Phase-2.1-P1 (existing)

**Unit tests:**
- `TestCalibrationEligibilityFiveRuleGate` — 14 tests covering all five rules
- `TestCalibrationEligibilityTier56Override` — Tier 5-6 override at ingestion layer
- `TestPowerBasedAerobicLoad` — 7 tests for power-based load formula
- `TestNeuromuscularLoad` — 5 tests for variability + VO2max time
- `TestStructuralLoad` — 7 tests for base + gradient + density penalty with cap
- `TestAllThreeDimensions` — 3 tests for combined load scores
- `TestSignalFlagsPopulation` — 5 tests for has_power/has_rr_intervals/has_gps

**Integration tests:**
- `TestSignalAvailabilityFlags` — 6 tests for GET endpoint signal flag responses

### Phase-2.1-P2 (existing)

**Unit tests:**
- `TestComputeQualityFlagsGpsLoss` — 10 tests covering:
  - `has_gps=false` → `gps_loss=False` (regardless of records)
  - `has_gps=true` + empty records → `gps_loss=True`
  - Single GPS record → `gps_loss=False`
  - All gaps < 30s → `gps_loss=False`
  - Largest gap = 30s → `gps_loss=False`
  - Any gap > 30s → `gps_loss=True`
  - Negative deltas (out-of-order) ignored, max gap preserved
  - `gps_spike_count` computed independently
- `TestReadStructuralRiskFlag` — 4 tests for repository-backed profile lookup

### Phase-2.1-P3 (newly added)

**Unit tests:**
- `TestFitParserServiceSportType` — 8 tests:
  - Running FIT (sport=1) → `sport_type='running'`, confidence='high'
  - Cycling FIT (sport=2) → `sport_type='cycling'`
  - Swimming FIT (sport=5) → `sport_type='swimming'`
  - Trail-running (sport=1, sub_sport=14) → `sport_type='running'` (sub doesn't override)
  - Generic/missing sport → `sport_type='unknown'`, confidence='unknown'
  - Unrecognized sport (99) → `sport_type='other'`, confidence='low'
  - Indoor-cycling (sport=2, sub_sport=8) → `sport_type='cycling'`
  - `detection_version='v1'` carried in ParsedFitData

- `TestCalibrationEligibilitySportTypeGate` — 8 tests:
  - Running activity passing five rules → `calibration_eligible=true`
  - Cycling, swimming, unknown, strength, yoga_mobility, other → `calibration_eligible=false`
  - Sport check runs **before** all other rules (verify cycling + perfect HR + perfect duration + no quality issues still rejected by sport gate, not five-rule gate)

- `TestSportTypePipeline` — 5 tests:
  - Running activity → `sport_type='running'` set on Activity
  - Cycling activity → `sport_type='cycling'` set on Activity
  - `sport_type_detected` event fires for non-manual-entry sources
  - Unknown sport → `calibration_eligible=false`

**Integration tests:**
- `TestSportTypeResponse` — 5 tests:
  - GET returns `sport_type` and `sport_type_detection_version`
  - Running activity shows correct sport type and calibration_eligible=true
  - Cycling activity shows `sport_type='cycling'` and `calibration_eligible=false`
  - Unknown sport shows `sport_type='unknown'` and `calibration_eligible=false`
  - List endpoint returns sport types for all activities
  - Manual-entry has `sport_type='unknown'` and null `sport_type_detection_version`

---

## Modified Files

| File | Change |
|------|--------|
| `tests/unit/test_calibration_eligibility_service.py` | Added `TestCalibrationEligibilitySportTypeGate` (8 tests); sport-type check as first gate rule |
| `tests/unit/test_fit_parser_service.py` | Added `TestFitParserServiceSportType` (8 tests); FIT sport extraction |
| `tests/unit/test_activity_ingestion_service.py` | Added `TestSportTypePipeline` (5 tests); existing P2 GPS loss and structural_risk_flag tests retained |
| `tests/integration/test_activity_endpoints.py` | Added `TestSportTypeResponse` (5 tests); sport_type and sport_type_detection_version in API |
| `tests/test-manifest/phase-2-1.yaml` | Added P2 features (gps_loss_continuous_gap_detection, structural_risk_flag_repository) and P3 features (sport_type_filtering, sport_type_detection_pipeline, sport_type_detection_event, sport_type_api_response); updated coverage, invariants, execution groups, history |

---

## Coverage Summary

### Routes Covered
- `POST /athletes/{id}/activities/upload` ✓
- `GET /athletes/{id}/activities` ✓
- `GET /athletes/{id}/activities/{aid}` ✓ (signal flags + sport_type)

### Events Covered
- `activity_ingested` ✓
- `activity_calibration_eligible` ✓
- `sport_type_detected` ✓ (P3)

### Invariants Covered
| Invariant | Coverage |
|-----------|----------|
| `calibration_eligible` set by `CalibrationEligibilityService` | ✓ |
| `fit_file_key` always set for source ≠ `manual_entry` | ✓ |
| Load scores null at creation, populated by `LoadComputationService` | ✓ |
| Signal availability flags (`has_power`, `has_rr_intervals`, `has_gps`) | ✓ |
| Tier 5-6 activities never calibration-eligible (at ingestion layer) | ✓ |
| Power-based aerobic load for Tier 1-2 | ✓ |
| Neuromuscular load for Tier 1-4 | ✓ |
| Structural load from GPS data | ✓ |
| **Non-running activities excluded from twin calibration** | ✓ (P3) |
| **Sport-type check runs before all other calibration rules** | ✓ (P3) |
| **sport_type = 'unknown' when detection fails** | ✓ (P3) |
| **GPS loss computed by continuous-gap detection, not coverage ratio** | ✓ (P2) |
| **structural_risk_flag defaults to False when profile missing** | ✓ (P2) |

---

## What Is NOT Covered (Deferred)

| Capability | Deferred To |
|------------|-------------|
| `isUsableSessionType` check in calibration eligibility (session_type from PlannedSession) | Phase 2.2 |
| Signal cleaning (`RawSensorStream` creation) | Phase 2.2 |
| Threshold detection algorithms | Phase 2.3 |
| `ActivityPowerProfile` creation | Phase 2.6 |
| `supra_threshold_joules`, `w_prime_depletion_pct` in coaching observations | Phase 2.6 |
| Auto-sync (intervals.icu, Garmin) | Future phase |
| Intervals.icu API metadata extraction for sport detection | Future phase (auto-sync phase) |
| Manual-upload sport selection UI flow | Future API enhancement |

---

## Self-Check Note

Test collection succeeded with **114 tests** collected across the Phase 2.1 test files:

```
tests/unit/test_fit_parser_service.py         — 30 tests (was 22, +8 P3 sport type)
tests/unit/test_calibration_eligibility_service.py — 24 tests (was 15, +8 P3 sport gate + 1 retained)
tests/unit/test_activity_ingestion_service.py — 30 tests (P2 GPS + P2 structural risk + P3 sport pipeline)
tests/integration/test_activity_endpoints.py   — 30 tests (was 24, +5 P3 sport type response, +1 retained)
```

---

## Execution Groups

| Group | Tests |
|-------|-------|
| `phase_2_1_smoke` | `test_calibration_eligibility_service.py`, `test_load_computation_service.py` |
| `phase_2_1_feature` | All Phase 2.1 unit + integration tests across all sub-phases |

**Note:** PHASE_1_6_HARD_OFF flag was removed from `CalibrationEligibilityService` implementation — the service now evaluates the full six-rule gate (sport-type as first rule, then five signal-quality rules). Tests that previously verified `PHASE_1_6_HARD_OFF is True` have been removed (Phase 1.6 behavior is no longer applicable).

---

## Lessons Learned

### 2026-07-06 — P3 Test Generation
No new DevOps-reported failures from Phase 2.1-P1/P2 execution to incorporate for P3. The existing README lessons on `mock_activity.planned_session_id` and `patch target must match import style` remain applicable.

Key P3 implementation notes:
1. **Mock `MagicMock(value="...")` for enum comparisons**: When testing sport-type values in mocked `ParsedFitData`, using `MagicMock(value="running")` allows `result.sport_type.value == "running"` to work without importing `SportType` into the test file.
2. **Layer boundary — FitParserService tests**: Use `patch.object(service, "_parse_sync", return_value=mock_result)` to isolate sport-type extraction tests from the actual FIT parsing.
3. **Layer boundary — CalibrationEligibilityService tests**: The sport-type gate reads `activity.sport_type` which is set during ingestion. Test by directly setting the attribute on the factory-created Activity.
4. **API response tests**: When using `Activity` model directly in integration tests, include `sport_type="running"` and `sport_type_detection_version="v1"` in the constructor to avoid schema validation errors.

---

## Approval Required

This test pack requires **DevOps execution** before promotion to `regression` group. All tests are currently in `feature` scope (`validation.executable = false`, `validation.passed = false`).