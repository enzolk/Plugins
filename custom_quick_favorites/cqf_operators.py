# cqf_operators.py
import re
import bpy
from bpy.types import Operator, Menu
from bpy.props import IntProperty, BoolProperty, EnumProperty, StringProperty

from .cqf_safe import safe_eval, safe_exec
from .cqf_ops_helpers import (
    try_copy_python_command_button,
    op_idname_from_button_operator,
    build_op_expr_from_keymap_item,
    remove_capture_combo_everywhere,
    find_capture_combo_kmi,
)
from .cqf_prop_helpers import (
    normalize_datapath,
    resolve_owner_for_prop,
    guess_prop_action_and_value,
    get_rna_prop,
    enum_items_keys,
    is_enum_flag,
    cycle_enum,
    parse_enum_flag_value,
    enum_flag_current_to_text,
)
from .cqf_config import (
    get_prefs,
    get_mode_key_from_context,
    ensure_default_config,
    load_config_into_prefs,
    save_config_now,
)
from . import cqf_search

from .cqf_types import CQF_UL_Modes, CQF_UL_Sections, CQF_UL_Items


# -----------------------------------------------------------------------------
# Friendly label helpers (auto-fill item text + tooltip)
# -----------------------------------------------------------------------------

_OPS_RE = re.compile(r"\bbpy\.ops\.([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*\(")


def _op_id_from_expr(expr: str):
    try:
        s = (expr or "").strip()
        m = _OPS_RE.search(s)
        if not m:
            return ""
        return f"{m.group(1).lower()}.{m.group(2).lower()}"
    except Exception:
        return ""


def _get_op_rna(op_idname: str):
    """
    More reliable than bpy.types.*.bl_description for many operators.
    """
    if not op_idname or "." not in op_idname:
        return None
    try:
        cat, name = op_idname.split(".", 1)
        ops_cat = getattr(bpy.ops, cat, None)
        if ops_cat is None:
            return None
        op_fn = getattr(ops_cat, name, None)
        if op_fn is None:
            return None
        return op_fn.get_rna_type()
    except Exception:
        return None


def _op_classname_from_idname(op_idname: str):
    """
    'object.mode_set' -> 'OBJECT_OT_mode_set'
    """
    try:
        if not op_idname or "." not in op_idname:
            return None
        mod, op = op_idname.split(".", 1)
        return f"{mod.upper()}_OT_{op}"
    except Exception:
        return None


def _friendly_label_for_operator(op_idname: str, fallback: str = "Operator"):
    """
    Prefer RNA name (like old script), fallback to bpy.types class bl_label, then idname.
    """
    try:
        op_id = (op_idname or "").strip()
        if not op_id:
            return fallback

        rna = _get_op_rna(op_id)
        if rna:
            nm = (getattr(rna, "name", "") or "").strip()
            if nm:
                return nm

        cls_name = _op_classname_from_idname(op_id)
        if cls_name and hasattr(bpy.types, cls_name):
            cls = getattr(bpy.types, cls_name, None)
            lab = (getattr(cls, "bl_label", "") or "").strip()
            if lab:
                return lab

        return op_id
    except Exception:
        return op_idname or fallback


def _friendly_tooltip_for_operator(op_idname: str):
    """
    Prefer RNA description (like old script), fallback to class bl_description.
    """
    try:
        op_id = (op_idname or "").strip()
        if not op_id:
            return ""

        rna = _get_op_rna(op_id)
        if rna:
            desc = (getattr(rna, "description", "") or "").strip()
            if desc:
                return desc

        cls_name = _op_classname_from_idname(op_id)
        if cls_name and hasattr(bpy.types, cls_name):
            cls = getattr(bpy.types, cls_name, None)
            desc = (getattr(cls, "bl_description", "") or "").strip()
            return desc
    except Exception:
        pass
    return ""


def _friendly_label_for_menu(menu_idname: str, fallback: str = "Menu"):
    try:
        if menu_idname and hasattr(bpy.types, menu_idname):
            cls = getattr(bpy.types, menu_idname, None)
            lab = (getattr(cls, "bl_label", "") or "").strip()
            if lab:
                return lab
        if menu_idname:
            return menu_idname
    except Exception:
        pass
    return fallback


def _friendly_tooltip_for_menu(menu_idname: str):
    try:
        if menu_idname and hasattr(bpy.types, menu_idname):
            cls = getattr(bpy.types, menu_idname, None)
            desc = (getattr(cls, "bl_description", "") or "").strip()
            return desc
    except Exception:
        pass
    return ""


