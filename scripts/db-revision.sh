#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

if [[ -z "${1:-}" ]]; then
  echo "Usage: scripts/db-revision.sh 'message'"
  exit 1
fi

scripts/alembic.sh revision --autogenerate -m "$1"