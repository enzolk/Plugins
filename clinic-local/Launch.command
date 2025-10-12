#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -x launcher.py ]; then
  chmod +x launcher.py
fi

cleanup() {
  status=$?
  if [ $status -ne 0 ]; then
    echo "\n❌ Une erreur est survenue. Les détails figurent ci-dessus."
    read "?Appuyez sur Entrée pour fermer cette fenêtre."
  fi
}
trap cleanup EXIT

/usr/bin/env python3 launcher.py
