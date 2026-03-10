# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import maya.cmds as cmds

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:
    from PySide2 import QtCore, QtGui, QtWidgets

try:
    from maya import OpenMaya as om
except Exception:
    om = None


_SPECIAL_KEYS = {
    QtCore.Qt.Key_Space: "Space",
    QtCore.Qt.Key_Tab: "Tab",
    QtCore.Qt.Key_Backspace: "Backspace",
    QtCore.Qt.Key_Return: "Enter",
    QtCore.Qt.Key_Enter: "Enter",
    QtCore.Qt.Key_Escape: "Esc",
    QtCore.Qt.Key_Delete: "Delete",
}


class ShortcutStore:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.edges = {}  # shortcut -> set(actions)
        self._listeners = []
        self.load()

    def load(self):
        if not self.file_path.exists():
            self.edges = {}
            return
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            self.edges = {k: set(v) for k, v in (data.get("edges") or {}).items()}
        except Exception:
            self.edges = {}

    def save(self):
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"edges": {k: sorted(v) for k, v in self.edges.items()}}
        self.file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_link(self, shortcut: str, action: str):
        if not shortcut or not action:
            return
        before = len(self.edges.get(shortcut, set()))
        self.edges.setdefault(shortcut, set()).add(action)
        after = len(self.edges.get(shortcut, set()))
        if after != before:
            self.save()
            self._notify()

    def add_listener(self, callback):
        if callback and callback not in self._listeners:
            self._listeners.append(callback)

    def _notify(self):
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                continue

    def components(self):
        # bipartite components: shortcuts <-> actions
        action_to_shortcuts = {}
        for s, acts in self.edges.items():
            for a in acts:
                action_to_shortcuts.setdefault(a, set()).add(s)

        visited_shortcuts = set()
        rows = []
        for shortcut in sorted(self.edges.keys()):
            if shortcut in visited_shortcuts:
                continue
            q_short = [shortcut]
            q_act = []
            comp_short = set()
            comp_act = set()

            while q_short or q_act:
                while q_short:
                    s = q_short.pop()
                    if s in comp_short:
                        continue
                    comp_short.add(s)
                    visited_shortcuts.add(s)
                    for a in self.edges.get(s, set()):
                        if a not in comp_act:
                            q_act.append(a)

                while q_act:
                    a = q_act.pop()
                    if a in comp_act:
                        continue
                    comp_act.add(a)
                    for s in action_to_shortcuts.get(a, set()):
                        if s not in comp_short:
                            q_short.append(s)

            rows.append((sorted(comp_short), sorted(comp_act)))

        return rows


