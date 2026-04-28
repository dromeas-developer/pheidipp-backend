#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${1:-}" ]]; then
  echo "Usage: scripts/db-revision.sh 'message'"
  exit 1
fi

scripts/alembic.sh revision --autogenerate -m "$1"