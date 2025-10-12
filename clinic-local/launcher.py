#!/usr/bin/env python3
"""Script de lancement convivial pour macOS."""
from __future__ import annotations

import argparse
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
from queue import Empty, Queue
from threading import Thread
from typing import Iterable, Protocol

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


class Logger(Protocol):
    def step(self, message: str) -> None: ...

    def info(self, message: str) -> None: ...

    def warn(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...


class ConsoleLogger:
    def step(self, message: str) -> None:
        border = "=" * len(message)
        print(f"\n{border}\n{message}\n{border}")

    def info(self, message: str) -> None:
        print(message)

    def warn(self, message: str) -> None:
        print(f"⚠️  {message}")

    def error(self, message: str) -> None:
        print(f"❌ {message}")


class TkLogger:
    def __init__(self, queue: Queue[tuple[str, str | int | None]]) -> None:
        self.queue = queue

    def _push(self, level: str, payload: str | int | None) -> None:
        self.queue.put((level, payload))

    def step(self, message: str) -> None:
        self._push("step", message)

    def info(self, message: str) -> None:
        self._push("info", message)

    def warn(self, message: str) -> None:
        self._push("warn", message)

    def error(self, message: str) -> None:
        self._push("error", message)


def ensure_venv(logger: Logger) -> Path:
    if not VENV_DIR.exists():
        logger.step("Création de l'environnement Python local…")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    else:
        logger.info("Environnement virtuel détecté – étape ignorée.")
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
    try:
        subprocess.check_call(list(command), cwd=PROJECT_ROOT, env=env)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - contrôlé via tests d'intégration
        raise LauncherError(
            "Une commande requise a échoué. Merci de vérifier les messages ci-dessus."
        ) from exc


def install_requirements(python_exe: Path, logger: Logger) -> None:
    required_hash = fingerprint_requirements()
    if read_hash() == required_hash:
        logger.info("Dépendances déjà installées – étape ignorée.")
        return

    logger.step("Installation/validation des dépendances…")
    run_cmd([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"])
    run_cmd([str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    write_hash(required_hash)


def ensure_env_file(logger: Logger) -> None:
    if ENV_FILE.exists() or not ENV_TEMPLATE.exists():
        logger.info("Fichier .env déjà présent – étape ignorée.")
        return
    logger.step("Création du fichier .env local…")
    shutil.copy2(ENV_TEMPLATE, ENV_FILE)


def prepare_directories(logger: Logger) -> None:
    for directory in DATA_DIRS:
        directory.mkdir(parents=True, exist_ok=True)
    logger.info("Dossiers de données vérifiés.")


def run_migrations(python_exe: Path, *, env: dict[str, str], logger: Logger) -> None:
    logger.step("Application des migrations de base de données…")
    run_cmd([str(python_exe), "-m", "alembic", "-c", str(ALEMBIC_INI), "upgrade", "head"], env=env)


def seed_database(python_exe: Path, *, env: dict[str, str], logger: Logger) -> None:
    logger.step("Chargement des données de démonstration…")
    run_cmd([str(python_exe), "-m", "app.cli", "seed", "--if-empty"], env=env)


def wait_for_server(url: str, logger: Logger, timeout: float = 180.0) -> bool:
    logger.step("Démarrage du serveur web…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    return False


def open_browser(url: str, logger: Logger) -> None:
    logger.step("Ouverture de l'interface dans votre navigateur par défaut…")
    webbrowser.open(url)


def launch_server(python_exe: Path, *, env: dict[str, str], logger: Logger) -> subprocess.Popen[bytes]:
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
    logger.step("Lancement d'OsteoDrainage – les journaux du serveur s'afficheront ci-dessous.")
    return subprocess.Popen(command, cwd=PROJECT_ROOT, env=env)


def execute_pipeline(
    *,
    open_ui: bool,
    logger: Logger,
    register_signals: bool,
    wait_for_exit: bool,
) -> int | subprocess.Popen[bytes]:
    os.chdir(PROJECT_ROOT)
    python_exe = ensure_venv(logger)

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))

    prepare_directories(logger)
    ensure_env_file(logger)
    install_requirements(python_exe, logger)
    run_migrations(python_exe, env=env, logger=logger)
    seed_database(python_exe, env=env, logger=logger)

    server = launch_server(python_exe, env=env, logger=logger)

    def shutdown_server(signum: int, frame) -> None:  # type: ignore[override]
        if server.poll() is None:
            server.terminate()
        raise SystemExit(0)

    if register_signals:
        signal.signal(signal.SIGINT, shutdown_server)
        signal.signal(signal.SIGTERM, shutdown_server)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, shutdown_server)

    if open_ui and wait_for_server(CHECK_URL, logger):
        open_browser(CHECK_URL, logger)
    elif open_ui:
        logger.warn(
            "Impossible de joindre automatiquement l'interface. Vous pouvez l'ouvrir manuellement sur "
            f"{CHECK_URL}."
        )

    if wait_for_exit:
        try:
            exit_code = server.wait()
        except KeyboardInterrupt:
            shutdown_server(signal.SIGINT, None)  # type: ignore[arg-type]
            exit_code = 0

        if exit_code == 0:
            logger.step("Arrêt du serveur. À bientôt !")
        else:
            logger.step(f"Le serveur s'est arrêté avec le code {exit_code}.")
        return exit_code

    return server


def run_cli(open_ui: bool) -> int:
    logger = ConsoleLogger()
    try:
        result = execute_pipeline(
            open_ui=open_ui,
            logger=logger,
            register_signals=True,
            wait_for_exit=True,
        )
        return int(result) if isinstance(result, int) else 0
    except LauncherError as exc:
        logger.error(str(exc))
        return 1


def run_gui(open_ui: bool) -> int:
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError as exc:  # pragma: no cover - dépend du système
        raise LauncherError(
            "L'interface graphique Tkinter est indisponible sur ce système."
        ) from exc

    queue: Queue[tuple[str, str | int | None]] = Queue()
    logger = TkLogger(queue)

    controller: dict[str, object] = {"server": None, "exit_code": 0, "running": False}

    root = tk.Tk()
    root.title("OsteoDrainage – Lancement")
    root.geometry("640x360")
    root.resizable(True, True)

    header = tk.Label(root, text="Démarrage de l'application locale", font=("Helvetica", 16, "bold"))
    header.pack(pady=12)

    log_box = tk.Text(root, wrap="word", state="disabled", height=12)
    log_box.pack(fill="both", expand=True, padx=16, pady=8)

    button_frame = tk.Frame(root)
    button_frame.pack(fill="x", padx=16, pady=8)

    status_var = tk.StringVar()
    status_label = tk.Label(button_frame, textvariable=status_var)
    status_label.pack(side="left")

    def append_log(message: str) -> None:
        log_box.configure(state="normal")
        log_box.insert("end", message + "\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    def on_close() -> None:
        server = controller.get("server")
        if isinstance(server, subprocess.Popen) and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        root.destroy()

    def worker() -> None:
        controller["running"] = True
        try:
            server = execute_pipeline(
                open_ui=open_ui,
                logger=logger,
                register_signals=False,
                wait_for_exit=False,
            )
            controller["server"] = server
            queue.put(("info", "Serveur démarré. Laissez cette fenêtre ouverte pour l'arrêter proprement."))
            queue.put(("server-started", None))
            exit_code = server.wait()
            controller["exit_code"] = int(exit_code)
            queue.put(("server-stopped", exit_code))
        except LauncherError as exc:
            queue.put(("error", str(exc)))
            controller["exit_code"] = 1
        except Exception as exc:  # pragma: no cover - sécurité utilisateur
            queue.put(("error", f"Une erreur inattendue est survenue : {exc}"))
            controller["exit_code"] = 1
        finally:
            queue.put(("finished", None))

    def on_start() -> None:
        if controller.get("running"):
            return
        start_button.config(state="disabled")
        stop_button.config(state="normal")
        status_var.set("Initialisation en cours…")
        Thread(target=worker, daemon=True).start()

    def on_stop() -> None:
        server = controller.get("server")
        if isinstance(server, subprocess.Popen) and server.poll() is None:
            server.terminate()
            status_var.set("Arrêt en cours…")
        else:
            status_var.set("Aucun serveur à arrêter.")

    start_button = tk.Button(button_frame, text="Lancer", width=12, command=on_start)
    start_button.pack(side="right", padx=(0, 8))

    stop_button = tk.Button(button_frame, text="Arrêter", width=12, state="disabled", command=on_stop)
    stop_button.pack(side="right", padx=(0, 8))

    def process_queue() -> None:
        try:
            while True:
                level, payload = queue.get_nowait()
                if level == "step" and isinstance(payload, str):
                    border = "=" * len(payload)
                    append_log(f"\n{border}\n{payload}\n{border}")
                elif level in {"info", "warn", "error"} and isinstance(payload, str):
                    prefix = {"info": "ℹ️ ", "warn": "⚠️ ", "error": "❌ "}[level]
                    append_log(prefix + payload)
                    if level == "error":
                        messagebox.showerror("Erreur", payload)
                        status_var.set("Erreur – voir les détails ci-dessus.")
                        stop_button.config(state="disabled")
                elif level == "server-started":
                    status_var.set("Serveur en cours d'exécution.")
                elif level == "server-stopped" and isinstance(payload, (int, type(None))):
                    code = payload or 0
                    if code == 0:
                        append_log("✅ Serveur arrêté proprement.")
                    else:
                        append_log(f"❌ Le serveur s'est arrêté avec le code {code}.")
                    status_var.set("Serveur arrêté.")
                    stop_button.config(state="disabled")
                elif level == "finished":
                    controller["running"] = False
                    start_button.config(state="normal")
        except Empty:
            pass
        root.after(150, process_queue)

    root.protocol("WM_DELETE_WINDOW", on_close)
    process_queue()
    root.mainloop()
    return int(controller.get("exit_code", 0))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lanceur tout-en-un pour OsteoDrainage")
    parser.add_argument("--no-browser", action="store_true", help="Ne pas ouvrir automatiquement le navigateur")
    parser.add_argument("--cli", action="store_true", help="Forcer le mode console")
    parser.add_argument("--gui", action="store_true", help="Forcer l'interface graphique")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    open_ui = not args.no_browser

    if args.cli and args.gui:
        raise LauncherError("Merci de choisir soit --cli soit --gui, mais pas les deux.")

    if args.cli or (not args.gui and sys.stdout.isatty()):
        return run_cli(open_ui=open_ui)

    try:
        return run_gui(open_ui=open_ui)
    except LauncherError:
        return run_cli(open_ui=open_ui)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LauncherError as exc:  # pragma: no cover - sécurité utilisateur
        print(f"❌ {exc}")
        sys.exit(1)
