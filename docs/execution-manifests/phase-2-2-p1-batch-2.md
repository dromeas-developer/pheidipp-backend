# Execution Manifest — Phase-2.2-P1 — Batch 2

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
Batch:             2 of 3
Manifest Version:  v1
Generated At:      2026-07-07T00:00:00Z
Source Plan Lines: 437
Manifest Lines:    202

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Generate the Alembic migration for the raw_sensor_streams table and implement SignalCleaningService to execute the first four steps of the signal-cleaning pipeline.

## Preconditions
Batches 1 through 1 are complete; their Batch Success Criteria hold

## Steps
### Step 2 — Generate the Alembic revision creating the `raw_sensor_streams` table.
Generate the Alembic revision creating the `raw_sensor_streams` table. The revision must depend on the head at plan start (the snapshot shows head `fd373abd4b9e` augmented by Phase-2.1's `2340974caeca` — use the actual current head when generating via `alembic revision --autogenerate`). Include the `UNIQUE` constraint on `activity_id` and the FK index in the upgrade; mirror them in the downgrade. Hand the generated file off to DevOps for review/application; do NOT call `db-upgrade.sh`.

### Step 5 — Implement `SignalCleaningService` in `app/services/signal_cleaning_service.py`.
Implement `SignalCleaningService` in `app/services/signal_cleaning_service.py`. The service is the single owner of step-1–4 logic; it holds an `AsyncSession`, an `ObjectStorageClient`, a `RawSensorStreamRepository`, an `ActivityRepository`, and a `FitParserService` (for re-parsing the raw FIT on each cleaning run — Phase-2.2 re-parses rather than stashing parsed records across services). Public surface: a single `async def clean(self, activity_id: uuid.UUID) -> CleaningResult` method. Behaviour:
   - Load the `Activity`. Guard: if it does not exist → raise (the worker surfaces a 404-style error to procrastinate). Guard: if `source = manual_entry` → return a no-op result (manual entries have no FIT, per invariant; the task enqueue gate already prevents this, but the guard is defence-in-depth). Guard: if `RawSensorStream` already exists for this activity (via `exists_for_activity`) → return success idempotently (retry after a partial-then-committed run). Guard: if `calibration_eligible = false` or `sport_type != running` → raise — these should never reach the task, but a stale queue entry (e.g. an activity later marked ineligible) must not corrupt state.
   - Download the raw FIT via `ObjectStorageClient.download_fit(activity.fit_file_key)` — raises if the key is missing; the worker retries.
   - Parse with `FitParserService.parse(...)` to obtain `ParsedFitData` (hr_records, power_records, rr_records, gps_records, duration_seconds, total_ascent_m, etc.). Parsing failures propagate — the worker retries per procrastinate backoff.
   - Run the pipeline steps in fixed order, each as a private method so the order is enforced by the call sequence, not by free-floating helpers:
     * `_resample_to_1hz(...)` — materialise a uniform 1 Hz time index from 0…duration_seconds-1; align each channel onto it (forward-fill for HR/power/cadence-equivalents is forbidden — null-propagate per the invariant; HR-resampling only coerces timestamps, it does NOT invent HR values).
     * `_remove_artifacts(...)` — apply the signal-cleaning.md thresholds exactly (HR null outside 30–220 bpm; power null above 3× rolling-30s median; speed null above 25 m/s; rr null outside 200–2500 ms).
     * `_smooth(...)` — HR exponential moving average (α=0.1, with null carry-forward of last smoothed value); power and pace Savitzky-Golay (window=7, poly=3). If `scipy.signal.savgol_filter` is available in the project's dependency set, use it; otherwise document the chosen fallback in the service module docstring. Nulls propagating from step 1 stay null through smoothing.
     * `_compute_derived_metrics(...)` — compute `gap_sec_per_km` per record via the inlined Gen-1 population GAP formula `raw_pace / (1 + a·grade + b·grade²)` with `a=0.033, b=0.00012` (the formula and coefficients are verbatim from `02-computations/effort-normalisation.md`; do NOT call out to a hypothetical `EffortNormalisationService` — see Notes → Implementation Clarifications). Raw pace is derived from `gps_records.speed` (m/s → sec/km); grade is derived from consecutive altitude deltas over horizontal distance. If GPS is absent or speed is null for a record, `gap_sec_per_km` is null for that record and `available_channels.pace = false`.
     * `_compute_rolling_features(...)` — for windows 30/60/120 s compute mean HR, mean power, mean GAP per record (rolling mean with the null-propagation rule: a window with any null input contributes a null output, not a mean over non-nulls). Write the variability index (coefficient of variation of pace/power over 30 s) into the `variability_index` field.
   - After step 4, evaluate the invariants that gate whether a `RawSensorStream` is created:
     * Compute `available_channels` by checking each channel's null fraction AFTER artifact removal. A channel with > 80% null → `false` per the invariant.
     * If the cleaned HR series has fewer than 300 non-null seconds (5 minutes) → return a `CleaningResult(created=False, reason="short_stream")` without writing anything. The `Activity` retains `cleaning_pipeline_version = null` and segmentation will skip it, exactly as the invariant specifies.
   - If all gates pass: serialise the `CleanedStream` (the structured time-series per signal-cleaning.md step 4 output) to gzipped bytes, build the cleaned-stream key, `upload_cleaned_stream(...)` (raise on conflict → the conflict IS the idempotency outcome, treat it as success and continue), insert the `RawSensorStream` row with `available_channels`, `sampling_rate_hz=1.0`, the cleaned-stream key, `cleaning_pipeline_version=self.PIPELINE_VERSION`, and atomically — in the same transaction — set `Activity.cleaning_pipeline_version = self.PIPELINE_VERSION` via `ActivityRepository.update_cleaning_version(activity_id, version)`. Return `CleaningResult(created=True, stream=stream)`.
   - `PIPELINE_VERSION = "v1-signal-cleaning"` is a frozen module constant. Do NOT derive it at runtime or read it from settings.

## Context Needed
### Step 2
**Primary:**    output of Step 1 (the model the autogenerator must discover);
              `alembic/versions/2340974caeca_phase_2_1_p3_sport_type_filtering.py`
              (most recent Phase-2.1 revision — use as the autogenerate
              template and confirm the down_revision head)
**Forbidden:**  The snapshot's `fd373abd4b9e` is NOT the head — Phase-2.1 added
              `2340974caeca`. Confirm `alembic heads` before generating.
**This is everything relevant to Step 2.**

### Step 5
**Primary:**    `02-computations/signal-cleaning.md` (The 7-Step Pipeline steps
              1–4 and Pipeline Invariants); `01-entities/raw-sensor-stream.md`
              (AvailableChannels shape + the four invariants); `app/services/fit_parser_service.py`
              (ParsedFitData fields the service reads: hr_records, power_records,
              rr_records, gps_records, total_ascent_m, total_distance_m,
              duration_seconds); ADR-009 Rules + Compliance block
**Secondary:**  `02-computations/effort-normalisation.md` (Generation 1 — GAP
              coefficients); `app/services/object_storage_client.py` (the
              upload_fit/download_fit pattern the new methods mirror — needed
              only if Step 4 has not landed yet)
**Fallback:**   If `gps_records.speed` ambiguity blocks pace derivation,
              `search_codebase("GpsRecord speed pace conversion")`
**This is everything relevant to Step 5.**

## Relevant Architecture Contracts
- `02-computations/signal-cleaning.md` — IMPLEMENTS (steps 1–4; the fixed 7-step pipeline order is preserved by only emitting steps 5–7 as no-ops-by-omission for this phase)
- `01-entities/raw-sensor-stream.md` — IMPLEMENTS (entity, key pattern `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`, append-only storage, all four invariants)
- `01-entities/activity.md` — DEPENDS ON (`cleaning_pipeline_version` field already exists; `calibration_eligible`, `sport_type`, `fit_file_key` already set by `CalibrationEligibilityService` / `FitParserService`; chain `calibration_evaluated → cleaned` state transition per the Activity state diagram)
- `02-computations/effort-normalisation.md` — DEPENDS ON (Gen-1 population GAP coefficients `a=0.033, b=0.00012` used in step 3; inlined, not promoted to a service — see Notes)
- `docs/adr/009-signal-cleaning-as-decoupled-async-task.md` — DECISION (read before implementing; constrains step 4 and the enqueue hook in step 5)

## Relevant Invariants
- "Steps run in fixed order 1→7. No step may be skipped or reordered." (`02-computations/signal-cleaning.md`)
- "Null propagation: artifact-removed nulls propagate through smoothing. A channel with > 80% null values after artifact removal is marked unavailable in `AvailableChannels`." (`02-computations/signal-cleaning.md`)
- "Resampling: FIT files vary in recording rate (1 Hz typical; some devices record at 0.5 Hz). The pipeline resamples to a uniform 1 Hz time series before step 1." (`02-computations/signal-cleaning.md`)
- "If the pipeline produces a stream shorter than 5 minutes of non-null HR data, `RawSensorStream` is not created and segmentation is skipped." (`02-computations/signal-cleaning.md`)
- "If cleaning fails (stream too short, all HR artifacts), no `RawSensorStream` is created. The Activity exists with null `cleaning_pipeline_version`. Segmentation is skipped for this activity." (`01-entities/raw-sensor-stream.md`)
- "Cleaned data stored in object storage is immutable (append-only, never updated)" (Phase-2.2 sub-phase)

## Relevant Event Contracts
None. This plan does not produce or consume events in Batch 2.

## Relevant Notes
None. No notes explicitly reference entities or concepts that appear in Batch 2's Steps or Context Needed.

## Files Expected To Change
- [NEW] `alembic/versions/<revision>_raw_sensor_streams_table.py`
- [NEW] `app/services/signal_cleaning_service.py`

## Batch Success Criteria
Batch 2 assumes Batch 1 is complete. Batch 2 complete when:
- The generated Alembic revision file exists under `alembic/versions/` with
  `down_revision` set to the actual current head (NOT a hardcoded revision from
  this plan), and `op.create_table('raw_sensor_streams', ...)` includes the
  UNIQUE constraint on `activity_id` and the FK index. The coder did NOT run
  `db-upgrade.sh` — the file is staged for DevOps.
- `SignalCleaningService.clean(activity_id)` runs the steps in fixed order
  `_resample_to_1hz → _remove_artifacts → _smooth → _compute_derived_metrics →
  _compute_rolling_features` (the call sequence is the enforcement — there is
  no `_run_step_N` dispatcher that could be re-ordered).
- The 5-minute / 300-second non-null HR gate causes `clean` to return
  `CleaningResult(created=False)` WITHOUT writing a `RawSensorStream` row or
  touching `Activity.cleaning_pipeline_version`.
- The per-channel "> 80% null after artifact removal → `available_channels.<channel> = false`"
  rule is applied for hr, rr_intervals, power, pace, cadence, elevation.
- `PIPELINE_VERSION` is a frozen module-level constant, not a setting.