def _friendly_owner_tag(owner_expr: str):
    s = (owner_expr or "").strip()
    if "space_data.overlay" in s:
        return "Overlay"
    if "space_data.shading" in s:
        return "Shading"
    if "tool_settings" in s:
        return "Tool Settings"
    if s.endswith("scene"):
        return "Scene"
    if s.endswith("view_layer"):
        return "View Layer"
    if s.endswith("preferences"):
        return "Preferences"
    if s.endswith("window_manager"):
        return "Window Manager"
    if s.endswith("object") or s.endswith("active_object"):
        return "Object"
    try:
        return s.split(".")[-1].replace("_", " ").title()
    except Exception:
        return ""


def _friendly_label_and_tooltip_for_property(owner_expr: str, prop_id: str):
    try:
        owner = None
        try:
            owner = safe_eval(owner_expr)
        except Exception:
            owner = None

        if owner is None or not hasattr(owner, prop_id):
            resolved = resolve_owner_for_prop(prop_id)
            if resolved:
                owner_expr = resolved
                try:
                    owner = safe_eval(owner_expr)
                except Exception:
                    owner = None

        rna_prop = get_rna_prop(owner, prop_id) if owner is not None else None
        pname = ""
        pdesc = ""

        if rna_prop is not None:
            pname = (getattr(rna_prop, "name", "") or "").strip()
            pdesc = (getattr(rna_prop, "description", "") or "").strip()

        base = pname if pname else (prop_id or "Property")
        tag = _friendly_owner_tag(owner_expr)
        label = f"{tag}: {base}" if tag else base
        return (label, pdesc)
    except Exception:
        return (prop_id or "Property", "")


# -----------------------------------------------------------------------------
# Helpers (active mode/section/item)
# -----------------------------------------------------------------------------

def _active_mode(prefs):
    if not prefs or not prefs.modes:
        return None
    idx = int(getattr(prefs, "active_mode_index", 0))
    if 0 <= idx < len(prefs.modes):
        return prefs.modes[idx]
    return prefs.modes[0]


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


def _active_section(mode_cfg):
    if not mode_cfg or not mode_cfg.sections:
        return None
    idx = int(getattr(mode_cfg, "active_section_index", 0))
    if 0 <= idx < len(mode_cfg.sections):
        return mode_cfg.sections[idx]
    return mode_cfg.sections[0]


def _active_item(section):
    if not section or not section.items:
        return None
    idx = int(getattr(section, "active_item_index", 0))
    if 0 <= idx < len(section.items):
        return section.items[idx]
    return section.items[0]


def _ensure_section_exists(mode_cfg):
    if not mode_cfg:
        return None
    if not mode_cfg.sections:
        s = mode_cfg.sections.add()
        s.title = "Section"
        mode_cfg.active_section_index = 0
    return _active_section(mode_cfg)


# -----------------------------------------------------------------------------
# Manual capture (Ctrl+Alt+Shift+9)
# -----------------------------------------------------------------------------

class CQF_OT_ManualCapture(Operator):
    bl_idname = "cqf.manual_capture"
    bl_label = "Manual UI Shortcut Capture"
    bl_options = {'INTERNAL'}

    _timer = None
    running: BoolProperty(default=False)

    def invoke(self, context, event):
        remove_capture_combo_everywhere()
        self.running = True
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.25, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not self.running:
            return {'CANCELLED'}

        if event.type == 'TIMER':
            kmi = find_capture_combo_kmi()
            if kmi:
                op_expr = build_op_expr_from_keymap_item(kmi) or ""
                op_id = getattr(kmi, "idname", "") or ""

                if not op_id and op_expr:
                    op_id = _op_id_from_expr(op_expr)

                prefs = get_prefs()
                ensure_default_config(prefs)
                mode_cfg = _mode_for_context(prefs, context)
                sec = _ensure_section_exists(mode_cfg)

                it = sec.items.add()
                it.type = "OP"
                it.op_expr = op_expr
                it.op_idname = op_id

                it.text = _friendly_label_for_operator(op_id, fallback="Captured Operator")
                it.tooltip = _friendly_tooltip_for_operator(op_id)

                sec.active_item_index = len(sec.items) - 1
                save_config_now()

                remove_capture_combo_everywhere()
                self._stop(context)
                self.report({'INFO'}, "Captured and added to Custom Quick Favorites.")
                return {'FINISHED'}

        if event.type in {'ESC'}:
            remove_capture_combo_everywhere()
            self._stop(context)
            self.report({'INFO'}, "Manual capture cancelled.")
            return {'CANCELLED'}

        return {'PASS_THROUGH'}

    def _stop(self, context):
        wm = context.window_manager
        if self._timer is not None:
            try:
                wm.event_timer_remove(self._timer)
            except Exception:
                pass
            self._timer = None
        self.running = False

    def cancel(self, context):
        remove_capture_combo_everywhere()
        self._stop(context)


