# Implementation Plan: Phase-1.7 — Architecture Simplification
## Plan ID: Phase-1.7-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.7
Sub-Phase Title: Architecture Simplification — MinIO and procrastinate

## Objective
Implement architecture simplification by replacing Redis with PostgreSQL-backed procrastinate for task queue and confirming MinIO support for object storage. This reduces operational complexity to a two-system stack (PostgreSQL + MinIO) while maintaining all functionality.

## Scope
- Update Docker Compose to remove Redis service and add MinIO service
- Update configuration to use procrastinate instead of ARQ/Redis
- Update environment variables and configuration files
- Remove Redis-related code and dependencies
- Verify object storage client supports MinIO (already implemented)
- Update integration tests to use procrastinate

## Out Of Scope
- Migration from MinIO to AWS S3 (zero code change required per architecture)
- Performance optimization for procrastinate (monitor first, optimize if needed)
- Cache re-introduction (monitor TwinState query latency first)

## Architecture Contracts
- `04-platform/storage-topology.md` — IMPLEMENTS (MinIO as object storage)
- `04-platform/async-pipeline.md` — IMPLEMENTS (procrastinate as task queue)
- `00-foundations/principles.md` — DEPENDS ON (Principle #7 updated for backend-agnostic queue)

## Invariants
- "All heavy processing is async." FIT parsing, twin recalibration, post-workout analysis — all run in a worker queue. API responses never wait for these. The queue backend is decoupled; early-stage implementation uses PostgreSQL-backed workers (`procrastinate 2.x`), with a defined migration path to Redis if queue contention requires it.
- Raw FIT files are never overwritten or deleted. They are the reprocessing anchor.

### Procrastinate Version Constraint

Procrastinate is pinned to `>=2.0,<3.0` in `requirements.txt`.

**Implementation detail:** Both procrastinate 2.x and 3.x use a connector-based, keyword-only API:
```python
from procrastinate.contrib.psycopg2 import Psycopg2Connector

# Strip SQLAlchemy driver suffix for libpq-style DSN  
_app_dsn = settings.PROCRASTINATE_DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
app = procrastinate.App(connector=Psycopg2Connector(conninfo=_app_dsn))
```

- Procrastinate 3.x requires `PsycopgConnector` (backed by psycopg v3), which would introduce a third database driver.
- Procrastinate 2.x supports `Psycopg2Connector` (backed by psycopg2), aligning with the project's existing sync-connection pattern.
- The worker runs as a separate process from the API; sync connector is acceptable for current scale and maintains operational simplicity.
- Because the queue is transitional — likely to be replaced by Redis/Celery if contention appears — we avoid new dependencies and use Psycopg2Connector in 2.x.
- The `.env` files keep the `postgresql+psycopg2://` format for SQLAlchemy consistency; the DSN is transformed at the App() construction site.

## Implementation Steps
1. [OWNER: DevOps] Update docker-compose.yml to remove Redis service and add MinIO service with appropriate configuration
2. [OWNER: DevOps] Update environment variables and configuration files to remove REDIS_URL and update any procrastinate-specific settings
3. [OWNER: Coder] Update requirements.txt to remove arq and add `procrastinate>=2.0,<3.0`
   with a comment explaining the 3.x pin
4. [OWNER: Coder] Update app/config.py to remove Redis configuration and add any procrastinate-specific configuration if needed
5. [OWNER: Coder] Update task queue implementation to use procrastinate 2.x instead of ARQ/Redis across all services;
   keep the URL-based `procrastinate.App(url=settings.PROCRASTINATE_DATABASE_URL)` API
6. [OWNER: Coder] Remove any Redis-specific code and imports across the codebase
7. [OWNER: Coder] Update ObjectStorageClient configuration if needed for MinIO (should already be supported via S3_ENDPOINT_URL)
8. [OWNER: Test Architect] Update integration tests to use procrastinate instead of ARQ/Redis
9. [OWNER: DevOps] Verify MinIO service starts correctly and is accessible from application
10. [OWNER: DevOps] Apply database migrations if needed for procrastinate tables
11. [OWNER: Test Architect] Run full test suite to verify all functionality works with new architecture

## Event Contracts
- All existing events remain unchanged since only infrastructure layer is being modified
- Event producers and consumers remain the same
- Event payloads and ordering assumptions unchanged

## Pseudocode
Start with current architecture
  → Remove Redis from docker-compose
  → Add MinIO service to docker-compose
  → Replace ARQ with procrastinate in requirements.txt
  → Update config to remove Redis settings
  → Implement procrastinate workers instead of ARQ workers
  → Verify object storage client works with MinIO via S3_ENDPOINT_URL
  → Run tests to ensure all functionality preserved

## Testing Requirements
1. Verify all tasks (FitIngestionTask, TwinRecalibrationTask, etc.) execute successfully with procrastinate
2. Verify object storage operations (upload, download, exists) work with MinIO
3. Verify API endpoints that trigger async tasks return 202 Accepted with task_id
4. Verify GET /tasks/{task_id} returns correct status for procrastinate tasks
5. Verify DLQ handling works for failed procrastinate tasks
6. Verify system event publishing works with new task queue

## Coder Handoff Notes
## Coder Scope
Execute:  Steps 3, 4, 5, 6, 7  [OWNER: Coder] — includes migration generation
Skip:     Step 1 (DevOps — docker-compose update),
          Step 2 (DevOps — env vars update),
          Step 8 (Test Architect — tests),
          Step 9 (DevOps — service verification),
          Step 10 (DevOps — migration application),
          Step 11 (Test Architect — test suite)