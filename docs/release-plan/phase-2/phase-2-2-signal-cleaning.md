# Phase 2 — Signal Cleaning & Raw Sensor Stream
## Sub-Phase ID: Phase-2.2

## Objective
Implement the signal cleaning pipeline that produces cleaned sensor streams and populates `RawSensorStream` for activities with `calibration_eligible = true`. This enables high-quality threshold detection by removing artifacts and creating consistent time-series data for analysis.

## Challenge Notes
The vision principle is clear: "clean data in, clean data out." Raw FIT files contain artifacts — sensor dropouts, cadence spikes, HR noise. The cleaning pipeline must handle these before threshold detection.

**Key decision:** The `RawSensorStream` entity is not exposed to athletes — it exists purely for downstream computation. This keeps the architecture clean while enabling sophisticated analysis.

**Simplifications deferred:**
- `PhysiologicalSegment` creation (uses cleaned streams but segmentation is separate)
- Real-time cleaning pipeline (initially post-processing after ingestion)

## Capabilities Delivered
- `SignalCleaningService` removes artifacts from HR, power, and RR interval series
- `RawSensorStream` records created for `calibration_eligible = true` activities
- Cleaned time-series stored in object storage for reprocessing
- `signal_cleaning.md` computation logic implemented
- `Activity.cleaning_pipeline_version` populated after cleaning completes

## Architectural Contracts Required
- `02-computations/signal-cleaning.md`
- `01-entities/activity.md` — `cleaning_pipeline_version` field
- `01-entities/raw-sensor-stream.md`
- `04-platform/object-storage-client.md`

## Vision References Required
- `twin/data-philosophy.md` — "real signals, not assumptions" principle
- `twin/load-fatigue.md` — clean data requirement for load computation

## Upstream Dependencies
- Phase-2.1 — `calibration_eligible = true` flag must exist; sport_type gate ensures only running activities reach this pipeline; FIT data with full signals available

## Downstream Enablement
- Phase-2.3 — ThresholdDetectionService uses cleaned RR series as input
- Phase-2.3 — Cleaned HR power series used for HR deflection analysis
- Phase-2.6 — Power profile computation uses cleaned power series
- Phase-5 (future) — Segmentation uses cleaned streams as input

## Invariants To Preserve
- Cleaned data stored in object storage is immutable (append-only, never updated)
- `cleaning_pipeline_version` null → non-null transition signals `RawSensorStream` ready
- Activities with `source = manual_entry` never get `RawSensorStream` (no FIT file)
- Signal cleaning failure does not block Activity creation — retry mechanism in place
- Dropout > 20% HR flags `quality_flags.hr_dropout_pct` but does not block cleaning

## Exit Gate
- For a running `calibration_eligible = true` activity with HR data, `RawSensorStream` record exists with cleaned HR series.
- For a running `calibration_eligible = true` activity with power data, `RawSensorStream` record exists with cleaned power series.
- For a running `calibration_eligible = true` activity with RR intervals, `RawSensorStream` record exists with cleaned RR series.
- `Activity.cleaning_pipeline_version` transitions from null to non-null for eligible running activities.
- Cleaned streams pass artifact validation thresholds (RR values within ±20% of rolling median retained).
- Non-running activities (sport_type != 'running') never trigger signal cleaning — they remain in the training record but are excluded from calibration pipeline.