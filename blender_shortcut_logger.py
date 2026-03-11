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

        before_signature = _current_execution_signature(context)

        def _delayed_log():
            executed_action = _resolve_executed_action(context, before_signature, actions)
            _print_shortcut_block(shortcut, actions, executed_action)
            return None

        bpy.app.timers.register(_delayed_log, first_interval=0.02)
        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        del event
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}


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


def _nice_label_from_identifier(identifier: str) -> str:
    if not identifier:
        return ""

    token = identifier.split(".")[-1]
    return token.replace("_", " ").title().strip()


def _indirect_actions_from_kmi(kmi) -> list[str]:
    actions = []
    props = getattr(kmi, "properties", None)
    if props is None:
        return actions

    if kmi.idname in {"wm.tool_set_by_id", "wm.tool_set_by_name", "wm.tool_set_by_index"}:
        prop_candidates = []
        for attr in ("name", "idname", "tool", "tool_name"):
            value = getattr(props, attr, None)
            if isinstance(value, str) and value.strip():
                prop_candidates.append(value.strip())

        for candidate in prop_candidates:
            pretty = _nice_label_from_identifier(candidate)
            if pretty:
                actions.append(f"{pretty} Tool")

    rna = getattr(props, "bl_rna", None)
    if rna is None:
        return actions

    rna_props = getattr(rna, "properties", None)
    if rna_props is None:
        return actions

    for prop_name in rna_props.keys():
        if prop_name == "rna_type":
            continue
        value = getattr(props, prop_name, None)
        if not isinstance(value, str):
            continue
        val = value.strip()
        if not val:
            continue

        pretty = _nice_label_from_identifier(val)
        if pretty and pretty.lower() not in {"none", "unknown"}:
            actions.append(pretty)

    return actions


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
                if action not in seen:
                    seen.add(action)
                    actions.append(action)

                for indirect_action in _indirect_actions_from_kmi(kmi):
                    if indirect_action in seen:
                        continue
                    seen.add(indirect_action)
                    actions.append(indirect_action)

    if not actions:
        actions.append("No action found")
    return actions


def _normalized(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _current_execution_signature(context):
    wm = context.window_manager
    op_count = len(wm.operators)
    tool_id = ""
    tool_label = ""

    ws = context.workspace
    if ws:
        mode = context.mode if context.mode else "OBJECT"
        try:
            tool = ws.tools.from_space_view3d_mode(mode, create=False)
        except Exception:
            tool = None
        if tool:
            tool_id = getattr(tool, "idname", "") or ""
            tool_label = getattr(tool, "label", "") or ""

    return op_count, tool_id, tool_label


def _resolve_executed_action(context, before_signature, possible_actions):
    wm = context.window_manager
    prev_count, prev_tool_id, prev_tool_label = before_signature

    candidates = []

    if len(wm.operators) > prev_count:
        op = wm.operators[-1]
        op_id = getattr(op, "bl_idname", "") or getattr(op, "bl_rna", None) and op.bl_rna.identifier or ""
        op_name = getattr(op, "name", "") or ""
        if op_name:
            candidates.append(op_name)
        if op_id:
            candidates.append(op_id)
            candidates.append(_nice_label_from_identifier(op_id))

    ws = context.workspace
    if ws:
        mode = context.mode if context.mode else "OBJECT"
        try:
            tool = ws.tools.from_space_view3d_mode(mode, create=False)
        except Exception:
            tool = None
        if tool:
            new_tool_id = getattr(tool, "idname", "") or ""
            new_tool_label = getattr(tool, "label", "") or ""
            if new_tool_id != prev_tool_id or new_tool_label != prev_tool_label:
                if new_tool_label:
                    candidates.append(new_tool_label)
                    candidates.append(f"{new_tool_label} Tool")
                if new_tool_id:
                    candidates.append(_nice_label_from_identifier(new_tool_id))
                    candidates.append(f"{_nice_label_from_identifier(new_tool_id)} Tool")

    normalized_possible = {_normalized(action): action for action in possible_actions}
    for cand in candidates:
        key = _normalized(cand)
        if key in normalized_possible:
            return normalized_possible[key]

    for cand in candidates:
        ckey = _normalized(cand)
        for pkey, action in normalized_possible.items():
            if ckey and (ckey in pkey or pkey in ckey):
                return action

    return "Unknown"


def _print_shortcut_block(shortcut: str, actions: list[str], executed_action: str) -> None:
    print(f'Shortcut : "{shortcut}"')
    print("")
    print("Possible actions :")
    for action in actions:
        print(f"- {action}")
    print("")
    print(f'Executed action : "{executed_action}"')


classes = (WM_OT_shortcut_listener,)


def register():
    for cls in classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


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
    start_shortcut_listener()
