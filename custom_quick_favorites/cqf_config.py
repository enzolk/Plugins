# cqf_config.py
import os
import json
import sys
import bpy

ADDON_VERSION = (1, 5, 0)  # ✅ bump version

DEFAULT_MODES = [
    "OBJECT",
    "EDIT_MESH",
    "SCULPT",
    "VERTEX_PAINT",
    "WEIGHT_PAINT",
    "TEXTURE_PAINT",
]


def _addon_key():
    return __package__.split(".")[0] if __package__ else __name__


def _addon_base_path():
    try:
        mod = sys.modules.get(_addon_key())
        p = getattr(mod, "__file__", "")
        if p:
            return os.path.dirname(os.path.abspath(p))
    except Exception:
        pass
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return ""


def config_path():
    d = _addon_base_path()
    if not d:
        return ""
    return os.path.join(d, "cqf_config.json")


def safe_read_json(path: str):
    try:
        if not path or not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def safe_write_json(path: str, data):
    try:
        if not path:
            return False
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_prefs():
    try:
        return bpy.context.preferences.addons[_addon_key()].preferences
    except Exception:
        return None


def get_mode_key_from_context(context) -> str:
    mk = (getattr(context, "mode", "") or "OBJECT").strip().upper()
    return mk if mk in DEFAULT_MODES else "OBJECT"


def ensure_default_config(prefs):
    if not prefs:
        return

    existing = set()
    for m in prefs.modes:
        existing.add((m.mode_key or "").strip().upper())

    for mk in DEFAULT_MODES:
        if mk in existing:
            continue
        m = prefs.modes.add()
        m.mode_key = mk
        s = m.sections.add()
        s.title = "Section"
        if hasattr(s, "popup_slot"):
            s.popup_slot = "TOP"

    for i in range(len(prefs.modes) - 1, -1, -1):
        mk = (prefs.modes[i].mode_key or "").strip().upper()
        if mk not in DEFAULT_MODES:
            prefs.modes.remove(i)

    current_order = [(m.mode_key or "").strip().upper() for m in prefs.modes]
    if current_order != DEFAULT_MODES:
        data = prefs_to_dict(prefs)
        dict_to_prefs(prefs, data)

    # ✅ Apply requested defaults ONLY when config file does NOT exist yet
    _ensure_ui_defaults(prefs)

    prefs.active_mode_index = max(0, min(int(getattr(prefs, "active_mode_index", 0)), len(prefs.modes) - 1))

    for m in prefs.modes:
        if not m.sections:
            s = m.sections.add()
            s.title = "Section"
            if hasattr(s, "popup_slot"):
                s.popup_slot = "TOP"
            m.active_section_index = 0

        for s in m.sections:
            if hasattr(s, "popup_slot"):
                v = (getattr(s, "popup_slot", "") or "").strip().upper()
                if v not in {"TOP", "LEFT", "RIGHT", "BOTTOM"}:
                    s.popup_slot = "TOP"


