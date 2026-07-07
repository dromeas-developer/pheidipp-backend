# Implementation Plan: Phase-2.1 — Sport Type Filtering (Delta)
## Plan ID: Phase-2.1-P3

## Sub-Phase Reference
Sub-Phase ID: Phase-2.1
Sub-Phase Title: FIT Ingestion Pipeline Expansion & Calibration Eligibility

## Objective
Close the MAJOR architecture finding from the Phase-2.1-P1 validation
revalidation report: "Missing sport type filtering for calibration
eligibility." The architecture now defines the `sport_type` field on
`Activity`, a `SportType` enum, a FIT sport-field detection mechanism, and
a sport-type gate as the first check in the calibration eligibility gate.
This plan implements that contract so that non-running activities
(cycling, swimming, strength, etc.) are correctly identified at ingestion,
persisted on the Activity record, and excluded from twin calibration —
enforcing Principle #8: "Non-running activities are excluded from twin
calibration."

This plan is a delta on top of the completed Phase-2.1-P1 and Phase-2.1-P2
work. It adds the sport-type plumbing without re-touching any of the load
computation, quality-flag, or remediation work already delivered.

## Scope
- Add `SportType` enum to `app/models/enums.py` with seven values:
  `running`, `cycling`, `swimming`, `strength`, `yoga_mobility`,
  `other`, `unknown`
- Add `sport_type` column to the `Activity` model (`app/models/activity.py`)
  with `nullable=False` and a `server_default` of `'unknown'`
- Add `sport_type` field to the `ParsedFitData` dataclass
  (`app/services/fit_parser_service.py`) carrying the detected `SportType`
  plus `detection_confidence` string
- Expand `FitParserService._parse_sync` to extract the FIT `sport` message
  (message name `session`, fields `sport` and `sub_sport`) and map it to
  `SportType` using the Garmin/Ant+ sport-mapping table from
  `02-computations/sport-type-detection.md`
- Add `sport_type` to `LoadComputationInputs` so the ingestion service can
  pass it through, and so non-running activities are treated as `data_tier = 6`
- Insert the sport-type exclusion as the **first** check in
  `CalibrationEligibilityService.evaluate`
- Wire `ActivityIngestionService._run_ingestion_pipeline` to:
  - Set `activity.sport_type` from `ParsedFitData.sport_type`
  - Override `data_tier` to `DataTier.TIER_6` when
    `sport_type != 'running'` (per architecture invariant)
  - Fire the `sport_type_detected` event after the Activity is updated
    and before `activity_calibration_eligible`
- Add `sport_type` and `sport_type_detection_version` to the `ActivityResponse`
  and `ActivityListResponse` schemas
- Add a `sport_type_detection_version` column to `Activity` (architecture
  requires versioning for reprocessing)
- Update `__init__.py` exports for new enum and updated exports

## Out Of Scope
- **Intervals.icu API metadata extraction**: The architecture's secondary
  detection path (reading `type` from the Intervals.icu `/activities`
  endpoint) is not implemented here. Phase 2.1 is "manual upload only"
  (per the sub-phase Challenge Notes); no Intervals.icu auto-sync is
  available. The FIT sport field (primary path) covers all manual-upload
  activities. The Intervals.icu mapping table will be wired when auto-sync
  is implemented in a later phase.
- **Manual-upload sport selection UI flow**: The architecture says "the
  athlete is prompted to select a sport type during upload" for
  `source = 'manual_upload'`. The `POST /activities/upload` endpoint does
  not currently accept a sport-selection parameter. Adding that is a UI/API
  flow concern; for FIT files the parser extracts sport from the FIT sport
  message, so the selection path is only needed for FIT files with
  `sport = generic/missing`. This plan defaults those to `'unknown'`
  (per the architecture's failure mode) and defers the selection prompt
  to a future API enhancement.
- **Coach message for `sport_type = 'unknown'`**: The architecture
  detection failure mode says "a coach message is generated explaining
  why the session was not analysed." That coach-message generation is not
  part of the ingestion pipeline contract; it is a downstream coaching
  capability that belongs to a later phase. This plan records `sport_type`
  and `calibration_eligible = false` correctly; it does not generate the
  coach message.
- **Reprocessing of existing activities**: Activities already ingested
  under Phase-2.1-P1/P2 have `sport_type = NULL` (the column does not exist
  yet). After the migration adds the column with `server_default =
  'unknown'`, existing rows will have `sport_type = 'unknown'` and hence
  `calibration_eligible` will need re-evaluation. A backfill of
  `calibration_eligible = false` for existing rows with
  `sport_type = 'unknown'` is included in the migration (to preserve
  the invariant that `unknown` activities are never calibration-eligible),
  but a full re-parse of existing FIT files to populate `sport_type`
  accurately is deferred to the reprocessing pipeline (Phase 2.x or a
  dedicated backfill task).
- Any change to load-computation formulas, quality-flag computation, or
  the five-rule gate's existing rules. The sport-type check is the **sixth
  rule added as the first check**, not a modification of the existing five.

## Architecture Contracts
- `01-entities/activity.md` — IMPLEMENTS (`sport_type` field,
  `SportType` enum, `sport_type_detection_version` field)
- `02-computations/sport-type-detection.md` — IMPLEMENTS (FIT sport field
  detection, Garmin/Ant+ mapping table, failure mode, detection version)
- `02-computations/load-computation.md` — IMPLEMENTS (calibration
  eligibility gate: `sport_type` check as first gate entry) →
  "Calibration Eligibility Gate" section
- `00-foundations/event-catalogue.md` → `sport_type_detected` — PRODUCES
  (payload: `{activity_id, sport_type, detection_confidence,
  detection_version}`)
- `principles.md` → Invariant #8 — DEPENDS ON (enforces: non-running
  activities excluded from twin calibration)
