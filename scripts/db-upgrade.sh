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
echo "Installing procrastinate schema..."
procrastinate --app=app.worker.app schema --install
echo "Procrastinate schema ready."