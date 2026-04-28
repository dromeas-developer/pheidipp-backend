#!/usr/bin/env bash
set -euo pipefail

echo "⚠️  This will RESET the database. Continue? (y/N)"
read -r confirm

if [[ "$confirm" != "y" ]]; then
  exit 0
fi

docker compose down -v
docker compose up -d

sleep 3

scripts/db-upgrade.sh

echo "✅ Database reset complete"