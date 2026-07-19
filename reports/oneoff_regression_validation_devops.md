# DevOps Report — oneoff_regression_validation
Date: 2026-07-19
Validator report: N/A (ad-hoc validation — no plan-id)
Test execution group: regression

## Implementation State
base_commit: f7593c4
current_commit: ab20925
db_revision: 21f955c743cb

## Result: PASS

Tests: 2635 passed / 0 failed / 2 skipped
Root causes identified: 0

## Checks

| Check | Status | Notes |
|---|---|---|
| Implementation state read | ✅ | |
| Services healthy | ✅ | api, db, minio, litellm all healthy |
| Migration file present (coder-generated) | N/A | No new migrations in this session |
| Migration drift reviewed | N/A | No new migration file to review |
| TimescaleDB augmentation | N/A | No new hypertable migration needed |
| Test DB upgrade clean | ✅ | Already at head (21f955c743cb) |
| No pending model changes (test DB) | ✅ | Check file had empty upgrade body |
| Test suite | ✅ | 2635 passed, 0 failed, 2 skipped (full regression) |
| Prod DB upgrade clean | ✅ | Alembic upgrade + procrastinate schema OK |
| Application build clean | ✅ | All 4 services healthy after build |

## Test Execution

Execution group: regression (full suite)
Tests run: `bash scripts/run-tests.sh` (no path args — full `tests/` directory)

## Infrastructure Fixes

| File | Change | Reason |
|---|---|---|
| `scripts/db-upgrade.sh` | Fixed procrastinate `--app` path from `app.worker.app` to `app.worker.app.app` and replaced CLI call with Python schema extraction + psql pipe | Procrastinate 2.15.1 CLI enforces async connector check for all commands, but the worker uses a sync `Psycopg2Connector`. The schema SQL is plain DDL — no async needed. |

## Root Cause Analysis

No root causes — all tests pass, build clean, no pending schema drift.

## Full Failure Detail

No failures.

## Next Step
→ PASS: Full pipeline validation complete. The twin recalibration user journey,
  schema tests, and LiteLLM smoke test all pass. The production schema is
  migrated to the same revision as the test DB. Ready for promotion.
