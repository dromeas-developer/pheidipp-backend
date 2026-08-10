#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

scripts/alembic.sh upgrade head

# Install the procrastinate schema (tables, enums, functions) if not
# already present.  Procrastinate manages its own schema — Alembic is
# configured to ignore procrastinate_* objects (see include_object in
# alembic/env.py).
#
# We extract the schema SQL from procrastinate via ``SchemaManager`` and
# pipe it to ``docker compose exec -T db psql``.  ``SchemaManager.get_schema``
# is a pure static method — the connector placeholder below is not
# connected to, so the python step works without a reachable DB.  The
# connection happens inside the docker network via ``docker compose exec``.
#
# IMPORTANT — this step is NOT idempotent.  ``get_schema`` emits plain
# ``CREATE TYPE`` / ``CREATE TABLE`` (no ``IF NOT EXISTS`` guards), so it
# will fail with ``type "procrastinate_job_status" already exists`` (or
# similar) on any DB that has procrastinate objects from a prior install —
# including leftover 2.x schemas, or a 3.x install that was applied by an
# earlier run of this script.  If you see that error, drop the legacy
# procrastinate objects first (see
# ``reports/phase-1-7-batch-1_devops.md`` for the operator runbook and
# the historical incident where the 2.x → 3.x schema gap was hidden
# behind the ``|| true`` that used to be on this line).
#
# No ``|| true`` here — a failed schema-install must surface so the
# operator can intervene, not be silently swallowed.
#
# Idempotency guard — version-aware, NOT a naive "if exists skip".
# ``SchemaManager.get_schema()`` emits plain ``CREATE TYPE`` / ``CREATE TABLE``
# with no ``IF NOT EXISTS`` guards, so a re-run on a correct 3.x schema
# would fail loudly (the very loudness that exposed the 2.x → 3.x gap).
# We skip only when both 3.x-specific markers are present:
#   * ``procrastinate_prune_stalled_workers_v1`` function (3.x-only)
#   * ``procrastinate_workers`` table (3.x-only, durable across 3.x minors)
# The dual marker guards against either one being renamed in a future 3.x
# minor, and explicitly does NOT accept a stale 2.x schema (which lacks
# both) — genuine drift still fails loudly below.
if docker compose exec -T db psql -U postgres -d pheidipp -tAc \
  "SELECT 1 FROM pg_proc WHERE proname='procrastinate_prune_stalled_workers_v1' \
   AND to_regclass('procrastinate_workers') IS NOT NULL" \
  | grep -q 1; then
  echo "Procrastinate 3.x schema already present — skipping install."
else
  echo "Installing procrastinate schema..."
  .venv/bin/python -c "
from procrastinate.schema import SchemaManager
postgres_url = 'postgresql://postgres:postgres@db:5432/pheidipp'
from procrastinate.contrib.psycopg2 import Psycopg2Connector
connector = Psycopg2Connector(kwargs={'dsn': postgres_url})
manager = SchemaManager(connector=connector)
print(manager.get_schema())
" | docker compose exec -T db psql -U postgres -d pheidipp -v ON_ERROR_STOP=1
  echo "Procrastinate schema ready."
fi