# cqf_script_line_ops.py
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from .cqf_config import get_prefs, ensure_default_config, save_config_now
from .cqf_types import sync_script_lines_from_code


def _active_script_item(prefs):
    if not prefs or not prefs.modes:
        return None

    midx = int(getattr(prefs, "active_mode_index", 0))
    if not (0 <= midx < len(prefs.modes)):
        return None
    mode_cfg = prefs.modes[midx]
    if not mode_cfg.sections:
        return None

    sidx = int(getattr(mode_cfg, "active_section_index", 0))
    if not (0 <= sidx < len(mode_cfg.sections)):
        return None
    sec = mode_cfg.sections[sidx]
    if not sec.items:
        return None

    iidx = int(getattr(sec, "active_item_index", 0))
    if not (0 <= iidx < len(sec.items)):
        return None
    it = sec.items[iidx]
    if (it.type or "") != "SCRIPT":
        return None
    return it


def _rebuild_script_code(it):
    it.script_code = "\n".join((ln.text or "") for ln in it.script_lines)
    it.script_lines_cache = it.script_code


class CQF_OT_ScriptLineAdd(Operator):
    bl_idname = "cqf.script_line_add"
    bl_label = "Add Script Line"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        it = _active_script_item(prefs)
        if not it:
            return {'CANCELLED'}

        sync_script_lines_from_code(it)
        idx = int(getattr(it, "active_script_line_index", 0))
        insert_at = max(0, min(idx + 1, len(it.script_lines)))

        it.script_lines.add()
        for i in range(len(it.script_lines) - 1, insert_at, -1):
            it.script_lines[i].text = it.script_lines[i - 1].text
        it.script_lines[insert_at].text = ""

        it.active_script_line_index = insert_at
        _rebuild_script_code(it)
        save_config_now()
        return {'FINISHED'}


class CQF_OT_ScriptLineRemove(Operator):
    bl_idname = "cqf.script_line_remove"
    bl_label = "Remove Script Line"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        it = _active_script_item(prefs)
        if not it:
            return {'CANCELLED'}

        sync_script_lines_from_code(it)
        if not it.script_lines:
            return {'CANCELLED'}

        idx = int(getattr(it, "active_script_line_index", 0))
        if not (0 <= idx < len(it.script_lines)):
            idx = len(it.script_lines) - 1

        it.script_lines.remove(idx)
        if not it.script_lines:
            row = it.script_lines.add()
            row.text = ""
            it.active_script_line_index = 0
        else:
            it.active_script_line_index = max(0, min(idx, len(it.script_lines) - 1))

        _rebuild_script_code(it)
        save_config_now()
        return {'FINISHED'}


class CQF_OT_ScriptLineMove(Operator):
    bl_idname = "cqf.script_line_move"
    bl_label = "Move Script Line"
    bl_options = {'INTERNAL'}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        it = _active_script_item(prefs)
        if not it:
            return {'CANCELLED'}

        sync_script_lines_from_code(it)
        idx = int(getattr(it, "active_script_line_index", 0))
        if not (0 <= idx < len(it.script_lines)):
            return {'CANCELLED'}

        new_idx = idx - 1 if self.direction == "UP" else idx + 1
        if 0 <= new_idx < len(it.script_lines):
            it.script_lines.move(idx, new_idx)
            it.active_script_line_index = new_idx
            _rebuild_script_code(it)
            save_config_now()

        return {'FINISHED'}


class CQF_OT_ScriptFromClipboard(Operator):
    bl_idname = "cqf.script_from_clipboard"
    bl_label = "Paste Script From Clipboard"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        it = _active_script_item(prefs)
        if not it:
            return {'CANCELLED'}

        clip = context.window_manager.clipboard or ""
        it.script_code = clip
        sync_script_lines_from_code(it)
        save_config_now()
        return {'FINISHED'}


class CQF_OT_ScriptToClipboard(Operator):
    bl_idname = "cqf.script_to_clipboard"
    bl_label = "Copy Script To Clipboard"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        it = _active_script_item(prefs)
        if not it:
            return {'CANCELLED'}

        sync_script_lines_from_code(it)
        context.window_manager.clipboard = it.script_code or ""
        self.report({'INFO'}, "Script copied to clipboard")
        return {'FINISHED'}


_CLASSES = (
    CQF_OT_ScriptLineAdd,
    CQF_OT_ScriptLineRemove,
    CQF_OT_ScriptLineMove,
    CQF_OT_ScriptFromClipboard,
    CQF_OT_ScriptToClipboard,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)
