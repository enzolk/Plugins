# cqf_custom_script.py
import bpy
from bpy.types import Operator

from .cqf_config import get_prefs, ensure_default_config, save_config_now


def run_custom_script(script_source: str, context=None):
    src = (script_source or "").strip()
    if not src:
        raise ValueError("Empty custom script.")

    ctx = context if context is not None else bpy.context

    safe_globals = {
        "__builtins__": __builtins__,
        "bpy": bpy,
        "context": ctx,
        "C": ctx,
    }
    safe_locals = {}
    exec(src, safe_globals, safe_locals)


def _active_mode(prefs):
    if not prefs or not prefs.modes:
        return None
    idx = int(getattr(prefs, "active_mode_index", 0))
    if 0 <= idx < len(prefs.modes):
        return prefs.modes[idx]
    return prefs.modes[0]


def _active_section(mode_cfg):
    if not mode_cfg or not mode_cfg.sections:
        return None
    idx = int(getattr(mode_cfg, "active_section_index", 0))
    if 0 <= idx < len(mode_cfg.sections):
        return mode_cfg.sections[idx]
    return mode_cfg.sections[0]


def _ensure_section_exists(mode_cfg):
    if not mode_cfg:
        return None
    if not mode_cfg.sections:
        s = mode_cfg.sections.add()
        s.title = "Section"
        mode_cfg.active_section_index = 0
    return _active_section(mode_cfg)


class CQF_OT_ItemAddCustomScript(Operator):
    bl_idname = "cqf.item_add_custom_script"
    bl_label = "Add Custom Script Button"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)

        mode_cfg = _active_mode(prefs)
        sec = _active_section(mode_cfg)
        if not sec:
            sec = _ensure_section_exists(mode_cfg)
        if not sec:
            return {'CANCELLED'}

        it = sec.items.add()
        it.type = "SCRIPT"
        it.text = "Custom Script"
        it.tooltip = "Run a custom Python script"
        it.script_code = "# Example:\n# bpy.ops.object.shade_smooth()\n"

        sec.active_item_index = len(sec.items) - 1
        save_config_now()
        return {'FINISHED'}


_CLASSES = (
    CQF_OT_ItemAddCustomScript,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)