def _ensure_ui_defaults(prefs):
    """
    IMPORTANT:
    - We only apply the "theme defaults" the first time (when cqf_config.json does not exist).
    - If the config file exists, do NOT overwrite user customizations.
    """
    try:
        cfg = config_path()
        if cfg and os.path.exists(cfg):
            return
    except Exception:
        return

    # ✅ Your requested defaults
    try:
        prefs.active_mode_index = 1
    except Exception:
        pass

    # Font sizes
    try:
        prefs.ui_header_font_size = 15
        prefs.ui_item_font_size = 14
        prefs.ui_tooltip_font_size = 12
    except Exception:
        pass

    # Font styles (weight/bold/italic/underline)
    try:
        prefs.ui_header_font_weight = 400
        prefs.ui_item_font_weight = 400
        prefs.ui_tooltip_font_weight = 400

        prefs.ui_header_bold = False
        prefs.ui_item_bold = False
        prefs.ui_tooltip_bold = False

        prefs.ui_header_italic = False
        prefs.ui_item_italic = False
        prefs.ui_tooltip_italic = False

        prefs.ui_header_underline = False
        prefs.ui_item_underline = False
        prefs.ui_tooltip_underline = False
    except Exception:
        pass

    # Colors / alpha
    try:
        prefs.ui_header_color = (0.4898492097854614, 0.4898492097854614, 0.4898492097854614)
        prefs.ui_header_alpha = 1.0

        prefs.ui_item_color = (0.8064299821853638, 0.8064299821853638, 0.8064299821853638)
        prefs.ui_item_alpha = 1.0

        prefs.ui_bg_color = (0.04551559314131737, 0.04551559314131737, 0.04551559314131737)
        prefs.ui_bg_alpha = 0.9399999976158142

        prefs.ui_border_color = (1.0, 1.0, 1.0)
        prefs.ui_border_alpha = 0.07000000029802322
        prefs.ui_border_thickness = 0

        prefs.ui_radius = 5

        prefs.ui_sep_color = (0.19370141625404358, 0.19370141625404358, 0.19370141625404358)
        prefs.ui_sep_alpha = 0.0
        prefs.ui_sep_thickness = 1

        prefs.ui_hover_color = (0.42472410202026367, 0.42472410202026367, 0.42472410202026367)
        prefs.ui_hover_alpha = 0.10000000149011612

        prefs.ui_shadow_offset_x = 3
        prefs.ui_shadow_offset_y = -3
        prefs.ui_shadow_alpha = 0.15000000596046448

        prefs.ui_line_height = 22
        prefs.ui_panel_pad_x = 16
        prefs.ui_panel_pad_y = 12
        prefs.ui_header_pad_y = 6
        prefs.ui_item_pad_y = 0
        prefs.ui_sep_pad_y = 1

        # ✅ Tooltip appearance defaults
        prefs.ui_tooltip_text_color = (0.92, 0.92, 0.92)
        prefs.ui_tooltip_text_alpha = 1.0

        prefs.ui_tooltip_bg_color = (0.03, 0.03, 0.03)
        prefs.ui_tooltip_bg_alpha = 0.95

        prefs.ui_tooltip_border_color = (1.0, 1.0, 1.0)
        prefs.ui_tooltip_border_alpha = 0.10
        prefs.ui_tooltip_border_thickness = 1

        prefs.ui_tooltip_radius = 6

        prefs.ui_tooltip_shadow_offset_x = 2
        prefs.ui_tooltip_shadow_offset_y = -2
        prefs.ui_tooltip_shadow_alpha = 0.25

        prefs.ui_tooltip_pad = 10
        prefs.ui_tooltip_max_w = 420
        prefs.ui_tooltip_offset_x = 18
        prefs.ui_tooltip_offset_y = -18
        prefs.ui_tooltip_line_height = 0  # 0 => auto based on font size
    except Exception:
        pass