class MayaShortcutLogger(QtCore.QObject):
    def __init__(self, store: ShortcutStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.enabled = True
        self.logged_shortcuts = set()
        self.command_history = []
        self.capture_window_ms = 220
        self.callback_id = None
        self._install_command_callback()

    def _install_command_callback(self):
        if om is None or self.callback_id is not None:
            return
        try:
            self.callback_id = om.MCommandMessage.addCommandOutputCallback(self._on_command_output)
        except Exception:
            self.callback_id = None

    def uninstall_callback(self):
        if om is None or self.callback_id is None:
            return
        try:
            om.MMessage.removeCallback(self.callback_id)
        except Exception:
            pass
        self.callback_id = None

    def _on_command_output(self, message, message_type=None, client_data=None):
        txt = str(message).strip()
        if not txt:
            return
        if not ("(" in txt or txt.endswith(";") or "setToolTo" in txt or "dR_" in txt):
            return
        self.command_history.append((time.time(), txt))
        if len(self.command_history) > 500:
            self.command_history = self.command_history[-500:]

    def eventFilter(self, obj, event):  # noqa: N802
        if not self.enabled:
            return False
        if event.type() != QtCore.QEvent.KeyPress:
            return False
        if hasattr(event, "isAutoRepeat") and event.isAutoRepeat():
            return False

        built = self._build_shortcut(event)
        if not built:
            return False
        shortcut, key, mods = built

        app = QtWidgets.QApplication.instance()
        global_seen = app.property("_msl_seen") if app else None
        if global_seen is None:
            global_seen = []

        if shortcut in self.logged_shortcuts or shortcut in global_seen:
            return False

        self.logged_shortcuts.add(shortcut)
        if app:
            app.setProperty("_msl_seen", list(global_seen) + [shortcut])

        possible = self._clean_actions(self._collect_possible_actions(key, mods))
        t0 = time.time()
        QtCore.QTimer.singleShot(
            self.capture_window_ms,
            lambda s=shortcut, p=possible, t=t0: self._finalize(s, p, t),
        )
        return False

    def _finalize(self, shortcut, possible, t0):
        commands = [txt for ts, txt in self.command_history if ts >= t0]
        executed = self._infer_executed(possible, commands)

        print(f'Shortcut : "{shortcut}"')
        print("\nPossible actions :")
        for a in possible:
            print(f"- {a}")
        if executed:
            official = self._official_action_name(executed)
            print("\nExecuted action :")
            print(f"- {official}")
            self.store.add_link(shortcut, official)
        print("")

    def _build_shortcut(self, event):
        key = event.key()
        if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Shift, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Meta):
            return None

        key_name = self._key_name(key, event)
        if not key_name:
            return None

        mods = event.modifiers()
        mod_state = {
            "ctrl": bool(mods & QtCore.Qt.ControlModifier),
            "alt": bool(mods & QtCore.Qt.AltModifier),
            "shift": bool(mods & QtCore.Qt.ShiftModifier),
        }
        chunks = []
        if mod_state["ctrl"]:
            chunks.append("Ctrl")
        if mod_state["alt"]:
            chunks.append("Alt")
        if mod_state["shift"]:
            chunks.append("Shift")
        chunks.append(key_name)
        return "+".join(chunks), key_name, mod_state

    def _key_name(self, key, event):
        if key in _SPECIAL_KEYS:
            return _SPECIAL_KEYS[key]
        if QtCore.Qt.Key_A <= key <= QtCore.Qt.Key_Z:
            return chr(key)
        if QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9:
            return chr(key)

        with_mod = bool(event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.ShiftModifier))
        label = QtGui.QKeySequence(key).toString(QtGui.QKeySequence.PortableText)
        if label:
            return label
        if not with_mod and event.text():
            return event.text()
        return None

    def _collect_possible_actions(self, key, mods):
        out = []
        seen = set()
        for variant in self._variants(key):
            for release in (False, True):
                cmd = self._hotkey_name(variant, mods, release=release)
                if cmd and cmd not in seen:
                    seen.add(cmd)
                    out.append(cmd)
                    out.extend(self._expand_name_command(cmd, seen))

        out.extend(self._from_assign_commands(key, mods, seen))
        if not out:
            out.append("No action found")
        return out

    def _hotkey_name(self, key, mods, release=False):
        flag = "releaseName" if release else "name"
        attempts = [
            ([key], {"query": True, flag: True, "ctrlModifier": mods["ctrl"], "altModifier": mods["alt"], "shiftModifier": mods["shift"]}),
            ([key], {"query": True, flag: True}),
        ]
        for args, kwargs in attempts:
            try:
                result = cmds.hotkey(*args, **kwargs)
                if result:
                    return result
            except Exception:
                continue
        return None

    def _expand_name_command(self, name_cmd, seen):
        out = []
        try:
            runtime = cmds.nameCommand(name_cmd, query=True, command=True)
        except Exception:
            runtime = None
        try:
            ann = cmds.nameCommand(name_cmd, query=True, annotation=True)
        except Exception:
            ann = None

        for item in (runtime, ann):
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    def _from_assign_commands(self, key, mods, seen):
        out = []
        try:
            count = int(cmds.assignCommand(query=True, numElements=True) or 0)
        except Exception:
            return out

        key_variants = {k.lower() for k in self._variants(key)}
        for idx in range(1, count + 1):
            try:
                key_string = cmds.assignCommand(idx, query=True, keyString=True)
            except Exception:
                continue
            if not self._match_keystring(key_string, key_variants, mods):
                continue

            for flag in ("name", "runTimeCommand", "annotation", "command"):
                try:
                    val = cmds.assignCommand(idx, query=True, **{flag: True})
                except Exception:
                    val = None
                if val and val not in seen:
                    seen.add(val)
                    out.append(val)
        return out

    def _match_keystring(self, key_string, key_variants, mods):
        if not key_string:
            return False
        t = str(key_string).lower().replace("control", "ctrl")
        t = t.replace(" ", "").replace("-", "+").replace("_", "+")
        for suffix in ("press", "release", "keydown", "keyup"):
            t = t.replace(suffix, "")

        has_ctrl = "ctrl" in t
        has_alt = "alt" in t
        has_shift = "shift" in t or "sht" in t
        if has_ctrl != mods["ctrl"] or has_alt != mods["alt"] or has_shift != mods["shift"]:
            return False

        for k in key_variants:
            if t.endswith(k) or f"+{k}" in t or k == t:
                return True
        return False

    def _variants(self, key):
        out = [key]
        if len(key) == 1 and key.isalpha():
            out.extend([key.lower(), key.upper()])
        dedup = []
        seen = set()
        for i in out:
            if i not in seen:
                seen.add(i)
                dedup.append(i)
        return dedup

    def _clean_actions(self, actions):
        clean = []
        seen = set()
        for a in actions:
            if not a:
                continue
            t = str(a).strip()
            if not t:
                continue
            if t.lower() in ("true", "false"):
                continue
            t = self._official_action_name(t)
            if t not in seen:
                seen.add(t)
                clean.append(t)
        return clean or ["No action found"]

    def _official_action_name(self, action):
        a = str(action).strip()
        if not a:
            return a

        # If this looks like a nameCommand, prefer human-readable annotation.
        if a.lower().endswith("namecommand") or "namecom" in a.lower():
            try:
                ann = cmds.nameCommand(a, query=True, annotation=True)
            except Exception:
                ann = None
            if ann:
                return ann

            try:
                runtime = cmds.nameCommand(a, query=True, command=True)
            except Exception:
                runtime = None

            if runtime:
                try:
                    rtc_ann = cmds.runTimeCommand(runtime, query=True, annotation=True)
                except Exception:
                    rtc_ann = None
                if rtc_ann:
                    return rtc_ann
                return runtime

        # If this is a runtime command name, use its annotation when available.
        try:
            if cmds.runTimeCommand(a, query=True, exists=True):
                try:
                    rtc_ann = cmds.runTimeCommand(a, query=True, annotation=True)
                except Exception:
                    rtc_ann = None
                if rtc_ann:
                    return rtc_ann
        except Exception:
            pass

        # Fallback: prettify technical tokens.
        pretty = re.sub(r"(NameCommand|NameCom)", "", a, flags=re.IGNORECASE)
        pretty = re.sub(r"([a-z])([A-Z])", r"\1 \2", pretty)
        pretty = pretty.replace("_", " ").strip()
        return pretty or a

    def _infer_executed(self, possible_actions, commands):
        if not commands:
            return None
        blob = self._norm(" ".join(commands))
        best = None
        best_score = 0
        for action in possible_actions:
            if action == "No action found":
                continue
            score = 0
            for tok in self._tokens(action):
                if tok and tok in blob:
                    score += len(tok)
            if score > best_score:
                best = action
                best_score = score
        return best

    def _tokens(self, action):
        raw = str(action)
        items = {self._norm(raw)}
        parts = re.sub(r"([a-z])([A-Z])", r"\1 \2", raw).replace("_", " ").replace("-", " ").split()
        for p in parts:
            n = self._norm(p)
            if len(n) >= 4:
                items.add(n)
        return sorted(items, key=len, reverse=True)

    def _norm(self, text):
        return re.sub(r"[^a-z0-9]", "", str(text).lower())
