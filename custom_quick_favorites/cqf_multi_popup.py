# cqf_multi_popup.py
import bpy
from bpy.types import Operator

import gpu
import blf
from gpu_extras.batch import batch_for_shader

from .cqf_config import get_prefs, ensure_default_config, get_mode_key_from_context


SLOT_TOP = "TOP"
SLOT_LEFT = "LEFT"
SLOT_RIGHT = "RIGHT"
SLOT_BOTTOM = "BOTTOM"
ALL_SLOTS = (SLOT_TOP, SLOT_LEFT, SLOT_RIGHT, SLOT_BOTTOM)


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


def _slot_of_section(sec):
    try:
        v = (getattr(sec, "popup_slot", "") or "").strip().upper()
        return v if v in ALL_SLOTS else SLOT_TOP
    except Exception:
        return SLOT_TOP


def _sections_indices_by_slot(mode_cfg):
    out = {s: [] for s in ALL_SLOTS}
    if not mode_cfg or not getattr(mode_cfg, "sections", None):
        return out
    for idx, sec in enumerate(mode_cfg.sections):
        out[_slot_of_section(sec)].append(idx)
    return out


def _get_prop_value(it):
    try:
        owner_expr = (it.owner_expr or "").strip()
        prop_id = (it.prop_id or "").strip()
        if not owner_expr or not prop_id:
            return False, None

        owner = eval(owner_expr, {"bpy": bpy, "context": bpy.context})
        if owner is None:
            return False, None

        try:
            value = getattr(owner, prop_id)
        except Exception:
            return False, None

        return True, value
    except Exception:
        return False, None


def _icon_text_for_item(it) -> str:
    t = (it.type or "").strip().upper()

    if t == "OP":
        return "▶"

    if t == "MENU":
        return "≡"

    if t == "PROP":
        ok, value = _get_prop_value(it)

        if ok and isinstance(value, bool):
            return "☑" if value else "☐"

        # fallback if not bool
        return "☐"

    if t == "SCRIPT":
        return "✦"

    return ""


def _build_slot_entries(mode_cfg, slot_key: str):
    entries = []
    if not mode_cfg or not mode_cfg.sections:
        return entries

    for si, sec in enumerate(mode_cfg.sections):
        if _slot_of_section(sec) != slot_key:
            continue

        title = (sec.title or "").strip()
        if title:
            entries.append({"kind": "HEADER", "label": title, "payload": None})

        for ii, it in enumerate(sec.items):
            if it.type == "SEP":
                entries.append({"kind": "SEP", "label": "", "payload": None})
                continue

            label = (it.text or "").strip()
            if not label:
                if it.type == "OP":
                    label = (it.op_idname or it.op_expr or "Operator").strip()
                elif it.type == "MENU":
                    label = (it.menu_idname or "Menu").strip()
                elif it.type == "SCRIPT":
                    label = "Custom Script"
                else:
                    label = (f"{it.owner_expr}.{it.prop_id}" if it.owner_expr else it.prop_id).strip() or "Property"

            entries.append({
                "kind": "ITEM",
                "label": label,
                "icon_text": _icon_text_for_item(it),
                "tooltip": (it.tooltip or "").strip(),
                "payload": (mode_cfg.mode_key, si, ii),
            })

        entries.append({"kind": "SPACE", "label": "", "payload": None})

    while entries and entries[-1]["kind"] in {"SPACE", "SEP"}:
        entries.pop()

    return entries


