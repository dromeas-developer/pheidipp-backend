#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Auto-generate an Alembic revision against the TEST database.
#
# This is the test-DB mirror of ``scripts/db-revision.sh``.  It overrides
# ``DATABASE_URL`` with ``TEST_DATABASE_URL`` so that ``--autogenerate``
# compares ORM models against ``test_pheidipp`` instead of the production
# database.
#
# Primary use cases in the DevOps workflow:
#
#   1. Pending-changes check (Step 4) — run against the test DB that was
#      just migrated, rather than against production.
#   2. Generating new revisions during development without touching the
#      production schema at all.
#
# Usage:
#   bash scripts/db-revision-test.sh "message"
#   bash scripts/db-revision-test.sh "check"    # pending-changes check
#
# Requires ``TEST_DATABASE_URL`` to be set (from ``.env.test``).
# ---------------------------------------------------------------------------
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

if [[ -z "${1:-}" ]]; then
  echo "Usage: scripts/db-revision-test.sh 'message'"
  exit 1
fi

# Load environment variables if .env.test exists
if [ -f .env.test ]; then
  export $(grep -v '^#' .env.test | xargs)
fi

# Ensure test database URL exists
if [ -z "${TEST_DATABASE_URL:-}" ]; then
  echo "ERROR: TEST_DATABASE_URL is not set"
  exit 1
fi

# Override DATABASE_URL for Alembic
export DATABASE_URL="$TEST_DATABASE_URL"

# Generate the revision using the alembic wrapper
scripts/alembic.sh revision --autogenerate -m "$1"
