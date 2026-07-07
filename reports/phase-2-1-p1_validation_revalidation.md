# Validation Report — Phase-2.1-P1 (Revalidation after Phase-2.1-P2 Remediation)
Date: 2026-07-02
Plan: docs/implementation/phase-2/phase-2-1-p1-fit-ingestion-expansion.md
Remediation: docs/implementation/phase-2/phase-2-1-p2-validation-remediation.md

## Result: PASS WITH MINORS

This is a revalidation of the Phase-2.1-P1 implementation after the two
coder-actionable findings from the original report
(`reports/phase-2-1-p1_validation.md`) were remediated by Phase-2.1-P2.

---

## Remediation Verification

### Step 1 — `gps_loss` continuous-gap detection (activity_ingestion_service.py)
**Status: ✅ REMEDIATED**

The original MINOR finding flagged `_compute_quality_flags` for using a
coverage-ratio heuristic (`actual_gps / expected_gps < 0.95`) instead of
the continuous-gap detection specified in Phase-2.1-P1 Coder Handoff
Note #2 ("only flag when position/altitude data is missing for > 30
continuous seconds during moving time").

The implementation now scans consecutive GPS record timestamps and sets
`gps_loss = true` if and only if any single continuous gap exceeds
30 seconds:

- `has_gps = false` → `gps_loss = False` (no GPS to lose) ✅
- `has_gps = true` but empty `gps_records` → `gps_loss = True` (claimed,
  no data) ✅
- Single or no GPS record → `gps_loss = False` (no gap to measure) ✅
- Largest forward gap exactly 30s → `gps_loss = False` (boundary: `> 30`,
  not `>= 30`) ✅
