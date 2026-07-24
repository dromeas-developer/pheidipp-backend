# app/worker/

## Purpose
Procrastinate worker application — PostgreSQL-backed async task queue for heavy processing. Tasks defined here are enqueued by the API layer (via FastAPI route handlers) and executed by a separate worker process. This keeps API responses fast by deferring FIT parsing, twin recalibration, and post-workout analysis to the background.

## Contents
### Worker
| File | Responsibility |
|---|---|
| `app.py` | Procrastinate `App` instance with `Psycopg2Connector` and registered async tasks: `fit_ingest`, `recalibrate_twin`, `signal_clean`, `threshold_detection`, `outbox_publisher` |

## Architecture Notes
- Procrastinate 2.x is used deliberately with `Psycopg2Connector` for psycopg2 compatibility; the queue is transitional and 3.x migration is intentionally deferred.
- The worker reads `PROCRASTINATE_DATABASE_URL` from environment — the DSN converter in `app.config` strips SQLAlchemy `+driver` suffixes for procrastinate compatibility.
- Workers are started via `procrastinate --app=app.worker.app worker` as a separate process from the API server.
- All tasks are `async def` and create their own `AsyncSession` instances — no session sharing between tasks or with the API layer.
- Task queue invariants per `async-pipeline.md`: API responses never wait for heavy processing; queue backend is decoupled from the API.
- The `outbox_publisher` task polls every 15 seconds (cron `*/15 * * * * *`) and delegates the publish-side transaction to `OutboxPublisherService` per ADR-013. The worker owns scheduling and exception handling only — it does not construct repositories or open sessions (ADR-001 `WorkerIntegration` / `RepositoryAccess`). The service is idempotent (filters on `status = 'pending'`) and operates in its own transaction. No external message bus is involved — the future-bus insertion point is documented inside the service.

## Cross-References
- [Platform: Async Pipeline](../../docs/architecture/04-platform/async-pipeline.md) — task queue invariants and worker topology
- [ADR-013: Outbox Publisher Service Ownership](../../docs/architecture/adr/ADR-013-outbox-publisher-service-ownership.md) — `OutboxPublisherService` owns the publish-side transaction; worker tasks must not construct repositories directly
