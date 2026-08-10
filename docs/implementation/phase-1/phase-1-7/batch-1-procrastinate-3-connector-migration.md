# Batch BRD: Phase 1-7 Delta — Batch 1 — Procrastinate 3.x Connector Migration
## Source: docs/implementation/phase-1/phase-1-7/overview.md

## Batch Objective
Migrate the procrastinate worker from `Psycopg2Connector` (sync, psycopg2) to `PsycopgConnector` (async, psycopg3), repin procrastinate 2.x→3.x, and convert all defer call sites from sync `defer()` to `await defer_async()` so the worker process can start. This resolves the Significant Architecture Gap escalated in the architect resolution report.

## Preconditions
Phase-1-7 batch-1 (architecture simplification) is complete; its Batch Success Criteria hold. The worker container exits with code 2 at the procrastinate CLI gate because `Psycopg2Connector` is sync and the CLI requires an async connector. ADR-014 is accepted and supersedes ADR-010.

## Scope
- Connector swap in `app/worker/app.py`: `Psycopg2Connector` → `PsycopgConnector`
- Version repin in `requirements.txt`: `procrastinate>=2.0,<3.0` → `procrastinate>=3.0,<4.0`
- Defer contract migration at all 5 call sites: `defer(...)` → `await defer_async(...)`
- `task_dispatcher` seam on `ActivityIngestionService`: sync callable → async callable
- Conftest fixture update for async connector compatibility
- Side fix: `alembic/env.py` references non-existent `settings.POSTGRES_DSN`