- Single continuous gap > 30s → `gps_loss = True` ✅
- Out-of-order timestamps (negative delta) ignored — `previous_ts`
  advances unconditionally so the next delta is measured against the
  most recent point in time ✅ (matches P2 Architecture Interpretation #2)
- `gps_spike_count` computation untouched — still flags `speed > 25 m/s` ✅
- `quality_flags` JSONB shape unchanged (`gps_loss: boolean`) ✅

Targeted tests added (`TestComputeQualityFlagsGpsLoss` in
`tests/unit/test_activity_ingestion_service.py`) cover all five plan
scenarios plus the boundary case. ✅

### Step 2 — Repository-backed `structural_risk_flag` (activity_ingestion_service.py)
**Status: ✅ REMEDIATED**

The original MINOR finding flagged `_read_structural_risk_flag` for using
raw `text("SELECT structural_risk_flag ...")` SQL instead of the
repository pattern used elsewhere in the ingestion service.

The implementation now:
- Calls `self.athlete_profiles.get_by_athlete_id(athlete_id)` ✅
- Returns `False` when profile missing ✅
- Returns `False` when `profile.structural_risk_flag is None` ✅
- Returns `bool(profile.structural_risk_flag)` otherwise ✅

`AthleteProfileRepository` is wired as an `Optional` constructor
dependency (defaulted to `AthleteProfileRepository(session)` when not
injected), matching the existing injection pattern for
`ActivityRepository`, `CalibrationEligibilityService`,
`ObjectStorageClient`, `EventPublisher`. ✅ — Verified at lines 91, 201
and 206 (import, constructor parameter, default instantation).

The `from sqlalchemy import text` import was removed from
`_read_structural_risk_flag` ✅ — the surviving three `text()` imports
(lines 639, 676, 727) live only in `_read_profile_date_of_birth`,
`_read_athlete_preferences`, and `_read_athlete_physiology`, which the
P2 plan explicitly leaves out-of-scope ("Deferred Items Explicitly Not
In This Plan"). No scope violation.

Targeted tests added (`TestReadStructuralRiskFlag` in
`tests/unit/test_activity_ingestion_service.py`) cover true / false /
None flag and missing profile. ✅

---

## Layer 1: Plan Conformance (Phase-2.1-P1)

All 15 coder-owned steps originally marked conformant remain conformant
post-remediation. No regression introduced by P2 edits.

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | Add `has_gps` field to Activity model | ✅ | `app/models/activity.py` lines 140-143 — `nullable=False`, `default=False`, `server_default="false"` |
| 2 | Generate Alembic migration | ✅ | `01432b6b91fe_phase_2_1_has_gps_column.py` adds column + filtered calibration index |
| 3 | Extend `ParsedFitData` dataclass | ✅ | `fit_parser_service.py` lines 104-122 — `gps_records`, `rr_records`, `total_distance_m`, `total_ascent_m`, `has_gps`, `moving_duration_seconds` all present |
| 4 | Expand `FitParserService._parse_sync` | ✅ | GPS records, RR time-series, session totals extracted lines 244-329; GPS spike detection at 25 m/s |
| 5 | Extend `LoadComputationInputs` | ✅ | `load_computation_service.py` lines 105-117 — `data_tier`, `total_distance_m`, `total_ascent_m`, `recent_structural_load_72h`, `structural_risk_flag`, `cp_estimate` |
| 6 | Power-based aerobic load computation | ✅ | Lines 253-273 — fourth-power formula for Tier 1-2 + population CP fallback |
| 7 | Neuromuscular load computation | ✅ | Lines 278-327 — variability index + VO2max time for Tier 1-4, null for 5-6 |
| 8 | Structural load computation | ✅ | Lines 330-359 — distance + gradient + density penalty (cap 15) |
| 9 | Return three-dimension `LoadScores` | ✅ | `compute_aerobic_load` returns `LoadScores` with all three fields |
| 10 | Activate five-rule calibration gate | ✅ | `calibration_eligibility_service.py` — no hard-off; gate evaluates all five rules |
| 11 | Update ingestion pipeline | ✅ | Lines 430-606 — `AthletePreferences` fetched, `infer_data_tier` applied, structural 72h load queried, `has_gps` populated, `hr_dropout_pct` computed |
| 12 | Fire `activity_calibration_eligible` event | ✅ | Lines 590-606 — fires after `activity_ingested`, gated on `eligible AND scores.aerobic_load is not None` |
| 13 | Add `get_recent_structural_load` to repository | ✅ | `activity_repository.py` lines 167-192 — sums `structural_load` for calibration-eligible activities in window |
| 14 | Add `has_gps` to API schemas | ✅ | `app/schemas/activity.py` line 67; `ActivityListResponse` reuses `ActivityResponse` |
| 15 | Update `__init__.py` exports | ✅ | `GpsRecord` exported in `app/services/__init__.py`; schemas unchanged in shape |

---

## Layer 2: Contract Conformance (Phase-2.1-P1)

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: `fit_file_key` REQUIRED for non-manual sources | ✅ | `stage_upload` writes to object storage before Activity insert; failure → no Activity row |
| Invariant: No averaged fields on Activity | ✅ | No `avg_hr`/`avg_pace`/`avg_power`/`avg_cadence`/`lap_data` columns |
| Invariant: Load scores null at creation, populated sync in ingestion task | ✅ | Staged row carries null scores; `_run_ingestion_pipeline` computes all scores before returning |
| Invariant: `calibration_eligible` set by service only | ✅ | Only `CalibrationEligibilityService.evaluate()` + ingestion-side Tier-5/6 override set this flag; never assigned at API layer |
| Invariant: Manual entry always `calibration_eligible=false` + null loads + null `fit_file_key` | ✅ | First rule in `_evaluate_full_rules` returns False for `manual_entry` |
| Invariant: Deduplication constraint | ✅ | Partial unique index `uq_activities_athlete_external_source` on Activity model |
| Invariant: Tier 5-6 never calibration eligible | ✅ | Enforced at ingestion layer (`if eligible and data_tier in (TIER_5, TIER_6): eligible = False`); service-layer guard preserves this without embedding tier knowledge in `CalibrationEligibilityService` |
| Invariant: Tier 6 has null load scores | ✅ | Tier 5-6 fall-through returns null aerobic / neuromuscular / structural — but ingestion only reaches compute when HR present, and Tier 6 (manual entry absence of prefs) maps to default Tier 4 in `LoadComputationInputs` dataclass default |
| Invariant: no GPS → Tier 6 structural load purposes | ✅ | `_compute_structural_load` returns `None` when `has_gps = false` |
| Invariant: GAP always used as mechanical work proxy | ⚠️ MINOR | Structural load uses raw distance + elevation, not GAP. P2 plan ratifies this as documented Phase-2.1 behaviour; GAP-based work is explicitly deferred to Phase 2.6. No remediation required. Remains MINOR for architecture tracking. |
| Invariant: Non-running activities excluded from twin calibration | ⚠️ PLAN GAP (MAJOR) | No sport-type filtering implemented. The P2 plan explicitly escalated this to the Architecture Author (see "Architecture Gap Escalation" section below) and did not implement it under this phase. The mechanism is undefined in the architecture: no `sport` field on `Activity`, no FIT-sport extraction contract, no gate entry. Coder must not add it without architecture direction. |
| Event: `activity_calibration_eligible` payload | ✅ | `{activity_id, aerobic_load, neuromuscular_load, structural_load}` matches spec |
| Event: `activity_calibration_eligible` fires after `activity_ingested` | ✅ | Outbox insertion order preserved; `activity_ingested` published first lines 575-589 |
| Event: Fires only when `calibration_eligible=true` AND load scores non-null | ✅ | Guard at line 594 checks `eligible and scores.aerobic_load is not None` |
| PLAN GAP: gps_loss continuous-gap rule | ✅ REMEDIATED | Was MINOR; now matches P1 Handoff Note #2 continuous-gap semantics |
| PLAN GAP: structural_risk_flag repository path | ✅ REMEDIATED | Was MINOR; now uses `AthleteProfileRepository.get_by_athlete_id` |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `hr_dropout_pct` / `sensor_malfunction` / `gps_spike_count` quality flags | Computed in `_compute_quality_flags` | Acceptable | Implementation detail — quality flag computation is within coder authority |
| Population CP estimate (200W) | Fallback in `_estimate_cp_from_population` | ✅ | Per Phase-2.1-P1 Coder Handoff Note #1 (bootstrap prior to Phase 2.3) |
| `_infer_data_tier` helper on ingestion service | Wraps `infer_data_tier()` for missing-preferences fallback | Acceptable | Routine helper |
| `_resolve_max_hr_estimate` / `_resolve_cp_estimate` helpers | Population fallback encapsulation | Acceptable | Routine helper |
| `ix_activities_athlete_calibration_eligible` index | Filtered index on `(athlete_id, calibration_eligible)` | DEVIATION (Acceptable) | Plan Step 1 said "Add index on `(athlete_id, activity_date)` filtered by `calibration_eligible = true`". Implementation adds a different filtered index (column `calibration_eligible` instead of pair `activity_date` composite filtered). Functionally serves the recent-load query; the exact composite-filter spec was not satisfied, but the existing unfiltered `ix_activities_athlete_date` already covers `(athlete_id, activity_date)`. No blocking concern. |
| `TestComputeQualityFlagsGpsLoss` + `TestReadStructuralRiskFlag` | New test classes for the two P2 fixes | ✅ | Per Phase-2.1-P2 Step 3 (Test Architect) |
| Out-of-scope raw SQL imports in `_read_profile_date_of_birth` / `_read_athlete_preferences` / `_read_athlete_physiology` | Still use `text()` | Acceptable (deferred) | P2 plan explicit "Deferred Items"; flagged in original report only for `_read_structural_risk_flag`. These three are NOT regressions and may be unified in a future consistency pass. |

No new files outside plan scope were created by P2. No new entity, event,
or migration was introduced. The remediation strictly modified
`app/services/activity_ingestion_service.py` (constructor + two methods)
and added tests in `tests/unit/test_activity_ingestion_service.py`.

---

## Stack-Truth

### CRITICAL
- None found

### MAJOR
- **Architecture gap — sport type filtering for calibration eligibility**
  (`app/services/calibration_eligibility_service.py`,
  `app/services/activity_ingestion_service.py`): The architecture invariant
  "Non-running activities are excluded from twin calibration"
  (`principles` invariant 8) remains unenforced. Until the Architecture
  Author defines the sport-detection mechanism (where `sport` lives, how it
  is populated, where in the pipeline the exclusion is enforced), a
  cycling or swimming FIT file with HR data that meets the five-rule gate
  will set `calibration_eligible = true`, fire
  `activity_calibration_eligible`, and feed `TwinRecalibrationService` —
  a direct invariant violation. The P2 plan correctly escalates this and
  forbids the coder from adding sport handling. Routed to p-architect —
  NOT a regression, NOT remediated by design.

### MINOR
- **GAP not used for mechanical work**
  (`app/services/load_computation_service.py` lines 330-359): structural
  load uses raw `distance_km` + `elevation_gain_m` with
  `surface_modifier = 1.0`, not grade-adjusted pace. The P2 plan
  ratifies this as documented Phase-2.1 behaviour (GAP-based work deferred
  to Phase 2.6). Remains MINOR for architecture tracking.
- **Composite-filter index spec mismatch**
  (`app/models/activity.py` Step 1): the filtered-index spec on
  `(athlete_id, activity_date) WHERE calibration_eligible = true` was
  implemented as `(athlete_id, calibration_eligible) WHERE calibration_eligible = true`.
  No functional regression — the existing unfiltered
  `ix_activities_athlete_date` already covers the date-ordered path, and
  the new index supports the calibration-lookup path.
- **Row-by-row manual hydration of `AthletePreferences` / `AthletePhysiology`**
  (`app/services/activity_ingestion_service.py`
  `_read_athlete_preferences`, `_read_athlete_physiology`): raw `text()`
  SELECT + dict reconstruction rather than repository lookup. Out-of-scope
  per P2 deferral. The remediation established the repository-backed
  pattern for `_read_structural_risk_flag`; mirror work for these two
  helpers is a future consistency item.

### Acceptable Deviations (no action needed)
- `GpsRecord` / `_BytesReader` dataclasses in `fit_parser_service.py`
- Population CP bootstrap value of 200 W (Handoff Note #1)
- Quality-flag computation details (HR dropout, sensor malfunction)

---

## Deviation Scan

No speculative secondary searches were performed beyond verifying:
- `AthleteProfileRepository` injection wiring (lines 91, 201, 206) ✅
- `GpsRecord` export in `app/services/__init__.py` line 40 ✅
- `ActivityResponse.has_gps` field at `app/schemas/activity.py` line 67 ✅
- `infer_data_tier` is imported and wired on ingestion ✅
- Tier-5/6 exclusion lives at the ingestion boundary, not the eligibility
  service (consistent with `CalibrationEligibilityService` docstring) ✅
- Remediation tests added and named per P2 Step 3 spec ✅
- No new files outside P2's stated scope (modified file set matches
  `implemented-state.md` change set + the remediation edits) ✅

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes — Phase-2.1-P1 and Phase-2.1-P2 both embed invariants and event contracts |
| Implementation files retrieved | 10 of 10 listed in scope (Plan P1) + 1 dependent repo + 2 test files (Plan P2 Step 3) |
| Release alignment checked | yes — phase-2.1-fit-ingestion-pipeline-expansion belongs to Phase 2; scope does not exceed the phase. No future-phase capabilities (threshold detection, signal cleaning, power profile) introduced. |
| Deviation scan complete | yes |
| Dynamic context available | yes — `docs/implementation/implemented-state.md` commit `0f75c9e` (the head includes the P2 remediation edits; change set lists `app/services/activity_ingestion_service.py` as modified) |
| Remediation verification complete | yes — both P2 Step 1 (gps_loss) and P2 Step 2 (structural_risk_flag) applied correctly to the scoped code; both passing their targeted tests |

Confidence is HIGH because all scope files loaded, dynamic state matched
the remediation change set, contracts are embedded, and the two
remediation fixes were directly verified against their plan pseudocode.

---

## Routing

| Finding | Route To |
|---------|----------|
| MAJOR (sport type filtering — architecture gap) | p-architect + this report — Architecture Author must define the non-running detection mechanism. Per P2 plan's Architecture Gap Escalation: the gap is NOT waiting on Phase 2.2 (Phase 2.2 release-plan has no sport-type extraction). Decision needed on whether this blocks Phase 2.3 threshold detection. |
| MINOR (GAP usage deferred to 2.6) | p-architect + this report — tracked; P2 ratifies as Phase-2.6 scope. No coder action. |
| MINOR (composite-filter index spec) | p-coder + this report — optional index alignment if the filtered `activity_date` composite is desired. |
| MINOR (out-of-scope `text()` SQL helpers) | p-coder + this report — future consistency pass to mirror the `_read_structural_risk_flag` repository pattern across `_read_profile_date_of_birth`, `_read_athlete_preferences`, `_read_athlete_physiology`. Not a P2 regression. |
| Remediated MINOR (gps_loss) | p-devops — merge the P2 fix; tests pass. |
| Remediated MINOR (structural_risk_flag SQL) | p-devops — merge the P2 fix; tests pass. |
| No new blocking findings | p-devops |

---

## Summary

The Phase-2.1-P2 remediation was applied correctly and exactly to its
scoped scope:

- **Both coder-actionable findings from the original Phase-2.1-P1 report
  are resolved:**
  - `gps_loss` now uses continuous-gap detection (> 30s) per the plan's
    Handoff Note #2 and the P2 pseudocode.
  - `_read_structural_risk_flag` now routes through
    `AthleteProfileRepository.get_by_athlete_id()` with the
    missing-profile `False` fallback preserved.

- **No regressions introduced.** All 15 originally-conformant P1 steps
  remain conformant. Tier-5/6 exclusion, event ordering, payload shape,
  deduplication, and `has_gps` propagation are unchanged.

- **Targeted tests added** for both fixes, matching the P2 Testing
  Requirements scenario list verbatim (including the boundary case where
  a 30s gap does NOT trip the flag).

- **The two non-actionable findings from the original report were
  correctly NOT touched by P2:**
  - The MAJOR sport-type-filtering architecture gap is escalated to the
    Architecture Author (not a coder item) and remains OPEN.
  - The MINOR GAP-usage finding is ratified as deferred to Phase 2.6.

- **One residual out-of-scope item**: the three other raw-`text()` SQL
  helpers in `ActivityIngestionService` (`_read_profile_date_of_birth`,
  `_read_athlete_preferences`, `_read_athlete_physiology`) remain as
  documented deferred items — not a P2 regression.

The Phase-2.1-P1 implementation, with the Phase-2.1-P2 remediation
applied, is **PASS WITH MINORS**. The remaining MAJOR finding is an
architecture gap routed to the Architecture Author and is explicitly out
of coder scope under any implementation plan until the architecture
defines the sport-filtering mechanism.
