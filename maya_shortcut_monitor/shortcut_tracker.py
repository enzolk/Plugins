# -*- coding: utf-8 -*-
"""Maya shortcut usage tracker.

Usage (Script Editor, Python):
    import maya_shortcut_monitor.shortcut_tracker as st
    tracker = st.start_tracker()  # Starts listening to key presses

    # ... work in Maya ...

    st.stop_tracker()             # Optional explicit stop

The tracker captures key events from Maya's main window, tries to resolve the
hotkey mapping to the associated command/tool, categorizes it, and persists
results in a JSON file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional, Tuple

import maya.cmds as cmds

try:
    from maya import OpenMayaUI as omui
except Exception as exc:  # pragma: no cover
    raise RuntimeError("This script must run inside Autodesk Maya.") from exc

QT_API = ""
try:
    from shiboken2 import wrapInstance
    from PySide2 import QtCore, QtWidgets

    QT_API = "PySide2"
except ImportError:
    try:
        from shiboken6 import wrapInstance
        from PySide6 import QtCore, QtWidgets

        QT_API = "PySide6"
    except ImportError as exc:
        raise RuntimeError(
            "Unable to import shiboken/PySide bindings. "
            "Expected shiboken2+PySide2 (Maya <= 2024) or shiboken6+PySide6 (Maya 2025+)."
        ) from exc


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(MODULE_DIR, "shortcuts_used.json")


@dataclass
class ShortcutEntry:
    shortcut: str
    command: str
    category: str
    hits: int = 1
    last_seen: str = ""


class ShortcutRepository:
    """Load/save shortcut usage with deduplication."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._entries: Dict[str, ShortcutEntry] = {}
        self.load()

    @property
    def entries(self) -> Dict[str, ShortcutEntry]:
        return self._entries

    def load(self) -> None:
        self._entries = {}
        if not os.path.exists(self.file_path):
            self.save()
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError):
            data = {"shortcuts": []}

        for item in data.get("shortcuts", []):
            shortcut = item.get("shortcut")
            if not shortcut:
                continue
            self._entries[shortcut] = ShortcutEntry(
                shortcut=shortcut,
                command=item.get("command", "Unknown"),
                category=item.get("category", "Autres"),
                hits=int(item.get("hits", 1)),
                last_seen=item.get("last_seen", ""),
            )

    def save(self) -> None:
        ordered = sorted(
            self._entries.values(),
            key=lambda e: (category_sort_key(e.category), e.shortcut.lower()),
        )
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "shortcuts": [asdict(entry) for entry in ordered],
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def upsert(self, shortcut: str, command: str, category: str) -> bool:
        now = datetime.now().isoformat(timespec="seconds")
        existing = self._entries.get(shortcut)
        if existing:
            changed = False
            if command and command != existing.command:
                existing.command = command
                changed = True
            if category and category != existing.category:
                existing.category = category
                changed = True
            existing.hits += 1
            existing.last_seen = now
            self.save()
            return changed

        self._entries[shortcut] = ShortcutEntry(
            shortcut=shortcut,
            command=command or "Unknown",
            category=category or "Autres",
            hits=1,
            last_seen=now,
        )
        self.save()
        return True


def category_sort_key(category: str) -> int:
    order = [
        "Sélection",
        "Transformation",
        "Modélisation",
        "UV",
        "Affichage",
        "Animation",
        "Autres",
    ]
    try:
        return order.index(category)
    except ValueError:
        return len(order)


def categorize_command(command_name: str) -> str:
    name = (command_name or "").lower()

    if any(token in name for token in ["select", "selection", "pick"]):
        return "Sélection"
    if any(token in name for token in ["move", "rotate", "scale", "transform"]):
        return "Transformation"
    if any(
        token in name
        for token in ["extrude", "bevel", "merge", "poly", "mesh", "model"]
    ):
        return "Modélisation"
    if "uv" in name or any(token in name for token in ["unwrap", "sew", "cut"]):
        return "UV"
    if any(token in name for token in ["view", "display", "isolate", "frame", "panel"]):
        return "Affichage"
    if any(
        token in name
        for token in ["key", "anim", "timeline", "playback", "graph", "dope"]
    ):
        return "Animation"
    return "Autres"


