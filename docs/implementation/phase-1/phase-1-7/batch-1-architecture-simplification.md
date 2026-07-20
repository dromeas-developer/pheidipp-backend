> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-7-p1-architecture-simplification.md` and `phase-1-8-p1-fix-event-ordering-and-async-processing.md` **on** 2026-07-19.
> This plan documents what was built in Phases 1-7 and 1-8, verified against the current codebase on 2026-07-19.

## Batch Objective

Replace Redis with PostgreSQL-backed procrastinate for the task queue, add MinIO for object storage (reducing the stack to PostgreSQL + MinIO), and wire the FIT ingestion pipeline to use async workers correctly — fixing the event ordering violation so events are published within the worker's transaction, not before commit.

## Preconditions

Depends on Phase-1.6 simple FIT import (basic HR-only ingestion pipeline already exists), `Activity` model, `FitParserService`, `LoadComputationService`, `TwinRecalibrationService`.

## Scope

**Infrastructure (Phase 1-7):**
- Remove Redis from Docker Compose; add MinIO service
- Replace ARQ/Redis with procrastinate 2.x (Psycopg2Connector, pinned `>=2.0,<3.0`)
- Remove Redis-related config, code, and dependencies
- ObjectStorageClient already supports MinIO via `S3_ENDPOINT_URL` — no code change needed
- Procrastinate worker runs as a separate process with its own DSN (SQLAlchemy driver suffix stripped for libpq format)

**Pipeline wiring (Phase 1-8):**
- Fix procrastinate `App()` constructor to use `Psycopg2Connector(conninfo=dsn)` instead of invalid `url=` parameter
- Create separate sync (`ingest`) and async (`ingest_async`) paths in `ActivityIngestionService`
- Extract `_run_ingestion_pipeline()` as the shared core (parse → load → eligibility → twin recalibration → events → defer signal_clean)
- Wire `fit_ingest` procrastinate task to download FIT, call `ingest_async()`, and commit within the worker session
- Update `POST /upload` endpoint to stage FIT in object storage, create Activity with null loads, enqueue `fit_ingest` task, return 202 Accepted with task_id
- Events (`activity_ingested`, `activity_calibration_eligible`, `sport_type_detected`) fired within the worker's transaction — transactional outbox compliance

## Steps

### Infrastructure

1. [OWNER: DevOps] Update docker-compose.yml: remove Redis service, add MinIO service (ports 9000/9001, creds minioadmin/minioadmin, healthcheck on /minio/health/live).

2. [OWNER: DevOps] Update environment variables: remove `REDIS_URL`, add `PROCRASTINATE_DATABASE_URL`.

3. [OWNER: Coder] Update `requirements.txt`: remove `arq`, add `procrastinate>=2.0,<3.0`.

4. [OWNER: Coder] Update `app/config.py`: remove Redis configuration, add procrastinate settings.

5. [OWNER: Coder] Create `app/worker/app.py` with procrastinate `App` using `Psycopg2Connector`. Strip SQLAlchemy driver suffix from DSN: `postgresql+psycopg2://` → `postgresql://`. Register tasks via `@app.task()` decorator.

6. [OWNER: Coder] Remove all Redis-specific code and imports across the codebase.

7. [OWNER: Coder] Run procrastinate migrations (`procrastinate --app=app.worker.app schema --apply`).

### Pipeline wiring

8. [OWNER: Coder] Export `_BytesReader` from `app/services/__init__.py`.

9. [OWNER: Coder] Extract `_run_ingestion_pipeline()` in `ActivityIngestionService` — the shared core that parses FIT, computes load, evaluates calibration eligibility, runs twin recalibration, fires events via `EventPublisher`, and defers `signal_clean`. Service flushes but never commits; the caller owns the commit boundary.

10. [OWNER: Coder] Create `ingest_async()` method that calls `_run_ingestion_pipeline()` — used by the `fit_ingest` worker task. The sync `ingest()` method (for test/debug) runs the same pipeline but may publish events differently.

