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

# Build test paths array - use all arguments or default to tests/
if [ $# -gt 0 ]; then
  TEST_PATHS="$*"
else
  TEST_PATHS="tests/"
fi

# Override DATABASE_URL for testing
export DATABASE_URL="$TEST_DATABASE_URL"

docker compose exec -e DATABASE_URL="$DATABASE_URL" api bash -c "pytest ${TEST_PATHS} -v"
