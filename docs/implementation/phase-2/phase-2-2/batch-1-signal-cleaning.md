> **Baseline — migrated from** `docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md` and `phase-2-2-p2-rr-deviation-filter-remediation.md` **on** 2026-07-19.
> This plan documents what was built in Phase 2-2, verified against the current codebase on 2026-07-19.

## Batch Objective

Deliver the signal cleaning pipeline that turns a calibration-eligible running activity's raw FIT records into a cleaned, resampled, artifact-removed time-series; persist that stream in object storage; create the matching `RawSensorStream` metadata row; and flip `Activity.cleaning_pipeline_version` from `null` to a non-null version. Cleaning runs as a standalone procrastinate task decoupled from the ingestion transaction (ADR-009).

## Preconditions

Depends on: `Activity` model (calibration_eligible, sport_type, fit_file_key already set by upstream), `FitParserService` (ParsedFitData), `ObjectStorageClient` (download_fit), `CalibrationEligibilityService` (eligibility gate).

## Scope

- `RawSensorStream` ORM model, table migration, and repository (net-new entity)
- `ObjectStorageClient` extension: `upload_cleaned_stream` / `download_cleaned_stream` / `build_cleaned_stream_key` with key pattern `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`
- `SignalCleaningService` implementing pipeline steps in fixed order:
  - `_resample_to_1hz` — uniform 1 Hz time index, null-propagate
  - `_remove_artifacts` — three passes: (a) hard bounds (HR 30–220 bpm, speed > 25 m/s, RR 200–2500 ms), (b) power 3× rolling-30s median, (c) **RR ±20% rolling-median deviation filter** (30s trailing window excluding candidate; nulls samples where `abs(sample - median) > 0.20 * median`; skips windows with < 2 non-null samples; only applies to RR channel)
  - `_smooth` — HR EMA α=0.1, power/pace Savitzky-Golay (window=7, poly=3)
  - `_compute_derived_metrics` — Gen-1 population GAP (a=0.033, b=0.00012)
  - `_compute_rolling_features` — 30/60/120s rolling means, variability index
- `available_channels` computed after all artifact removal (>80% null → false per channel)
- 5-minute HR gate: < 300s non-null HR → no `RawSensorStream` created
- `signal_clean` procrastinate task in `app/worker/app.py`
- Enqueue hook in `ActivityIngestionService._run_ingestion_pipeline`
- `Activity.cleaning_pipeline_version` null → non-null transition
- Module constants: `PIPELINE_VERSION = "v1-signal-cleaning"`, `RR_ROLLING_WINDOW_S = 30`, `RR_DEVIATION_THRESHOLD = 0.20`

## Steps

1. [OWNER: Coder] Add the `RawSensorStream` ORM model in `app/models/raw_sensor_stream.py`. Append-only table `raw_sensor_streams` with columns: `id` (UUID PK), `activity_id` (UUID FK → activities.id, ON DELETE CASCADE, UNIQUE), `fit_file_key` (cleaned-stream object key), `sampling_rate_hz` (default 1.0), `available_channels` (JSONB: hr, rr_intervals, power, pace, cadence, elevation — all booleans), `cleaning_pipeline_version` (non-null string), `created_at` (server-default). Register in `app/models/__init__.py`.

2. [OWNER: Coder] Generate Alembic migration for `raw_sensor_streams` table.

3. [OWNER: Coder] Create `RawSensorStreamRepository` in `app/repositories/raw_sensor_stream_repository.py`. Methods: `insert(stream)` (flush & refresh), `get_by_activity_id(activity_id)`, `exists_for_activity(activity_id)`. Append-only — no UPDATE/DELETE. Register in `app/repositories/__init__.py`.

4. [OWNER: Coder] Extend `ObjectStorageClient` with cleaned-stream methods: `build_cleaned_stream_key(athlete_id, activity_id)` → `"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"`, `upload_cleaned_stream(...)` (raise `ObjectStorageConflictError` if key exists), `download_cleaned_stream(key)`. Reuse existing error hierarchy.

