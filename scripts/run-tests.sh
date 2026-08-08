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

JUNIT_FLAG=""
if [ -n "${JUNIT_XML_PATH:-}" ]; then
  JUNIT_FLAG="--junit-xml=$JUNIT_XML_PATH"
fi

# Override DATABASE_URL for testing
export DATABASE_URL="$TEST_DATABASE_URL"

set +e
docker compose exec -e DATABASE_URL="$DATABASE_URL" api bash -c "pytest ${TEST_PATHS} -v $JUNIT_FLAG"
EXIT_CODE=$?
set -e

# Extract Juice from JUnit XML (node IDs + reasons, regardless of tty).
# Emits a tagged section with START/END sentinels so the subagent can
# extract it unambiguously. The section is always emitted when
# JUNIT_XML_PATH is set — empty when all tests pass.
if [ -n "${JUNIT_XML_PATH:-}" ]; then
  docker compose exec api python3 - "$JUNIT_XML_PATH" << 'PYEOF'
import xml.etree.ElementTree as ET, sys
lines = []
for tc in ET.parse(sys.argv[1]).iter("testcase"):
    for child in tc:
        if child.tag in ("failure", "error"):
            parts = tc.get("classname", "").rsplit(".", 1)
            if len(parts) > 1 and parts[1][0].isupper():
                node = f"{parts[0].replace('.', '/')}.py::{parts[1]}::{tc.get('name', '')}"
            else:
                node = f"{tc.get('classname', '').replace('.', '/')}.py::{tc.get('name', '')}"
            status = "FAILED" if child.tag == "failure" else "ERROR"
            message = (child.get("message") or "")[:1000]
            lines.append(f"{status} {node} - {message}")
print("--- JUICE START ---")
for line in lines:
    print(line)
print("--- JUICE END ---")
PYEOF
fi

exit $EXIT_CODE