class CQF_OT_StopManualCapture(Operator):
    bl_idname = "cqf.stop_manual_capture"
    bl_label = "Stop assigning the UI element"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        remove_capture_combo_everywhere()
        context.window_manager.cqf_manual_capture_active = False
        self.report({'INFO'}, "Stopped manual capture.")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Manual search add
# -----------------------------------------------------------------------------

class CQF_OT_AddFromSearch(Operator):
    bl_idname = "cqf.add_from_search"
    bl_label = "Add from Search"
    bl_options = {'INTERNAL'}

    enum_id: StringProperty(default="")

    def execute(self, context):
        it = cqf_search.get_item_by_enum_id(self.enum_id)
        if not it:
            self.report({'WARNING'}, "No action selected.")
            return {'CANCELLED'}

        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _mode_for_context(prefs, context)
        sec = _ensure_section_exists(mode_cfg)

        new = sec.items.add()

        if it["kind"] == "EXPR":
            expr = (it["payload"].get("op_expr", "") or "").strip()
            if not expr.startswith("bpy.ops."):
                sec.items.remove(len(sec.items) - 1)
                self.report({'ERROR'}, "Invalid EXPR payload.")
                return {'CANCELLED'}

            new.type = "OP"
            new.op_expr = expr
            new.op_idname = _op_id_from_expr(expr) or ""
            new.text = (it.get("label", "") or "Expression").strip()
            new.tooltip = ""
            sec.active_item_index = len(sec.items) - 1
            save_config_now()
            self.report({'INFO'}, f"Added: {new.text}")
            return {'FINISHED'}

        if it["kind"] == "OP":
            op_id = it["payload"].get("op_idname", "")
            new.type = "OP"
            new.op_idname = op_id
            new.op_expr = f"bpy.ops.{op_id}('INVOKE_DEFAULT')"
            new.text = _friendly_label_for_operator(op_id, fallback=op_id or "Operator")
            new.tooltip = _friendly_tooltip_for_operator(op_id)

        elif it["kind"] == "MENU":
            menu_id = it["payload"].get("menu_idname", "")
            new.type = "MENU"
            new.menu_idname = menu_id
            new.menu_call = it["payload"].get("call", "call_menu")
            new.text = _friendly_label_for_menu(menu_id, fallback=menu_id or "Menu")
            new.tooltip = _friendly_tooltip_for_menu(menu_id)

        elif it["kind"] == "PROP":
            owner_expr = it["payload"].get("owner_expr", "")
            prop_id = it["payload"].get("prop_id", "")

            new.type = "PROP"
            new.owner_expr = owner_expr
            new.prop_id = prop_id

            lab, tip = _friendly_label_and_tooltip_for_property(owner_expr, prop_id)
            new.text = lab
            new.tooltip = tip

            owner = None
            try:
                owner = safe_eval(owner_expr)
            except Exception:
                owner = None

            if owner is not None and hasattr(owner, prop_id):
                act, val = guess_prop_action_and_value(owner, prop_id)
                new.prop_action = act
                new.prop_value = val

                rna_prop = get_rna_prop(owner, prop_id)
                if rna_prop and getattr(rna_prop, "type", None) == "ENUM" and is_enum_flag(rna_prop):
                    new.prop_action = "SET"
                    new.prop_value = enum_flag_current_to_text(getattr(owner, prop_id))
            else:
                new.prop_action = "SET"
                new.prop_value = ""

        else:
            sec.items.remove(len(sec.items) - 1)
            self.report({'ERROR'}, "Unsupported action kind.")
            return {'CANCELLED'}

        sec.active_item_index = len(sec.items) - 1
        save_config_now()
        self.report({'INFO'}, f"Added: {new.text}")
        return {'FINISHED'}


