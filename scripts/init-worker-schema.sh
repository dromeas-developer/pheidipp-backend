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
# (``procrastinate --app=app.worker.app.app worker`` opens the app, which
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

# The procrastinate console-script (``.venv/bin/procrastinate``) does not
# include the project root on ``sys.path`` at launch — its entrypoint sets
# ``sys.path[0]`` to ``.venv/bin/``.  Export ``PYTHONPATH`` so the CLI's
# ``importlib`` call resolves the top-level ``app`` package.  When this
# script runs inside the docker worker container, ``PYTHONPATH`` is
# already set to ``/app`` by ``docker-compose.yml`` and is preserved by
# the ``${PYTHONPATH:-...}`` defaulting below.
export PYTHONPATH="${PYTHONPATH:-$(pwd)}"

echo "Installing procrastinate schema..."

# In Procrastinate 3.x the schema subcommand takes ``--apply`` (a flag)
# that runs ``SchemaManager.apply_schema()`` against the DB configured
# by ``PROCRASTINATE_DATABASE_URL``.  The 2.x ``schema --install``
# subcommand does not exist in 3.x.
#
# CRITICAL — this command is NOT idempotent and is NOT safe to re-run
# against a DB with any pre-existing procrastinate objects.
# ``apply_schema`` emits plain ``CREATE TYPE`` / ``CREATE TABLE``
# (no ``IF NOT EXISTS`` guards), so it will fail with
# ``type "procrastinate_job_status" already exists`` (or similar) on any
# DB that has procrastinate objects from any prior install — including
# the 3.x schema itself, or a leftover 2.x schema.
#
# The drop-then-reinstall pattern used by ``tests/conftest.py:320-370``
# is the canonical approach for a fresh state.  For prod (``pheidipp``)
# the operator must drop legacy procrastinate objects MANUALLY before
# running this script, or accept that this script is for fresh DBs
# only.  See ``reports/phase-1-7-batch-1_devops.md`` for the operator
# runbook in the current promotion-gate scenario.
procrastinate --app=app.worker.app.app schema --apply

echo "Procrastinate schema installed successfully."