def prefs_to_dict(prefs) -> dict:
    ui = {
        "header_font_size": int(getattr(prefs, "ui_header_font_size", 15)),
        "item_font_size": int(getattr(prefs, "ui_item_font_size", 14)),
        "tooltip_font_size": int(getattr(prefs, "ui_tooltip_font_size", 12)),

        "header_font_weight": int(getattr(prefs, "ui_header_font_weight", 400)),
        "item_font_weight": int(getattr(prefs, "ui_item_font_weight", 400)),
        "tooltip_font_weight": int(getattr(prefs, "ui_tooltip_font_weight", 400)),

        "header_bold": bool(getattr(prefs, "ui_header_bold", False)),
        "item_bold": bool(getattr(prefs, "ui_item_bold", False)),
        "tooltip_bold": bool(getattr(prefs, "ui_tooltip_bold", False)),

        "header_italic": bool(getattr(prefs, "ui_header_italic", False)),
        "item_italic": bool(getattr(prefs, "ui_item_italic", False)),
        "tooltip_italic": bool(getattr(prefs, "ui_tooltip_italic", False)),

        "header_underline": bool(getattr(prefs, "ui_header_underline", False)),
        "item_underline": bool(getattr(prefs, "ui_item_underline", False)),
        "tooltip_underline": bool(getattr(prefs, "ui_tooltip_underline", False)),

        "header_color": list(getattr(prefs, "ui_header_color", (0.4898492097854614, 0.4898492097854614, 0.4898492097854614))),
        "header_alpha": float(getattr(prefs, "ui_header_alpha", 1.0)),

        "item_color": list(getattr(prefs, "ui_item_color", (0.8064299821853638, 0.8064299821853638, 0.8064299821853638))),
        "item_alpha": float(getattr(prefs, "ui_item_alpha", 1.0)),

        "bg_color": list(getattr(prefs, "ui_bg_color", (0.04551559314131737, 0.04551559314131737, 0.04551559314131737))),
        "bg_alpha": float(getattr(prefs, "ui_bg_alpha", 0.9399999976158142)),

        "border_color": list(getattr(prefs, "ui_border_color", (1.0, 1.0, 1.0))),
        "border_alpha": float(getattr(prefs, "ui_border_alpha", 0.07000000029802322)),
        "border_thickness": int(getattr(prefs, "ui_border_thickness", 0)),

        "radius": int(getattr(prefs, "ui_radius", 5)),

        "sep_color": list(getattr(prefs, "ui_sep_color", (0.19370141625404358, 0.19370141625404358, 0.19370141625404358))),
        "sep_alpha": float(getattr(prefs, "ui_sep_alpha", 0.0)),
        "sep_thickness": int(getattr(prefs, "ui_sep_thickness", 1)),

        "hover_color": list(getattr(prefs, "ui_hover_color", (0.42472410202026367, 0.42472410202026367, 0.42472410202026367))),
        "hover_alpha": float(getattr(prefs, "ui_hover_alpha", 0.10000000149011612)),

        "shadow_offset_x": int(getattr(prefs, "ui_shadow_offset_x", 3)),
        "shadow_offset_y": int(getattr(prefs, "ui_shadow_offset_y", -3)),
        "shadow_alpha": float(getattr(prefs, "ui_shadow_alpha", 0.15000000596046448)),

        "line_height": int(getattr(prefs, "ui_line_height", 22)),
        "panel_pad_x": int(getattr(prefs, "ui_panel_pad_x", 16)),
        "panel_pad_y": int(getattr(prefs, "ui_panel_pad_y", 12)),
        "header_pad_y": int(getattr(prefs, "ui_header_pad_y", 6)),
        "item_pad_y": int(getattr(prefs, "ui_item_pad_y", 0)),
        "sep_pad_y": int(getattr(prefs, "ui_sep_pad_y", 1)),

        # ✅ Tooltip full appearance
        "tooltip_text_color": list(getattr(prefs, "ui_tooltip_text_color", (0.92, 0.92, 0.92))),
        "tooltip_text_alpha": float(getattr(prefs, "ui_tooltip_text_alpha", 1.0)),

        "tooltip_bg_color": list(getattr(prefs, "ui_tooltip_bg_color", (0.03, 0.03, 0.03))),
        "tooltip_bg_alpha": float(getattr(prefs, "ui_tooltip_bg_alpha", 0.95)),

        "tooltip_border_color": list(getattr(prefs, "ui_tooltip_border_color", (1.0, 1.0, 1.0))),
        "tooltip_border_alpha": float(getattr(prefs, "ui_tooltip_border_alpha", 0.10)),
        "tooltip_border_thickness": int(getattr(prefs, "ui_tooltip_border_thickness", 1)),

        "tooltip_radius": int(getattr(prefs, "ui_tooltip_radius", 6)),

        "tooltip_shadow_offset_x": int(getattr(prefs, "ui_tooltip_shadow_offset_x", 2)),
        "tooltip_shadow_offset_y": int(getattr(prefs, "ui_tooltip_shadow_offset_y", -2)),
        "tooltip_shadow_alpha": float(getattr(prefs, "ui_tooltip_shadow_alpha", 0.25)),

        "tooltip_pad": int(getattr(prefs, "ui_tooltip_pad", 10)),
        "tooltip_max_w": int(getattr(prefs, "ui_tooltip_max_w", 420)),
        "tooltip_offset_x": int(getattr(prefs, "ui_tooltip_offset_x", 18)),
        "tooltip_offset_y": int(getattr(prefs, "ui_tooltip_offset_y", -18)),
        "tooltip_line_height": int(getattr(prefs, "ui_tooltip_line_height", 0)),
    }

    data = {
        "version": [int(x) for x in ADDON_VERSION],
        "active_mode_index": int(getattr(prefs, "active_mode_index", 1)),
        "ui": ui,
        "modes": [],
    }

    for m in prefs.modes:
        mdata = {
            "mode_key": (m.mode_key or ""),
            "active_section_index": int(getattr(m, "active_section_index", 0)),
            "sections": [],
        }
        for s in m.sections:
            sdata = {
                "title": (s.title or ""),
                "popup_slot": (getattr(s, "popup_slot", "TOP") or "TOP"),
                "active_item_index": int(getattr(s, "active_item_index", 0)),
                "items": [],
            }
            for it in s.items:
                sdata["items"].append({
                    "type": (it.type or "OP"),
                    "text": (it.text or ""),
                    "tooltip": (it.tooltip or ""),
                    "icon_name": (getattr(it, "icon_name", "") or ""),
                    "icon_value": int(getattr(it, "icon_value", 0) or 0),

                    "op_idname": (it.op_idname or ""),
                    "op_expr": (it.op_expr or ""),

                    "menu_idname": (it.menu_idname or ""),
                    "menu_call": (it.menu_call or "call_menu"),

                    "owner_expr": (it.owner_expr or ""),
                    "prop_id": (it.prop_id or ""),
                    "prop_action": (it.prop_action or "TOGGLE"),
                    "prop_value": (it.prop_value or ""),

                    "script_code": (getattr(it, "script_code", "") or ""),
                })
            mdata["sections"].append(sdata)
        data["modes"].append(mdata)

    return data


