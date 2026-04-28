#!/usr/bin/env bash
set -euo pipefail
source scripts/common.sh

ensure_project_root
ensure_venv

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000