class CQF_OT_AskManualAdd(Operator):
    bl_idname = "cqf.ask_manual_add"
    bl_label = "Manual Add (Search / Capture)"
    bl_options = {'INTERNAL'}

    search_query: StringProperty(
        name="Search",
        description="Type words like: snap vertex / snap grid / add modifier / wireframe / menu / overlay / engine ...",
        default="",
    )
    search_result: EnumProperty(
        name="Results",
        items=cqf_search.enum_items_callback,
    )

    def invoke(self, context, event):
        try:
            cqf_search.build_cache()
        except Exception:
            pass

        try:
            items = cqf_search.enum_items_callback(self, context)
            if items:
                self.search_result = items[0][0]
        except Exception:
            pass

        return context.window_manager.invoke_props_dialog(self, width=820)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Manual Add", icon="VIEWZOOM")
        layout.separator()

        box2 = layout.box()
        box2.label(text="Method A — Search (Smart Enums + Operators + Menus + Properties)", icon="VIEWZOOM")
        box2.prop(self, "search_query", text="Search")
        box2.prop(self, "search_result", text="Match")

        row = box2.row(align=True)
        op = row.operator("cqf.add_from_search", text="Add selected to active section", icon="ADD")
        op.enum_id = self.search_result

        layout.separator()

        box = layout.box()
        box.label(text="Method B — Ctrl+Alt+Shift+9 (Assign Shortcut)", icon="KEYINGSET")
        box.label(text="Steps:")
        box.label(text="1) We'll clear Ctrl+Alt+Shift+9 shortcuts")
        box.label(text="2) You assign Ctrl+Alt+Shift+9 to the UI element (Right-click → Assign Shortcut)")
        box.label(text="3) We'll detect it, add it to the active section")
        box.label(text="4) We'll clear Ctrl+Alt+Shift+9 again")
        box.label(text="Stop anytime: use 'Stop assigning the UI element' in Preferences", icon="INFO")

    def execute(self, context):
        context.window_manager.cqf_manual_capture_active = True
        bpy.ops.cqf.manual_capture('INVOKE_DEFAULT')
        self.report({'INFO'}, "Assign Ctrl+Alt+Shift+9 to the desired UI element now.")
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Run Item
# -----------------------------------------------------------------------------

