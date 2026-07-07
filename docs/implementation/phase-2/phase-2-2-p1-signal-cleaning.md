# Implementation Plan: Phase-2.2 — Signal Cleaning & Raw Sensor Stream
## Plan ID: Phase-2.2-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-2.2
Sub-Phase Title: Signal Cleaning & Raw Sensor Stream

## Objective
Deliver the signal cleaning pipeline that turns a calibration-eligible running
activity's raw FIT records into a cleaned, resampled, artifact-removed
time-series; persist that stream in object storage; create the matching
`RawSensorStream` metadata row; and flip `Activity.cleaning_pipeline_version`
from `null` to a non-null version. Cleaning runs as a standalone procrastinate
task decoupled from the ingestion transaction so a cleaning failure never
blocks Activity creation (ADR-009). This is the only plan for the sub-phase.

## Scope
- `RawSensorStream` ORM model, table migration, and repository (net-new entity)
- `ObjectStorageClient` extension: `upload_cleaned_stream` / `download_cleaned_stream` / `build_cleaned_stream_key` using the `cleaned-streams/{athlete_id}/{activity_id}/stream.gz` key pattern
- `SignalCleaningService` implementing signal-cleaning.md steps 1–4 (resample to 1 Hz, artifact removal, smoothing, derived metrics incl. Gen-1 population GAP, rolling features); steps 5–7 (changepoint / state inference / segment alignment) are deferred to the segmentation phases
- `signal_clean` procrastinate task in `app/worker/app.py` that opens its own session, calls `SignalCleaningService.clean(activity_id)`, and commits
- Enqueue hook in `ActivityIngestionService._run_ingestion_pipeline`: after calibration eligibility is confirmed AND `sport_type = running`, defer the `signal_clean` task; the ingestion transaction commits independently and the cleaning task runs out-of-band
- `Activity.cleaning_pipeline_version` `null` → `non-null` transition driven exclusively by the cleaning task
- Test manifest for Phase-2.2

