# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import maya.cmds as cmds

try:
    from PySide6 import QtWidgets
except Exception:
    from PySide2 import QtWidgets

from .core import MayaShortcutLogger, ShortcutStore
from .ui import ShortcutSummaryDialog

_MANAGER = None


class _Manager:
    def __init__(self):
        self.store = ShortcutStore(_data_file_path())
        self.listener = None
        self.dialog = None
        self.store.add_listener(self._on_store_updated)

    def start(self):
        app = QtWidgets.QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication unavailable")

        existing = app.property("_maya_shortcut_logger_instance")
        if existing is not None:
            try:
                app.removeEventFilter(existing)
            except Exception:
                pass

        self.listener = MayaShortcutLogger(self.store)
        app.installEventFilter(self.listener)
        app.setProperty("_maya_shortcut_logger_instance", self.listener)
        print("MayaShortcutLogger listening enabled.")

    def stop(self):
        app = QtWidgets.QApplication.instance()
        if self.listener and app:
            try:
                app.removeEventFilter(self.listener)
            except Exception:
                pass
        if self.listener:
            self.listener.uninstall_callback()
            self.listener.deleteLater()
        self.listener = None
        if app:
            app.setProperty("_maya_shortcut_logger_instance", None)
        print("MayaShortcutLogger listening disabled.")

    def open_ui(self):
        if self.dialog is None:
            self.dialog = ShortcutSummaryDialog(self)
        self.dialog.refresh()
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _on_store_updated(self):
        if self.dialog is None:
            return
        try:
            self.dialog.refresh()
        except Exception:
            pass


def _data_file_path():
    # Persistent file in Maya prefs so it survives restarts.
    try:
        pref_dir = Path(cmds.internalVar(userPrefDir=True))
    except Exception:
        pref_dir = Path(__file__).resolve().parent / "data"
    return pref_dir / "maya_shortcut_logger_table.json"


def _manager():
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = _Manager()
    return _MANAGER


def auto_start():
    _manager().start()


def open_shortcut_logger_ui():
    _manager().open_ui()


def disable_shortcut_listener():
    _manager().stop()


def enable_shortcut_listener():
    _manager().start()
