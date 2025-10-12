#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
VENV_DIR="$ROOT_DIR/.venv-build-mac"
PYTHON=${PYTHON:-python3}

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON" -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

pip install -U pip
pip install -r "$ROOT_DIR/requirements.txt"
pip install pyinstaller==5.13.2

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

pyinstaller \
  --name Clinic \
  --windowed \
  --noconfirm \
  --clean \
  --add-data "$ROOT_DIR/app/ui/qml:app/ui/qml" \
  --add-data "$ROOT_DIR/app/ui/assets:app/ui/assets" \
  --add-data "$ROOT_DIR/app/ui/styles:app/ui/styles" \
  --add-data "$ROOT_DIR/files:files" \
  --add-data "$ROOT_DIR/data:data" \
  --hidden-import "PySide6.QtQml" \
  --hidden-import "PySide6.QtQuickControls2" \
  --hidden-import "PySide6.QtSvg" \
  --hidden-import "weasyprint" \
  "$ROOT_DIR/app/main.py"

mkdir -p "$DIST_DIR/Clinic.app/Contents/Resources"
cp -R dist/Clinic/* "$DIST_DIR/"

echo "Application macOS générée dans $DIST_DIR"
