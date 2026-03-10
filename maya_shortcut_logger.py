# -*- coding: utf-8 -*-
"""Maya Shortcut Logger

Capture every unique pressed shortcut and log all possible Maya actions attached to it.
Compatible with Maya 2022+ (PySide2/PySide6).
"""

from __future__ import annotations

import traceback
import re
import time
import json
from pathlib import Path

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

    def _debug(self, stage, **payload):
        if not self.debug_enabled:
            return
        data = {
            "timestamp": time.time(),
            "stage": stage,
        }
        data.update(payload)
        try:
            print("[ShortcutDebug] " + json.dumps(data, ensure_ascii=False, default=str))
        except Exception:
            print("[ShortcutDebug] " + str(data))

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logged_shortcuts = set()
        self._parsed_file_bindings = None
        self._assign_index = None
        self.debug_enabled = True

    def eventFilter(self, obj, event):  # noqa: N802 (Qt API naming)
        if event.type() != QtCore.QEvent.KeyPress:
            return False

        shortcut_data = self._build_shortcut_from_event(event)
        if not shortcut_data:
            return False

        shortcut_str, key_token, mods = shortcut_data
        self._debug("key_press_detected", shortcut=shortcut_str, key_token=key_token, mods=mods)
        if shortcut_str in self.logged_shortcuts:
            self._debug("shortcut_duplicate_ignored", shortcut=shortcut_str)
            return False

        self.logged_shortcuts.add(shortcut_str)

        try:
            possible_actions = self._collect_possible_actions(key_token, mods)
            self._debug("collection_completed", shortcut=shortcut_str, action_count=len(possible_actions))
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
        self._debug("collect_start", key_name=key_name, mod_state=mod_state, key_variants=key_variants, contexts=contexts)

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

        # Primary fallback: parse active hotkey-set files directly (.mhk/.mel), bypassing
        # cmds.hotkey query differences across Maya versions.
        before = len(actions)
        actions.extend(self._collect_actions_from_hotkey_files(key_name, mod_state, seen))
        self._debug("collect_hotkey_files_done", key_name=key_name, added=len(actions)-before)

        # Secondary fallback: resolve from a prebuilt assignCommand shortcut index.
        before = len(actions)
        actions.extend(self._collect_actions_from_assign_index(key_name, mod_state, seen))
        self._debug("collect_assign_index_done", key_name=key_name, added=len(actions)-before)

        # Last fallback: query hotkey raw return and expand any token returned.
        for key_variant in key_variants:
            before = len(actions)
            actions.extend(self._collect_actions_from_hotkey_raw_query(key_variant, mod_state, seen))
            self._debug("collect_hotkey_raw_done", key_variant=key_variant, added=len(actions)-before)

        if not actions:
            actions.append("No action found")
            self._debug("collect_no_action", key_name=key_name, mod_state=mod_state)

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

        call_specs = []

        # Style A: positional key argument in query mode (required in some Maya versions).
        call_specs.append(
            {
                "args": [key_shortcut],
                "kwargs": {
                    "query": True,
                    query_flag: True,
                    "ctrlModifier": mod_state["ctrl"],
                    "altModifier": mod_state["alt"],
                    "shiftModifier": mod_state["shift"],
                },
            }
        )

        # Style B: positional key with only active modifiers.
        active_kwargs = {"query": True, query_flag: True}
        if mod_state["ctrl"]:
            active_kwargs["ctrlModifier"] = True
        if mod_state["alt"]:
            active_kwargs["altModifier"] = True
        if mod_state["shift"]:
            active_kwargs["shiftModifier"] = True
        call_specs.append({"args": [key_shortcut], "kwargs": active_kwargs})

        # Style C: legacy keyShortcut flag usage (works in some environments).
        call_specs.append(
            {
                "args": [],
                "kwargs": {
                    "keyShortcut": key_shortcut,
                    "query": True,
                    query_flag: True,
                    "ctrlModifier": mod_state["ctrl"],
                    "altModifier": mod_state["alt"],
                    "shiftModifier": mod_state["shift"],
                },
            }
        )

        for spec in call_specs:
            kwargs = dict(spec["kwargs"])
            if context:
                kwargs["ctxClient"] = context
            try:
                result = cmds.hotkey(*spec["args"], **kwargs)
                self._debug(
                    "hotkey_name_query",
                    key_shortcut=key_shortcut,
                    context=context,
                    release=release,
                    args=spec["args"],
                    kwargs=kwargs,
                    result=result,
                )
                if result:
                    return result
            except Exception as exc:
                self._debug(
                    "hotkey_name_query_error",
                    key_shortcut=key_shortcut,
                    context=context,
                    release=release,
                    args=spec["args"],
                    kwargs=kwargs,
                    error=str(exc),
                )
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

    def _collect_actions_from_hotkey_raw_query(self, key_variant, mod_state, seen, context=None):
        out = []
        call_specs = [
            {
                "args": [key_variant],
                "kwargs": {
                    "query": True,
                    "ctrlModifier": mod_state["ctrl"],
                    "altModifier": mod_state["alt"],
                    "shiftModifier": mod_state["shift"],
                },
            },
            {"args": [key_variant], "kwargs": {"query": True}},
            {
                "args": [],
                "kwargs": {
                    "keyShortcut": key_variant,
                    "query": True,
                    "ctrlModifier": mod_state["ctrl"],
                    "altModifier": mod_state["alt"],
                    "shiftModifier": mod_state["shift"],
                },
            },
            {"args": [], "kwargs": {"keyShortcut": key_variant, "query": True}},
        ]

        for spec in call_specs:
            kwargs = dict(spec["kwargs"])
            if context:
                kwargs["ctxClient"] = context
            try:
                raw = cmds.hotkey(*spec["args"], **kwargs)
                self._debug(
                    "hotkey_raw_query",
                    key_variant=key_variant,
                    context=context,
                    args=spec["args"],
                    kwargs=kwargs,
                    raw=raw,
                )
            except Exception as exc:
                self._debug(
                    "hotkey_raw_query_error",
                    key_variant=key_variant,
                    context=context,
                    args=spec["args"],
                    kwargs=kwargs,
                    error=str(exc),
                )
                continue

            for token in self._flatten_hotkey_result_tokens(raw):
                if not token:
                    continue

                label = f"hotkeyRaw: {token}"
                if label not in seen:
                    seen.add(label)
                    out.append(label)

                details = self._expand_token_details(token)
                for d in details:
                    if d not in seen:
                        seen.add(d)
                        out.append(d)

        return out

    def _flatten_hotkey_result_tokens(self, raw):
        tokens = []
        if raw is None:
            return tokens

        # Maya may return bare booleans for existence checks in query mode.
        if isinstance(raw, bool):
            return tokens

        if isinstance(raw, str):
            tokens.append(raw)
            return tokens

        if isinstance(raw, (list, tuple, set)):
            for item in raw:
                tokens.extend(self._flatten_hotkey_result_tokens(item))
            return tokens

        if isinstance(raw, dict):
            for k, v in raw.items():
                tokens.extend(self._flatten_hotkey_result_tokens(k))
                tokens.extend(self._flatten_hotkey_result_tokens(v))
            return tokens

        tokens.append(str(raw))
        return tokens

    def _expand_token_details(self, token):
        out = []
        tok = str(token).strip()
        if not tok:
            return out

        nc = self._describe_name_command(tok)
        if nc and nc != f"nameCommand: {tok}":
            out.append(nc)
            out.extend(self._expand_action_details(tok))

        rtc = self._describe_runtime_command(tok)
        if rtc:
            out.append(rtc)

        return out

    def _collect_actions_from_hotkey_files(self, key_name, mod_state, seen):
        out = []
        key_variants = {k.lower() for k in self._hotkey_query_variants(key_name)}

        # Force refresh to avoid stale empty cache when hotkey set changes at runtime.
        self._parsed_file_bindings = None
        bindings = self._load_parsed_hotkey_file_bindings()
        self._debug("hotkey_file_lookup_start", key_name=key_name, mods=mod_state, bindings_count=len(bindings))
        for binding in bindings:
            if binding.get("key", "").lower() not in key_variants:
                continue
            if bool(binding.get("ctrl")) != bool(mod_state.get("ctrl")):
                continue
            if bool(binding.get("alt")) != bool(mod_state.get("alt")):
                continue
            if bool(binding.get("shift")) != bool(mod_state.get("shift")):
                continue

            name_cmd = binding.get("name")
            release_name = binding.get("releaseName")
            source = binding.get("source")

            if name_cmd:
                label = f"fileHotkey: {name_cmd} ({source})"
                if label not in seen:
                    seen.add(label)
                    out.append(label)
                for d in self._expand_action_details(name_cmd):
                    if d not in seen:
                        seen.add(d)
                        out.append(d)

            if release_name:
                label = f"fileHotkey: {release_name} (release) ({source})"
                if label not in seen:
                    seen.add(label)
                    out.append(label)
                for d in self._expand_action_details(release_name):
                    if d not in seen:
                        seen.add(d)
                        out.append(d)

        return out

    def _load_parsed_hotkey_file_bindings(self):
        if self._parsed_file_bindings is not None:
            return self._parsed_file_bindings

        bindings = []
        pref_dir = None
        try:
            pref_dir = cmds.internalVar(userPrefDir=True)
        except Exception:
            pref_dir = None

        if not pref_dir:
            self._parsed_file_bindings = bindings
            return bindings

        pref_path = Path(pref_dir)
        candidates = []

        current_set = None
        try:
            current_set = cmds.hotkeySet(query=True, current=True)
        except Exception:
            current_set = None

        if current_set:
            set_mhk = pref_path / "hotkeys" / f"{current_set}.mhk"
            if set_mhk.exists() and set_mhk.is_file():
                candidates.append(set_mhk)
            set_mel = pref_path / "hotkeys" / f"userHotkeys_{current_set}.mel"
            if set_mel.exists() and set_mel.is_file():
                candidates.append(set_mel)

        explicit = [
            pref_path / "userHotkeys.mel",
            pref_path / "hotkeys" / "userHotkeys.mel",
        ]
        for c in explicit:
            if c.exists() and c.is_file() and c not in candidates:
                candidates.append(c)

        for pattern in ("*.mhk", "*Hotkey*.mel", "*hotkey*.mel"):
            for c in pref_path.rglob(pattern):
                if c.is_file() and c not in candidates:
                    candidates.append(c)

        self._debug(
            "hotkey_file_candidates",
            pref_dir=str(pref_path),
            current_hotkey_set=current_set,
            candidate_count=len(candidates),
            candidates=[str(c) for c in candidates[:40]],
        )

        for file_path in candidates:
            text = self._read_text_any_encoding(file_path)
            if not text:
                continue

            cmds_text = self._extract_hotkey_command_chunks(text)
            self._debug("hotkey_file_scan", file=str(file_path), chunk_count=len(cmds_text))
            for cmd_text in cmds_text:
                parsed = self._parse_hotkey_command_text(cmd_text)
                if not parsed:
                    continue
                parsed["source"] = str(file_path)
                bindings.append(parsed)

        self._debug("hotkey_file_bindings_loaded", count=len(bindings), sample=bindings[:20])
        self._parsed_file_bindings = bindings
        return bindings

    def _read_text_any_encoding(self, file_path):
        try:
            raw = file_path.read_bytes()
        except Exception as exc:
            self._debug("hotkey_file_read_error", file=str(file_path), error=str(exc))
            return ""

        for enc in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except Exception:
                continue

        return raw.decode("utf-8", errors="ignore")

    def _extract_hotkey_command_chunks(self, text):
        # Parse command chunks robustly for MEL and MHK formats.
        chunks = []
        # Prefer semicolon-separated MEL statements.
        for part in text.split(";"):
            stmt = part.strip()
            if not stmt:
                continue
            if re.search(r"(?i)\bhotkey\b", stmt):
                chunks.append(stmt + ";")

        # If empty (or sparse), fallback to line-based detection.
        if not chunks:
            for line in text.splitlines():
                stmt = line.strip()
                if re.search(r"(?i)^hotkey\b", stmt):
                    chunks.append(stmt)

        return chunks

    def _parse_hotkey_command_text(self, cmd_text):
        key = self._extract_quoted_flag(cmd_text, "k") or self._extract_quoted_flag(cmd_text, "keyShortcut")
        if not key:
            return None

        name_cmd = self._extract_quoted_flag(cmd_text, "name")
        release_name = self._extract_quoted_flag(cmd_text, "releaseName")

        ctrl = self._extract_bool_flag(cmd_text, ["ctl", "ctrl", "ctrlModifier", "ctlModifier"])
        alt = self._extract_bool_flag(cmd_text, ["alt", "altModifier"])
        shift = self._extract_bool_flag(cmd_text, ["sht", "shift", "shiftModifier"])

        if not name_cmd and not release_name:
            return None

        return {
            "key": key,
            "name": name_cmd,
            "releaseName": release_name,
            "ctrl": ctrl,
            "alt": alt,
            "shift": shift,
        }

    def _extract_quoted_flag(self, text, flag):
        m = re.search(rf"(?:-|/){re.escape(flag)}\\s+\"([^\"]+)\"", text, flags=re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    def _extract_bool_flag(self, text, possible_flags):
        for flag in possible_flags:
            # explicit value, e.g. -ctrlModifier true
            m = re.search(rf"(?:-|/){re.escape(flag)}\s+(true|false|1|0)", text, flags=re.IGNORECASE)
            if m:
                return m.group(1).lower() in ("true", "1")
            # switch style, e.g. -ctl or -sht
            if re.search(rf"(?:-|/){re.escape(flag)}(?=\s|-|/|$)", text, flags=re.IGNORECASE):
                return True
        return False

    def _collect_actions_from_assign_index(self, key_name, mod_state, seen):
        out = []
        key_variants = {k.lower() for k in self._hotkey_query_variants(key_name)}

        index = self._build_assign_index()
        self._debug("assign_index_lookup_start", key_name=key_name, mods=mod_state, index_size=len(index))
        matched = 0
        for rec in index:
            key_string = rec.get("keyString")
            if not self._assign_keystring_matches_shortcut(key_string, key_variants, mod_state):
                continue

            idx = rec.get("idx")
            label_parts = [f"assignIndex[{idx}] keyString: {key_string}"]

            name_cmd = rec.get("name")
            rtc = rec.get("runTimeCommand")
            ann = rec.get("annotation")
            cmd_text = rec.get("command")

            if name_cmd:
                label_parts.append(f"name: {name_cmd}")
            if rtc:
                label_parts.append(f"runTimeCommand: {rtc}")
            if ann:
                label_parts.append(f"annotation: {ann}")
            if cmd_text:
                label_parts.append(f"command: {cmd_text}")

            label = " | ".join(label_parts)
            if label not in seen:
                seen.add(label)
                out.append(label)
                matched += 1
                self._debug("assign_index_match", idx=idx, keyString=key_string, name=name_cmd, runTimeCommand=rtc)

            if name_cmd:
                for d in self._expand_action_details(name_cmd):
                    if d not in seen:
                        seen.add(d)
                        out.append(d)

            if rtc:
                rtc_line = self._describe_runtime_command(rtc)
                if rtc_line and rtc_line not in seen:
                    seen.add(rtc_line)
                    out.append(rtc_line)

        if not matched:
            self._debug("assign_index_no_match", key_name=key_name, mods=mod_state)
        return out

    def _build_assign_index(self):
        if self._assign_index is not None:
            return self._assign_index

        out = []
        try:
            count = cmds.assignCommand(query=True, numElements=True)
            self._debug("assign_index_count", count=count)
        except Exception as exc:
            self._debug("assign_index_count_error", error=str(exc))
            self._assign_index = out
            return out

        if not count:
            self._assign_index = out
            return out

        for idx in range(1, int(count) + 1):
            key_string = self._safe_assign_query(idx, "keyString")
            if not key_string:
                continue

            rec = {
                "idx": idx,
                "keyString": key_string,
                "name": self._safe_assign_query(idx, "name"),
                "runTimeCommand": self._safe_assign_query(idx, "runTimeCommand"),
                "annotation": self._safe_assign_query(idx, "annotation"),
                "command": self._safe_assign_query(idx, "command"),
            }
            out.append(rec)

        sample = out[:20]
        self._debug("assign_index_built", size=len(out), sample=sample)
        self._assign_index = out
        return out

    def _assign_keystring_matches_shortcut(self, key_string, key_variants, mod_state):
        if not key_string:
            return False

        text = str(key_string).strip().lower()
        text = text.replace("control", "ctrl")
        text = text.replace("command", "meta")
        text = text.replace(" ", "")
        text = text.replace("-", "+")
        text = text.replace("_", "+")

        # Remove non-semantic suffixes commonly found in key strings.
        for suffix in ("press", "release", "keydown", "keyup"):
            text = text.replace(suffix, "")

        # Tokenize by + and also keep merged string for fallback checks.
        tokens = [t for t in text.split("+") if t]
        token_set = set(tokens)

        wants_ctrl = bool(mod_state.get("ctrl"))
        wants_alt = bool(mod_state.get("alt"))
        wants_shift = bool(mod_state.get("shift"))

        has_ctrl = ("ctrl" in token_set) or ("ctrl" in text)
        has_alt = ("alt" in token_set) or ("alt" in text)
        has_shift = ("shift" in token_set) or ("sht" in token_set) or ("shift" in text)

        if has_ctrl != wants_ctrl:
            return False
        if has_alt != wants_alt:
            return False
        if has_shift != wants_shift:
            return False

        # Key match: tolerate compact forms where key may be concatenated.
        for key in key_variants:
            if key in token_set:
                return True
            if text.endswith(key):
                return True
            if f"+{key}+" in f"+{text}+":
                return True

        return False

    def _parse_assign_keystring(self, key_string):
        text = str(key_string).strip().lower()
        text = text.replace("control", "ctrl")
        text = text.replace(" ", "")
        text = text.replace("-", "+")
        text = text.replace("_", "+")

        press_type = "press"
        if "release" in text:
            press_type = "release"

        text = text.replace("release", "")
        text = text.replace("press", "")
        text = text.replace("keydown", "")
        text = text.replace("keyup", "")

        parts = [p for p in text.split("+") if p]
        if not parts:
            return None

        mods = set(parts[:-1]) if len(parts) > 1 else set()
        key = parts[-1]
        if not key:
            return None

        return {
            "key": key,
            "ctrl": "ctrl" in mods,
            "alt": "alt" in mods,
            "shift": "shift" in mods,
            "press_type": press_type,
        }

    def _collect_actions_from_assign_keystrings(self, key_name, mod_state, seen):
        out = []
        target_tokens = self._target_keystring_tokens(key_name, mod_state)

        try:
            count = cmds.assignCommand(query=True, numElements=True)
        except Exception:
            return out

        if not count:
            return out

        for idx in range(1, int(count) + 1):
            key_string = self._safe_assign_query(idx, "keyString")
            if not key_string:
                continue

            if not self._keystring_matches_shortcut(key_string, target_tokens):
                continue

            name_cmd = self._safe_assign_query(idx, "name")
            rtc = self._safe_assign_query(idx, "runTimeCommand")
            ann = self._safe_assign_query(idx, "annotation")
            cmd_text = self._safe_assign_query(idx, "command")

            label_parts = [f"assignCommand[{idx}] keyString: {key_string}"]
            if name_cmd:
                label_parts.append(f"name: {name_cmd}")
            if rtc:
                label_parts.append(f"runTimeCommand: {rtc}")
            if ann:
                label_parts.append(f"annotation: {ann}")
            if cmd_text:
                label_parts.append(f"command: {cmd_text}")

            label = " | ".join(label_parts)
            if label not in seen:
                seen.add(label)
                out.append(label)

            if name_cmd:
                details = self._expand_action_details(name_cmd)
                for detail in details:
                    if detail not in seen:
                        seen.add(detail)
                        out.append(detail)

            if rtc:
                rtc_line = self._describe_runtime_command(rtc)
                if rtc_line and rtc_line not in seen:
                    seen.add(rtc_line)
                    out.append(rtc_line)

        return out

    def _target_keystring_tokens(self, key_name, mod_state):
        key_variants = {k.lower() for k in self._hotkey_query_variants(key_name)}
        return {
            "keys": key_variants,
            "ctrl": bool(mod_state["ctrl"]),
            "alt": bool(mod_state["alt"]),
            "shift": bool(mod_state["shift"]),
        }

    def _keystring_matches_shortcut(self, key_string, target):
        text = self._normalize_keystring(str(key_string))

        has_ctrl = "ctrl" in text
        has_alt = "alt" in text
        has_shift = "shift" in text

        if has_ctrl != target["ctrl"]:
            return False
        if has_alt != target["alt"]:
            return False
        if has_shift != target["shift"]:
            return False

        for key in target["keys"]:
            if f"+{key}" in text or text.endswith(key) or f"({key})" in text:
                return True
            if text == key:
                return True

        return False

    def _normalize_keystring(self, text):
        text = text.strip().lower()
        text = text.replace("control", "ctrl")
        text = text.replace("command", "meta")
        text = text.replace(" ", "")
        text = text.replace("-", "+")
        text = text.replace("_", "+")
        text = text.replace("(press)", "")
        text = text.replace("(release)", "")
        return text

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

    existing = app.property("_maya_shortcut_logger_instance")
    if existing is not None:
        try:
            app.removeEventFilter(existing)
        except Exception:
            pass

    if _SHORTCUT_LOGGER_INSTANCE is not None:
        try:
            app.removeEventFilter(_SHORTCUT_LOGGER_INSTANCE)
        except Exception:
            pass

    parent = _maya_main_window()
    _SHORTCUT_LOGGER_INSTANCE = MayaShortcutLogger(parent=parent)
    app.installEventFilter(_SHORTCUT_LOGGER_INSTANCE)
    app.setProperty("_maya_shortcut_logger_instance", _SHORTCUT_LOGGER_INSTANCE)
    print("MayaShortcutLogger installed.")
    return _SHORTCUT_LOGGER_INSTANCE


def uninstall_shortcut_logger():
    """Remove the Maya shortcut logger Qt event filter."""
    global _SHORTCUT_LOGGER_INSTANCE

    app = QtWidgets.QApplication.instance()

    if app:
        existing = app.property("_maya_shortcut_logger_instance")
        if existing is not None:
            try:
                app.removeEventFilter(existing)
            except Exception:
                pass
            app.setProperty("_maya_shortcut_logger_instance", None)

    if _SHORTCUT_LOGGER_INSTANCE is None:
        print("MayaShortcutLogger is not installed.")
        return

    if app:
        try:
            app.removeEventFilter(_SHORTCUT_LOGGER_INSTANCE)
        except Exception:
            pass

    _SHORTCUT_LOGGER_INSTANCE.deleteLater()
    _SHORTCUT_LOGGER_INSTANCE = None
    print("MayaShortcutLogger uninstalled.")


# Auto-install when the script is executed in Maya Script Editor.
install_shortcut_logger()
