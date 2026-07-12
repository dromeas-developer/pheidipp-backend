# Execution Manifest — Phase-2.3-P1 — Batch 2

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Batch:             2 of 4
Manifest Version:  v1
Generated At:      2026-07-10T00:00:00Z
Source Plan Lines: 598
Manifest Lines:    194

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Implement the `ThresholdObservation` dataclass, `ThresholdDetectionService`
skeleton with signal selection logic, and the `detect()` entry point to
establish the core computation engine for threshold detection.

## Preconditions
Batches 1 through 1 are complete; their Batch Success Criteria hold

## Steps
### Step 5 — Create `ThresholdObservation` dataclass
[OWNER: Coder] Create `ThresholdObservation` dataclass in a new
`app/services/threshold_detection_service.py` (or a shared types module
if the service file is large). Fields: `parameter` (PhysiologyParameter),
`observed_value` (float), `source` (MeasurementSource), `weight` (float —
from evidence-mapping table), `activity_id` (UUID), `measurement_date`
(date), `algorithm_used` (str), `confidence_weight` (float | None —
algorithm-specific 0.0–1.0). This is the data contract between
`ThresholdDetectionService` and `PhysiologyUpdateService` (Plan P2).

### Step 6 — Implement `ThresholdDetectionService`
[OWNER: Coder] Implement `ThresholdDetectionService` in
`app/services/threshold_detection_service.py`. The service is constructed
with an `AsyncSession`, `ObjectStorageClient`,
`RawSensorStreamRepository`, `ActivityRepository`,
`AthletePhysiologyRepository`, and `PhysiologyMeasurementRepository`.
The primary entry point `async def detect(self, athlete_id, activity_id)
-> list[ThresholdObservation]` performs:
- Load the Activity row; verify `calibration_eligible = true` and
  `sport_type = RUNNING` (skip silently if not — return empty list).
- Load the `RawSensorStream` row for the activity; if missing (signal
  cleaning not yet complete), return empty list (per ADR-009: downstream
  consumers handle "not yet ready" by skipping).
- Download the cleaned stream from object storage using the
  `fit_file_key` from the `RawSensorStream` row. Deserialise the gzipped
  JSON into `CleanedStream` records (reuse the deserialisation logic from
  `SignalCleaningService` — extract a shared `parse_cleaned_stream` helper
  if the existing code has one, otherwise implement inline).
- Run signal selection: determine which algorithms apply based on
  `activity.has_rr_intervals`, `activity.has_hr`, `activity.has_power`,
  and the `available_channels` from the cleaned stream.
- Execute applicable algorithms (Steps 7–10) and collect observations.
- For natural training analysis (Step 11), query historical easy runs via
  `ActivityRepository` and `PhysiologyMeasurementRepository`.
- Return the list of `ThresholdObservation` objects. The service does NOT
  write to `PhysiologyMeasurement` — that is `PhysiologyUpdateService`'s
  responsibility (Plan P2). The service does NOT mutate `AthletePhysiology`.

### Step 10 — Implement the signal selection logic
[OWNER: Coder] Implement the signal selection logic on
`ThresholdDetectionService`. Per `threshold-detection.md`:
```
if has_rr_intervals → run RR inflection (Algorithm 2)
if has_hr:
    if has_power → run HR deflection (Algorithm 1) + power-to-HR ratio (Algorithm 3)
    else → run HR deflection (Algorithm 1)
→ 'none' (no update from this session)
```
RR inflection takes priority over HR deflection when both are available
(RR is the richer signal). Both may run — RR inflection produces
higher-weight observations, HR deflection produces supplementary
observations. The power-to-HR ratio always runs alongside HR-based
detection when power is available.

## Context Needed
Step 5:
  Primary:    `app/services/signal_cleaning_service.py` (`CleanedRecord`,
              `CleanedStream` dataclasses — the shape this observation
              derives from)
  Secondary:  `app/models/enums.py` (`MeasurementSource`, `PhysiologyParameter`
              from Step 1)
  Fallback:   —
  Forbidden:  —
Step 6:
  Primary:    `app/services/signal_cleaning_service.py` (CleanedStream
              deserialisation, `CleanedRecord` shape),
              `app/repositories/raw_sensor_stream_repository.py`
              (`get_by_activity_id` method),
              `app/repositories/activity_repository.py` (`get_by_id` method),
              `app/services/object_storage_client.py` (`download_fit` method)
  Secondary:  `app/services/fit_parser_service.py` (`ParsedFitData` — for
              understanding the raw signal shape if needed for edge cases)
  Fallback:   —
  Forbidden:  `app/services/twin_recalibration_service.py` (this service does
              NOT call TwinRecalibrationService — that is Plan P3's pipeline)
Step 10:
  Primary:    `docs/architecture/02-computations/threshold-detection.md` (Signal
              Selection section), output of Steps 7–9
  Secondary:  —
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

## Files Expected To Change
- [EXISTING] app/services/threshold_detection_service.py
- [NEW] app/services/fit_parser_service.py (if needed for ParsedFitData reference)
- [EXISTING] app/models/enums.py (import PhysiologyParameter from Step 1)
- [EXISTING] app/models/physiology_measurement.py (import MeasurementSource)

## Batch Success Criteria
Batch 2 assumes Batch 1 is complete. Batch 2 complete when:
- `ThresholdObservation` dataclass exists with all specified fields
- `ThresholdDetectionService` class exists with constructor accepting
  `AsyncSession`, `ObjectStorageClient`, `RawSensorStreamRepository`,
  `ActivityRepository`, `AthletePhysiologyRepository`,
  `PhysiologyMeasurementRepository`
- `detect(athlete_id, activity_id)` method exists and returns
  `list[ThresholdObservation]`
- Signal selection logic correctly routes to algorithms based on
  `has_rr_intervals`, `has_hr`, `has_power`
- Activities with `calibration_eligible = false` or `sport_type != RUNNING`
  return an empty list
- Missing `RawSensorStream` returns an empty list (no exception raised)