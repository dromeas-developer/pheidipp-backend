---
id: ADR-014
status: accepted
tags: [async-pipeline, procrastinate, connector, task-queue, testing, psycopg3]
supersedes: ADR-010
superseded-by: ~
---

# ADR 014: Procrastinate 3.x With PsycopgConnector (psycopg3) — Async Defer

## Rules
**Async defer only**: All call sites that enqueue a procrastinate task MUST use `await defer_async(...)`, never sync `defer`. This applies to every `procrastinate_app.tasks["<name>"].defer_async(...)` call in `app/`.
**Async dispatcher seam**: The `task_dispatcher` constructor parameter on `ActivityIngestionService` (and any future service that defers a procrastinate task) MUST be an async callable `async (**kwargs) -> int`, a coroutine. Test fakes injected through this seam MUST be async (`async def __call__`, not `def __call__`).
**`await` required on defer**: A `defer_async(...)` call MUST be awaited. Calling it without `await` returns a coroutine that is never executed — the job is never enqueued.
**Connector is async**: The shared `procrastinate.App` in `app/worker/app.py` is configured with `PsycopgConnector` (psycopg3, async-capable). Both `defer_async` and the procrastinate CLI worker are supported.
**Third driver is deliberate**: psycopg3 (`psycopg[binary]>=3.1`) is activated as the procrastinate connector driver alongside asyncpg (application async pool) and psycopg2 (alembic sync engine). The third-driver cost is accepted as the price of a working worker process.

## Decision
The shared procrastinate `App` in `app/worker/app.py` is migrated from `Psycopg2Connector` (psycopg2, sync-only) to `PsycopgConnector` (psycopg3, async-capable), and the procrastinate version pin is repinned from `>=2.0,<3.0` to `>=3.0,<4.0`. All task enqueue call sites switch from sync `defer(...)` to `await defer_async(...)`. The `task_dispatcher` seam on `ActivityIngestionService` changes from a sync callable to an async callable. This decision is forced by procrastinate 2.x's categorical refusal to run a worker with a sync connector at any entrypoint (CLI, `App.run_worker`, `App.run_worker_async`) — the architecture as previously specified (sync connector + sync defer + async worker tasks) is unimplementable in procrastinate 2.x.

## Rationale
- Procrastinate 2.x's `BaseConnector` (the sync base class that `Psycopg2Connector` subclasses) defines all async methods (`open_async`, `execute_query_async`, `listen_notify`) to unconditionally raise `SyncConnectorConfigurationError`. The CLI gate is only one of three enforcement points; bypassing the CLI does not bypass the connector-class constraint. There is no entrypoint in procrastinate 2.x that runs a worker with a sync connector.
- `PsycopgConnector` (psycopg3-based) is the only async connector available in procrastinate without a third-party driver. It supports both `defer_async` (for enqueue) and the CLI worker (for execution), resolving the startup blocker.
- `psycopg[binary]>=3.1` is already declared in `requirements.txt` (line 22) but currently has zero imports in `app/` or `tests/`. This migration activates an existing dependency rather than introducing a new one.
- The migration preserves the existing task abstractions (`@app.task` decorators, task names, task bodies), the worker process model (separate container, CLI-launched), and the defer-after-commit ordering pattern. No new architectural abstractions are introduced.
- For initial rollout with a small user base, this is the simplest path that produces a working worker without adding infrastructure (no Redis) or creating new abstractions (no custom poller). The architecture's stated migration target (Redis/Celery) remains available for future queue contention but is not accelerated.

