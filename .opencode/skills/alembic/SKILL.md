---
name: alembic
description: Use when creating, reviewing, or applying Alembic database migrations for pheidipp
---

# Alembic Migration Workflow — Pheidipp

## Engine Rule
Migrations use sync engine (psycopg2). App uses async engine (asyncpg). Never mix. The project uses `get_postgres_url(sync=True)` from `app/core/config.py` which:
- Swaps asyncpg → psycopg2 automatically
- Handles db/localhost hostname based on Docker detection
- Must be used in `alembic/env.py` — never hardcode the URL

## Required env.py Pattern
```python
# alembic/env.py — must have both of these
from app.core.config import get_postgres_url
from app.db.base import Base
import app.models  # noqa: F401 — registers all models with Base.metadata

target_metadata = Base.metadata

def run_migrations_online() -> None:
    connectable = create_engine(
        get_postgres_url(sync=True),
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

## Command Execution (STRICT)
NEVER run `alembic` directly.
ALWAYS use scripts:
- `bash scripts/db-revision.sh "<descriptive_name>"` — generate migration
- `bash scripts/db-upgrade.sh` — apply migrations
If a required script is missing → STOP and report.

## Workflow
1. Update SQLAlchemy ORM model in `app/models/`
2. Update `app/models/__init__.py` to export the new model
3. `bash scripts/db-revision.sh "<descriptive_name>"`
4. Verify the generated file — if empty, models are not imported (see below)
5. `bash scripts/db-upgrade.sh`
6. `make context` — updates injected schema in dynamic.md

## Empty Migration — Common Failure
If the generated migration has no operations:
- `app/models/__init__.py` is not importing all models
- Fix: add `from app.models.your_model import YourModel` to `__init__.py`
- Then delete the empty migration and regenerate

## TimescaleDB + pgvector Order
When creating hypertables or vector columns, use `op.execute()` in this sequence:
1. `CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;`
2. `CREATE EXTENSION IF NOT EXISTS vector;`
3. Table creation via `op.create_table(...)`
4. `SELECT create_hypertable('table_name', 'ts_column', if_not_exists => TRUE);`

## pgvector
- Always `vector(384)` for embeddings
- Use HNSW index — not IVFFlat — for local performance

## Safety
- Run `alembic current` before generating to verify head is correct
- Migration names must be descriptive: `add_activity_embeddings_table` not `update`
- `downgrade()` must safely reverse all changes
- Never drop database extensions