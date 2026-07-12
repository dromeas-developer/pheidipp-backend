# Execution Manifest — Phase-2.3-P1 — Batch 4

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Batch:             4 of 4
Manifest Version:  v1
Generated At:      2026-07-10T00:00:00Z
Source Plan Lines: 598
Manifest Lines:    142

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Implement the LT1 passive inference methods (natural training analysis, HR drift,
HR recovery) to provide supplementary LT1 estimates from historical and
per-session data analysis.

## Preconditions
Batches 1 through 3 are complete; their Batch Success Criteria hold

## Steps
### Step 11 — Implement LT1 passive inference methods
[OWNER: Coder] Implement LT1 passive inference methods on
`ThresholdDetectionService`. Per `lt1-detection.md` methods 3–5:
- **Natural Training Analysis** (cross-session): Query
  `ActivityRepository` for recent easy runs (≥3 with consistent HR
  patterns, ±5 bpm across runs). Use the `hr_30s_mean` or `hr_60s_mean`
  from the cleaned stream to compute mean HR per easy run. If consistent,
  use that HR as an LT1 estimate. Source: `TRAINING_HR_DEFLECTION`,
  weight: 0.5 (lower confidence than active tests). This method queries
  historical activities and their cleaned streams — it does NOT require
  the current activity to be an easy run; it runs as a supplementary
  analysis after per-session algorithms.
- **HR Drift** (per-session): Identify steady-state segments (constant
  pace, constant grade) ≥20 min. Compute HR at start (first 5 min) and
  end (last 5 min). If HR drift > 5 bpm, intensity is likely above LT1.
  If HR drift < 2 bpm, intensity is likely below LT1. Use this as a
  constraint to refine the LT1 estimate, not a direct observation. Source:
  `TRAINING_HR_DEFLECTION`, weight: 1.0.
- **HR Recovery** (per-session): After hard effort (above LT2 or near
  max HR), compute HR at cessation and HR at 2 min into recovery. HR
  recovery = HR_start - HR_2min. Faster recovery (>30 bpm in 2 min)
  suggests lower LT1; slower recovery (<20 bpm in 2 min) suggests higher
  LT1. Source: `TRAINING_HR_DEFLECTION`, weight: 0.5 (supplementary).
These methods produce `ThresholdObservation` objects for `LT1_HR` only.
They run as supplementary analysis after the per-session algorithms (7–9).

## Context Needed
Step 11:
  Primary:    `docs/architecture/02-computations/lt1-detection.md` (methods 3,
              4, 5), `app/repositories/activity_repository.py` (needs
              `get_recent_activities_for_athlete` — add if missing),
              output of Step 6
  Secondary:  `app/repositories/physiology_measurement_repository.py` (output of
              Step 4 — for querying existing LT1 observations as context)
  Fallback:   —
  Forbidden:  —

## Relevant Architecture Contracts
- `02-computations/threshold-detection.md` — IMPLEMENTS (3 algorithms, signal
  selection, confidence weight outputs)
- `02-computations/lt1-detection.md` — IMPLEMENTS (passive inference methods:
  natural training analysis, HR drift, HR recovery)
- `02-computations/physiology-update.md` — DEPENDS ON (observation weights by
  source define the weight field on `ThresholdObservation`)
- `02-computations/evidence-mapping.md` — DEPENDS ON (evidence source → metric
  mapping defines which parameters each source contributes to)
- `01-entities/athlete-physiology.md` — DEPENDS ON (PhysiologyMeasurement
  append-only table, MeasurementSource enum, PhysiologyParameterState shape)
- `00-foundations/confidence-model.md` — DEPENDS ON (evidence weight thresholds
  4.0/8.0; observation weights by source)
- `02-computations/signal-cleaning.md` — DEPENDS ON (CleanedStream shape
  consumed as input; available_channels determines algorithm selection)
- `01-entities/raw-sensor-stream.md` — DEPENDS ON (RawSensorStream row provides
  the cleaned-stream object key)

## Relevant Invariants
- "Threshold detection only runs for `calibration_eligible = true` activities"
  (sub-phase invariant)
- "Easy runs are calibration-eligible for load computation but do NOT provide
  threshold detection evidence (insufficient intensity variation for HR
  deflection/RR inflection algorithms)" (data-tiers invariant)
- "`PhysiologyMeasurement` is append-only" (athlete-physiology storage model)
- "Confidence is **per-metric**: each physiological parameter accumulates
  evidence independently. A field test for LT2 increases LT2 confidence, not
  LT1 confidence." (confidence-model invariant)
- "Evidence weight thresholds (4.0 for MEDIUM, 8.0 for HIGH) are initial
  defaults based on observation weights." (confidence-model invariant)
- "Per-metric evidence accumulation — a session contributes to specific
  metrics only" (sub-phase invariant)
- "For athletes with RR intervals, `training_rr_inflection` observations have
  higher weight (2.5 vs 1.0)." (sub-phase exit gate)
- "For athletes with power, `training_power_hr_ratio` observations contribute
  to CP estimate." (sub-phase exit gate)

## Relevant Event Contracts
This plan does not produce or consume events. `ThresholdDetectionService`
produces `ThresholdObservation` data structures consumed by
`PhysiologyUpdateService` (Plan P2). No events are fired at this layer.

## Relevant Notes
### Implementation Clarifications
- **Observation weights are fixed constants from `evidence-mapping.md`**, not
  computed dynamically. `training_hr_deflection` = 1.0,
  `training_rr_inflection` = 2.5, `training_power_hr_ratio` = 1.5. These are
  the same values used by `PhysiologyUpdateService` (Plan P2) for the Bayesian
  update. The `ThresholdObservation.weight` field carries this value so
  `PhysiologyUpdateService` does not need to re-derive it.
- **`confidence_weight` on `ThresholdObservation` is algorithm-specific** (0.0
  to 1.0) and is distinct from the evidence `weight` (which is source-specific
  and comes from the evidence-mapping table). The `confidence_weight` reflects
  signal quality (e.g., R² for HR deflection, RMSSD signal quality for RR
  inflection). It is stored on `PhysiologyMeasurement` for audit but does NOT
  affect the Bayesian update — the evidence `weight` does.
- **Natural training analysis queries historical activities**: this method
  needs `ActivityRepository` to support querying recent easy runs by
  `session_type` or by HR patterns. The current `ActivityRepository` does not
  have this method — add a `get_recent_activities_for_athlete(athlete_id,
  sport_type, limit)` method that returns recent running activities with
  `calibration_eligible = true`. The method then downloads each activity's
  cleaned stream to compute mean HR. This is the most expensive algorithm —
  it should be the last one run and should fail silently if historical data
  is unavailable.

## Files Expected To Change
- [EXISTING] app/services/threshold_detection_service.py
- [EXISTING] app/repositories/activity_repository.py (add get_recent_activities_for_athlete)

## Batch Success Criteria
Batch 4 assumes Batch 3 is complete. Batch 4 complete when:
- Natural training analysis produces `LT1_HR` observation with weight 0.5
  when ≥3 easy runs with consistent HR (±5 bpm)
- HR drift method identifies steady-state segments ≥20 min and produces
  `LT1_HR` observation with weight 1.0
- HR recovery method produces `LT1_HR` observation with weight 0.5 when hard
  effort + ≥2 min recovery data available