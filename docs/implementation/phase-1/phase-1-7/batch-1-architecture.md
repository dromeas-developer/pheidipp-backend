# Architecture Documentation Updates — Phase 1-7 Delta — Batch 1: Procrastinate 3.x Connector Migration

## docs/architecture/04-platform/async-pipeline.md
### Infrastructure block (lines 12-15)
- Update connector from `Psycopg2Connector (sync-compatible, built on psycopg2)` to `PsycopgConnector (async-capable, built on psycopg3)`
- Update version constraint from `procrastinate>=2.0,<3.0` to `procrastinate>=3.0,<4.0`
- Update the pin rationale: "Pinned to 3.x to use PsycopgConnector (psycopg3-based, async-capable) which is required for the procrastinate CLI worker. The 2.x Psycopg2Connector (sync-only) cannot run a worker at any entrypoint — procrastinate 2.x's BaseConnector defines all async methods to raise SyncConnectorConfigurationError unconditionally."
- Update "Worker tasks run in separate process; sync connector acceptable for current scale" to "Worker tasks run in separate process; async connector required for the procrastinate CLI worker."
- Update migration path note: "Redis/Celery remains the longer-term migration path if queue contention appears, but the queue is no longer pinned to 2.x + psycopg2. See ADR-014 for the connector migration decision."
- See `batch-1-procrastinate-3-connector-migration.md` for the implemented migration.

## docs/architecture/04-platform/storage-topology.md
### "Why PostgreSQL for the task queue" paragraph (line ~60)
- Drop the sentence: "This justifies keeping the simpler 2.x URL-based configuration rather than adopting the psycopg3 connector required by 3.x."
- Replace with: "Procrastinate is pinned to 3.x with PsycopgConnector (psycopg3-based, async-capable) — the 2.x Psycopg2Connector (sync-only) cannot run the procrastinate CLI worker at any entrypoint. See ADR-014 for the connector migration decision. Redis/Celery remains the longer-term migration path if queue contention appears."
- Keep the two-system stack framing (PostgreSQL + MinIO) — the connector migration does not add infrastructure.
- See `batch-1-procrastinate-3-connector-migration.md` for the implemented migration.

## app/worker/README.md
### Architecture Notes section (lines 13-15)
- Update line 13: "Procrastinate 3.x is used with `PsycopgConnector` (psycopg3-based, async-capable); the 2.x `Psycopg2Connector` (sync-only) cannot run the procrastinate CLI worker. See ADR-014 for the connector migration decision."
- Update line 15: "Workers are started via `procrastinate --app=app.worker.app worker` as a separate process from the API server." (unchanged — the CLI command is the same in 3.x)
- Update the Contents table (line 10): change "`Psycopg2Connector`" to "`PsycopgConnector`"
- Add a note: "All task enqueue uses `await defer_async(...)` (async) per ADR-014. The sync `defer()` method is not available with PsycopgConnector in 3.x."
- See `batch-1-procrastinate-3-connector-migration.md` for the implemented migration.

## docs/adr/010-procrastinate-sync-defer-on-psycopg2-connector.md
- Status changed from `accepted` to `superseded` (already updated in the ADR frontmatter)
- `superseded-by: ADR-014` (already updated in the ADR frontmatter)
- No content changes needed — the ADR body documents the historical decision and its rationale; ADR-014 supersedes it.

## docs/adr/009-signal-cleaning-as-decoupled-async-task.md
### Cross-References section
- Add a precision note: "The `signal_clean` defer context changes from sync `defer()` to `await defer_async()` per ADR-014. The decoupling principle (separate task, own session, failure isolation) is unchanged; only the defer call shape changes. ADR-010's sync-only constraint on the `task_dispatcher` seam is superseded by ADR-014's async seam."
