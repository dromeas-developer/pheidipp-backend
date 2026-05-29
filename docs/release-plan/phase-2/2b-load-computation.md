# 2b — Load Computation & Twin Layer 1
*Three load scores, calibration eligibility, real twin recalibration*

## Objective

Compute the three load dimensions for every ingested FIT file and begin updating
the twin from real training data. For the first time the twin's fitness and fatigue
estimates reflect what the athlete has actually been doing.

## Scope

Three load score formulas (heuristic — replaced by threshold-referenced in 2d).
Calibration eligibility logic. `ingestion_pipeline_version` tagging. Twin Layer 1
recalibration from load scores. `activity_sync` TwinState trigger.

## Non-Goals

- Threshold-referenced load formulas — these replace heuristic formulas in 2d
  once threshold estimates are real-data-derived
- Signal cleaning pipeline — deferred to 5a; heuristic load computation works
  directly from FIT parser output
- Per-athlete GAP curve — deferred to 5c (requires accumulated session data)

## Architecture References

- Three load dimension formulas (heuristic version):
  `architecture/load-and-thresholds.md` → Three Load Dimensions
- Calibration eligibility five-rule gate:
  `architecture/load-and-thresholds.md` → Calibration Eligibility
- `ingestion_pipeline_version` versioning:
  `architecture/versioning.md`
- Twin Layer 1 recalibration trigger `activity_sync`:
  `architecture/twin-state.md` → Recalibration Triggers
- The reprocessing test for computed fields:
  `architecture/versioning.md` → The Reprocessing Test

## Dependencies

Requires 2a (Activity exists with `fit_file_key`; `FitData` available from parser).

## Models Modified

**`Activity`** — `aerobic_load`, `neuromuscular_load`, `structural_load` populated
(were null after 2a). `calibration_eligible` set. `ingestion_pipeline_version` set.
No new columns — all defined in 1a.

## Services & Tasks Introduced

**`LoadComputationService`** (sync, Python) — computes three load scores from FitData.
- `compute(fit_data, twin_state) → LoadScores` — returns aerobic, neuromuscular,
  structural scores. At this stage uses heuristic formulas (see arch reference).
  `twin_state` is used only for data tier determination; threshold values not yet
  used in load formulas (that changes in 2d).

**`CalibrationEligibilityService`** (sync, Python) — evaluates the five-rule gate.
- `evaluate(activity, fit_data) → (bool, list[str])` — returns eligible flag
  and list of disqualifying reasons if ineligible.
  Five rules: `has_hr`, source not manual, duration ≥ 20 minutes moving time,
  no disqualifying quality_flags, session type produces usable signal.

**`TwinRecalibrationService`** (sync, Python) — updates twin from new activity.
- `recalibrate_layer1(athlete_id, activity) → TwinState` — reads the most recent
  TwinState, applies Banister model update with the new load scores, creates and
  inserts a new TwinState with `trigger = activity_sync`.
  Uses population time constants (fitness ~42 days, fatigue ~7 days) at this stage.
  Returns the new TwinState.

`LoadComputationService` and `CalibrationEligibilityService` are called within
`FitIngestionTask` from 2a, extending it:

Updated `FitIngestionTask` pipeline:
1-5. (as in 2a)
6. Compute load scores via `LoadComputationService`
7. Evaluate calibration eligibility via `CalibrationEligibilityService`
8. Update Activity with load scores, calibration_eligible, ingestion_pipeline_version
9. If `calibration_eligible = true`: enqueue `TwinRecalibrationTask`

**`TwinRecalibrationTask`** (async worker) — runs `TwinRecalibrationService`.
Runs after ingestion to avoid blocking the ingestion pipeline.

## Endpoints Modified

- `GET /athletes/{athlete_id}/activities/{activity_id}` — now returns load scores
  and `calibration_eligible` flag (were null in 2a).

## Key Constraints

- Load scores are computed from the stored FIT file data, never from averaged values.
  `LoadComputationService` must receive raw records from `FitParserService`, not summary stats.
- Load scores are persisted on `Activity` because they are queried frequently across
  weeks of history. This passes the reprocessing test — they can be recomputed from
  the FIT file, but the query performance justification exists.
- Every new TwinState appended — `TwinRecalibrationService` never updates the existing
  record.
- The pipeline version string is written to `ingestion_pipeline_version` at creation.
  If the formula changes, the version increments and historical activities can be
  reprocessed through the new formula using their `fit_file_key`.
- Manual entries (`source = manual_entry`) always have `calibration_eligible = false`
  and null load scores. `LoadComputationService` is never called for them.

## Done Criteria

- After syncing a session, its Activity has non-null `aerobic_load`,
  `neuromuscular_load`, `structural_load` and a correctly set `calibration_eligible`.
- A calibration-eligible session triggers a new TwinState with `trigger = activity_sync`
  and an updated `fitness_score`.
- An uncalibration-eligible session (e.g. too short, manual entry) does not create
  a new TwinState.
- `GET /athletes/{athlete_id}/twin/history` shows the TwinState series growing
  with each calibration-eligible session.
- Sessions with `source = manual_entry` have null load scores and `calibration_eligible = false`.
