import bpy
from .cqf_safe import safe_eval

def normalize_datapath(raw: str):
    if not raw:
        return None

    p = raw.strip()

    if p.startswith("bpy."):
        return p

    stable_roots = (
        "scene.", "view_layer.", "tool_settings.", "preferences.", "workspace.",
        "window_manager.", "window.", "screen.", "area.", "space_data.", "region_data.",
        "object.", "active_object.",
    )
    for r in stable_roots:
        if p.startswith(r):
            return "bpy.context." + p

    if "areas[" in p and ".spaces[" in p and ".overlay." in p:
        after = p.split(".overlay.", 1)[1]
        return "bpy.context.space_data.overlay." + after

    if "areas[" in p and ".spaces[" in p and ".shading." in p:
        after = p.split(".shading.", 1)[1]
        return "bpy.context.space_data.shading." + after

    if "areas[" in p and ".spaces[" in p and ".region_3d." in p:
        after = p.split(".region_3d.", 1)[1]
        return "bpy.context.region_data." + after

    if "." in p:
        return "bpy.context." + p

    return p


def get_rna_prop(owner, prop_id):
    try:
        return owner.bl_rna.properties.get(prop_id, None)
    except Exception:
        return None


def enum_items_keys(rna_prop):
    try:
        return [it.identifier for it in rna_prop.enum_items]
    except Exception:
        return []


def is_enum_flag(rna_prop):
    try:
        return bool(getattr(rna_prop, "is_enum_flag", False))
    except Exception:
        return False


def cycle_enum(owner, prop_id, rna_prop):
    keys = enum_items_keys(rna_prop)
    if not keys:
        raise ValueError("Enum has no items")
    cur = getattr(owner, prop_id)
    if cur not in keys:
        setattr(owner, prop_id, keys[0])
        return
    i = keys.index(cur)
    nxt = keys[(i + 1) % len(keys)]
    setattr(owner, prop_id, nxt)


def parse_enum_flag_value(raw: str, current_set, allowed_keys):
    s = (raw or "").strip()
    if s == "":
        raise ValueError("Empty enum-flag value")

    up = s.upper()
    if up == "NONE":
        return set()
    if up == "ALL":
        return set(allowed_keys)

    tokens = [t.strip() for t in s.replace(",", " ").split() if t.strip()]
    if not tokens:
        raise ValueError("No tokens")

    if any(t[0] in "+-" for t in tokens):
        newset = set(current_set) if isinstance(current_set, (set, frozenset)) else set()
        for t in tokens:
            if t[0] not in "+-":
                raise ValueError("Mixed tokens: use +X/-Y or plain list, not both")
            sign = t[0]
            key = t[1:]
            if key not in allowed_keys:
                raise ValueError(f"Invalid enum-flag key '{key}'")
            if sign == "+":
                newset.add(key)
            else:
                newset.discard(key)
        return newset

    newset = set()
    for t in tokens:
        if t not in allowed_keys:
            raise ValueError(f"Invalid enum-flag key '{t}'")
        newset.add(t)
    return newset


def resolve_owner_for_prop(prop_id: str):
    candidates = [
        "bpy.context.tool_settings",
        "bpy.context.scene",
        "bpy.context.scene.render",
        "bpy.context.view_layer",
        "bpy.context.space_data",
        "bpy.context.space_data.overlay if bpy.context.space_data and hasattr(bpy.context.space_data,'overlay') else None",
        "bpy.context.space_data.shading if bpy.context.space_data and hasattr(bpy.context.space_data,'shading') else None",
        "bpy.context.object",
        "bpy.context.active_object",
        "bpy.context.active_object.data if bpy.context.active_object else None",
        "bpy.context.preferences",
        "bpy.context.window_manager",
        "bpy.context.screen",
        "bpy.context.area",
        "bpy.context.region_data",
    ]
    for expr in candidates:
        try:
            owner = safe_eval(expr)
            if owner is None:
                continue
            if hasattr(owner, prop_id):
                return expr
        except Exception:
            continue
    return None


def guess_prop_action_and_value(owner, prop_id):
    try:
        cur = getattr(owner, prop_id)
    except Exception:
        return "SET", ""
    if isinstance(cur, bool):
        return "TOGGLE", ""
    return "SET", ""


def enum_flag_current_to_text(value):
    if isinstance(value, (set, frozenset)):
        return ",".join(sorted(value))
    try:
        return ",".join(sorted(list(value)))
    except Exception:
        return ""