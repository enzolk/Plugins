bl_info = {
    "name": "Blender Shortcut Logger",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Shortcut Logger",
    "description": "Logs used shortcuts and executed actions as a persistent memo table.",
    "category": "Interface",
}

import json
from pathlib import Path

import bpy
from bpy.app.handlers import persistent


_TABLE_FILENAME = "shortcut_table.json"
_modal_operator_running = False
_suspend_auto_save = False

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


def _auto_save_update(self, context):
    del self
    if context is None or _suspend_auto_save:
        return
    _save_table(context)


class BSL_ActionItem(bpy.types.PropertyGroup):
    internal_name: bpy.props.StringProperty(name="Internal")
    display_name: bpy.props.StringProperty(name="Display", update=_auto_save_update)


class BSL_RowItem(bpy.types.PropertyGroup):
    is_separator: bpy.props.BoolProperty(default=False)
    separator_label: bpy.props.StringProperty(name="Separator", default="────────", update=_auto_save_update)
    shortcut: bpy.props.StringProperty(name="Shortcut")
    actions: bpy.props.CollectionProperty(type=BSL_ActionItem)


class BSL_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    enable_listener: bpy.props.BoolProperty(
        name="Enable shortcut listening",
        default=False,
        description="Start/stop the shortcut listener",
        update=lambda self, context: _sync_listener_state(),
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "enable_listener")


class BSL_OT_shortcut_listener(bpy.types.Operator):
    bl_idname = "bsl.shortcut_listener"
    bl_label = "Shortcut Listener"

    def modal(self, context, event):
        if not _modal_operator_running:
            return {"CANCELLED"}

        if event.value != "PRESS":
            return {"PASS_THROUGH"}

        shortcut = _shortcut_from_event(event)
        if not shortcut:
            return {"PASS_THROUGH"}

        possible_entries = _collect_possible_action_entries(event)
        before_signature = _current_execution_signature(context)

        def _delayed_log():
            executed_action = _resolve_executed_action(context, before_signature, possible_entries)
            _upsert_shortcut_action(shortcut, executed_action)
            return None

        bpy.app.timers.register(_delayed_log, first_interval=0.02)
        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        del event
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}


