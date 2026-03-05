import bpy

CAPTURE_KEY_TYPES = {'NINE', 'NUMPAD_9'}
CAPTURE_CTRL = True
CAPTURE_ALT = True
CAPTURE_SHIFT = True
CAPTURE_VALUE = 'PRESS'

_SENTINEL = "__CQF_SENTINEL__"


def op_idname_from_button_operator(button_operator):
    if button_operator is None:
        return None

    ident = None
    try:
        ident = button_operator.bl_rna.identifier
    except Exception:
        pass

    if not ident:
        try:
            ident = button_operator.idname()
        except Exception:
            pass

    if not ident or "_OT_" not in ident:
        return None

    mod, op = ident.split("_OT_", 1)
    return f"{mod.lower()}.{op.lower()}"


# ----------------------------------------------------------------------
# Robust UI copy helpers (ported from old script)
# ----------------------------------------------------------------------

def _try_call_with_override(context, op_callable, window=None, screen=None, area=None, region=None):
    try:
        override = {}
        if window:
            override["window"] = window
        if screen:
            override["screen"] = screen
        if area:
            override["area"] = area
        if region:
            override["region"] = region
        if override:
            with context.temp_override(**override):
                return op_callable()
        return op_callable()
    except Exception:
        return None


def _ui_copy_with_bruteforce_overrides(context, op_callable):
    """
    Crucial: header menus usually need region.type == 'HEADER' (not WINDOW).
    Also tries current area type first.
    """
    # 1) Try current context first
    res = _try_call_with_override(
        context,
        op_callable,
        window=getattr(context, "window", None),
        screen=getattr(context, "screen", None),
        area=getattr(context, "area", None),
        region=getattr(context, "region", None),
    )
    if res is not None:
        return res

    wm = getattr(context, "window_manager", None)
    if not wm:
        return None

    ctx_area = getattr(context, "area", None)
    ctx_area_type = getattr(ctx_area, "type", "") if ctx_area else ""

    region_priority = ["HEADER", "TOOL_HEADER", "UI", "WINDOW", "TOOLS", "CHANNELS", "TEMPORARY"]

    def sort_regions(regions):
        if not regions:
            return []
        def key(r):
            t = getattr(r, "type", "")
            return region_priority.index(t) if t in region_priority else (len(region_priority) + 10)
        return sorted(regions, key=key)

    def sort_areas(areas):
        if not areas:
            return []
        def key(a):
            t = getattr(a, "type", "")
            if ctx_area_type and t == ctx_area_type:
                return 0
            if t == "VIEW_3D":
                return 1
            return 2
        return sorted(areas, key=key)

    windows = list(getattr(wm, "windows", []))
    for win in windows:
        scr = getattr(win, "screen", None)
        if not scr:
            continue
        areas = sort_areas(list(getattr(scr, "areas", [])))
        for area in areas:
            regs = sort_regions(list(getattr(area, "regions", [])))
            for region in regs:
                res = _try_call_with_override(context, op_callable, window=win, screen=scr, area=area, region=region)
                if res is not None:
                    return res

    return None


def try_copy_python_command_button(context):
    """
    Returns a bpy.ops... command string if possible.
    Robust for header/menus via brute-force overrides.
    """
    wm = getattr(context, "window_manager", None)
    if not wm:
        return None

    old_clip = wm.clipboard
    try:
        wm.clipboard = _SENTINEL

        def _do_copy_btn():
            return bpy.ops.ui.copy_python_command_button()

        _ui_copy_with_bruteforce_overrides(context, _do_copy_btn)
        cmd = (wm.clipboard or "").strip()

        # Fallback: copy_python_command (works in some contexts where button one fails)
        if (not cmd) or (cmd == _SENTINEL):
            wm.clipboard = _SENTINEL

            def _do_copy_cmd():
                return bpy.ops.ui.copy_python_command()

            _ui_copy_with_bruteforce_overrides(context, _do_copy_cmd)
            cmd = (wm.clipboard or "").strip()

        if (not cmd) or (cmd == _SENTINEL):
            return None

        if cmd.startswith("bpy.ops."):
            return cmd
        return None

    except Exception:
        return None
    finally:
        wm.clipboard = old_clip


def _py_repr_for_value(v):
    try:
        return repr(v)
    except Exception:
        return "None"


def build_op_expr_from_keymap_item(kmi):
    if not kmi or not getattr(kmi, "idname", ""):
        return None

    idname = kmi.idname
    if "." not in idname:
        return f"bpy.ops.{idname}()"

    props = []
    try:
        props_rna = kmi.properties.bl_rna.properties
        for p in props_rna:
            pid = p.identifier
            if pid == "rna_type":
                continue
            try:
                val = getattr(kmi.properties, pid)
            except Exception:
                continue

            include = True
            if val is None:
                include = False
            elif isinstance(val, str) and val == "":
                include = False
            elif isinstance(val, (int, float)) and val == 0:
                include = False
            elif isinstance(val, bool) and val is False:
                include = False
            elif isinstance(val, (set, frozenset)) and len(val) == 0:
                include = False

            if include:
                props.append(f"{pid}={_py_repr_for_value(val)}")
    except Exception:
        props = []

    args = "(" + ", ".join(props) + ")" if props else "()"
    return f"bpy.ops.{idname}{args}"


def is_capture_combo(kmi):
    try:
        if getattr(kmi, "type", None) in (None, 'UNKNOWN'):
            return False
        return (
            kmi.type in CAPTURE_KEY_TYPES
            and kmi.value == CAPTURE_VALUE
            and bool(kmi.ctrl) == CAPTURE_CTRL
            and bool(kmi.alt) == CAPTURE_ALT
            and bool(kmi.shift) == CAPTURE_SHIFT
        )
    except Exception:
        return False


def extract_button_icon(context):
    """
    Best-effort icon extraction from the current UI button context.
    Returns (icon_name, icon_value).
    """
    icon_name = ""
    icon_value = 0

    try:
        raw_name = getattr(context, "button_icon", "")
        if raw_name:
            icon_name = str(raw_name)
    except Exception:
        pass

    try:
        raw_val = getattr(context, "button_icon_value", 0)
        if raw_val:
            icon_value = max(0, int(raw_val))
    except Exception:
        pass

    return icon_name, icon_value


def _remove_capture_combo_from_keyconfig(kc):
    removed = 0
    if not kc:
        return 0
    for km in kc.keymaps:
        for kmi in list(km.keymap_items):
            if is_capture_combo(kmi):
                try:
                    km.keymap_items.remove(kmi)
                    removed += 1
                except Exception:
                    pass
    return removed


def remove_capture_combo_everywhere():
    wm = bpy.context.window_manager
    if not wm:
        return 0
    removed = 0
    try:
        removed += _remove_capture_combo_from_keyconfig(wm.keyconfigs.user)
    except Exception:
        pass
    try:
        removed += _remove_capture_combo_from_keyconfig(wm.keyconfigs.addon)
    except Exception:
        pass
    return removed


def find_capture_combo_kmi():
    wm = bpy.context.window_manager
    if not wm:
        return None

    for kc in [wm.keyconfigs.user, wm.keyconfigs.addon]:
        if not kc:
            continue
        for km in kc.keymaps:
            for kmi in km.keymap_items:
                if is_capture_combo(kmi):
                    return kmi
    return None
