# -*- coding: utf-8 -*-
"""Maya Shortcut Logger

Capture every unique pressed shortcut and log all possible Maya actions attached to it.
Compatible with Maya 2022+ (PySide2/PySide6).
"""

from __future__ import annotations

import traceback

import maya.cmds as cmds

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    import shiboken6 as shiboken
except Exception:
    from PySide2 import QtCore, QtGui, QtWidgets
    import shiboken2 as shiboken

try:
    from maya import OpenMayaUI as omui
except Exception:
    omui = None


_SPECIAL_KEYS = {
    QtCore.Qt.Key_Space: "Space",
    QtCore.Qt.Key_Tab: "Tab",
    QtCore.Qt.Key_Backspace: "Backspace",
    QtCore.Qt.Key_Return: "Enter",
    QtCore.Qt.Key_Enter: "Enter",
    QtCore.Qt.Key_Escape: "Esc",
    QtCore.Qt.Key_Delete: "Delete",
    QtCore.Qt.Key_Insert: "Insert",
    QtCore.Qt.Key_Home: "Home",
    QtCore.Qt.Key_End: "End",
    QtCore.Qt.Key_PageUp: "PageUp",
    QtCore.Qt.Key_PageDown: "PageDown",
    QtCore.Qt.Key_Left: "Left",
    QtCore.Qt.Key_Right: "Right",
    QtCore.Qt.Key_Up: "Up",
    QtCore.Qt.Key_Down: "Down",
}

for _f_idx in range(1, 25):
    _SPECIAL_KEYS[getattr(QtCore.Qt, f"Key_F{_f_idx}")] = f"F{_f_idx}"


