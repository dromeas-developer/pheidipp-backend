# Execution Manifest — Phase-2.3-P1 — Batch 3

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Batch:             3 of 4
Manifest Version:  v1
Generated At:      2026-07-10T00:00:00Z
Source Plan Lines: 598
Manifest Lines:    184

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Implement the three core detection algorithms (HR deflection, RR inflection,
power-to-HR ratio) to produce threshold observations from cleaned sensor
streams.

## Preconditions
Batches 1 through 2 are complete; their Batch Success Criteria hold

## Steps
### Step 7 — Implement the HR deflection algorithm
[OWNER: Coder] Implement the HR deflection algorithm as a method on
`ThresholdDetectionService`. Per `threshold-detection.md` Algorithm 1:
- Segment the cleaned stream into intensity bins using GAP
  (`gap_sec_per_km` from `CleanedRecord`) or power (`power_w`).
- For each bin: compute mean HR and mean intensity.
- Fit linear HR-intensity regression across bins.
- LT1: first bin where slope increases above baseline (first departure from
  linearity).
- LT2: second, steeper departure.
- Return null (no observation) if < 3 distinct intensity steps or R² < 0.80.
- If successful, produce two `ThresholdObservation` objects: one for
  `LT1_HR` and one for `LT2_HR`, both with source
  `TRAINING_HR_DEFLECTION` and weight 1.0 (from evidence-mapping).
- Algorithm confidence weight: derived from R² value (higher R² = higher
  confidence).

### Step 8 — Implement the HRV/RR inflection algorithm
[OWNER: Coder] Implement the HRV/RR inflection algorithm as a method on
`ThresholdDetectionService`. Per `threshold-detection.md` Algorithm 2:
- Clean RR series (artifact detection; values outside ±20% of rolling
  median removed — the cleaned stream from Phase 2.2 already has this
  applied, so this is a verification pass, not a re-cleaning).
- Compute RMSSD in 60-second rolling windows throughout the session using
  the `rr_ms` field from `CleanedRecord`.
- Align RMSSD time-series with intensity time-series (GAP or power).
- LT1: first significant decrease in RMSSD as intensity rises (threshold:
  RMSSD drops > 15% below pre-effort baseline within the window).
- LT2: second inflection; typically less distinct; requires more data.
- Return null if < 8 minutes at each required intensity level.
- If successful, produce two `ThresholdObservation` objects: one for
  `LT1_HR` and one for `LT2_HR`, both with source
  `TRAINING_RR_INFLECTION` and weight 2.5 (from evidence-mapping — higher
  than HR deflection because RR is a richer signal).

### Step 9 — Implement the power-to-HR ratio algorithm
[OWNER: Coder] Implement the power-to-HR ratio algorithm as a method on
`ThresholdDetectionService`. Per `threshold-detection.md` Algorithm 3:
- Used alongside HR-based detection when power data is available. Not
  standalone — only runs when `has_power = true`.
- At sub-threshold: power/HR ratio is stable within a session.
- Above LT2: ratio begins sustained decline (cardiovascular cost rises
  faster than output).
- Detect the ratio breakpoint.
- Only produce an observation when the power series shows a clear ratio
  breakpoint.
- If successful, produce one `ThresholdObservation` for `CP` with source
  `TRAINING_POWER_HR_RATIO` and weight 1.5 (from evidence-mapping).

## Context Needed
Step 7:
  Primary:    `docs/architecture/02-computations/threshold-detection.md`
              (Algorithm 1 specification), output of Step 6 (service skeleton)
  Secondary:  `app/services/signal_cleaning_service.py` (CleanedRecord fields:
              `hr_bpm`, `gap_sec_per_km`, `power_w`, `hr_30s_mean`)
  Fallback:   —
  Forbidden:  —
Step 8:
  Primary:    `docs/architecture/02-computations/threshold-detection.md`
              (Algorithm 2 specification), output of Step 6
  Secondary:  `app/services/signal_cleaning_service.py` (CleanedRecord fields:
              `rr_ms`, `hr_bpm`)
  Fallback:   —
  Forbidden:  —
Step 9:
  Primary:    `docs/architecture/02-computations/threshold-detection.md`
              (Algorithm 3 specification), output of Step 6
  Secondary:  `app/services/signal_cleaning_service.py` (CleanedRecord fields:
              `power_w`, `hr_bpm`, `power_30s_mean`)
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
- **Cleaned stream deserialisation**: `SignalCleaningService` serialises the
  `CleanedStream` to gzipped JSON and uploads to object storage. The
  `ThresholdDetectionService` must download and deserialise this. Extract a
  shared `parse_cleaned_stream(raw_bytes) -> CleanedStream` helper if
  `SignalCleaningService` already has deserialisation logic; otherwise
  implement it in the threshold detection service. The `CleanedRecord` and
  `CleanedStream` dataclasses from `signal_cleaning_service.py` define the
  shape.
- **Intensity bin segmentation quality**: the HR deflection algorithm depends
  on clean intensity bin segmentation. GAP values from the cleaned stream are
  in `sec_per_km` (higher = slower). The segmentation must produce bins with
  sufficient HR samples per bin — bins with >80% null HR values should be
  skipped per the signal cleaning null-propagation invariant.

## Files Expected To Change
- [EXISTING] app/services/threshold_detection_service.py

## Batch Success Criteria
Batch 3 assumes Batch 2 is complete. Batch 3 complete when:
- HR deflection algorithm produces `LT1_HR` and `LT2_HR` observations with
  source `TRAINING_HR_DEFLECTION` and weight 1.0 when ≥3 intensity steps and
  R² ≥ 0.80
- HR deflection returns no observations when <3 steps or R² < 0.80
- RR inflection algorithm produces `LT1_HR` and `LT2_HR` observations with
  source `TRAINING_RR_INFLECTION` and weight 2.5 when RR data and ≥8 min per
  level
- Power-to-HR ratio algorithm produces `CP` observation with source
  `TRAINING_POWER_HR_RATIO` and weight 1.5 when power data shows clear
  breakpoint