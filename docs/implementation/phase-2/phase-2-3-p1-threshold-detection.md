# Implementation Plan: Phase-2.3 — Threshold Detection Service
## Plan ID: Phase-2.3-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-2.3
Sub-Phase Title: Threshold Detection & Physiology Update

## Objective
Implement the `ThresholdDetectionService` — the computation engine that
analyses cleaned sensor streams from calibration-eligible running activities
and produces physiological threshold observations (LT1 HR, LT2 HR, CP).
This plan also introduces the `PhysiologyMeasurement` model and
`PhysiologyParameter` enum that the observation history depends on. This is
the first plan in the sub-phase; Plans P2 (PhysiologyUpdateService) and P3
(TwinRecalibrationService extension + pipeline integration) depend on the
components built here.

## Scope
- `PhysiologyParameter` enum (lt1_hr, lt1_power, lt1_pace, lt2_hr, lt2_power,
  lt2_pace, cp, vo2max_ml_kg_min, vo2max_power, max_hr)
- `PhysiologyMeasurement` model — append-only observation history table
- `PhysiologyMeasurementRepository` — insert and range/parameter queries
- Alembic migration for the `physiology_measurements` table
- `ThresholdDetectionService` implementing three detection algorithms:
  - HR deflection (≥3 intensity steps, R² ≥ 0.80)
  - HRV/RR inflection (RR data, ≥8 min per intensity level)
  - Power-to-HR ratio (power-enabled athletes, supplementary CP only)
- LT1 passive inference methods from `lt1-detection.md`:
  - Natural training analysis (cross-session, ≥3 easy runs with consistent HR)
  - HR drift (per-session, steady-state ≥20 min)
  - HR recovery (per-session, hard effort + ≥2 min recovery)
- Signal selection logic (which algorithm applies based on available signals)
- Observation data structures (`ThresholdObservation`) carrying parameter,
  observed value, source, weight, activity_id, measurement_date, algorithm,
  and algorithm confidence
- Reading cleaned streams from object storage via `RawSensorStreamRepository`
  and `ObjectStorageClient`

## Out Of Scope
- `PhysiologyUpdateService` (Bayesian update) — Plan P2
- `AthletePhysiology` posterior mutation — Plan P2
- `TwinRecalibrationService` calibration trigger extension — Plan P3
- Worker task and pipeline wiring — Plan P3
- Event firing (`physiology_updated`, `twin_recalibrated`) — Plans P2/P3
- MAF Test and Controlled Progression Test (active field test protocols) —
  deferred per sub-phase: "Lab test and field test ingestion deferred"
- Lab test and field test manual ingestion endpoints — deferred
- API endpoints for physiology/measurements — deferred (architecture defines
  them but sub-phase focuses on training-derived pipeline)
- Segmentation (steps 5–7 of signal cleaning) — deferred to later sub-phase

## Architecture Contracts
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

## Invariants
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

## Implementation Steps

1. [OWNER: Coder] Add `PhysiologyParameter` enum to `app/models/enums.py` with
   values: `LT1_HR`, `LT1_POWER`, `LT1_PACE`, `LT2_HR`, `LT2_POWER`,
   `LT2_PACE`, `CP`, `VO2MAX_ML_KG_MIN`, `VO2MAX_POWER`, `MAX_HR`. Follow the
   existing `str, Enum` pattern used by `MeasurementSource`. Register the enum
   in `app/models/__init__.py` imports.

2. [OWNER: Coder] Create `PhysiologyMeasurement` model in
   `app/models/physiology_measurement.py`. Append-only table
   `physiology_measurements` with columns: `id` (UUID PK), `athlete_id`
   (FK → athletes, CASCADE), `activity_id` (FK → activities, SET NULL — null
   for lab/field test measurements), `parameter` (PhysiologyParameter enum,
   non-native String), `observed_value` (Float, non-null), `source`
   (MeasurementSource enum, non-native String), `measurement_date` (Date,
   non-null), `algorithm_used` (String(64), nullable — null for manual
   entries), `confidence_weight` (Float, nullable — algorithm-specific
   confidence 0.0–1.0), `raw_data_reference` (String(512), nullable),
   `notes` (Text, nullable), `created_at` (DateTime, server_default=now()).
   Indexes: `(athlete_id, measurement_date DESC)` for history queries,
   `(athlete_id, parameter, source)` for dedup lookup. No UPDATE/DELETE
   methods on the model. Register in `app/models/__init__.py`.

