# Phase 2 — Real Data
*FIT ingestion, load computation, structured workouts, threshold detection*

## Hypothesis

Does the coaching feel materially better when it reads actual training data?
Threshold estimates should visibly shift from questionnaire defaults. Workout
targets should be credible. Post-workout analysis should reference specific
execution data from the FIT file.

## Twin State at Completion

Layer 1 (fitness/fatigue) updating from real load data. Layer 2 (thresholds)
at MEDIUM confidence for athletes with HR data; HIGH for athletes with RR intervals
or one dedicated calibration session.

## Sub-Phases

| Sub-phase | Title | Key deliverable |
|---|---|---|
| 2a | FIT Ingestion Pipeline | intervals.icu integration, async FIT processing, Activity lean model |
| 2b | Load Computation & Twin L1 | Three load scores, calibration eligibility, twin real data update |
| 2c | Structured Workout Generation | PhysiologicalIntentState, WorkoutStep, two-column targets |
| 2d | Threshold Detection & Twin L2 | HR deflection, RR inflection, Bayesian update, MEDIUM/HIGH confidence |

## Done Criteria

- Sync a real workout from intervals.icu and receive a post-workout analysis that
  references specific execution patterns from the actual FIT file.
- After four calibration-eligible sessions with HR data, threshold estimates visibly
  shift from questionnaire defaults. TwinState confidence transitions to MEDIUM.
- Day-of workout targets are expressed using the athlete's data tier
  (power targets for Tier 1-2, pace for Tier 3-4, effort for Tier 5-6) and
  reflect current threshold estimates rather than population norms.
- Workout structure uses `WorkoutStep` records with `physiological_intent` — not
  a JSON blob.

## Go / No-Go for Phase 3

- Every synced Activity has a `fit_file_key`. No Activity commits without it.
- Ingestion pipeline runs without manual intervention on a schedule.
- Duplicate detection works — syncing the same session twice creates one Activity.
- Twin Layer 1 updates are auditable — each recalibration creates a new TwinState.
