---
name: infrastructure-reference
description: >
  Load this when an agent needs the Pheidipp platform's service map,
  database architecture, command inventory, check-file rule, or
  TimescaleDB augmentation procedures. Consumed by s-alembic (primary
  — owns the migration lifecycle), s-devops-ops (docker lifecycle),
  s-infra-config-editor (config file authoring — needs the service
  map to know what services should exist), and p-devops (operational
  reference). Coder agents no longer load this skill — migration
  generation is delegated to s-alembic.
---

# Infrastructure Reference

Shared reference for the Pheidipp platform's runtime infrastructure,
database architecture, and script inventory. Agents load this skill for
"what commands exist and how they work" and retain only their own
decision logic for when to use them.

---

## Service Map

| Service | Role | Port |
|---|---|---|
| `api` | FastAPI application — tests run inside this container | 8000 |
| `worker` | procrastinate job processor (Postgres-native async queue, no Redis) — same image as api | — |
| `db` | TimescaleDB (pg16) — hosts both `pheidipp` and `test_pheidipp` | 5432 |
| `minio` | FIT file object storage | 9000/9001 |
| `litellm-proxy` | LiteLLM proxy — sole gateway for all LLM access; all agents and services route through it, never to providers directly | 4000 |

The `api` container must be healthy before tests can run. The `db` container
must be healthy before any migration can run. Both depend on healthchecks
defined in docker-compose — `docker-build.sh` waits for them.

When diagnosing failures, use `bash scripts/docker-logs.sh` to inspect
all container logs. To inspect a specific service: the script may accept
a service name argument — check if it does before assuming it logs all services.

---

## Database Architecture

The project runs **two databases inside the same Docker stack**:

| Database | Variable | Used by |
|---|---|---|
| `pheidipp` | `DATABASE_URL` | Production application |
| `test_pheidipp` | `TEST_DATABASE_URL` | Test suite and test migrations |

The scripts handle the distinction automatically — you never set `DATABASE_URL`
manually. The separation matters for test DB migration vs prod DB migration:
they are independent operations against independent DBs.

**Alembic uses a sync engine (psycopg2), the app uses async (asyncpg).** This
is handled transparently by `get_postgres_url(sync=True)` in `app/core/config.py`
and is already wired in `alembic/env.py`. Never touch this wiring.

**Two `db-revision` scripts exist, targeting different databases.**
`db-revision.sh` targets the production DB (`DATABASE_URL` / `pheidipp`).
`db-revision-test.sh` targets the test DB (`TEST_DATABASE_URL` /
`test_pheidipp`) — it loads `.env.test` and overrides `DATABASE_URL` the
same way `db-upgrade-test.sh` does. Both accept `"check"` as the revision
message to run in verification-only mode.

**The pending-changes check uses `db-revision-test.sh`, not
`db-revision.sh`.** At that point in the DevOps flow, only `test_pheidipp`
has been migrated — `pheidipp` is not touched until later. Running the
check against prod would always show a non-empty diff (prod is still on
the old revision), which is a false positive, not a real drift finding.
Checking against `test_pheidipp` — which was just upgraded to head — is
the correct target: it verifies the coder's migration file actually
captures every ORM model change, not just that `alembic upgrade head` ran
without error.

**If the test DB is in a broken state** (failed mid-migration, schema
corrupted, migration history diverged from prod) there is no
`db-reset-test.sh` script currently. Reset manually:
```bash
docker compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS test_pheidipp;"
docker compose exec db psql -U postgres -c "CREATE DATABASE test_pheidipp;"
bash scripts/db-upgrade-test.sh
```
Record this in the report if performed. Flag to the human that a
`scripts/db-reset-test.sh` would prevent this step in future.

---

## Command Inventory

### DevOps scripts

