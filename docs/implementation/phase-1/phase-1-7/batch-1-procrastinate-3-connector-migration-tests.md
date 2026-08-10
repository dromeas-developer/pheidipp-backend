# Test Scenarios — Phase 1-7 Delta — Batch 1: Procrastinate 3.x Connector Migration

## Step 2 — Connector swap (Psycopg2Connector → PsycopgConnector)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | Worker app constructs with async connector | Import `app.worker.app.app` | `app.connector` is an instance of `PsycopgConnector` (not `Psycopg2Connector`); no `SyncConnectorConfigurationError` raised at import time | application-logic | none |
| 2 | Worker CLI starts without sync-connector gate | Run `procrastinate --app=app.worker.app.app worker` in a container with the repinned procrastinate 3.x | Worker process starts and stays running (does not exit with code 2); no `argparse.ArgumentError` about async connector | application-logic | external-only |

## Steps 4–7 — Defer contract migration (defer → await defer_async)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 3 | FIT upload enqueues fit_ingest via defer_async | `POST /athletes/{id}/activities/upload` with a valid FIT file, after the route commits the Activity row | `defer_async` is called (not sync `defer`); a row is inserted into `procrastinate_jobs` with `task_name = 'fit_ingest'`; response is 202 with a `task_id` | application-logic | external-only |
| 4 | signal_clean enqueues threshold_detection via defer_async | Run `signal_clean` task for an eligible activity; the task commits the cleaned stream | `defer_async` is called for `threshold_detection` (not sync `defer`); a row is inserted into `procrastinate_jobs` with `task_name = 'threshold_detection'`; the defer happens after `session.commit()` | application-logic | external-only |
| 5 | generate_plan enqueues generate_first_message via defer_async | Run `generate_plan` task for an athlete; the service commits the plan | `defer_async` is called for `generate_first_message` (not sync `defer`); a row is inserted into `procrastinate_jobs` with `task_name = 'generate_first_message'`; the defer happens after `service.generate_plan()` returns (post-commit) | application-logic | external-only |
| 6 | _defer_signal_clean uses async dispatcher | `ActivityIngestionService.run_ingestion_pipeline` for a running, calibration-eligible, non-manual activity | `_defer_signal_clean` calls `await dispatcher(activity_id=...)`; the dispatcher resolves to `signal_clean.defer_async`; a row is inserted into `procrastinate_jobs` with `task_name = 'signal_clean'` | application-logic | external-only |
| 7 | _defer_generate_plan uses async defer_async | `OnboardingService.complete_onboarding` after the onboarding commit | `_defer_generate_plan` calls `await dispatcher(athlete_id)`; the dispatcher resolves to `generate_plan.defer_async`; a row is inserted into `procrastinate_jobs` with `task_name = 'generate_plan'` | application-logic | external-only |

## Steps 4–7 — Failure isolation (swallow-and-log preserved)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 8 | _defer_signal_clean swallows defer failure | `ActivityIngestionService` with a `task_dispatcher` fake that raises `RuntimeError("defer failed")`; `run_ingestion_pipeline` for an eligible activity | The ingestion pipeline completes successfully; the Activity is committed with load scores; the `RuntimeError` is caught and logged via `log_event(event="activity.signal_clean.enqueue.failure", ...)`; no exception propagates to the caller | application-logic | db-session |
| 9 | _defer_generate_plan swallows defer failure | `OnboardingService` with `_defer_generate_plan` monkeypatched to raise `RuntimeError("procrastinate defer failed")`; `complete_onboarding` called | Onboarding completes successfully; `athlete.onboarding_complete` is `True`; the `RuntimeError` is caught and logged via `log_event(event="generate_plan.defer.failure", ...)`; the `twin_model_ready` outbox row is committed | application-logic | db-session |
| 10 | task_dispatcher seam accepts async fake | `ActivityIngestionService` constructed with `task_dispatcher=AsyncRecordingDispatcher()` (an `async def __call__` fake); `run_ingestion_pipeline` for an eligible activity | The fake is awaited (not called sync); `fake.call_log` contains `{"activity_id": "<uuid-str>"}`; the pipeline completes without `TypeError: object coroutine can't be used in 'await' expression` | application-logic | none |

## Step 8 — Conftest fixture compatibility

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 11 | Test suite opens procrastinate app with async connector | Run `pytest` with the repinned procrastinate 3.x and PsycopgConnector | The `_open_procrastinate_app` fixture opens the app (via `open()` or `open_async()` as appropriate for the async connector); `schema_manager.apply_schema()` (or `apply_schema_async()`) runs; the `ConnectorException` / `DuplicateObject` handling skips duplicate-DDL errors; the test session proceeds without `SyncConnectorConfigurationError` | application-logic | none |

## Step 9 — Side fix (alembic/env.py)

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 12 | Alembic offline mode does not raise AttributeError | Run `alembic revision --autogenerate -m "test"` (or any alembic command that reads `env.py`) | `env.py` reads `settings.DATABASE_URL` (not `settings.POSTGRES_DSN`); no `AttributeError: 'Settings' object has no attribute 'POSTGRES_DSN'` | application-logic | none |
