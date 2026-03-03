# cqf_types.py
import bpy
from bpy.types import PropertyGroup, AddonPreferences, UIList
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
    ("TOP", "Top popup", "Show this section in the TOP quad popup panel"),
    ("LEFT", "Left popup", "Show this section in the LEFT quad popup panel"),
    ("RIGHT", "Right popup", "Show this section in the RIGHT quad popup panel"),
    ("BOTTOM", "Bottom popup", "Show this section in the BOTTOM quad popup panel"),
]


# -----------------------------------------------------------------------------
# Data model (Prefs)
# -----------------------------------------------------------------------------

class CQF_Item(PropertyGroup):
    type: EnumProperty(name="Type", items=ITEM_TYPES, default="OP", update=_prefs_update_cb)

    text: StringProperty(name="Button Text", default="", update=_prefs_update_cb)
    tooltip: StringProperty(name="Tooltip", default="", update=_prefs_update_cb)

    op_idname: StringProperty(name="Operator idname", default="", update=_prefs_update_cb)
    op_expr: StringProperty(name="Operator full python expr", default="", update=_prefs_update_cb)

    script_code: StringProperty(name="Custom Script", default="", options={'MULTILINE'}, update=_prefs_update_cb)

    menu_idname: StringProperty(name="Menu idname", default="", update=_prefs_update_cb)
    menu_call: EnumProperty(
        name="Menu Call",
        items=[("call_menu", "wm.call_menu", ""), ("call_menu_pie", "wm.call_menu_pie", "")],
        default="call_menu",
        update=_prefs_update_cb,
    )

    owner_expr: StringProperty(name="Owner expression", default="", update=_prefs_update_cb)
    prop_id: StringProperty(name="Property identifier", default="", update=_prefs_update_cb)
    prop_action: EnumProperty(
        name="Action",
        items=[
            ("TOGGLE", "Toggle", ""),
            ("SET", "Set", ""),
            ("CYCLE", "Cycle Enum", ""),
            ("TOGGLE_ENUM", "Toggle Enum", ""),
            ("TOGGLE_ENUM_FLAG", "Toggle Enum Flag", ""),
        ],
        default="TOGGLE",
        update=_prefs_update_cb,
    )
    prop_value: StringProperty(name="Value", default="", update=_prefs_update_cb)


class CQF_Section(PropertyGroup):
    title: StringProperty(name="Title", default="Section", update=_prefs_update_cb)
    popup_slot: EnumProperty(name="Popup Slot", items=SECTION_SLOTS, default="TOP", update=_prefs_update_cb)

    items: CollectionProperty(type=CQF_Item)
    active_item_index: IntProperty(default=0, update=_prefs_update_cb)


class CQF_ModeConfig(PropertyGroup):
    mode_key: StringProperty(name="Mode Key", default="OBJECT", update=_prefs_update_cb)
    sections: CollectionProperty(type=CQF_Section)
    active_section_index: IntProperty(default=0, update=_prefs_update_cb)