class CQF_OT_OpenQuadMenu(Operator):
    bl_idname = "cqf.open_menu_quad"
    bl_label = "Open Custom Quick Favorites (Quad)"
    bl_options = {'INTERNAL'}

    DEFAULT_LINE_H = 22
    DEFAULT_PAD_X = 16
    DEFAULT_PAD_Y = 12

    PANEL_MIN_W = 240
    PANEL_MAX_W = 420
    PANEL_MAX_H = 520

    GAP = 18
    SAFE_PAD = 10
    _active_instance = None

    def _reset_state(self):
        self._handle = None
        self._area = None
        self._region = None

        self._mx = 0
        self._my = 0
        self._origin = (0, 0)

        self._prefs = None
        self._mode_cfg = None

        self._slot_entries = {s: [] for s in ALL_SLOTS}
        self._panels = {}

        self._hit_by_slot = {s: [] for s in ALL_SLOTS}
        self._hover_by_slot = {s: -1 for s in ALL_SLOTS}

        self._finished = False

        self._shader = None
        self._style = None
        self._toggle_key = None

    # ---------------- Font style helpers ----------------

    def _blf_opt(self, names):
        for n in names:
            if hasattr(blf, n):
                return getattr(blf, n)
        return None

    def _apply_font_style(self, font_id: int, bold: bool, italic: bool, underline: bool):
        """
        BLF supports a few style toggles depending on Blender build.
        We try multiple constant names for robustness.
        """
        try:
            bold_opt = self._blf_opt(["BOLD", "BLF_BOLD"])
            italic_opt = self._blf_opt(["ITALIC", "BLF_ITALIC"])
            underline_opt = self._blf_opt(["UNDERLINE", "BLF_UNDERLINE"])
            if bold_opt is not None:
                (blf.enable if bold else blf.disable)(font_id, bold_opt)
            if italic_opt is not None:
                (blf.enable if italic else blf.disable)(font_id, italic_opt)
            if underline_opt is not None:
                (blf.enable if underline else blf.disable)(font_id, underline_opt)
        except Exception:
            pass

    def _weight_to_bold(self, weight: int) -> bool:
        try:
            return int(weight) >= 600
        except Exception:
            return False

    def _read_style(self):
        p = self._prefs
        if not p:
            return {
                "header_size": 15,
                "item_size": 14,

                "header_weight": 400,
                "item_weight": 400,
                "tooltip_weight": 400,

                "header_bold": False,
                "item_bold": False,
                "tooltip_bold": False,

                "header_italic": False,
                "item_italic": False,
                "tooltip_italic": False,

                "header_underline": False,
                "item_underline": False,
                "tooltip_underline": False,

                "header_rgba": (0.4898492097854614, 0.4898492097854614, 0.4898492097854614, 1.0),
                "item_rgba": (0.8064299821853638, 0.8064299821853638, 0.8064299821853638, 1.0),

                "bg_rgba": (0.04551559314131737, 0.04551559314131737, 0.04551559314131737, 0.9399999976158142),
                "border_rgba": (1.0, 1.0, 1.0, 0.07000000029802322),
                "border_thickness": 0,
                "radius": 5,

                "sep_rgba": (0.19370141625404358, 0.19370141625404358, 0.19370141625404358, 0.0),
                "sep_thickness": 1,
                "hover_rgba": (0.42472410202026367, 0.42472410202026367, 0.42472410202026367, 0.10000000149011612),

                "shadow_off": (3, -3),
                "shadow_alpha": 0.15000000596046448,

                "line_h": 22,
                "pad_x": 16,
                "pad_y": 12,
                "header_pad_y": 6,
                "item_pad_y": 0,
                "sep_pad_y": 1,

                # Tooltip
                "tooltip_size": 12,
                "tooltip_text_rgba": (0.92, 0.92, 0.92, 1.0),
                "tooltip_bg_rgba": (0.03, 0.03, 0.03, 0.95),
                "tooltip_border_rgba": (1.0, 1.0, 1.0, 0.10),
                "tooltip_border_thickness": 1,
                "tooltip_radius": 6,
                "tooltip_shadow_off": (2, -2),
                "tooltip_shadow_alpha": 0.25,
                "tooltip_pad": 10,
                "tooltip_max_w": 420,
                "tooltip_offset_x": 18,
                "tooltip_offset_y": -18,
                "tooltip_line_h": 0,
            }

        def _rgba(rgb, a):
            try:
                return (float(rgb[0]), float(rgb[1]), float(rgb[2]), float(a))
            except Exception:
                return (1.0, 1.0, 1.0, 1.0)

        header_size = int(getattr(p, "ui_header_font_size", 15))
        item_size = int(getattr(p, "ui_item_font_size", 14))
        tooltip_size = int(getattr(p, "ui_tooltip_font_size", 12))

        header_weight = int(getattr(p, "ui_header_font_weight", 400))
        item_weight = int(getattr(p, "ui_item_font_weight", 400))
        tooltip_weight = int(getattr(p, "ui_tooltip_font_weight", 400))

        header_bold = bool(getattr(p, "ui_header_bold", False)) or self._weight_to_bold(header_weight)
        item_bold = bool(getattr(p, "ui_item_bold", False)) or self._weight_to_bold(item_weight)
        tooltip_bold = bool(getattr(p, "ui_tooltip_bold", False)) or self._weight_to_bold(tooltip_weight)

        header_italic = bool(getattr(p, "ui_header_italic", False))
        item_italic = bool(getattr(p, "ui_item_italic", False))
        tooltip_italic = bool(getattr(p, "ui_tooltip_italic", False))

        header_underline = bool(getattr(p, "ui_header_underline", False))
        item_underline = bool(getattr(p, "ui_item_underline", False))
        tooltip_underline = bool(getattr(p, "ui_tooltip_underline", False))

        header_rgba = _rgba(getattr(p, "ui_header_color", (0.4898492097854614, 0.4898492097854614, 0.4898492097854614)), getattr(p, "ui_header_alpha", 1.0))
        item_rgba = _rgba(getattr(p, "ui_item_color", (0.8064299821853638, 0.8064299821853638, 0.8064299821853638)), getattr(p, "ui_item_alpha", 1.0))
        bg_rgba = _rgba(getattr(p, "ui_bg_color", (0.04551559314131737, 0.04551559314131737, 0.04551559314131737)), getattr(p, "ui_bg_alpha", 0.9399999976158142))
        border_rgba = _rgba(getattr(p, "ui_border_color", (1.0, 1.0, 1.0)), getattr(p, "ui_border_alpha", 0.07000000029802322))

        border_thickness = int(getattr(p, "ui_border_thickness", 0))
        radius = int(getattr(p, "ui_radius", 5))

        sep_rgba = _rgba(getattr(p, "ui_sep_color", (0.19370141625404358, 0.19370141625404358, 0.19370141625404358)), getattr(p, "ui_sep_alpha", 0.0))
        sep_thickness = int(getattr(p, "ui_sep_thickness", 1))

        hover_rgba = _rgba(getattr(p, "ui_hover_color", (0.42472410202026367, 0.42472410202026367, 0.42472410202026367)), getattr(p, "ui_hover_alpha", 0.10000000149011612))

        shadow_off = (int(getattr(p, "ui_shadow_offset_x", 3)), int(getattr(p, "ui_shadow_offset_y", -3)))
        shadow_alpha = float(getattr(p, "ui_shadow_alpha", 0.15000000596046448))

        line_h = int(getattr(p, "ui_line_height", 22))
        pad_x = int(getattr(p, "ui_panel_pad_x", 16))
        pad_y = int(getattr(p, "ui_panel_pad_y", 12))
        header_pad_y = int(getattr(p, "ui_header_pad_y", 6))
        item_pad_y = int(getattr(p, "ui_item_pad_y", 0))
        sep_pad_y = int(getattr(p, "ui_sep_pad_y", 1))

        # Tooltip appearance from prefs
        tooltip_text_rgba = _rgba(getattr(p, "ui_tooltip_text_color", (0.92, 0.92, 0.92)), getattr(p, "ui_tooltip_text_alpha", 1.0))
        tooltip_bg_rgba = _rgba(getattr(p, "ui_tooltip_bg_color", (0.03, 0.03, 0.03)), getattr(p, "ui_tooltip_bg_alpha", 0.95))
        tooltip_border_rgba = _rgba(getattr(p, "ui_tooltip_border_color", (1.0, 1.0, 1.0)), getattr(p, "ui_tooltip_border_alpha", 0.10))
        tooltip_border_thickness = int(getattr(p, "ui_tooltip_border_thickness", 1))
        tooltip_radius = int(getattr(p, "ui_tooltip_radius", 6))
        tooltip_shadow_off = (int(getattr(p, "ui_tooltip_shadow_offset_x", 2)), int(getattr(p, "ui_tooltip_shadow_offset_y", -2)))
        tooltip_shadow_alpha = float(getattr(p, "ui_tooltip_shadow_alpha", 0.25))
        tooltip_pad = int(getattr(p, "ui_tooltip_pad", 10))
        tooltip_max_w = int(getattr(p, "ui_tooltip_max_w", 420))
        tooltip_offset_x = int(getattr(p, "ui_tooltip_offset_x", 18))
        tooltip_offset_y = int(getattr(p, "ui_tooltip_offset_y", -18))
        tooltip_line_h = int(getattr(p, "ui_tooltip_line_height", 0))

        return {
            "header_size": max(8, header_size),
            "item_size": max(8, item_size),

            "header_weight": max(100, min(900, header_weight)),
            "item_weight": max(100, min(900, item_weight)),
            "tooltip_weight": max(100, min(900, tooltip_weight)),

            "header_bold": bool(header_bold),
            "item_bold": bool(item_bold),
            "tooltip_bold": bool(tooltip_bold),

            "header_italic": bool(header_italic),
            "item_italic": bool(item_italic),
            "tooltip_italic": bool(tooltip_italic),

            "header_underline": bool(header_underline),
            "item_underline": bool(item_underline),
            "tooltip_underline": bool(tooltip_underline),

            "header_rgba": header_rgba,
            "item_rgba": item_rgba,
            "bg_rgba": bg_rgba,
            "border_rgba": border_rgba,
            "border_thickness": max(0, border_thickness),
            "radius": max(0, radius),
            "sep_rgba": sep_rgba,
            "sep_thickness": max(1, sep_thickness),
            "hover_rgba": hover_rgba,
            "shadow_off": shadow_off,
            "shadow_alpha": max(0.0, min(1.0, shadow_alpha)),
            "line_h": max(16, line_h),
            "pad_x": max(6, pad_x),
            "pad_y": max(4, pad_y),
            "header_pad_y": max(0, header_pad_y),
            "item_pad_y": max(0, item_pad_y),
            "sep_pad_y": max(0, sep_pad_y),

            "tooltip_size": max(8, tooltip_size),
            "tooltip_text_rgba": tooltip_text_rgba,
            "tooltip_bg_rgba": tooltip_bg_rgba,
            "tooltip_border_rgba": tooltip_border_rgba,
            "tooltip_border_thickness": max(0, tooltip_border_thickness),
            "tooltip_radius": max(0, tooltip_radius),
            "tooltip_shadow_off": tooltip_shadow_off,
            "tooltip_shadow_alpha": max(0.0, min(1.0, tooltip_shadow_alpha)),
            "tooltip_pad": max(2, tooltip_pad),
            "tooltip_max_w": max(120, tooltip_max_w),
            "tooltip_offset_x": tooltip_offset_x,
            "tooltip_offset_y": tooltip_offset_y,
            "tooltip_line_h": max(0, tooltip_line_h),
        }

    def invoke(self, context, event):
        current = CQF_OT_OpenQuadMenu._active_instance
        if current and not getattr(current, "_finished", True):
            current._finish(context)
            return {'CANCELLED'}

        self._reset_state()

        if not context.area or context.area.type != "VIEW_3D":
            bpy.ops.wm.call_menu(name="CQF_MT_favorites_menu")
            return {'FINISHED'}

        self._prefs = get_prefs()
        ensure_default_config(self._prefs)
        self._style = self._read_style()

        self._mode_cfg = _mode_for_context(self._prefs, context)

        self._area = context.area
        self._region = context.region

        self._mx = int(event.mouse_region_x)
        self._my = int(event.mouse_region_y)
        self._origin = (self._mx, self._my)
        self._toggle_key = {
            "type": event.type,
            "shift": bool(event.shift),
            "ctrl": bool(event.ctrl),
            "alt": bool(event.alt),
            "oskey": bool(event.oskey),
        }

        by_slot = _sections_indices_by_slot(self._mode_cfg)
        for s in ALL_SLOTS:
            if len(by_slot.get(s, [])) > 0:
                self._slot_entries[s] = _build_slot_entries(self._mode_cfg, s)
            else:
                self._slot_entries[s] = []

        if all(len(self._slot_entries[s]) == 0 for s in ALL_SLOTS):
            self._slot_entries[SLOT_TOP] = [{"kind": "HEADER", "label": "No configuration found.", "payload": None}]

        self._rebuild_layout(context)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_callback, (context,), 'WINDOW', 'POST_PIXEL'
        )
        CQF_OT_OpenQuadMenu._active_instance = self

        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if self._finished:
            return {'FINISHED'}

        if not context.area or context.area != self._area:
            self._finish(context)
            return {'CANCELLED'}

        if event.type in {'ESC'}:
            self._finish(context)
            return {'CANCELLED'}

        tk = self._toggle_key or {}
        if (
            event.value == 'PRESS'
            and event.type == tk.get("type")
            and bool(event.shift) == tk.get("shift")
            and bool(event.ctrl) == tk.get("ctrl")
            and bool(event.alt) == tk.get("alt")
            and bool(event.oskey) == tk.get("oskey")
        ):
            self._finish(context)
            return {'CANCELLED'}

        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self._finish(context)
            return {'CANCELLED'}

        if event.type == 'MOUSEMOVE':
            self._mx = int(event.mouse_region_x)
            self._my = int(event.mouse_region_y)
            self._update_hover()
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            slot, idx = self._pick_hovered()
            if slot and idx is not None:
                hits = self._hit_by_slot.get(slot, [])
                if 0 <= idx < len(hits):
                    payload = hits[idx].get("payload")
                    if payload:
                        mode_key, section_index, item_index = payload
                        try:
                            bpy.ops.cqf.run_item(mode_key=mode_key, section_index=section_index, item_index=item_index)
                        except Exception:
                            pass
                        self._finish(context)
                        return {'FINISHED'}

            self._finish(context)
            return {'CANCELLED'}

        if event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'MIDDLEMOUSE'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    # --------- Layout & hit testing ---------

    def _measure_text(self, text: str, size: int):
        try:
            blf.size(0, size)
            w, h = blf.dimensions(0, text)
            return float(w), float(h)
        except Exception:
            return 0.0, 0.0

    def _panel_size_for_entries(self, entries):
        if not entries:
            return (0, 0)

        style = self._style or self._read_style()
        header_size = style["header_size"]
        item_size = style["item_size"]
        pad_x = style["pad_x"]
        pad_y = style["pad_y"]
        line_h = style["line_h"]

        maxw = 0
        lines = 0

        for e in entries:
            k = e["kind"]
            if k in {"SPACE", "SEP"}:
                lines += 1
                continue

            label = e.get("label", "")
            size = header_size if k == "HEADER" else item_size

            if k == "ITEM":
                icon_txt = e.get("icon_text", "")
                if icon_txt:
                    iw, _ = self._measure_text(icon_txt + " ", size)
                else:
                    iw = 0.0
                w, _ = self._measure_text(label, size)
                maxw = max(maxw, iw + w)
            else:
                w, _ = self._measure_text(label, size)
                maxw = max(maxw, w)

            lines += 1

        w = int(max(self.PANEL_MIN_W, min(self.PANEL_MAX_W, maxw + pad_x * 2)))
        h = int(min(self.PANEL_MAX_H, lines * line_h + pad_y * 2))
        return (w, h)

    def _clamp_panel_in_region(self, x, y, w, h, reg_w, reg_h, pad=None):
        if pad is None:
            pad = self.SAFE_PAD
        x = max(pad, min(int(x), int(reg_w - w - pad)))
        y = max(pad, min(int(y), int(reg_h - h - pad)))
        return x, y

    @staticmethod
    def _rects_overlap(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)

    def _resolve_overlaps(self, panels, reg_w, reg_h):
        def push_dir(slot):
            if slot == SLOT_TOP:
                return (0, 1)
            if slot == SLOT_BOTTOM:
                return (0, -1)
            if slot == SLOT_LEFT:
                return (-1, 0)
            if slot == SLOT_RIGHT:
                return (1, 0)
            return (0, 1)

        order = [SLOT_TOP, SLOT_LEFT, SLOT_RIGHT, SLOT_BOTTOM]

        for _ in range(14):
            changed = False
            for si in order:
                if si not in panels:
                    continue
                xi, yi, wi, hi = panels[si]
                ri = (xi, yi, wi, hi)

                for sj in order:
                    if sj == si or sj not in panels:
                        continue
                    rj = panels[sj]
                    if not self._rects_overlap(ri, rj):
                        continue

                    dx, dy = push_dir(si)
                    step = 14
                    xi += dx * step
                    yi += dy * step
                    xi, yi = self._clamp_panel_in_region(xi, yi, wi, hi, reg_w, reg_h)
                    panels[si] = (xi, yi, wi, hi)
                    ri = (xi, yi, wi, hi)
                    changed = True

            if not changed:
                break

        return panels

    def _rebuild_layout(self, context):
        reg_w = int(self._region.width)
        reg_h = int(self._region.height)
        ox, oy = self._origin

        sizes = {s: self._panel_size_for_entries(self._slot_entries[s]) for s in ALL_SLOTS}
        panels = {}

        if sizes[SLOT_TOP] != (0, 0):
            w, h = sizes[SLOT_TOP]
            x = ox - w // 2
            y = oy + self.GAP
            x, y = self._clamp_panel_in_region(x, y, w, h, reg_w, reg_h)
            panels[SLOT_TOP] = (x, y, w, h)

        if sizes[SLOT_BOTTOM] != (0, 0):
            w, h = sizes[SLOT_BOTTOM]
            x = ox - w // 2
            y = oy - self.GAP - h
            x, y = self._clamp_panel_in_region(x, y, w, h, reg_w, reg_h)
            panels[SLOT_BOTTOM] = (x, y, w, h)

        if sizes[SLOT_LEFT] != (0, 0):
            w, h = sizes[SLOT_LEFT]
            x = ox - self.GAP - w
            y = oy - h // 2
            x, y = self._clamp_panel_in_region(x, y, w, h, reg_w, reg_h)
            panels[SLOT_LEFT] = (x, y, w, h)

        if sizes[SLOT_RIGHT] != (0, 0):
            w, h = sizes[SLOT_RIGHT]
            x = ox + self.GAP
            y = oy - h // 2
            x, y = self._clamp_panel_in_region(x, y, w, h, reg_w, reg_h)
            panels[SLOT_RIGHT] = (x, y, w, h)

        panels = self._resolve_overlaps(panels, reg_w, reg_h)
        self._panels = panels

        self._hit_by_slot = {s: [] for s in ALL_SLOTS}
        for slot, rect in self._panels.items():
            x, y, w, h = rect
            entries = self._slot_entries.get(slot, [])
            self._hit_by_slot[slot] = self._build_hits_for_panel(slot, x, y, w, h, entries)

        self._update_hover()

    def _build_hits_for_panel(self, slot, x, y, w, h, entries):
        style = self._style or self._read_style()
        pad_y = style["pad_y"]
        line_h = style["line_h"]

        hits = []
        cy_top = y + h - pad_y
        for e in entries:
            kind = e["kind"]
            row_y_bot = cy_top - line_h

            if kind == "ITEM":
                rect = (x + 6, row_y_bot + 2, w - 12, line_h - 4)
                hits.append({
                    "rect": rect,
                    "payload": e.get("payload"),
                    "label": e.get("label", ""),
                    "tooltip": e.get("tooltip", ""),
                })

            cy_top -= line_h
        return hits

    def _update_hover(self):
        mx, my = self._mx, self._my
        self._hover_by_slot = {s: -1 for s in ALL_SLOTS}

        for slot, hits in self._hit_by_slot.items():
            for i, it in enumerate(hits):
                rx, ry, rw, rh = it["rect"]
                if (mx >= rx) and (mx <= rx + rw) and (my >= ry) and (my <= ry + rh):
                    self._hover_by_slot[slot] = i
                    return

    def _pick_hovered(self):
        for slot in ALL_SLOTS:
            idx = self._hover_by_slot.get(slot, -1)
            if idx is not None and idx >= 0:
                return slot, idx
        return None, None

    # --------- Drawing helpers ---------

    def _get_uniform_shader(self):
        if self._shader is not None:
            return self._shader
        for name in ("UNIFORM_COLOR", "FLAT_COLOR"):
            try:
                self._shader = gpu.shader.from_builtin(name)
                return self._shader
            except Exception:
                continue
        self._shader = None
        return None

    @staticmethod
    def _rounded_rect_verts(x, y, w, h, r, seg=8):
        r = max(0.0, min(float(r), min(float(w), float(h)) * 0.5))
        if r <= 0.01:
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]

        import math

        def arc(cx, cy, a0, a1):
            pts = []
            for i in range(seg + 1):
                t = i / seg
                a = a0 + (a1 - a0) * t
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
            return pts

        tr = arc(x + w - r, y + h - r, 0.0, math.pi * 0.5)
        tl = arc(x + r, y + h - r, math.pi * 0.5, math.pi)
        bl = arc(x + r, y + r, math.pi, math.pi * 1.5)
        br = arc(x + w - r, y + r, math.pi * 1.5, math.pi * 2.0)

        verts = []
        verts += tr[:-1]
        verts += tl[:-1]
        verts += bl[:-1]
        verts += br[:-1]
        return [(float(px), float(py)) for (px, py) in verts]

    def _draw_rounded_rect(self, x, y, w, h, r, color):
        shader = self._get_uniform_shader()
        if shader is None:
            return

        verts = self._rounded_rect_verts(x, y, w, h, r, seg=10)
        indices = []
        for i in range(1, len(verts) - 1):
            indices.append((0, i, i + 1))

        batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def _draw_rounded_border(self, x, y, w, h, r, color, thickness=1):
        shader = self._get_uniform_shader()
        if shader is None:
            return

        verts = self._rounded_rect_verts(x, y, w, h, r, seg=10)
        verts2 = verts + [verts[0]]

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": verts2})
        shader.bind()
        shader.uniform_float("color", color)
        try:
            gpu.state.line_width_set(max(1, int(thickness)))
        except Exception:
            pass
        batch.draw(shader)
        try:
            gpu.state.line_width_set(1)
        except Exception:
            pass

    def _draw_text(self, x, y, text, size, color, bold=False, italic=False, underline=False):
        font_id = 0
        blf.size(font_id, size)
        self._apply_font_style(font_id, bold=bool(bold), italic=bool(italic), underline=bool(underline))
        blf.position(font_id, x, y, 0)
        blf.color(font_id, *color)
        blf.draw(font_id, text)

    def _draw_separator_line(self, x0, y, x1, sep_rgba, thickness=1):
        w = max(1, int(x1 - x0))
        t = max(1, int(thickness))
        self._draw_rounded_rect(x0, y, w, t, 0, sep_rgba)

    # --------- Tooltip ---------

    def _wrap_text(self, text: str, size: int, max_w: int):
        s = (text or "").strip()
        if not s:
            return []

        words = s.replace("\r\n", "\n").replace("\r", "\n").split()
        if not words:
            return []

        lines = []
        cur = ""
        for w in words:
            cand = (cur + " " + w).strip() if cur else w
            tw, _ = self._measure_text(cand, size)
            if tw <= max_w or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def _get_hover_tooltip(self):
        for slot in ALL_SLOTS:
            idx = self._hover_by_slot.get(slot, -1)
            if idx is None or idx < 0:
                continue
            hits = self._hit_by_slot.get(slot, [])
            if 0 <= idx < len(hits):
                tip = (hits[idx].get("tooltip", "") or "").strip()
                if tip:
                    return tip
        return ""

    def _draw_tooltip(self):
        if not self._region:
            return

        tip = self._get_hover_tooltip()
        if not tip:
            return

        style = self._style or self._read_style()

        font_size = int(style.get("tooltip_size", 12))
        pad = int(style.get("tooltip_pad", 10))
        max_text_w = int(style.get("tooltip_max_w", 420))
        off_x = int(style.get("tooltip_offset_x", 18))
        off_y = int(style.get("tooltip_offset_y", -18))

        lines = self._wrap_text(tip, font_size, max_text_w)
        if not lines:
            return

        # Measure tooltip size
        maxw = 0.0
        line_h = int(style.get("tooltip_line_h", 0))
        if line_h <= 0:
            line_h = max(14, int(font_size * 1.25))

        for ln in lines:
            w, _ = self._measure_text(ln, font_size)
            maxw = max(maxw, w)

        box_w = int(maxw + pad * 2)
        box_h = int(len(lines) * line_h + pad * 2)

        # Position near cursor
        x = int(self._mx + off_x)
        y = int(self._my + off_y - box_h)

        reg_w = int(self._region.width)
        reg_h = int(self._region.height)

        x = max(self.SAFE_PAD, min(x, reg_w - box_w - self.SAFE_PAD))
        y = max(self.SAFE_PAD, min(y, reg_h - box_h - self.SAFE_PAD))

        bg = style.get("tooltip_bg_rgba", (0.03, 0.03, 0.03, 0.95))
        border = style.get("tooltip_border_rgba", (1.0, 1.0, 1.0, 0.10))
        text_col = style.get("tooltip_text_rgba", (0.92, 0.92, 0.92, 1.0))
        radius = int(style.get("tooltip_radius", 6))
        border_th = int(style.get("tooltip_border_thickness", 1))
        sx, sy = style.get("tooltip_shadow_off", (2, -2))
        sh_a = float(style.get("tooltip_shadow_alpha", 0.25))

        # Shadow
        if sh_a > 0.0:
            self._draw_rounded_rect(x + sx, y + sy, box_w, box_h, radius, (0.0, 0.0, 0.0, sh_a))

        self._draw_rounded_rect(x, y, box_w, box_h, radius, bg)
        if border_th > 0 and border[3] > 0.0:
            self._draw_rounded_border(x, y, box_w, box_h, radius, border, thickness=border_th)

        tx = x + pad
        ty_top = y + box_h - pad - line_h

        bold = bool(style.get("tooltip_bold", False))
        italic = bool(style.get("tooltip_italic", False))
        underline = bool(style.get("tooltip_underline", False))

        for i, ln in enumerate(lines):
            self._draw_text(tx, ty_top - i * line_h, ln, font_size, text_col, bold=bold, italic=italic, underline=underline)

    # --------- Panel drawing ---------

    def _draw_panel(self, slot, rect, entries):
        style = self._style or self._read_style()

        x, y, w, h = rect
        pad_x = style["pad_x"]
        pad_y = style["pad_y"]
        line_h = style["line_h"]

        try:
            gpu.state.blend_set('ALPHA')
        except Exception:
            pass

        sx, sy = style["shadow_off"]
        a = float(style["shadow_alpha"])
        self._draw_rounded_rect(x + sx, y + sy, w, h, style["radius"], (0.0, 0.0, 0.0, a))

        self._draw_rounded_rect(x, y, w, h, style["radius"], style["bg_rgba"])

        if style["border_thickness"] > 0 and style["border_rgba"][3] > 0.0:
            self._draw_rounded_border(x, y, w, h, style["radius"], style["border_rgba"], thickness=style["border_thickness"])

        cx = x + pad_x
        cy_top = y + h - pad_y

        hover_idx = self._hover_by_slot.get(slot, -1)
        if hover_idx is not None and hover_idx >= 0:
            hits = self._hit_by_slot.get(slot, [])
            if 0 <= hover_idx < len(hits):
                rx, ry, rw, rh = hits[hover_idx]["rect"]
                self._draw_rounded_rect(rx, ry, rw, rh, 6, style["hover_rgba"])

        for e in entries:
            kind = e["kind"]
            label = e.get("label", "")
            row_y_bot = cy_top - line_h

            if kind == "HEADER":
                ytxt = row_y_bot + 6 + style["header_pad_y"]
                self._draw_text(
                    cx, ytxt, label,
                    style["header_size"], style["header_rgba"],
                    bold=style.get("header_bold", False),
                    italic=style.get("header_italic", False),
                    underline=style.get("header_underline", False),
                )

                sep_y = row_y_bot + 2 + style["sep_pad_y"]
                self._draw_separator_line(x + 10, sep_y, x + w - 10, style["sep_rgba"], thickness=style["sep_thickness"])

            elif kind == "SEP":
                sep_y = row_y_bot + (line_h // 2) - (style["sep_thickness"] // 2)
                sep_y += style["sep_pad_y"]
                self._draw_separator_line(x + 10, sep_y, x + w - 10, style["sep_rgba"], thickness=style["sep_thickness"])

            elif kind == "SPACE":
                pass

            elif kind == "ITEM":
                ytxt = row_y_bot + 6 + style["item_pad_y"]

                icon_txt = (e.get("icon_text") or "").strip()
                if icon_txt:
                    self._draw_text(
                        cx, ytxt, icon_txt,
                        style["item_size"], style["item_rgba"],
                        bold=style.get("item_bold", False),
                        italic=style.get("item_italic", False),
                        underline=style.get("item_underline", False),
                    )
                    iw, _ = self._measure_text(icon_txt + " ", style["item_size"])
                    self._draw_text(
                        cx + iw, ytxt, label,
                        style["item_size"], style["item_rgba"],
                        bold=style.get("item_bold", False),
                        italic=style.get("item_italic", False),
                        underline=style.get("item_underline", False),
                    )
                else:
                    self._draw_text(
                        cx, ytxt, label,
                        style["item_size"], style["item_rgba"],
                        bold=style.get("item_bold", False),
                        italic=style.get("item_italic", False),
                        underline=style.get("item_underline", False),
                    )

            cy_top -= line_h

    def _draw_callback(self, context):
        if self._finished or not self._region:
            return

        if context.area != self._area or context.region != self._region:
            return

        try:
            gpu.state.blend_set('ALPHA')
        except Exception:
            pass

        try:
            try:
                gpu.state.depth_test_set('NONE')
            except Exception:
                pass
            try:
                gpu.state.face_culling_set('NONE')
            except Exception:
                pass

            self._style = self._read_style()

            for slot in (SLOT_TOP, SLOT_LEFT, SLOT_RIGHT, SLOT_BOTTOM):
                rect = self._panels.get(slot)
                if not rect:
                    continue
                entries = self._slot_entries.get(slot, [])
                self._draw_panel(slot, rect, entries)

            # Tooltip on top
            self._draw_tooltip()

        except Exception as e:
            print("CQF DRAW ERROR:", repr(e))
        finally:
            try:
                gpu.state.blend_set('NONE')
            except Exception:
                pass

    def _finish(self, context):
        self._finished = True
        if CQF_OT_OpenQuadMenu._active_instance is self:
            CQF_OT_OpenQuadMenu._active_instance = None
        try:
            if self._handle is not None:
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except Exception:
            pass
        self._handle = None

        try:
            if self._area:
                self._area.tag_redraw()
        except Exception:
            pass


_CLASSES = (
    CQF_OT_OpenQuadMenu,
)


def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)
