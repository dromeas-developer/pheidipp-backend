#!/usr/bin/env bash
set -euo pipefail

ensure_venv() {
  if [[ -z "${VIRTUAL_ENV:-}" ]]; then
    if [[ -f ".venv/bin/activate" ]]; then
      source .venv/bin/activate
    else
      echo "ERROR: .venv not found. Run scripts/bootstrap.sh first."
      exit 1
    fi
  fi
}

ensure_project_root() {
  if [[ ! -f "requirements.txt" && ! -f "pyproject.toml" ]]; then
    echo "ERROR: Run from project root."
    exit 1
  fi
}