## Out Of Scope
- Steps 5–7 of the signal-cleaning pipeline (changepoint detection, state inference, segment alignment) — these require `PhysiologicalSegment` and `PlannedSegment`, both deferred to segmentation phases per the sub-phase's "Simplifications deferred"
- `PhysiologicalSegment` creation (explicitly deferred by the sub-phase)
- Real-time / inline cleaning during ingestion (sub-phase explicitly defers this — post-processing only)
- `EffortNormalisationService` as a standalone shared service — the Gen-1 population GAP formula is inlined as a private helper inside `SignalCleaningService` (see Notes → Implementation Clarifications)
- Cadence cleaning: `ParsedFitData` does not expose cadence today and FIT parsing expansion is out of scope; `cadence_rpm` is carried as `null` and `available_channels.cadence = false` until a later phase parses it
- Any change to `LoadComputationService` or `CalibrationEligibilityService` — they are upstream dependencies, already complete; this plan only reads their results
- Any new event contract — no event is produced or consumed by this plan (signal-cleaning readiness is signalled by the `cleaning_pipeline_version` column transition, not an event, per `activity.md` Implementation Notes)
- Reprocessing of historical activities through the new pipeline — that is a later-phase concern (Principle #14); this plan handles only newly-ingested activities

## Architecture Contracts
- `02-computations/signal-cleaning.md` — IMPLEMENTS (steps 1–4; the fixed 7-step pipeline order is preserved by only emitting steps 5–7 as no-ops-by-omission for this phase)
- `01-entities/raw-sensor-stream.md` — IMPLEMENTS (entity, key pattern `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`, append-only storage, all four invariants)
- `01-entities/activity.md` — DEPENDS ON (`cleaning_pipeline_version` field already exists; `calibration_eligible`, `sport_type`, `fit_file_key` already set by `CalibrationEligibilityService` / `FitParserService`; chain `calibration_evaluated → cleaned` state transition per the Activity state diagram)
- `02-computations/effort-normalisation.md` — DEPENDS ON (Gen-1 population GAP coefficients `a=0.033, b=0.00012` used in step 3; inlined, not promoted to a service — see Notes)
- `04-platform/async-pipeline.md` → `FitIngestionTask` task inventory — DEPENDS ON (the documented order "…if eligible: enqueue TwinRecalibrationTask → clean signal → store RawSensorStream → enqueue SegmentationTask" is the source of the decoupled-task ordering)
- `04-platform/object-storage-client.md` — DEPENDS ON (referenced by sub-phase; the doc does not exist on disk — see Notes → Architecture Clarifications; the immutability and key-pattern contract is drawn from `raw-sensor-stream.md` and the existing `ObjectStorageClient` implementation)
- `docs/adr/009-signal-cleaning-as-decoupled-async-task.md` — DECISION (read before implementing; constrains step 4 and the enqueue hook in step 5)

## Invariants
Copied verbatim from the architecture corpus. The plan MUST preserve each one.

- "One `RawSensorStream` per `Activity`. Created atomically with the cleaned stream upload." (`01-entities/raw-sensor-stream.md`)
- "If cleaning fails (stream too short, all HR artifacts), no `RawSensorStream` is created. The Activity exists with null `cleaning_pipeline_version`. Segmentation is skipped for this activity." (`01-entities/raw-sensor-stream.md`)
- "The `fit_file_key` on `RawSensorStream` is the cleaned stream key — different from `Activity.fit_file_key` (raw FIT). The naming is intentional: both entities use the same field name pointing to different keys." (`01-entities/raw-sensor-stream.md`)
- "`available_channels` reflects what survived artifact removal — an activity that had HR but all values were flagged as artifacts will have `hr: false`." (`01-entities/raw-sensor-stream.md`)
- "Steps run in fixed order 1→7. No step may be skipped or reordered." (`02-computations/signal-cleaning.md`)
- "Null propagation: artifact-removed nulls propagate through smoothing. A channel with > 80% null values after artifact removal is marked unavailable in `AvailableChannels`." (`02-computations/signal-cleaning.md`)
- "Resampling: FIT files vary in recording rate (1 Hz typical; some devices record at 0.5 Hz). The pipeline resamples to a uniform 1 Hz time series before step 1." (`02-computations/signal-cleaning.md`)
- "If the pipeline produces a stream shorter than 5 minutes of non-null HR data, `RawSensorStream` is not created and segmentation is skipped." (`02-computations/signal-cleaning.md`)
- "Cleaned data stored in object storage is immutable (append-only, never updated)" (Phase-2.2 sub-phase)
- "Activities with `source = manual_entry` never get `RawSensorStream` (no FIT file)" (Phase-2.2 sub-phase)
- "Signal cleaning failure does not block Activity creation — retry mechanism in place" (Phase-2.2 sub-phase)
- "Dropout > 20% HR flags `quality_flags.hr_dropout_pct` but does not block cleaning" (Phase-2.2 sub-phase; the flag is already set by ingestion, cleaning reads it as informational only)
- "Activities with `sport_type != 'running'` are treated as `calibration_eligible = false` and `data_tier = 6` by the `CalibrationEligibilityService`, regardless of hardware signal quality." (`01-entities/activity.md`)

## Implementation Steps

1. [OWNER: Coder] Add the `RawSensorStream` ORM model in `app/models/raw_sensor_stream.py`. The table is `raw_sensor_streams`, append-only. Columns follow `raw-sensor-stream.md` exactly: `id` (UUID PK), `activity_id` (UUID FK → activities.id, ON DELETE CASCADE, with a UNIQUE constraint enforcing one-row-per-Activity), `fit_file_key` (the cleaned-stream object key — not raw FIT), `sampling_rate_hz` (default/stored 1.0 after resampling), `available_channels` (JSONB with keys `hr`, `rr_intervals`, `power`, `pace`, `cadence`, `elevation` — all booleans), `cleaning_pipeline_version` (non-null string), `created_at` (server-default now). Add the FK index `ix_raw_sensor_streams_activity` to support the one-to-one lookup. Do NOT add a `cleaned_at` or `updated_at` column — append-only means no mutation columns. Register the model in `app/models/__init__.py` so Alembic discovery includes it.

2. [OWNER: Coder] Generate the Alembic revision creating the `raw_sensor_streams` table. The revision must depend on the head at plan start (the snapshot shows head `fd373abd4b9e` augmented by Phase-2.1's `2340974caeca` — use the actual current head when generating via `alembic revision --autogenerate`). Include the `UNIQUE` constraint on `activity_id` and the FK index in the upgrade; mirror them in the downgrade. Hand the generated file off to DevOps for review/application; do NOT call `db-upgrade.sh`.

3. [OWNER: Coder] Introduce `RawSensorStreamRepository` in `app/repositories/raw_sensor_stream_repository.py`. The repository exposes only: `insert(stream)` (flushes & refreshes), `get_by_activity_id(activity_id)` (the one-to-one lookup used by downstream threshold detection in Phase-2.3), and `exists_for_activity(activity_id)` (used by the cleaning task for retry idempotency — if a row already exists for the activity, the task returns success without re-doing the work). Mirror the pattern in `app/repositories/activity_repository.py`: AsyncSession injected at construction; reads via `select(...)`; no UPDATE or DELETE methods. Register it in `app/repositories/__init__.py`.

4. [OWNER: Coder] Extend `ObjectStorageClient` (`app/services/object_storage_client.py`) with cleaned-stream methods that reuse the existing S3/local-fallback plumbing:
   - `build_cleaned_stream_key(athlete_id, activity_id)` → `"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"` (deterministic FROM `activity_id` — not a fresh UUID, so retry hits the immutability-conflict path)
   - `upload_cleaned_stream(*, athlete_id, activity_id, payload_bytes, content_type="application/gzip") -> StoredCleanedStream` (parallel to `upload_fit`: PUT in thread executor, raise `ObjectStorageConflictError` if the key already exists to act as the retry idempotency gate, return key + MD5 + byte count)
   - `download_cleaned_stream(key) -> bytes` (parallel to `download_fit`)
   - `exists(key)` already exists on the client and works for any key — do not duplicate it
   Reuse the existing `ObjectStorageUploadError` / `ObjectStorageConflictError` / `ObjectStorageNotConfiguredError` exception hierarchy; do NOT add new error classes. Define `StoredCleanedStream` as a small frozen dataclass in the same module mirroring `StoredFitObject`. The cleaned-stream key derivation MUST live on the client (alongside `build_fit_key`) — not in the service — so the key pattern has exactly one source of truth.

5. [OWNER: Coder] Implement `SignalCleaningService` in `app/services/signal_cleaning_service.py`. The service is the single owner of step-1–4 logic; it holds an `AsyncSession`, an `ObjectStorageClient`, a `RawSensorStreamRepository`, an `ActivityRepository`, and a `FitParserService` (for re-parsing the raw FIT on each cleaning run — Phase-2.2 re-parses rather than stashing parsed records across services). Public surface: a single `async def clean(self, activity_id: uuid.UUID) -> CleaningResult` method. Behaviour:
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

6. [OWNER: Coder] Add `update_cleaning_version` to `ActivityRepository` (mirroring the existing `update_load_scores` / `update_calibration_eligibility` pattern): look up by id, set `cleaning_pipeline_version`, flush, refresh, return. Document the only permitted transition as `null → non-null` (no downgrade path is exposed; re-cleaning with a new version is a future-phase concern, flagged in ADR-009 tradeoffs).

7. [OWNER: Coder] Add the `signal_clean` procrastinate task to `app/worker/app.py` alongside `fit_ingest` and `recalibrate_twin`. Signature: `async def signal_clean(*, activity_id: str) -> dict[str, Any]`. Body opens its own `AsyncSessionLocal` session, constructs `SignalCleaningService(session=session, ...)`, calls `await service.clean(uuid.UUID(activity_id))`, then `await session.commit()`. On any exception, the session is not committed (cleaned-stream upload that succeeded but DB write failed is impossible — they share the transaction; a conflict on retry is converted to success in step 5). Returns `{"activity_id": str, "raw_sensor_stream_id": str | None, "created": bool}`. The task is named `signal_clean` and registered on the shared `app` instance so `procrastinate ... worker` picks it up. Do NOT add retry/timeout decorators — procrastinate's default retry policy applies; the architecture's load-compute retry semantics ("up to 3×, then DLQ") are inherited via the same worker app configuration.

8. [OWNER: Coder] Wire the enqueue hook into `ActivityIngestionService._run_ingestion_pipeline`. After the existing block that publishes `activity_calibration_eligible` and calls `self.twin_recalibration.recalibrate(...)`, add: if `eligible and activity.sport_type == SportType.RUNNING and activity.source != ActivitySource.MANUAL_ENTRY`, defer the `signal_clean` task with `await app.signals.signal_clean.defer(activity_id=str(activity.id))` (use the procrastinate app import already established in `app/worker/app.py`; pass it in via the service constructor as an optional `task_dispatcher` so tests can substitute a fake). Do NOT await the task result — the ingestion transaction commits and returns immediately. The cleaning task runs asynchronously per the architecture. If the `defer` call itself raises (queue backend outage) swallow it and log `activity.signal_clean.enqueue.failure` — the ingestion commit MUST still succeed; the activity can be cleaned later via a backfill (Principle #14 reprocessing covers this).

9. [OWNER: DevOps] Review the Alembic revision generated by Step 2. Augment it if hypertable/extension requirements apply (they do not for `raw_sensor_streams` per `raw-sensor-stream.md`'s storage model — `append-only`, not a TimescaleDB hypertable — but confirm during review). Apply the revision to the test database and to staging/production as the release process dictates. The coder generated the file but does not run migrations.

10. [OWNER: Test Architect] Generate `tests/test-manifest/phase-2-2.yaml` listing every capability in Phase-2.2 and the test files that exercise it. Mirror the structure of `tests/test-manifest/phase-2-1.yaml` exactly: per-feature entries with `status: generated`, `owned_by_plan`, `protects` (the invariants each test guards), `impacts` (downstream capabilities the feature enables), `execution_prerequisites` (migrations: true; seed_data: false; external_services: []), `validation` block, and `tests.unit` / `tests.integration` paths. Update `tests/test-manifest/index.yaml` to include Phase-2.2.

## Event Contracts
None. This plan produces no events and consumes no events.

The `cleaning_pipeline_version` `null → non-null` transition is the readiness
signal consumed by Phase-2.3 (`ThresholdDetectionService`) and Phase-2.5
(segmentation); both are out-of-plan. No event is published by the cleaning
task — `activity.md` Implementation Notes explicitly states this column
transition IS the signal, and ADR-009's compliance block codifies that no
`cleaning_requested` event is introduced (that would be an architecture-level
event-contract change requiring escalation, not an implementation choice).

Designing the readiness signal as a column transition rather than an event
has one consequence for the coder: the enqueue hook in Step 8 fires
`activity_calibration_eligible` (already implemented) and then defers
`signal_clean`. Both happen inside the ingestion transaction. Per the
async-pipeline note, `TwinRecalibrationTask` and the cleaning task may run
concurrently; the twin recalibration uses raw HR for HR deflection and
skips RR inflection when `RawSensorStream` is not yet present. The coder
does not enforce or await this ordering — procrastinate handles task
scheduling.

## Pseudocode
The orchestration across the ingestion transaction and the cleaning task:

```
# Inside ActivityIngestionService._run_ingestion_pipeline (existing tx):
parse FIT → compute load → update Activity →
evaluate eligibility →
publish sport_type_detected →
publish activity_ingested →
if eligible: publish activity_calibration_eligible →
twin_recalibration.recalibrate(activity)
→ if eligible and sport_type == 'running': defer signal_clean(activity.id)
→ return  # worker commits the ingestion transaction

# Inside signal_clean (separate tx, may run later/concurrently):
activity = activities.get_by_id(activity_id)
guard: missing / manual_entry / already-cleaned / not-eligible / not-running
fit_bytes = object_storage.download_fit(activity.fit_file_key)
parsed = fit_parser.parse(fit_bytes)
resampled = _resample_to_1hz(parsed)
artifact_free = _remove_artifacts(resampled)
smoothed = _smooth(artifact_free)
derived = _compute_derived_metrics(smoothed, gap_coefficients=POPULATION)
features = _compute_rolling_features(derived)
available = _available_channels(artifact_free)   # >80% null → false
if non_null_hr_seconds(features) < 300:
    return CleaningResult(created=False, reason="short_stream")
key = object_storage.build_cleaned_stream_key(activity.athlete_id, activity.id)
payload = gzip(serialise(features))
try:
    object_storage.upload_cleaned_stream(athlete_id, activity.id, payload)
except ObjectStorageConflictError:
    pass  # idempotent retry — key already written
streams.insert(RawSensorStream(activity_id=activity.id, fit_file_key=key,
                               sampling_rate_hz=1.0,
                               available_channels=available,
                               cleaning_pipeline_version=PIPELINE_VERSION))
activities.update_cleaning_version(activity.id, PIPELINE_VERSION)
# caller (worker) commits — upload + insert + update land atomically
return CleaningResult(created=True, stream=features)
```

## Testing Requirements
Each requirement maps to a sub-phase Exit Gate bullet; all are
independently verifiable at this plan's completion — none depend on
Phase-2.3+.

- For an eligible running activity with HR data, a `RawSensorStream` row exists whose `available_channels.hr = true` and `cleaning_pipeline_version` is non-null. Assert via `RawSensorStreamRepository.get_by_activity_id(activity.id)` after the cleaning task runs.
- For an eligible running activity with power data, `available_channels.power = true` on the persisted `RawSensorStream`. (Power artifacts removed: assert that no cleaned record carries power > 3× the recording-30s-median.)
- For an eligible running activity with RR intervals, `available_channels.rr_intervals = true` and the cleaned RR series contains no values outside 200–2500 ms.
- `Activity.cleaning_pipeline_version` is `null` before the `signal_clean` task runs and equals `SignalCleaningService.PIPELINE_VERSION` after it commits. Assert via `ActivityRepository.get_by_id`.
- Cleaned RR values that deviate more than ±20% from the rolling median are filtered out — the cleaned RR series excludes them. (This is the Exit Gate's explicit artifact-validation threshold; the cleaning service's artifact-removal step 1 applies the 200/2500 ms bounds, and a follow-on deviation check enforces the ±20% rolling-median criterion for RR specifically.)
- An eligible running activity whose cleaned HR series has < 5 minutes of non-null data after artifact removal produces NO `RawSensorStream` row and `Activity.cleaning_pipeline_version` stays `null`. Assert via `streams.exists_for_activity(id) is False`.
- A `CalibrationEligibilityService`-ineligible activity (e.g. `sport_type = cycling` that happened to be enqueued via a stale queue entry) raises inside `SignalCleaningService.clean` and writes nothing.
- A `manual_entry` Activity returns the no-op path and writes nothing.
- Re-running `signal_clean` against an activity that already has a `RawSensorStream` is idempotent — the second call returns `created=False, reason="already_cleaned"` and does not re-upload or re-insert.
- Re-running `signal_clean` against an activity whose cleaned-stream object was uploaded but whose DB write failed (simulated by raising between upload and commit on first attempt) succeeds on the retry: the cleaned-stream upload hits `ObjectStorageConflictError` which the service converts to success, then inserts the `RawSensorStream` row and updates `Activity.cleaning_pipeline_version`.
- Non-running activities (sport_type != 'running') never trigger signal cleaning — verify the Step 8 enqueue gate does not defer `signal_clean` when `sport_type != running`, even if `calibration_eligible` were hypothetically true.
- The cleaned-stream object key matches `cleaned-streams/{athlete_id}/{activity_id}/stream.gz` exactly (Spot-check on a sample run; protects the cross-reference invariant that the name `fit_file_key` on `RawSensorStream` points to a different key than `Activity.fit_file_key`.)
- HR dropout > 20% (present in `quality_flags.hr_dropout_pct`) does NOT block cleaning — the `RawSensorStream` is still created with `available_channels.hr` reflecting only the post-artifact null fraction, not the dropout flag. Assert that an activity with `hr_dropout_pct = 0.5` still produces a `RawSensorStream` row.

## Notes

**Architecture Clarifications** — the future coder's reading of existing docs that
applies here. The architecture's `04-platform/async-pipeline.md` documents the
FitIngestionTask as `… → if eligible: enqueue TwinRecalibrationTask → clean signal
→ store RawSensorStream → enqueue SegmentationTask`. This plan enqueues the
cleaning task AFTER `twin_recalibration.recalibrate(...)` returns inside the
ingestion transaction; the cleaning task runs on a separate procrastinate worker
schedule and may execute concurrently with or after the twin recalibration task.
This matches the async-pipeline note verbatim: "TwinRecalibrationTask is enqueued
BEFORE signal cleaning completes." The coder must not invert this order — the
ingestion transaction's twin-recalibration call MUST complete (and be queued) before
the `signal_clean` defer runs, otherwise the twin update and the cleaning persist
against different Activity snapshots. The ordering inside Step 8 is the only place
this constraint is enforced.

The `04-platform/object-storage-client.md` platform contract referenced by the
sub-phase does not exist on disk (verified via `find_files`). The contract
surface needed by this plan — immutability, key pattern, retention, the
`ObjectStorageConflictError` conflict-as-idempotency semantics — is entirely
covered by `01-entities/raw-sensor-stream.md` and `04-platform/async-pipeline.md`.
The coder should treat the existing `ObjectStorageClient` implementation as the
authoritative reference for the client API shape and not spend time searching for
a standalone platform doc.

**Deferred Decisions** — out-of-scope for this phase with a defined placeholder.
Effort-normalisation Generations 2 and 3 (per-athlete curve, physiological cost
model) are not yet active for any athlete (the 20+ outdoor sessions threshold is
not reached at this stage of the product) and are out of scope; the inlined Gen-1
population GAP placeholder stands in for them. A later phase will promote the GAP
helper to a shared `EffortNormalisationService` when a second consumer requires
per-athlete curves. Cadence cleaning is deferred: `ParsedFitData.cadence` does not
exist; `available_channels.cadence = false` for Phase-2.2 and the cleaned stream
carries `cadence_rpm: null` throughout. A future FIT-parser expansion phase will
populate cadence; this plan's `available_channels` contract is forward-compatible.

**Implementation Clarifications** — telling the coder exactly what to do where a
reasonable engineer might otherwise have picked a different defensible option.
The Gen-1 population GAP formula is inlined as a private helper inside
`SignalCleaningService` (not extracted into an `EffortNormalisationService`)
because: (a) no other consumer of GAP exists in this codebase yet;
(b) the architecture defines the formula and coefficients verbatim, so a helper
duplicates no logic; (c) promoting it to a service now would create an
architecture-level ownership boundary that the architecture corpus has not yet
established (per `effort-normalisation.md`, the service boundary is implied but
not contracted). The coder MUST hardcode the coefficients `a=0.033, b=0.00012`
as module constants named `GAP_COEFFICIENT_A` and `GAP_COEFFICIENT_B` with a
docstring pointing to `02-computations/effort-normalisation.md` so a future
extraction has an unambiguous anchor.

The Savitzky-Golay smoothing (window=7, polynomial=3) for power and pace is the
signal-cleaning.md step-2 specification. If `scipy` is not already in
`requirements.txt`, the coder should add it as a direct dependency and document
the addition in the handoff — it is a multi-megabyte native-wheel dependency
and the DevOps review step is the place to catch a regression. The HR α=0.1 EMA
is implemented inline (no scipy needed).

`PIPELINE_VERSION = "v1-signal-cleaning"` is the frozen version string. When the
algorithm changes in a future phase, the version is incremented and re-cleaning
produces a new `RawSensorStream` row with the new version (per ADR-009 tradeoff:
the cleaned-stream key would then need a version suffix; this is a future
decision, recorded in the ADR).

`task_dispatcher` in `ActivityIngestionService.__init__` defaults to the
procrastinate `app` imported from `app/worker/app.py`. Tests substitute a fake
recording `defer` calls without touching the real queue. This mirrors the
existing `Optional[...]` injection pattern used for `EventPublisher`, `fit_parser`
etc. on the same constructor.

**Known Risks** — only one. `gps_records` on `ParsedFitData` carries per-record
`speed` (m/s) but no explicit per-second pace. Converting `speed → sec/km` is
`pace = 1000 / speed` when speed > 0; when `speed = 0` or null, `gap_sec_per_km`
must be null (not infinity, not zero). The coder should verify the FIT files
in `var/object-storage/fit-files/` actually carry non-null `speed` on a
representative sample before assuming pace derivation works; if `speed` is
absent on a class of files, `available_channels.pace = false` is the correct
fallback and the cleaning loop continues — this matches the invariant "a
channel with > 80% null values after artifact removal is marked unavailable".

## Coder Handoff Notes

ADR-009 (`docs/adr/009-signal-cleaning-as-decoupled-async-task.md`) is the
governing constraint. The single highest-risk thing the coder can get wrong:
running cleaning inline inside `_run_ingestion_pipeline`'s transaction. The ADR
prohibits this because the sub-phase invariant "Signal cleaning failure does not
block Activity creation" requires an independent transaction boundary. If the
coder is tempted to "just call `service.clean(activity.id)` before returning
from `_run_ingestion_pipeline`" — do not. The whole point of the separate
`signal_clean` task is that its commit/rollback is decoupled from the ingestion
commit. Read the ADR's compliance block, then re-read Step 8: the ingestion
service DEFERS the task; it does not call `service.clean(...)` itself.

The biggest conceptual slip risk is the reverse: thinking that because cleaning
runs in a separate transaction it is fine for the ingestion pipeline to keep
going "as if cleaned" before `RawSensorStream` exists. It is fine — and that
is exactly what the async-pipeline note anticipates. `ThresholdDetectionService`
(Phase-2.3) will later observe the absence and skip RR inflection. The coder's
job in Phase-2.2 is to MAKE the absence legible (a missing row + a null
`cleaning_pipeline_version`) and the presence legible (a `RawSensorStream` row
+ a non-null version). Do not add a fallback/placeholder marker — null IS the
marker.

### Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8  [OWNER: Coder] — Step 2 includes
          Alembic revision generation
Skip:     Step 9  (DevOps — migration review and application),
          Step 10 (Test Architect — test manifest)

### Coder Batches
Batch 1: Steps 1, 3, 6 — the RawSensorStream model, repository, and the
         ActivityRepository.update_cleaning_version method. Pure persistence
         scaffolding; no behaviour, no cross-file coupling beyond
         registrations. Three small files in the models/repositories layer.
Batch 2: Steps 2, 5 — the migration (Step 2, generated by the coder off the
         Batch 1 model) and the SignalCleaningService (Step 5; the single
         disproportionately complex unit in this plan — it owns steps 1–4 of
         the 7-step pipeline plus all the gate logic). Both depend on Batch 1
         outputs: the migration needs the model registered, the service needs
         the repository built in Batch 1. Grouped so the service's behaviour
         and its schema dependency land together.
Batch 3: Steps 4, 7, 8 — extend ObjectStorageClient with cleaned-stream methods
         (Step 4), add the `signal_clean` task (Step 7 — references the Batch 2
         service), wire the enqueue hook into ActivityIngestionService
         (Step 8 — references the Batch 1 + Batch 2 outputs + the Batch 3 task).
         The task and the hookup belong in one batch because the hookup is
         what makes the task reachable; testing either piece alone is harder
         than testing them after they are wired.

### Batch Success Criteria
Batch 1 complete when:
- `app/models/raw_sensor_stream.py` exists, the `RawSensorStream` class is
  registered in `app/models/__init__.py`, and the table name is
  `raw_sensor_streams` with `activity_id` UNIQUE + FK + index
  `ix_raw_sensor_streams_activity`.
- `app/repositories/raw_sensor_stream_repository.py` exists with exactly
  `insert`, `get_by_activity_id`, `exists_for_activity` — no UPDATE/DELETE —
  and is registered in `app/repositories/__init__.py`.
- `ActivityRepository.update_cleaning_version(activity_id, version)` exists
  and sets `cleaning_pipeline_version` on the loaded row.

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

Batch 3 assumes Batches 1 and 2 are complete. Batch 3 complete when:
- `ObjectStorageClient.build_cleaned_stream_key(athlete_id, activity_id)`
  returns the literal string
  `"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"`; uploading to an
  existing cleaned-stream key raises `ObjectStorageConflictError` (the same
  immutability semantics `upload_fit` enforces).
- The `signal_clean` task is registered on the procrastinate `app` instance in
  `app/worker/app.py` and opens its own `AsyncSessionLocal` session, calls
  `service.clean(activity_id)`, and commits exactly once. It is importable
  without a DB connection (defer is a free operation; only execution needs
  the DB).
- `ActivityIngestionService._run_ingestion_pipeline` defers `signal_clean`
  ONLY when `eligible and sport_type == RUNNING and source != MANUAL_ENTRY`,
  AFTER `twin_recalibration.recalibrate(...)` returns. A defer-queue backend
  error is swallowed so the ingestion commit still succeeds.
- The Step 8 ordering constraint from `04-platform/async-pipeline.md` is
  preserved exactly: `twin_recalibration.recalibrate(...)` is awaited to
  completion (within the ingestion tx) BEFORE the `signal_clean` defer. There
  is no path where the defer runs first.

### Context Needed
Step 1:
  Primary:    `01-entities/raw-sensor-stream.md` (TypeScript Schema + Object
              Storage Key Pattern + Invariants sections); `app/models/activity.py`
              (column style, FK pattern, JSONB default pattern to mirror)
  Secondary:  `app/db/base.py` (Base import)
  Forbidden:  Do not add mutation columns (`updated_at`, `cleaned_at`) — append-only
  This is everything relevant to Step 1.

Step 3:
  Primary:    `app/repositories/activity_repository.py` (the exact AsyncSession
              injection, flush-then-refresh, no-DELETE pattern to mirror);
              output of Step 1 (the RawSensorStream model)
  This is everything relevant to Step 3.

Step 6:
  Primary:    `app/repositories/activity_repository.py` → `update_load_scores`
              and `update_calibration_eligibility` (the three existing
              load-only mutations; this step adds a fourth, `update_cleaning_version`,
              following the identical pattern)
  This is everything relevant to Step 6.

Step 2:
  Primary:    output of Step 1 (the model the autogenerator must discover);
              `alembic/versions/2340974caeca_phase_2_1_p3_sport_type_filtering.py`
              (most recent Phase-2.1 revision — use as the autogenerate
              template and confirm the down_revision head)
  Forbidden:  The snapshot's `fd373abd4b9e` is NOT the head — Phase-2.1 added
              `2340974caeca`. Confirm `alembic heads` before generating.
  This is everything relevant to Step 2.

Step 5:
  Primary:    `02-computations/signal-cleaning.md` (The 7-Step Pipeline steps
              1–4 and Pipeline Invariants); `01-entities/raw-sensor-stream.md`
              (AvailableChannels shape + the four invariants); `app/services/fit_parser_service.py`
              (ParsedFitData fields the service reads: hr_records, power_records,
              rr_records, gps_records, total_ascent_m, total_distance_m,
              duration_seconds); ADR-009 Rules + Compliance block
  Secondary:  `02-computations/effort-normalisation.md` (Generation 1 — GAP
              coefficients); `app/services/object_storage_client.py` (the
              upload_fit/download_fit pattern the new methods mirror — needed
              only if Step 4 has not landed yet)
  Fallback:   If `gps_records.speed` ambiguity blocks pace derivation,
              `search_codebase("GpsRecord speed pace conversion")`
  This is everything relevant to Step 5.

Step 4:
  Primary:    `app/services/object_storage_client.py` (extend in place —
              `upload_fit`, `download_fit`, `build_fit_key`, the `_upload_local` /
              `_download_local` fallbacks, the `ObjectStorageConflictError` raise
              path that Step 5 depends on for idempotency);
              `01-entities/raw-sensor-stream.md` (the exact key pattern)
  This is everything relevant to Step 4.

Step 7:
  Primary:    `app/worker/app.py` (existing `fit_ingest` and `recalibrate_twin`
              task shape — AsyncSessionLocal usage, the commit-once pattern);
              output of Step 5 (`SignalCleaningService` constructor + the
              `clean(activity_id)` signature)
  This is everything relevant to Step 7.

Step 8:
  Primary:    `app/services/activity_ingestion_service.py` →
              `_run_ingestion_pipeline` (the exact location after
              `activity_calibration_eligible` publish and
              `twin_recalibration.recalibrate(...)`); ADR-009 Rules + Compliance
              (the defer-vs-inline prohibition); `app/worker/app.py` (the
              procrastinate `app` instance to defer against)
  Secondary:  The Optional-injection pattern on `ActivityIngestionService.__init__`
              (existing optional `EventPublisher` / `fit_parser` params — add
              `task_dispatcher` the same way so tests can substitute)
  This is everything relevant to Step 8.

All Step-1, Step-3, and Step-6 items above (the Batch 1 Primary references) and
all Batch 2 and Batch 3 Primary references are fetched together in Pre-Flight
Step 3. Secondary and Fallback are requested only on demand.