class CQF_OT_RunItem(Operator):
    bl_idname = "cqf.run_item"
    bl_label = "Run Item"
    bl_options = {'INTERNAL'}

    mode_key: StringProperty(default="OBJECT")
    section_index: IntProperty(default=0)
    item_index: IntProperty(default=0)

    @classmethod
    def description(cls, context, properties):
        try:
            prefs = get_prefs()
            m = _find_mode_exact(prefs, properties.mode_key)
            if not m:
                return cls.bl_description
            if not (0 <= properties.section_index < len(m.sections)):
                return cls.bl_description
            s = m.sections[properties.section_index]
            if not (0 <= properties.item_index < len(s.items)):
                return cls.bl_description
            it = s.items[properties.item_index]
            tip = (it.tooltip or "").strip()
            return tip if tip else cls.bl_description
        except Exception:
            return cls.bl_description

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)

        m = _find_mode_exact(prefs, self.mode_key)
        if not m:
            return {'CANCELLED'}
        if not (0 <= self.section_index < len(m.sections)):
            return {'CANCELLED'}
        s = m.sections[self.section_index]
        if not (0 <= self.item_index < len(s.items)):
            return {'CANCELLED'}
        it = s.items[self.item_index]

        if it.type == "SEP":
            return {'FINISHED'}

        try:
            if it.type == "OP":
                expr = (it.op_expr or "").strip()
                if expr.startswith("bpy.ops."):
                    safe_exec(expr)
                    return {'FINISHED'}

                op_id = (it.op_idname or "").strip()
                if op_id and "." in op_id:
                    mod, op = op_id.split(".", 1)
                    fn = getattr(getattr(bpy.ops, mod), op)
                    fn('INVOKE_DEFAULT')
                    return {'FINISHED'}

                self.report({'WARNING'}, "Operator item missing op_expr/op_idname.")
                return {'CANCELLED'}

            if it.type == "MENU":
                mid = (it.menu_idname or "").strip()
                if not mid:
                    self.report({'WARNING'}, "Menu item missing menu_idname.")
                    return {'CANCELLED'}
                if it.menu_call == "call_menu_pie":
                    bpy.ops.wm.call_menu_pie(name=mid)
                else:
                    bpy.ops.wm.call_menu(name=mid)
                return {'FINISHED'}

            owner = None
            try:
                owner = safe_eval(it.owner_expr)
            except Exception:
                owner = None

            if owner is None or not hasattr(owner, it.prop_id):
                resolved = resolve_owner_for_prop(it.prop_id)
                if resolved:
                    it.owner_expr = resolved
                    try:
                        owner = safe_eval(resolved)
                    except Exception:
                        owner = None

            if owner is None:
                self.report({'WARNING'}, f"Property owner not available now (prop: {it.prop_id}).")
                return {'CANCELLED'}

            if not hasattr(owner, it.prop_id):
                self.report({'WARNING'}, f"Property not available now: {it.prop_id} (owner: {it.owner_expr})")
                return {'CANCELLED'}

            cur = getattr(owner, it.prop_id)
            rna_prop = get_rna_prop(owner, it.prop_id)
            raw = (it.prop_value or "").strip()

            if it.prop_action == "TOGGLE":
                if isinstance(cur, bool):
                    setattr(owner, it.prop_id, not cur)
                    return {'FINISHED'}
                self.report({'WARNING'}, "Toggle only works on boolean properties. Use SET.")
                return {'CANCELLED'}

            if raw == "":
                if isinstance(cur, bool):
                    setattr(owner, it.prop_id, not cur)
                    return {'FINISHED'}

                if rna_prop and getattr(rna_prop, "type", None) == "ENUM" and not is_enum_flag(rna_prop):
                    cycle_enum(owner, it.prop_id, rna_prop)
                    return {'FINISHED'}

                if rna_prop and getattr(rna_prop, "type", None) == "ENUM" and is_enum_flag(rna_prop):
                    self.report({'WARNING'}, "Enum-flag needs a value. Set prop_value in Preferences.")
                    return {'CANCELLED'}

                self.report({'WARNING'}, "SET mode but empty value. Set a value in Preferences.")
                return {'CANCELLED'}

            if rna_prop and getattr(rna_prop, "type", None) == "ENUM":
                keys = enum_items_keys(rna_prop)

                if is_enum_flag(rna_prop):
                    try:
                        vset = parse_enum_flag_value(raw, cur, keys)
                    except Exception as e:
                        self.report({'ERROR'}, f"Invalid enum-flag value '{raw}': {e}")
                        return {'CANCELLED'}
                    setattr(owner, it.prop_id, vset)
                    return {'FINISHED'}

                if raw not in keys:
                    self.report({'ERROR'}, f"Enum '{raw}' not in {tuple(keys)}")
                    return {'CANCELLED'}
                setattr(owner, it.prop_id, raw)
                return {'FINISHED'}

            try:
                if isinstance(cur, bool):
                    v = raw.lower() in {"1", "true", "yes", "y", "on"}
                elif isinstance(cur, int):
                    v = int(float(raw))
                elif isinstance(cur, float):
                    v = float(raw)
                else:
                    v = raw
            except Exception:
                self.report({'ERROR'}, f"Invalid value '{raw}' for property type {type(cur).__name__}")
                return {'CANCELLED'}

            setattr(owner, it.prop_id, v)
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, f"Failed: {e}")
            return {'CANCELLED'}


# -----------------------------------------------------------------------------
# Right-click auto add
# -----------------------------------------------------------------------------