3. [OWNER: Coder] Generate Alembic migration for the
   `physiology_measurements` table. The migration creates the table with all
   columns and indexes from Step 2. Follow the existing migration naming
   convention (`phase_2_3_p1_physics_measurement.py`).

4. [OWNER: Coder] Create `PhysiologyMeasurementRepository` in
   `app/repositories/physiology_measurement_repository.py`. Expose:
   `insert(measurement)` (flush, no commit), `get_by_athlete(athlete_id,
   limit)` (newest first), `get_by_athlete_and_parameter(athlete_id,
   parameter, limit)`, `get_recent_for_parameter(athlete_id, parameter,
   source, from_date, limit)` (for dedup detection and natural training
   analysis queries). No update/delete methods. Register in
   `app/repositories/__init__.py`.

5. [OWNER: Coder] Create `ThresholdObservation` dataclass in a new
   `app/services/threshold_detection_service.py` (or a shared types module
   if the service file is large). Fields: `parameter` (PhysiologyParameter),
   `observed_value` (float), `source` (MeasurementSource), `weight` (float —
   from evidence-mapping table), `activity_id` (UUID), `measurement_date`
   (date), `algorithm_used` (str), `confidence_weight` (float | None —
   algorithm-specific 0.0–1.0). This is the data contract between
   `ThresholdDetectionService` and `PhysiologyUpdateService` (Plan P2).

6. [OWNER: Coder] Implement `ThresholdDetectionService` in
   `app/services/threshold_detection_service.py`. The service is constructed
   with an `AsyncSession`, `ObjectStorageClient`,
   `RawSensorStreamRepository`, `ActivityRepository`,
   `AthletePhysiologyRepository`, `PhysiologyMeasurementRepository`, and
   optionally `PlannedSessionRepository` (required only by the natural
   training analysis method in Step 11 — see the Implementation
   Clarifications note on `session_type` for the reason). The
   `PlannedSessionRepository` parameter defaults to `None`; when `None`,
   natural training analysis is skipped silently (returns `[]`).
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

7. [OWNER: Coder] Implement the HR deflection algorithm as a method on
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

8. [OWNER: Coder] Implement the HRV/RR inflection algorithm as a method on
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

9. [OWNER: Coder] Implement the power-to-HR ratio algorithm as a method on
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

10. [OWNER: Coder] Implement the signal selection logic on
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

11. [OWNER: Coder] Implement LT1 passive inference methods on
    `ThresholdDetectionService`. Per `lt1-detection.md` methods 3–5:
    - **Natural Training Analysis** (cross-session): Query
      `ActivityRepository` for recent running activities, then filter to
      easy / recovery runs by loading each activity's linked `PlannedSession`
      via `PlannedSessionRepository` and checking `session_type` (the
      `session_type` field lives on `PlannedSession`, NOT on `Activity` —
      `Activity` has only a `planned_session_id` FK). Requires ≥3 easy /
      recovery runs with consistent HR patterns (±5 bpm across runs). Use
      the `hr_30s_mean` or `hr_60s_mean` from the cleaned stream to compute
      mean HR per easy run. If consistent, use that HR as an LT1 estimate.
      Source: `TRAINING_HR_DEFLECTION`, weight: 0.5 (lower confidence than
      active tests). This method queries historical activities and their
      cleaned streams — it does NOT require the current activity to be an
      easy run; it runs as a supplementary analysis after per-session
      algorithms. If `PlannedSessionRepository` was not provided to the
      constructor, this method returns `[]` (skips silently).
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

12. [OWNER: Test Architect] Generate test files and update the test manifest
    for Phase 2.3 P1. Tests include:
    - Unit tests for each algorithm (HR deflection, RR inflection,
      power-to-HR ratio) with synthetic cleaned stream data.
    - Unit tests for LT1 passive inference methods with synthetic data.
    - Unit tests for signal selection logic.
    - Integration test for `PhysiologyMeasurementRepository` CRUD.
    - Integration test for `ThresholdDetectionService.detect()` with a mock
      cleaned stream — verifies the correct observations are produced for
      each signal combination.
    - Test manifest entry: `tests/test-manifest/phase-2-3.yaml`.

## Event Contracts
This plan does not produce or consume events. `ThresholdDetectionService`
produces `ThresholdObservation` data structures consumed by
`PhysiologyUpdateService` (Plan P2). No events are fired at this layer.

