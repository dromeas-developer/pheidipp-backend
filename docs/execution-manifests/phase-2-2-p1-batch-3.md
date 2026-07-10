# Execution Manifest — Phase-2.2-P1 — Batch 3

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
Batch:             3 of 3
Manifest Version:  v1
Generated At:      2026-07-07T00:00:00Z
Source Plan Lines: 437
Manifest Lines:    185

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Extend ObjectStorageClient with cleaned-stream methods, add the signal_clean procrastinate task, and wire the enqueue hook into ActivityIngestionService.

## Preconditions
Batches 1 through 2 are complete; their Batch Success Criteria hold

## Steps
### Step 4 — Extend `ObjectStorageClient` (`app/services/object_storage_client.py`) with cleaned-stream methods that reuse the existing S3/local-fallback plumbing:
Extend `ObjectStorageClient` (`app/services/object_storage_client.py`) with cleaned-stream methods that reuse the existing S3/local-fallback plumbing:
   - `build_cleaned_stream_key(athlete_id, activity_id)` → `"cleaned-streams/{athlete_id}/{activity_id}/stream.gz"` (deterministic FROM `activity_id` — not a fresh UUID, so retry hits the immutability-conflict path)
   - `upload_cleaned_stream(*, athlete_id, activity_id, payload_bytes, content_type="application/gzip") -> StoredCleanedStream` (parallel to `upload_fit`: PUT in thread executor, raise `ObjectStorageConflictError` if the key already exists to act as the retry idempotency gate, return key + MD5 + byte count)
   - `download_cleaned_stream(key) -> bytes` (parallel to `download_fit`)
   - `exists(key)` already exists on the client and works for any key — do not duplicate it
   Reuse the existing `ObjectStorageUploadError` / `ObjectStorageConflictError` / `ObjectStorageNotConfiguredError` exception hierarchy; do NOT add new error classes. Define `StoredCleanedStream` as a small frozen dataclass in the same module mirroring `StoredFitObject`. The cleaned-stream key derivation MUST live on the client (alongside `build_fit_key`) — not in the service — so the key pattern has exactly one source of truth.

### Step 7 — Add the `signal_clean` procrastinate task to `app/worker/app.py` alongside `fit_ingest` and `recalibrate_twin`.
Add the `signal_clean` procrastinate task to `app/worker/app.py` alongside `fit_ingest` and `recalibrate_twin`. Signature: `async def signal_clean(*, activity_id: str) -> dict[str, Any]`. Body opens its own `AsyncSessionLocal` session, constructs `SignalCleaningService(session=session, ...)`, calls `await service.clean(uuid.UUID(activity_id))`, then `await session.commit()`. On any exception, the session is not committed (cleaned-stream upload that succeeded but DB write failed is impossible — they share the transaction; a conflict on retry is converted to success in step 5). Returns `{"activity_id": str, "raw_sensor_stream_id": str | None, "created": bool}`. The task is named `signal_clean` and registered on the shared `app` instance so `procrastinate ... worker` picks it up. Do NOT add retry/timeout decorators — procrastinate's default retry policy applies; the architecture's load-compute retry semantics ("up to 3×, then DLQ") are inherited via the same worker app configuration.

### Step 8 — Wire the enqueue hook into `ActivityIngestionService._run_ingestion_pipeline`.
Wire the enqueue hook into `ActivityIngestionService._run_ingestion_pipeline`. After the existing block that publishes `activity_calibration_eligible` and calls `self.twin_recalibration.recalibrate(...)`, add: if `eligible and activity.sport_type == SportType.RUNNING and activity.source != ActivitySource.MANUAL_ENTRY`, defer the `signal_clean` task with `await app.signals.signal_clean.defer(activity_id=str(activity.id))` (use the procrastinate app import already established in `app/worker/app.py`; pass it in via the service constructor as an optional `task_dispatcher` so tests can substitute a fake). Do NOT await the task result — the ingestion transaction commits and returns immediately. The cleaning task runs asynchronously per the architecture. If the `defer` call itself raises (queue backend outage) swallow it and log `activity.signal_clean.enqueue.failure` — the ingestion commit MUST still succeed; the activity can be cleaned later via a backfill (Principle #14 reprocessing covers this).

## Context Needed
### Step 4
**Primary:**    `app/services/object_storage_client.py` (extend in place —
              `upload_fit`, `download_fit`, `build_fit_key`, the `_upload_local` /
              `_download_local` fallbacks, the `ObjectStorageConflictError` raise
              path that Step 5 depends on for idempotency);
              `01-entities/raw-sensor-stream.md` (the exact key pattern)
**This is everything relevant to Step 4.**

### Step 7
**Primary:**    `app/worker/app.py` (existing `fit_ingest` and `recalibrate_twin`
              task shape — AsyncSessionLocal usage, the commit-once pattern);
              output of Step 5 (`SignalCleaningService` constructor + the
              `clean(activity_id)` signature)
**This is everything relevant to Step 7.**

### Step 8
**Primary:**    `app/services/activity_ingestion_service.py` →
              `_run_ingestion_pipeline` (the exact location after
              `activity_calibration_eligible` publish and
              `twin_recalibration.recalibrate(...)`); ADR-009 Rules + Compliance
              (the defer-vs-inline prohibition); `app/worker/app.py` (the
              procrastinate `app` instance to defer against)
**Secondary:**  The Optional-injection pattern on `ActivityIngestionService.__init__`
              (existing optional `EventPublisher` / `fit_parser` params — add
              `task_dispatcher` the same way so tests can substitute)
**This is everything relevant to Step 8.**

## Relevant Architecture Contracts
- `04-platform/async-pipeline.md` → `FitIngestionTask` task inventory — DEPENDS ON (the documented order "…if eligible: enqueue TwinRecalibrationTask → clean signal → store RawSensorStream → enqueue SegmentationTask" is the source of the decoupled-task ordering)
- `01-entities/raw-sensor-stream.md` — DEPENDS ON (key pattern `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`)
- `docs/adr/009-signal-cleaning-as-decoupled-async-task.md` — DECISION (read before implementing; constrains step 4 and the enqueue hook in step 5)

## Relevant Invariants
- "Signal cleaning failure does not block Activity creation — retry mechanism in place" (Phase-2.2 sub-phase)
- "Activities with `sport_type != 'running'` are treated as `calibration_eligible = false` and `data_tier = 6` by the `CalibrationEligibilityService`, regardless of hardware signal quality." (`01-entities/activity.md`)
- "Cleaned data stored in object storage is immutable (append-only, never updated)" (Phase-2.2 sub-phase)

## Relevant Event Contracts
None. This plan does not produce or consume events in Batch 3.

## Relevant Notes
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

## Files Expected To Change
- [EXISTING] `app/services/object_storage_client.py`
- [NEW] `app/worker/app.py` (modification to add signal_clean task; note: file is EXISTING, this step modifies it)

## Batch Success Criteria
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