class CQF_OT_AddFromButtonContext(Operator):
    bl_idname = "cqf.add_from_button_context"
    bl_label = "Add to Custom Quick Favorites"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _mode_for_context(prefs, context)
        sec = _ensure_section_exists(mode_cfg)

        op_expr = try_copy_python_command_button(context)
        button_op = getattr(context, "button_operator", None)
        op_id = op_idname_from_button_operator(button_op) or ""

        if (not op_id) and op_expr:
            op_id = _op_id_from_expr(op_expr)

        if op_expr or op_id:
            it = sec.items.add()
            it.type = "OP"
            it.op_expr = op_expr or ""
            it.op_idname = op_id or ""

            it.text = _friendly_label_for_operator(op_id, fallback=(op_id or "Operator"))
            it.tooltip = _friendly_tooltip_for_operator(op_id)

            sec.active_item_index = len(sec.items) - 1
            save_config_now()
            return {'FINISHED'}

        raw_path = None
        try:
            bpy.ops.ui.copy_data_path_button()
            raw_path = context.window_manager.clipboard
        except Exception:
            raw_path = None

        if raw_path:
            norm = normalize_datapath(raw_path)

            owner_expr = None
            prop_id = None

            if norm and norm.startswith("bpy.") and "." in norm:
                owner_expr, prop_id = norm.rsplit(".", 1)

            if norm and "." not in norm and not norm.startswith("bpy."):
                prop_id = norm
                owner_expr = resolve_owner_for_prop(prop_id)

            owner = None
            if owner_expr and prop_id:
                try:
                    owner = safe_eval(owner_expr)
                except Exception:
                    owner = None

                if owner is None or not hasattr(owner, prop_id):
                    resolved = resolve_owner_for_prop(prop_id)
                    if resolved:
                        owner_expr = resolved
                        try:
                            owner = safe_eval(owner_expr)
                        except Exception:
                            owner = None

            if owner_expr and prop_id:
                it = sec.items.add()
                it.type = "PROP"
                it.owner_expr = owner_expr
                it.prop_id = prop_id

                lab, tip = _friendly_label_and_tooltip_for_property(owner_expr, prop_id)
                it.text = lab
                it.tooltip = tip

                if owner is not None and hasattr(owner, prop_id):
                    act, val = guess_prop_action_and_value(owner, prop_id)
                    it.prop_action = act
                    it.prop_value = val

                    rna_prop = get_rna_prop(owner, prop_id)
                    if rna_prop and getattr(rna_prop, "type", None) == "ENUM" and is_enum_flag(rna_prop):
                        it.prop_action = "SET"
                        it.prop_value = enum_flag_current_to_text(getattr(owner, prop_id))
                else:
                    it.prop_action = "SET"
                    it.prop_value = ""

                sec.active_item_index = len(sec.items) - 1
                save_config_now()
                return {'FINISHED'}

        bpy.ops.cqf.ask_manual_add('INVOKE_DEFAULT')
        return {'CANCELLED'}


def cqf_draw_button_context(self, context):
    layout = self.layout
    layout.separator()
    layout.operator("cqf.add_from_button_context", icon="BOOKMARKS")


# -----------------------------------------------------------------------------
# Manager UI + Menu Q
# -----------------------------------------------------------------------------

class CQF_OT_OpenManager(Operator):
    bl_idname = "cqf.open_manager"
    bl_label = "Custom Quick Favorites Manager"

    def execute(self, context):
        return bpy.ops.cqf.manager_popup('INVOKE_DEFAULT')


class CQF_OT_ManagerPopup(Operator):
    bl_idname = "cqf.manager_popup"
    bl_label = "Custom Quick Favorites"

    def invoke(self, context, event):
        prefs = get_prefs()
        ensure_default_config(prefs)
        return context.window_manager.invoke_props_dialog(self, width=1080)

    def draw(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)

        layout = self.layout

        box = layout.box()
        box.label(text="Manual Add", icon="KEYINGSET")
        row = box.row(align=True)
        row.operator("cqf.ask_manual_add", text="Manual Add (Search / Capture)…", icon="VIEWZOOM")
        row.operator("cqf.stop_manual_capture", text="Stop assigning the UI element", icon="CANCEL")

        layout.separator()

        row = layout.row()
        col_left = row.column()
        col_mid = row.column()
        col_right = row.column()

        col_left.label(text="Modes (fixed)")
        col_left.template_list("CQF_UL_Modes", "", prefs, "modes", prefs, "active_mode_index", rows=8)
        col_left.label(text="(Cannot rename / delete)", icon="INFO")

        mode_cfg = _active_mode(prefs)
        if not mode_cfg:
            col_mid.label(text="No mode config.")
            return

        col_mid.label(text=f"Sections — {mode_cfg.mode_key}")
        col_mid.template_list("CQF_UL_Sections", "", mode_cfg, "sections", mode_cfg, "active_section_index", rows=8)

        sec_ops = col_mid.row(align=True)
        sec_ops.operator("cqf.section_add", text="", icon="ADD")
        sec_ops.operator("cqf.section_remove", text="", icon="REMOVE")
        sec_ops.operator("cqf.section_move", text="", icon="TRIA_UP").direction = "UP"
        sec_ops.operator("cqf.section_move", text="", icon="TRIA_DOWN").direction = "DOWN"

        sec = _active_section(mode_cfg)
        if not sec:
            col_right.label(text="Add a section.")
            return

        col_right.label(text="Items")
        col_right.template_list("CQF_UL_Items", "", sec, "items", sec, "active_item_index", rows=10)

        item_ops = col_right.row(align=True)
        item_ops.operator("cqf.item_add_separator", text="Add Separator", icon="REMOVE")
        item_ops.operator("cqf.ask_manual_add", text="Manual Add…", icon="VIEWZOOM")

        item_ops2 = col_right.row(align=True)
        item_ops2.operator("cqf.item_remove", text="Remove", icon="TRASH")
        item_ops2.operator("cqf.item_move", text="", icon="TRIA_UP").direction = "UP"
        item_ops2.operator("cqf.item_move", text="", icon="TRIA_DOWN").direction = "DOWN"

        it = _active_item(sec)
        if it:
            box2 = col_right.box()
            box2.label(text="Selected Item Settings")
            box2.prop(it, "type", text="Type")

            if it.type == "SEP":
                box2.label(text="Separator has no settings.", icon="INFO")
            else:
                box2.prop(it, "text", text="Button Text")
                box2.prop(it, "tooltip", text="Tooltip")

                if it.type == "OP":
                    box2.prop(it, "op_idname")
                    box2.prop(it, "op_expr")
                    box2.label(text="Tip: op_expr preserves arguments.", icon="INFO")
                elif it.type == "MENU":
                    box2.prop(it, "menu_idname")
                    box2.prop(it, "menu_call")
                elif it.type == "PROP":
                    box2.prop(it, "owner_expr")
                    box2.prop(it, "prop_id")
                    box2.prop(it, "prop_action")
                    if it.prop_action == "SET":
                        box2.prop(it, "prop_value")
                        box2.label(text="Enum-flag: 'EDGE,FACE' or '+EDGE -FACE' or 'NONE' or 'ALL'", icon="INFO")


