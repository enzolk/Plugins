# cqf_types.py
import bpy
from bpy.types import AddonPreferences, PropertyGroup, UIList
from bpy.props import (
    StringProperty, EnumProperty, CollectionProperty, IntProperty, BoolProperty,
    FloatProperty, FloatVectorProperty
)

from .cqf_config import _prefs_update_cb, config_path
from .cqf_config import ensure_default_config


ITEM_TYPES = [
    ("OP", "Operator", ""),
    ("MENU", "Menu", ""),
    ("PROP", "Property", ""),
    ("SCRIPT", "Custom Script", ""),
    ("SEP", "Separator", ""),
]

SECTION_SLOTS = [
    ("TOP", "Top popup", "Show this section in the TOP popup (above mouse)"),
    ("LEFT", "Left popup", "Show this section in the LEFT popup"),
    ("RIGHT", "Right popup", "Show this section in the RIGHT popup"),
    ("BOTTOM", "Bottom popup", "Show this section in the BOTTOM popup (below mouse)"),
]


def _get_addon_prefs(context):
    try:
        ad = context.preferences.addons.get(__package__.split(".")[0])
        return ad.preferences if ad else None
    except Exception:
        return None


def _active_script_item_from_context(context):
    prefs = _get_addon_prefs(context)
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
    if (getattr(it, "type", "") or "") != "SCRIPT":
        return None
    return it


def _script_code_update_cb(self, context):
    try:
        if hasattr(self, "script_lines_cache"):
            self.script_lines_cache = (self.script_code or "")
    except Exception:
        pass
    _prefs_update_cb(self, context)


def _script_line_update_cb(self, context):
    it = _active_script_item_from_context(context)
    if not it:
        return
    try:
        it.script_code = "\n".join((ln.text or "") for ln in it.script_lines)
        it.script_lines_cache = it.script_code
    except Exception:
        pass
    _prefs_update_cb(it, context)


def sync_script_lines_from_code(item):
    if not item:
        return

    code = (getattr(item, "script_code", "") or "")
    cache = (getattr(item, "script_lines_cache", "") or "")
    if cache == code and len(getattr(item, "script_lines", [])) > 0:
        return

    lines = code.splitlines()
    if code.endswith("\n"):
        lines.append("")
    if not lines:
        lines = [""]

    item.script_lines.clear()
    for line in lines:
        row = item.script_lines.add()
        row.text = line

    item.active_script_line_index = min(max(0, int(getattr(item, "active_script_line_index", 0))), len(item.script_lines) - 1)
    item.script_lines_cache = code


class CQF_ScriptLine(PropertyGroup):
    text: StringProperty(name="Line", default="", update=_script_line_update_cb)


class CQF_Item(PropertyGroup):
    type: EnumProperty(name="Type", items=ITEM_TYPES, default="OP", update=_prefs_update_cb)

    text: StringProperty(name="Button Text", default="", update=_prefs_update_cb)
    tooltip: StringProperty(name="Tooltip", default="", update=_prefs_update_cb)

    op_idname: StringProperty(name="Operator idname", default="", update=_prefs_update_cb)
    op_expr: StringProperty(name="Operator full python expr", default="", update=_prefs_update_cb)

    menu_idname: StringProperty(name="Menu idname", default="", update=_prefs_update_cb)
    menu_call: EnumProperty(
        name="Menu Call",
        items=[("call_menu", "wm.call_menu", ""), ("call_menu_pie", "wm.call_menu_pie", "")],
        default="call_menu",
        update=_prefs_update_cb,
    )

    owner_expr: StringProperty(name="Owner Expr", default="", update=_prefs_update_cb)
    prop_id: StringProperty(name="Prop Id", default="", update=_prefs_update_cb)
    prop_action: EnumProperty(
        name="Action",
        items=[("TOGGLE", "Toggle (bool)", ""), ("SET", "Set value", "")],
        default="TOGGLE",
        update=_prefs_update_cb,
    )
    prop_value: StringProperty(name="Value (text)", default="", update=_prefs_update_cb)

    script_code: StringProperty(name="Custom Script", default="", update=_script_code_update_cb)
    script_lines: CollectionProperty(type=CQF_ScriptLine)
    active_script_line_index: IntProperty(default=0, update=_prefs_update_cb)
    script_lines_cache: StringProperty(default="")


class CQF_Section(PropertyGroup):
    title: StringProperty(name="Title", default="Section", update=_prefs_update_cb)

    popup_slot: EnumProperty(
        name="Popup Slot",
        items=SECTION_SLOTS,
        default="TOP",
        update=_prefs_update_cb,
    )

    items: CollectionProperty(type=CQF_Item)
    active_item_index: IntProperty(default=0, update=_prefs_update_cb)


