#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Install the procrastinate schema (tables, enums, functions) into the
# production database.
#
# Procrastinate manages its own schema (procrastinate_jobs,
# procrastinate_events, procrastinate_periodic_defers, and supporting
# functions like procrastinate_defer_job).  This schema is NOT part of
# any Alembic migration — Alembic is configured (via the include_object
# filter in alembic/env.py) to ignore procrastinate_* objects entirely.
#
# In production the schema is auto-installed when the worker starts
# (``procrastinate --app=app.worker.app worker`` opens the app, which
# calls ``schema_manager.apply_schema()``).  This script exists for:
#
#   1. Explicit bootstrap in deployment pipelines — run after Alembic
#      migrations, before the worker starts, to avoid any timing
#      dependency on the worker's first-start schema install.
#   2. Test / CI environments where the worker is not running but
#      the schema must be present so ``defer()`` calls succeed.
#   3. Fresh development environments — run once after ``docker-build``
#      and ``db-upgrade``.
#
# Usage:
#   bash scripts/init-worker-schema.sh
#
# The script reads ``PROCRASTINATE_DATABASE_URL`` from the environment
# (already set in ``.env`` and ``.env.test``).
# ---------------------------------------------------------------------------
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

echo "Installing procrastinate schema..."

# The --schema --install flags create the procrastinate internal tables,
# enums, and functions if they do not already exist.  The command is
# idempotent — it uses CREATE IF NOT EXISTS internally.
procrastinate --app=app.worker.app schema --install

echo "Procrastinate schema installed successfully."
