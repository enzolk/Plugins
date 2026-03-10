from __future__ import annotations

import bpy
from pathlib import Path

from .store import ShortcutStore

MODIFIER_KEYS = {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT", "OSKEY"}
IGNORED_VALUES = {"RELEASE", "CLICK_DRAG"}


class ShortcutLoggerManager:
    def __init__(self):
        self.store = ShortcutStore(self._persistent_path())
        self.listening = False
        self._pending_events: dict[str, dict] = {}
        self.store.add_listener(self._tag_redraw)

    @staticmethod
    def _persistent_path() -> Path:
        config_root = Path(bpy.utils.user_resource("CONFIG"))
        return config_root / "blender_shortcut_logger" / "shortcut_table.json"

    def start(self) -> None:
        if self.listening:
            return
        self.listening = True
        try:
            bpy.ops.wm.shortcut_logger_listener("INVOKE_DEFAULT")
            self._log("Listening enabled")
        except Exception:
            self._log("Listener launch deferred until UI context is available")

    def stop(self) -> None:
        if not self.listening:
            return
        self.listening = False
        self._pending_events.clear()
        self._log("Listening disabled")

    def process_key_event(self, context: bpy.types.Context, event: bpy.types.Event) -> None:
        if not self.listening:
            return
        if event.value in IGNORED_VALUES or event.is_repeat:
            return
        if event.type in MODIFIER_KEYS:
            return

        shortcut = self._format_shortcut(event)
        candidates = self._possible_actions(context, event)
        snapshot = self._operator_snapshot(context.window_manager)

        event_id = f"{shortcut}:{event.type}:{event.ctrl}:{event.shift}:{event.alt}:{event.oskey}"
        self._pending_events[event_id] = {
            "shortcut": shortcut,
            "candidates": candidates,
            "snapshot": snapshot,
        }

        def _finalize() -> None:
            payload = self._pending_events.pop(event_id, None)
            if payload is None or not self.listening:
                return None
            executed = self._infer_executed_action(context.window_manager, payload["snapshot"], payload["candidates"])
            if executed:
                self.store.add_link(payload["shortcut"], executed)
            self._print_log(payload["shortcut"], payload["candidates"], executed)
            return None

        bpy.app.timers.register(_finalize, first_interval=0.2)

    def _format_shortcut(self, event: bpy.types.Event) -> str:
        parts = []
        if event.ctrl:
            parts.append("Ctrl")
        if event.shift:
            parts.append("Shift")
        if event.alt:
            parts.append("Alt")
        if event.oskey:
            parts.append("Cmd")
        parts.append(event.type.title().replace("_", " "))
        return "+".join(parts)

    def _possible_actions(self, context: bpy.types.Context, event: bpy.types.Event) -> list[str]:
        wm = context.window_manager
        matches: dict[str, str] = {}

        for keyconfig in (wm.keyconfigs.user, wm.keyconfigs.addon, wm.keyconfigs.default):
            if keyconfig is None:
                continue
            for keymap in keyconfig.keymaps:
                for item in keymap.keymap_items:
                    if not item.active or item.map_type != "KEYBOARD":
                        continue
                    if item.value not in {"PRESS", "CLICK"}:
                        continue
                    if item.type != event.type:
                        continue
                    if bool(item.ctrl) != bool(event.ctrl):
                        continue
                    if bool(item.shift) != bool(event.shift):
                        continue
                    if bool(item.alt) != bool(event.alt):
                        continue
                    if bool(item.oskey) != bool(event.oskey):
                        continue

                    action_label = self._action_label(item)
                    key = f"{item.idname}|{action_label}"
                    matches[key] = action_label

        return sorted(matches.values())

    @staticmethod
    def _action_label(item: bpy.types.KeyMapItem) -> str:
        idname = item.idname or ""
        op_name = idname
        if "." in idname:
            category, op_id = idname.split(".", 1)
            op_name = f"{category.title()} {op_id.replace('_', ' ').title()}"

        keymap_name = item.name if item.name else op_name
        return f"{keymap_name} ({idname})"

    @staticmethod
    def _operator_snapshot(wm: bpy.types.WindowManager) -> set[str]:
        return {op.bl_idname for op in wm.operators if getattr(op, "bl_idname", None)}

    def _infer_executed_action(self, wm: bpy.types.WindowManager, previous_ops: set[str], candidates: list[str]) -> str | None:
        new_ops = [op for op in wm.operators if getattr(op, "bl_idname", None) and op.bl_idname not in previous_ops]
        if not new_ops:
            return None

        newest = new_ops[-1]
        bl_idname = newest.bl_idname

        for candidate in candidates:
            if f"({bl_idname})" in candidate:
                return candidate

        return f"{newest.bl_label or bl_idname} ({bl_idname})"

    @staticmethod
    def _print_log(shortcut: str, candidates: list[str], executed: str | None) -> None:
        print(f'Shortcut : "{shortcut}"')
        print("Possible actions :")
        if candidates:
            for action in candidates:
                print(f"  - {action}")
        else:
            print("  - No action found")
        print("Executed action :")
        print(f"  - {executed or 'No match'}")

    @staticmethod
    def _log(message: str) -> None:
        print(f"[ShortcutLogger] {message}")

    @staticmethod
    def _tag_redraw() -> None:
        wm = bpy.context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                area.tag_redraw()


_MANAGER: ShortcutLoggerManager | None = None


def manager() -> ShortcutLoggerManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ShortcutLoggerManager()
    return _MANAGER
