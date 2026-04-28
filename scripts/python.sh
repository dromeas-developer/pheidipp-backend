#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

python "$@"