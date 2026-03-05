bl_info = {
    "name": "Cursor Auto Attach (Vertex/Edge/Face) - Edit+Object + Manual Cursor Editing (Timer Safe)",
    "author": "ChatGPT",
    "version": (2, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar (N) > Cursor",
    "description": "Auto-attach 3D Cursor to nearest mesh component. Cursor stays editable and compatible with other cursor tools (timer poll + depsgraph follow).",
    "category": "3D View",
}

import bpy
import bmesh
from bpy.props import (
    BoolProperty,
    StringProperty,
    EnumProperty,
    IntProperty,
    FloatProperty,
    PointerProperty,
)
from bpy.types import Panel, PropertyGroup
from mathutils import Vector, Matrix, Quaternion
from mathutils import geometry


# ------------------------------------------------------------
# Constants / globals
# ------------------------------------------------------------

_HANDLER_TAG = "CURSOR_AUTO_ATTACH_HANDLER"
_TIMER_TAG = "CURSOR_AUTO_ATTACH_TIMER"
_UNDO_REDO_TAG = "CURSOR_AUTO_ATTACH_UNDO_REDO"

_EPS = 1e-12

# "has cursor changed?" tolerances
CURSOR_LOC_EPS = 1e-10
CURSOR_ROT_EPS = 1e-10

# Timer interval (seconds)
TIMER_INTERVAL = 0.08
_timer_running = False

# Edit-mode BBox freeze anti-false-positive (when components move fast)
_BBOX_GRACE_TICKS = 2
_bbox_outside_counts = {}  # key: scene pointer -> int

# Per-object cursor state keys (custom properties)
_OBJ_STATE_PREFIX = "_caa_"
_OBJ_STATE_VERSION = 1

# Active object switch tracking (per scene)
_last_active_by_scene = {}  # scene_key -> {"ptr": int, "name": str}

# Track last known transform of objects (for Undo/Redo / fast moves)
_last_obj_xform = {}  # obj_ptr -> (loc(Vector3), rot(Quat), scale(Vector3))

# thresholds for object transform change detection
OBJ_LOC_EPS = 1e-12
OBJ_ROT_EPS = 1e-12
OBJ_SCL_EPS = 1e-12


# ------------------------------------------------------------
# Math helpers
# ------------------------------------------------------------

def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def _safe_normalize(v: Vector, fallback: Vector = Vector((1.0, 0.0, 0.0))) -> Vector:
    if v.length_squared < _EPS:
        return fallback.copy()
    v2 = v.copy()
    v2.normalize()
    return v2


def _quat_len2(q: Quaternion) -> float:
    return float(q.dot(q))


def _safe_quat(q: Quaternion) -> Quaternion:
    qq = q.copy()
    if _quat_len2(qq) < _EPS:
        qq = Quaternion((1.0, 0.0, 0.0, 0.0))
    try:
        qq.normalize()
    except Exception:
        qq = Quaternion((1.0, 0.0, 0.0, 0.0))
    return qq


def _make_orthonormal_basis(x: Vector, y_hint: Vector, z_hint: Vector = None) -> Matrix:
    X = _safe_normalize(x, Vector((1.0, 0.0, 0.0)))
    Z = z_hint if z_hint is not None else y_hint
    Z = Z - X * Z.dot(X)
    Z = _safe_normalize(Z, Vector((0.0, 0.0, 1.0)))
    Y = Z.cross(X)
    Y = _safe_normalize(Y, Vector((0.0, 1.0, 0.0)))
    Z = X.cross(Y)
    Z = _safe_normalize(Z, Vector((0.0, 0.0, 1.0)))
    return Matrix((X, Y, Z)).transposed()


def _barycentric_weights(a: Vector, b: Vector, c: Vector, p: Vector):
    v0 = b - a
    v1 = c - a
    v2 = p - a
    d00 = v0.dot(v0)
    d01 = v0.dot(v1)
    d11 = v1.dot(v1)
    d20 = v2.dot(v0)
    d21 = v2.dot(v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < _EPS:
        return None
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return (u, v, w)


def _basis_to_quat(basis_world_3x3: Matrix) -> Quaternion:
    X = Vector((basis_world_3x3[0][0], basis_world_3x3[1][0], basis_world_3x3[2][0]))
    Y = Vector((basis_world_3x3[0][1], basis_world_3x3[1][1], basis_world_3x3[2][1]))
    Z = Vector((basis_world_3x3[0][2], basis_world_3x3[1][2], basis_world_3x3[2][2]))
    basis = _make_orthonormal_basis(X, Y, Z)
    return _safe_quat(basis.to_quaternion())


def _decompose_matrix_world(obj) -> tuple:
    """Return (loc, rot_quat, scale) from obj.matrix_world."""
    try:
        loc, rot, scl = obj.matrix_world.decompose()
        return loc.copy(), _safe_quat(rot), Vector((float(scl.x), float(scl.y), float(scl.z)))
    except Exception:
        mw = obj.matrix_world
        loc = mw.to_translation()
        rot = _safe_quat(mw.to_quaternion())
        scl = Vector((1.0, 1.0, 1.0))
        return loc, rot, scl


def _obj_xform_changed(obj) -> bool:
    """Detect if object transform changed since last tick (Undo/Redo etc.)."""
    if not obj:
        return False
    try:
        ptr = obj.as_pointer()
    except Exception:
        ptr = id(obj)

    loc, rot, scl = _decompose_matrix_world(obj)
    prev = _last_obj_xform.get(ptr)
    if prev is None:
        _last_obj_xform[ptr] = (loc, rot, scl)
        return False

    ploc, prot, pscl = prev

    if (loc - ploc).length_squared > OBJ_LOC_EPS:
        return True

    # quat difference (sign invariant)
    qa = _safe_quat(rot)
    qb = _safe_quat(prot)
    d1 = (qa.w - qb.w) ** 2 + (qa.x - qb.x) ** 2 + (qa.y - qb.y) ** 2 + (qa.z - qb.z) ** 2
    d2 = (qa.w + qb.w) ** 2 + (qa.x + qb.x) ** 2 + (qa.y + qb.y) ** 2 + (qa.z + qb.z) ** 2
    if min(d1, d2) > OBJ_ROT_EPS:
        return True

    if (scl - pscl).length_squared > OBJ_SCL_EPS:
        return True

    return False


def _update_obj_xform_cache(obj):
    if not obj:
        return
    try:
        ptr = obj.as_pointer()
    except Exception:
        ptr = id(obj)
    _last_obj_xform[ptr] = _decompose_matrix_world(obj)


# ------------------------------------------------------------
# Cursor IO (IMPORTANT: do NOT force rotation_mode)
# ------------------------------------------------------------

def _cursor_world(scene) -> Vector:
    return scene.cursor.location.copy()


def _set_cursor_world(scene, p_world: Vector):
    scene.cursor.location = p_world


def _cursor_world_quat(scene) -> Quaternion:
    c = scene.cursor
    m = getattr(c, "matrix", None)
    if isinstance(m, Matrix):
        try:
            return _safe_quat(m.to_quaternion())
        except Exception:
            pass
    mode = getattr(c, "rotation_mode", "XYZ")
    try:
        if mode == "QUATERNION":
            return _safe_quat(c.rotation_quaternion)
        e = c.rotation_euler.copy()
        return _safe_quat(e.to_quaternion())
    except Exception:
        return Quaternion((1.0, 0.0, 0.0, 0.0))


def _set_cursor_world_quat(scene, q_world: Quaternion):
    """
    Preserve user's rotation_mode:
    - if cursor is in QUATERNION mode -> set quaternion
    - else -> set Euler
    """
    c = scene.cursor
    q = _safe_quat(q_world)
    mode = getattr(c, "rotation_mode", "XYZ")
    try:
        if mode == "QUATERNION":
            c.rotation_quaternion = q
        else:
            try:
                c.rotation_euler = q.to_euler(mode)
            except Exception:
                c.rotation_euler = q.to_euler("XYZ")
    except Exception:
        try:
            c.rotation_mode = "XYZ"
            c.rotation_euler = q.to_euler("XYZ")
        except Exception:
            pass


# ------------------------------------------------------------
# Bounding box helpers (world space)
# ------------------------------------------------------------

def _cursor_inside_object_bbox_world(obj, depsgraph, cursor_world: Vector, margin: float) -> bool:
    if not obj:
        return True
    try:
        o = obj
        if depsgraph is not None:
            try:
                o = obj.evaluated_get(depsgraph)
            except Exception:
                o = obj

        bb = getattr(o, "bound_box", None)
        if not bb:
            return True

        mw = o.matrix_world
        pts = [mw @ Vector(corner) for corner in bb]

        minx = min(p.x for p in pts) - margin
        miny = min(p.y for p in pts) - margin
        minz = min(p.z for p in pts) - margin
        maxx = max(p.x for p in pts) + margin
        maxy = max(p.y for p in pts) + margin
        maxz = max(p.z for p in pts) + margin

        p = cursor_world
        return (minx <= p.x <= maxx) and (miny <= p.y <= maxy) and (minz <= p.z <= maxz)
    except Exception:
        return True


# ------------------------------------------------------------
# Handler / timer registration
# ------------------------------------------------------------

def _ensure_handler_registered():
    for fn in bpy.app.handlers.depsgraph_update_post:
        if getattr(fn, "__name__", "") == _HANDLER_TAG:
            break
    else:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_handler)

    for fn in bpy.app.handlers.undo_post:
        if getattr(fn, "__name__", "") == _UNDO_REDO_TAG:
            break
    else:
        bpy.app.handlers.undo_post.append(_undo_redo_handler)

    for fn in bpy.app.handlers.redo_post:
        if getattr(fn, "__name__", "") == _UNDO_REDO_TAG:
            break
    else:
        bpy.app.handlers.redo_post.append(_undo_redo_handler)


def _ensure_handler_unregistered():
    to_remove = []
    for fn in bpy.app.handlers.depsgraph_update_post:
        if getattr(fn, "__name__", "") == _HANDLER_TAG:
            to_remove.append(fn)
    for fn in to_remove:
        bpy.app.handlers.depsgraph_update_post.remove(fn)

    to_remove = []
    for fn in bpy.app.handlers.undo_post:
        if getattr(fn, "__name__", "") == _UNDO_REDO_TAG:
            to_remove.append(fn)
    for fn in to_remove:
        bpy.app.handlers.undo_post.remove(fn)

    to_remove = []
    for fn in bpy.app.handlers.redo_post:
        if getattr(fn, "__name__", "") == _UNDO_REDO_TAG:
            to_remove.append(fn)
    for fn in to_remove:
        bpy.app.handlers.redo_post.remove(fn)


def _undo_redo_handler(_dummy=None):
    _undo_redo_handler.__name__ = _UNDO_REDO_TAG

    for scene in bpy.data.scenes:
        s = _get_settings(scene)
        if not s or not s.auto_attach:
            continue

        if not _has_attachment(scene):
            continue

        obj = _find_object(scene, s.object_name)
        if not obj or obj.type != "MESH":
            continue

        mode, payload = _get_mesh_access_for_follow(obj, None)
        if mode == "NONE" or not payload:
            continue

        try:
            if mode == "EDIT":
                bm = payload
                comp_point_world = _compute_comp_point_world_from_attachment(s, obj, bm, "EDIT")
                comp_q = _component_world_quat_from_data(s, obj, bm, "EDIT")
            else:
                obj_like, me = payload
                comp_point_world = _compute_comp_point_world_from_attachment(s, obj_like, me, "MESH")
                comp_q = _component_world_quat_from_data(s, obj_like, me, "MESH")

            if comp_point_world is None or comp_q is None:
                continue

            _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=obj)
            _obj_save_state(scene, obj)
        finally:
            _free_mesh_access(mode, payload)


