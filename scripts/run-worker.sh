#!/usr/bin/env bash
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

# Phase-1.7: Replaced ARQ with procrastinate (PostgreSQL-backed task queue).
# The app attribute lives in module ``app.worker.app`` (see app/worker/app.py),
# so the CLI import path is ``app.worker.app.app``.
procrastinate --app=app.worker.app.app worker