class CQF_ModeConfig(PropertyGroup):
    mode_key: StringProperty(name="Mode Key", default="OBJECT", update=_prefs_update_cb)
    sections: CollectionProperty(type=CQF_Section)
    active_section_index: IntProperty(default=0, update=_prefs_update_cb)


def _keymap_pref_update(self, context):
    try:
        from . import cqf_keymap
        cqf_keymap.refresh_keymap()
    except Exception:
        pass


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


def _active_item(section):
    if not section or not section.items:
        return None
    idx = int(getattr(section, "active_item_index", 0))
    if 0 <= idx < len(section.items):
        return section.items[idx]
    return section.items[0]


class CQF_AddonPrefs(AddonPreferences):
    bl_idname = __package__.split(".")[0]

    modes: CollectionProperty(type=CQF_ModeConfig)
    active_mode_index: IntProperty(default=1, update=_prefs_update_cb)

    use_q_instead_of_shift_q: BoolProperty(
        name="Use Q instead of Shift+Q",
        description="If enabled, Q opens Custom Quick Favorites and overrides Blender native Quick Favorites. If disabled, Shift+Q opens Custom Quick Favorites and Q remains native.",
        default=False,
        update=_keymap_pref_update,
    )

    # ------------------------------------------------------------------
    # UI Appearance preferences
    # ------------------------------------------------------------------

    # Fonts: sizes
    ui_header_font_size: IntProperty(name="Section font size", default=15, min=8, max=32, update=_prefs_update_cb)
    ui_item_font_size: IntProperty(name="Item font size", default=14, min=8, max=32, update=_prefs_update_cb)
    ui_tooltip_font_size: IntProperty(name="Tooltip font size", default=12, min=8, max=32, update=_prefs_update_cb)

    # Fonts: style controls
    ui_header_font_weight: IntProperty(name="Section weight", default=400, min=100, max=900, update=_prefs_update_cb)
    ui_item_font_weight: IntProperty(name="Item weight", default=400, min=100, max=900, update=_prefs_update_cb)
    ui_tooltip_font_weight: IntProperty(name="Tooltip weight", default=400, min=100, max=900, update=_prefs_update_cb)

    ui_header_bold: BoolProperty(name="Section bold", default=False, update=_prefs_update_cb)
    ui_item_bold: BoolProperty(name="Item bold", default=False, update=_prefs_update_cb)
    ui_tooltip_bold: BoolProperty(name="Tooltip bold", default=False, update=_prefs_update_cb)

    ui_header_italic: BoolProperty(name="Section italic", default=False, update=_prefs_update_cb)
    ui_item_italic: BoolProperty(name="Item italic", default=False, update=_prefs_update_cb)
    ui_tooltip_italic: BoolProperty(name="Tooltip italic", default=False, update=_prefs_update_cb)

    ui_header_underline: BoolProperty(name="Section underline", default=False, update=_prefs_update_cb)
    ui_item_underline: BoolProperty(name="Item underline", default=False, update=_prefs_update_cb)
    ui_tooltip_underline: BoolProperty(name="Tooltip underline", default=False, update=_prefs_update_cb)

    # Colors / alpha
    ui_header_color: FloatVectorProperty(name="Section color", subtype='COLOR', size=3,
                                         default=(0.4898492097854614, 0.4898492097854614, 0.4898492097854614),
                                         min=0.0, max=1.0, update=_prefs_update_cb)
    ui_header_alpha: FloatProperty(name="Section alpha", default=1.0, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_item_color: FloatVectorProperty(name="Item color", subtype='COLOR', size=3,
                                       default=(0.8064299821853638, 0.8064299821853638, 0.8064299821853638),
                                       min=0.0, max=1.0, update=_prefs_update_cb)
    ui_item_alpha: FloatProperty(name="Item alpha", default=1.0, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_bg_color: FloatVectorProperty(name="Background color", subtype='COLOR', size=3,
                                     default=(0.04551559314131737, 0.04551559314131737, 0.04551559314131737),
                                     min=0.0, max=1.0, update=_prefs_update_cb)
    ui_bg_alpha: FloatProperty(name="Background alpha", default=0.9399999976158142, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_border_color: FloatVectorProperty(name="Border color", subtype='COLOR', size=3,
                                         default=(1.0, 1.0, 1.0), min=0.0, max=1.0, update=_prefs_update_cb)
    ui_border_alpha: FloatProperty(name="Border alpha", default=0.07000000029802322, min=0.0, max=1.0, update=_prefs_update_cb)
    ui_border_thickness: IntProperty(name="Border thickness", default=0, min=0, max=6, update=_prefs_update_cb)

    ui_radius: IntProperty(name="Corner radius", default=5, min=0, max=40, update=_prefs_update_cb)

    ui_sep_color: FloatVectorProperty(name="Separator color", subtype='COLOR', size=3,
                                      default=(0.19370141625404358, 0.19370141625404358, 0.19370141625404358),
                                      min=0.0, max=1.0, update=_prefs_update_cb)
    ui_sep_alpha: FloatProperty(name="Separator alpha", default=0.0, min=0.0, max=1.0, update=_prefs_update_cb)
    ui_sep_thickness: IntProperty(name="Separator thickness", default=1, min=1, max=8, update=_prefs_update_cb)

    ui_hover_color: FloatVectorProperty(name="Hover color", subtype='COLOR', size=3,
                                        default=(0.42472410202026367, 0.42472410202026367, 0.42472410202026367),
                                        min=0.0, max=1.0, update=_prefs_update_cb)
    ui_hover_alpha: FloatProperty(name="Hover alpha", default=0.10000000149011612, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_shadow_offset_x: IntProperty(name="Shadow offset X", default=3, min=-20, max=20, update=_prefs_update_cb)
    ui_shadow_offset_y: IntProperty(name="Shadow offset Y", default=-3, min=-20, max=20, update=_prefs_update_cb)
    ui_shadow_alpha: FloatProperty(name="Shadow alpha", default=0.15000000596046448, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_line_height: IntProperty(name="Row height", description="Height of each row (items/headers/separators).",
                                default=22, min=16, max=48, update=_prefs_update_cb)

    ui_panel_pad_x: IntProperty(name="Panel padding X", description="Left/right padding inside panels.",
                                default=16, min=6, max=40, update=_prefs_update_cb)
    ui_panel_pad_y: IntProperty(name="Panel padding Y", description="Top/bottom padding inside panels.",
                                default=12, min=4, max=40, update=_prefs_update_cb)

    ui_header_pad_y: IntProperty(name="Header padding Y", description="Extra vertical padding for section headers.",
                                 default=6, min=0, max=20, update=_prefs_update_cb)
    ui_item_pad_y: IntProperty(name="Item padding Y", description="Extra vertical padding for items.",
                               default=0, min=0, max=20, update=_prefs_update_cb)
    ui_sep_pad_y: IntProperty(name="Separator padding Y", description="Extra vertical padding around separators.",
                              default=1, min=0, max=20, update=_prefs_update_cb)

    # ------------------------------------------------------------------
    # ✅ Tooltip appearance (complete)
    # ------------------------------------------------------------------
    ui_tooltip_text_color: FloatVectorProperty(name="Tooltip text color", subtype='COLOR', size=3,
                                               default=(0.92, 0.92, 0.92), min=0.0, max=1.0, update=_prefs_update_cb)
    ui_tooltip_text_alpha: FloatProperty(name="Tooltip text alpha", default=1.0, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_tooltip_bg_color: FloatVectorProperty(name="Tooltip background color", subtype='COLOR', size=3,
                                             default=(0.03, 0.03, 0.03), min=0.0, max=1.0, update=_prefs_update_cb)
    ui_tooltip_bg_alpha: FloatProperty(name="Tooltip background alpha", default=0.95, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_tooltip_border_color: FloatVectorProperty(name="Tooltip border color", subtype='COLOR', size=3,
                                                 default=(1.0, 1.0, 1.0), min=0.0, max=1.0, update=_prefs_update_cb)
    ui_tooltip_border_alpha: FloatProperty(name="Tooltip border alpha", default=0.10, min=0.0, max=1.0, update=_prefs_update_cb)
    ui_tooltip_border_thickness: IntProperty(name="Tooltip border thickness", default=1, min=0, max=6, update=_prefs_update_cb)

    ui_tooltip_radius: IntProperty(name="Tooltip corner radius", default=6, min=0, max=40, update=_prefs_update_cb)

    ui_tooltip_shadow_offset_x: IntProperty(name="Tooltip shadow offset X", default=2, min=-20, max=20, update=_prefs_update_cb)
    ui_tooltip_shadow_offset_y: IntProperty(name="Tooltip shadow offset Y", default=-2, min=-20, max=20, update=_prefs_update_cb)
    ui_tooltip_shadow_alpha: FloatProperty(name="Tooltip shadow alpha", default=0.25, min=0.0, max=1.0, update=_prefs_update_cb)

    ui_tooltip_pad: IntProperty(name="Tooltip padding", default=10, min=2, max=40, update=_prefs_update_cb)
    ui_tooltip_max_w: IntProperty(name="Tooltip max width", default=420, min=120, max=1200, update=_prefs_update_cb)
    ui_tooltip_offset_x: IntProperty(name="Tooltip offset X", default=18, min=-200, max=200, update=_prefs_update_cb)
    ui_tooltip_offset_y: IntProperty(name="Tooltip offset Y", default=-18, min=-200, max=200, update=_prefs_update_cb)
    ui_tooltip_line_height: IntProperty(name="Tooltip line height (0=auto)", default=0, min=0, max=80, update=_prefs_update_cb)

    def draw(self, context):
        layout = self.layout
        ensure_default_config(self)

        layout.label(text="Custom Quick Favorites — Per-Mode / Sections", icon="BOOKMARKS")

        info = layout.box()
        info.label(text="Shortcut", icon="KEYINGSET")
        info.prop(self, "use_q_instead_of_shift_q")

        if self.use_q_instead_of_shift_q:
            info.label(text="• Open menu: Q (Overrides native Quick Favorites)", icon="INFO")
        else:
            info.label(text="• Open menu: Shift+Q (Q stays native)", icon="INFO")

        cfg = config_path()
        if cfg:
            info.label(text=f"Config file: {cfg}")

        layout.separator()

        app = layout.box()
        app.label(text="Menu Appearance", icon="COLOR")

        col = app.column(align=True)

        col.label(text="Fonts — Size")
        row = col.row(align=True)
        row.prop(self, "ui_header_font_size")
        row.prop(self, "ui_item_font_size")
        row.prop(self, "ui_tooltip_font_size")

        col.separator()
        col.label(text="Fonts — Style (Weight / Bold / Italic / Underline)")
        row = col.row(align=True)
        row.prop(self, "ui_header_font_weight")
        row.prop(self, "ui_header_bold")
        row.prop(self, "ui_header_italic")
        row.prop(self, "ui_header_underline")

        row = col.row(align=True)
        row.prop(self, "ui_item_font_weight")
        row.prop(self, "ui_item_bold")
        row.prop(self, "ui_item_italic")
        row.prop(self, "ui_item_underline")

        row = col.row(align=True)
        row.prop(self, "ui_tooltip_font_weight")
        row.prop(self, "ui_tooltip_bold")
        row.prop(self, "ui_tooltip_italic")
        row.prop(self, "ui_tooltip_underline")

        col.separator()
        col.label(text="Text colors")
        row = col.row(align=True)
        row.prop(self, "ui_header_color")
        row.prop(self, "ui_header_alpha")

        row = col.row(align=True)
        row.prop(self, "ui_item_color")
        row.prop(self, "ui_item_alpha")

        col.separator()
        col.label(text="Panels")
        row = col.row(align=True)
        row.prop(self, "ui_bg_color")
        row.prop(self, "ui_bg_alpha")

        row = col.row(align=True)
        row.prop(self, "ui_border_color")
        row.prop(self, "ui_border_alpha")

        row = col.row(align=True)
        row.prop(self, "ui_border_thickness")
        row.prop(self, "ui_radius")

        col.separator()
        col.label(text="Separators & Hover")
        row = col.row(align=True)
        row.prop(self, "ui_sep_color")
        row.prop(self, "ui_sep_alpha")
        row.prop(self, "ui_sep_thickness")

        row = col.row(align=True)
        row.prop(self, "ui_hover_color")
        row.prop(self, "ui_hover_alpha")

        col.separator()
        col.label(text="Shadow")
        row = col.row(align=True)
        row.prop(self, "ui_shadow_offset_x")
        row.prop(self, "ui_shadow_offset_y")
        row.prop(self, "ui_shadow_alpha")

        col.separator()
        col.label(text="Spacing / Padding")
        row = col.row(align=True)
        row.prop(self, "ui_line_height")
        row.prop(self, "ui_panel_pad_x")
        row.prop(self, "ui_panel_pad_y")

        row = col.row(align=True)
        row.prop(self, "ui_header_pad_y")
        row.prop(self, "ui_item_pad_y")
        row.prop(self, "ui_sep_pad_y")

        # ✅ Tooltip box
        layout.separator()
        tip = layout.box()
        tip.label(text="Tooltip Appearance", icon="INFO")

        c2 = tip.column(align=True)
        c2.label(text="Tooltip text")
        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_text_color")
        r.prop(self, "ui_tooltip_text_alpha")

        c2.separator()
        c2.label(text="Tooltip box")
        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_bg_color")
        r.prop(self, "ui_tooltip_bg_alpha")

        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_border_color")
        r.prop(self, "ui_tooltip_border_alpha")

        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_border_thickness")
        r.prop(self, "ui_tooltip_radius")

        c2.separator()
        c2.label(text="Tooltip shadow")
        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_shadow_offset_x")
        r.prop(self, "ui_tooltip_shadow_offset_y")
        r.prop(self, "ui_tooltip_shadow_alpha")

        c2.separator()
        c2.label(text="Tooltip layout")
        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_pad")
        r.prop(self, "ui_tooltip_max_w")

        r = c2.row(align=True)
        r.prop(self, "ui_tooltip_offset_x")
        r.prop(self, "ui_tooltip_offset_y")
        r.prop(self, "ui_tooltip_line_height")

        layout.separator()

        tools = layout.box()
        tools.label(text="Tools", icon="TOOL_SETTINGS")
        row = tools.row(align=True)
        row.operator("cqf.ask_manual_add", text="Manual Add (Search / Capture)…", icon="VIEWZOOM")
        row.operator("cqf.stop_manual_capture", text="Stop assigning the UI element", icon="CANCEL")

        layout.separator()

        row = layout.row()
        col_left = row.column()
        col_mid = row.column()
        col_right = row.column()

        col_left.label(text="Modes (fixed)")
        col_left.template_list("CQF_UL_Modes", "", self, "modes", self, "active_mode_index", rows=8)
        col_left.label(text="(Cannot rename / delete)", icon="INFO")

        mode_cfg = _active_mode(self)
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
        item_ops.operator("cqf.item_add_custom_script", text="Custom Script Button", icon="FILE_SCRIPT")

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
                elif it.type == "SCRIPT":
                    sync_script_lines_from_code(it)
                    box2.label(text="Custom Script (scrollable)", icon="FILE_SCRIPT")

                    rows = box2.row(align=True)
                    rows.template_list("CQF_UL_ScriptLines", "", it, "script_lines", it, "active_script_line_index", rows=10)

                    side = rows.column(align=True)
                    side.operator("cqf.script_line_add", text="", icon="ADD")
                    side.operator("cqf.script_line_remove", text="", icon="REMOVE")
                    side.separator()
                    side.operator("cqf.script_line_move", text="", icon="TRIA_UP").direction = "UP"
                    side.operator("cqf.script_line_move", text="", icon="TRIA_DOWN").direction = "DOWN"

                    tools = box2.row(align=True)
                    tools.operator("cqf.script_from_clipboard", text="Paste Clipboard", icon="PASTEDOWN")
                    tools.operator("cqf.script_to_clipboard", text="Copy Script", icon="COPYDOWN")

                    box2.label(text="Script has access to bpy, context and C.", icon="INFO")


class CQF_UL_Modes(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        mk = (item.mode_key or "").strip()
        layout.label(text=mk if mk else "MODE", icon="FILE_BLEND")


class CQF_UL_Sections(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        row = layout.row(align=True)
        row.prop(item, "title", text="", emboss=False, icon="BOOKMARKS")
        row.prop(item, "popup_slot", text="", emboss=True)


class CQF_UL_Items(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        it = item
        row = layout.row(align=True)

        if it.type == "OP":
            label = (it.text or "").strip() or (it.op_idname or "").strip() or "Operator"
            row.label(text=label, icon="PLAY")
        elif it.type == "MENU":
            label = (it.text or "").strip() or (it.menu_idname or "").strip() or "Menu"
            row.label(text=label, icon="MENU_PANEL")
        elif it.type == "PROP":
            if (it.owner_expr or "").strip() and (it.prop_id or "").strip():
                fallback = f"{it.owner_expr}.{it.prop_id}"
            else:
                fallback = (it.prop_id or "").strip() or "Property"
            label = (it.text or "").strip() or fallback
            row.label(text=label, icon="CHECKBOX_HLT")
        elif it.type == "SCRIPT":
            label = (it.text or "").strip() or "Custom Script"
            row.label(text=label, icon="FILE_SCRIPT")
        else:
            row.label(text="────────", icon="REMOVE")


class CQF_UL_ScriptLines(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0):
        layout.prop(item, "text", text="", emboss=True)


_CLASSES = (
    CQF_ScriptLine,
    CQF_Item,
    CQF_Section,
    CQF_ModeConfig,
    CQF_AddonPrefs,
    CQF_UL_Modes,
    CQF_UL_Sections,
    CQF_UL_Items,
    CQF_UL_ScriptLines,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)