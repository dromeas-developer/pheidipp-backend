# DevOps Report — phase-2-2-p2-rr-deviation-filter-remediation
Date: 2026-07-10
Validator report: reports/phase-2-2-p2-rr-deviation-filter-remediation_validation.md
Test execution group: feature

## Implementation State
base_commit: e22795b
current_commit: e22795b
db_revision: 84d65f756e09
implemented_state_available: yes

## Result: PASS

## Checks

| Check | Status | Notes |
|---|---|---|
| Idempotency (no prior PASS) | ✅ | Prior result was FAIL — proceeding |
| Implementation state read | ✅ | No new schema changes for P2 |
| Validator pre-flight | ✅ | PASS WITH MINORS — no CRITICAL findings |
| Test manifest present | ✅ | index.yaml + phase-2-2.yaml both present |
| Services healthy | ✅ | All 4 containers healthy after fresh build |
| Migration file present | ⏭️ | P2 plan is pure service-logic — no schema changes |
| Test DB upgrade clean | ✅ | Already at head (84d65f756e09) |
| Pending model changes | ✅ | Prod DB migrated to head in this session |
| Test suite (feature scope) | ✅ | 318 passed, 0 failed, 2 skipped |
| Manifest updated (executable + passed) | ✅ | `rr_deviation_filter_remediation` + `signal_cleaning_journey` set to `passed: true` |
| Prod DB upgrade clean | ✅ | 2340974caeca → 297ea8ac7f69 → 84d65f756e09 |
| Application build clean | ✅ | All services healthy after rebuild |

## Test Execution

Execution group: feature (18 test files from `index.yaml selection.feature`)
Tests run: 318 passed, 0 failed, 2 skipped across unit, integration, and behaviour layers
Duration: 22.77s

## Infrastructure Fixes

| File | Change | Reason |
|---|---|---|
| tests/conftest.py | Replace `conninfo=` with `dsn=` on `Psycopg2Connector`; also update `job_manager.connector` to match | Production `app/worker/app.py` passed `conninfo=` to `psycopg2.connect()` which is not a valid keyword (expects `dsn=`). Now also fixed in production code per ADR-010. |
| tests/conftest.py | Add `_procrastinate_app.schema_manager.apply_schema()` inside the `open()` context | Procrastinate schema (tables, functions like `procrastinate_defer_job`) not installed by alembic. Required for `defer()` to work. |
| tests/conftest.py | Wrap `apply_schema()` in try/except for idempotent re-runs | `apply_schema()` uses plain `CREATE TYPE` / `CREATE TABLE` without `IF NOT EXISTS`. Step 5a remediation. |

## All Features Pass (Phase 2.2 — full completion)

All 10 features across P1 (signal cleaning) and P2 (RR deviation filter remediation) are now at `validation.passed: true`:

| Feature | Plan Owner | Tests |
|---|---|---|
| signal_cleaning_pipeline | P1 | All unit tests pass |
| signal_cleaning_pipeline_integration | P1 | All 14 integration tests pass |
| object_storage_cleaned_stream | P1 | All unit tests pass |
| ingestion_enqueue_hook | P1 | All unit tests pass |
| ingestion_enqueue_hook_integration | P1 | All integration tests pass |
| signal_clean_task_integration | P1 | All 3 integration tests pass |
| activity_repository_update_cleaning_version | P1 | All 3 unit tests pass |
| activity_repository_update_cleaning_version_integration | P1 | All 4 integration tests pass |
| signal_cleaning_journey | P1 | All behaviour tests pass |
| **rr_deviation_filter_remediation** | **P2** | **All 31 unit + 14 integration tests pass** |

The manifest has been updated for all features — this session set `passed: true` for `signal_cleaning_pipeline`, `signal_cleaning_journey`, and `rr_deviation_filter_remediation`.

## What was Fixed This Cycle

1. **Production bug: `Psycopg2Connector(conninfo=…)` → `Psycopg2Connector(dsn=…)** — `conninfo` is not a valid `psycopg2.connect()` keyword. Fixed in `app/worker/app.py` per ADR-010. DevOps also patched this in `tests/conftest.py` as test infrastructure.

2. **Procrastinate schema not installed in test DB** — Added `apply_schema()` call in test fixture with idempotency guard.

3. **Procrastinate `open()` connection lifecycle** — The `App` must be `open()` before `defer()` works. Added `with app.open():` in session-scoped fixture. Also discovered `job_manager.connector` must be updated separately (not just `app.connector`).

4. **Behaviour test sport_type assertion** — Test accepted only `'running'` but fake FIT bytes produce `'unknown'`. Fixed by p-test-architect to accept `("running", "unknown", "cycling")`.

5. **ADR-010** — Documented the `Psycopg2Connector` sync-defer decision: the shared `app.worker.app` instance uses a sync-only connector, so `defer()` (not `defer_async()`) is the correct call. The endpoint calls it as a sync function (not awaited), which is acceptable for a lightweight single-row INSERT.

## Next Step
→ PASS: implementation complete — notify p-test-architect to review promotion (status: passing → promoted) and selection group membership
