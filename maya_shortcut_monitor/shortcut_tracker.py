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

try:
    from maya import OpenMaya as om1
except Exception:  # pragma: no cover
    om1 = None

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


class CommandOutputBuffer:
    def __init__(self):
        self._lines = []
        self._callback_id = None

    def start(self):
        if om1 is None or self._callback_id is not None:
            return
        try:
            self._callback_id = om1.MCommandMessage.addCommandOutputCallback(self._on_output)
        except Exception:
            self._callback_id = None

    def stop(self):
        if om1 is None or self._callback_id is None:
            return
        try:
            om1.MMessage.removeCallback(self._callback_id)
        except Exception:
            pass
        self._callback_id = None

    def mark(self) -> int:
        return len(self._lines)

    def _on_output(self, message, message_type, _client_data):
        text = clean_command_text(str(message))
        if not text:
            return
        self._lines.append(text)
        if len(self._lines) > 500:
            self._lines = self._lines[-500:]

    @staticmethod
    def _normalize_command_line(line: str) -> str:
        if line.endswith(';'):
            line = line[:-1]
        return clean_command_text(line)

    @staticmethod
    def _is_noise_command(line: str) -> bool:
        lowered = (line or '').strip().lower()
        if not lowered:
            return True
        if lowered.startswith('# result:'):
            return True
        if lowered.startswith('import '):
            return True
        if lowered.isdigit():
            return True
        noisy_prefixes = (
            'texturewindowupdatetextures',
            'texturewindowupdateuvsets',
            'uvtbupdatetextureitems',
            'dr_',
            'headsupdisplay',
            'refresh',
        )
        return lowered.startswith(noisy_prefixes)

    def newest_command_since(self, mark: int) -> str:
        candidates = []
        for line in self._lines[mark:]:
            normalized = self._normalize_command_line(line)
            if self._is_noise_command(normalized):
                continue
            candidates.append(normalized)

        if not candidates:
            return ''

        # Keep the first actionable command after the keypress: this best reflects
        # the command that the shortcut actually triggered (e.g. Ctrl+Z -> Undo).
        return candidates[0]


COMMAND_OUTPUT = CommandOutputBuffer()


READABLE_COMMAND_ALIASES = {
    "fitPanel -selectedNoChildren": "Frame Selected without children",
    "FrameSelectedWithoutChildren": "Frame Selected without children",
    "ConnectComponents": "Edit Mesh: Connect",
    "Connect_Flow": "Edit Mesh: Connect (Flow)",
    "performPolyExtrude 0": "Edit Mesh: Extrude",
    "SmartExtrude": "Edit Mesh: Smart Extrude",
    "PolyExtrude": "Edit Mesh: Extrude",
    "Undo": "Edit: Undo",
    "Redo": "Edit: Redo",
    "undo": "Edit: Undo",
    "redo": "Edit: Redo",
    "updateEditPivot": "Modeling Toolkit: Edit Pivot",
}

READABLE_PREFIX_ALIASES = {
    "fitPanel ": "Viewport: Frame Selected",
    "polyExtrude": "Edit Mesh: Extrude",
    "performPolyExtrude": "Edit Mesh: Extrude",
    "undo": "Edit: Undo",
    "redo": "Edit: Redo",
    "select -": "Select",
}


def _to_readable_command(action: str) -> str:
    normalized = clean_command_text(action or "")
    if not normalized:
        return "Unknown"

    if normalized in READABLE_COMMAND_ALIASES:
        return READABLE_COMMAND_ALIASES[normalized]

    for prefix, readable in READABLE_PREFIX_ALIASES.items():
        if normalized.startswith(prefix):
            return readable

    return normalized