def _timer_func():
    global _timer_running

    if not _timer_running:
        return None

    if not hasattr(bpy.types.Scene, "cursor_auto_attach_settings"):
        _timer_running = False
        return None

    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        depsgraph = None

    for scene in bpy.data.scenes:
        s = _get_settings(scene)
        if not s or not s.auto_attach:
            continue
        _auto_attach_tick(scene, depsgraph, source="TIMER")

    return TIMER_INTERVAL


def _ensure_timer_registered():
    global _timer_running
    if _timer_running:
        return
    _timer_running = True
    bpy.app.timers.register(_timer_func, first_interval=TIMER_INTERVAL, persistent=True)


def _ensure_timer_unregistered():
    global _timer_running
    _timer_running = False


# ------------------------------------------------------------
# Settings / state
# ------------------------------------------------------------

def _get_settings(scene):
    return getattr(scene, "cursor_auto_attach_settings", None)


def _set_status(scene, msg: str):
    s = _get_settings(scene)
    if s:
        s.status = msg or ""


def _log_debug(scene, msg: str):
    """Minimal debug logger for operator diagnostics."""
    scn_name = "?"
    try:
        scn_name = scene.name
    except Exception:
        pass
    print(f"[CursorAutoAttach][{scn_name}] {msg}")


def _find_object(scene, name: str):
    if not name:
        return None
    obj = scene.objects.get(name)
    if obj:
        return obj
    return bpy.data.objects.get(name)


def _clear_attachment(scene, reason: str = ""):
    s = _get_settings(scene)
    if not s:
        return
    s.object_name = ""
    s.mesh_name = ""
    s.component_type = "NONE"
    s.v_index = -1
    s.v_tangent = -1
    s.e_v1 = -1
    s.e_v2 = -1
    s.e_t = 0.0
    s.f_v1 = -1
    s.f_v2 = -1
    s.f_v3 = -1
    s.f_w1 = 0.0
    s.f_w2 = 0.0
    s.f_w3 = 0.0
    s.off_w = 1.0
    s.off_x = 0.0
    s.off_y = 0.0
    s.off_z = 0.0
    s.pos_off_x = 0.0
    s.pos_off_y = 0.0
    s.pos_off_z = 0.0
    if reason:
        _set_status(scene, reason)
    try:
        _bbox_outside_counts.pop(scene.as_pointer(), None)
    except Exception:
        pass


def _has_attachment(scene) -> bool:
    s = _get_settings(scene)
    if not s:
        return False
    if not s.object_name:
        return False
    if s.component_type == "NONE":
        return False
    return True


def _get_rot_offset(scene) -> Quaternion:
    s = _get_settings(scene)
    return _safe_quat(Quaternion((float(s.off_w), float(s.off_x), float(s.off_y), float(s.off_z))))


def _set_rot_offset(scene, q: Quaternion):
    s = _get_settings(scene)
    qq = _safe_quat(q)
    s.off_w, s.off_x, s.off_y, s.off_z = float(qq.w), float(qq.x), float(qq.y), float(qq.z)


def _get_pos_offset(scene) -> Vector:
    s = _get_settings(scene)
    return Vector((float(s.pos_off_x), float(s.pos_off_y), float(s.pos_off_z)))


def _set_pos_offset(scene, v: Vector):
    s = _get_settings(scene)
    s.pos_off_x = float(v.x)
    s.pos_off_y = float(v.y)
    s.pos_off_z = float(v.z)


def _get_last_applied_cursor(scene):
    s = _get_settings(scene)
    loc = Vector((float(s.last_cur_x), float(s.last_cur_y), float(s.last_cur_z)))
    rot = _safe_quat(Quaternion((float(s.last_rot_w), float(s.last_rot_x), float(s.last_rot_y), float(s.last_rot_z))))
    return loc, rot


def _set_last_applied_cursor(scene, loc: Vector, rot: Quaternion):
    s = _get_settings(scene)
    s.last_cur_x, s.last_cur_y, s.last_cur_z = float(loc.x), float(loc.y), float(loc.z)
    r = _safe_quat(rot)
    s.last_rot_w, s.last_rot_x, s.last_rot_y, s.last_rot_z = float(r.w), float(r.x), float(r.y), float(r.z)


def _loc_changed(a: Vector, b: Vector) -> bool:
    return (a - b).length_squared > CURSOR_LOC_EPS


def _rot_changed(a: Quaternion, b: Quaternion) -> bool:
    qa = _safe_quat(a)
    qb = _safe_quat(b)
    d1 = (qa.w - qb.w) ** 2 + (qa.x - qb.x) ** 2 + (qa.y - qb.y) ** 2 + (qa.z - qb.z) ** 2
    d2 = (qa.w + qb.w) ** 2 + (qa.x + qb.x) ** 2 + (qa.y + qb.y) ** 2 + (qa.z + qb.z) ** 2
    return min(d1, d2) > CURSOR_ROT_EPS


# ------------------------------------------------------------
# Per-object cursor state (custom properties)
# ------------------------------------------------------------

def _k(name: str) -> str:
    return _OBJ_STATE_PREFIX + name


def _obj_has_state(obj) -> bool:
    if not obj:
        return False
    try:
        return (_k("ver") in obj) and int(obj.get(_k("ver"), 0)) == _OBJ_STATE_VERSION
    except Exception:
        return False


def _obj_save_state(scene, obj):
    """
    Save current cursor + attachment state into OBJ custom properties.
    IMPORTANT: The attachment is saved "relative to THIS object".
    """
    if not scene or not obj:
        return
    s = _get_settings(scene)
    if not s:
        return

    cur_loc = _cursor_world(scene)
    cur_rot = _cursor_world_quat(scene)

    obj[_k("ver")] = _OBJ_STATE_VERSION

    # cursor transform (world)
    obj[_k("cur_x")] = float(cur_loc.x)
    obj[_k("cur_y")] = float(cur_loc.y)
    obj[_k("cur_z")] = float(cur_loc.z)

    obj[_k("rot_w")] = float(cur_rot.w)
    obj[_k("rot_x")] = float(cur_rot.x)
    obj[_k("rot_y")] = float(cur_rot.y)
    obj[_k("rot_z")] = float(cur_rot.z)

    # attachment (relative, no object name stored)
    obj[_k("ctype")] = str(s.component_type or "NONE")

    obj[_k("v_index")] = int(s.v_index)
    obj[_k("v_tangent")] = int(s.v_tangent)

    obj[_k("e_v1")] = int(s.e_v1)
    obj[_k("e_v2")] = int(s.e_v2)
    obj[_k("e_t")] = float(s.e_t)

    obj[_k("f_v1")] = int(s.f_v1)
    obj[_k("f_v2")] = int(s.f_v2)
    obj[_k("f_v3")] = int(s.f_v3)

    obj[_k("f_w1")] = float(s.f_w1)
    obj[_k("f_w2")] = float(s.f_w2)
    obj[_k("f_w3")] = float(s.f_w3)

    # offsets
    obj[_k("off_w")] = float(s.off_w)
    obj[_k("off_x")] = float(s.off_x)
    obj[_k("off_y")] = float(s.off_y)
    obj[_k("off_z")] = float(s.off_z)

    obj[_k("pos_off_x")] = float(s.pos_off_x)
    obj[_k("pos_off_y")] = float(s.pos_off_y)
    obj[_k("pos_off_z")] = float(s.pos_off_z)

    # last applied cursor
    obj[_k("last_cur_x")] = float(s.last_cur_x)
    obj[_k("last_cur_y")] = float(s.last_cur_y)
    obj[_k("last_cur_z")] = float(s.last_cur_z)

    obj[_k("last_rot_w")] = float(s.last_rot_w)
    obj[_k("last_rot_x")] = float(s.last_rot_x)
    obj[_k("last_rot_y")] = float(s.last_rot_y)
    obj[_k("last_rot_z")] = float(s.last_rot_z)