11. [OWNER: Coder] Implement `fit_ingest` procrastinate task in `app/worker/app.py`: opens its own `AsyncSession`, downloads FIT from object storage via `download_fit()`, calls `ingest_async()`, commits. Task signature: `(*, activity_id: str, athlete_id: str) -> dict`.

12. [OWNER: Coder] Update `POST /athletes/{id}/activities/upload` endpoint to:
    - Upload raw FIT to object storage via `ObjectStorageClient.upload_fit()`
    - Create Activity record with null load scores and `fit_file_key` set
    - Commit (Activity now exists with null loads)
    - Enqueue `fit_ingest` task with activity_id and athlete_id
    - Return 202 Accepted with task_id
    - On object storage failure, return 503 with no Activity created

13. [OWNER: Coder] Event ordering within the worker transaction: `sport_type_detected` → `activity_ingested` → `activity_calibration_eligible` (when eligible). All fired before commit via `EventPublisher` — the outbox makes them visible after commit.

## Context Needed

Infrastructure: `docker-compose.yml`, `app/config.py`, `requirements.txt`, `app/main.py`
Worker: `app/worker/app.py`, procrastinate 2.x docs (Psycopg2Connector)
Pipeline: `app/services/activity_ingestion_service.py`, `app/services/fit_parser_service.py`, `app/services/load_computation_service.py`, `app/services/twin_recalibration_service.py`, `app/services/calibration_eligibility_service.py`, `app/services/event_publisher.py`
API: `app/api/v1/activity.py`, `app/schemas/activity.py`
Architecture: `04-platform/async-pipeline.md`, `04-platform/storage-topology.md`, `01-entities/activity.md`

## Batch Success Criteria

- Redis removed from docker-compose; MinIO service present and healthy
- Procrastinate 2.x replaces ARQ; Redis config and code removed
- `app/worker/app.py` initialises `procrastinate.App` with `Psycopg2Connector`, DSN stripped of driver suffix
- `_run_ingestion_pipeline()` is the shared core — parse → load → eligibility → twin → events → defer signal_clean
- `fit_ingest` worker task downloads FIT, calls `ingest_async()`, commits in its own session
- `POST /upload` returns 202 Accepted with task_id; Activity created with null loads and `fit_file_key`
- Object storage failure returns 503 with no Activity created
- Events (`sport_type_detected`, `activity_ingested`, `activity_calibration_eligible`) fired within worker transaction before commit — transactional outbox compliance
- All existing functionality (POST /analyse, GET /activities, GET /twin) preserved

## Files Expected To Change

- `docker-compose.yml` — remove Redis, add MinIO
- `.env` / `.env.example` — remove REDIS_URL, add PROCRASTINATE_DATABASE_URL
- `requirements.txt` — remove arq, add procrastinate>=2.0,<3.0
- `app/config.py` — remove Redis settings, add procrastinate settings
- `app/worker/app.py` — procrastinate App with Psycopg2Connector, register tasks
- `app/services/activity_ingestion_service.py` — extract pipeline, add ingest_async, wire events
- `app/services/__init__.py` — export _BytesReader
- `app/api/v1/activity.py` — async upload endpoint with 202 response
- `app/schemas/activity.py` — upload response schema with task_id

## Coder Notes

- Procrastinate is pinned to `<3.0` because 3.x requires `PsycopgConnector` (psycopg v3), which would introduce a third database driver. The 2.x `Psycopg2Connector` aligns with the existing sync-connection pattern.
- The `worker` service is not defined in docker-compose.yml. Workers are started manually: `procrastinate --app=app.worker.app worker`.
- `app/worker/README.md` is stale — references `post_workout_task` and `signal_cleaning_task` which don't exist in code. The actual tasks are `fit_ingest`, `recalibrate_twin`, `signal_clean`, `threshold_detection`.
- Verified against current codebase (2026-07-19): all services, tasks, endpoints, and configuration exist as described. No discrepancies.
