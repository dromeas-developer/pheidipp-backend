#!/usr/bin/env bash
set -euo pipefail

if [ -f .env.test ]; then
  export $(grep -v '^#' .env.test | xargs)
fi

TEST_PATH="tests/integration/test_discard_refresh_token_ips.py"

if [ -z "${TEST_DATABASE_URL:-}" ]; then
  echo "ERROR: TEST_DATABASE_URL is not set"
  exit 1
fi

export DATABASE_URL="$TEST_DATABASE_URL"

docker compose exec -e DATABASE_URL="$DATABASE_URL" api bash -c "pytest ${TEST_PATH} -v"
