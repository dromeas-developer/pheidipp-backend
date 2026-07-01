#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

# Phase-1.7: Replaced ARQ with procrastinate (PostgreSQL-backed task queue).
# TODO(coder): Update the app path below after implementing the procrastinate worker in Step 5.
#   Expected: procrastinate --app=app.worker.app worker
procrastinate --app=app.worker.app worker