def maya_main_window() -> QtWidgets.QWidget:
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        raise RuntimeError("Unable to find Maya main window.")
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def normalize_key(key: int) -> str:
    key_enum = QtCore.Qt.Key(key)
    special = {
        QtCore.Qt.Key_Space: "Space",
        QtCore.Qt.Key_Return: "Enter",
        QtCore.Qt.Key_Enter: "Enter",
        QtCore.Qt.Key_Escape: "Esc",
        QtCore.Qt.Key_Backspace: "Backspace",
        QtCore.Qt.Key_Delete: "Delete",
        QtCore.Qt.Key_Tab: "Tab",
        QtCore.Qt.Key_Up: "Up",
        QtCore.Qt.Key_Down: "Down",
        QtCore.Qt.Key_Left: "Left",
        QtCore.Qt.Key_Right: "Right",
    }
    if key_enum in special:
        return special[key_enum]

    text = QtGuiKeyHelper.key_to_text(key_enum)
    if text:
        return text.upper()

    return str(int(key))


class QtGuiKeyHelper:
    @staticmethod
    def key_to_text(key: QtCore.Qt.Key) -> str:
        try:
            return QtGuiKeyHelper._qkeysequence_to_text(key)
        except Exception:
            return ""

    @staticmethod
    def _qkeysequence_to_text(key: QtCore.Qt.Key) -> str:
        if QT_API == "PySide6":
            from PySide6 import QtGui
        else:
            from PySide2 import QtGui

        text = QtGui.QKeySequence(int(key)).toString()
        return text


def event_to_shortcut(event: QtCore.QEvent) -> Optional[str]:
    if event.type() != QtCore.QEvent.KeyPress:
        return None

    key = event.key()
    if key in (
        QtCore.Qt.Key_Control,
        QtCore.Qt.Key_Shift,
        QtCore.Qt.Key_Alt,
        QtCore.Qt.Key_Meta,
    ):
        return None

    mods = event.modifiers()
    parts = []
    if mods & QtCore.Qt.ControlModifier:
        parts.append("Ctrl")
    if mods & QtCore.Qt.AltModifier:
        parts.append("Alt")
    if mods & QtCore.Qt.ShiftModifier:
        parts.append("Shift")

    parts.append(normalize_key(key))
    return "+".join(parts)


def shortcut_to_maya_query(shortcut: str) -> Optional[Tuple[str, Dict[str, bool]]]:
    parts = shortcut.split("+")
    if not parts:
        return None

    key = parts[-1]
    mods = {
        "altModifier": "Alt" in parts[:-1],
        "ctrlModifier": "Ctrl" in parts[:-1],
        "shiftModifier": "Shift" in parts[:-1],
    }

    key_map = {
        "Space": "Space",
        "Enter": "Return",
        "Esc": "Escape",
        "Up": "Up",
        "Down": "Down",
        "Left": "Left",
        "Right": "Right",
        "Tab": "Tab",
        "Delete": "Delete",
        "Backspace": "Backspace",
    }

    maya_key = key_map.get(key, key.lower())
    return maya_key, mods


def resolve_hotkey_command(shortcut: str) -> str:
    query = shortcut_to_maya_query(shortcut)
    if query is None:
        return "Unknown"

    key, mods = query
    try:
        command_name = cmds.hotkey(k=key, q=True, name=True, **mods)
        if command_name:
            return command_name

        runtime_name = cmds.hotkey(k=key, q=True, releaseName=True, **mods)
        if runtime_name:
            return runtime_name
    except Exception:
        pass

    return "Unknown"


class ShortcutEventFilter(QtCore.QObject):
    """Qt event filter that records Maya shortcuts."""

    def __init__(self, repository: ShortcutRepository):
        super(ShortcutEventFilter, self).__init__()
        self.repository = repository

    def eventFilter(self, obj, event):  # noqa: N802 - Qt naming requirement
        shortcut = event_to_shortcut(event)
        if shortcut:
            command = resolve_hotkey_command(shortcut)
            category = categorize_command(command)
            self.repository.upsert(shortcut, command, category)
        return False


_TRACKER = None


class MayaShortcutTracker:
    def __init__(self, save_file: str = SAVE_FILE):
        self.repository = ShortcutRepository(save_file)
        self.filter = ShortcutEventFilter(self.repository)
        self.main_window = maya_main_window()
        self.running = False

    def start(self) -> None:
        if self.running:
            return
        self.main_window.installEventFilter(self.filter)
        self.running = True
        print("[ShortcutTracker] Tracking started.")

    def stop(self) -> None:
        if not self.running:
            return
        self.main_window.removeEventFilter(self.filter)
        self.running = False
        print("[ShortcutTracker] Tracking stopped.")


def start_tracker() -> MayaShortcutTracker:
    global _TRACKER
    if _TRACKER is None:
        _TRACKER = MayaShortcutTracker()
    _TRACKER.start()
    return _TRACKER


def stop_tracker() -> None:
    global _TRACKER
    if _TRACKER is not None:
        _TRACKER.stop()