```
bash scripts/docker-build.sh              # build and start all services
bash scripts/docker-down.sh               # stop all services
bash scripts/docker-logs.sh               # inspect container logs on failure
bash scripts/db-upgrade-test.sh           # migrate test_pheidipp (reads .env.test)
bash scripts/db-upgrade.sh                # migrate pheidipp (reads .env / DATABASE_URL)
bash scripts/db-revision.sh "<message>"   # autogenerate revision / check against prod DB
bash scripts/db-revision-test.sh "<message>"  # autogenerate revision / check against test_pheidipp
bash scripts/run-tests.sh [paths...]      # run pytest inside api container against test_pheidipp
```

**How `run-tests.sh` works:**
- Loads `.env.test` to get `TEST_DATABASE_URL`
- Overrides `DATABASE_URL` with `TEST_DATABASE_URL` for the pytest run
- Runs `docker compose exec -e DATABASE_URL="$DATABASE_URL" api bash -c "pytest <paths> -v"`
- Pass test paths as space-separated arguments: `bash scripts/run-tests.sh tests/unit/ tests/integration/test_auth.py`
- Paths may be bare files, class-qualified (`tests/unit/test_foo.py::TestBar`),
  or function-qualified (`tests/unit/test_foo.py::TestBar::test_baz`) pytest
  node IDs — the script passes them through to pytest unchanged
- No arguments = runs the full `tests/` directory

**How `db-upgrade-test.sh` works:**
- Loads `.env.test` to get `TEST_DATABASE_URL`
- Overrides `DATABASE_URL` with `TEST_DATABASE_URL`
- Runs `alembic upgrade head` against `test_pheidipp`

If a required script is missing → STOP and report which script is absent.
Do not attempt to run `alembic`, `pytest`, or `python` directly.

### Test Architect scripts

```
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```

Always use `scripts/pytest.sh`, never bare `pytest` — pytest is installed
in `.venv`, which a bare `pytest` invocation will not have activated, and
the check will fail with "pytest not installed" even though it is.

**Class-based test discovery:** The test manifest stores an optional `class`
field per function entry for class-based tests. When present, construct the
pytest selector as `file.py::ClassName::function_name`. When absent, use
`file.py::function_name` (module-level). If a function's `class` field is
missing but the test is actually class-based (pytest reports "not found"),
run `--collect-only` as a fallback to discover the correct class-qualified
path:

```bash
# Fallback: discover class-qualified paths when manifest class field is missing
bash scripts/pytest.sh --collect-only -q tests/api/test_coach_endpoints_async.py
# Output: tests/api/test_coach_endpoints_async.py::TestManualFirstMessageReturns201IfAsyncHasNotRun::test_201_with_new_message
```

### Diagnostics Fixer scripts

```
bash scripts/typecheck.sh                 # basedpyright — workspace-wide or scoped via path argument
bash scripts/lint.sh                      # ruff check . (lint + formatting rules)
bash scripts/format.sh                    # only if a fix introduces formatting drift
```

---

## Check File Rule (NON-NEGOTIABLE)

`db-revision.sh "check"` and `db-revision-test.sh "check"` each generate a
file named `<hash>_check.py` in `alembic/versions/`. This is a
schema-verification artefact — NOT an official revision. It must NEVER be
applied to any database, regardless of which script produced it.

Before EVERY `db-upgrade.sh` or `db-upgrade-test.sh` call:
1. Use `find_files` to search `alembic/versions/` for files matching `*_check.py`
2. If any found → DELETE them via bash `rm`, record in report, then continue
3. Never apply a migration whose filename contains `_check`

---

## TimescaleDB Augmentation

If a plan flags a hypertable requirement and the coder has not already
added the TimescaleDB blocks, DevOps adds them:

In `upgrade()`, in this exact sequence:
1. Extensions — only if no prior hypertable migration exists:
   - `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")`
   - `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")`
2. After `op.create_table(...)`:
   - `op.execute("SELECT create_hypertable('table_name', 'time_column', if_not_exists => TRUE);")`

In `downgrade()`, before `op.drop_table(...)`:
- `op.execute("SELECT drop_hypertable('table_name', if_exists => TRUE, cascade => TRUE);")`
- Never drop extensions in downgrade