class MayaShortcutLogger(QtCore.QObject):
    """Qt event filter that logs unique shortcuts and all possible Maya actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logged_shortcuts = set()

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API naming)
        if event.type() != QtCore.QEvent.KeyPress:
            return False

        shortcut_data = self._build_shortcut_from_event(event)
        if not shortcut_data:
            return False

        shortcut_str, key_token, mods = shortcut_data
        if shortcut_str in self.logged_shortcuts:
            return False

        self.logged_shortcuts.add(shortcut_str)

        try:
            possible_actions = self._collect_possible_actions(key_token, mods)
            self._print_log_block(shortcut_str, possible_actions)
        except Exception:
            print(f'Shortcut : "{shortcut_str}"')
            print("\nPossible actions :")
            print("- Error while collecting actions")
            traceback.print_exc()

        return False

    def _build_shortcut_from_event(self, event):
        key = event.key()

        if key in (
            QtCore.Qt.Key_Control,
            QtCore.Qt.Key_Shift,
            QtCore.Qt.Key_Alt,
            QtCore.Qt.Key_Meta,
        ):
            return None

        key_name = self._key_name_from_keycode(key, event)
        if not key_name:
            return None

        modifiers = event.modifiers()
        mod_state = {
            "ctrl": bool(modifiers & QtCore.Qt.ControlModifier),
            "alt": bool(modifiers & QtCore.Qt.AltModifier),
            "shift": bool(modifiers & QtCore.Qt.ShiftModifier),
        }

        pieces = []
        if mod_state["ctrl"]:
            pieces.append("Ctrl")
        if mod_state["alt"]:
            pieces.append("Alt")
        if mod_state["shift"]:
            pieces.append("Shift")
        pieces.append(key_name)

        shortcut_string = "+".join(pieces)
        return shortcut_string, key_name, mod_state

    def _key_name_from_keycode(self, key, event):
        if key in _SPECIAL_KEYS:
            return _SPECIAL_KEYS[key]

        if QtCore.Qt.Key_A <= key <= QtCore.Qt.Key_Z:
            return chr(key)

        if QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9:
            return chr(key)

        # Never use event.text() when a modifier is active.
        has_modifier = bool(
            event.modifiers()
            & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier)
        )

        key_label = QtGui.QKeySequence(key).toString(QtGui.QKeySequence.PortableText)
        if key_label:
            return key_label

        if not has_modifier:
            txt = event.text()
            if txt:
                return txt

        return None

    def _collect_possible_actions(self, key_name, mod_state):
        actions = []
        seen = set()

        key_variants = self._hotkey_query_variants(key_name)
        contexts = self._list_hotkey_contexts()

        for key_variant in key_variants:
            # Global mapping
            actions.extend(self._collect_actions_from_hotkey(key_variant, mod_state, seen))

            # Context mappings (if available)
            for ctx in contexts:
                actions.extend(
                    self._collect_actions_from_hotkey(
                        key_variant,
                        mod_state,
                        seen,
                        context=ctx,
                    )
                )

        if not actions:
            actions.append("No action found")

        return actions

    def _collect_actions_from_hotkey(self, key_variant, mod_state, seen, context=None):
        out = []
        for release in (False, True):
            name_cmd = self._query_hotkey_name_command(
                key_variant,
                mod_state,
                release=release,
                context=context,
            )
            if not name_cmd:
                continue

            label = self._format_name_command_label(name_cmd, release=release, context=context)
            if label and label not in seen:
                seen.add(label)
                out.append(label)

            details = self._expand_action_details(name_cmd, context=context)
            for d in details:
                if d not in seen:
                    seen.add(d)
                    out.append(d)

        return out

    def _query_hotkey_name_command(self, key_shortcut, mod_state, release=False, context=None):
        query_flag = "releaseName" if release else "name"

        # Maya versions can vary in what combinations of flags are accepted in query mode.
        # Try strict query first, then progressively looser variants.
        candidate_kwargs = []

        base = {
            "keyShortcut": key_shortcut,
            "query": True,
            query_flag: True,
        }

        strict = dict(base)
        strict.update(
            {
                "ctlModifier": mod_state["ctrl"],
                "altModifier": mod_state["alt"],
                "shiftModifier": mod_state["shift"],
            }
        )
        candidate_kwargs.append(strict)

        # Some environments reject explicit False modifier flags. Retry with only active modifiers.
        active_only = dict(base)
        if mod_state["ctrl"]:
            active_only["ctlModifier"] = True
        if mod_state["alt"]:
            active_only["altModifier"] = True
        if mod_state["shift"]:
            active_only["shiftModifier"] = True
        candidate_kwargs.append(active_only)

        # Last fallback: query only by key (lets Maya resolve current state internally).
        candidate_kwargs.append(dict(base))

        for kwargs in candidate_kwargs:
            if context:
                kwargs["ctxClient"] = context
            try:
                result = cmds.hotkey(**kwargs)
                if result:
                    return result
            except Exception:
                continue

        return None

    def _expand_action_details(self, name_cmd, context=None):
        details = []

        base = self._describe_name_command(name_cmd)
        if base:
            details.append(base)

        runtime_name = self._query_name_command(name_cmd, "command")
        if runtime_name:
            rtc_details = self._describe_runtime_command(runtime_name)
            if rtc_details:
                details.append(rtc_details)

        details.extend(self._describe_assign_command_matches(name_cmd))

        hotkey_set = self._current_hotkey_set()
        if hotkey_set:
            details.append(f"HotkeySet: {hotkey_set}")
        if context:
            details.append(f"Context: {context}")

        return [d for d in details if d]

    def _format_name_command_label(self, name_cmd, release=False, context=None):
        chunks = [name_cmd]
        if release:
            chunks.append("(release)")
        if context:
            chunks.append(f"[{context}]")
        return " ".join(chunks)

    def _describe_name_command(self, name_cmd):
        ann = self._query_name_command(name_cmd, "annotation")
        cmd = self._query_name_command(name_cmd, "command")

        parts = [f"nameCommand: {name_cmd}"]
        if ann:
            parts.append(f"annotation: {ann}")
        if cmd:
            parts.append(f"command: {cmd}")
        return " | ".join(parts)

    def _query_name_command(self, name_cmd, field):
        field_flags = {
            "annotation": "annotation",
            "command": "command",
        }

        flag = field_flags.get(field)
        if not flag:
            return None

        try:
            return cmds.nameCommand(name_cmd, query=True, **{flag: True})
        except Exception:
            return None

    def _describe_runtime_command(self, runtime_name):
        try:
            exists = cmds.runTimeCommand(runtime_name, query=True, exists=True)
        except Exception:
            exists = False

        if not exists:
            return None

        annotation = self._safe_runtime_query(runtime_name, "annotation")
        command = self._safe_runtime_query(runtime_name, "command")

        parts = [f"runTimeCommand: {runtime_name}"]
        if annotation:
            parts.append(f"annotation: {annotation}")
        if command:
            parts.append(f"command: {command}")
        return " | ".join(parts)

    def _safe_runtime_query(self, runtime_name, flag_name):
        try:
            return cmds.runTimeCommand(runtime_name, query=True, **{flag_name: True})
        except Exception:
            return None

    def _describe_assign_command_matches(self, name_cmd):
        matches = []
        try:
            count = cmds.assignCommand(query=True, numElements=True)
        except Exception:
            return matches

        if not count:
            return matches

        for idx in range(1, int(count) + 1):
            try:
                cmd_name = cmds.assignCommand(idx, query=True, name=True)
            except Exception:
                continue

            if cmd_name != name_cmd:
                continue

            cmd_text = self._safe_assign_query(idx, "command")
            ann = self._safe_assign_query(idx, "annotation")
            rtc = self._safe_assign_query(idx, "runTimeCommand")

            parts = [f"assignCommand[{idx}] name: {cmd_name}"]
            if rtc:
                parts.append(f"runTimeCommand: {rtc}")
            if ann:
                parts.append(f"annotation: {ann}")
            if cmd_text:
                parts.append(f"command: {cmd_text}")

            matches.append(" | ".join(parts))

        return matches

    def _safe_assign_query(self, idx, flag):
        try:
            return cmds.assignCommand(idx, query=True, **{flag: True})
        except Exception:
            return None

    def _current_hotkey_set(self):
        try:
            return cmds.hotkeySet(query=True, current=True)
        except Exception:
            return None

    def _list_hotkey_contexts(self):
        contexts = []
        for kwargs in (
            {"query": True, "list": True},
            {"query": True, "all": True},
        ):
            try:
                result = cmds.hotkeyCtx(**kwargs)
                if result:
                    contexts.extend(result)
            except Exception:
                continue

        # Preserve order and uniqueness.
        dedup = []
        seen = set()
        for c in contexts:
            if c not in seen:
                seen.add(c)
                dedup.append(c)
        return dedup

    def _hotkey_query_variants(self, key_name):
        variants = [key_name]

        if len(key_name) == 1 and key_name.isalpha():
            # Maya hotkeys for letters are usually stored as lowercase keyShortcut.
            variants.append(key_name.lower())
            variants.append(key_name.upper())

        dedup = []
        seen = set()
        for item in variants:
            if item not in seen:
                seen.add(item)
                dedup.append(item)
        return dedup

    def _print_log_block(self, shortcut_str, actions):
        print(f'Shortcut : "{shortcut_str}"')
        print("\nPossible actions :")
        for action in actions:
            print(f"- {action}")
        print("")


_SHORTCUT_LOGGER_INSTANCE = None


def _maya_main_window():
    if omui is None:
        return QtWidgets.QApplication.instance()

    ptr = omui.MQtUtil.mainWindow()
    if not ptr:
        return QtWidgets.QApplication.instance()

    return shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)


def install_shortcut_logger():
    """Install the Maya shortcut logger Qt event filter."""
    global _SHORTCUT_LOGGER_INSTANCE

    app = QtWidgets.QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication is not available.")

    if _SHORTCUT_LOGGER_INSTANCE is not None:
        print("MayaShortcutLogger already installed.")
        return _SHORTCUT_LOGGER_INSTANCE

    parent = _maya_main_window()
    _SHORTCUT_LOGGER_INSTANCE = MayaShortcutLogger(parent=parent)
    app.installEventFilter(_SHORTCUT_LOGGER_INSTANCE)
    print("MayaShortcutLogger installed.")
    return _SHORTCUT_LOGGER_INSTANCE


def uninstall_shortcut_logger():
    """Remove the Maya shortcut logger Qt event filter."""
    global _SHORTCUT_LOGGER_INSTANCE

    if _SHORTCUT_LOGGER_INSTANCE is None:
        print("MayaShortcutLogger is not installed.")
        return

    app = QtWidgets.QApplication.instance()
    if app:
        app.removeEventFilter(_SHORTCUT_LOGGER_INSTANCE)

    _SHORTCUT_LOGGER_INSTANCE.deleteLater()
    _SHORTCUT_LOGGER_INSTANCE = None
    print("MayaShortcutLogger uninstalled.")


# Auto-install when the script is executed in Maya Script Editor.
install_shortcut_logger()
