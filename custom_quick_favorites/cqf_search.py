# cqf_search.py
import bpy
from .cqf_safe import safe_eval

_SEARCH_CACHE = {"built": False, "items": []}


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    for ch in [" ", "\t", "-", "/", "(", ")", "[", "]", "{", "}", ":", ";", ","]:
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s

def _tokens(s: str):
    s = _norm(s)
    out = []
    for chunk in s.replace(".", "_").split("_"):
        chunk = chunk.strip()
        if chunk:
            out.append(chunk)
    return out

def _match(query: str, text: str) -> bool:
    qt = _tokens(query)
    if not qt:
        return True
    t = _norm(text).replace(".", "_")
    return all(tok in t for tok in qt)


_ENUM_ALIASES = {
    "INCREMENT": ["grid", "increment", "step"],
    "VERTEX": ["vertex", "vert"],
    "EDGE": ["edge"],
    "FACE": ["face", "polygon", "poly"],
    "VOLUME": ["volume"],
    "EDGE_MIDPOINT": ["midpoint", "edge_midpoint"],
    "EDGE_PERPENDICULAR": ["perpendicular", "edge_perpendicular"],
}

_PATH_ALIASES = {
    "scene.tool_settings.snap_elements_base": ["snap_target", "snap_base", "snap_elements_base", "snap"],
    "scene.tool_settings.snap_elements": ["snap", "snap_elements"],
}

def _aliases_for_enum_id(enum_id: str):
    return _ENUM_ALIASES.get(enum_id, [])

def _aliases_for_path(data_path: str):
    return _PATH_ALIASES.get(data_path, [])


def _build_operator_items():
    ops = []
    try:
        for mod_name in dir(bpy.ops):
            if mod_name.startswith("_"):
                continue
            mod = getattr(bpy.ops, mod_name, None)
            if mod is None:
                continue
            for op_name in dir(mod):
                if op_name.startswith("_"):
                    continue
                try:
                    getattr(mod, op_name)
                except Exception:
                    continue
                op_id = f"{mod_name}.{op_name}"
                ops.append({
                    "kind": "OP",
                    "id": op_id,
                    "label": f"OP   {op_id}",
                    "payload": {"op_idname": op_id},
                    "search_text": f"operator op {op_id}",
                })
    except Exception:
        pass
    return ops


def _build_menu_items():
    menus = []
    try:
        for name in dir(bpy.types):
            if "_MT_" not in name:
                continue
            cls = getattr(bpy.types, name, None)
            if cls is None:
                continue
            try:
                if not isinstance(cls, type):
                    continue
                if not issubclass(cls, bpy.types.Menu):
                    continue
            except Exception:
                continue

            bl_idname = getattr(cls, "bl_idname", "") or name
            bl_label = getattr(cls, "bl_label", "") or bl_idname

            menus.append({
                "kind": "MENU",
                "id": bl_idname,
                "label": f"MENU {bl_idname} — {bl_label}",
                "payload": {"menu_idname": bl_idname, "call": "call_menu"},
                "search_text": f"menu {bl_idname} {bl_label}",
            })

        uniq = {}
        for it in menus:
            uniq[it["id"]] = it
        menus = list(uniq.values())
    except Exception:
        pass
    return menus


def _build_prop_items():
    owners = [
        ("bpy.context.scene", "scene"),
        ("bpy.context.scene.render", "render"),
        ("bpy.context.tool_settings", "tool_settings"),
        ("bpy.context.view_layer", "view_layer"),
        ("bpy.context.preferences", "preferences"),
        ("bpy.context.window_manager", "window_manager"),
        ("bpy.context.space_data", "space_data"),
        ("bpy.context.space_data.overlay if bpy.context.space_data and hasattr(bpy.context.space_data,'overlay') else None", "overlay"),
        ("bpy.context.space_data.shading if bpy.context.space_data and hasattr(bpy.context.space_data,'shading') else None", "shading"),
        ("bpy.context.region_data", "region_data"),
        ("bpy.context.object", "object"),
        ("bpy.context.active_object", "active_object"),
    ]

    props = []
    for expr, tag in owners:
        try:
            owner = safe_eval(expr)
        except Exception:
            owner = None
        if owner is None:
            continue

        try:
            rna_props = owner.bl_rna.properties
        except Exception:
            continue

        for p in rna_props:
            pid = getattr(p, "identifier", None)
            if not pid or pid == "rna_type":
                continue

            try:
                if getattr(p, "is_readonly", False):
                    continue
            except Exception:
                pass

            ptype = getattr(p, "type", None)
            if ptype not in {"BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"}:
                continue

            props.append({
                "kind": "PROP",
                "id": f"{expr}.{pid}",
                "label": f"PROP {tag}.{pid}",
                "payload": {"owner_expr": expr, "prop_id": pid},
                "search_text": f"prop property {tag} {pid} {expr}",
            })

    uniq = {}
    for it in props:
        uniq[it["id"]] = it
    return list(uniq.values())


