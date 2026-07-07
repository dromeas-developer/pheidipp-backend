# Implementation Plan: Phase-2.1 — Validation Remediation
## Plan ID: Phase-2.1-P2

## Sub-Phase Reference
Sub-Phase ID: Phase-2.1
Sub-Phase Title: FIT Ingestion Pipeline Expansion & Calibration Eligibility

## Objective
Remediate the two coder-actionable findings from the Phase-2.1-P1 validation
report (`reports/phase-2-1-p1_validation.md`) that are direct plan-conformance
deviations inside the existing Phase-2.1 scope. This plan does **not** introduce
new architectural capabilities; it corrects two places where the implemented
behaviour diverges from the original Phase-2.1-P1 plan. The MAJOR sport-type
finding and the MINOR GAP handling finding from the same report are **not**
addressed here — they are routed separately (see Architecture Gap Escalation
below and Coder Handoff Notes).

## Scope
- Replace the `gps_loss` coverage-ratio heuristic in
  `ActivityIngestionService._compute_quality_flags` with the
  continuous-gap detection specified in Phase-2.1-P1 Coder Handoff Note #2:
  flag `gps_loss = true` only when position/altitude data is missing for
  > 30 continuous seconds during moving time.
- Replace the raw `text()` SQL lookup in
  `ActivityIngestionService._read_structural_risk_flag` with a call through
  `AthleteProfileRepository`, restoring consistency with the repository
  pattern used elsewhere in the ingestion service.

## Out Of Scope
- **Sport type filtering** (validation MAJOR finding): the architecture
  invariant "Non-running activities are excluded from twin calibration"
  (`principles` invariant 8) is not enforced, but the architecture does not
  define the detection mechanism — there is no `sport` field on the
  `Activity` entity contract, no documented FIT `sport` extraction contract,
  and no entry in the calibration eligibility gate for sport filtering.
  Phase-2.2 (signal cleaning) is also not its home; Phase-2.2's release-plan
  document mentions no sport-type extraction. This is an architecture gap,
  escalated separately (see Architecture Gap Escalation below). The coder
  must NOT add a `sport` column, a sport-detection branch, or any
  calibration-eligibility change in response to that finding under this plan.
- **GAP computation** (validation MINOR finding): the structural load formula
  using raw distance + elevation with `surface_modifier = 1.0` for
  `unknown` surface is the **documented Phase-2.1 behaviour** — the
  Phase-2.1 sub-phase explicitly defers GAP-based mechanical work to
  Phase-2.6, and the load-computation architecture's structural load
  formula uses `distance_m` + `elevation_gain_m` + `surface_type` (with
  `unknown` default), not GAP directly. No change.
- Any change to `CalibrationEligibilityService` rule logic, event payload,
  or load-computation formulas.
- Any schema change, migration, or new entity field.
- Test-suite additions beyond what is required to verify the two fixes.

## Architecture Contracts
- `02-computations/load-computation.md` → Quality Flags — DEPENDS ON (defines
  the `gps_loss` quality flag consumed by the calibration gate)
- `01-entities/activity.md` → `quality_flags` field — DEPENDS ON (JSONB shape
  must remain `gps_loss: boolean`)
- `01-entities/athlete-profile.md` → `structural_risk_flag` — DEPENDS ON (read
  via repository, not raw SQL)
- `app/repositories/athlete_profile_repository.py` — CONSUMES (existing
  repository providing `AthleteProfile` access)

## Invariants
- `calibration_eligible` is set by `CalibrationEligibilityService` and never
  manually overridden. — This plan does not touch the gate logic; the change
  is to a *quality flag* the gate reads, so the gate's authority is preserved.
- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields
  do not exist on `Activity`. They are never added. — Unchanged; this plan
  touches no Activity columns.
- No `UPDATE` or `DELETE` on Activity beyond the documented
  `update_load_scores`, `update_calibration_eligibility`, and
  `calibration_eligible`-filtered query paths. — Unchanged.
- `quality_flags` JSONB shape is stable (`hr_dropout_pct`, `gps_loss`,
  `sensor_malfunction`, `gps_spike_count`). — The `gps_loss` *computation*
  changes; the stored field name and type do not.

## Implementation Steps

