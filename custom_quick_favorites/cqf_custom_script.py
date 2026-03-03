# cqf_custom_script.py
"""
Custom Script items:
- Stored per item as `script_code` (multi-line).
- Executed with a restricted global namespace (no imports).
- Available names inside the script:
    bpy, context (bpy.context), data (bpy.data), ops (bpy.ops)
"""

import ast
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty

from .cqf_config import (
    get_prefs,
    ensure_default_config,
    save_config_now,
    get_mode_key_from_context,
)


# -----------------------------------------------------------------------------
# Minimal helpers (kept here to avoid circular imports)
# -----------------------------------------------------------------------------

def _find_mode_exact(prefs, mode_key: str):
    mk = (mode_key or "").strip().upper()
    for m in prefs.modes:
        if (m.mode_key or "").strip().upper() == mk:
            return m
    return None

def _mode_for_context(prefs, context):
    mk = get_mode_key_from_context(context)
    m = _find_mode_exact(prefs, mk)
    if m:
        return m
    return _find_mode_exact(prefs, "OBJECT") or (prefs.modes[0] if prefs.modes else None)

def _ensure_section_exists(mode_cfg):
    if not mode_cfg:
        return None
    if not mode_cfg.sections:
        s = mode_cfg.sections.add()
        s.title = "Section"
        if hasattr(s, "popup_slot"):
            s.popup_slot = "TOP"
        mode_cfg.active_section_index = 0
        return s
    idx = int(getattr(mode_cfg, "active_section_index", 0))
    idx = max(0, min(idx, len(mode_cfg.sections) - 1))
    mode_cfg.active_section_index = idx
    return mode_cfg.sections[idx]


# -----------------------------------------------------------------------------
# Safe-ish user script execution (no imports, restricted builtins)
# -----------------------------------------------------------------------------

_FORBIDDEN_CALL_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "input", "globals", "locals", "vars",
}

def _has_forbidden_dunder(code: str) -> bool:
    # Block obvious escape hatches
    return "__" in (code or "")

class _UserScriptValidator(ast.NodeVisitor):
    def visit_Import(self, node):  # noqa: N802
        raise ValueError("Imports are not allowed in Custom Script.")
    def visit_ImportFrom(self, node):  # noqa: N802
        raise ValueError("Imports are not allowed in Custom Script.")
    def visit_Global(self, node):  # noqa: N802
        raise ValueError("global is not allowed in Custom Script.")
    def visit_Nonlocal(self, node):  # noqa: N802
        raise ValueError("nonlocal is not allowed in Custom Script.")

    def visit_Call(self, node):  # noqa: N802
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in _FORBIDDEN_CALL_NAMES:
            raise ValueError(f"Forbidden call: {fn.id}()")
        self.generic_visit(node)

def safe_user_script_exec(code: str, context):
    s = (code or "").strip()
    if not s:
        return None

    if _has_forbidden_dunder(s):
        raise ValueError("Custom Script: '__' is not allowed.")

    tree = ast.parse(s, mode="exec")
    _UserScriptValidator().visit(tree)

    safe_builtins = {
        "True": True,
        "False": False,
        "None": None,
        "range": range,
        "len": len,
        "min": min,
        "max": max,
        "abs": abs,
        "sum": sum,
        "print": print,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "tuple": tuple,
        "dict": dict,
        "set": set,
        "enumerate": enumerate,
        "zip": zip,
    }

    g = {
        "__builtins__": safe_builtins,
        "bpy": bpy,
        "context": context if context is not None else bpy.context,
        "data": bpy.data,
        "ops": bpy.ops,
    }

    return exec(compile(tree, filename="<cqf_custom_script>", mode="exec"), g, {})


# -----------------------------------------------------------------------------
# Operator: add a Custom Script item to the active section
# -----------------------------------------------------------------------------

class CQF_OT_ItemAddCustomScript(Operator):
    bl_idname = "cqf.item_add_custom_script"
    bl_label = "Add Custom Script Button"
    bl_options = {'INTERNAL'}

    open_manager: BoolProperty(default=True)

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)

        mode_cfg = _mode_for_context(prefs, context)
        sec = _ensure_section_exists(mode_cfg)
        if not sec:
            return {'CANCELLED'}

        it = sec.items.add()
        it.type = "SCRIPT"
        it.text = "Custom Script"
        it.tooltip = "Run your custom Python snippet (restricted: no imports)."

        if hasattr(it, "script_code"):
            it.script_code = (
                "# Custom Script (no imports)\n"
                "# Available: bpy, context, data, ops\n\n"
                "# Example:\n"
                "# ops.object.mode_set(mode='OBJECT')\n"
            )

        sec.active_item_index = len(sec.items) - 1
        save_config_now()

        if self.open_manager:
            try:
                bpy.ops.cqf.open_manager('INVOKE_DEFAULT')
            except Exception:
                pass

        self.report({'INFO'}, "Added a Custom Script item. Edit its script in Preferences.")
        return {'FINISHED'}