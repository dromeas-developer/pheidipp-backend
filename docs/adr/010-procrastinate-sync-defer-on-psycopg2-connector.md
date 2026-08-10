---
id: ADR-010
status: superseded
tags: [async-pipeline, procrastinate, connector, task-queue, testing]
supersedes: ~
superseded-by: ADR-014
---

# ADR 010: Procrastinate Sync `defer` On Psycopg2Connector

## Rules
**Sync defer only**: All call sites that enqueue a procrastinate task MUST use the sync `defer` method, never `defer_async`. This applies to every `procrastinate_app.tasks["<name>"].defer(...)` call in `app/`.
**Sync dispatcher seam**: The `task_dispatcher` constructor parameter on `ActivityIngestionService` (and any future service that defers a procrastinate task) MUST be a sync callable `(**kwargs) -> int`, not a coroutine. Test fakes injected via this seam MUST be sync (`def __call__`, not `async def __call__`).
**No `await` on defer**: A `defer(...)` call MUST NOT be awaited. `await defer(...)` is a type error against a sync callable and will fail at runtime.
**Connector is the constraint**: The sync-only rule is a direct consequence of the `Psycopg2Connector` choice in `app/worker/app.py`. It is NOT negotiable at the call site — if a call site needs `defer_async`, the connector must be upgraded first (see Alternatives Rejected).

## Decision
Every procrastinate task enqueue in the application uses the sync `defer` method because the shared `procrastinate.App` in `app/worker/app.py` is configured with `Psycopg2Connector` (psycopg2, sync-only). `defer_async` on a `Psycopg2Connector` unconditionally raises `SyncConnectorConfigurationError` at runtime. The `task_dispatcher` test seam on `ActivityIngestionService` is therefore a sync callable, and all test fakes that stand in for `procrastinate_app.tasks[...].defer` must be sync.

## Rationale
- The shared procrastinate app is constructed once with `Psycopg2Connector` (`app/worker/app.py`), and both the API and worker containers import that same instance. There is no per-call-site connector choice — the constraint is global, so the defer method choice must be global too.
- `defer_async` is the more intuitive method name in an async-first codebase, so the bug it introduces is non-obvious: it passes unit and integration tests (which inject async fakes that happen to satisfy the `await dispatcher(...)` shape) but fails in real runtime where the connector is sync. An ADR makes the constraint explicit so future contributors do not re-derive it by hitting the same runtime failure.
- The defer operation is a lightweight single-row INSERT into `procrastinate_jobs`. Calling it synchronously from an async endpoint or service adds negligible blocking time (sub-millisecond on a local PostgreSQL) and does not justify a connector migration.
- Procrastinate 2.x is used deliberately with psycopg2 because the queue is transitional (per the `app/worker/app.py` module docstring). Upgrading to procrastinate 3.x + psycopg3 to unlock `defer_async` is a larger dependency migration that is out of scope for the current phase; the sync defer rule is the stable contract until that migration happens.

## Alternatives Rejected
| Option | Why Rejected |
|---|---|
| Use `defer_async` and wrap in `asyncio.to_thread()` | Does not fix the bug. `defer_async` on `Psycopg2Connector` raises `SyncConnectorConfigurationError` unconditionally — the raise happens inside procrastinate's connector before any thread dispatch, so wrapping the call does not help. |
| Migrate to procrastinate 3.x + `PsycopgConnector` (psycopg3) to unlock `defer_async` | Valid long-term path but a larger dependency migration (psycopg2 → psycopg3 across the codebase, procrastinate 2.x → 3.x connector API changes). Out of scope for the current phase; the queue is explicitly transitional. Revisit when the queue backend is upgraded. |
| Keep `defer_async` and switch the connector to an async-capable one in `app/worker/app.py` only | The connector is shared by the worker CLI and every import site. Changing it in isolation would break the worker's sync entrypoint and any test that imports `app.worker.app` without an async event loop. The connector choice is a global decision, not a per-call-site one. |
| Add a runtime adapter that auto-detects connector type and picks `defer` vs `defer_async` | Hides the constraint behind magic and makes the test seam ambiguous (is the fake sync or async?). An explicit, documented rule is cheaper than an adapter and keeps the seam contract unambiguous. |

## Tradeoffs
- **Pro**: One rule, one call shape, one test seam contract — no per-call-site reasoning about connector capabilities.
- **Pro**: The sync defer path is provably correct against the current connector; no runtime `SyncConnectorConfigurationError` surprises in production.
- **Pro**: Test fakes are simpler (sync callables are easier to construct and reason about than coroutines).
- **Con**: A sync DB INSERT runs on the event loop thread of the calling async endpoint or service. For the current defer workload (single-row INSERT) this is negligible, but a future high-frequency enqueue path could starve the event loop and would need `asyncio.to_thread()` wrapping — at which point the connector migration becomes the better fix.
- **Con**: The rule is coupled to the `Psycopg2Connector` choice. If/when the codebase migrates to procrastinate 3.x + psycopg3, this ADR must be revisited and likely superseded to re-allow `defer_async`.

## Compliance

**Compliant**
```python
# app/api/v1/activity.py — sync defer, no await
job = procrastinate_app.tasks["fit_ingest"].defer(
    athlete_id=str(athlete_id),
    activity_id=str(activity.id),
)
```

```python
# app/services/activity_ingestion_service.py — sync dispatcher seam
dispatcher = procrastinate_app.tasks["signal_clean"].defer
try:
    dispatcher(activity_id=str(activity_id))
except Exception as exc:
    log_event(...)
```

```python
# tests — sync fake matching the seam contract
@dataclass
class _RecordingDispatcher:
    call_log: List[dict] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> int:  # sync, not async
        self.call_log.append(kwargs)
        return len(self.call_log)
```

**Non-compliant**
```python
# WRONG: defer_async on a Psycopg2Connector raises SyncConnectorConfigurationError
job = await procrastinate_app.tasks["fit_ingest"].defer_async(
    athlete_id=str(athlete_id),
    activity_id=str(activity.id),
)
```

```python
# WRONG: async fake does not match the sync seam contract
class _RecordingDispatcher:
    async def __call__(self, **kwargs: Any) -> int:  # async — will not be awaited
        ...
```

```python
# WRONG: awaiting a sync callable is a type error and fails at runtime
job = await procrastinate_app.tasks["fit_ingest"].defer(
    athlete_id=str(athlete_id),
    activity_id=str(activity.id),
)
```

## Cross-References
- [ADR-009: Signal Cleaning As A Decoupled Async Task](./009-signal-cleaning-as-decoupled-async-task.md) — defines the `signal_clean` task and the `task_dispatcher` seam that this ADR constrains to sync.
- [ADR-002: Async-First Database Access](./002-async-first-database-access.md) — establishes the async-first DB access rule; this ADR carves out the single exception (procrastinate defer) because the connector is sync-only, and documents why the exception is safe.
- `app/worker/app.py` module docstring — records the deliberate procrastinate 2.x + psycopg2 choice and the transitional nature of the queue; this ADR is the downstream consequence of that choice.
- `04-platform/async-pipeline.md` — defines the task enqueue points (`fit_ingest`, `signal_clean`, `recalibrate_twin`) that this ADR constrains to sync defer.