5. [OWNER: Coder] Implement `SignalCleaningService` in `app/services/signal_cleaning_service.py`. Public entry: `async def clean(self, activity_id) -> CleaningResult`. Guards: missing activity → raise; manual_entry → no-op; already cleaned → idempotent return; not calibration_eligible or not running → raise.

    Pipeline steps in fixed order — the call sequence is the enforcement:
    - `_resample_to_1hz` — uniform 1 Hz, null-propagate (no forward-fill)
    - `_remove_artifacts` — three passes in order:
       1. Hard bounds: HR null outside 30–220 bpm, speed null above 25 m/s, RR null outside 200–2500 ms
       2. Power: null above 3× rolling-30s median
       3. **RR ±20% deviation filter**: for each non-null RR sample at index t, compute rolling median over trailing window `[max(0, t-30), t)` EXCLUDING the candidate; if `abs(sample - median) > 0.20 * median`, null the sample. Skip windows with < 2 non-null samples. Only applies to RR — not HR, power, speed, or elevation. The window must exclude the candidate (unlike the power pass which includes it — a 3× outlier doesn't move the median enough to pass; a 20% outlier does).
    - `_smooth` — HR EMA α=0.1, power/pace Savitzky-Golay (window=7, poly=3). Nulls propagate.
    - `_compute_derived_metrics` — Gen-1 population GAP (a=0.033, b=0.00012). No GPS → `available_channels.pace = false`.
    - `_compute_rolling_features` — 30/60/120s rolling means, variability index.

    After step 4: compute `available_channels` (>80% null after ALL artifact passes → false per channel). If < 300s non-null HR → return `CleaningResult(created=False, reason="short_stream")`. If gates pass: serialise → gzip → upload → insert `RawSensorStream` → set `Activity.cleaning_pipeline_version`. Store `PIPELINE_VERSION = "v1-signal-cleaning"` as frozen module constant. Store `RR_ROLLING_WINDOW_S = 30` and `RR_DEVIATION_THRESHOLD = 0.20` as frozen module constants. Service does NOT store `self._session` — the session flows through injected repositories.

6. [OWNER: Coder] Add `update_cleaning_version` to `ActivityRepository`.

7. [OWNER: Coder] Add `signal_clean` procrastinate task to `app/worker/app.py`. Opens own `AsyncSessionLocal`, constructs service, calls `clean(activity_id)`, commits. Returns `{"activity_id", "raw_sensor_stream_id", "created"}`.

8. [OWNER: Coder] Wire enqueue hook into `ActivityIngestionService._run_ingestion_pipeline`. After `twin_recalibration.recalibrate(...)`, if `eligible and sport_type == RUNNING and source != MANUAL_ENTRY`, defer `signal_clean` task. Swallow defer failures after logging.

## Context Needed

Step 1: `01-entities/raw-sensor-stream.md`, `app/models/activity.py`
Step 3: `app/repositories/activity_repository.py` (AsyncSession pattern)
Step 6: `app/repositories/activity_repository.py` (`update_load_scores` pattern)
Step 2: output of Step 1, latest Alembic head
Step 5: `02-computations/signal-cleaning.md`, `01-entities/raw-sensor-stream.md`, `app/services/fit_parser_service.py`, `02-computations/threshold-detection.md` (Algorithm 2 consumer contract), ADR-009
Step 4: `app/services/object_storage_client.py`, `01-entities/raw-sensor-stream.md`
Step 7: `app/worker/app.py` (existing task patterns), output of Step 5
Step 8: `app/services/activity_ingestion_service.py` (`_run_ingestion_pipeline`), ADR-009

## Batch Success Criteria

- `RawSensorStream` model exists with UNIQUE on activity_id, registered
- `RawSensorStreamRepository` exists with insert/get/exists — no UPDATE/DELETE
- `ActivityRepository.update_cleaning_version` exists
- Alembic migration creates `raw_sensor_streams` table
- `SignalCleaningService.clean()` runs steps in fixed order, all gates enforced
- `_remove_artifacts` runs three passes: hard bounds → power 3× median → RR ±20% deviation filter
- RR deviation filter uses trailing window EXCLUDING candidate, nulls samples where `abs(sample - median) > 0.20 * median`, skips windows with < 2 non-null samples
- RR deviation filter does NOT fire on HR, power, speed, or elevation — only RR
- 5-minute HR gate returns `created=False` without writing
- `available_channels` computed correctly (>80% null rule, evaluated after ALL artifact passes)
- `PIPELINE_VERSION`, `RR_ROLLING_WINDOW_S`, `RR_DEVIATION_THRESHOLD` are frozen module constants
- `ObjectStorageClient` cleaned-stream methods exist, conflict=idempotency
- `signal_clean` task registered, opens own session, commits once
- Enqueue hook fires only for eligible/running/non-manual, after twin recalibration
- Defer failures swallowed

## Files Expected To Change

- `app/models/raw_sensor_stream.py` — new model
- `app/models/__init__.py` — register model
- `alembic/versions/<migration>.py` — new migration
- `app/repositories/raw_sensor_stream_repository.py` — new repository
- `app/repositories/__init__.py` — register repository
- `app/repositories/activity_repository.py` — add `update_cleaning_version`
- `app/services/signal_cleaning_service.py` — new service with all pipeline steps, constants, and artifact passes
- `app/services/__init__.py` — register service
- `app/services/object_storage_client.py` — extend with cleaned-stream methods
- `app/worker/app.py` — new `signal_clean` task
- `app/services/activity_ingestion_service.py` — enqueue hook

## Coder Notes

- ADR-009 constraint: cleaning runs as a separate task, NOT inline in the ingestion transaction.
- The RR deviation window MUST exclude the candidate sample (unlike the power artifact window). A 3× outlier doesn't move the median enough to pass; a 20% outlier does.
- The RR deviation filter runs AFTER the hard bound — the hard bound must null extreme artefacts first so they don't poison the rolling median.
- `self._session` is not stored on the service — the session flows through injected repositories.
- Verified against current codebase (2026-07-19): all entities, services, repositories, worker task, and tests exist. No discrepancies.
