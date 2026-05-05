#!/usr/bin/env bash
set -euo pipefail

TEST_PATH="${1:-tests/}"

docker compose exec api bash -c "pytest ${TEST_PATH} -v"