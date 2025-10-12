#!/usr/bin/env python3
"""Script de lancement convivial pour macOS."""
from __future__ import annotations

import hashlib
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
ENV_FILE = PROJECT_ROOT / ".env"
ENV_TEMPLATE = PROJECT_ROOT / ".env.example"
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"
DATA_DIRS = [PROJECT_ROOT / "data", PROJECT_ROOT / "files", PROJECT_ROOT / "logs"]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
CHECK_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
HASH_MARKER = VENV_DIR / ".requirements-hash"


class LauncherError(Exception):
    """Erreur contrôlée par le lanceur."""


def print_step(message: str) -> None:
    border = "=" * len(message)
    print(f"\n{border}\n{message}\n{border}")


def ensure_venv() -> Path:
    if not VENV_DIR.exists():
        print_step("Création de l'environnement Python local…")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    bin_dir = VENV_DIR / ("Scripts" if sys.platform.startswith("win") else "bin")
    return bin_dir / ("python.exe" if sys.platform.startswith("win") else "python3")


def fingerprint_requirements() -> str:
    hasher = hashlib.sha256()
    with REQUIREMENTS.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_hash() -> str | None:
    if not HASH_MARKER.exists():
        return None
    return HASH_MARKER.read_text().strip()


def write_hash(value: str) -> None:
    HASH_MARKER.write_text(value)


def run_cmd(command: Iterable[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.check_call(list(command), cwd=PROJECT_ROOT, env=env)


def install_requirements(python_exe: Path) -> None:
    required_hash = fingerprint_requirements()
    if read_hash() == required_hash:
        print("Dépendances déjà installées – étape ignorée.")
        return

    print_step("Installation/validation des dépendances…")
    run_cmd([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"])
    run_cmd([str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    write_hash(required_hash)


def ensure_env_file() -> None:
    if ENV_FILE.exists() or not ENV_TEMPLATE.exists():
        return
    shutil.copy2(ENV_TEMPLATE, ENV_FILE)


def prepare_directories() -> None:
    for directory in DATA_DIRS:
        directory.mkdir(parents=True, exist_ok=True)


def run_migrations(python_exe: Path, *, env: dict[str, str]) -> None:
    print_step("Application des migrations de base de données…")
    run_cmd([str(python_exe), "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"], env=env)


def seed_database(python_exe: Path, *, env: dict[str, str]) -> None:
    print_step("Chargement des données de démonstration…")
    run_cmd([str(python_exe), "-m", "app.cli", "seed", "--if-empty"], env=env)


def wait_for_server(url: str, timeout: float = 180.0) -> bool:
    print_step("Démarrage du serveur web…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    return False


def open_browser(url: str) -> None:
    print_step("Ouverture de l'interface dans votre navigateur par défaut…")
    webbrowser.open(url)


def launch_server(python_exe: Path, *, env: dict[str, str]) -> subprocess.Popen[bytes]:
    command = [
        str(python_exe),
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        DEFAULT_HOST,
        "--port",
        str(DEFAULT_PORT),
    ]
    print_step("Lancement d'OsteoDrainage – les journaux du serveur s'afficheront ci-dessous.")
    return subprocess.Popen(command, cwd=PROJECT_ROOT, env=env)


def main(open_ui: bool = True) -> int:
    os.chdir(PROJECT_ROOT)
    python_exe = ensure_venv()

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))

    prepare_directories()
    ensure_env_file()
    install_requirements(python_exe)
    run_migrations(python_exe, env=env)
    seed_database(python_exe, env=env)

    server = launch_server(python_exe, env=env)

    def shutdown_server(signum: int, frame) -> None:  # type: ignore[override]
        if server.poll() is None:
            server.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGINT, shutdown_server)
    signal.signal(signal.SIGTERM, shutdown_server)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, shutdown_server)

    if open_ui and wait_for_server(CHECK_URL):
        open_browser(CHECK_URL)
    elif open_ui:
        print("⚠️ Impossible de joindre automatiquement l'interface. Vous pouvez l'ouvrir manuellement sur", CHECK_URL)

    try:
        exit_code = server.wait()
    except KeyboardInterrupt:
        shutdown_server(signal.SIGINT, None)  # type: ignore[arg-type]
        exit_code = 0

    if exit_code == 0:
        print_step("Arrêt du serveur. À bientôt !")
    else:
        print_step(f"Le serveur s'est arrêté avec le code {exit_code}.")
    return exit_code


if __name__ == "__main__":
    try:
        sys.exit(main(open_ui="--no-browser" not in sys.argv))
    except LauncherError as exc:  # pragma: no cover - sécurité utilisateur
        print(f"❌ {exc}")
        sys.exit(1)
