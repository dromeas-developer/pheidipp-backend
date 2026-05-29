# 2d — Threshold Detection & Twin Layer 2
*HR deflection, RR inflection, Bayesian update, real threshold estimates*

## Objective

Threshold estimates move from population norms to real data-derived values.
The twin becomes meaningfully personalised for the first time. Workout targets
update to reflect the athlete's actual physiological state rather than age-graded
defaults. This is the first phase where the coaching can claim to know something
real about the athlete.

## Scope

`ThresholdUpdateService` with HR deflection algorithm and RR inflection point
detection. Bayesian update mechanism. `calibration` TwinState trigger. Confidence
transition LOW → MEDIUM → HIGH. Threshold-referenced load formulas replacing
heuristic formulas from 2b.

## Non-Goals

- Full signal cleaning pipeline before threshold detection — deferred to 5a.
  Detection in this phase works from FIT parser output with basic smoothing only,
  not the full 7-step preprocessing pipeline.
- `PlannedSegment` / `PhysiologicalSegment` segmentation — deferred to 5b.
  Threshold detection in this phase works at session level, not segment level.
- Per-athlete GAP curve — deferred to 5c.

## Architecture References

- Threshold detection signal hierarchy and all three algorithms:
  `architecture/load-and-thresholds.md` → Threshold Detection
- HR deflection algorithm requirements (≥ 3 intensity steps):
  `architecture/load-and-thresholds.md` → HR Deflection Analysis
- HRV inflection point algorithm requirements (≥ 8 minutes per intensity level):
  `architecture/load-and-thresholds.md` → HRV Inflection Point Detection
- Bayesian update formula and prior decay:
  `architecture/load-and-thresholds.md` → Bayesian Threshold Update
- Confidence transition thresholds:
  `architecture/twin-state.md` → Confidence Level Transitions
- `ftp_estimate_watts` and `vo2max_estimate` on TwinState:
  `architecture/load-and-thresholds.md` → TwinState Threshold Fields

## Dependencies

Requires 2a (FIT files stored), 2b (calibration eligibility evaluated,
TwinState Layer 1 updating), 2c (WorkoutStep exists — threshold-referenced
workout targets depend on real threshold data).

## Services & Tasks Introduced

**`ThresholdDetectionService`** (sync, Python) — runs after each calibration-eligible
session. Selects algorithm based on available signals:
- `has_rr_intervals = True` → `RrInflectionDetector.detect(rr_series, intensity_series)`
- `has_hr = True` (no RR) → `HrDeflectionDetector.detect(hr_series, intensity_series)`
- `has_power = True` → `PowerHrRatioAnalyser.analyse(power_series, hr_series)` (supplementary)
- All else → no detection; confidence does not update from this session.

Each detector returns `{lt1_estimate, lt2_estimate, confidence_weight}` or null
if session type does not produce adequate signal (fewer than 3 intensity steps
for HR deflection; fewer than 8 minutes per level for RR).

**`ThresholdBayesianUpdater`** (sync, Python) — applies detection results to
the current prior.
- `update(prior_twin_state, detection_result) → ThresholdUpdate`
- Implements the posterior mean formula from `architecture/load-and-thresholds.md`.
- Applies prior decay: observations older than 6 weeks carry reduced weight.
- Returns updated threshold values and the new confidence level.

**`TwinRecalibrationService`** (updated) — now calls `ThresholdDetectionService`
and `ThresholdBayesianUpdater` for calibration-eligible sessions.
New trigger type: `calibration` for sessions that produce a detection result.
`activity_sync` used when only Layer 1 updates. `calibration` used when Layer 2
also updates.

**Load formula upgrade:** `LoadComputationService` is updated to use threshold-
referenced formulas once a MEDIUM confidence TwinState exists. Heuristic formulas
remain the fallback for LOW confidence athletes. `ingestion_pipeline_version`
incremented to reflect the formula change. Historical activities with LOW confidence
are not reprocessed automatically — they remain on the heuristic version.

## Key Constraints

- `ThresholdDetectionService` only runs on `calibration_eligible = true` sessions.
  It must not run on manual entries, sessions without HR, or sessions under 20 minutes.
- The Bayesian update never decreases confidence — it can only maintain or increase it.
  Confidence ratchets upward as evidence accumulates.
- An `ftp_estimate_watts` is only written to TwinState when power data is available
  and the power-to-HR ratio analysis produces a result. It remains null otherwise.
- When the first MEDIUM confidence TwinState is created, the `WorkoutGenerationAgent`
  must generate subsequent workouts using updated threshold-referenced targets.
  The first message noting the threshold update is a `post_workout` type CoachingMessage
  generated without an `activity_id` — it is triggered by the confidence upgrade event.

## Done Criteria

- After four calibration-eligible sessions with HR data, `GET /athletes/{id}/twin`
  shows `confidence_level = medium` and `lt1_estimate_bpm`, `lt2_estimate_bpm`
  values that differ from the questionnaire bootstrap values.
- After two RR-interval sessions, `confidence_level = high`.
- A session without sufficient intensity variation (e.g. easy aerobic jog with no
  progression) does not produce a threshold update.
- Generated workouts for a MEDIUM confidence athlete use threshold-referenced targets
  (e.g. pace at LT2) rather than effort descriptions.
- `ftp_estimate_watts` is non-null on the TwinState of an athlete who has synced
  sessions with power data.
