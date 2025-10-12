#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -x "run.sh" ]; then
  chmod +x run.sh
fi

echo "🚀 Lancement d'OsteoDrainage..."

open_browser_when_ready() {
  # On attend que le serveur Uvicorn soit joignable avant d'ouvrir le navigateur.
  /usr/bin/env python3 <<'PY'
import subprocess
import time
import urllib.error
import urllib.request

URL = "http://localhost:8000"
deadline = time.time() + 180
while time.time() < deadline:
    try:
        with urllib.request.urlopen(URL, timeout=1):
            break
    except (urllib.error.URLError, TimeoutError):
        time.sleep(1)
else:
    raise SystemExit(0)

subprocess.run(["open", URL], check=False)
PY
}

# On lance l'ouverture automatique dans un job de fond pour ne pas bloquer l'interface.
open_browser_when_ready &

cleanup() {
  exit_code=$?
  if [ $exit_code -ne 0 ]; then
    echo "❌ Le lancement a échoué (code $exit_code). Vérifiez les messages ci-dessus."
    read "?Appuyez sur Entrée pour fermer cette fenêtre."
  fi
}
trap cleanup EXIT

./run.sh