@dataclass
class ShortcutEntry:
    shortcut: str
    command: str
    category: str
    context: str = ""
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
            command = item.get("command", "Unknown")
            context = item.get("context", "")
            entry = ShortcutEntry(
                shortcut=shortcut,
                command=command,
                category=item.get("category", "Autres"),
                context=context,
                hits=int(item.get("hits", 1)),
                last_seen=item.get("last_seen", ""),
            )
            self._entries[self._entry_key(shortcut, command, context)] = entry

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

    @staticmethod
    def _entry_key(shortcut: str, command: str, context: str = "") -> str:
        return "{0}|{1}|{2}".format(shortcut, command or "Unknown", context or "")

    def upsert(self, shortcut: str, command: str, category: str, context: str = "") -> None:
        now = datetime.now().isoformat(timespec="seconds")
        safe_command = command or "Unknown"
        safe_context = context or ""
        existing = self._entries.get(self._entry_key(shortcut, safe_command, safe_context))
        if existing:
            if safe_command and safe_command != "Unknown":
                existing.command = safe_command
            if category and category != "Autres":
                existing.category = category
            existing.context = safe_context
            existing.hits += 1
            existing.last_seen = now
            self.save()
            return

        self._entries[self._entry_key(shortcut, safe_command, safe_context)] = ShortcutEntry(
            shortcut=shortcut,
            command=safe_command,
            category=category or "Autres",
            context=safe_context,
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


def _is_generic_tool_action(action: str) -> bool:
    lowered = (action or "").lower()
    return lowered.startswith("tool:") and any(t in lowered for t in ["move", "rotate", "scale", "manip"])


def resolve_hotkey_command(shortcut: str, ctx_clients=None) -> str:
    query = shortcut_to_maya_query(shortcut)
    if query is None:
        return "Unknown"

    key, mods = query
    candidates = [key.lower(), key.upper()] if len(key) == 1 else [key]

    contextual_matches = []
    global_matches = []

    if ctx_clients:
        for ctx_client in ctx_clients:
            for candidate_key in candidates:
                try:
                    name_cmd = cmds.hotkey(k=candidate_key, q=True, name=True, ctxClient=ctx_client, **mods)
                    resolved = _resolve_name_command(name_cmd)
                    if resolved:
                        contextual_matches.append(resolved)

                    release_cmd = cmds.hotkey(
                        k=candidate_key,
                        q=True,
                        releaseName=True,
                        ctxClient=ctx_client,
                        **mods,
                    )
                    resolved_release = _resolve_name_command(release_cmd)
                    if resolved_release:
                        contextual_matches.append(resolved_release)
                except Exception:
                    continue

    for candidate_key in candidates:
        try:
            name_cmd = cmds.hotkey(k=candidate_key, q=True, name=True, **mods)
            resolved = _resolve_name_command(name_cmd)
            if resolved:
                global_matches.append(resolved)

            release_cmd = cmds.hotkey(k=candidate_key, q=True, releaseName=True, **mods)
            resolved_release = _resolve_name_command(release_cmd)
            if resolved_release:
                global_matches.append(resolved_release)
        except Exception:
            continue

    for action in contextual_matches:
        if not _is_generic_tool_action(action):
            return action
    if contextual_matches:
        return contextual_matches[0]

    for action in global_matches:
        if not _is_generic_tool_action(action):
            return action
    if global_matches:
        return global_matches[0]

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


def get_last_undo_label() -> str:
    try:
        return clean_command_text(cmds.undoInfo(q=True, undoName=True))
    except Exception:
        return ""


def resolve_active_context() -> str:
    panel = ""
    try:
        panel = cmds.getPanel(withFocus=True) or ""
    except Exception:
        panel = ""

    panel_type = ""
    if panel:
        try:
            panel_type = cmds.getPanel(typeOf=panel) or ""
        except Exception:
            panel_type = ""

    tool = resolve_current_tool()
    parts = [p for p in [panel_type, panel, tool] if p and p != "Unknown"]
    return " | ".join(parts)


def resolve_context_clients() -> list:
    clients = []
    try:
        panel = cmds.getPanel(withFocus=True)
        if panel:
            clients.append(panel)
            panel_type = cmds.getPanel(typeOf=panel)
            if panel_type:
                clients.append(panel_type)
    except Exception:
        pass
    try:
        ctx = cmds.currentCtx()
        if ctx:
            clients.append(ctx)
    except Exception:
        pass
    # unique order-preserving
    seen = set()
    unique = []
    for c in clients:
        if c and c not in seen:
            unique.append(c)
            seen.add(c)
    return unique


def _shortcut_prefers_tool_fallback(shortcut: str) -> bool:
    return shortcut in {"Q", "W", "E", "R", "T", "Y"}


def resolve_executed_action(
    shortcut: str,
    pre_last: str,
    pre_tool: str,
    pre_undo: str,
    pre_output_mark: int,
    mapped_action: str,
) -> str:
    post_undo = get_last_undo_label()
    if post_undo and post_undo != pre_undo:
        return post_undo

    post_last = get_last_executed_command()
    if post_last and post_last != pre_last:
        return post_last

    command_output = COMMAND_OUTPUT.newest_command_since(pre_output_mark)
    if command_output:
        return command_output

    if mapped_action and mapped_action != "Unknown":
        return mapped_action

    post_tool = resolve_current_tool()
    if post_tool != "Unknown" and post_tool != pre_tool:
        return post_tool

    if post_tool != "Unknown" and _shortcut_prefers_tool_fallback(shortcut):
        return post_tool

    return "Unknown"


def _label_for_tool_context(ctx_name: str) -> str:
    if not ctx_name:
        return ""

    known = {
        "$gmove": "Move Tool",
        "$grotate": "Rotate Tool",
        "$gscale": "Scale Tool",
    }
    key = ctx_name.strip().lower()
    if key in known:
        return known[key]

    try:
        title = cmds.contextInfo(ctx_name, q=True, title=True)
        if title:
            return title
    except Exception:
        pass

    lowered = ctx_name.lower()
    if "multicut" in lowered:
        return "Multi-Cut"

    return ""


def humanize_action_label(action: str, fallback_tool: str = "") -> str:
    normalized = clean_command_text(action or "")
    if not normalized:
        return "Unknown"

    if normalized.startswith("setToolTo "):
        ctx_name = normalized.split(None, 1)[1].strip()
        tool_label = _label_for_tool_context(ctx_name)
        if not tool_label and fallback_tool.startswith("Tool: "):
            tool_label = fallback_tool.replace("Tool: ", "", 1)
        if tool_label:
            return "Tool: {0}".format(tool_label)

    mm_map = {
        "buildTranslateMM": "Tool: Move Tool",
        "buildRotateMM": "Tool: Rotate Tool",
        "buildScaleMM": "Tool: Scale Tool",
    }
    if normalized in mm_map:
        return mm_map[normalized]

    return _to_readable_command(normalized)


class ShortcutMonitorWindow(QtWidgets.QDialog):
    def __init__(self, repository: ShortcutRepository, parent=None):
        super(ShortcutMonitorWindow, self).__init__(parent)
        self.repository = repository
        self.setObjectName(WINDOW_NAME)
        self.setWindowTitle("Maya Shortcut Monitor")
        self.resize(900, 460)

        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Shortcut", "Action/Commande", "Catégorie", "Contexte", "Hits", "Last Seen"])
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
            values = [entry.shortcut, entry.command, entry.category, entry.context, str(entry.hits), entry.last_seen]
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
            pre_undo = get_last_undo_label()
            pre_output_mark = COMMAND_OUTPUT.mark()
            ctx_clients = resolve_context_clients()
            QtCore.QTimer.singleShot(
                0,
                lambda s=shortcut, pl=pre_last, pt=pre_tool, pu=pre_undo, po=pre_output_mark, cc=ctx_clients: self._record_shortcut(
                    s,
                    pl,
                    pt,
                    pu,
                    po,
                    cc,
                ),
            )
        return False

    def _record_shortcut(self, shortcut: str, pre_last: str, pre_tool: str, pre_undo: str, pre_output_mark: int, ctx_clients):
        mapped_action = resolve_hotkey_command(shortcut, ctx_clients=ctx_clients)
        executed_action = resolve_executed_action(shortcut, pre_last, pre_tool, pre_undo, pre_output_mark, mapped_action)
        friendly_action = humanize_action_label(executed_action, fallback_tool=resolve_current_tool())
        if friendly_action == "Unknown":
            return
        category = categorize_command(friendly_action)
        self.repository.upsert(shortcut, friendly_action, category, resolve_active_context())
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
        COMMAND_OUTPUT.start()
        self.main_window.installEventFilter(self.filter)
        self.running = True
        self._create_or_show_window()
        print("[ShortcutTracker] Tracking started.")

    def stop(self) -> None:
        if not self.running:
            return
        self.main_window.removeEventFilter(self.filter)
        COMMAND_OUTPUT.stop()
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
