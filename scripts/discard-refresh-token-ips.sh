#!/usr/bin/env bash
# Run once-daily env-friendly invocation:
#     crontab: 0 3 * * * /path/to/backend/scripts/discard-refresh-token-ips.sh
#
# Truncates / nullifies ip_address on athlete_refresh_tokens older than
# the 7-day retention window per ADR-005.

set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

scripts/python.sh -m app.tasks.discard_refresh_token_ips_cli "$@"