## Pseudocode

```
ThresholdDetectionService.detect(athlete_id, activity_id):
    activity = activities.get_by_id(activity_id)
    if not activity.calibration_eligible or activity.sport_type != RUNNING:
        return []

    raw_stream = raw_streams.get_by_activity_id(activity_id)
    if raw_stream is None:
        return []  # signal cleaning not yet complete

    cleaned_bytes = object_storage.download_fit(raw_stream.fit_file_key)
    stream = parse_cleaned_stream(cleaned_bytes)

    observations = []

    # Signal selection
    if activity.has_rr_intervals and stream.available_channels.rr_intervals:
        observations += _rr_inflection(stream, activity)
    if activity.has_hr:
        observations += _hr_deflection(stream, activity)
        if activity.has_power and stream.available_channels.power:
            observations += _power_hr_ratio(stream, activity)

    # LT1 passive inference (supplementary)
    observations += _hr_drift(stream, activity)
    observations += _hr_recovery(stream, activity)
    observations += _natural_training_analysis(athlete_id, activity)

    return observations


_hr_deflection(stream, activity):
    bins = _segment_into_intensity_bins(stream, min_steps=3)
    if len(bins) < 3:
        return []
    regression = _fit_hr_intensity_regression(bins)
    if regression.r_squared < 0.80:
        return []
    lt1_hr = _detect_first_departure(regression)
    lt2_hr = _detect_second_departure(regression)
    observations = []
    if lt1_hr is not None:
        observations.append(ThresholdObservation(
            parameter=LT1_HR, observed_value=lt1_hr,
            source=TRAINING_HR_DEFLECTION, weight=1.0,
            algorithm_used="hr_deflection_v1",
            confidence_weight=regression.r_squared))
    if lt2_hr is not None:
        observations.append(ThresholdObservation(
            parameter=LT2_HR, observed_value=lt2_hr,
            source=TRAINING_HR_DEFLECTION, weight=1.0,
            algorithm_used="hr_deflection_v1",
            confidence_weight=regression.r_squared))
    return observations


_rr_inflection(stream, activity):
    rr_series = _extract_rr_series(stream)
    if not _meets_min_duration_per_level(rr_series, min_minutes=8):
        return []
    rmssd_series = _compute_rolling_rmssd(rr_series, window_s=60)
    intensity_series = _extract_intensity_series(stream)
    lt1_hr = _detect_rmssd_drop(rmssd_series, intensity_series, threshold_pct=15)
    lt2_hr = _detect_second_rmssd_inflection(rmssd_series, intensity_series)
    observations = []
    if lt1_hr is not None:
        observations.append(ThresholdObservation(
            parameter=LT1_HR, observed_value=lt1_hr,
            source=TRAINING_RR_INFLECTION, weight=2.5,
            algorithm_used="rr_inflection_v1",
            confidence_weight=_signal_quality(rmssd_series)))
    if lt2_hr is not None:
        observations.append(ThresholdObservation(
            parameter=LT2_HR, observed_value=lt2_hr,
            source=TRAINING_RR_INFLECTION, weight=2.5,
            algorithm_used="rr_inflection_v1",
            confidence_weight=_signal_quality(rmssd_series)))
    return observations


_power_hr_ratio(stream, activity):
    ratio_series = _compute_power_hr_ratio(stream)
    breakpoint = _detect_ratio_breakpoint(ratio_series)
    if breakpoint is None:
        return []
    cp_watts = _estimate_cp_from_breakpoint(breakpoint)
    return [ThresholdObservation(
        parameter=CP, observed_value=cp_watts,
        source=TRAINING_POWER_HR_RATIO, weight=1.5,
        algorithm_used="power_hr_ratio_v1",
        confidence_weight=_breakpoint_confidence(breakpoint))]


_natural_training_analysis(athlete_id, current_activity):
    easy_runs = activities.get_recent_easy_runs(athlete_id, limit=10)
    if len(easy_runs) < 3:
        return []
    mean_hrs = [_compute_mean_hr_for_activity(run) for run in easy_runs]
    if _std_dev(mean_hrs) > 5.0:  # ±5 bpm consistency
        return []
    lt1_estimate = mean(mean_hrs)
    return [ThresholdObservation(
        parameter=LT1_HR, observed_value=lt1_estimate,
        source=TRAINING_HR_DEFLECTION, weight=0.5,
        algorithm_used="natural_training_v1",
        confidence_weight=None)]
```

