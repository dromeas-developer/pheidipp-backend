# app/worker/

## Purpose
Procrastinate worker application — PostgreSQL-backed async task queue for heavy processing. Tasks defined here are enqueued by the API layer (via FastAPI route handlers) and executed by a separate worker process. This keeps API responses fast by deferring FIT parsing, twin recalibration, and post-workout analysis to the background.

## Contents
### Worker
| File | Responsibility |
|---|---|
| `app.py` | Procrastinate `App` instance with `PsycopgConnector` and registered async tasks: `fit_ingest`, `recalibrate_twin`, `signal_clean`, `threshold_detection`, `generate_plan`, `generate_first_message`, `outbox_publisher` |

## Architecture Notes
- Procrastinate 3.x (`procrastinate>=3.0,<4.0`) is used with `PsycopgConnector` (psycopg3-based, async-capable), constructed as `PsycopgConnector(conninfo=get_procrastinate_dsn())` — the `conninfo=` keyword replaces 2.x's `dsn=`. The 2.x `Psycopg2Connector` (sync-only) cannot run the procrastinate CLI worker. See ADR-014 for the connector migration decision.
- The worker reads `PROCRASTINATE_DATABASE_URL` from environment — the DSN converter in `app.config` strips SQLAlchemy `+driver` suffixes, yielding the libpq-format `postgresql://` DSN `PsycopgConnector` expects. The env var itself stays `postgresql+psycopg2://…`; `psycopg2-binary` remains installed for alembic's sync engine.
- Workers are started via `procrastinate --app=app.worker.app.app worker` as a separate process from the API server. The procrastinate schema is managed by procrastinate itself (`schema --apply`), not by alembic.
- All tasks are `async def` and create their own `AsyncSession` instances — no session sharing between tasks or with the API layer.
- Task queue invariants per `async-pipeline.md`: API responses never wait for heavy processing; queue backend is decoupled from the API.
- The `outbox_publisher` task polls every 15 seconds (cron `*/15 * * * * *`) and delegates the publish-side transaction to `OutboxPublisherService` per ADR-013. The worker owns scheduling and exception handling only — it does not construct repositories or open sessions (ADR-001 `WorkerIntegration` / `RepositoryAccess`). The service is idempotent (filters on `status = 'pending'`) and operates in its own transaction. No external message bus is involved — the future-bus insertion point is documented inside the service.
- All task enqueue uses `await ….defer_async(...)` per ADR-014 — the sync `defer()` method is unavailable on an async connector. Worker-internal chaining follows this too: `signal_clean` defers `threshold_detection` (only when the cleaning run created a row), and `generate_plan` defers `generate_first_message` after the plan is durably committed.
- Defers run on the connector's own connection pool, independent of the caller's `AsyncSession` transaction — every defer is therefore placed after the caller's commit so the queued job never observes uncommitted state.

## Cross-References
- [Platform: Async Pipeline](../../docs/architecture/04-platform/async-pipeline.md) — task queue invariants and worker topology
- [ADR-013: Outbox Publisher Service Ownership](../../docs/architecture/adr/ADR-013-outbox-publisher-service-ownership.md) — `OutboxPublisherService` owns the publish-side transaction; worker tasks must not construct repositories directly
- [ADR-014: Procrastinate 3.x / psycopg3 Async Connector](../../docs/adr/014-procrastinate-3-psycopg3-async-connector.md) — supersedes ADR-010; connector swap and the `defer_async` contract