def _obj_load_state(scene, obj):
    """
    Load cursor + attachment state from OBJ custom properties into scene settings + cursor.
    IMPORTANT: Rebind attachment to THIS object (obj.name).
    """
    if not scene or not obj:
        return False
    s = _get_settings(scene)
    if not s:
        return False

    if not _obj_has_state(obj):
        return False

    # cursor
    cur_loc = Vector((
        float(obj.get(_k("cur_x"), 0.0)),
        float(obj.get(_k("cur_y"), 0.0)),
        float(obj.get(_k("cur_z"), 0.0)),
    ))
    cur_rot = _safe_quat(Quaternion((
        float(obj.get(_k("rot_w"), 1.0)),
        float(obj.get(_k("rot_x"), 0.0)),
        float(obj.get(_k("rot_y"), 0.0)),
        float(obj.get(_k("rot_z"), 0.0)),
    )))

    _set_cursor_world(scene, cur_loc)
    _set_cursor_world_quat(scene, cur_rot)

    # REBIND to this object
    s.object_name = obj.name
    s.mesh_name = obj.data.name if obj.data else ""
    s.component_type = str(obj.get(_k("ctype"), "NONE"))

    s.v_index = int(obj.get(_k("v_index"), -1))
    s.v_tangent = int(obj.get(_k("v_tangent"), -1))

    s.e_v1 = int(obj.get(_k("e_v1"), -1))
    s.e_v2 = int(obj.get(_k("e_v2"), -1))
    s.e_t = float(obj.get(_k("e_t"), 0.0))

    s.f_v1 = int(obj.get(_k("f_v1"), -1))
    s.f_v2 = int(obj.get(_k("f_v2"), -1))
    s.f_v3 = int(obj.get(_k("f_v3"), -1))

    s.f_w1 = float(obj.get(_k("f_w1"), 0.0))
    s.f_w2 = float(obj.get(_k("f_w2"), 0.0))
    s.f_w3 = float(obj.get(_k("f_w3"), 0.0))

    s.off_w = float(obj.get(_k("off_w"), 1.0))
    s.off_x = float(obj.get(_k("off_x"), 0.0))
    s.off_y = float(obj.get(_k("off_y"), 0.0))
    s.off_z = float(obj.get(_k("off_z"), 0.0))

    s.pos_off_x = float(obj.get(_k("pos_off_x"), 0.0))
    s.pos_off_y = float(obj.get(_k("pos_off_y"), 0.0))
    s.pos_off_z = float(obj.get(_k("pos_off_z"), 0.0))

    # last applied (treat restore as last applied => no immediate overwrite)
    last_loc = Vector((
        float(obj.get(_k("last_cur_x"), cur_loc.x)),
        float(obj.get(_k("last_cur_y"), cur_loc.y)),
        float(obj.get(_k("last_cur_z"), cur_loc.z)),
    ))
    last_rot = _safe_quat(Quaternion((
        float(obj.get(_k("last_rot_w"), cur_rot.w)),
        float(obj.get(_k("last_rot_x"), cur_rot.x)),
        float(obj.get(_k("last_rot_y"), cur_rot.y)),
        float(obj.get(_k("last_rot_z"), cur_rot.z)),
    )))
    _set_last_applied_cursor(scene, last_loc, last_rot)

    try:
        _bbox_outside_counts.pop(scene.as_pointer(), None)
    except Exception:
        pass

    # refresh xform cache (important for undo detection)
    _update_obj_xform_cache(obj)

    return True


def _obj_init_state_from_origin(scene, obj):
    """If no state exists: initialize cursor at object's origin (world loc+rot) and save."""
    if not scene or not obj:
        return
    s = _get_settings(scene)
    if not s:
        return

    mw = obj.matrix_world
    loc = mw.translation.copy()
    rot = _safe_quat(mw.to_quaternion())

    _set_cursor_world(scene, loc)
    _set_cursor_world_quat(scene, rot)

    # bind to this object but no attachment yet
    s.object_name = obj.name
    s.mesh_name = obj.data.name if obj.data else ""
    s.component_type = "NONE"

    s.v_index = -1
    s.v_tangent = -1
    s.e_v1 = -1
    s.e_v2 = -1
    s.e_t = 0.0
    s.f_v1 = -1
    s.f_v2 = -1
    s.f_v3 = -1
    s.f_w1 = 0.0
    s.f_w2 = 0.0
    s.f_w3 = 0.0

    # offsets reset
    s.pos_off_x = 0.0
    s.pos_off_y = 0.0
    s.pos_off_z = 0.0

    # rotation offset default = cursor rotation (harmless)
    s.off_w = float(rot.w)
    s.off_x = float(rot.x)
    s.off_y = float(rot.y)
    s.off_z = float(rot.z)

    _set_last_applied_cursor(scene, loc, rot)

    _obj_save_state(scene, obj)
    _set_status(scene, "Cursor state initialized from object origin.")

    _update_obj_xform_cache(obj)


def _handle_active_object_switch(scene, depsgraph):
    """Detect active object change and swap per-object cursor state (context scene only)."""
    if not scene:
        return

    try:
        ctx_scene = bpy.context.scene
    except Exception:
        ctx_scene = None
    if ctx_scene is not scene:
        return

    try:
        active = bpy.context.view_layer.objects.active
    except Exception:
        active = None

    try:
        scene_key = scene.as_pointer()
    except Exception:
        scene_key = id(scene)

    entry = _last_active_by_scene.get(scene_key, {"ptr": 0, "name": ""})
    prev_name = entry.get("name", "")

    cur_ptr = 0
    try:
        cur_ptr = active.as_pointer() if active else 0
    except Exception:
        cur_ptr = 0

    if cur_ptr == entry.get("ptr", 0):
        return

    # Save previous active object's state
    if prev_name:
        prev_obj = bpy.data.objects.get(prev_name)
        if prev_obj:
            _obj_save_state(scene, prev_obj)

    # Load / init new active object's state
    if active:
        if _obj_has_state(active):
            _obj_load_state(scene, active)
            _set_status(scene, f"Cursor state loaded for: {active.name}")
        else:
            _obj_init_state_from_origin(scene, active)
            _set_status(scene, f"Cursor state created for: {active.name}")

    _last_active_by_scene[scene_key] = {"ptr": cur_ptr, "name": active.name if active else ""}


# ------------------------------------------------------------
# Robust to_mesh helpers
# ------------------------------------------------------------

def _try_to_mesh(eval_obj, depsgraph):
    if not eval_obj:
        return None
    try:
        return eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    except TypeError:
        pass
    except Exception:
        return None
    try:
        return eval_obj.to_mesh(preserve_all_data_layers=True)
    except Exception:
        return None


def _try_to_mesh_clear(eval_obj):
    try:
        eval_obj.to_mesh_clear()
    except Exception:
        pass


# ------------------------------------------------------------
# Mesh access
# ------------------------------------------------------------

def _get_mesh_access_for_follow(obj, depsgraph):
    try:
        if obj.type == "MESH" and obj.mode == "EDIT" and obj.data and obj.data.is_editmode:
            bm = bmesh.from_edit_mesh(obj.data)
            return ("EDIT", bm)
    except Exception:
        pass

    try:
        if depsgraph is None:
            raise RuntimeError("No depsgraph")
        eval_obj = obj.evaluated_get(depsgraph)
        me = _try_to_mesh(eval_obj, depsgraph)
        if me is not None:
            return ("EVAL", (eval_obj, me))
    except Exception:
        pass

    if obj.type == "MESH" and obj.data:
        return ("BASE", (obj, obj.data))

    return ("NONE", None)


def _free_mesh_access(mode, payload):
    if mode == "EVAL" and payload:
        eval_obj, _me = payload
        _try_to_mesh_clear(eval_obj)


# ------------------------------------------------------------
# Nearest scanning
# ------------------------------------------------------------

def _choose_best_with_priority(best_vert, d2_vert, best_edge, d2_edge, best_face, d2_face, tol: float):
    tol2 = max(0.0, tol) * max(0.0, tol)
    if best_vert is not None and d2_vert is not None and d2_vert <= tol2:
        return best_vert
    if best_edge is not None and d2_edge is not None and d2_edge <= tol2:
        return best_edge

    best = None
    best_d2 = None
    for cand, d2 in ((best_vert, d2_vert), (best_edge, d2_edge), (best_face, d2_face)):
        if cand is None or d2 is None:
            continue
        if best_d2 is None or d2 < best_d2:
            best_d2 = d2
            best = cand
    return best