## Testing Requirements
- Given a cleaned stream with ≥3 distinct intensity steps and R² ≥ 0.80,
  `ThresholdDetectionService.detect()` returns observations for `LT1_HR` and
  `LT2_HR` with source `TRAINING_HR_DEFLECTION` and weight 1.0.
- Given a cleaned stream with <3 intensity steps, HR deflection returns no
  observations.
- Given a cleaned stream with RR data and ≥8 min per intensity level,
  `detect()` returns observations for `LT1_HR` and `LT2_HR` with source
  `TRAINING_RR_INFLECTION` and weight 2.5.
- Given a cleaned stream with power data showing a clear ratio breakpoint,
  `detect()` returns an observation for `CP` with source
  `TRAINING_POWER_HR_RATIO` and weight 1.5.
- Given an activity with `calibration_eligible = false`, `detect()` returns
  an empty list.
- Given an activity with no `RawSensorStream` (signal cleaning not yet
  complete), `detect()` returns an empty list.
- Given ≥3 easy runs with consistent HR (±5 bpm), natural training analysis
  produces an `LT1_HR` observation with weight 0.5.
- `PhysiologyMeasurementRepository.insert()` persists a row and
  `get_by_athlete()` retrieves it; no update/delete methods exist on the
  repository.
- `PhysiologyParameter` enum has all 10 values and is registered in
  `app/models/__init__.py`.

## Notes

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
- **Natural training analysis queries historical activities**: this method
  needs `ActivityRepository` to support querying recent running activities.
  Add a `get_recent_activities_for_athlete(athlete_id, sport_type, limit)`
  method that returns recent running activities with
  `calibration_eligible = true`. The method then downloads each activity's
  cleaned stream to compute mean HR. This is the most expensive algorithm —
  it should be the last one run and should fail silently if historical data
  is unavailable.
- **`session_type` lives on `PlannedSession`, not `Activity`**: the
  `Activity` model has a `planned_session_id` FK (nullable) but no
  `session_type` column. To filter activities by "easy run" or "recovery
  run", the natural training analysis method must load each candidate
  activity's linked `PlannedSession` via `PlannedSessionRepository.get_by_id`
  and check `planned.session_type`. This is why `PlannedSessionRepository`
  is a required constructor parameter for full functionality — without it,
  natural training analysis is skipped. The parameter is optional (defaults
  to `None`) so unit tests exercising only the per-session algorithms do
  not need to wire it. Plan P3 (pipeline wiring) MUST pass
  `PlannedSessionRepository` to the constructor when building the service
  in the `threshold_detection` worker task.
- **`measurement_date` source**: the `measurement_date` field on
  `ThresholdObservation` (and subsequently on `PhysiologyMeasurement`)
  MUST be set to `activity.activity_date` — the date the activity occurred,
  not the date the detection ran. This is the semantically correct choice:
  the observation reflects a physiological state measured during the
  activity, so the measurement date is the activity date.

### Known Risks
- **Cleaned stream availability**: ADR-009 explicitly notes that
  `ThresholdDetectionService` must handle the case where `RawSensorStream`
  does not yet exist (signal cleaning not yet complete). The service returns
  an empty observation list — it does NOT raise. The pipeline (Plan P3) will
  only enqueue threshold detection after signal cleaning commits, but retry
  timing means the stream might not be available on the first attempt.
- **Intensity bin segmentation quality**: the HR deflection algorithm depends
  on clean intensity bin segmentation. GAP values from the cleaned stream are
  in `sec_per_km` (higher = slower). The segmentation must produce bins with
  sufficient HR samples per bin — bins with >80% null HR values should be
  skipped per the signal cleaning null-propagation invariant.
- **RR inflection LT2 detection is less distinct than LT1**: the architecture
  notes "LT2: second inflection; typically less distinct; requires more
  data." The algorithm should return null for LT2 when the second inflection
  is ambiguous rather than producing a low-confidence observation.

## Coder Handoff Notes

### Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 [OWNER: Coder] — includes
          migration generation (Step 3)
Skip:     Step 12 (Test Architect — tests)