class BSL_UL_rows(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        del context, data, icon, active_data, active_propname, index
        split = layout.split(factor=0.35, align=True)
        if item.is_separator:
            split.label(text="— Separator", icon="REMOVE")
            split.label(text=item.separator_label)
        else:
            action_names = [a.display_name or a.internal_name for a in item.actions]
            actions_text = ", ".join(action_names) if action_names else "(No action)"
            split.label(text=item.shortcut, icon="EVENT_K")
            split.label(text=actions_text)


class BSL_OT_move_row(bpy.types.Operator):
    bl_idname = "bsl.move_row"
    bl_label = "Move Row"

    direction: bpy.props.EnumProperty(items=(("UP", "Up", ""), ("DOWN", "Down", "")))

    def execute(self, context):
        wm = context.window_manager
        idx = wm.bsl_active_row_index
        rows = wm.bsl_rows
        if idx < 0 or idx >= len(rows):
            return {"CANCELLED"}

        new_idx = idx - 1 if self.direction == "UP" else idx + 1
        if new_idx < 0 or new_idx >= len(rows):
            return {"CANCELLED"}

        rows.move(idx, new_idx)
        wm.bsl_active_row_index = new_idx
        _save_table(context)
        return {"FINISHED"}


class BSL_OT_add_separator(bpy.types.Operator):
    bl_idname = "bsl.add_separator"
    bl_label = "Add Separator"

    label: bpy.props.StringProperty(name="Label", default="Separator")

    def execute(self, context):
        wm = context.window_manager
        row = wm.bsl_rows.add()
        row.is_separator = True
        row.separator_label = self.label
        wm.bsl_active_row_index = len(wm.bsl_rows) - 1
        _save_table(context)
        return {"FINISHED"}

    def invoke(self, context, event):
        del event
        return context.window_manager.invoke_props_dialog(self)


class BSL_OT_remove_row(bpy.types.Operator):
    bl_idname = "bsl.remove_row"
    bl_label = "Remove Row"

    def execute(self, context):
        wm = context.window_manager
        idx = wm.bsl_active_row_index
        if idx < 0 or idx >= len(wm.bsl_rows):
            return {"CANCELLED"}
        wm.bsl_rows.remove(idx)
        wm.bsl_active_row_index = min(idx, len(wm.bsl_rows) - 1)
        _save_table(context)
        return {"FINISHED"}


class BSL_PT_panel(bpy.types.Panel):
    bl_label = "Shortcut Logger"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Shortcut Logger"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        prefs = _get_prefs()

        col = layout.column(align=True)
        col.prop(prefs, "enable_listener")

        table = layout.box()
        header = table.row(align=True)
        split = header.split(factor=0.35, align=True)
        split.label(text="Shortcut")
        split.label(text="Executed Actions")
        table.template_list("BSL_UL_rows", "", wm, "bsl_rows", wm, "bsl_active_row_index", rows=8)

        controls = layout.row(align=True)
        op = controls.operator("bsl.move_row", text="Move Up", icon="TRIA_UP")
        op.direction = "UP"
        op = controls.operator("bsl.move_row", text="Move Down", icon="TRIA_DOWN")
        op.direction = "DOWN"
        controls.operator("bsl.add_separator", text="Add Separator", icon="ADD")
        controls.operator("bsl.remove_row", text="Remove", icon="X")

        idx = wm.bsl_active_row_index
        if 0 <= idx < len(wm.bsl_rows):
            item = wm.bsl_rows[idx]
            box = layout.box()
            if item.is_separator:
                box.prop(item, "separator_label", text="Separator Label")
            else:
                box.label(text=f"Shortcut: {item.shortcut}")
                if item.actions:
                    for action in item.actions:
                        box.prop(action, "display_name", text=action.internal_name)
                else:
                    box.label(text="No action logged yet")


def _table_file_path() -> Path:
    return Path(__file__).resolve().parent / _TABLE_FILENAME


def _get_prefs():
    return bpy.context.preferences.addons[__name__].preferences


def _event_key_label(event_type: str) -> str:
    if event_type in _SPECIAL_KEY_LABELS:
        return _SPECIAL_KEY_LABELS[event_type]
    if len(event_type) == 1:
        return event_type.upper()
    if event_type.startswith("NUMPAD_"):
        return event_type.replace("NUMPAD_", "Numpad ").title()
    return event_type.replace("_", " ").title()


def _shortcut_from_event(event):
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
    return " + ".join(parts)


def _modifier_matches(kmi_modifier, event_modifier: bool) -> bool:
    if kmi_modifier == -1:
        return True
    return bool(kmi_modifier) == bool(event_modifier)


def _keymap_item_matches_event(kmi, event) -> bool:
    if kmi.type != event.type:
        return False
    if kmi.value not in {"PRESS", "CLICK", "DOUBLE_CLICK", "CLICK_DRAG", "ANY"}:
        return False

    if not kmi.any:
        if not _modifier_matches(kmi.ctrl, event.ctrl):
            return False
        if not _modifier_matches(kmi.alt, event.alt):
            return False
        if not _modifier_matches(kmi.shift, event.shift):
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


def _normalized(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _mesh_submode_variants(text: str):
    if not text:
        return []

    variants = []
    replacements = {
        "vertex": ["edge", "face"],
        "edge": ["vertex", "face"],
        "face": ["vertex", "edge"],
    }

    lowered = text.lower()
    for source, targets in replacements.items():
        if source not in lowered:
            continue
        for target in targets:
            variant = lowered.replace(source, target)
            if variant != lowered:
                variants.append(variant)

    deduped = []
    seen = set()
    for variant in variants:
        pretty = variant.replace("_", " ").title()
        key = _normalized(pretty)
        if key and key not in seen:
            seen.add(key)
            deduped.append(pretty)
    return deduped


def _indirect_actions_from_kmi(kmi):
    actions = []
    props = getattr(kmi, "properties", None)
    if props is None:
        return actions

    if kmi.idname in {"wm.tool_set_by_id", "wm.tool_set_by_name", "wm.tool_set_by_index"}:
        for attr in ("name", "idname", "tool", "tool_name"):
            value = getattr(props, attr, None)
            if isinstance(value, str) and value.strip():
                pretty = _nice_label_from_identifier(value.strip())
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


def _add_possible_action(entries, seen_labels, label: str, *match_values: str):
    if label in seen_labels:
        return

    match_keys = set()
    for value in match_values:
        if not isinstance(value, str):
            continue
        normalized = _normalized(value)
        if normalized:
            match_keys.add(normalized)

    label_key = _normalized(label)
    if label_key:
        match_keys.add(label_key)

    seen_labels.add(label)
    entries.append({"label": label, "match_keys": match_keys})


def _collect_possible_action_entries(event):
    entries = []
    seen_labels = set()

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
                _add_possible_action(
                    entries,
                    seen_labels,
                    action,
                    action,
                    kmi.idname,
                    _nice_label_from_identifier(kmi.idname),
                )

                for indirect_action in _indirect_actions_from_kmi(kmi):
                    _add_possible_action(
                        entries,
                        seen_labels,
                        indirect_action,
                        indirect_action,
                        kmi.idname,
                        _nice_label_from_identifier(kmi.idname),
                    )

    if bpy.context.mode == "EDIT_MESH":
        for entry in tuple(entries):
            for variant in _mesh_submode_variants(entry["label"]):
                _add_possible_action(entries, seen_labels, variant, variant)

    if not entries:
        _add_possible_action(entries, seen_labels, "No action found")
    return entries


def _current_execution_signature(context):
    wm = context.window_manager
    op_count = len(wm.operators)
    last_operator_signature = ""
    tool_id = ""
    tool_label = ""

    if wm.operators:
        op = wm.operators[-1]
        op_id = getattr(op, "bl_idname", "") or getattr(op, "bl_rna", None) and op.bl_rna.identifier or ""
        op_name = getattr(op, "name", "") or ""
        last_operator_signature = f"{op_id}|{op_name}"

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

    return op_count, last_operator_signature, tool_id, tool_label


def _resolve_executed_action(context, before_signature, possible_entries):
    wm = context.window_manager
    prev_count, prev_last_operator, prev_tool_id, prev_tool_label = before_signature

    candidates = []

    if len(wm.operators) > prev_count or wm.operators:
        op = wm.operators[-1]
        op_id = getattr(op, "bl_idname", "") or getattr(op, "bl_rna", None) and op.bl_rna.identifier or ""
        op_name = getattr(op, "name", "") or ""
        current_signature = f"{op_id}|{op_name}"

        if len(wm.operators) > prev_count or current_signature != prev_last_operator:
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
                    pretty_tool = _nice_label_from_identifier(new_tool_id)
                    candidates.append(pretty_tool)
                    candidates.append(f"{pretty_tool} Tool")

    for cand in candidates:
        ckey = _normalized(cand)
        if not ckey:
            continue
        for entry in possible_entries:
            if ckey in entry["match_keys"]:
                return entry["label"]

    for cand in candidates:
        ckey = _normalized(cand)
        if not ckey:
            continue
        for entry in possible_entries:
            for pkey in entry["match_keys"]:
                if ckey in pkey or pkey in ckey:
                    return entry["label"]

    return "Unknown"


def _upsert_shortcut_action(shortcut: str, executed_action: str):
    context = bpy.context
    wm = context.window_manager

    shortcut_key = (shortcut or "").strip()
    if not shortcut_key:
        return

    internal_key = (executed_action or "").strip() or "Unknown"

    # De-duplicate only exact (shortcut + action) pairs.
    # A known action on a different shortcut must still be logged.
    row = None
    for item in wm.bsl_rows:
        if item.is_separator:
            continue
        if (item.shortcut or "").strip() != shortcut_key:
            continue
        row = item
        for action in item.actions:
            if (action.internal_name or "").strip() == internal_key:
                return
        break

    if row is None:
        row = wm.bsl_rows.add()
        row.shortcut = shortcut_key

    action = row.actions.add()
    action.internal_name = internal_key
    action.display_name = internal_key
    _save_table(context)


def _serialize_rows(context):
    wm = context.window_manager
    payload = []
    for row in wm.bsl_rows:
        if row.is_separator:
            payload.append({"type": "separator", "label": row.separator_label})
            continue
        payload.append(
            {
                "type": "shortcut",
                "shortcut": row.shortcut,
                "actions": [
                    {"internal": action.internal_name, "display": action.display_name}
                    for action in row.actions
                ],
            }
        )
    return payload


def _save_table(context):
    try:
        data = {"rows": _serialize_rows(context)}
        _table_file_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[Blender Shortcut Logger] Failed to save table: {exc}")


def _load_table(context):
    global _suspend_auto_save
    wm = context.window_manager
    _suspend_auto_save = True
    try:
        wm.bsl_rows.clear()
        wm.bsl_active_row_index = -1

        table_path = _table_file_path()
        if not table_path.exists():
            return

        try:
            data = json.loads(table_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[Blender Shortcut Logger] Failed to load table: {exc}")
            return

        for row_data in data.get("rows", []):
            row = wm.bsl_rows.add()
            if row_data.get("type") == "separator":
                row.is_separator = True
                row.separator_label = row_data.get("label", "Separator")
                continue

            row.shortcut = row_data.get("shortcut", "")
            for action_data in row_data.get("actions", []):
                action = row.actions.add()
                action.internal_name = action_data.get("internal", "Unknown")
                action.display_name = action_data.get("display", action.internal_name)

        if len(wm.bsl_rows) > 0:
            wm.bsl_active_row_index = 0
    finally:
        _suspend_auto_save = False


def _start_shortcut_listener():
    global _modal_operator_running
    if _modal_operator_running:
        return
    _modal_operator_running = True
    bpy.ops.bsl.shortcut_listener("INVOKE_DEFAULT")


def _stop_shortcut_listener():
    global _modal_operator_running
    _modal_operator_running = False


def _sync_listener_state():
    try:
        prefs = _get_prefs()
    except Exception:
        return

    if prefs.enable_listener:
        _start_shortcut_listener()
    else:
        _stop_shortcut_listener()


@persistent
def _on_load_post(dummy):
    del dummy
    _load_table(bpy.context)
    _sync_listener_state()


classes = (
    BSL_ActionItem,
    BSL_RowItem,
    BSL_AddonPreferences,
    BSL_OT_shortcut_listener,
    BSL_UL_rows,
    BSL_OT_move_row,
    BSL_OT_add_separator,
    BSL_OT_remove_row,
    BSL_PT_panel,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.bsl_rows = bpy.props.CollectionProperty(type=BSL_RowItem)
    bpy.types.WindowManager.bsl_active_row_index = bpy.props.IntProperty(default=-1)

    _load_table(bpy.context)

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    bpy.app.timers.register(_sync_listener_state, first_interval=0.2)


def unregister():
    _stop_shortcut_listener()

    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    del bpy.types.WindowManager.bsl_rows
    del bpy.types.WindowManager.bsl_active_row_index

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