# -----------------------------------------------------------------------------
# Section operators
# -----------------------------------------------------------------------------

class CQF_OT_SectionAdd(Operator):
    bl_idname = "cqf.section_add"
    bl_label = "Add Section"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _active_mode(prefs)
        if not mode_cfg:
            return {'CANCELLED'}

        s = mode_cfg.sections.add()
        s.title = "New Section"
        mode_cfg.active_section_index = len(mode_cfg.sections) - 1
        save_config_now()
        return {'FINISHED'}


class CQF_OT_SectionRemove(Operator):
    bl_idname = "cqf.section_remove"
    bl_label = "Remove Section"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _active_mode(prefs)
        if not mode_cfg:
            return {'CANCELLED'}

        idx = int(mode_cfg.active_section_index)
        if 0 <= idx < len(mode_cfg.sections):
            mode_cfg.sections.remove(idx)
            mode_cfg.active_section_index = max(0, min(idx, len(mode_cfg.sections) - 1))

        if not mode_cfg.sections:
            s = mode_cfg.sections.add()
            s.title = "Section"
            mode_cfg.active_section_index = 0

        save_config_now()
        return {'FINISHED'}


class CQF_OT_SectionMove(Operator):
    bl_idname = "cqf.section_move"
    bl_label = "Move Section"
    bl_options = {'INTERNAL'}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _active_mode(prefs)
        if not mode_cfg:
            return {'CANCELLED'}

        idx = int(mode_cfg.active_section_index)
        if not (0 <= idx < len(mode_cfg.sections)):
            return {'CANCELLED'}

        new_idx = idx - 1 if self.direction == "UP" else idx + 1
        if 0 <= new_idx < len(mode_cfg.sections):
            mode_cfg.sections.move(idx, new_idx)
            mode_cfg.active_section_index = new_idx

        save_config_now()
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Item operators
# -----------------------------------------------------------------------------

class CQF_OT_ItemAddSeparator(Operator):
    bl_idname = "cqf.item_add_separator"
    bl_label = "Add Separator"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _active_mode(prefs)
        sec = _active_section(mode_cfg)
        if not sec:
            sec = _ensure_section_exists(mode_cfg)

        it = sec.items.add()
        it.type = "SEP"
        it.text = ""
        it.tooltip = ""
        sec.active_item_index = len(sec.items) - 1
        save_config_now()
        return {'FINISHED'}


class CQF_OT_ItemRemove(Operator):
    bl_idname = "cqf.item_remove"
    bl_label = "Remove Item"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _active_mode(prefs)
        sec = _active_section(mode_cfg)
        if not sec:
            return {'CANCELLED'}

        idx = int(sec.active_item_index)
        if 0 <= idx < len(sec.items):
            sec.items.remove(idx)
            sec.active_item_index = max(0, min(idx, len(sec.items) - 1))

        save_config_now()
        return {'FINISHED'}


