import bpy


_logged_shortcuts = set()
_modal_operator_running = False


_SPECIAL_KEY_LABELS = {
    "SPACE": "Space",
    "RET": "Enter",
    "ESC": "Esc",
    "BACK_SPACE": "Backspace",
    "TAB": "Tab",
    "LEFT_ARROW": "Left",
    "RIGHT_ARROW": "Right",
    "UP_ARROW": "Up",
    "DOWN_ARROW": "Down",
    "PAGE_UP": "PageUp",
    "PAGE_DOWN": "PageDown",
}


def _event_key_label(event_type: str) -> str:
    if event_type in _SPECIAL_KEY_LABELS:
        return _SPECIAL_KEY_LABELS[event_type]
    if len(event_type) == 1:
        return event_type.upper()
    if event_type.startswith("NUMPAD_"):
        return event_type.replace("NUMPAD_", "Numpad ").title()
    return event_type.replace("_", " ").title()


def _shortcut_from_event(event) -> str | None:
    if event.type in {"LEFT_CTRL", "RIGHT_CTRL", "LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_ALT", "RIGHT_ALT"}:
        return None

    parts = []
    if event.ctrl:
        parts.append("Ctrl")
    if event.alt:
        parts.append("Alt")
    if event.shift:
        parts.append("Shift")

    parts.append(_event_key_label(event.type))
    return "+".join(parts)


def _keymap_item_matches_event(kmi, event) -> bool:
    if kmi.type != event.type:
        return False
    if kmi.value not in {"PRESS", "CLICK", "DOUBLE_CLICK", "CLICK_DRAG", "ANY"}:
        return False

    if not kmi.any:
        if bool(kmi.ctrl) != bool(event.ctrl):
            return False
        if bool(kmi.alt) != bool(event.alt):
            return False
        if bool(kmi.shift) != bool(event.shift):
            return False
    return True


def _action_label_from_kmi(kmi) -> str:
    if kmi.name and kmi.name != "None":
        return kmi.name
    if kmi.idname:
        return kmi.idname
    return "Unknown Action"


def _collect_possible_actions(event) -> list[str]:
    actions = []
    seen = set()

    wm = bpy.context.window_manager
    keyconfigs = [wm.keyconfigs.user, wm.keyconfigs.addon, wm.keyconfigs.default]

    for keyconfig in keyconfigs:
        if keyconfig is None:
            continue
        for keymap in keyconfig.keymaps:
            for kmi in keymap.keymap_items:
                if not _keymap_item_matches_event(kmi, event):
                    continue
                action = _action_label_from_kmi(kmi)
                if action in seen:
                    continue
                seen.add(action)
                actions.append(action)

    if not actions:
        actions.append("No action found")
    return actions


def _print_shortcut_block(shortcut: str, actions: list[str]) -> None:
    print(f'Shortcut : "{shortcut}"')
    print("")
    print("Possible actions :")
    for action in actions:
        print(f"- {action}")


class WM_OT_shortcut_listener(bpy.types.Operator):
    bl_idname = "wm.shortcut_listener"
    bl_label = "Shortcut Listener"

    def modal(self, context, event):
        if not _modal_operator_running:
            return {"CANCELLED"}

        if event.value != "PRESS":
            return {"PASS_THROUGH"}

        shortcut = _shortcut_from_event(event)
        if not shortcut:
            return {"PASS_THROUGH"}

        if shortcut in _logged_shortcuts:
            return {"PASS_THROUGH"}

        _logged_shortcuts.add(shortcut)
        actions = _collect_possible_actions(event)
        _print_shortcut_block(shortcut, actions)
        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        del event
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}


classes = (WM_OT_shortcut_listener,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


def start_shortcut_listener(clear_history: bool = False):
    global _modal_operator_running
    if clear_history:
        _logged_shortcuts.clear()
    if _modal_operator_running:
        return
    _modal_operator_running = True
    bpy.ops.wm.shortcut_listener("INVOKE_DEFAULT")


def stop_shortcut_listener():
    global _modal_operator_running
    _modal_operator_running = False


if __name__ == "__main__":
    register()