### Coder Batches
Batch 1: Steps 1, 2, 3, 4   — PhysiologyMeasurement model, enum, migration, repository
Batch 2: Steps 5, 6, 10     — ThresholdObservation dataclass, service skeleton, signal selection
Batch 3: Steps 7, 8, 9       — Three detection algorithms (HR deflection, RR inflection, power-to-HR ratio)
Batch 4: Step 11            — LT1 passive inference methods (cross-session analysis — disproportionately complex)

### Batch Success Criteria
Batch 1 complete when:
- `PhysiologyParameter` enum exists in `app/models/enums.py` with all 10
  values and is imported in `app/models/__init__.py`
- `PhysiologyMeasurement` model exists in
  `app/models/physiology_measurement.py` with all specified columns and
  indexes, registered in `app/models/__init__.py`
- Alembic migration file exists and creates the `physiology_measurements`
  table
- `PhysiologyMeasurementRepository` exists in
  `app/repositories/physiology_measurement_repository.py` with `insert`,
  `get_by_athlete`, `get_by_athlete_and_parameter`,
  `get_recent_for_parameter` methods, registered in
  `app/repositories/__init__.py`
- No update/delete methods exist on the repository

Batch 2 assumes Batch 1 is complete. Batch 2 complete when:
- `ThresholdObservation` dataclass exists with all specified fields
- `ThresholdDetectionService` class exists with constructor accepting
  `AsyncSession`, `ObjectStorageClient`, `RawSensorStreamRepository`,
  `ActivityRepository`, `AthletePhysiologyRepository`,
  `PhysiologyMeasurementRepository`, and optional
  `PlannedSessionRepository` (defaults to `None`; when `None`, natural
  training analysis is skipped)
- `detect(athlete_id, activity_id)` method exists and returns
  `list[ThresholdObservation]`
- Signal selection logic correctly routes to algorithms based on
  `has_rr_intervals`, `has_hr`, `has_power`
- Activities with `calibration_eligible = false` or `sport_type != RUNNING`
  return an empty list
- Missing `RawSensorStream` returns an empty list (no exception raised)

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

Batch 4 assumes Batch 3 is complete. Batch 4 complete when:
- Natural training analysis produces `LT1_HR` observation with weight 0.5
  when ≥3 easy runs with consistent HR (±5 bpm)
- HR drift method identifies steady-state segments ≥20 min and produces
  `LT1_HR` observation with weight 1.0
- HR recovery method produces `LT1_HR` observation with weight 0.5 when hard
  effort + ≥2 min recovery data available

### Context Needed
Step 1:
  Primary:    `app/models/enums.py` (existing enum pattern — `MeasurementSource`
              is the closest model)
  Secondary:  `app/models/__init__.py` (registration pattern)
  Fallback:   —
  Forbidden:  —
Step 2:
  Primary:    `app/models/athlete_physiology.py` (FK target, JSONB shape
              reference), `app/models/raw_sensor_stream.py` (append-only model
              pattern with UniqueConstraint)
  Secondary:  `app/models/enums.py` (MeasurementSource enum for source column)
  Fallback:   —
  Forbidden:  —
Step 3:
  Primary:    output of Step 2 (model definition), existing migration
              `alembic/versions/297ea8ac7f69_phase_2_2_p1_batch_1_raw_sensor_streams.py`
              (migration naming and structure pattern)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 4:
  Primary:    `app/repositories/raw_sensor_stream_repository.py` (repository
              pattern — insert + flush, no commit), output of Step 2
  Secondary:  `app/repositories/__init__.py` (registration pattern)
  Fallback:   —
  Forbidden:  —
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
Step 10:
  Primary:    `docs/architecture/02-computations/threshold-detection.md` (Signal
              Selection section), output of Steps 7–9
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 11:
  Primary:    `docs/architecture/02-computations/lt1-detection.md` (methods 3,
              4, 5), `app/repositories/activity_repository.py` (needs
              `get_recent_activities_for_athlete` — add if missing),
              `app/repositories/planned_session_repository.py` (needs
              `get_by_id` — for filtering by `session_type` since
              `session_type` lives on `PlannedSession`, not `Activity`),
              output of Step 6
  Secondary:  `app/repositories/physiology_measurement_repository.py` (output of
              Step 4 — for querying existing LT1 observations as context)
  Fallback:   —
  Forbidden:  —

(This is everything relevant to the steps above. Primary items are fetched
together in Pre-Flight Step 3; Secondary and Fallback are requested only on
demand.)