class CQF_AddonPrefs(AddonPreferences):
    bl_idname = __package__.split(".")[0] if __package__ else __name__

    config_file_path: StringProperty(
        name="Config file",
        default="",
        subtype='FILE_PATH',
        update=_prefs_update_cb,
    )

    active_mode_index: IntProperty(default=0, update=_prefs_update_cb)

    modes: CollectionProperty(type=CQF_ModeConfig)

    # UI styling (kept from your version)
    ui_header_font_size: IntProperty(name="Header font size", default=15, min=8, max=64, update=_prefs_update_cb)
    ui_item_font_size: IntProperty(name="Item font size", default=14, min=8, max=64, update=_prefs_update_cb)

    ui_panel_width: IntProperty(name="Panel width", default=240, min=120, max=600, update=_prefs_update_cb)
    ui_row_height: IntProperty(name="Row height", default=26, min=18, max=60, update=_prefs_update_cb)
    ui_gap: IntProperty(name="Panel gap", default=14, min=0, max=80, update=_prefs_update_cb)

    ui_pad_x: IntProperty(name="Padding X", default=12, min=0, max=80, update=_prefs_update_cb)
    ui_pad_y: IntProperty(name="Padding Y", default=10, min=0, max=80, update=_prefs_update_cb)

    ui_round: IntProperty(name="Corner round", default=14, min=0, max=40, update=_prefs_update_cb)
    ui_shadow: BoolProperty(name="Shadow", default=True, update=_prefs_update_cb)

    ui_header_rgba: FloatVectorProperty(name="Header color", size=4, subtype='COLOR', default=(1, 1, 1, 1), min=0, max=1, update=_prefs_update_cb)
    ui_item_rgba: FloatVectorProperty(name="Item color", size=4, subtype='COLOR', default=(1, 1, 1, 1), min=0, max=1, update=_prefs_update_cb)
    ui_bg_rgba: FloatVectorProperty(name="Background color", size=4, subtype='COLOR', default=(0.12, 0.12, 0.12, 0.92), min=0, max=1, update=_prefs_update_cb)
    ui_border_rgba: FloatVectorProperty(name="Border color", size=4, subtype='COLOR', default=(0.2, 0.2, 0.2, 1), min=0, max=1, update=_prefs_update_cb)

    ui_border_thickness: FloatProperty(name="Border thickness", default=1.0, min=0.0, max=6.0, update=_prefs_update_cb)

    ui_tooltip_rgba: FloatVectorProperty(name="Tooltip text", size=4, subtype='COLOR', default=(1, 1, 1, 1), min=0, max=1, update=_prefs_update_cb)
    ui_tooltip_bg_rgba: FloatVectorProperty(name="Tooltip bg", size=4, subtype='COLOR', default=(0.05, 0.05, 0.05, 0.95), min=0, max=1, update=_prefs_update_cb)

    use_q_instead_of_shift_q: BoolProperty(
        name="Use Q instead of Shift+Q",
        default=False,
        description="If enabled, overrides native Quick Favorites (Q) with this add-on.\nIf disabled, uses Shift+Q (default).",
        update=_prefs_update_cb,
    )

    def draw(self, context):
        layout = self.layout
        ensure_default_config(self)

        box = layout.box()
        box.label(text="Config", icon="FILE_BLEND")
        row = box.row()
        row.prop(self, "config_file_path", text="")
        row.operator("cqf.open_manager", text="Open Manager", icon="PREFERENCES")

        layout.separator()

        row = layout.row()
        col_left = row.column()
        col_right = row.column()

        col_left.label(text="Modes", icon="FILE_BLEND")
        col_left.template_list("CQF_UL_Modes", "", self, "modes", self, "active_mode_index", rows=8)

        if not self.modes:
            col_right.label(text="No mode configs.", icon="INFO")
            return

        m = self.modes[self.active_mode_index]

        col_right.label(text=f"Sections ({m.mode_key})", icon="BOOKMARKS")
        col_right.template_list("CQF_UL_Sections", "", m, "sections", m, "active_section_index", rows=6)

        if not m.sections:
            col_right.label(text="No sections.", icon="INFO")
            return

        s = m.sections[m.active_section_index]

        col_right.separator()
        col_right.label(text=f"Items ({s.title})", icon="SEQUENCE")
        col_right.template_list("CQF_UL_Items", "", s, "items", s, "active_item_index", rows=10)

        col_right.separator()

        # Selected item settings
        if not s.items:
            col_right.label(text="No items.", icon="INFO")
            return
        if not (0 <= s.active_item_index < len(s.items)):
            s.active_item_index = 0
        it = s.items[s.active_item_index]

        box2 = col_right.box()
        box2.label(text="Selected Item Settings", icon="PREFERENCES")

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
                box2.prop(it, "script_code", text="Custom Script")
                box2.label(text="Available: bpy, context (bpy.context), data (bpy.data), ops (bpy.ops)", icon="INFO")


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


_CLASSES = (
    CQF_Item,
    CQF_Section,
    CQF_ModeConfig,
    CQF_AddonPrefs,
    CQF_UL_Modes,
    CQF_UL_Sections,
    CQF_UL_Items,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)