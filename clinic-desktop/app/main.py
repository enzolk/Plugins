from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .app_context import app_ctx


def main() -> int:
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()
    qml_path = Path(__file__).parent / "ui" / "qml" / "MainWindow.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