- `docs/vision/twin/core.md` → "The running-only boundary" — DEPENDS ON
  (vision rationale: the twin sees running; the training record sees
  everything)
- Phase-2.1-P1 (`docs/implementation/phase-2/phase-2-1-p1-fit-ingestion-expansion.md`)
  — DEPENDS ON (must be fully implemented; this plan extends its pipeline)
- Phase-2.1-P2 (`docs/implementation/phase-2/phase-2-1-p2-validation-remediation.md`)
  — DEPENDS ON (must be fully implemented; this plan does not re-touch
  its fixes)

## Invariants
Copied verbatim from the architecture documents:

- "Non-running activities are excluded from twin calibration. Activities
  with `sport_type != 'running'` (detected at ingestion from FIT file sport
  field or Intervals.icu metadata) are logged in the training record but
  are never calibration-eligible. They do not feed load computation,
  threshold detection, execution analysis, or adaptation modelling." —
  `principles` invariant 8

- "For non-manual entry sources, `sport_type` is populated during
  `FitParserService` execution and is never null at the time of Activity
  creation. If the parser cannot determine the sport, it must default to
  `'unknown'`." — `activity` invariant

- "Activities with `sport_type != 'running'` are treated as
  `calibration_eligible = false` and `data_tier = 6` by the
  `CalibrationEligibilityService`, regardless of hardware signal quality.
  This enforces the running-only twin model (Principle #8)." — `activity`
  invariant

- "`sport_type = 'unknown'` implies `calibration_eligible = false`." —
  `sport-type-detection` invariant

- "`sport_type != 'running'` implies `calibration_eligible = false` and
  `data_tier = 6` (manual-entry equivalent)." — `sport-type-detection`
  invariant

- "`sport_type` is populated before `Activity` record creation." —
  `sport-type-detection` invariant

- "The sport type mapping is versioned (`sport_type_detection_version`) to
  enable reprocessing if mappings change." — `sport-type-detection`
  invariant

- "Source `manual_entry` activities always have `calibration_eligible =
  false`, null load scores, and null `fit_file_key`. These are not error
  conditions." — `activity` invariant (unchanged; manual-entry activities
  have no FIT file and therefore no sport-type extraction — they default
  to `'unknown'`)

- "`calibration_eligible` is set by `CalibrationEligibilityService` and
  never manually overridden." — `activity` invariant (unchanged; the
  sport-type check is added inside the service's `evaluate` method)

## Implementation Steps

1. [OWNER: Coder] Add `SportType` enum to `app/models/enums.py` with
   values: `running`, `cycling`, `swimming`, `strength`, `yoga_mobility`,
   `other`, `unknown`. This is a `str` enum matching `ActivitySource` and
   the other string-enums already in the file. Register it in
   `app/models/__init__.py` exports alongside the existing enums.

2. [OWNER: Coder] Add two columns to the `Activity` model in
   `app/models/activity.py`:
   - `sport_type: Mapped[SportType]` — use `SAEnum(SportType, ...)` with
     `native_enum=False`, `length=32`, `values_callable` matching the
     pattern already used for `ActivitySource`. Set `nullable=False`,
     `server_default="unknown"`. This ensures existing rows (that have no
     sport_type) default to `'unknown'` rather than raising on migration.
   - `sport_type_detection_version: Mapped[str | None]` — `String(16)`,
     `nullable=True`. Populated with the detection pipeline version string
     at ingestion time; null for manual-entry activities (no detection
     ran). No index required.

3. [OWNER: DevOps] Generate Alembic migration for the two new columns
   (`sport_type` and `sport_type_detection_version`) on the `activities`
   table. Review for the following augmentation requirements:
   - `sport_type` must be added with a server-side default of `'unknown'`
     so existing rows do not violate the `NOT NULL` constraint.
   - After the column is added, backfill `calibration_eligible = false`
     for all existing rows where `sport_type = 'unknown'` (which is all
     existing rows). This preserves the invariant that `unknown` activities
     are never calibration-eligible immediately after migration, without
     requiring a re-parse pass.
   - Apply to test database. Verify no lock-duration issues on existing
     rows.

4. [OWNER: Coder] Extend `ParsedFitData` dataclass in
   `app/services/fit_parser_service.py` to include:
   - `sport_type: SportType` — defaulting to `SportType.UNKNOWN` (so
     files without a sport message produce the architecture-mandated
     `'unknown'` fallback without error)
   - `detection_confidence: str` — defaulting to `"unknown"` (matching
     the architecture's `'high' | 'low' | 'unknown'` confidence values;
     FIT extracted sports map to `"high"` confidence since the FIT
     `sport` message is an explicit declaration, not a heuristic)
   - `detection_version: str` — a constant string for this pipeline
     version (e.g. `"v1"`)

5. [OWNER: Coder] Expand `FitParserService._parse_sync` to extract the
   FIT `sport` and `sub_sport` fields from the `session` message (the
   existing loop already processes `session` messages for session-level
   totals — extend it to also read `sport` and `sub_sport`). Map the
   raw integer values to `SportType` using the Garmin/Ant+ sport-mapping
   table from `02-computations/sport-type-detection.md`:
   - sport=1 (running) → `running` (regardless of sub_sport)
   - sport=2 (cycling) → `cycling`
   - sport=3 (transition) → `other`
   - sport=4 (fitness_equipment) → `strength`
   - sport=5 (swimming) → `swimming`
   - sport=14 (walking) → `other`
   - sport=254 (all) or sport=0 (generic) or sport missing → `unknown`
   Set `detection_confidence = "high"` when the FIT sport field is
   present and mappable; `"unknown"` when it is absent or generic. Do not
   raise on an unrecognized sport value — default to `'other'` with
   `detection_confidence = "low"`. Preserve all existing extraction
   behavior (HR, power, GPS, RR, session totals). Add the three new
   fields to the `ParsedFitData(...)` constructor call at the end of
   `_parse_sync`.

6. [OWNER: Coder] Add `sport_type` and `sport_type_detection_version` to
   `LoadComputationInputs` in `app/services/load_computation_service.py`
   so the ingestion service can pass them through. The load computation
   service does not use `sport_type` directly (it receives `data_tier`
   which already encodes the non-running override as Tier 6), but the
   field must be present for future phases that pass the full pipeline
   context. Do not change any load formula.

7. [OWNER: Coder] Insert the sport-type exclusion as the **first** check
   in `CalibrationEligibilityService.evaluate` (in
   `app/services/calibration_eligibility_service.py`). The check is:
   if `activity.sport_type != 'running'`, return `False` immediately,
   before any of the existing five rules are evaluated. This matches the
   architecture's `isCalibrationEligible` gate where `sport_type !==
   'running' → return false` is the very first condition. The existing
   five-rule gate logic remains unchanged below this check. The method
   now reads `activity.sport_type` which is a populated field (set by
   the ingestion service before `evaluate` is called).

8. [OWNER: Coder] Update `ActivityIngestionService._run_ingestion_pipeline`
   (in `app/services/activity_ingestion_service.py`) to wire sport-type
   through the pipeline. After the FIT parse (step 3 of the pipeline)
   and before the data-tier inference (step 4):
   a. Set `activity.sport_type` from `parsed.sport_type`.
   b. Set `activity.sport_type_detection_version` from
      `parsed.detection_version`.
   c. When `parsed.sport_type != SportType.RUNNING`, override the
      inferred `data_tier` to `DataTier.TIER_6` (per the architecture
      invariant: `sport_type != 'running' → data_tier = 6`). This
      happens after the normal `self._infer_data_tier(preferences)` call
      — the sport-type override takes precedence over the
      hardware-based tier inference.
   d. Include `sport_type` and `sport_type_detection_version` in the
      `LoadComputationInputs` constructor call.
   e. Include `sport_type` in the `activity_ingested` event payload
      (add `"sport_type": activity.sport_type.value` to the payload
      dict — the architecture `activity_ingested` payload does not
      list it explicitly in v1, but the sport-type-detection document
      says "sport type is embedded in the Activity record" consumed
      by `activity_ingested`; embedding it in the event payload makes
      it visible to downstream consumers without a separate query).
   f. Fire the `sport_type_detected` event via `EventPublisher.publish`
      after the Activity update flush and **before** the
      `activity_calibration_eligible` event. Payload: `{activity_id,
      sport_type, detection_confidence, detection_version}`. This event
      fires for all non-manual-entry sources regardless of whether the
      sport is running or not — the detection result is the event, not
      the eligibility outcome. Do **not** fire `sport_type_detected` for
      `source = 'manual_entry'` activities (they have no FIT file and
      no detection was performed).
   g. The calibration eligibility evaluation (`evaluate` call) now reads
      `activity.sport_type` which was set in step (a) above. No change
      is needed to the call site — the gate's first check will return
      `False` for non-running activities. The existing `data_tier in
      (TIER_5, TIER_6) → eligible = False` post-check is now redundant
      for non-running activities (they are already stopped by the
      sport gate) but remains correct for running Tier-5/6 activities
      and should be left in place.

9. [OWNER: Coder] Add `sport_type` and `sport_type_detection_version` to
   `ActivityResponse` in `app/schemas/activity.py`. `sport_type` should
   be typed as `SportType` (the enum, imported from
   `app.models.enums`) — Pydantic will serialize the enum value
   (`"running"`, `"cycling"`, etc.). `sport_type_detection_version` is
   `Optional[str]`. Update `ActivityListResponse` if it independently
   defines fields (it currently reuses `ActivityResponse` via a list,
   so it inherits the new field automatically). Update
   `app/schemas/__init__.py` if `SportType` needs exporting (it is in
   `app.models.enums`, already accessible; the schema import from that
   module is sufficient).

10. [OWNER: Coder] Update `app/models/__init__.py` to export `SportType`.
    Update `app/services/__init__.py` to export `SportType` if any of
    the service-layer dataclasses (`ParsedFitData`, `LoadComputationInputs`)
    reference it in their type hints and are re-exported. Verify
    `app/services/__init__.py` still exports `ParsedFitData` and
    `LoadComputationInputs` with the new fields.

11. [OWNER: Test Architect] Write tests for `FitParserService` sport-type
    extraction:
    - A running FIT file (sport=1) parses to `sport_type = 'running'`
      with `detection_confidence = 'high'`.
    - A cycling FIT file (sport=2) parses to `sport_type = 'cycling'`.
    - A swimming FIT file (sport=5) parses to `sport_type = 'swimming'`.
    - A trail-running FIT file (sport=1, sub_sport=14) parses to
      `sport_type = 'running'` (sub_sport does not override running).
    - A FIT file with sport=0 (generic) or missing sport field parses to
      `sport_type = 'unknown'` with `detection_confidence = 'unknown'`.
    - A FIT file with an unrecognized sport integer (e.g. 99) parses to
      `sport_type = 'other'` with `detection_confidence = 'low'`.
    - An indoor-cycling FIT file (sport=2, sub_sport=8) parses to
      `sport_type = 'cycling'`.

12. [OWNER: Test Architect] Write tests for `CalibrationEligibilityService`
    sport-type gate:
    - An activity with `sport_type = 'running'` that passes the five
      rules is `calibration_eligible = true`.
    - An activity with `sport_type = 'cycling'` is
      `calibration_eligible = false` regardless of HR/duration/quality
      flags.
    - An activity with `sport_type = 'swimming'` is
      `calibration_eligible = false`.
    - An activity with `sport_type = 'unknown'` is
      `calibration_eligible = false`.
    - An activity with `sport_type = 'strength'` is
      `calibration_eligible = false`.
    - An activity with `sport_type = 'other'` is
      `calibration_eligible = false`.
    - The sport-type check runs before all other rules: an activity with
      `sport_type = 'cycling'` and HR dropout > 20% returns `false` from
      the sport check, not the HR check (verify by having the test pass
      all five rules — the sport check alone is the disqualifier).

13. [OWNER: Test Architect] Write integration tests for
    `ActivityIngestionService` sport-type pipeline:
    - Uploading a running FIT file creates an `Activity` with
      `sport_type = 'running'`, `sport_type_detection_version` set, and
      `calibration_eligible` follows the existing five-rule gate.
    - Uploading a cycling FIT file creates an `Activity` with
      `sport_type = 'cycling'` and `calibration_eligible = false`.
    - Uploading a swimming FIT file creates an `Activity` with
      `sport_type = 'swimming'` and `calibration_eligible = false`.
    - Uploading a FIT file with undetectable sport creates an `Activity`
      with `sport_type = 'unknown'` and `calibration_eligible = false`.
    - A non-running activity's `data_tier` is overridden to `TIER_6`
      regardless of athlete preferences (the hardware tier is ignored for
      non-running activities).
    - The `sport_type_detected` event fires with payload
      `{activity_id, sport_type, detection_confidence, detection_version}`.
    - The `sport_type_detected` event fires before
      `activity_calibration_eligible` (outbox insertion order).
    - A manual-entry activity does NOT fire `sport_type_detected` (no
      FIT parse, no detection performed).
    - `GET /athletes/{id}/activities/{aid}` returns `sport_type` and
      `sport_type_detection_version` correctly populated.

## Event Contracts

### Produces

| Event | Trigger | Payload | Ordering |
|---|---|---|---|
| `sport_type_detected` | After `FitParserService` identifies sport and `Activity.sport_type` is set | `{ activity_id: string, sport_type: SportType, detection_confidence: 'high' \| 'low' \| 'unknown', detection_version: string }` | Fires after `activity_ingested` (which already fires after the Activity update flush, per the existing pipeline). Fires **before** `activity_calibration_eligible` (when the latter fires — it only fires for running activities that pass all rules, so `sport_type_detected` is always first). For non-running activities, `activity_calibration_eligible` does not fire (they are ineligible), so `sport_type_detected` is the last event in the ingestion chain. For `source = 'manual_entry'`, `sport_type_detected` does NOT fire (no detection performed). |

### Consumes
None. This plan only produces events.

## Pseudocode

```
# Step 5 — FIT sport extraction inside _parse_sync session branch

sport_int = message.get_value("sport")       # raw int or None
sub_sport_int = message.get_value("sub_sport")

sport_type = map_fit_sport_to_enum(sport_int, sub_sport_int)
detection_confidence = "high" if sport_int not in (None, 0, 254) else "unknown"
detection_version = SPORT_TYPE_DETECTION_VERSION  # "v1"

# Mapping function:
def map_fit_sport_to_enum(sport, sub_sport):
    if sport is None or sport == 0 or sport == 254:
        return SportType.UNKNOWN
    if sport == 1:   # running — sub_sport irrelevant
        return SportType.RUNNING
    if sport == 2:
        return SportType.CYCLING
    if sport == 3:
        return SportType.OTHER       # transition
    if sport == 4:
        return SportType.STRENGTH    # fitness_equipment
    if sport == 5:
        return SportType.SWIMMING
    if sport == 14:
        return SportType.OTHER       # walking
    # Unknown sport int — default to other with low confidence
    return SportType.OTHER
```

```
# Step 7 — CalibrationEligibilityService.evaluate with sport gate

def evaluate(activity):
    # Sport-type exclusion — first check, before all other rules
    if activity.sport_type != SportType.RUNNING:
        return False
    # Existing five-rule gate follows
    return _evaluate_full_rules(activity)
```

```
# Step 8 — _run_ingestion_pipeline sport-type wiring (after parse, before load)

# After FitParserService.parse returns `parsed`:
activity.sport_type = parsed.sport_type
activity.sport_type_detection_version = parsed.detection_version

# Infer data tier from preferences, then override for non-running
data_tier = self._infer_data_tier(athlete_preferences)
if parsed.sport_type != SportType.RUNNING:
    data_tier = DataTier.TIER_6   # architecture invariant

# ... (existing load computation, score update, quality flags, flush) ...

# Fire sport_type_detected event (after flush, before calibration event)
if activity.source != ActivitySource.MANUAL_ENTRY:
    await self.events.publish(
        event_type="sport_type_detected",
        athlete_id=athlete_id,
        payload={
            "activity_id": str(activity.id),
            "sport_type": activity.sport_type.value,
            "detection_confidence": parsed.detection_confidence,
            "detection_version": parsed.detection_version,
        },
    )

# Fire activity_ingested (existing — add sport_type to payload)
await self.events.publish(
    event_type="activity_ingested",
    athlete_id=athlete_id,
    payload={
        ...existing fields...,
        "sport_type": activity.sport_type.value,
    },
)

# Fire activity_calibration_eligible when eligible (existing — unchanged)
# Non-running activities never reach here (sport gate returned False)
if eligible and scores.aerobic_load is not None:
    await self.events.publish(
        event_type="activity_calibration_eligible",
        ...
    )
```

```
# Event ordering within _run_ingestion_pipeline transaction:
#   1. Activity update flush (sport_type, load scores, quality flags)
#   2. sport_type_detected    (fires for all non-manual-entry sources)
#   3. activity_ingested       (fires for all activities — existing,
#                               now includes sport_type in payload)
#   4. activity_calibration_eligible (fires only for eligible running
#                               activities — existing, unchanged)
```

## Testing Requirements
- Uploading a running FIT file with power data creates an `Activity` with
  `sport_type = 'running'`, `sport_type_detection_version` populated
  (non-null), and `calibration_eligible = true` when it meets the
  six-rule gate (sport-type + five rules).
- Uploading a cycling FIT file creates an `Activity` with
  `sport_type = 'cycling'` and `calibration_eligible = false` regardless
  of HR data quality, duration, or signal completeness.
- Uploading a swimming FIT file creates an `Activity` with
  `sport_type = 'swimming'` and `calibration_eligible = false`.
- Uploading a FIT file where the sport field is missing or generic
  creates an `Activity` with `sport_type = 'unknown'` and
  `calibration_eligible = false`.
- Uploading a trail-running FIT file (sport=1, sub_sport=14) creates an
  `Activity` with `sport_type = 'running'` (sub_sport does not override
  running classification) — preserving calibration eligibility for
  trail runs.
- A non-running activity's `data_tier` is `TIER_6` even when the
  athlete's preferences (HR source, power source) would normally infer
  a higher tier — the sport-type override applies before load
  computation.
- The `sport_type_detected` event fires with payload
  `{activity_id, sport_type, detection_confidence, detection_version}`
  for non-manual-entry sources.
- The `sport_type_detected` event does NOT fire for
  `source = 'manual_entry'` activities.
- The `sport_type_detected` event is inserted into the outbox **before**
  `activity_ingested` and `activity_calibration_eligible` (publishing
  order follows outbox insertion order).
- `GET /athletes/{id}/activities/{aid}` returns `sport_type` and
  `sport_type_detection_version` in the response body, correctly
  populated from the stored Activity row.
- Manual-entry activities (no FIT file) have `sport_type = 'unknown'`
  (the column default) and `calibration_eligible = false` — this is
  the existing behavior, now explicitly confirmed by the sport-type gate.
- The existing five-rule gate is not weakened: a running activity that
  fails the five rules (e.g. duration < 1200s, HR dropout > 20%) remains
  `calibration_eligible = false` — the sport-type check does not pass
  ineligible running activities through.
- Existing Phase-2.1-P1/P2 test fixtures that ingest running FIT files
  continue to pass; the sport-type addition does not regress previously
  eligible activities.

## Coder Handoff Notes

## Coder Scope
Execute:  Steps 1, 2, 4, 5, 6, 7, 8, 9, 10  [OWNER: Coder] — includes
          migration generation
Skip:     Step 3 (DevOps — migration review, backfill augmentation,
          and application to test database),
          Steps 11, 12, 13 (Test Architect — tests)

## Coder Batches
Batch 1: Steps 1, 2, 9, 10  — Schema-layer changes (enum, model columns,
                                response schema, exports)
Batch 2: Steps 4, 5          — FIT parser sport extraction
Batch 3: Steps 6, 7          — Load computation inputs + calibration gate
Batch 4: Step 8             — Ingestion pipeline wiring + event firing

### Batch rationale
- **Batch 1** establishes the new types (`SportType`, model columns,
  response schema field) before any service logic references them.
- **Batch 2** extends the FIT parser to produce `sport_type` — it
  depends only on `SportType` from Batch 1.
- **Batch 3** passes sport_type through load inputs and adds the gate
  check — depends on `SportType` and the `Activity` column from
  Batch 1.
- **Batch 4** wires everything in the ingestion pipeline and fires the
  new event — depends on the parser output (Batch 2), the gate check
  (Batch 3), and the model columns (Batch 1). This is the largest step
  and has no downstream dependency within this plan.

If executing as a single invocation, the batches still tell you a safe
grouping for consolidating same-file edits — see "Consolidate Same-File
Edits" in the coder's Execution Protocol.

## Context Needed
Step 1:  Existing: `app/models/enums.py` (the enum file — follow the
         `str, Enum` pattern used by `ActivitySource`, `SportBackground`,
         etc.). Entities: `SportType` enum from
         `01-entities/activity.md` "TypeScript Schema" section
         (values: running, cycling, swimming, strength, yoga_mobility,
         other, unknown). Invariants: none specific.
Step 2:  Existing: `app/models/activity.py` (the `Activity` model — add
         the column after `duration_seconds` per the entity schema
         layout, using the `SAEnum(...)` pattern already on `source`).
         Entities: `01-entities/activity.md` "TypeScript Schema" section
         (`sport_type: SportType` field and the
         `sport_type_detection_version` versioning invariant).
         Invariants: `sport_type` populated before Activity creation;
         `unknown` implies `calibration_eligible = false`.
Step 4:  Existing: `app/services/fit_parser_service.py` (the
         `ParsedFitData` dataclass, lines ~104-143 — add fields after
         `moving_duration_seconds`; the `_parse_sync` method, lines
         ~197-330). Entities: `02-computations/sport-type-detection.md`
         "Detection Strategy" + "Garmin/Ant+ Sport Mappings" table and
         "Output" section. Invariants: `sport_type = 'unknown'` on
         failure; detection versioned.
Step 5:  Existing: output of Step 4 (the `_parse_sync` method, not yet
         on disk). Entities: the Garmin/Ant+ mapping table
         (sport=1→running, 2→cycling, 3→other, 4→strength, 5→swimming,
         14→other, 254/0/missing→unknown). Invariants: missing sport
         → `'unknown'` with confidence `'unknown'`.
Step 6:  Existing: `app/services/load_computation_service.py` — the
         `LoadComputationInputs` dataclass (add `sport_type` and
         `sport_type_detection_version` fields; do not change the
         `compute_aerobic_load` signature). Entities: none — the
         load formulas do not consume `sport_type`. Invariants: none.
Step 7:  Existing: `app/services/calibration_eligibility_service.py`
         (the `evaluate` method — add the sport check before
         `_evaluate_full_rules`, using `activity.sport_type`).
         Entities: `02-computations/load-computation.md`
         "Calibration Eligibility Gate" section (`isCalibrationEligible`
         — `sport_type !== 'running' → return false` is the first check).
         Invariants: `sport_type != 'running'` implies
         `calibration_eligible = false`; `unknown` implies
         `calibration_eligible = false`.
Step 8:  Existing: `app/services/activity_ingestion_service.py` (the
         `_run_ingestion_pipeline` method, lines ~448-630, and the
         `EventPublisher` injection already on `self.events` — see
         the existing `activity_ingested` and
         `activity_calibration_eligible` publish calls for the exact
         pattern). Entities: `sport_type_detected` event payload
         from `00-foundations/event-catalogue.md`. Invariants:
         `sport_type` populated before Activity creation (set it
         before the flush); `sport_type != 'running' → data_tier = 6`;
         `sport_type_detected` not fired for `manual_entry`.
Step 9:  Existing: `app/schemas/activity.py` (the `ActivityResponse`
         class — add `sport_type: SportType` and
         `sport_type_detection_version: Optional[str]` fields;
         `ActivityListResponse` reuses `ActivityResponse` so no
         separate change needed). Entities: `01-entities/activity.md`
         "TypeScript Schema" (`sport_type` field is non-optional in
         the entity; in the wire schema it is always populated because
         the column has `server_default = 'unknown'`).
Step 10: Existing: `app/models/__init__.py`, `app/services/__init__.py`
         (add `SportType` to the model exports; verify service exports
         include `ParsedFitData` and `LoadComputationInputs` with the
         new fields — these are already exported, just imported).
         Entities: none. Invariants: none.

### Known Risks

1. **Existing activities will have `sport_type = 'unknown'` after
   migration.** The column is added with `server_default = 'unknown'`
   so the `NOT NULL` constraint does not break existing rows. However,
   some of those existing rows may have `calibration_eligible = true`
   (running activities that passed the five-rule gate under P1/P2).
   The migration must backfill `calibration_eligible = false` for all
   rows where `sport_type = 'unknown'` to immediately enforce
   `unknown → calibration_eligible = false`. The accurate re-population
   of `sport_type` for existing rows requires re-parsing their FIT
   files; that backfill-reparse is deferred (see Out Of Scope). The
   DevOps migration step (Step 3) is responsible for the
   `calibration_eligible` backfill.

2. **`data_tier` override precedence.** The architecture says
   `sport_type != 'running' → data_tier = 6`. This override takes
   precedence over the hardware-based `_infer_data_tier(preferences)`
   call. A cyclist with a chest-strap HR and a power meter (which would
   normally infer `TIER_1`) must still be treated as `TIER_6` so that
   load computation returns null scores and the calibration gate
   rejects the activity. The override is applied in the ingestion
   service (§), NOT in the `_infer_data_tier` helper itself — the helper
   is a pure mapping from preferences to tier and must not gain sport
   knowledge (it is also called from onboarding and other paths that do
   not involve sport-type detection).

3. **`sport_type_detected` event does not fire for `manual_entry`.**
   The architecture says the `sport_type_detected` event is produced
   by `FitParserService` after it identifies the sport. Manual-entry
   activities never go through `FitParserService` — they are created
   via the `POST /activities` manual endpoint, not the upload
   pipeline. Therefore `sport_type_detected` must NOT fire for manual
   entries. The `sport_type` column for manual entries defaults to
   `'unknown'` and the calibration gate will reject them (as it
   already does via the `source == 'manual_entry'` check — which is
   now the **second** check in the gate, after the sport-type check).

4. **Event ordering: `sport_type_detected` before `activity_ingested`.**
   The architecture's sport-type-detection document lists `activity_ingested`
   as a **consumed** event ("sport type is embedded in the Activity record").
   The ingestion pipeline currently fires `activity_ingested` after the
   Activity update flush. The `sport_type_detected` event must fire
   before `activity_ingested` in the outbox insertion order, because
   `activity_ingested` conceptually carries the sport type embedded in
   the Activity record (the "Consumed Events" table is conceptual — it
   means "sport type is available by the time activity_ingested fires").
   Insert `sport_type_detected` into the outbox **before** the
   `activity_ingested` publish call in the pipeline. Both events are in
   the same transaction — the outbox is published in insertion order
   after commit, so `sport_type_detected` will always reach consumers
   first.

5. **`ParsedFitData.sport_type` default must be `SportType.UNKNOWN`
   in the dataclass.** Some FIT files may not contain a `session`
   message at all (very rare for proper FIT files, but observed in
   some corrupt or truncated files). The `Frozen=True` dataclass
   default ensures the filename is still parsed without error — the
   quality flags and `unknown` sport_type will correctly disqualify
   it from calibration.

### Architecture Interpretations

1. **Where the sport-type gate lives.** The architecture defines the
   gate as the first check inside `isCalibrationEligible` (the
   `CalibrationEligibilityService.evaluate` method). It does NOT
   place the gate at the ingestion boundary (skipping load computation
   for non-running activities). This means load computation still runs
   for non-running activities, but their scores are null because
   `data_tier = TIER_6` (and the load formulas return null for
   `TIER_6`). The architecture is deliberate: the ingestion pipeline
   is the same for all activities; the gate is what distinguishes the
   running twin-model path from the training-record-only path.

2. **`detection_confidence` semantics.** The architecture defines
   confidence as `'high' | 'low' | 'unknown'`. For FIT-extracted sports:
   - `'high'` = the FIT `sport` field was present and mappable to a
     recognised value (running, cycling, swimming, etc.). This is
     explicit athlete-declared intent.
   - `'low'` = the FIT `sport` field was present but the integer value
     is not in the mapping table (defaulted to `'other'`). This is an
     inference, not a declaration.
   - `'unknown'` = the FIT `sport` field is absent, generic (0), or
     "all" (254). The sport could not be determined.

3. **`sport_type_detection_version` is per-activity, not global.** The
   architecture says the mapping is versioned for reprocessing. Each
   Activity stores the version string that was active at ingestion
   time, so future reprocessing can identify which activities used
   an older mapping. The constant `"v1"` is the initial detection
   version; it is stored on the Activity and embedded in the
   `sport_type_detected` event.

4. **Manual-entry `sport_type`.** Manual-entry activities have no FIT
   file and therefore no sport detection is performed. The column
   default `'unknown'` is correct — the architecture says "If the
   parser cannot determine the sport, it must default to `'unknown'`"
   and manual entries have no parser invocation. The calibration gate
   rejects them through the sport-type check first, then through the
   `source == 'manual_entry'` check (which is now second). No code
   change is needed for this path — the column default handles it.

5. **The `activity_ingested` payload `sport_type` field.** The
   architecture's `activity_ingested` v1 payload is
   `{activity_id, date, duration, has_hr, has_rr, has_power, fit_file_key}`.
   The sport-type-detection document says `activity_ingested` is
   consumed with note "sport type is embedded in the Activity record".
   This means the consumer reads `sport_type` from the Activity table
   row, not from the event payload. Adding `sport_type` to the event
   payload is a convenience for consumers that do not want to re-query
   the Activity row — it does not change the event version contract
   because `activity_ingested` v1 payload is documented as a
   `{activity_id, date, duration, has_hr, has_rr, has_power, fit_file_key}`
   shape; adding a non-breaking supplementary field that downstream
   consumers may ignore is within the plan's authority (it does not
   change the required fields of the v1 contract). If this is treated
   as a contract change that requires architecture sign-off, escalate
   — but the simpler path is: the schema-level `sport_type_detected`
   event is the authoritative sport-type event, and `activity_ingested`
   need not carry it.

### Why The `data_tier = 6` Override Is In The Ingestion Service

The architecture says `sport_type != 'running' → data_tier = 6`. There
are two places this could be enforced:

- In `CalibrationEligibilityService` — but the service is stateless and
  receives only the `Activity` object; it does not currently receive or
  compute `data_tier`. Adding `data_tier` to the service's input would
  change its signature and break its established contract.
- In `ActivityIngestionService._run_ingestion_pipeline` — where
  `data_tier` is already inferred and available for override.

The architecture says `CalibrationEligibilityService` treats
`non-running → calibration_eligible = false AND data_tier = 6`. The
service enforces `calibration_eligible = false` directly via the sport
gate. The `data_tier = 6` portion is an ingestion-layer concern: it
controls which load formula is used (TIER_6 → null scores). The
ingestion service is the correct place to override `data_tier` because
that is where `data_tier` is already computed and where it is passed to
`LoadComputationService`. The existing `data_tier in (TIER_5, TIER_6)
→ eligible = False` post-check stays — it catches running Tier-5/6
activities the gate would otherwise pass.

### Deferred Items Explicitly Not In This Plan
- Intervals.icu API `type` field mapping (deferred until auto-sync, a
  later phase).
- Manual-upload sport-selection API parameter (deferred — FIT sport
  field covers current uploads; `unknown` fallback handles missing
  sports; the UI prompt is a consumer-side enhancement).
- Coach message for `sport_type = 'unknown'` activities (deferred — a
  downstream coaching capability, not an ingestion-pipeline concern).
- Reprocessing backfill of `sport_type` for existing FIT-derived
  activities (deferred — the migration sets `unknown` + `calibration_eligible = false`
  for safety; accurate re-parse is a dedicated backfill task).
- The three surviving raw-`text()` SQL helpers in
  `ActivityIngestionService` (`_read_profile_date_of_birth`,
  `_read_athlete_preferences`, `_read_athlete_physiology`) — these are
  the deferred consistency items from Phase-2.1-P2. This plan does not
  touch them.
