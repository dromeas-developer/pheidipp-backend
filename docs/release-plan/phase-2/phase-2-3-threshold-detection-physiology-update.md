# Phase 2 — Threshold Detection & Physiology Update
## Sub-Phase ID: Phase-2.3

## Objective
Implement the threshold detection pipeline that produces physiological observations and updates `AthletePhysiology` via Bayesian update. This is the first time the twin model is updated from real training data rather than population defaults. Activities marked `calibration_eligible = true` now contribute to LT1, LT2, and CP estimates.

## Challenge Notes
The threshold detection algorithms (HR deflection, RR inflection, power-to-HR ratio) are well-defined in architecture. The key orchestration challenge is the pipeline order:

1. `SignalCleaningService` completes (Phase 2.2)
2. `ThresholdDetectionService` runs on cleaned data
3. `PhysiologyUpdateService` applies Bayesian update
4. `TwinRecalibrationService` creates new `TwinState`

**Important:** This phase does NOT create comparable sessions — that requires history, which comes after the first few calibration-eligible sessions.

**Deferral:** Lab test and field test ingestion (high-weight evidence sources) are deferred to a later phase. Phase 2 focuses on training-derived evidence accumulation.

## Capabilities Delivered
- `ThresholdDetectionService` implements HR deflection algorithm for sessions with ≥3 intensity steps
- `ThresholdDetectionService` implements RR inflection algorithm for sessions with RR and ≥8 min/intensity level
- `ThresholdDetectionService` implements power-to-HR ratio analysis for power-enabled athletes
- `PhysiologyUpdateService` applies Bayesian update to `AthletePhysiology` posterior estimates
- `TwinRecalibrationService` creates new `TwinState` records with updated `metric_confidence`
- `lt1-detection.md` computation logic implemented (passive LT1 inference)
- `physiology-update.md` computation logic implemented
- Confidence transitions LOW → MEDIUM trigger for LT1/LT2 HR when evidence weight ≥ 4.0

## Architectural Contracts Required
- `02-computations/threshold-detection.md`
- `02-computations/lt1-detection.md`
- `02-computations/physiology-update.md`
- `01-entities/athlete-physiology.md`
- `01-entities/twin-state.md`
- `00-foundations/confidence-model.md`
- `02-computations/evidence-mapping.md`

## Vision References Required
- `twin/training-zones.md` — threshold definitions and intent ranges
- `twin/confidence-and-uncertainty.md` — honest confidence communication
- `twin/load-fatigue.md` — three load dimensions and data tier implications

## Upstream Dependencies
- Phase-2.1 — `sport_type` gate ensures only running activities can be calibration-eligible; Activity schema with sport_type field
- Phase-2.2 — Cleaned sensor streams required for threshold detection quality; only for running activities with `calibration_eligible = true`
- Phase-1.2c — `TwinState` and `AthletePhysiology` schema exist

## Downstream Enablement
- Phase-2.4 — Comparable session matching uses `TwinState.metric_confidence` for similarity scoring
- Phase-2.5 — Objective updates use threshold estimates to evaluate session targets
- Phase-2.6 — Power profile computation uses updated `AthletePhysiology.cp` for zone mapping

## Invariants To Preserve
- Per-metric evidence accumulation — a session contributes to specific metrics only
- Bayesian update with 42-day prior decay for evidence staleness
- Confidence is monotonic (only increases, never decreases)
- Observation thresholds: 4.0 for LOW→MEDIUM, 8.0 for MEDIUM→HIGH (per metric)
- `physiology_updated` event fires only when posterior shifts by > 1 bpm (to avoid noise)
- Threshold detection only runs for `calibration_eligible = true` activities

## Exit Gate
- After uploading a calibration-eligible session with ≥3 intensity steps, `TwinState` shows updated `metric_confidence.lt2_hr` with `prior_weight > 0`.
- After sufficient sessions (4+ HR deflection-eligible), `metric_confidence.lt2_hr` transitions to "medium" when `prior_weight >= 4.0`.
- `AthletePhysiology.lt2.hr.value` shows posterior mean shifted from population default toward observed values.
- For athletes with RR intervals, `training_rr_inflection` observations have higher weight (2.5 vs 1.0).
- For athletes with power, `training_power_hr_ratio` observations contribute to CP estimate.