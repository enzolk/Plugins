# -*- coding: utf-8 -*-
"""Maya shortcut usage tracker with live UI and context-aware action resolution."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
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
WINDOW_NAME = "MayaShortcutMonitorWindow"


@dataclass
class ShortcutEntry:
    shortcut: str
    command: str
    category: str
    hits: int = 1
    last_seen: str = ""


class ShortcutRepository:
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

    def sorted_entries(self):
        return sorted(
            self._entries.values(),
            key=lambda e: (category_sort_key(e.category), e.shortcut.lower()),
        )

    def save(self) -> None:
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "shortcuts": [asdict(entry) for entry in self.sorted_entries()],
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def upsert(self, shortcut: str, command: str, category: str) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        existing = self._entries.get(shortcut)
        if existing:
            if command and command != "Unknown":
                existing.command = command
            if category and category != "Autres":
                existing.category = category
            existing.hits += 1
            existing.last_seen = now
            self.save()
            return

        self._entries[shortcut] = ShortcutEntry(
            shortcut=shortcut,
            command=command or "Unknown",
            category=category or "Autres",
            hits=1,
            last_seen=now,
        )
        self.save()


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
    return order.index(category) if category in order else len(order)


def categorize_command(command_name: str) -> str:
    name = (command_name or "").lower()
    if any(t in name for t in ["select", "selection", "pick"]):
        return "Sélection"
    if any(t in name for t in ["move", "rotate", "scale", "transform", "manip"]):
        return "Transformation"
    if any(
        t in name
        for t in ["poly", "mesh", "extrude", "bevel", "merge", "multicut", "connect", "model"]
    ):
        return "Modélisation"
    if any(t in name for t in ["uv", "unwrap", "sew", "cutuv", "unfold"]):
        return "UV"
    if any(t in name for t in ["view", "display", "isolate", "frame", "panel", "camera", "viewport"]):
        return "Affichage"
    if any(t in name for t in ["anim", "key", "timeline", "graph", "dope", "playback"]):
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
        return QtGui.QKeySequence(int(key)).toString()


def event_to_shortcut(event: QtCore.QEvent) -> Optional[str]:
    if event.type() != QtCore.QEvent.KeyPress:
        return None

    key = event.key()
    if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
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
    return key_map.get(key, key.lower()), mods


def clean_command_text(text: str) -> str:
    if not text:
        return ""
    compact = " ".join(text.replace("\n", " ").replace("\r", " ").split())
    return compact[:180]


def _query_runtime_label(runtime_name: str) -> str:
    if not runtime_name:
        return ""
    try:
        ann = cmds.runTimeCommand(runtime_name, q=True, annotation=True)
        if ann:
            return ann
    except Exception:
        pass
    try:
        cmd_str = cmds.runTimeCommand(runtime_name, q=True, command=True)
        if cmd_str:
            return clean_command_text(cmd_str)
    except Exception:
        pass
    return runtime_name


def _resolve_name_command(name_cmd: str) -> str:
    if not name_cmd:
        return ""

    # If nameCommand points to a runTimeCommand, annotation gives a readable UI action label.
    try:
        runtime_name = cmds.nameCommand(name_cmd, q=True, command=True)
        runtime_label = _query_runtime_label(runtime_name)
        if runtime_label:
            return runtime_label
    except Exception:
        pass

    # Fallbacks for other mapping types.
    try:
        assign_cmd = cmds.assignCommand(name_cmd, q=True, command=True)
        if assign_cmd:
            return clean_command_text(assign_cmd)
    except Exception:
        pass

    try:
        ann = cmds.nameCommand(name_cmd, q=True, ann=True)
        if ann:
            return ann
    except Exception:
        pass

    return name_cmd


def resolve_hotkey_command(shortcut: str) -> str:
    query = shortcut_to_maya_query(shortcut)
    if query is None:
        return "Unknown"

    key, mods = query
    candidates = []
    if len(key) == 1:
        candidates = [key.lower(), key.upper()]
    else:
        candidates = [key]

    for candidate_key in candidates:
        try:
            name_cmd = cmds.hotkey(k=candidate_key, q=True, name=True, **mods)
            resolved = _resolve_name_command(name_cmd)
            if resolved:
                return resolved

            release_cmd = cmds.hotkey(k=candidate_key, q=True, releaseName=True, **mods)
            resolved_release = _resolve_name_command(release_cmd)
            if resolved_release:
                return resolved_release
        except Exception:
            continue

    return "Unknown"


def resolve_current_tool() -> str:
    try:
        ctx = cmds.currentCtx()
        title = cmds.contextInfo(ctx, q=True, title=True) if ctx else ""
        if title:
            return "Tool: {0}".format(title)
        if ctx:
            return "Tool: {0}".format(ctx)
    except Exception:
        pass
    return "Unknown"


def get_last_executed_command() -> str:
    try:
        last_cmd = cmds.repeatLast(q=True, ac=True)
        return clean_command_text(last_cmd)
    except Exception:
        return ""


def resolve_executed_action(pre_last: str, pre_tool: str, mapped_action: str) -> str:
    post_last = get_last_executed_command()
    if post_last and post_last != pre_last:
        return post_last

    if mapped_action and mapped_action != "Unknown":
        return mapped_action

    post_tool = resolve_current_tool()
    if post_tool != "Unknown" and post_tool != pre_tool:
        return post_tool

    if post_tool != "Unknown":
        return post_tool

    return "Unknown"


class ShortcutMonitorWindow(QtWidgets.QDialog):
    def __init__(self, repository: ShortcutRepository, parent=None):
        super(ShortcutMonitorWindow, self).__init__(parent)
        self.repository = repository
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("Maya Shortcut Monitor")
        self.resize(900, 460)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Shortcut", "Action/Commande", "Catégorie", "Hits", "Last Seen"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        refresh_btn = QtWidgets.QPushButton("Rafraîchir")
        refresh_btn.clicked.connect(self.refresh)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(refresh_btn)

        self.refresh()

    def refresh(self):
        entries = self.repository.sorted_entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [entry.shortcut, entry.command, entry.category, str(entry.hits), entry.last_seen]
            for col, val in enumerate(values):
                self.table.setItem(row, col, QtWidgets.QTableWidgetItem(val))
        self.table.resizeColumnsToContents()


class ShortcutEventFilter(QtCore.QObject):
    def __init__(self, repository: ShortcutRepository, on_update=None):
        super(ShortcutEventFilter, self).__init__()
        self.repository = repository
        self.on_update = on_update

    def eventFilter(self, obj, event):  # noqa: N802
        shortcut = event_to_shortcut(event)
        if shortcut:
            pre_last = get_last_executed_command()
            pre_tool = resolve_current_tool()
            QtCore.QTimer.singleShot(
                0,
                lambda s=shortcut, pl=pre_last, pt=pre_tool: self._record_shortcut(
                    s,
                    pl,
                    pt,
                ),
            )
        return False

    def _record_shortcut(self, shortcut: str, pre_last: str, pre_tool: str):
        mapped_action = resolve_hotkey_command(shortcut)
        executed_action = resolve_executed_action(pre_last, pre_tool, mapped_action)
        category = categorize_command(executed_action)
        self.repository.upsert(shortcut, executed_action, category)
        if self.on_update:
            self.on_update()


_TRACKER = None


class MayaShortcutTracker:
    def __init__(self, save_file: str = SAVE_FILE):
        self.repository = ShortcutRepository(save_file)
        self.main_window = maya_main_window()
        self.window = None
        self.filter = ShortcutEventFilter(self.repository, on_update=self._refresh_window)
        self.running = False

    def _create_or_show_window(self):
        if self.window is None:
            self.window = ShortcutMonitorWindow(self.repository, parent=self.main_window)
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _refresh_window(self):
        if self.window is not None:
            self.window.refresh()

    def start(self) -> None:
        if self.running:
            self._create_or_show_window()
            return
        self.main_window.installEventFilter(self.filter)
        self.running = True
        self._create_or_show_window()
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
