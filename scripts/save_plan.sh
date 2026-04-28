#!/usr/bin/env bash
set -e

FILENAME=$1

if [ -z "$FILENAME" ]; then
  echo "Error: missing filename"
  exit 1
fi

mkdir -p plans

cat > "plans/${FILENAME}.md"

echo "Plan saved to plans/${FILENAME}.md"