## Out Of Scope
- Redis/Celery migration (rejected — adds infrastructure for no benefit at current scale)
- Custom async worker polling `procrastinate_jobs` (rejected — new abstraction, unjustified complexity)
- Alembic migration to psycopg3 (psycopg2 stays for alembic's sync engine)
- Removing psycopg2-binary from requirements.txt (still used by alembic)
- Architecture doc updates (routed separately to s-vision-and-architect-author via batch-1-architecture.md)
- ADR-014 writing (already written and indexed)

## Steps

1. [OWNER: Coder] Repin procrastinate in `requirements.txt` from `procrastinate>=2.0,<3.0` to `procrastinate>=3.0,<4.0`. The `psycopg[binary]>=3.1` dependency is already present (line 22) and will be activated by the connector swap. Do NOT remove `psycopg2-binary` — it is still used by alembic's sync engine.
   Primary: `requirements.txt` (current pins at lines 21-22)
   Secondary: ADR-014 (rationale for the repin and third-driver decision)
   Fallback: `docs/architecture/04-platform/async-pipeline.md` Infrastructure block (current version pin rationale)
   Forbidden: Do not remove `psycopg2-binary` from requirements.txt

2. [OWNER: Coder] Swap the connector in `app/worker/app.py` from `Psycopg2Connector` to `PsycopgConnector`. Change the import from `from procrastinate.contrib.psycopg2 import Psycopg2Connector` to `from procrastinate.contrib.psycopg import PsycopgConnector`. Change the app construction from `procrastinate.App(connector=Psycopg2Connector(dsn=get_procrastinate_dsn()))` to `procrastinate.App(connector=PsycopgConnector(conninfo=get_procrastinate_dsn()))`. Note: PsycopgConnector uses `conninfo=` keyword (not `dsn=`) per procrastinate 3.x API. The `get_procrastinate_dsn()` helper in `app/config.py` already strips `postgresql+psycopg2://` → `postgresql://` which produces a libpq-format DSN that PsycopgConnector accepts — no change to `app/config.py` is needed unless verification in Step 3 finds otherwise.
   Primary: `app/worker/app.py` (connector construction at ~L65), `app/config.py` (`get_procrastinate_dsn` at ~L90)
   Secondary: ADR-014 Compliance section (PsycopgConnector construction example)
   Fallback: `docs/adr/014-procrastinate-3-psycopg3-async-connector.md`
   Forbidden: Do not change `get_procrastinate_dsn()` to return a `postgresql+psycopg3://` URL — PsycopgConnector expects a libpq-format DSN (`postgresql://`), which is what the strip already produces

3. [OWNER: Coder] Verify the DSN format compatibility. `get_procrastinate_dsn()` in `app/config.py` strips `postgresql+psycopg2://` → `postgresql://` from `PROCRASTINATE_DATABASE_URL`. Confirm that `PsycopgConnector` accepts this libpq-format DSN. If it does (expected — psycopg3 accepts standard libpq DSNs), no change to `app/config.py` is needed. If it does not, adjust the strip to produce whatever format PsycopgConnector requires. The `PROCRASTINATE_DATABASE_URL` env var in `docker-compose.yml` stays as `postgresql+psycopg2://...` — the strip handles the conversion.
   Primary: `app/config.py` (`get_procrastinate_dsn` at ~L90), `docker-compose.yml` (worker env at L74)
   Secondary: PsycopgConnector upstream docs (conninfo parameter accepts libpq DSN)
   Fallback: `get_entity_context(PsycopgConnector)`

4. [OWNER: Coder] Convert the defer call site in `app/api/v1/activity.py` (L155) from `procrastinate_app.tasks["fit_ingest"].defer(...)` to `await procrastinate_app.tasks["fit_ingest"].defer_async(...)`. The route handler `post_upload_activity` is already `async def` — the `await` is valid. The defer happens after `session.commit()` at L140 — the after-commit ordering is preserved. Update the inline comment block (L142-L154) to reference ADR-014 instead of ADR-010 and to document `defer_async` instead of `defer`.
   Primary: `app/api/v1/activity.py` (defer call at L155, commit at L140)
   Secondary: ADR-014 Compliance section (async defer example)
   Fallback: `docs/adr/014-procrastinate-3-psycopg3-async-connector.md`

5. [OWNER: Coder] Convert the two defer call sites in `app/worker/app.py`: (a) `threshold_detection.defer(activity_id=activity_id)` at ~L200 inside the `signal_clean` task → `await threshold_detection.defer_async(activity_id=activity_id)`. The `signal_clean` task is already `async def` — the `await` is valid. The defer happens after `session.commit()` — the after-commit ordering is preserved. (b) `generate_first_message.defer(athlete_id=str(athlete_uuid))` at ~L365 inside the `generate_plan` task → `await generate_first_message.defer_async(athlete_id=str(athlete_uuid))`. The `generate_plan` task is already `async def` — the `await` is valid. The defer happens after `service.generate_plan()` which commits internally — the after-commit ordering is preserved. Update inline comments referencing ADR-010 to reference ADR-014.
   Primary: `app/worker/app.py` (defer at ~L200 and ~L365)
   Secondary: ADR-014 Compliance section
   Fallback: `docs/adr/014-procrastinate-3-psycopg3-async-connector.md`

6. [OWNER: Coder] Convert the `task_dispatcher` seam and `_defer_signal_clean` in `app/services/activity_ingestion_service.py`. (a) Update the constructor docstring/comment block (~L158-L172) to document the seam as an async callable `async (**kwargs) -> int` per ADR-014, replacing the sync callable documentation per ADR-010. (b) In `_defer_signal_clean` (~L832-L868), change `dispatcher(activity_id=str(activity_id))` to `await dispatcher(activity_id=str(activity_id))`. The method is already `async def` — the `await` is valid. (c) Change the lazy resolution from `signal_clean.defer` to `signal_clean.defer_async` at ~L858. The swallow-and-log failure isolation pattern is preserved — the `try/except` around the defer call stays.
   Primary: `app/services/activity_ingestion_service.py` (seam at ~L158, `_defer_signal_clean` at ~L832)
   Secondary: ADR-014 Compliance section (async dispatcher seam example), ADR-009 (decoupling principle — unchanged)
   Fallback: `docs/adr/014-procrastinate-3-psycopg3-async-connector.md`

7. [OWNER: Coder] Convert the defer call inside `_defer_generate_plan` in `app/services/onboarding_service.py` (~L502-L519). Change `dispatcher = cast(Callable[..., Any], generate_plan.defer)` to `dispatcher = cast(Callable[..., Any], generate_plan.defer_async)` and change `dispatcher(...)` to `await dispatcher(...)`. The method is already `async def` — the `await` is valid. The swallow-and-log failure isolation pattern is preserved. Update the docstring reference from ADR-010 to ADR-014.
   Primary: `app/services/onboarding_service.py` (`_defer_generate_plan` at ~L502)
   Secondary: ADR-014 Compliance section
   Fallback: `docs/adr/014-procrastinate-3-psycopg3-async-connector.md`

8. [OWNER: Coder] Update the conftest fixture `_open_procrastinate_app` in `tests/conftest.py` (~L139-L178) for async connector compatibility. The current fixture uses `with procrastinate_app.open():` (sync context manager) and `procrastinate_app.schema_manager.apply_schema()`. With `PsycopgConnector` (async), verify whether `app.open()` still works as a sync context manager or whether the fixture needs `async with procrastinate_app.open_async():` and `await procrastinate_app.schema_manager.apply_schema_async()`. If the sync `open()` is not available on an async connector, convert the fixture to an async fixture (using `pytest-asyncio` session-scoped async fixture). The `ConnectorException` / `DuplicateObject` handling for `apply_schema` must be preserved — the schema is not idempotent and re-runs are the expected steady state.
   Primary: `tests/conftest.py` (`_open_procrastinate_app` at ~L139)
   Secondary: `tests/conftest.py` (`_ensure_procrastinate_test_url` at ~L29 — env var setup, unchanged)
   Fallback: PsycopgConnector upstream docs (open vs open_async)

9. [OWNER: Coder] Fix the side observation in `alembic/env.py` at ~L68. The code references `settings.POSTGRES_DSN` which does not exist in `app/config.py` — the correct attribute is `settings.DATABASE_URL`. Change `settings.POSTGRES_DSN` to `settings.DATABASE_URL`. This is unrelated to the connector migration but was flagged in the architect resolution report and is a one-line fix in a file already in scope.
   Primary: `alembic/env.py` (L68), `app/config.py` (Settings class — DATABASE_URL field)
   Secondary: Architect resolution report side observation
   Fallback: `grep_files` for `POSTGRES_DSN` across the codebase

10. [OWNER: Coder] Verify the docker-compose worker command. The current command is `procrastinate --app=app.worker.app.app worker`. Procrastinate 3.x CLI syntax is the same (`procrastinate --app=<module.path> worker`) — no change expected. If the 3.x CLI changed the syntax, update the command in `docker-compose.yml` (L81). The `PROCRASTINATE_DATABASE_URL` env var stays as `postgresql+psycopg2://...` — the strip in `get_procrastinate_dsn()` handles the conversion to libpq format.
   Primary: `docker-compose.yml` (worker service at L65-L81)
   Secondary: Procrastinate 3.x CLI docs
   Fallback: `procrastinate --help` in the worker container after repin

> (This is everything relevant to the steps above. Primary items are
> fetched together in Pre-Flight Step 3; Secondary and Fallback are
> requested only on demand.)

## Batch Success Criteria
Batch 1 complete when:
- `requirements.txt` pins `procrastinate>=3.0,<4.0`; `psycopg2-binary` is still present (for alembic)
- `app/worker/app.py` constructs `procrastinate.App(connector=PsycopgConnector(conninfo=get_procrastinate_dsn()))` — no `Psycopg2Connector` import or usage remains
- All 5 defer call sites use `await ...defer_async(...)` — no sync `.defer(` calls remain in `app/`
- `ActivityIngestionService.task_dispatcher` seam is documented as async; `_defer_signal_clean` uses `await dispatcher(...)`
- `tests/conftest.py` `_open_procrastinate_app` fixture works with the async connector — the test suite opens the app and applies schema without `SyncConnectorConfigurationError`
- `alembic/env.py` references `settings.DATABASE_URL` (not `settings.POSTGRES_DSN`)
- The worker container starts without exiting with code 2 — `procrastinate --app=app.worker.app.app worker` runs
- All existing tests pass (no behavioural change — only connector type and defer call style change)

## Relevant Invariants
- "All heavy processing is async. FIT parsing, twin recalibration, post-workout analysis — all run in a worker queue. API responses never wait for these. The queue backend is decoupled; early-stage implementation uses PostgreSQL-backed workers (`procrastinate`), with a defined migration path to Redis if queue contention requires it." (`principles.md`, field `procrastinate`)
- "Signal cleaning runs in its own procrastinate task with its own `AsyncSession`; it never runs inline inside `ActivityIngestionService._run_ingestion_pipeline`'s transaction." (ADR-009)
- "A signal-cleaning failure MUST NOT roll back the already-committed `Activity` row; the task raises so procrastinate retries it; `Activity.cleaning_pipeline_version` stays `null` until a retry succeeds." (ADR-009)
- "At-least-once delivery: tasks may execute more than once. All tasks must be idempotent or have idempotency checks." (`async-pipeline.md`)

## Relevant Notes
- Architecture documentation updates for the connector migration are in `batch-1-architecture.md` — routed separately to s-vision-and-architect-author. The coder does not modify architecture docs.
- ADR-014 (`docs/adr/014-procrastinate-3-psycopg3-async-connector.md`) is already written and indexed. It supersedes ADR-010. The coder does not modify ADRs.
- The `task_dispatcher` seam on `ActivityIngestionService` is the canonical seam per ADR-010 (now ADR-014). Every test fake injected through this seam must follow the new async shape (`async def __call__`). State Explorer confirmed no test file currently injects a `task_dispatcher` fake — the blast radius is zero for existing tests.
- The test fake in `tests/integration/test_onboarding_service.py:375` (`failing_defer`) is already `async def` — no change needed. It monkeypatches `_defer_generate_plan` (not `task_dispatcher`), and the method is already async.
- The defer-transaction-boundary is an existing characteristic: the procrastinate connector uses its own connection pool, not the caller's `AsyncSession`. A defer INSERT into `procrastinate_jobs` is committed by the connector's own connection, independent of the caller's transaction. This is true for both sync `defer()` and async `defer_async()` — the migration does not change this behaviour. The swallow-and-log pattern in `_defer_signal_clean` and `_defer_generate_plan` is the mitigation for defer failures.

## Relevant Pseudocode
From ADR-014 Compliance section:
```python
# app/worker/app.py — async connector
from procrastinate.contrib.psycopg import PsycopgConnector
app = procrastinate.App(connector=PsycopgConnector(conninfo=get_procrastinate_dsn()))

# app/api/v1/activity.py — async defer, awaited
job = await procrastinate_app.tasks["fit_ingest"].defer_async(
    athlete_id=str(athlete_id),
    activity_id=str(activity.id),
)

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

## Files Expected To Change
- [EXISTING — modified] `requirements.txt` — repin procrastinate 3.x
- [EXISTING — modified] `app/worker/app.py` — connector swap + 2 defer call sites
- [EXISTING — modified] `app/api/v1/activity.py` — defer → await defer_async
- [EXISTING — modified] `app/services/activity_ingestion_service.py` — seam doc + _defer_signal_clean
- [EXISTING — modified] `app/services/onboarding_service.py` — _defer_generate_plan defer call
- [EXISTING — modified] `tests/conftest.py` — _open_procrastinate_app fixture
- [EXISTING — modified] `alembic/env.py` — side fix: POSTGRES_DSN → DATABASE_URL
- [EXISTING — reference only] `docker-compose.yml` — verify worker command (may not need changes)
- [EXISTING — reference only] `app/config.py` — verify DSN format (may not need changes)
- [EXISTING — reference only] `docs/adr/014-procrastinate-3-psycopg3-async-connector.md` — already written, for compliance reference
- [EXISTING — reference only] `docs/adr/010-procrastinate-sync-defer-on-psycopg2-connector.md` — already superseded, for reference

## Coder Notes
- The procrastinate 3.x schema is forward-compatible from 2.x per upstream release notes. After the repin, run `procrastinate --app=app.worker.app.app schema --apply` in the worker container to ensure any 3.x-specific schema changes are applied. This is not an alembic migration — procrastinate manages its own schema (`procrastinate_jobs`, `procrastinate_workers`, etc.).
- The `PsycopgConnector` constructor keyword is `conninfo=` (not `dsn=` as in `Psycopg2Connector`). This is a procrastinate 3.x API change — the coder must use the correct keyword.
- The `app.open()` sync context manager may not be available on an async connector. If `tests/conftest.py` fixture fails with an error about the connector being async, convert to `async with app.open_async():` and `await app.schema_manager.apply_schema_async()`. The `ConnectorException` / `DuplicateObject` handling must be preserved in the async form.
- The `PROCRASTINATE_DATABASE_URL` env var stays as `postgresql+psycopg2://...` in docker-compose.yml and .env. The `get_procrastinate_dsn()` strip converts it to `postgresql://` (libpq format) which PsycopgConnector accepts. Do not change the env var to `postgresql+psycopg3://` — the strip would not match and the connector would receive a malformed DSN.
