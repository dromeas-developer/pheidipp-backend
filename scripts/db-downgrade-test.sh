#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

echo "Running database migrations on TEST database..."

# Load environment variables if .env.test exists
if [ -f .env.test ]; then
  export $(grep -v '^#' .env.test | xargs)
fi

# Ensure test database URL exists
if [ -z "${TEST_DATABASE_URL:-}" ]; then
  echo "ERROR: TEST_DATABASE_URL is not set"
  exit 1
fi

echo "Using TEST_DATABASE_URL:"
echo "$TEST_DATABASE_URL"

# Use venv like production script
ensure_venv
ensure_project_root

# Override DATABASE_URL for Alembic
export DATABASE_URL="$TEST_DATABASE_URL"

# Run migrations using the alembic wrapper
scripts/alembic.sh downgrade -1

echo "Test database migrations completed successfully."