def save_config_now():
    prefs = get_prefs()
    if not prefs:
        return
    path = config_path()
    if not path:
        return
    safe_write_json(path, prefs_to_dict(prefs))


def _prefs_update_cb(self, context):
    try:
        save_config_now()
    except Exception:
        pass


def dict_to_prefs(prefs, data: dict):
    if not prefs or not isinstance(data, dict):
        return

    ui = data.get("ui", {})
    if isinstance(ui, dict):
        def _vec3(key, default):
            v = ui.get(key, default)
            if isinstance(v, (list, tuple)) and len(v) >= 3:
                try:
                    return (float(v[0]), float(v[1]), float(v[2]))
                except Exception:
                    return default
            return default

        def _f(key, default):
            try:
                return float(ui.get(key, default))
            except Exception:
                return default

        def _i(key, default):
            try:
                return int(ui.get(key, default))
            except Exception:
                return default

        def _b(key, default):
            try:
                return bool(ui.get(key, default))
            except Exception:
                return default

        prefs.ui_header_font_size = _i("header_font_size", int(getattr(prefs, "ui_header_font_size", 15)))
        prefs.ui_item_font_size = _i("item_font_size", int(getattr(prefs, "ui_item_font_size", 14)))
        prefs.ui_tooltip_font_size = _i("tooltip_font_size", int(getattr(prefs, "ui_tooltip_font_size", 12)))

        prefs.ui_header_font_weight = _i("header_font_weight", int(getattr(prefs, "ui_header_font_weight", 400)))
        prefs.ui_item_font_weight = _i("item_font_weight", int(getattr(prefs, "ui_item_font_weight", 400)))
        prefs.ui_tooltip_font_weight = _i("tooltip_font_weight", int(getattr(prefs, "ui_tooltip_font_weight", 400)))

        prefs.ui_header_bold = _b("header_bold", bool(getattr(prefs, "ui_header_bold", False)))
        prefs.ui_item_bold = _b("item_bold", bool(getattr(prefs, "ui_item_bold", False)))
        prefs.ui_tooltip_bold = _b("tooltip_bold", bool(getattr(prefs, "ui_tooltip_bold", False)))

        prefs.ui_header_italic = _b("header_italic", bool(getattr(prefs, "ui_header_italic", False)))
        prefs.ui_item_italic = _b("item_italic", bool(getattr(prefs, "ui_item_italic", False)))
        prefs.ui_tooltip_italic = _b("tooltip_italic", bool(getattr(prefs, "ui_tooltip_italic", False)))

        prefs.ui_header_underline = _b("header_underline", bool(getattr(prefs, "ui_header_underline", False)))
        prefs.ui_item_underline = _b("item_underline", bool(getattr(prefs, "ui_item_underline", False)))
        prefs.ui_tooltip_underline = _b("tooltip_underline", bool(getattr(prefs, "ui_tooltip_underline", False)))

        prefs.ui_header_color = _vec3("header_color", getattr(prefs, "ui_header_color", (0.4898492097854614, 0.4898492097854614, 0.4898492097854614)))
        prefs.ui_header_alpha = _f("header_alpha", float(getattr(prefs, "ui_header_alpha", 1.0)))

        prefs.ui_item_color = _vec3("item_color", getattr(prefs, "ui_item_color", (0.8064299821853638, 0.8064299821853638, 0.8064299821853638)))
        prefs.ui_item_alpha = _f("item_alpha", float(getattr(prefs, "ui_item_alpha", 1.0)))

        prefs.ui_bg_color = _vec3("bg_color", getattr(prefs, "ui_bg_color", (0.04551559314131737, 0.04551559314131737, 0.04551559314131737)))
        prefs.ui_bg_alpha = _f("bg_alpha", float(getattr(prefs, "ui_bg_alpha", 0.9399999976158142)))

        prefs.ui_border_color = _vec3("border_color", getattr(prefs, "ui_border_color", (1.0, 1.0, 1.0)))
        prefs.ui_border_alpha = _f("border_alpha", float(getattr(prefs, "ui_border_alpha", 0.07000000029802322)))
        prefs.ui_border_thickness = _i("border_thickness", int(getattr(prefs, "ui_border_thickness", 0)))

        prefs.ui_radius = _i("radius", int(getattr(prefs, "ui_radius", 5)))

        prefs.ui_sep_color = _vec3("sep_color", getattr(prefs, "ui_sep_color", (0.19370141625404358, 0.19370141625404358, 0.19370141625404358)))
        prefs.ui_sep_alpha = _f("sep_alpha", float(getattr(prefs, "ui_sep_alpha", 0.0)))
        prefs.ui_sep_thickness = _i("sep_thickness", int(getattr(prefs, "ui_sep_thickness", 1)))

        prefs.ui_hover_color = _vec3("hover_color", getattr(prefs, "ui_hover_color", (0.42472410202026367, 0.42472410202026367, 0.42472410202026367)))
        prefs.ui_hover_alpha = _f("hover_alpha", float(getattr(prefs, "ui_hover_alpha", 0.10000000149011612)))

        prefs.ui_shadow_offset_x = _i("shadow_offset_x", int(getattr(prefs, "ui_shadow_offset_x", 3)))
        prefs.ui_shadow_offset_y = _i("shadow_offset_y", int(getattr(prefs, "ui_shadow_offset_y", -3)))
        prefs.ui_shadow_alpha = _f("shadow_alpha", float(getattr(prefs, "ui_shadow_alpha", 0.15000000596046448)))

        prefs.ui_line_height = _i("line_height", int(getattr(prefs, "ui_line_height", 22)))
        prefs.ui_panel_pad_x = _i("panel_pad_x", int(getattr(prefs, "ui_panel_pad_x", 16)))
        prefs.ui_panel_pad_y = _i("panel_pad_y", int(getattr(prefs, "ui_panel_pad_y", 12)))
        prefs.ui_header_pad_y = _i("header_pad_y", int(getattr(prefs, "ui_header_pad_y", 6)))
        prefs.ui_item_pad_y = _i("item_pad_y", int(getattr(prefs, "ui_item_pad_y", 0)))
        prefs.ui_sep_pad_y = _i("sep_pad_y", int(getattr(prefs, "ui_sep_pad_y", 1)))

        prefs.ui_tooltip_text_color = _vec3("tooltip_text_color", getattr(prefs, "ui_tooltip_text_color", (0.92, 0.92, 0.92)))
        prefs.ui_tooltip_text_alpha = _f("tooltip_text_alpha", float(getattr(prefs, "ui_tooltip_text_alpha", 1.0)))

        prefs.ui_tooltip_bg_color = _vec3("tooltip_bg_color", getattr(prefs, "ui_tooltip_bg_color", (0.03, 0.03, 0.03)))
        prefs.ui_tooltip_bg_alpha = _f("tooltip_bg_alpha", float(getattr(prefs, "ui_tooltip_bg_alpha", 0.95)))

        prefs.ui_tooltip_border_color = _vec3("tooltip_border_color", getattr(prefs, "ui_tooltip_border_color", (1.0, 1.0, 1.0)))
        prefs.ui_tooltip_border_alpha = _f("tooltip_border_alpha", float(getattr(prefs, "ui_tooltip_border_alpha", 0.10)))
        prefs.ui_tooltip_border_thickness = _i("tooltip_border_thickness", int(getattr(prefs, "ui_tooltip_border_thickness", 1)))

        prefs.ui_tooltip_radius = _i("tooltip_radius", int(getattr(prefs, "ui_tooltip_radius", 6)))

        prefs.ui_tooltip_shadow_offset_x = _i("tooltip_shadow_offset_x", int(getattr(prefs, "ui_tooltip_shadow_offset_x", 2)))
        prefs.ui_tooltip_shadow_offset_y = _i("tooltip_shadow_offset_y", int(getattr(prefs, "ui_tooltip_shadow_offset_y", -2)))
        prefs.ui_tooltip_shadow_alpha = _f("tooltip_shadow_alpha", float(getattr(prefs, "ui_tooltip_shadow_alpha", 0.25)))

        prefs.ui_tooltip_pad = _i("tooltip_pad", int(getattr(prefs, "ui_tooltip_pad", 10)))
        prefs.ui_tooltip_max_w = _i("tooltip_max_w", int(getattr(prefs, "ui_tooltip_max_w", 420)))
        prefs.ui_tooltip_offset_x = _i("tooltip_offset_x", int(getattr(prefs, "ui_tooltip_offset_x", 18)))
        prefs.ui_tooltip_offset_y = _i("tooltip_offset_y", int(getattr(prefs, "ui_tooltip_offset_y", -18)))
        prefs.ui_tooltip_line_height = _i("tooltip_line_height", int(getattr(prefs, "ui_tooltip_line_height", 0)))

    try:
        prefs.modes.clear()
    except Exception:
        for i in range(len(prefs.modes) - 1, -1, -1):
            prefs.modes.remove(i)

    modes_in = data.get("modes", [])
    if not isinstance(modes_in, list):
        modes_in = []

    m_map = {}
    for mdata in modes_in:
        try:
            mk = str(mdata.get("mode_key", "OBJECT")).strip().upper()
        except Exception:
            mk = "OBJECT"
        m_map[mk] = mdata

    for mk in DEFAULT_MODES:
        m = prefs.modes.add()
        m.mode_key = mk

        mdata = m_map.get(mk, {})
        m.active_section_index = int(mdata.get("active_section_index", 0))

        sections = mdata.get("sections", [])
        if not isinstance(sections, list) or not sections:
            s = m.sections.add()
            s.title = "Section"
            if hasattr(s, "popup_slot"):
                s.popup_slot = "TOP"
            s.active_item_index = 0
        else:
            for sdata in sections:
                s = m.sections.add()
                s.title = str(sdata.get("title", "Section"))

                if hasattr(s, "popup_slot"):
                    slot = str(sdata.get("popup_slot", "TOP")).strip().upper()
                    s.popup_slot = slot if slot in {"TOP", "LEFT", "RIGHT", "BOTTOM"} else "TOP"

                items = sdata.get("items", [])
                if isinstance(items, list):
                    for itdata in items:
                        it = s.items.add()
                        it.type = str(itdata.get("type", "OP"))
                        it.text = str(itdata.get("text", ""))
                        it.tooltip = str(itdata.get("tooltip", ""))
                        if hasattr(it, "icon_name"):
                            it.icon_name = str(itdata.get("icon_name", ""))
                        if hasattr(it, "icon_value"):
                            it.icon_value = max(0, int(itdata.get("icon_value", 0) or 0))

                        it.op_idname = str(itdata.get("op_idname", ""))
                        it.op_expr = str(itdata.get("op_expr", ""))

                        it.menu_idname = str(itdata.get("menu_idname", ""))
                        it.menu_call = str(itdata.get("menu_call", "call_menu"))

                        it.owner_expr = str(itdata.get("owner_expr", ""))
                        it.prop_id = str(itdata.get("prop_id", ""))
                        it.prop_action = str(itdata.get("prop_action", "TOGGLE"))
                        it.prop_value = str(itdata.get("prop_value", ""))
                        if hasattr(it, "script_code"):
                            it.script_code = str(itdata.get("script_code", ""))

                s.active_item_index = int(sdata.get("active_item_index", 0))

        if m.sections:
            m.active_section_index = max(0, min(m.active_section_index, len(m.sections) - 1))
        else:
            m.active_section_index = 0

    prefs.active_mode_index = int(data.get("active_mode_index", 1))
    prefs.active_mode_index = max(0, min(prefs.active_mode_index, len(prefs.modes) - 1))

    ensure_default_config(prefs)


def load_config_into_prefs(prefs):
    data = safe_read_json(config_path())
    if data:
        dict_to_prefs(prefs, data)
    else:
        ensure_default_config(prefs)
        save_config_now()

    ensure_default_config(prefs)
    for m in prefs.modes:
        if not m.sections:
            s = m.sections.add()
            s.title = "Section"
            if hasattr(s, "popup_slot"):
                s.popup_slot = "TOP"
            m.active_section_index = 0
