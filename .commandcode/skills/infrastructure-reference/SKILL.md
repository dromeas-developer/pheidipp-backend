---
name: infrastructure-reference
description: >
  Load this when an agent needs the Pheidipp platform's service map,
  database architecture, command inventory, check-file rule, or
  TimescaleDB augmentation procedures. Consumed by p-devops (primary)
  and p-coder.
---

# Infrastructure Reference

Script inventory, check-file rule, and TimescaleDB augmentation procedures.
Stack truth (service map, database architecture, async rules, LLM proxy) is
in AGENTS.md — this skill covers operational commands only, not platform
description.

---

## Command Inventory

### DevOps scripts

```
bash scripts/docker-build.sh              # build and start all services
bash scripts/docker-down.sh               # stop all services
bash scripts/docker-logs.sh               # inspect container logs on failure
bash scripts/db-upgrade-test.sh           # migrate test_pheidipp
bash scripts/db-upgrade.sh                # migrate pheidipp
bash scripts/db-revision.sh "<message>"   # autogenerate revision / check against prod DB
bash scripts/db-revision-test.sh "<message>"  # autogenerate revision / check against test_pheidipp
bash scripts/run-tests.sh [paths...]      # run pytest inside api container
```

### Test Architect scripts

```
bash scripts/pytest.sh --collect-only <path> [<path> ...]
```

### Diagnostics Fixer scripts

```
bash scripts/typecheck.sh                 # basedpyright
bash scripts/lint.sh                      # ruff check .
bash scripts/format.sh                    # only if a fix introduces formatting drift
```

---

## Check File Rule (NON-NEGOTIABLE)

Before EVERY `db-upgrade.sh` or `db-upgrade-test.sh` call:
1. Use `find_files` to search `alembic/versions/` for files matching `*_check.py`
2. If any found → DELETE them, record in report, then continue
3. Never apply a migration whose filename contains `_check`

---

## TimescaleDB Augmentation

If a plan flags a hypertable requirement, DevOps adds to the migration:

In `upgrade()`, in sequence:
1. Extensions: `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;`
2. After `op.create_table(...)`: `SELECT create_hypertable('table_name', 'time_column', if_not_exists => TRUE);`

In `downgrade()`, before `op.drop_table(...)`:
- `SELECT drop_hypertable('table_name', if_exists => TRUE, cascade => TRUE);`
- Never drop extensions in downgrade