class CQF_OT_ItemMove(Operator):
    bl_idname = "cqf.item_move"
    bl_label = "Move Item"
    bl_options = {'INTERNAL'}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)
        mode_cfg = _active_mode(prefs)
        sec = _active_section(mode_cfg)
        if not sec:
            return {'CANCELLED'}

        idx = int(sec.active_item_index)
        if not (0 <= idx < len(sec.items)):
            return {'CANCELLED'}

        new_idx = idx - 1 if self.direction == "UP" else idx + 1
        if 0 <= new_idx < len(sec.items):
            sec.items.move(idx, new_idx)
            sec.active_item_index = new_idx

        save_config_now()
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Menu (Q / Shift+Q)
# -----------------------------------------------------------------------------

class CQF_MT_FavoritesMenu(Menu):
    bl_label = "Custom Quick Favorites"
    bl_idname = "CQF_MT_favorites_menu"

    def draw(self, context):
        prefs = get_prefs()
        ensure_default_config(prefs)

        mode_cfg = _mode_for_context(prefs, context)
        layout = self.layout

        if not mode_cfg or not mode_cfg.sections:
            layout.label(text="No configuration found.", icon="INFO")
            layout.label(text="Open Add-on Preferences to manage sections/items.", icon="PREFERENCES")
            return

        for si, sec in enumerate(mode_cfg.sections):
            title = (sec.title or "").strip()
            if title:
                layout.label(text=title)

            col = layout.column(align=True)
            for ii, it in enumerate(sec.items):
                if it.type == "SEP":
                    col.separator()
                    continue

                label = (it.text or "").strip()
                if not label:
                    if it.type == "OP":
                        label = (it.op_idname or it.op_expr or "Operator").strip()
                    elif it.type == "MENU":
                        label = (it.menu_idname or "Menu").strip()
                    else:
                        label = (f"{it.owner_expr}.{it.prop_id}" if it.owner_expr else it.prop_id).strip() or "Property"

                icon = "DOT"
                if it.type == "OP":
                    icon = "PLAY"
                elif it.type == "MENU":
                    icon = "MENU_PANEL"
                elif it.type == "PROP":
                    icon = "CHECKBOX_HLT"

                op = col.operator("cqf.run_item", text=label, icon=icon)
                op.mode_key = mode_cfg.mode_key
                op.section_index = si
                op.item_index = ii

            layout.separator()


class CQF_OT_OpenMenu(Operator):
    bl_idname = "cqf.open_menu"
    bl_label = "Open Custom Quick Favorites"

    def invoke(self, context, event):
        # ✅ Open custom quad UI (hover perfect, no warp)
        return bpy.ops.cqf.open_menu_quad('INVOKE_DEFAULT')

    def execute(self, context):
        # fallback
        bpy.ops.cqf.open_menu_quad('INVOKE_DEFAULT')
        return {'FINISHED'}


_CLASSES = (
    CQF_OT_ManualCapture,
    CQF_OT_StopManualCapture,
    CQF_OT_AddFromSearch,
    CQF_OT_AskManualAdd,

    CQF_OT_RunItem,

    CQF_OT_AddFromButtonContext,
    CQF_OT_OpenManager,
    CQF_OT_ManagerPopup,

    CQF_OT_SectionAdd,
    CQF_OT_SectionRemove,
    CQF_OT_SectionMove,

    CQF_OT_ItemAddSeparator,
    CQF_OT_ItemRemove,
    CQF_OT_ItemMove,

    CQF_MT_FavoritesMenu,
    CQF_OT_OpenMenu,
)

_context_menu_hooked = False


def register():
    global _context_menu_hooked

    for c in _CLASSES:
        bpy.utils.register_class(c)

    bpy.types.WindowManager.cqf_manual_capture_active = BoolProperty(default=False)

    prefs = get_prefs()
    if prefs:
        load_config_into_prefs(prefs)

    bpy.types.WM_MT_button_context.append(cqf_draw_button_context)
    _context_menu_hooked = True


def unregister():
    global _context_menu_hooked

    try:
        save_config_now()
    except Exception:
        pass

    try:
        remove_capture_combo_everywhere()
    except Exception:
        pass

    if hasattr(bpy.types.WindowManager, "cqf_manual_capture_active"):
        del bpy.types.WindowManager.cqf_manual_capture_active

    if _context_menu_hooked:
        try:
            bpy.types.WM_MT_button_context.remove(cqf_draw_button_context)
        except Exception:
            pass
        _context_menu_hooked = False

    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)