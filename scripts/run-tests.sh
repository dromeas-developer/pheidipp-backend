#!/usr/bin/env bash
set -euo pipefail

# Load environment variables if .env.test exists
if [ -f .env.test ]; then
  export $(grep -v '^#' .env.test | xargs)
fi

# Ensure test database URL exists
if [ -z "${TEST_DATABASE_URL:-}" ]; then
  echo "ERROR: TEST_DATABASE_URL is not set"
  exit 1
fi

TEST_PATH="${1:-tests/}"

# Override DATABASE_URL for testing
export DATABASE_URL="$TEST_DATABASE_URL"

docker compose exec -e DATABASE_URL="$DATABASE_URL" api bash -c "pytest ${TEST_PATH} -v"
