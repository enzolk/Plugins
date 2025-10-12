#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$PROJECT_ROOT/.venv"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$PROJECT_ROOT/requirements.txt"
mkdir -p "$PROJECT_ROOT/data" "$PROJECT_ROOT/files" "$PROJECT_ROOT/logs"
export PYTHONPATH="$PROJECT_ROOT"
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
fi
alembic -c "$PROJECT_ROOT/alembic.ini" upgrade head
python -m app.cli seed --if-empty
HOST=${UVICORN_HOST:-127.0.0.1}
PORT=${UVICORN_PORT:-8000}
uvicorn app.main:app --host "$HOST" --port "$PORT"
