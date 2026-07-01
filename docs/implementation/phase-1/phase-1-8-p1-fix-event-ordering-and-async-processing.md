# Implementation Plan: Phase-1.8 — Fix Event Ordering and Async Processing

## Plan ID: Phase-1.8-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.8
Sub-Phase Title: Fix Event Ordering and Async Processing

## Objective
Address critical validation findings from Phase-1.6 and Phase-1.7 implementation by fixing the event ordering violation and implementing proper async processing with procrastinate workers. This ensures compliance with the transactional outbox pattern and the architecture principle that all heavy processing must be async.

## Scope
- Move `activity_ingested` event publication to after transaction commit or implement proper transactional outbox pattern
- Implement async FIT ingestion using procrastinate workers as specified in Phase-1.7 architecture
- Update API endpoints to return 202 Accepted with task_id instead of 201 Created
- Add missing exports for `_BytesReader` in services __init__.py
- Update ActivityIngestionService to support both sync (for testing) and async (for production) modes
- Create proper task enqueueing logic in the upload endpoint

## Out Of Scope
- Power, GPS, or RR interval data processing (HR only continues as Phase 1.6)
- RawSensorStream entity creation (data parsed on-the-fly and discarded)
- ExecutionObservation or rep-level analysis (post-workout remains compliance + effort narrative only)
- Any changes to the core ingestion logic or business rules

## Architecture Contracts
- `01-entities/activity.md` — IMPLEMENTS (event ordering fix)
- `04-platform/system-event.md` — IMPLEMENTS (transactional outbox pattern)
- `04-platform/async-pipeline.md` — IMPLEMENTS (procrastinate worker integration)
- `04-platform/event-topology.md` — IMPLEMENTS (proper event sequencing)
- `docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md` — CORRECTS (async processing deviation)
- `docs/implementation/phase-1/phase-1-7-p1-architecture-simplification.md` — COMPLETES (worker implementation)

## Invariants
- Object storage upload happens BEFORE `Activity` record creation. If upload fails, no `Activity` is created.
- Events are published AFTER the producing transaction commits, never before.
- All heavy processing (FIT parsing, load computation, twin recalibration) runs in a worker queue. API responses never wait for these.
- The queue backend is decoupled; PostgreSQL-backed workers (`procrastinate`) are used with a defined migration path to Redis if needed.
- Raw FIT files are never overwritten or deleted. They are the reprocessing anchor.

## Implementation Steps
0. [OWNER: Coder] **Prerequisite: Fix procrastinate App() constructor in app/worker/app.py**
   
   The current implementation uses the invalid `url=` parameter. Update to use `Psycopg2Connector`:
   ```python
   from procrastinate.contrib.psycopg2 import Psycopg2Connector
   
   _app_dsn = settings.PROCRASTINATE_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
   app = procrastinate.App(connector=Psycopg2Connector(conninfo=_app_dsn))
   ```
   
   This fixes the IDE error and ensures Phase-1.8's upload endpoint (which imports `app` from this module) can function.
   Note: The worker runs as a separate process; sync connector is acceptable for current scale.

1. [OWNER: Coder] Update `app/services/__init__.py` to export `_BytesReader` from `fit_parser_service.py`

2. [OWNER: Coder] Modify `ActivityIngestionService.ingest()` method to separate the core ingestion logic from event publishing. Create a new internal method `_run_ingestion_pipeline()` that contains all the processing logic but does NOT publish events.

3. [OWNER: Coder] Update the existing `ingest()` method to call `_run_ingestion_pipeline()` and then publish the `activity_ingested` event, but only when running in sync mode (for testing purposes).

4. [OWNER: Coder] Create a new method `ingest_async()` in `ActivityIngestionService` that calls `_run_ingestion_pipeline()` and publishes the event within the same transaction, ensuring proper ordering.

5. [OWNER: Coder] Update `app/api/v1/activity.py` POST `/upload` endpoint to:
   - Upload raw FIT file to object storage
   - Create Activity record with null load scores and fit_file_key
   - Enqueue `fit_ingest` procrastinate task with activity_id and athlete_id
   - Return 202 Accepted with task_id in response

