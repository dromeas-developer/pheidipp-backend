#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip

if [[ -f "requirements.txt" ]]; then
  pip install -r requirements.txt
elif [[ -f "pyproject.toml" ]]; then
  pip install .
fi

echo "✅ Bootstrap complete"