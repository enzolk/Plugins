#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON=${PYTHON:-python3}

if [ ! -d "$VENV_DIR" ]; then
  echo "[dev_run] Création de l'environnement virtuel..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install -U pip
pip install -r "$ROOT_DIR/requirements.txt"

export PYTHONPATH="$ROOT_DIR"
export QT_QUICK_CONTROLS_CONF="$ROOT_DIR/app/ui/styles/qtquickcontrols2.conf"

python -m app.main "$@"
