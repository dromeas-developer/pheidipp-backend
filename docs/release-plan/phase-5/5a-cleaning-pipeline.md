# 5a — Cleaning Pipeline
*Artifact removal, smoothing, derived metrics, RawSensorStream*

## Objective

Establish the 7-step signal preprocessing pipeline that all downstream analytical
systems depend on. Clean, derived sensor data replaces direct FIT parser output
as the input for load computation, threshold detection, and eventually segmentation.
The cleaned stream is stored in object storage — the foundation for Phase 5b
segmentation and Phase 6 HMM.

## Scope

`RawSensorStream` model. 7-step cleaning pipeline. Updated `FitIngestionTask`
to run the pipeline. `cleaning_pipeline_version` tagging on Activity.
Historical reprocessing capability.

## Non-Goals

- Segmentation — deferred to 5b
- Load formula update from cleaned signals — the load formulas already use
  cleaned inputs after this sub-phase; the formulas themselves stay the same
  until 5d (per-athlete GAP) and 6a (three-dimensional load upgrade)

## Architecture References

- Signal preprocessing order — all 7 steps in fixed order:
  `architecture/segmentation-pipeline.md` → Signal Preprocessing Order
- `RawSensorStream` model field spec:
  `architecture/data-models.md` → Segmentation Layer
- `cleaning_pipeline_version` and reprocessing rules:
  `architecture/versioning.md`
- Reprocessing anchor (`fit_file_key`):
  `architecture/versioning.md` → The Reprocessing Anchor

## Dependencies

Requires 2a (`fit_file_key` exists on all Activities; `FitParserService` available).

## Models Introduced

**`RawSensorStream`** — metadata for the cleaned stream stored in object storage.
Full field spec from arch reference:
`activity_id` FK (unique), `fit_file_key` (object storage key for cleaned stream —
separate from the raw FIT file key), `sampling_rate_hz`, `available_channels` (JSONB),
`cleaning_pipeline_version`.

## Services Introduced

**`SignalCleaningService`** (sync, Python) — runs the 7-step pipeline.
- `clean(fit_data) → CleanedStream`
  Step 1: Artifact removal — HR > 220 or < 30 bpm eliminated; GPS outliers
  removed (speed > 25 m/s); power spikes (> 3× rolling median) removed.
  Step 2: Smoothing — exponential moving average for HR (α=0.1);
  Savitzky-Golay filter for power and pace (window=7, poly=3).
  Step 3: Derived metrics — GAP computed per record using the current formula
  (population static in 5a; per-athlete in 5d). Power-to-HR ratio computed.
  Variability index computed per 30-second window.
  Step 4: Rolling features — 30s, 60s, 120s statistics (mean, std, trend slope)
  for HR, power, pace, cadence.
  Steps 5-7 (changepoint detection, state inference, alignment) are deferred to 5b.

**`RawSensorStreamService`** (async) — stores cleaned stream in object storage
and writes `RawSensorStream` metadata record.
- `store(activity_id, cleaned_stream) → RawSensorStream`

## Services Modified

**`FitIngestionTask`** (updated) — after load computation (step 8 from 2b),
runs `SignalCleaningService` and `RawSensorStreamService` as additional steps.
Updated pipeline:
1-8. (as in 2b — FIT parse, upload raw, create Activity, compute load,
     evaluate eligibility, update Activity, recalibrate twin)
9. Run `SignalCleaningService.clean(fit_data)` → CleanedStream
10. `RawSensorStreamService.store(activity_id, cleaned_stream)` → RawSensorStream
11. Update `Activity.cleaning_pipeline_version`

**`LoadComputationService`** (updated) — for activities processed after 5a,
uses cleaned signal data from `CleanedStream` rather than raw `FitData`.
`ingestion_pipeline_version` incremented to reflect the input quality change.

## Key Constraints

- Cleaned stream stored in object storage under a different key prefix from raw FIT:
  `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`
- Raw FIT files are never overwritten — `fit_file_key` on Activity always points
  to the original raw file.
- If cleaning fails (e.g. stream too short, all HR artifacts), the Activity is
  still created and load computation proceeds from raw FitData. `cleaning_pipeline_version`
  is null; `RawSensorStream` is not created. Segmentation in 5b is skipped for
  this activity.
- Historical reprocessing: a `ReprocessCleaningTask` can be enqueued for any
  Activity with a `fit_file_key`. It downloads the raw FIT, runs the cleaning
  pipeline, stores a new stream, supersedes the old `RawSensorStream` record.

## Done Criteria

- After 5a, every new Activity from a FIT file has a linked `RawSensorStream`.
- The cleaned stream in object storage contains the 4 derived feature columns
  (GAP, power-to-HR ratio, variability index, rolling features).
- An Activity with all HR data removed by artifact detection still has a valid
  `RawSensorStream` record (with `available_channels` not including `hr`).
- Historical reprocessing of a prior Activity produces a new `RawSensorStream`
  without modifying the original Activity record.
