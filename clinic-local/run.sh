#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

if [ ! -x launcher.py ]; then
  chmod +x launcher.py
fi

PYTHON_BIN="${PYTHON:-python3}"

exec "$PYTHON_BIN" launcher.py --cli --no-browser