def _scan_nearest_on_mesh(mesh, matrix_world, cursor_world: Vector, snap_tol: float):
    M = matrix_world
    verts = mesh.vertices

    best_vert = None
    best_edge = None
    best_face = None

    d2_vert = None
    d2_edge = None
    d2_face = None

    for i, v in enumerate(verts):
        pw = M @ v.co
        d2 = (pw - cursor_world).length_squared
        if d2_vert is None or d2 < d2_vert:
            d2_vert = d2
            best_vert = {"type": "VERT", "v": i, "p": pw}

    for e in mesh.edges:
        i1, i2 = e.vertices[0], e.vertices[1]
        a = M @ verts[i1].co
        b = M @ verts[i2].co
        _cp, fac = geometry.intersect_point_line(cursor_world, a, b)
        t = _clamp01(float(fac))
        p = a.lerp(b, t)
        d2 = (p - cursor_world).length_squared
        if d2_edge is None or d2 < d2_edge:
            d2_edge = d2
            best_edge = {"type": "EDGE", "v1": i1, "v2": i2, "t": t, "p": p}

    try:
        mesh.calc_loop_triangles()
        ltris = mesh.loop_triangles
    except Exception:
        ltris = []

    for tri in ltris:
        i1, i2, i3 = tri.vertices[0], tri.vertices[1], tri.vertices[2]
        a = M @ verts[i1].co
        b = M @ verts[i2].co
        c = M @ verts[i3].co
        p_closest = geometry.closest_point_on_tri(cursor_world, a, b, c)
        d2 = (p_closest - cursor_world).length_squared
        if d2_face is None or d2 < d2_face:
            w = _barycentric_weights(a, b, c, p_closest)
            if w is None:
                continue
            d2_face = d2
            best_face = {"type": "FACE", "v1": i1, "v2": i2, "v3": i3, "w": w, "p": p_closest}

    return _choose_best_with_priority(best_vert, d2_vert, best_edge, d2_edge, best_face, d2_face, snap_tol)


def _find_vertex_tangent_neighbor_edit(bm, v_index: int):
    try:
        bm.verts.ensure_lookup_table()
        v = bm.verts[v_index]
    except Exception:
        return -1

    if not v.link_edges:
        return -1

    best_other = -1
    best_len2 = None

    for e in v.link_edges:
        other = e.other_vert(v)
        if not other:
            continue
        d2 = (other.co - v.co).length_squared
        if best_len2 is None or d2 < best_len2:
            best_len2 = d2
            best_other = other.index

    return best_other if best_other is not None else -1