1. [OWNER: Coder] Rework `gps_loss` detection inside
   `ActivityIngestionService._compute_quality_flags` (in
   `app/services/activity_ingestion_service.py`, the `parsed.has_gps`
   branch currently lines ~813–825). Replace the existing coverage-ratio
   heuristic (`actual_gps / expected_gps < 0.95`) with a continuous-gap
   scan over `parsed.gps_records` (a chronologically ordered list of
   `GpsRecord`, each carrying a `timestamp`). Compute inter-record deltas
   between consecutive GPS timestamps; set `gps_loss = true` if and only if
   any single continuous gap exceeds 30 seconds. Preserve the existing
   behaviour for the no-GPS branch (set `gps_loss = False` when
   `has_gps = false`) and the empty-GPS-list branch (set `gps_loss = True`
   when `has_gps = true` but `gps_records` is empty). Keep the
   `gps_spike_count` flag computation exactly as-is — it is unrelated to
   this finding and already conforms to the plan.

2. [OWNER: Coder] Modify `ActivityIngestionService._read_structural_risk_flag`
   (currently in `app/services/activity_ingestion_service.py`, lines ~765–783)
   to obtain `structural_risk_flag` via `AthleteProfileRepository` instead of
   a raw `text("SELECT structural_risk_flag ...")` query. Add
   `AthleteProfileRepository` as a constructor dependency of
   `ActivityIngestionService` (follow the same injection pattern already used
   for `ActivityRepository`, `CalibrationEligibilityService`, etc. — make it
   an `Optional[AthleteProfileRepository]` defaulted to `None` and build a
   default instance in the existing `_build_default_*` helper pattern when not
   injected, exactly as the other optional repositories are built). Return
   `False` when the profile is missing — preserving current behaviour. Remove
   the now-unused local `from sqlalchemy import text` import in that method
   (leave any other `text` imports that are still used elsewhere in the file).
   Do not change `_read_profile_date_of_birth` or `_read_athlete_preferences`
   in this plan — those raw-SQL lookups are out of scope here and are tracked
   as a separate consistency item.

3. [OWNER: Test Architect] Add targeted tests for the two fixes:
   - `gps_loss` continuous-gap detection: a GPS record stream with a 31-second
     gap between two timestamps sets `gps_loss = true`; a stream whose largest
     gap is exactly 30 seconds sets `gps_loss = false`; a stream with several
     sub-30s gaps sets `gps_loss = false`; an empty GPS record list with
     `has_gps = true` sets `gps_loss = true`; a `has_gps = false` activity
     sets `gps_loss = false` regardless of records.
   - `_read_structural_risk_flag` returns the profile's `structural_risk_flag`
     when a profile exists and `False` when none exists, exercising the
     repository-backed path (use the same test fixture pattern already used
     for other repository-backed ingestion lookups in this codebase).

## Event Contracts
None. This plan produces and consumes no events. It only changes the value of
a quality flag and the data-access path for one profile lookup.

## Pseudocode

```
# Step 1 — _compute_quality_flags, gps_loss branch

if not parsed.has_gps:
    gps_loss = False          # no GPS to lose; preserve current behaviour
elif not parsed.gps_records:
    gps_loss = True           # claimed GPS but zero records; preserve current behaviour
else:
    # Continuous-gap detection per Phase-2.1-P1 Handoff Note #2.
    # gps_records arrives in chronological order from FitParserService.
    previous_ts = gps_records[0].timestamp
    max_continuous_gap_s = 0.0
    for record in gps_records[1:]:
        delta = (record.timestamp - previous_ts).total_seconds()
        if delta > max_continuous_gap_s:
            max_continuous_gap_s = delta
        # Only treat forward gaps (delta < 0 means out-of-order; ignore)
        previous_ts = record.timestamp
    gps_loss = max_continuous_gap_s > 30.0

quality_flags["gps_loss"] = gps_loss
# gps_spike_count computation is untouched.
```

```
# Step 2 — _read_structural_risk_flag (repository-backed)

profile = await self.athlete_profiles.get_by_athlete_id(athlete_id)
if profile is None or profile.structural_risk_flag is None:
    return False
return bool(profile.structural_risk_flag)
```

## Testing Requirements
- A FIT-derived GPS stream containing a single > 30s continuous timestamp gap
  produces `activity.quality_flags["gps_loss"] == True`; the rest of the
  quality flags (`hr_dropout_pct`, `sensor_malfunction`, `gps_spike_count`)
  are unchanged from the pre-fix run.
- The same GPS stream with the gap reduced to ≤ 30s produces
  `activity.quality_flags["gps_loss"] == False`.
- An activity ingested for an athlete whose `AthleteProfile` carries
  `structural_risk_flag = True` results in the structural-load density
  penalty using the crossover coefficient (`0.08`), confirming the
  repository-backed lookup returned `True`. (This is verified by observing
  the same `structural_load` value the coverage-ratio-era code would have
  produced for the same inputs — i.e. behaviour is identical, only the
  data-access path changed.)
