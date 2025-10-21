#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_NAME="ClinicPortable"

mkdir -p "$DIST_DIR"
export PYTHONPATH="$ROOT_DIR"

ARGS=(
    "$ROOT_DIR/app/main.py"
    --name "$APP_NAME"
    --windowed
    --noconfirm
    --add-data "$ROOT_DIR/app/ui/qml:ui/qml"
    --add-data "$ROOT_DIR/app/ui/assets:ui/assets"
    --add-data "$ROOT_DIR/app/ui/styles:ui/styles"
    --add-data "$ROOT_DIR/files/pdf_templates:pdf_templates"
    --add-data "$ROOT_DIR/README.md:."
    --add-data "$ROOT_DIR/LICENSE:."
    --target-arch universal2
)

pyinstaller "${ARGS[@]}"

if [ -d "$DIST_DIR/$APP_NAME.app" ]; then
    pushd "$DIST_DIR" >/dev/null
    zip -r "$APP_NAME-macos.zip" "$APP_NAME.app"
    popd >/dev/null
fi