def _find_nearest_component_in_edit(obj, cursor_world: Vector, snap_tol: float):
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    M = obj.matrix_world

    best_vert = None
    best_edge = None
    best_face = None

    d2_vert = None
    d2_edge = None
    d2_face = None

    for v in bm.verts:
        pw = M @ v.co
        d2 = (pw - cursor_world).length_squared
        if d2_vert is None or d2 < d2_vert:
            d2_vert = d2
            best_vert = {"type": "VERT", "v": v.index, "p": pw}

    for e in bm.edges:
        v1, v2 = e.verts[0], e.verts[1]
        a = M @ v1.co
        b = M @ v2.co
        _cp, fac = geometry.intersect_point_line(cursor_world, a, b)
        t = _clamp01(float(fac))
        p = a.lerp(b, t)
        d2 = (p - cursor_world).length_squared
        if d2_edge is None or d2 < d2_edge:
            d2_edge = d2
            best_edge = {"type": "EDGE", "v1": v1.index, "v2": v2.index, "t": t, "p": p}

    bm2 = bm.copy()
    try:
        bm2.verts.ensure_lookup_table()
        bm2.faces.ensure_lookup_table()
        try:
            bmesh.ops.triangulate(bm2, faces=bm2.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
        except Exception:
            pass

        bm2.faces.ensure_lookup_table()
        for f in bm2.faces:
            if len(f.verts) != 3:
                continue
            va, vb, vc = f.verts[0], f.verts[1], f.verts[2]
            a = M @ va.co
            b = M @ vb.co
            c = M @ vc.co
            p_closest = geometry.closest_point_on_tri(cursor_world, a, b, c)
            d2 = (p_closest - cursor_world).length_squared
            if d2_face is None or d2 < d2_face:
                w = _barycentric_weights(a, b, c, p_closest)
                if w is None:
                    continue
                d2_face = d2
                best_face = {"type": "FACE", "v1": va.index, "v2": vb.index, "v3": vc.index, "w": w, "p": p_closest}
    finally:
        try:
            bm2.free()
        except Exception:
            pass

    return _choose_best_with_priority(best_vert, d2_vert, best_edge, d2_edge, best_face, d2_face, snap_tol)


def _find_nearest_component_objectmode(obj, depsgraph, cursor_world: Vector, snap_tol: float):
    try:
        if depsgraph is None:
            raise RuntimeError("No depsgraph")
        eval_obj = obj.evaluated_get(depsgraph)
        me_eval = _try_to_mesh(eval_obj, depsgraph)
        if me_eval is not None:
            try:
                best = _scan_nearest_on_mesh(me_eval, eval_obj.matrix_world, cursor_world, snap_tol)
                if best:
                    return best
            finally:
                _try_to_mesh_clear(eval_obj)
    except Exception:
        pass

    if obj.data:
        return _scan_nearest_on_mesh(obj.data, obj.matrix_world, cursor_world, snap_tol)

    return None


# ------------------------------------------------------------
# Component orientation (world)
# ------------------------------------------------------------

def _basis_world_from_vertex_local(obj_like, v_co_local: Vector, v_normal_local: Vector, tangent_local: Vector):
    basis_local = _make_orthonormal_basis(tangent_local, v_normal_local, v_normal_local)
    M3 = obj_like.matrix_world.to_3x3()
    return M3 @ basis_local


def _basis_world_from_edge_local(obj_like, a_local: Vector, b_local: Vector, normal_local: Vector):
    tangent = b_local - a_local
    basis_local = _make_orthonormal_basis(tangent, normal_local, normal_local)
    M3 = obj_like.matrix_world.to_3x3()
    return M3 @ basis_local


def _basis_world_from_tri_local(obj_like, a_local: Vector, b_local: Vector, c_local: Vector):
    tangent = b_local - a_local
    normal = (b_local - a_local).cross(c_local - a_local)
    normal = _safe_normalize(normal, Vector((0.0, 0.0, 1.0)))
    basis_local = _make_orthonormal_basis(tangent, normal, normal)
    M3 = obj_like.matrix_world.to_3x3()
    return M3 @ basis_local


def _component_world_quat_from_data(s, obj_like, mesh_or_bm, mode: str):
    if s.component_type == "VERT":
        if mode == "EDIT":
            bm = mesh_or_bm
            bm.verts.ensure_lookup_table()
            if s.v_index < 0 or s.v_index >= len(bm.verts):
                return None
            v = bm.verts[s.v_index]
            nrm = v.normal.copy()
            t_idx = s.v_tangent
            if 0 <= t_idx < len(bm.verts):
                tang = bm.verts[t_idx].co - v.co
            else:
                tang = Vector((1.0, 0.0, 0.0))
            if v.link_edges:
                other = v.link_edges[0].other_vert(v)
                if other:
                    tang = other.co - v.co
            basis_w = _basis_world_from_vertex_local(obj_like, v.co, nrm, tang)
            return _basis_to_quat(basis_w)
        else:
            me = mesh_or_bm
            verts = me.vertices
            if s.v_index < 0 or s.v_index >= len(verts):
                return None
            v = verts[s.v_index]
            nrm = v.normal.copy()
            t_idx = s.v_tangent
            tang = (verts[t_idx].co - v.co) if (0 <= t_idx < len(verts)) else Vector((1.0, 0.0, 0.0))
            basis_w = _basis_world_from_vertex_local(obj_like, v.co, nrm, tang)
            return _basis_to_quat(basis_w)

    elif s.component_type == "EDGE":
        if mode == "EDIT":
            bm = mesh_or_bm
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            i1, i2 = s.e_v1, s.e_v2
            if min(i1, i2) < 0 or max(i1, i2) >= len(bm.verts):
                return None
            a = bm.verts[i1].co
            b = bm.verts[i2].co
            edge = None
            for e in bm.edges:
                va, vb = e.verts[0].index, e.verts[1].index
                if (va == i1 and vb == i2) or (va == i2 and vb == i1):
                    edge = e
                    break
            nrm = Vector((0.0, 0.0, 0.0))
            if edge and edge.link_faces:
                for f in edge.link_faces:
                    nrm += f.normal
            if nrm.length_squared < _EPS:
                nrm = bm.verts[i1].normal + bm.verts[i2].normal
            nrm = _safe_normalize(nrm, Vector((0.0, 0.0, 1.0)))
            basis_w = _basis_world_from_edge_local(obj_like, a, b, nrm)
            return _basis_to_quat(basis_w)
        else:
            me = mesh_or_bm
            verts = me.vertices
            i1, i2 = s.e_v1, s.e_v2
            if min(i1, i2) < 0 or max(i1, i2) >= len(verts):
                return None
            a = verts[i1].co
            b = verts[i2].co
            nrm = _safe_normalize(verts[i1].normal + verts[i2].normal, Vector((0.0, 0.0, 1.0)))
            basis_w = _basis_world_from_edge_local(obj_like, a, b, nrm)
            return _basis_to_quat(basis_w)

    elif s.component_type == "FACE":
        if mode == "EDIT":
            bm = mesh_or_bm
            bm.verts.ensure_lookup_table()
            i1, i2, i3 = s.f_v1, s.f_v2, s.f_v3
            if min(i1, i2, i3) < 0 or max(i1, i2, i3) >= len(bm.verts):
                return None
            a = bm.verts[i1].co
            b = bm.verts[i2].co
            c = bm.verts[i3].co
            basis_w = _basis_world_from_tri_local(obj_like, a, b, c)
            return _basis_to_quat(basis_w)
        else:
            me = mesh_or_bm
            verts = me.vertices
            i1, i2, i3 = s.f_v1, s.f_v2, s.f_v3
            if min(i1, i2, i3) < 0 or max(i1, i2, i3) >= len(verts):
                return None
            a = verts[i1].co
            b = verts[i2].co
            c = verts[i3].co
            basis_w = _basis_world_from_tri_local(obj_like, a, b, c)
            return _basis_to_quat(basis_w)

    return None


# ------------------------------------------------------------
# Attachment bookkeeping
# ------------------------------------------------------------

def _set_attachment_from_best(scene, obj, best):
    s = _get_settings(scene)

    s.object_name = obj.name
    s.mesh_name = obj.data.name if obj.data else ""

    s.component_type = "NONE"
    s.v_index = -1
    s.v_tangent = -1
    s.e_v1 = s.e_v2 = -1
    s.e_t = 0.0
    s.f_v1 = s.f_v2 = s.f_v3 = -1
    s.f_w1 = s.f_w2 = s.f_w3 = 0.0

    if best["type"] == "VERT":
        s.component_type = "VERT"
        s.v_index = int(best["v"])
        if obj.mode == "EDIT" and obj.data and obj.data.is_editmode:
            bm = bmesh.from_edit_mesh(obj.data)
            s.v_tangent = _find_vertex_tangent_neighbor_edit(bm, s.v_index)
        else:
            s.v_tangent = -1

    elif best["type"] == "EDGE":
        s.component_type = "EDGE"
        s.e_v1 = int(best["v1"])
        s.e_v2 = int(best["v2"])
        s.e_t = float(best["t"])

    elif best["type"] == "FACE":
        s.component_type = "FACE"
        s.f_v1 = int(best["v1"])
        s.f_v2 = int(best["v2"])
        s.f_v3 = int(best["v3"])
        u, v, w = best["w"]
        s.f_w1 = float(u)
        s.f_w2 = float(v)
        s.f_w3 = float(w)


def _compute_comp_point_world_from_attachment(s, obj_like, bm_or_me, mode: str):
    M = obj_like.matrix_world

    if mode == "EDIT":
        bm = bm_or_me
        bm.verts.ensure_lookup_table()

        if s.component_type == "VERT":
            i = s.v_index
            if i < 0 or i >= len(bm.verts):
                return None
            return M @ bm.verts[i].co

        if s.component_type == "EDGE":
            i1, i2 = s.e_v1, s.e_v2
            if min(i1, i2) < 0 or max(i1, i2) >= len(bm.verts):
                return None
            a = bm.verts[i1].co
            b = bm.verts[i2].co
            return M @ a.lerp(b, _clamp01(s.e_t))

        if s.component_type == "FACE":
            i1, i2, i3 = s.f_v1, s.f_v2, s.f_v3
            if min(i1, i2, i3) < 0 or max(i1, i2, i3) >= len(bm.verts):
                return None
            a = bm.verts[i1].co
            b = bm.verts[i2].co
            c = bm.verts[i3].co
            u, v, w = s.f_w1, s.f_w2, s.f_w3
            return M @ ((a * u) + (b * v) + (c * w))

        return None

    me = bm_or_me
    verts = me.vertices
    n = len(verts)

    if s.component_type == "VERT":
        i = s.v_index
        if i < 0 or i >= n:
            return None
        return M @ verts[i].co

    if s.component_type == "EDGE":
        i1, i2 = s.e_v1, s.e_v2
        if min(i1, i2) < 0 or max(i1, i2) >= n:
            return None
        a = verts[i1].co
        b = verts[i2].co
        return M @ a.lerp(b, _clamp01(s.e_t))

    if s.component_type == "FACE":
        i1, i2, i3 = s.f_v1, s.f_v2, s.f_v3
        if min(i1, i2, i3) < 0 or max(i1, i2, i3) >= n:
            return None
        a = verts[i1].co
        b = verts[i2].co
        c = verts[i3].co
        u, v, w = s.f_w1, s.f_w2, s.f_w3
        return M @ ((a * u) + (b * v) + (c * w))

    return None


def _update_offsets_to_match_current_cursor(scene, comp_point_world: Vector, comp_q: Quaternion):
    """
    IMPORTANT: updates offsets WITHOUT writing cursor.
    VERT rule: cursor rotation must remain fixed in WORLD space.
    If user rotates cursor manually, it becomes the new fixed rotation.
    """
    s = _get_settings(scene)

    cur_loc = _cursor_world(scene)
    cur_rot = _cursor_world_quat(scene)

    basis = comp_q.to_matrix()
    pos_off_local = basis.inverted() @ (cur_loc - comp_point_world)
    _set_pos_offset(scene, pos_off_local)

    if s.follow_rotation:
        if s.component_type == "VERT":
            _set_rot_offset(scene, cur_rot)  # fixed world rotation
        else:
            rot_off = _safe_quat(comp_q.inverted() @ cur_rot)
            _set_rot_offset(scene, rot_off)

    _set_last_applied_cursor(scene, cur_loc, cur_rot)


def _apply_attachment_to_cursor(scene, comp_point_world: Vector, comp_q: Quaternion, attach_obj=None):
    """Follow: write cursor only when it wasn't manually changed this tick."""
    s = _get_settings(scene)

    basis = comp_q.to_matrix()
    pos_off_local = _get_pos_offset(scene)

    out_loc = comp_point_world + (basis @ pos_off_local)

    out_rot = _cursor_world_quat(scene)
    if s.follow_rotation:
        rot_off = _get_rot_offset(scene)
        if s.component_type == "VERT":
            out_rot = rot_off  # fixed world rotation
        else:
            out_rot = comp_q @ rot_off

    _set_cursor_world(scene, out_loc)
    if s.follow_rotation:
        _set_cursor_world_quat(scene, out_rot)

    _set_last_applied_cursor(scene, out_loc, out_rot)

    # update xform cache so Undo/Redo is detected properly next time
    if attach_obj is not None:
        _update_obj_xform_cache(attach_obj)


def _get_attachment_component_transform(scene, depsgraph=None):
    """Return (comp_point_world, comp_quat_world, attach_obj) for current attachment."""
    s = _get_settings(scene)
    if not s or not _has_attachment(scene):
        return None, None, None

    obj = _find_object(scene, s.object_name)
    if not obj or obj.type != "MESH":
        return None, None, None

    mode, payload = _get_mesh_access_for_follow(obj, depsgraph)
    if mode == "NONE":
        return None, None, None

    try:
        if mode == "EDIT":
            bm = payload
            comp_point_world = _compute_comp_point_world_from_attachment(s, obj, bm, "EDIT")
            comp_q = _component_world_quat_from_data(s, obj, bm, "EDIT")
        else:
            obj_like, me = payload
            comp_point_world = _compute_comp_point_world_from_attachment(s, obj_like, me, "MESH")
            comp_q = _component_world_quat_from_data(s, obj_like, me, "MESH")
        return comp_point_world, comp_q, obj
    except Exception:
        return None, None, None
    finally:
        _free_mesh_access(mode, payload)


def _selected_component_transform(context):
    """Best-effort selected component transform for any active object type."""
    obj = context.active_object
    if not obj:
        return None, None, None

    # Mesh edit mode: use selected mesh components.
    if obj.type == "MESH" and obj.mode == "EDIT" and obj.data and obj.data.is_editmode:
        bm = bmesh.from_edit_mesh(obj.data)
        sel_faces = [f for f in bm.faces if f.select]
        sel_edges = [e for e in bm.edges if e.select]
        sel_verts = [v for v in bm.verts if v.select]

        if sel_faces:
            center_obj = Vector((0.0, 0.0, 0.0))
            normal_obj = Vector((0.0, 0.0, 0.0))
            for f in sel_faces:
                center_obj += f.calc_center_median()
                normal_obj += f.normal
            center_obj /= float(len(sel_faces))

            mw3 = obj.matrix_world.to_3x3()
            center_world = obj.matrix_world @ center_obj
            z_axis = _safe_normalize(mw3 @ normal_obj, Vector((0.0, 0.0, 1.0)))

            tangent_obj = None
            for f in sel_faces:
                if len(f.verts) >= 2:
                    tangent_obj = f.verts[1].co - f.verts[0].co
                    if tangent_obj.length_squared > _EPS:
                        break
            if tangent_obj is None:
                tangent_obj = Vector((1.0, 0.0, 0.0))

            x_axis = mw3 @ tangent_obj
            x_axis = x_axis - z_axis * x_axis.dot(z_axis)
            if x_axis.length_squared < _EPS:
                x_axis = Vector((1.0, 0.0, 0.0))
            q = _basis_to_quat(_make_orthonormal_basis(x_axis, z_axis, z_axis))
            return center_world, q, obj

        if sel_edges:
            center_obj = Vector((0.0, 0.0, 0.0))
            edge_dir_obj = Vector((0.0, 0.0, 0.0))
            for e in sel_edges:
                c = (e.verts[0].co + e.verts[1].co) * 0.5
                center_obj += c
                edge_dir_obj += (e.verts[1].co - e.verts[0].co)
            center_obj /= float(len(sel_edges))

            mw3 = obj.matrix_world.to_3x3()
            center_world = obj.matrix_world @ center_obj
            x_axis = _safe_normalize(mw3 @ edge_dir_obj, Vector((1.0, 0.0, 0.0)))

            normal_obj = Vector((0.0, 0.0, 0.0))
            for e in sel_edges:
                for v in e.verts:
                    normal_obj += v.normal
            z_axis = _safe_normalize(mw3 @ normal_obj, mw3 @ Vector((0.0, 0.0, 1.0)))
            q = _basis_to_quat(_make_orthonormal_basis(x_axis, z_axis, z_axis))
            return center_world, q, obj

        if sel_verts:
            center_obj = Vector((0.0, 0.0, 0.0))
            normal_obj = Vector((0.0, 0.0, 0.0))
            for v in sel_verts:
                center_obj += v.co
                normal_obj += v.normal
            center_obj /= float(len(sel_verts))

            mw3 = obj.matrix_world.to_3x3()
            center_world = obj.matrix_world @ center_obj
            z_axis = _safe_normalize(mw3 @ normal_obj, mw3 @ Vector((0.0, 0.0, 1.0)))
            x_axis = _safe_normalize(mw3 @ Vector((1.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)))
            q = _basis_to_quat(_make_orthonormal_basis(x_axis, z_axis, z_axis))
            return center_world, q, obj

    # Fallback for all non-mesh or object-level selection.
    loc = obj.matrix_world.translation.copy()
    rot = _safe_quat(obj.matrix_world.to_quaternion())
    return loc, rot, obj


def _resolve_origin_reference(context):
    """Resolve reference frame used by origin tools.
    Priority: current attachment -> selected component/object -> cursor transform.
    Returns (origin_pos, origin_rot, source_obj, source_tag).
    """
    scene = context.scene
    comp_point_world, comp_q, attach_obj = _get_attachment_component_transform(scene, context.evaluated_depsgraph_get())
    if comp_point_world is not None and comp_q is not None:
        return comp_point_world, comp_q, attach_obj, "ATTACHMENT"

    sel_loc, sel_rot, sel_obj = _selected_component_transform(context)
    if sel_loc is not None and sel_rot is not None:
        return sel_loc, sel_rot, sel_obj, "SELECTION"

    return _cursor_world(scene), _cursor_world_quat(scene), None, "CURSOR"


def _resolve_origin_base_and_current(context):
    """Return base transform and current virtual origin transform used by origin tools."""
    scene = context.scene
    s = _get_settings(scene)
    depsgraph = context.evaluated_depsgraph_get()

    base_pos, base_q, source_obj = _get_attachment_component_transform(scene, depsgraph)
    if base_pos is None or base_q is None:
        sel_loc, sel_rot, sel_obj = _selected_component_transform(context)
        if sel_loc is not None and sel_rot is not None:
            basis = sel_rot.to_matrix()
            current_origin_pos = sel_loc + (basis @ _get_pos_offset(scene))
            if s and s.follow_rotation:
                current_origin_q = _safe_quat(sel_rot @ _get_rot_offset(scene))
            else:
                current_origin_q = _get_rot_offset(scene)
            _log_debug(scene, f"Origin tools fallback to selected transform ({sel_obj.name}).")
            return sel_loc, sel_rot, current_origin_pos, current_origin_q, sel_obj, "SELECTION"

        cur_loc = _cursor_world(scene)
        cur_q = _cursor_world_quat(scene)
        _log_debug(scene, "Origin tools fallback to cursor frame (no attachment/selection transform found).")
        return cur_loc, cur_q, cur_loc, cur_q, None, "CURSOR"

    basis = base_q.to_matrix()
    current_origin_pos = base_pos + (basis @ _get_pos_offset(scene))
    if s and s.follow_rotation:
        current_origin_q = _safe_quat(base_q @ _get_rot_offset(scene))
    else:
        current_origin_q = _get_rot_offset(scene)

    return base_pos, base_q, current_origin_pos, current_origin_q, source_obj, "ATTACHMENT"


def _aim_z_quaternion(origin_world: Vector, target_world: Vector, x_hint: Vector = None):
    """Return a quaternion where Z axis points from origin to target."""
    aim_vec = target_world - origin_world
    if aim_vec.length_squared < _EPS:
        return None

    z_axis = _safe_normalize(aim_vec, Vector((0.0, 0.0, 1.0)))
    if x_hint is None:
        x_hint = Vector((1.0, 0.0, 0.0))

    x_axis = x_hint - z_axis * x_hint.dot(z_axis)
    if x_axis.length_squared < _EPS:
        fallback = Vector((1.0, 0.0, 0.0))
        if abs(fallback.dot(z_axis)) > 0.98:
            fallback = Vector((0.0, 1.0, 0.0))
        x_axis = fallback - z_axis * fallback.dot(z_axis)

    x_axis = _safe_normalize(x_axis, Vector((1.0, 0.0, 0.0)))
    y_axis = _safe_normalize(z_axis.cross(x_axis), Vector((0.0, 1.0, 0.0)))
    x_axis = _safe_normalize(y_axis.cross(z_axis), Vector((1.0, 0.0, 0.0)))
    basis = Matrix((x_axis, y_axis, z_axis)).transposed()
    return _basis_to_quat(basis)


# ------------------------------------------------------------
# Main tick (shared by timer + depsgraph)
# ------------------------------------------------------------

def _auto_attach_tick(scene, depsgraph, source=""):
    s = _get_settings(scene)
    if not s or not s.auto_attach:
        return

    # Per-object cursor state swap on active object change (context scene only)
    _handle_active_object_switch(scene, depsgraph)

    obj = bpy.context.active_object
    if not obj or obj.type != "MESH":
        _clear_attachment(scene, "Auto Attach: no active Mesh object.")
        return

    # Ensure binding points to current object if it has a saved state
    if s.object_name != obj.name and _obj_has_state(obj):
        s.object_name = obj.name
        s.mesh_name = obj.data.name if obj.data else ""

    cur_loc = _cursor_world(scene)
    cur_rot = _cursor_world_quat(scene)
    last_loc, last_rot = _get_last_applied_cursor(scene)

    user_moved = _loc_changed(cur_loc, last_loc)
    user_rotated = _rot_changed(cur_rot, last_rot)

    # If cursor changed (manual or by another addon/operator), adapt offsets / reattach
    if (not _has_attachment(scene)) or user_moved:
        tol = max(0.0, float(s.snap_tolerance))

        if obj.mode == "EDIT" and obj.data and obj.data.is_editmode:
            best = _find_nearest_component_in_edit(obj, cur_loc, tol)
        else:
            best = _find_nearest_component_objectmode(obj, depsgraph, cur_loc, tol)

        if not best:
            _clear_attachment(scene, "Auto Attach: cannot access mesh to find nearest.")
            return

        _set_attachment_from_best(scene, obj, best)

        mode, payload = _get_mesh_access_for_follow(obj, depsgraph)
        if mode == "NONE" or not payload:
            _clear_attachment(scene, "Auto Attach: cannot access mesh data.")
            return

        try:
            if mode == "EDIT":
                bm = payload
                comp_q = _component_world_quat_from_data(s, obj, bm, "EDIT")
                comp_point_world = _compute_comp_point_world_from_attachment(s, obj, bm, "EDIT")
            else:
                obj_like, me = payload
                comp_q = _component_world_quat_from_data(s, obj_like, me, "MESH")
                comp_point_world = _compute_comp_point_world_from_attachment(s, obj_like, me, "MESH")

            if comp_q is None or comp_point_world is None:
                _clear_attachment(scene, "Auto Attach: cannot compute component rotation.")
                return

            _update_offsets_to_match_current_cursor(scene, comp_point_world, comp_q)
            _set_status(scene, f"Auto Attached: {s.component_type}")

            try:
                _bbox_outside_counts.pop(scene.as_pointer(), None)
            except Exception:
                pass

            _obj_save_state(scene, obj)
            _update_obj_xform_cache(obj)

        finally:
            _free_mesh_access(mode, payload)

        return

    # Existing attachment follow
    attach_obj = _find_object(scene, s.object_name)
    if not attach_obj or attach_obj.type != "MESH":
        _clear_attachment(scene, "Auto Attach: attached object missing.")
        return

    mode, payload = _get_mesh_access_for_follow(attach_obj, depsgraph)
    if mode == "NONE" or not payload:
        _clear_attachment(scene, "Auto Attach: cannot access mesh data.")
        return

    try:
        if mode == "EDIT":
            bm = payload
            comp_point_world = _compute_comp_point_world_from_attachment(s, attach_obj, bm, "EDIT")
            comp_q = _component_world_quat_from_data(s, attach_obj, bm, "EDIT")
        else:
            obj_like, me = payload
            comp_point_world = _compute_comp_point_world_from_attachment(s, obj_like, me, "MESH")
            comp_q = _component_world_quat_from_data(s, obj_like, me, "MESH")

        if comp_point_world is None or comp_q is None:
            _clear_attachment(scene, "Auto Attach: attachment invalid (topology changed).")
            return

        # If user rotated manually: update offsets (do not write cursor)
        if user_rotated:
            _update_offsets_to_match_current_cursor(scene, comp_point_world, comp_q)
            _obj_save_state(scene, obj)
            _update_obj_xform_cache(attach_obj)
            return

        # NEW: if object transform changed (Undo/Redo etc.), force follow (unless user is moving cursor)
        obj_changed = _obj_xform_changed(attach_obj)
        if obj_changed and (not user_moved) and (not user_rotated):
            _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=attach_obj)
            _obj_save_state(scene, obj)
            return

        # Object Mode: ignore bbox always.
        is_edit_mode = (attach_obj.mode == "EDIT" and attach_obj.data and attach_obj.data.is_editmode)
        if is_edit_mode:
            margin = max(0.0, float(getattr(s, "bbox_margin", 0.0)))
            try:
                key = scene.as_pointer()
            except Exception:
                key = id(scene)
            prev_outside_count = _bbox_outside_counts.get(key, 0)

            basis = comp_q.to_matrix()
            pos_off_local = _get_pos_offset(scene)
            predicted_loc = comp_point_world + (basis @ pos_off_local)

            inside_now = _cursor_inside_object_bbox_world(attach_obj, depsgraph, cur_loc, margin)
            inside_pred = _cursor_inside_object_bbox_world(attach_obj, depsgraph, predicted_loc, margin)

            if not inside_now and not inside_pred:
                cnt = prev_outside_count + 1
                _bbox_outside_counts[key] = cnt

                if cnt <= _BBOX_GRACE_TICKS:
                    _set_status(scene, "Auto Attach: bbox check (grace)...")
                    return

                _set_status(scene, "Auto Attach: cursor outside bbox (freeze follow).")
                return
            else:
                _bbox_outside_counts.pop(key, None)

                # If follow was frozen while cursor was outside bbox, preserve the current
                # cursor transform when re-entering follow so attach does not create a jump.
                if prev_outside_count > _BBOX_GRACE_TICKS:
                    _update_offsets_to_match_current_cursor(scene, comp_point_world, comp_q)

        # Follow: write cursor
        _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=attach_obj)
        _obj_save_state(scene, obj)

    finally:
        _free_mesh_access(mode, payload)