6. [OWNER: Coder] Update the procrastinate worker task `fit_ingest` in `app/worker/app.py` to use the new `ingest_async()` method instead of duplicating the ingestion logic.

7. [OWNER: Coder] Remove the duplicated ingestion logic from the `fit_ingest` worker task and simplify it to just call the service method.

8. [OWNER: Coder] Update error handling in the API endpoint to handle object storage failures properly (return 503) while ensuring no Activity record is created on failure.

9. [OWNER: Coder] Add proper HTTP status codes: 202 Accepted for successful task enqueueing, appropriate error codes for failures.

10. [OWNER: Coder] Generate Alembic migration if any schema changes are needed (likely none, but verify).

11. [OWNER: DevOps] Review and apply the Alembic migration if generated.

12. [OWNER: Test Architect] Update test files to handle the new async behavior and 202 responses, including task status checking.

## Event Contracts
- `activity_ingested` — PRODUCES
  - Payload: `{activity_id, date, duration, has_hr, has_rr, has_power, fit_file_key, aerobic_load}`
  - Ordering: Must fire AFTER Activity record is committed and object storage upload succeeds
  - Transaction: Event publication must be part of the same transaction that creates/updates the Activity

## Pseudocode
```
FIT file upload received
  → Store raw FIT file in object storage with key fit-files/{athlete_id}/{activity_date}/{uuid}.fit
  → If storage fails → return 503, no Activity created
  → Create Activity record with source = manual_upload, fit_file_key = storage_key, load scores = null
  → Commit transaction (Activity now exists with null loads)
  → Enqueue fit_ingest task with activity_id and athlete_id
  → Return 202 Accepted with task_id

Worker task fit_ingest executes:
  → Download raw FIT file from object storage using fit_file_key
  → Parse FIT file to extract HR records, duration, start_time
  → Compute aerobic_load using LoadComputationService
  → Update Activity with computed load scores
  → Set calibration_eligible = false (Phase 1.6 simplification)
  → Apply Banister update to AthleteFitness via TwinRecalibrationService
  → Create new TwinState record with trigger = activity_sync
  → Fire activity_ingested event (within same transaction as updates)
  → Commit transaction (Activity fully populated, event published)
```

## Testing Requirements
- Uploading a valid FIT file returns 202 Accepted with task_id immediately
- GET /tasks/{task_id} shows task status progressing from pending to completed
- After task completes, Activity has populated aerobic_load score and non-null fit_file_key
- GET /athletes/{id}/twin/history shows a new TwinState after task completion
- Simulating object storage failure during upload returns 503 and creates no Activity record
- Event `activity_ingested` is only published after Activity record is fully committed
- All existing functionality (POST /analyse, GET /activities, etc.) continues to work
- Error handling for FIT parsing failures works correctly in the worker context

## Coder Handoff Notes
```
## Coder Scope
Execute:  Steps 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10  [OWNER: Coder] — includes migration generation and procrastinate fix
Skip:     Step 11 (DevOps — migration review and application),
          Step 12 (Test Architect — tests)
```

Key implementation considerations:
- **Procrastinate App() fix (Step 0)**: The current `app/worker/app.py` uses an invalid `url=` parameter. Replace with `AiopgConnector` as documented. This is a prerequisite for all other steps.
- **Transactional outbox compliance**: Ensure events are only published after the transaction that produces them commits successfully. The current implementation violates this by publishing before commit.
- **Async-first design**: The primary flow should be async via procrastinate workers. Sync mode should only exist for testing/debugging purposes.
- **API contract change**: Change from 201 Created to 202 Accepted with task_id. This aligns with the original Phase-1.6 plan specification.
- **Error handling**: Object storage failures should prevent Activity creation entirely. Worker task failures should leave the Activity in a partially populated state (null loads) for retry.
- **Backward compatibility**: Existing API consumers may need to adapt to 202 responses and task polling, but this is expected per the original architecture.
- **Worker task simplification**: The current worker task duplicates logic that should live in the service layer. Consolidate this into the ActivityIngestionService.
- **Missing export**: Don't forget to add `_BytesReader` to the services __init__.py exports for completeness.
- **Follow existing patterns**: Use the same patterns established in other service methods and worker tasks throughout the codebase.