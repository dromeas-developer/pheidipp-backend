# Test Pack — Phase-2.1-P2 Validation Remediation

**Plan:** `docs/implementation/phase-2/phase-2-1-p2-validation-remediation.md`
**Generated:** 2026-07-02
**Test execution group:** feature (existing `phase_2_1_feature`)
**Tests added to:** `tests/unit/test_activity_ingestion_service.py`

---

## Overview

Phase-2.1-P2 remediates two coder-actionable findings from the Phase-2.1-P1 validation report:

1. **`gps_loss` quality flag** — replaces the coverage-ratio heuristic with continuous-gap detection (>30 s threshold)
2. **`structural_risk_flag` lookup** — replaces raw `text()` SQL with `AthleteProfileRepository.get_by_athlete_id()`

No new execution groups are required. Both fixes live in `ActivityIngestionService` and are tested via `tests/unit/test_activity_ingestion_service.py`, already a member of `phase_2_1_feature`.

---

## What Was Added

### `tests/unit/test_activity_ingestion_service.py`

**Import added:**
```python
from app.services.fit_parser_service import GpsRecord, ParsedFitData
```
(`GpsRecord` was added to the existing `ParsedFitData` import.)

**New test class: `TestComputeQualityFlagsGpsLoss`** — 9 synchronous tests covering the `gps_loss` continuous-gap detection in `_compute_quality_flags`.

**New test class: `TestReadStructuralRiskFlag`** — 4 async tests covering the repository-backed `_read_structural_risk_flag`.

---

## Test Case Inventory

### `TestComputeQualityFlagsGpsLoss` (9 tests)

| Test | Scenario | Expected `gps_loss` |
|------|----------|---------------------|
| `test_gps_loss_false_when_has_gps_is_false` | `has_gps=False`, records exist | `False` |
| `test_gps_loss_true_when_has_gps_true_but_no_records` | `has_gps=True`, `gps_records=[]` | `True` |
| `test_gps_loss_false_when_single_gps_record` | One GPS record only | `False` |
| `test_gps_loss_false_when_all_gaps_are_under_30_seconds` | 5 records, largest gap = 9 s | `False` |
| `test_gps_loss_false_when_largest_gap_is_exactly_30_seconds` | 2 records, gap = exactly 30 s | `False` (boundary: > 30, not ≥ 30) |
| `test_gps_loss_true_when_single_gap_exceeds_30_seconds` | 2 records, gap = 31 s | `True` |
| `test_gps_loss_true_when_any_single_gap_exceeds_30_seconds` | 5 records, one gap = 31 s | `True` |
| `test_gps_loss_false_ignores_negative_deltas` | Out-of-order timestamps (delta < 0) ignored | `False` |
| `test_gps_spike_count_is_preserved` | GPS speed spikes computed independently | `False` (gps_spike_count = 2) |

### `TestReadStructuralRiskFlag` (4 async tests)

| Test | Scenario | Expected return |
|------|----------|-----------------|
| `test_returns_true_when_profile_has_structural_risk_flag_true` | Profile exists, flag = `True` | `True` |
| `test_returns_false_when_profile_has_structural_risk_flag_false` | Profile exists, flag = `False` | `False` |
| `test_returns_false_when_profile_exists_but_flag_is_none` | Profile exists, flag = `None` | `False` |
| `test_returns_false_when_profile_does_not_exist` | No profile for athlete | `False` |

---

## Coverage Against Plan Testing Requirements

| Plan Testing Requirement | Test(s) | Status |
|-------------------------|---------|--------|
| GPS stream with single >30s gap → `gps_loss=True` | `test_gps_loss_true_when_single_gap_exceeds_30_seconds` | ✅ Covered |
| GPS stream with largest gap ≤30s → `gps_loss=False` | `test_gps_loss_false_when_largest_gap_is_exactly_30_seconds`, `test_gps_loss_false_when_all_gaps_are_under_30_seconds` | ✅ Covered |
| GPS stream with several sub-30s gaps → `gps_loss=False` | `test_gps_loss_false_when_all_gaps_are_under_30_seconds` | ✅ Covered |
| `has_gps=true` + empty `gps_records` → `gps_loss=True` | `test_gps_loss_true_when_has_gps_true_but_no_records` | ✅ Covered |
| `has_gps=false` → `gps_loss=False` | `test_gps_loss_false_when_has_gps_is_false` | ✅ Covered |
| `gps_spike_count` unchanged by fix | `test_gps_spike_count_is_preserved` | ✅ Covered |
| Profile with `structural_risk_flag=True` → returns `True` | `test_returns_true_when_profile_has_structural_risk_flag_true` | ✅ Covered |
| No profile → returns `False` (fallback preserved) | `test_returns_false_when_profile_does_not_exist` | ✅ Covered |
| Profile with `flag=False` → returns `False` | `test_returns_false_when_profile_has_structural_risk_flag_false` | ✅ Covered |
| Profile with `flag=None` → returns `False` | `test_returns_false_when_profile_exists_but_flag_is_none` | ✅ Covered |

---

## Self-Check

Collection-only verification (no execution):

```
$ python -m pytest --collect-only tests/unit/test_activity_ingestion_service.py
========================= 31 tests collected =========================
```

All 31 tests (22 pre-existing + 9 new `TestComputeQualityFlagsGpsLoss` + 4 new async `TestReadStructuralRiskFlag`) are discoverable. No import errors, no fixture-not-found errors.

---

## Manifest Updates

- `tests/test-manifest/phase-2-1.yaml`: `last_reviewed_at` updated; history entry appended for Phase-2.1-P2
- `tests/test-manifest/index.yaml`: no changes — `test_activity_ingestion_service.py` already listed under `selection.feature` and `execution_groups.phase_2_1_feature`

---

## Out of Scope (Architecture Gaps, Not Test Gaps)

| Finding | Route To | Why Not Covered Here |
|---------|----------|----------------------|
| MAJOR: Sport-type filtering for calibration eligibility | Architecture Author | No `sport` field on `Activity`; detection mechanism undefined |
| MINOR: GAP computation for structural load | Phase 2.6 (explicit deferral in sub-phase doc) | Plan scope excludes this |

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-07-02 | p-test-architect | Initial generation: `TestComputeQualityFlagsGpsLoss` (9) + `TestReadStructuralRiskFlag` (4) added to `test_activity_ingestion_service.py`. Collection-only self-check passed. |