# ------------------------------------------------------------
# Depsgraph handler (mesh/object changes)
# ------------------------------------------------------------

def _depsgraph_handler(depsgraph):
    _depsgraph_handler.__name__ = _HANDLER_TAG
    for scene in bpy.data.scenes:
        s = _get_settings(scene)
        if not s or not s.auto_attach:
            continue
        _auto_attach_tick(scene, depsgraph, source="DEPSGRAPH")


# ------------------------------------------------------------
# Properties
# ------------------------------------------------------------

class CursorAutoAttachSettings(PropertyGroup):
    auto_attach: BoolProperty(
        name="Auto Attach",
        description="Auto attach cursor to nearest component. Compatible with other cursor tools (Maya Pivot etc.).",
        default=False,
    )
    follow_rotation: BoolProperty(
        name="Follow Rotation",
        description="Cursor follows attached component rotation via an offset",
        default=True,
    )
    snap_tolerance: FloatProperty(
        name="Snap Tolerance",
        description="If cursor is within this distance of a vertex/edge, prefer attaching to it over a face",
        default=0.001,
        min=0.0,
        soft_max=1.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )
    bbox_margin: FloatProperty(
        name="BBox Margin (Edit Mode only)",
        description="Extra margin added around the attached object's world bounding box. Used ONLY in Edit Mode. In Object Mode, bbox is ignored.",
        default=0.05,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )

    status: StringProperty(default="")

    object_name: StringProperty(default="")
    mesh_name: StringProperty(default="")

    component_type: EnumProperty(
        name="Component",
        items=[
            ("NONE", "None", ""),
            ("VERT", "Vertex", ""),
            ("EDGE", "Edge", ""),
            ("FACE", "Face (Triangle)", ""),
        ],
        default="NONE",
    )

    v_index: IntProperty(default=-1)
    v_tangent: IntProperty(default=-1)

    e_v1: IntProperty(default=-1)
    e_v2: IntProperty(default=-1)
    e_t: FloatProperty(default=0.0, min=0.0, max=1.0)

    f_v1: IntProperty(default=-1)
    f_v2: IntProperty(default=-1)
    f_v3: IntProperty(default=-1)
    f_w1: FloatProperty(default=0.0)
    f_w2: FloatProperty(default=0.0)
    f_w3: FloatProperty(default=0.0)

    # rotation offset
    off_w: FloatProperty(default=1.0)
    off_x: FloatProperty(default=0.0)
    off_y: FloatProperty(default=0.0)
    off_z: FloatProperty(default=0.0)

    # position offset
    pos_off_x: FloatProperty(default=0.0)
    pos_off_y: FloatProperty(default=0.0)
    pos_off_z: FloatProperty(default=0.0)

    # last applied cursor transform
    last_cur_x: FloatProperty(default=0.0)
    last_cur_y: FloatProperty(default=0.0)
    last_cur_z: FloatProperty(default=0.0)

    last_rot_w: FloatProperty(default=1.0)
    last_rot_x: FloatProperty(default=0.0)
    last_rot_y: FloatProperty(default=0.0)
    last_rot_z: FloatProperty(default=0.0)