- An activity ingested for an athlete with no `AthleteProfile` results in
  `structural_risk_flag = False` (density coefficient `0.12`), confirming
  the missing-profile fallback is preserved.
- Calibration eligibility outcomes are unchanged for activities that already
  passed/failed the gate before this plan: a previously-eligible activity
  that has no GPS (and therefore `gps_loss = False`) remains eligible; a
  previously-eligible activity that has a > 30s GPS gap becomes ineligible
  (`gps_loss = True` now correctly disqualifies it, where the old 95%
  coverage heuristic may have let it through).

## Architecture Gap Escalation

The validation report's **MAJOR** finding — "Missing sport type filtering for
calibration eligibility" — is an **architecture gap**, not a coder-deferred
item, and is **not** addressed by this plan. The report routes it to
"p-architect + this report" and states it "requires clarification whether
this should block Phase 2.3 threshold detection." That routing is correct.

### Gap Statement
- **Architecture invariant that is unenforced:** `principles` invariant 8 —
  "Non-running activities are excluded from twin calibration. They appear in
  the training record. They never feed load computation, threshold detection,
  execution analysis, or adaptation modelling."
- **Why the mechanism is undefined:** The `Activity` entity contract
  (`01-entities/activity.md`) has no `sport` field. The calibration
  eligibility gate in `02-computations/load-computation.md` references
  `isUsableSessionType(activity.session_type)` — but `activity.session_type`
  is not a field on `Activity`; the 16-value `SessionType` lives on
  `PlannedSession` / `WorkoutStep` and is derived from the training plan,
  not from the FIT file. The FIT `session.sport` field (running / cycling /
  swimming / etc.) is trivially available at parse time but has no
  documented contract: no entity field to persist it on, no named
  `isRunningSport` / `isUsableSport` predicate, no entry in the calibration
  gate.
- **Why this cannot be resolved in the plan:** Adding a `sport` field to
  `Activity`, defining the RUNNING_SPORT set, or inserting a sport predicate
  into `CalibrationEligibilityService.evaluate` are all architecture
  decisions — they change entity contracts, invariants, or the calibration
  gate contract. Per the Implementation Architect's authority boundary, an
  implementation plan may not introduce entity fields, redefine event
  contracts, or alter the calibration gate. Several valid approaches exist
  (persist `sport` on `Activity`; read sport transiently at parse time and
  pass it to the gate without persisting; gate at the ingestion boundary
  before `LoadComputationService` runs) and the choice between them is an
  architecture decision, not a coder decision.
- **Correction to the validation report's premise:** The report states the
  check "requires session classification from Phase 2.2." Phase-2.2
  (`docs/release-plan/phase-2/phase-2-2-signal-cleaning.md`) is signal
  cleaning and `RawSensorStream` creation — its capabilities list and
  architectural contracts contain no sport-type or session-classification
  extraction. The deferral target in the report is incorrect; the gap is
  architectural, not sequencing.
- **Blocking impact:** Until resolved, uploading a cycling or swimming FIT
  file with HR data that meets the five-rule gate will set
  `calibration_eligible = true`, fire `activity_calibration_eligible`, and
  feed `TwinRecalibrationService` — directly violating invariant 8. Whether
  this blocks Phase-2.3 threshold detection (which consumes
  calibration-eligible activities) is a decision for the Architecture Author.

**Action required:** The Architecture Author must define the non-running
detection mechanism: where the sport identity lives, how it is populated, and
where in the ingestion/calibration pipeline the exclusion is enforced. Until
that contract exists, no implementation plan — including this one — should
add sport handling.

## Coder Handoff Notes

## Coder Scope
Execute:  Steps 1, 2  [OWNER: Coder]
Skip:     Step 3 (Test Architect — tests),
          Architecture Gap Escalation section (not an execute step)

## Coder Batches
Batch 1: Step 1  — `gps_loss` continuous-gap detection
Batch 2: Step 2  — repository-backed `structural_risk_flag` lookup

The two fixes touch different methods of the same file
(`app/services/activity_ingestion_service.py`) but have no inter-dependency;
either order is safe. They are kept as separate batches so a single
invocation's edit footprint stays bounded and the two changes are reviewable
independently. If executing as a single invocation, consolidate edits to the
shared file in one pass.