def _enum_items(owner_expr: str, prop_id: str):
    try:
        owner = safe_eval(owner_expr)
    except Exception:
        owner = None
    if owner is None or not hasattr(owner, "bl_rna"):
        return (False, [])

    try:
        rna_prop = owner.bl_rna.properties.get(prop_id, None)
    except Exception:
        rna_prop = None

    if not rna_prop:
        return (False, [])

    if getattr(rna_prop, "type", None) != "ENUM":
        return (False, [])

    is_flag = bool(getattr(rna_prop, "is_enum_flag", False))

    items = []
    try:
        for it in rna_prop.enum_items:
            eid = getattr(it, "identifier", "")
            ename = getattr(it, "name", "") or eid
            edesc = getattr(it, "description", "") or ""
            if eid:
                items.append((eid, ename, edesc))
    except Exception:
        pass

    return (is_flag, items)


def _build_expr_items():
    expr_items = []

    data_path = "scene.tool_settings.snap_elements_base"
    owner_expr = "bpy.context.scene.tool_settings"
    prop_id = "snap_elements_base"

    is_flag, items = _enum_items(owner_expr, prop_id)
    if items:
        path_aliases = _aliases_for_path(data_path)
        path_alias_txt = " ".join(path_aliases)

        for eid, ename, edesc in items:
            aliases = _aliases_for_enum_id(eid)
            alias_txt = " ".join(aliases)

            friendly = ename
            if eid == "INCREMENT":
                friendly = "Grid"

            label = f"SNAP {friendly} ({eid}) — {data_path}"
            search_text = f"snap target {friendly} {eid} {ename} {edesc} {data_path} {path_alias_txt} {alias_txt}"

            op_expr = (
                "bpy.ops.wm.context_toggle_enum("
                f"data_path={repr(data_path)}, value={repr(eid)})"
            )

            expr_items.append({
                "kind": "EXPR",
                "id": f"{data_path}|TOGGLE|{eid}",
                "label": label,
                "payload": {
                    # ✅ IMPORTANT: cqf_operators expects op_expr
                    "op_expr": op_expr,
                    "label": label,
                },
                "search_text": search_text,
            })

    uniq = {}
    for it in expr_items:
        uniq[it["id"]] = it
    return list(uniq.values())


def build_cache():
    if _SEARCH_CACHE["built"]:
        return

    items = []
    items.extend(_build_operator_items())
    items.extend(_build_menu_items())
    items.extend(_build_prop_items())
    items.extend(_build_expr_items())

    uniq = {}
    for it in items:
        uniq[f"{it['kind']}|{it['id']}"] = it
    items = list(uniq.values())

    items.sort(key=lambda d: (d["kind"], d["id"]))
    _SEARCH_CACHE["items"] = items
    _SEARCH_CACHE["built"] = True


def search(query: str, limit: int = 80):
    build_cache()

    q = (query or "").strip()
    if not q:
        ops = [it for it in _SEARCH_CACHE["items"] if it["kind"] == "OP"][:25]
        menus = [it for it in _SEARCH_CACHE["items"] if it["kind"] == "MENU"][:25]
        exprs = [it for it in _SEARCH_CACHE["items"] if it["kind"] == "EXPR"][:25]
        props = [it for it in _SEARCH_CACHE["items"] if it["kind"] == "PROP"][:25]
        return (ops + menus + exprs + props)[:limit]

    hits = []
    qn = _norm(q)

    for it in _SEARCH_CACHE["items"]:
        text = f"{it.get('label','')} {it.get('id','')} {it.get('search_text','')}"
        if not _match(q, text):
            continue

        tn = _norm(text)
        score = 0

        if tn.startswith(qn):
            score += 140
        if qn in tn:
            score += 70

        score -= min(len(it.get("id", "")), 220) * 0.02

        if "menu" in qn and it["kind"] == "MENU":
            score += 50
        if ("prop" in qn or "property" in qn) and it["kind"] == "PROP":
            score += 50
        if ("operator" in qn or "op" in qn) and it["kind"] == "OP":
            score += 50
        if ("snap" in qn or "grid" in qn or "vertex" in qn) and it["kind"] == "EXPR":
            score += 60

        if it["kind"] == "EXPR":
            score += 15

        hits.append((score, it))

    hits.sort(key=lambda x: (-x[0], x[1]["kind"], x[1]["id"]))
    return [it for _, it in hits[:limit]]


def enum_items_callback(self, context):
    query = getattr(self, "search_query", "")
    results = search(query, limit=80)

    items = []
    for it in results:
        ident = f"{it['kind']}|{it['id']}"
        items.append((ident, it["label"], ""))

    if not items:
        items = [("NONE", "No match", "")]
    return items


def get_item_by_enum_id(enum_id: str):
    if not enum_id or enum_id == "NONE" or "|" not in enum_id:
        return None
    kind, _id = enum_id.split("|", 1)

    build_cache()
    for it in _SEARCH_CACHE["items"]:
        if it["kind"] == kind and it["id"] == _id:
            return it
    return None