class CAA_OT_set_origin_pos_to_cursor(bpy.types.Operator):
    bl_idname = "caa.set_origin_pos_to_cursor"
    bl_label = "Set Origin Position to Cursor Position"

    def execute(self, context):
        scene = context.scene
        base_pos, base_q, _origin_pos, _origin_q, origin_obj, source = _resolve_origin_base_and_current(context)
        cur_loc = _cursor_world(scene)
        pos_off_local = base_q.conjugated() @ (cur_loc - base_pos)
        _set_pos_offset(scene, pos_off_local)
        src_name = origin_obj.name if origin_obj else source
        _log_debug(scene, f"Set origin position to cursor. source={src_name}, pos_off={tuple(round(v, 6) for v in pos_off_local)}")
        _set_status(scene, f"Origin position set to cursor position ({src_name}).")
        return {'FINISHED'}


class CAA_OT_set_origin_rot_to_cursor(bpy.types.Operator):
    bl_idname = "caa.set_origin_rot_to_cursor"
    bl_label = "Set Origin Orientation to Cursor Orientation"

    def execute(self, context):
        scene = context.scene
        s = _get_settings(scene)
        _base_pos, base_q, _origin_pos, _origin_q, origin_obj, source = _resolve_origin_base_and_current(context)
        cur_q = _cursor_world_quat(scene)
        if s and s.follow_rotation:
            rot_off = base_q.conjugated() @ cur_q
        else:
            rot_off = cur_q
        _set_rot_offset(scene, rot_off)
        src_name = origin_obj.name if origin_obj else source
        _log_debug(scene, f"Set origin orientation to cursor. source={src_name}, follow_rotation={bool(s and s.follow_rotation)}")
        _set_status(scene, f"Origin orientation set to cursor orientation ({src_name}).")
        return {'FINISHED'}


class CAA_OT_set_origin_pos_to_selected(bpy.types.Operator):
    bl_idname = "caa.set_origin_pos_to_selected"
    bl_label = "Set Origin Position to Selected Component Position"

    def execute(self, context):
        scene = context.scene
        base_pos, base_q, _origin_pos, _origin_q, _origin_obj, _source = _resolve_origin_base_and_current(context)
        sel_loc, _sel_rot, sel_obj = _selected_component_transform(context)
        if sel_loc is None:
            _log_debug(scene, "Set origin position from selection failed: no selected component/object.")
            self.report({'WARNING'}, "No selected component/object.")
            return {'CANCELLED'}
        pos_off_local = base_q.conjugated() @ (sel_loc - base_pos)
        _set_pos_offset(scene, pos_off_local)
        _log_debug(scene, f"Set origin position from selection. selected={sel_obj.name}, pos_off={tuple(round(v, 6) for v in pos_off_local)}")
        _set_status(scene, f"Origin position set from selection ({sel_obj.name}).")
        return {'FINISHED'}


class CAA_OT_set_origin_rot_to_selected(bpy.types.Operator):
    bl_idname = "caa.set_origin_rot_to_selected"
    bl_label = "Set Origin Orientation to Selected Component Orientation"

    def execute(self, context):
        scene = context.scene
        s = _get_settings(scene)
        _base_pos, base_q, _origin_pos, _origin_q, _origin_obj, _source = _resolve_origin_base_and_current(context)
        _sel_loc, sel_rot, sel_obj = _selected_component_transform(context)
        if sel_rot is None:
            _log_debug(scene, "Set origin orientation from selection failed: no selected component/object.")
            self.report({'WARNING'}, "No selected component/object.")
            return {'CANCELLED'}
        if s and s.follow_rotation:
            rot_off = base_q.conjugated() @ sel_rot
        else:
            rot_off = sel_rot
        _set_rot_offset(scene, rot_off)
        _log_debug(scene, f"Set origin orientation from selection. selected={sel_obj.name}, follow_rotation={bool(s and s.follow_rotation)}")
        _set_status(scene, f"Origin orientation set from selection ({sel_obj.name}).")
        return {'FINISHED'}


class CAA_OT_aim_origin_z_to_selected(bpy.types.Operator):
    bl_idname = "caa.aim_origin_z_to_selected"
    bl_label = "Aim Origin (Z) to Selection"

    def execute(self, context):
        scene = context.scene
        s = _get_settings(scene)
        _base_pos, base_q, origin_pos, origin_q, _origin_obj, _source = _resolve_origin_base_and_current(context)
        sel_loc, _sel_rot, sel_obj = _selected_component_transform(context)
        if sel_loc is None:
            _log_debug(scene, "Aim origin Z failed: no selected component/object.")
            self.report({'WARNING'}, "No selected component/object.")
            return {'CANCELLED'}

        x_hint = origin_q.to_matrix().col[0].xyz.copy()
        aimed_q = _aim_z_quaternion(origin_pos, sel_loc, x_hint)
        if aimed_q is None:
            _log_debug(scene, "Aim origin Z cancelled: origin and selection are coincident.")
            self.report({'WARNING'}, "Origin is already at selection.")
            return {'CANCELLED'}

        if s and s.follow_rotation:
            rot_off = base_q.conjugated() @ aimed_q
        else:
            rot_off = aimed_q
        _set_rot_offset(scene, rot_off)
        _log_debug(scene, f"Aim origin Z to selection. selected={sel_obj.name}, follow_rotation={bool(s and s.follow_rotation)}")
        _set_status(scene, f"Origin Z aimed to selection ({sel_obj.name}).")
        return {'FINISHED'}


