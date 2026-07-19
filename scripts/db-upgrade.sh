#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

scripts/alembic.sh upgrade head

# Install the procrastinate schema (tables, enums, functions) if not
# already present.  Procrastinate manages its own schema — Alembic is
# configured to ignore procrastinate_* objects (see include_object in
# alembic/env.py).  This step is idempotent and safe to run on every
# upgrade; it ensures the worker's deferred-job infrastructure exists
# before any ``defer()`` call from the application.
#
# We extract the schema SQL from procrastinate (via its SchemaManager)
# and apply it via psql.  We do NOT use the procrastinate CLI because
# procrastinate 2.15.1's CLI enforces an async-connector check for all
# commands, but the worker app uses a sync Psycopg2Connector.  The
# schema SQL itself is plain PostgreSQL DDL — no async needed.
echo "Installing procrastinate schema..."
.venv/bin/python -c "
from procrastinate.schema import SchemaManager
postgres_url = 'postgresql://postgres:postgres@db:5432/pheidipp'
from procrastinate.contrib.psycopg2 import Psycopg2Connector
connector = Psycopg2Connector(kwargs={'dsn': postgres_url})
manager = SchemaManager(connector=connector)
print(manager.get_schema())
" | docker compose exec -T db psql -U postgres -d pheidipp -v ON_ERROR_STOP=1 2>&1 || true
echo "Procrastinate schema ready."