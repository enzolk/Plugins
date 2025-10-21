from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from .app_context import AppContext
from .platform_paths import get_app_paths


def setup_logging(paths) -> None:
    log_path = paths.default_log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def main() -> int:
    paths = get_app_paths()
    setup_logging(paths)
    logging.info("Démarrage de ClinicPortable")

    app = QApplication(sys.argv)
    app.setApplicationName("ClinicPortable")
    app.setOrganizationName("ClinicPortable")
    app.setQuitOnLastWindowClosed(True)

    icon_path = Path(__file__).resolve().parent / "ui" / "assets" / "icons" / "app_icon.svg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    context = AppContext()
    context.bootstrap_database()

    engine = QQmlApplicationEngine()

    ui_root = Path(__file__).resolve().parent / "ui" / "qml"
    engine.addImportPath(str(ui_root))
    engine.rootContext().setContextProperty("appContext", context)
    engine.load(QUrl.fromLocalFile(str(ui_root / "MainWindow.qml")))

    if not engine.rootObjects():
        logging.error("Impossible de charger l'interface QML")
        return 1

    logging.info("Interface initialisée")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