## Context Needed
Step 1:  Existing: `app/services/activity_ingestion_service.py` (the
         `_compute_quality_flags` method, currently lines ~785–852).
         Entities/architecture: `02-computations/load-computation.md`
         "calibration eligibility gate" section (consumes `gps_loss`).
         Invariants: `quality_flags` JSONB shape stability. No new files.
Step 2:  Existing: `app/services/activity_ingestion_service.py` (constructor
         and `_read_structural_risk_flag`); `app/repositories/athlete_profile_repository.py`
         (existing repository to consume — read its public method for fetching
         a profile by athlete_id before wiring). Entities: `athlete-profile`
         entity's `structural_risk_flag` field. Invariants: none specific.

### Known Risks
1. **`gps_loss` strictness may regress previously-eligible activities.** The
   old 95% coverage heuristic could pass streams with many short gaps; the new
   > 30s continuous-gap rule fails only on a single long gap. In practice the
   new rule is **more permissive** for intermittent dropouts and **less
   permissive** for a single sustained outage. Re-running the existing
   Phase-2.1 ingestion test fixtures should reveal any activity that flips.
   If a fixture was crafted around the coverage heuristic, update the fixture's
   expectation to the continuous-gap semantics — do not weaken the new rule.

2. **`AthleteProfileRepository` method name.** `implemented-state.md` lists
   `AthleteProfileRepository -> AthleteProfile` but does not enumerate its
   methods. Before wiring Step 2, read the repository's public surface; if it
   exposes a `get_by_athlete_id` (or similarly named) method that returns the
   profile or `None`, use it. If no such method exists, add one following the
   exact pattern used by the other `*_by_athlete_id` lookups in the
   repositories directory — this is a routine repository addition, not an
   architecture change.

### Architecture Interpretations
1. **`gps_loss` semantics.** The Phase-2.1-P1 plan Handoff Note #2 is
   explicit: "only flag when position/altitude data is missing for > 30
   continuous seconds during moving time." The implementation must interpret
   "continuous seconds" as **wall-clock gap between consecutive GPS record
   timestamps**, not "duration without a GPS record at a particular 1Hz
   sampling assumption." If the FIT file's GPS streams are not 1Hz (some
   devices record at 1s, some at the cadence of the recording), the
   timestamp-delta approach is the only correct one; the old coverage-ratio
   heuristic assumed 1Hz sampling and was therefore doubly wrong.

2. **Out-of-order timestamps.** Some FIT producers emit GPS records slightly
   out of chronological order at session boundaries. The continuous-gap scan
   should accumulate the *forward* delta only (`record.timestamp - previous_ts`
   where positive); a negative delta (out-of-order) should not be treated as a
   gap and should not reset the running maximum. `previous_ts` updates to the
   latest record's timestamp regardless, so the next delta is measured against
   the most recent point in time.

3. **Repository injection pattern.** `ActivityIngestionService` already uses
   optional repository dependencies defaulted to `None` (see
   `Optional[ObjectStorageClient]`, `Optional[CalibrationEligibilityService]`
   in `implemented-state.md`'s Service Wiring section). Add
   `Optional[AthleteProfileRepository]` the same way and build a default in
   the existing default-builder pattern. Do **not** make it a required
   constructor argument — that would break existing call sites that construct
   the service without it.

### Why The Two Findings Are The Only Coder-Actionable Ones
- **MAJOR (sport filtering):** architecture gap. The mechanism for detecting
  non-running activities is undefined (no `sport` field on `Activity`, no
  FIT-sport extraction contract, no gate entry). Routed to the Architecture
  Author via the Architecture Gap Escalation section above. The coder must
  not implement it under this plan.
- **MINOR (GAP):** explicit Phase-2.1 deferral. The sub-phase document
  states "Surface type defaults to `unknown`" and the load-computation
  architecture's structural load formula uses `distance_m` + `elevation_gain_m`
  + `surface_type` (with `unknown = 1.0`), not GAP directly. GAP-based
  mechanical work is Phase-2.6 scope per the sub-phase's downstream-enablement
  list. No action.
- **MINOR (gps_loss):** coder-actionable — addressed in Step 1.
- **MINOR (local SQL):** coder-actionable — addressed in Step 2.

### Deferred Items Explicitly Not In This Plan
- `_read_profile_date_of_birth` and `_read_athlete_preferences` also use raw
  `text()` SQL. They are out of scope here because the validation report
  flagged only `_read_structural_risk_flag`. They are noted as a future
  consistency pass; do not touch them under this plan unless asked.
- The MAJOR sport-filter gap is **not** deferred to a later coder step; it is
  escalated to the Architecture Author and may not be implemented until the
  architecture defines the mechanism.