class CAA_OT_set_cursor_rot_to_selected(bpy.types.Operator):
    bl_idname = "caa.set_cursor_rot_to_selected"
    bl_label = "Set Cursor Orientation to Selected Component Orientation"

    def execute(self, context):
        scene = context.scene
        _sel_loc, sel_rot, sel_obj = _selected_component_transform(context)
        if sel_rot is None:
            self.report({'WARNING'}, "No selected component/object.")
            return {'CANCELLED'}
        _set_cursor_world_quat(scene, sel_rot)
        _set_last_applied_cursor(scene, _cursor_world(scene), sel_rot)
        _set_status(scene, f"Cursor orientation set from selection ({sel_obj.name}).")
        return {'FINISHED'}


class CAA_OT_set_cursor_pos_to_selected(bpy.types.Operator):
    bl_idname = "caa.set_cursor_pos_to_selected"
    bl_label = "Set Cursor Position to Selected Component Position"

    def execute(self, context):
        scene = context.scene
        sel_loc, _sel_rot, sel_obj = _selected_component_transform(context)
        if sel_loc is None:
            self.report({'WARNING'}, "No selected component/object.")
            return {'CANCELLED'}
        _set_cursor_world(scene, sel_loc)
        _set_last_applied_cursor(scene, sel_loc, _cursor_world_quat(scene))
        _set_status(scene, f"Cursor position set from selection ({sel_obj.name}).")
        return {'FINISHED'}


class CAA_OT_aim_cursor_z_to_selected(bpy.types.Operator):
    bl_idname = "caa.aim_cursor_z_to_selected"
    bl_label = "Aim Cursor (Z) to Selection"

    def execute(self, context):
        scene = context.scene
        sel_loc, _sel_rot, sel_obj = _selected_component_transform(context)
        if sel_loc is None:
            self.report({'WARNING'}, "No selected component/object.")
            return {'CANCELLED'}

        cur_loc = _cursor_world(scene)
        cur_q = _cursor_world_quat(scene)
        x_hint = cur_q.to_matrix().col[0].xyz.copy()
        aimed_q = _aim_z_quaternion(cur_loc, sel_loc, x_hint)
        if aimed_q is None:
            self.report({'WARNING'}, "Cursor is already at selection.")
            return {'CANCELLED'}

        _set_cursor_world_quat(scene, aimed_q)
        _set_last_applied_cursor(scene, cur_loc, aimed_q)
        _set_status(scene, f"Cursor Z aimed to selection ({sel_obj.name}).")
        return {'FINISHED'}


class CAA_OT_reset_cursor_rot_world(bpy.types.Operator):
    bl_idname = "caa.reset_cursor_rot_world"
    bl_label = "Reset Cursor Orientation to World"

    def execute(self, context):
        scene = context.scene
        q = Quaternion((1.0, 0.0, 0.0, 0.0))
        _set_cursor_world_quat(scene, q)
        _set_last_applied_cursor(scene, _cursor_world(scene), q)
        _set_status(scene, "Cursor orientation reset to world.")
        return {'FINISHED'}


class CAA_OT_reset_cursor_pos_world(bpy.types.Operator):
    bl_idname = "caa.reset_cursor_pos_world"
    bl_label = "Reset Cursor Position to World"

    def execute(self, context):
        scene = context.scene
        loc = Vector((0.0, 0.0, 0.0))
        _set_cursor_world(scene, loc)
        _set_last_applied_cursor(scene, loc, _cursor_world_quat(scene))
        _set_status(scene, "Cursor position reset to world origin.")
        return {'FINISHED'}


class CAA_OT_reset_cursor_rot_to_selected_local(bpy.types.Operator):
    bl_idname = "caa.reset_cursor_rot_to_selected_local"
    bl_label = "Reset Cursor Orientation to Selected Object Local Orientation"

    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object.")
            return {'CANCELLED'}
        q = _safe_quat(obj.matrix_world.to_quaternion())
        _set_cursor_world_quat(scene, q)
        _set_last_applied_cursor(scene, _cursor_world(scene), q)
        _set_status(scene, f"Cursor orientation reset to {obj.name} local orientation.")
        return {'FINISHED'}


class CAA_OT_reset_cursor_pos_to_selected_origin(bpy.types.Operator):
    bl_idname = "caa.reset_cursor_pos_to_selected_origin"
    bl_label = "Reset Cursor Position to Selected Object Origin"

    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object.")
            return {'CANCELLED'}
        loc = obj.matrix_world.translation.copy()
        _set_cursor_world(scene, loc)
        _set_last_applied_cursor(scene, loc, _cursor_world_quat(scene))
        _set_status(scene, f"Cursor position reset to {obj.name} origin.")
        return {'FINISHED'}


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

class VIEW3D_PT_cursor_auto_attach(Panel):
    bl_label = "Cursor Auto Attach"
    bl_idname = "VIEW3D_PT_cursor_auto_attach"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cursor"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = _get_settings(scene)

        layout.prop(s, "auto_attach", toggle=True, text="Auto Attach")
        layout.prop(s, "follow_rotation", toggle=True)
        layout.prop(s, "snap_tolerance")
        layout.prop(s, "bbox_margin")

        layout.separator()

        box = layout.box()
        box.label(text="Attachment")
        box.label(text=f"Object: {s.object_name or '-'}")
        box.label(text=f"Type: {s.component_type}")

        if s.component_type == "VERT":
            box.label(text=f"Vertex: {s.v_index}")
            box.label(text="Rotation: FIXED (VERT)", icon="LOCKED")
        elif s.component_type == "EDGE":
            box.label(text=f"Edge: {s.e_v1}-{s.e_v2} t={s.e_t:.4f}")
        elif s.component_type == "FACE":
            box.label(text=f"Tri: {s.f_v1}, {s.f_v2}, {s.f_v3}")

        box.separator()
        box.label(text="Offsets")
        box.label(text=f"Pos: {s.pos_off_x:.4f}, {s.pos_off_y:.4f}, {s.pos_off_z:.4f}")
        box.label(text=f"Rot: {s.off_w:.4f}, {s.off_x:.4f}, {s.off_y:.4f}, {s.off_z:.4f}")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Origin")
        col.operator("caa.set_origin_pos_to_cursor", text="Set Origin Position to Cursor Position")
        col.operator("caa.set_origin_rot_to_cursor", text="Set Origin Orientation to Cursor Orientation")
        col.operator("caa.set_origin_pos_to_selected", text="Set Origin Position to Selected Component Position")
        col.operator("caa.set_origin_rot_to_selected", text="Set Origin Orientation to Selected Component Orientation")
        col.operator("caa.aim_origin_z_to_selected", text="Aim Origin (Z) to Selection")

        layout.separator()
        col = layout.column(align=True)
        col.label(text="Cursor")
        col.operator("caa.set_cursor_pos_to_selected", text="Set Cursor Position to Selected Component Position")
        col.operator("caa.set_cursor_rot_to_selected", text="Set Cursor Orientation to Selected Component Orientation")
        col.operator("caa.aim_cursor_z_to_selected", text="Aim Cursor (Z) to Selection")
        col.operator("caa.reset_cursor_pos_world", text="Reset Cursor Position to World")
        col.operator("caa.reset_cursor_rot_world", text="Reset Cursor Orientation to World")
        col.operator("caa.reset_cursor_pos_to_selected_origin", text="Reset Cursor Position to Selected Object Origin")
        col.operator("caa.reset_cursor_rot_to_selected_local", text="Reset Cursor Orientation to Selected Object Local Orientation")

        if s.status:
            layout.separator()
            layout.label(text=s.status, icon="INFO")


# ------------------------------------------------------------
# Register
# ------------------------------------------------------------

CLASSES = (
    CursorAutoAttachSettings,
    CAA_OT_set_origin_pos_to_cursor,
    CAA_OT_set_origin_rot_to_cursor,
    CAA_OT_set_origin_pos_to_selected,
    CAA_OT_set_origin_rot_to_selected,
    CAA_OT_aim_origin_z_to_selected,
    CAA_OT_set_cursor_rot_to_selected,
    CAA_OT_aim_cursor_z_to_selected,
    CAA_OT_set_cursor_pos_to_selected,
    CAA_OT_reset_cursor_rot_world,
    CAA_OT_reset_cursor_pos_world,
    CAA_OT_reset_cursor_rot_to_selected_local,
    CAA_OT_reset_cursor_pos_to_selected_origin,
    VIEW3D_PT_cursor_auto_attach,
)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)

    bpy.types.Scene.cursor_auto_attach_settings = PointerProperty(type=CursorAutoAttachSettings)

    _ensure_handler_registered()
    _ensure_timer_registered()


def unregister():
    _ensure_timer_unregistered()
    _ensure_handler_unregistered()

    if hasattr(bpy.types.Scene, "cursor_auto_attach_settings"):
        del bpy.types.Scene.cursor_auto_attach_settings

    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)

    _bbox_outside_counts.clear()
    _last_active_by_scene.clear()
    _last_obj_xform.clear()


if __name__ == "__main__":
    register()