## Alternatives Rejected
| Option | Why Rejected |
|---|---|
| Custom async worker polling `procrastinate_jobs` directly with SQLAlchemy `AsyncSession` (Path B from delta proposal) | Creates a new architectural abstraction (custom runner) the architecture corpus does not name. Depends on `procrastinate_jobs` internal schema (column names the library does not formally promise). Introduces a new ownership boundary, event contract (poll loop), and invariant (exactly-once fetch under concurrent pollers). Unjustified complexity for a small user base. |
| Accelerate Redis/Celery migration (Path C from delta proposal) | Adds a third infrastructure service (Redis) to the stack — contradicts the Phase 1-7 simplification goal of PostgreSQL + MinIO only. For a small user base, Redis latency benefit is irrelevant. Largest deviation: ~10+ files, every defer call site rewritten, every test fixture rewritten, two ADRs superseded, docker-compose changes. A full sub-phase, not a delta. |
| Run the worker programmatically inside an async context, keeping the sync connector (coder's option (b)) | `App.run_worker_async` requires the connector to be async. `app.open_async()` invokes `connector.open_async` which raises `SyncConnectorConfigurationError` on `BaseConnector`. The async methods are defined to raise, not merely unimplemented. Converts a clean startup error into a runtime crash at first async I/O — strictly worse operationally. |
| Keep procrastinate 2.x and use `defer` only, accepting no worker process | The architecture requires a worker process (async-pipeline.md: "Worker tasks run in separate process"). Without a worker, deferred tasks never execute — the entire async pipeline is non-functional. |

## Tradeoffs
- **Pro**: The worker process starts and runs — the startup blocker is resolved. The CLI worker, `defer_async`, and all async connector methods work as designed.
- **Pro**: No new infrastructure (no Redis), no new abstractions (no custom runner). The existing task inventory, task names, and task bodies are unchanged.
- **Pro**: Moves toward stack-truth compliance — `PsycopgConnector` is async, aligning with ADR-002's "no sync SQLAlchemy" mandate. The sync connector was the one documented exception to the async-first rule; this migration eliminates the exception.
- **Con**: Activates a third database driver (psycopg3 alongside asyncpg and psycopg2). psycopg2's only remaining use after this migration is alembic's sync engine. A future cleanup could migrate alembic to psycopg3, reducing back to two drivers — but that is out of scope for this delta.
- **Con**: The `task_dispatcher` seam signature changes from sync to async, requiring every test fake injected through that seam to become `async def __call__`. In the current codebase, no test file directly injects a `task_dispatcher` fake (State Explorer confirmed), so the blast radius is small — but future tests must follow the new async shape.
- **Con**: Procrastinate 3.x schema is forward-compatible from 2.x per upstream release notes, but the `procrastinate --app=... schema --apply` must be re-run in the worker container after the repin to ensure any 3.x-specific schema changes are applied.

## Compliance

**Compliant**
```python
# app/worker/app.py — async connector
from procrastinate.contrib.psycopg import PsycopgConnector

app = procrastinate.App(connector=PsycopgConnector(conninfo=get_procrastinate_dsn()))
```

```python
# app/api/v1/activity.py — async defer, awaited
job = await procrastinate_app.tasks["fit_ingest"].defer_async(
    athlete_id=str(athlete_id),
    activity_id=str(activity.id),
)
```

```python
# app/services/activity_ingestion_service.py — async dispatcher seam
async def _defer_signal_clean(self, *, activity_id: uuid.UUID) -> None:
    dispatcher = self._task_dispatcher
    if dispatcher is None:
        from app.worker.app import signal_clean
        dispatcher = signal_clean.defer_async
    try:
        await dispatcher(activity_id=str(activity_id))
    except Exception as exc:
        log_event(...)
```

```python
# tests — async fake matching the seam contract
class _RecordingDispatcher:
    def __init__(self) -> None:
        self.call_log: list[dict] = []

    async def __call__(self, **kwargs: Any) -> int:  # async, awaited
        self.call_log.append(kwargs)
        return len(self.call_log)
```

**Non-compliant**
```python
# WRONG: sync defer on PsycopgConnector — not available in 3.x
job = procrastinate_app.tasks["fit_ingest"].defer(...)
```

```python
# WRONG: sync fake does not match the async seam contract
class _RecordingDispatcher:
    def __call__(self, **kwargs: Any) -> int:  # sync — will not be awaited
        ...
```

```python
# WRONG: defer_async without await — coroutine never executed, job never enqueued
job = procrastinate_app.tasks["fit_ingest"].defer_async(...)
```

## Cross-References
- [ADR-010: Procrastinate Sync `defer` On Psycopg2Connector](./010-procrastinate-sync-defer-on-psycopg2-connector.md) — superseded by this ADR. The sync-only rule, sync dispatcher seam, and Psycopg2Connector constraint are all replaced by the async equivalents defined here.
- [ADR-009: Signal Cleaning As A Decoupled Async Task](./009-signal-cleaning-as-decoupled-async-task.md) — defines the `signal_clean` task and the `task_dispatcher` seam. The decoupling principle (separate task, own session, failure isolation) is unchanged; only the defer call shape changes from sync `defer()` to `await defer_async()`.
- [ADR-002: Async-First Database Access](./002-async-first-database-access.md) — establishes the async-first DB access rule. This ADR eliminates the one documented exception (sync procrastinate defer) by moving the connector to async.
- `docs/architecture/04-platform/async-pipeline.md` — Infrastructure block: connector type, version pin, worker mechanism. Updated to reflect PsycopgConnector and procrastinate 3.x.
- `docs/architecture/04-platform/storage-topology.md` — "Why PostgreSQL for the task queue" paragraph: updated to reflect 3.x connector as the chosen path.
