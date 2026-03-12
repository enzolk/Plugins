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
import time
import os
import tempfile
import json
import addon_utils
from bpy.app.handlers import persistent
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
_LOAD_RELOAD_TAG = "CURSOR_AUTO_ATTACH_LOAD_RELOAD"

_EPS = 1e-12

# "has cursor changed?" tolerances
CURSOR_LOC_EPS = 1e-10
CURSOR_ROT_EPS = 1e-10

# Timer interval (seconds)
TIMER_INTERVAL = 0.02
_timer_running = False

# Follow freeze distance (meters)
_DEFAULT_FREEZE_DISTANCE = 0.05  # 5 cm

# Per-object cursor state keys (custom properties)
_OBJ_STATE_PREFIX = "_caa_"
_OBJ_STATE_VERSION = 1

# Active object switch tracking (per scene)
_last_active_by_scene = {}  # scene_key -> {"ptr": int, "name": str}

# Track last known transform of objects (for Undo/Redo / fast moves)
_last_obj_xform = {}  # obj_ptr -> (loc(Vector3), rot(Quat), scale(Vector3))

# Edit-mode safety throttling (scene_ptr -> remaining ticks to skip)
_scene_edit_skip_ticks = {}

# Scene-level recovery/throttling helpers
_scene_force_follow_ticks = {}
_scene_last_depsgraph_tick = {}

# Frozen-idle throttling (scene-level)
_scene_idle_until = {}
_scene_frozen_streak = {}
_scene_last_frozen_sig = {}
_scene_last_cursor_obs = {}  # scene_key -> (loc, rot)
_scene_last_active_obs = {}  # scene_key -> active_obj_ptr
_scene_stable_streak = {}  # scene_key -> stable timer ticks

# If a depsgraph tick happened very recently, timer can skip this scene.
_TIMER_AFTER_DEPSGRAPH_SKIP_SEC = 0.015

# idle backoff when scene is repeatedly frozen and unchanged
_IDLE_MIN_INTERVAL = 0.08
_IDLE_MAX_INTERVAL = 0.40
_IDLE_STREAK_FOR_BACKOFF = 3

# deep idle tier (very stable frozen state)
_DEEP_IDLE_STREAK = 12
_DEEP_IDLE_INTERVAL = 0.75

# runtime soft refresh (no data loss)
_RUNTIME_REFRESH_PERIOD = 300.0  # 5 minutes
_next_runtime_refresh_at = 0.0
_hard_reload_pending = False
_hard_reload_in_progress = False

_RELOAD_STATE_KEY = "_caa_reload_state_json"
_SESSION_RELOAD_FLAG = "_caa_session_start_hard_reload_done"

# non-frozen stable idle backoff
_STABLE_IDLE_STREAK = 2
_STABLE_IDLE_BASE_INTERVAL = 0.25
_STABLE_IDLE_MAX_INTERVAL = 1.00

_DEBUG_LOG_DEFAULT_PATH = os.path.join(tempfile.gettempdir(), "cursor_follow_debug.log")

# Operators known to mutate topology in edit mode.
_SENSITIVE_EDIT_OP_KEYWORDS = (
    "MESH_OT_crease",
    "MESH_OT_bevel",
    "MESH_OT_merge",
    "MESH_OT_delete",
    "MESH_OT_dissolve",
    "MESH_OT_split",
    "MESH_OT_rip",
    "MESH_OT_subdivide",
    "MESH_OT_unsubdivide",
    "MESH_OT_poke",
    "MESH_OT_extrude",
    "MESH_OT_duplicate",
    "MESH_OT_separate",
    "MESH_OT_symmetrize",
)

# thresholds for object transform change detection
# NOTE: previous values (1e-12) were too strict and caused false positives
# from floating-point/evaluated-mesh jitter.
OBJ_LOC_EPS = 1e-8
OBJ_ROT_EPS = 1e-10
OBJ_SCL_EPS = 1e-8

# require N consecutive transform-change detections before applying obj-changed follow
OBJ_CHANGE_CONFIRM_TICKS = 2
_obj_change_streak = {}  # obj_ptr -> consecutive changed ticks


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


def _obj_xform_changed(obj) -> tuple:
    """
    Detect if object transform changed since last tick (Undo/Redo etc.).
    Returns: (changed: bool, details: dict)
    """
    if not obj:
        return False, {"ptr": 0, "loc_d2": 0.0, "rot_d2": 0.0, "scl_d2": 0.0}
    try:
        ptr = obj.as_pointer()
    except Exception:
        ptr = id(obj)

    loc, rot, scl = _decompose_matrix_world(obj)
    prev = _last_obj_xform.get(ptr)
    if prev is None:
        _last_obj_xform[ptr] = (loc, rot, scl)
        return False, {"ptr": ptr, "loc_d2": 0.0, "rot_d2": 0.0, "scl_d2": 0.0}

    ploc, prot, pscl = prev

    loc_d2 = float((loc - ploc).length_squared)

    # quat difference (sign invariant)
    qa = _safe_quat(rot)
    qb = _safe_quat(prot)
    d1 = (qa.w - qb.w) ** 2 + (qa.x - qb.x) ** 2 + (qa.y - qb.y) ** 2 + (qa.z - qb.z) ** 2
    d2 = (qa.w + qb.w) ** 2 + (qa.x + qb.x) ** 2 + (qa.y + qb.y) ** 2 + (qa.z + qb.z) ** 2
    rot_d2 = float(min(d1, d2))

    scl_d2 = float((scl - pscl).length_squared)

    changed = (loc_d2 > OBJ_LOC_EPS) or (rot_d2 > OBJ_ROT_EPS) or (scl_d2 > OBJ_SCL_EPS)
    return changed, {"ptr": ptr, "loc_d2": loc_d2, "rot_d2": rot_d2, "scl_d2": scl_d2}


def _update_obj_xform_cache(obj):
    if not obj:
        return
    try:
        ptr = obj.as_pointer()
    except Exception:
        ptr = id(obj)
    _last_obj_xform[ptr] = _decompose_matrix_world(obj)


def _scene_key(scene) -> int:
    try:
        return scene.as_pointer()
    except Exception:
        return id(scene)


def _schedule_edit_skip(scene, ticks: int = 1):
    if not scene:
        return
    key = _scene_key(scene)
    _scene_edit_skip_ticks[key] = max(int(ticks), int(_scene_edit_skip_ticks.get(key, 0)))


def _consume_edit_skip(scene) -> bool:
    if not scene:
        return False
    key = _scene_key(scene)
    ticks = int(_scene_edit_skip_ticks.get(key, 0))
    if ticks <= 0:
        return False
    if ticks == 1:
        _scene_edit_skip_ticks.pop(key, None)
    else:
        _scene_edit_skip_ticks[key] = ticks - 1
    return True


def _schedule_force_follow(scene, ticks: int = 1):
    if not scene:
        return
    key = _scene_key(scene)
    _scene_force_follow_ticks[key] = max(int(ticks), int(_scene_force_follow_ticks.get(key, 0)))


def _consume_force_follow(scene) -> bool:
    if not scene:
        return False
    key = _scene_key(scene)
    ticks = int(_scene_force_follow_ticks.get(key, 0))
    if ticks <= 0:
        return False
    if ticks == 1:
        _scene_force_follow_ticks.pop(key, None)
    else:
        _scene_force_follow_ticks[key] = ticks - 1
    return True


def _scene_idle_active(scene, now: float) -> bool:
    if not scene:
        return False
    key = _scene_key(scene)
    return float(_scene_idle_until.get(key, 0.0)) > float(now)


def _scene_idle_set(scene, now: float, frozen_sig: tuple):
    if not scene:
        return
    key = _scene_key(scene)
    last_sig = _scene_last_frozen_sig.get(key)
    if frozen_sig == last_sig:
        streak = int(_scene_frozen_streak.get(key, 0)) + 1
    else:
        streak = 1
    _scene_frozen_streak[key] = streak
    _scene_last_frozen_sig[key] = frozen_sig

    if streak >= _DEEP_IDLE_STREAK:
        interval = _DEEP_IDLE_INTERVAL
    elif streak < _IDLE_STREAK_FOR_BACKOFF:
        interval = TIMER_INTERVAL
    else:
        step = streak - _IDLE_STREAK_FOR_BACKOFF + 1
        interval = min(_IDLE_MIN_INTERVAL + 0.02 * step, _IDLE_MAX_INTERVAL)

    _scene_idle_until[key] = float(now + interval)


def _scene_idle_clear(scene):
    if not scene:
        return
    key = _scene_key(scene)
    _scene_idle_until.pop(key, None)
    _scene_frozen_streak.pop(key, None)
    _scene_last_frozen_sig.pop(key, None)


def _scene_cursor_observed_changed(scene) -> bool:
    if not scene:
        return False
    key = _scene_key(scene)
    cur_loc = _cursor_world(scene)
    cur_rot = _cursor_world_quat(scene)
    prev = _scene_last_cursor_obs.get(key)
    _scene_last_cursor_obs[key] = (cur_loc, cur_rot)
    if prev is None:
        return True
    ploc, prot = prev
    return _loc_changed(cur_loc, ploc) or _rot_changed(cur_rot, prot)


def _scene_active_observed_changed(scene) -> bool:
    if not scene:
        return False
    key = _scene_key(scene)
    try:
        active = bpy.context.view_layer.objects.active
        cur_ptr = active.as_pointer() if active else 0
    except Exception:
        cur_ptr = 0
    prev_ptr = int(_scene_last_active_obs.get(key, -1))
    _scene_last_active_obs[key] = int(cur_ptr)
    return cur_ptr != prev_ptr


def _scene_stable_idle_set(scene, now: float):
    if not scene:
        return
    key = _scene_key(scene)
    streak = int(_scene_stable_streak.get(key, 0)) + 1
    _scene_stable_streak[key] = streak

    if streak < _STABLE_IDLE_STREAK:
        return

    step = streak - _STABLE_IDLE_STREAK
    interval = min(_STABLE_IDLE_BASE_INTERVAL + 0.03 * step, _STABLE_IDLE_MAX_INTERVAL)
    _scene_idle_until[key] = max(float(_scene_idle_until.get(key, 0.0)), float(now + interval))


def _scene_stable_idle_clear(scene):
    if not scene:
        return
    _scene_stable_streak[_scene_key(scene)] = 0


def _has_sensitive_running_operator() -> bool:
    try:
        wm = bpy.context.window_manager
        ops = getattr(wm, "operators", None)
        if not ops:
            return False
        for op in ops:
            op_id = getattr(op, "bl_idname", "") or getattr(op, "idname", "")
            op_id_norm = str(op_id).replace(".", "_OT_").upper()
            if any(k in op_id_norm for k in _SENSITIVE_EDIT_OP_KEYWORDS):
                return True
    except Exception:
        return False
    return False


def _is_safe_edit_mesh_context(scene, obj) -> bool:
    if not scene or not obj or obj.type != "MESH":
        return False
    if obj.mode != "EDIT" or not obj.data or not obj.data.is_editmode:
        return False
    try:
        if bpy.context.scene is not scene:
            return False
        if bpy.context.active_object is not obj:
            return False
    except Exception:
        return False
    if _has_sensitive_running_operator():
        return False
    return True


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
# Handler / timer registration
# ------------------------------------------------------------



@persistent
def _load_reload_handler(_dummy=None):
    _load_reload_handler.__name__ = _LOAD_RELOAD_TAG
    _request_hard_reload(reason="file_load_or_new")

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

    for fn in bpy.app.handlers.load_post:
        if getattr(fn, "__name__", "") == _LOAD_RELOAD_TAG:
            break
    else:
        bpy.app.handlers.load_post.append(_load_reload_handler)

    for fn in bpy.app.handlers.load_factory_startup_post:
        if getattr(fn, "__name__", "") == _LOAD_RELOAD_TAG:
            break
    else:
        bpy.app.handlers.load_factory_startup_post.append(_load_reload_handler)


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

    to_remove = []
    for fn in bpy.app.handlers.load_post:
        if getattr(fn, "__name__", "") == _LOAD_RELOAD_TAG:
            to_remove.append(fn)
    for fn in to_remove:
        bpy.app.handlers.load_post.remove(fn)

    to_remove = []
    for fn in bpy.app.handlers.load_factory_startup_post:
        if getattr(fn, "__name__", "") == _LOAD_RELOAD_TAG:
            to_remove.append(fn)
    for fn in to_remove:
        bpy.app.handlers.load_factory_startup_post.remove(fn)


def _undo_redo_handler(_dummy=None):
    _undo_redo_handler.__name__ = _UNDO_REDO_TAG

    for scene in bpy.data.scenes:
        s = _get_settings(scene)
        if not s or not s.auto_attach:
            continue

        _debug_log(scene, "undo_redo_handler", attached=_has_attachment(scene), object_name=s.object_name or "")

        if not _has_attachment(scene):
            _debug_log(scene, "undo_redo_skip", reason="no_attachment")
            continue

        obj = _find_object(scene, s.object_name)
        if not obj or obj.type != "MESH":
            _debug_log(scene, "undo_redo_skip", reason="missing_or_non_mesh", object_name=s.object_name or "")
            continue

        # Force a couple of follow ticks after undo/redo to guarantee a stable resync,
        # even if mesh access is temporarily unavailable in this callback.
        _schedule_force_follow(scene, ticks=2)
        _debug_log(scene, "undo_redo_schedule", object=obj.name, force_ticks=2)

        mode, payload = _get_mesh_access_for_follow(obj, None)
        if mode == "NONE" or not payload:
            _debug_log(scene, "undo_redo_skip", reason="mesh_access_none", object=obj.name)
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
                _debug_log(scene, "undo_redo_skip", reason="component_compute_failed", object=obj.name, mode=mode)
                continue

            loc_written, rot_written = _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=obj)
            if loc_written or rot_written:
                _obj_save_state(scene, obj)
            _debug_log(scene, "undo_redo_apply", object=obj.name, component=s.component_type, loc_written=loc_written, rot_written=rot_written)
        finally:
            _free_mesh_access(mode, payload)


def _capture_reload_state() -> str:
    """Capture scene-level settings so hard reload is transparent."""
    try:
        wm = bpy.context.window_manager
    except Exception:
        wm = None

    if wm is None:
        return ""

    fields = (
        "auto_attach", "follow_rotation", "snap_tolerance", "freeze_distance",
        "object_name", "mesh_name", "component_type",
        "v_index", "v_tangent", "e_v1", "e_v2", "e_t",
        "f_v1", "f_v2", "f_v3", "f_w1", "f_w2", "f_w3",
        "off_w", "off_x", "off_y", "off_z",
        "pos_off_x", "pos_off_y", "pos_off_z",
        "last_cur_x", "last_cur_y", "last_cur_z",
        "last_rot_w", "last_rot_x", "last_rot_y", "last_rot_z",
        "debug_logging", "debug_log_to_file", "debug_log_path",
        "status",
    )

    payload = {"scenes": {}}
    try:
        scenes = getattr(bpy.data, "scenes", None)
    except Exception:
        scenes = None

    if not scenes:
        return ""

    for scene in scenes:
        s = _get_settings(scene)
        if not s:
            continue
        item = {}
        for f in fields:
            try:
                item[f] = getattr(s, f)
            except Exception:
                pass
        payload["scenes"][scene.name] = item

    try:
        return json.dumps(payload)
    except Exception:
        return ""


def _restore_reload_state_if_any():
    try:
        wm = bpy.context.window_manager
    except Exception:
        wm = None
    if wm is None:
        return

    raw = wm.get(_RELOAD_STATE_KEY, "")
    if not raw:
        return

    try:
        data = json.loads(raw)
    except Exception:
        wm.pop(_RELOAD_STATE_KEY, None)
        return

    # During addon register, Blender can expose RestrictData; defer restore until scenes exist.
    try:
        scenes = getattr(bpy.data, "scenes", None)
    except Exception:
        scenes = None

    if not scenes:
        return

    scene_map = data.get("scenes", {}) if isinstance(data, dict) else {}
    for scene in scenes:
        s = _get_settings(scene)
        if not s:
            continue
        item = scene_map.get(scene.name)
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            try:
                setattr(s, k, v)
            except Exception:
                pass

    wm.pop(_RELOAD_STATE_KEY, None)


def _do_hard_reload(reason: str = ""):
    global _hard_reload_in_progress, _next_runtime_refresh_at

    if _hard_reload_in_progress:
        return
    _hard_reload_in_progress = True

    try:
        try:
            wm = bpy.context.window_manager
        except Exception:
            wm = None

        if wm is not None:
            snap = _capture_reload_state()
            if snap:
                wm[_RELOAD_STATE_KEY] = snap

        mod_name = (__package__ or "").split(".")[0]
        if not mod_name:
            return

        addon_utils.disable(mod_name, default_set=False)
        addon_utils.enable(mod_name, default_set=False)
    finally:
        _hard_reload_in_progress = False
        _next_runtime_refresh_at = time.monotonic() + _RUNTIME_REFRESH_PERIOD


def _request_hard_reload(reason: str = "periodic"):
    global _hard_reload_pending
    if _hard_reload_pending:
        return

    try:
        scenes = getattr(bpy.data, "scenes", None)
    except Exception:
        scenes = None
    if scenes:
        for scene in scenes:
            _debug_log(scene, "hard_reload_requested", reason=reason)
    _hard_reload_pending = True

    def _runner():
        global _hard_reload_pending
        _hard_reload_pending = False
        _do_hard_reload(reason=reason)
        return None

    bpy.app.timers.register(_runner, first_interval=0.01)


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

    now = time.monotonic()

    if _next_runtime_refresh_at > 0.0 and now >= _next_runtime_refresh_at:
        _request_hard_reload(reason="periodic")
        return max(TIMER_INTERVAL, _DEEP_IDLE_INTERVAL)

    next_due = _DEEP_IDLE_INTERVAL

    for scene in bpy.data.scenes:
        s = _get_settings(scene)
        if not s or not s.auto_attach:
            continue

        key = _scene_key(scene)

        # If scene is in frozen idle mode, skip full tick until next due time.
        # Depsgraph/undo/redo callbacks still wake immediately.
        if _scene_idle_active(scene, now):
            if int(_scene_force_follow_ticks.get(key, 0)) <= 0:
                # Wake early if cursor/active object changed while idle.
                cursor_changed = _scene_cursor_observed_changed(scene)
                active_changed = _scene_active_observed_changed(scene)
                if (not cursor_changed) and (not active_changed):
                    due = float(_scene_idle_until.get(key, now + TIMER_INTERVAL)) - now
                    if due > 0.0:
                        next_due = min(next_due, max(TIMER_INTERVAL, due))
                    continue
                _scene_idle_clear(scene)

        _auto_attach_tick(scene, depsgraph, source="TIMER")
        next_due = min(next_due, TIMER_INTERVAL)

    return max(TIMER_INTERVAL, min(next_due, _DEEP_IDLE_INTERVAL))


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


def _debug_enabled(scene) -> bool:
    s = _get_settings(scene)
    return bool(s and getattr(s, "debug_logging", False))


def _debug_log(scene, event: str, **data):
    if not _debug_enabled(scene):
        return

    s = _get_settings(scene)
    ts = time.monotonic()
    bits = [f"t={ts:.6f}", f"event={event}"]
    for k, v in data.items():
        bits.append(f"{k}={v}")
    line = "[CursorFollow] " + " | ".join(bits)

    print(line)

    if not s or not getattr(s, "debug_log_to_file", False):
        return

    path = getattr(s, "debug_log_path", "") or _DEBUG_LOG_DEFAULT_PATH
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


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
    if not obj or obj.type != "MESH" or not obj.data or not obj.data.is_editmode:
        return None

    try:
        bm = bmesh.from_edit_mesh(obj.data)
        if bm is None:
            return None
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
    except Exception:
        return None

    M = obj.matrix_world

    best_vert = None
    best_edge = None
    best_face = None

    d2_vert = None
    d2_edge = None
    d2_face = None

    try:
        verts = list(bm.verts)
        edges = list(bm.edges)
    except Exception:
        return None

    for v in verts:
        pw = M @ v.co
        d2 = (pw - cursor_world).length_squared
        if d2_vert is None or d2 < d2_vert:
            d2_vert = d2
            best_vert = {"type": "VERT", "v": v.index, "p": pw}

    for e in edges:
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

    try:
        bm2 = bm.copy()
    except Exception:
        bm2 = None
    if bm2 is None:
        return _choose_best_with_priority(best_vert, d2_vert, best_edge, d2_edge, best_face, d2_face, snap_tol)

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


def _nearest_component_distance(obj, depsgraph, cursor_world: Vector, snap_tol: float):
    if not obj or obj.type != "MESH":
        return None

    if obj.mode == "EDIT" and obj.data and obj.data.is_editmode:
        if not _is_safe_edit_mesh_context(getattr(bpy.context, "scene", None), obj):
            return None
        nearest = _find_nearest_component_in_edit(obj, cursor_world, snap_tol)
    else:
        nearest = _find_nearest_component_objectmode(obj, depsgraph, cursor_world, snap_tol)

    if not nearest:
        return None

    p = nearest.get("p")
    if p is None:
        return None

    return (cursor_world - p).length


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
            if not (0 <= t_idx < len(verts)):
                t_idx = _find_vertex_tangent_neighbor_mesh(me, s.v_index)
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
            nrm = _edge_normal_from_mesh(me, i1, i2)
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


def _find_vertex_tangent_neighbor_mesh(me, v_index: int) -> int:
    """Pick a stable tangent neighbor for vertex orientation in object mode."""
    if not me:
        return -1
    verts = me.vertices
    if v_index < 0 or v_index >= len(verts):
        return -1

    best = -1
    best_d2 = float("inf")
    vco = verts[v_index].co

    try:
        edges = me.edges
        for e in edges:
            a = e.vertices[0]
            b = e.vertices[1]
            if a == v_index:
                o = b
            elif b == v_index:
                o = a
            else:
                continue
            d2 = (verts[o].co - vco).length_squared
            if d2 < best_d2:
                best_d2 = d2
                best = o
    except Exception:
        return -1

    return best


def _edge_normal_from_mesh(me, i1: int, i2: int) -> Vector:
    """Compute edge normal from linked polygon normals to match edit mode behavior."""
    if not me:
        return Vector((0.0, 0.0, 1.0))

    nrm = Vector((0.0, 0.0, 0.0))
    try:
        for poly in me.polygons:
            vids = poly.vertices
            for j in range(len(vids)):
                a = vids[j]
                b = vids[(j + 1) % len(vids)]
                if (a == i1 and b == i2) or (a == i2 and b == i1):
                    nrm += poly.normal
                    break
    except Exception:
        pass

    if nrm.length_squared < _EPS:
        try:
            verts = me.vertices
            nrm = verts[i1].normal + verts[i2].normal
        except Exception:
            nrm = Vector((0.0, 0.0, 1.0))

    return _safe_normalize(nrm, Vector((0.0, 0.0, 1.0)))


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
        elif obj.data:
            s.v_tangent = _find_vertex_tangent_neighbor_mesh(obj.data, s.v_index)
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
    """
    Follow: write cursor only when needed to avoid gizmo interaction jitter.
    Returns (loc_written: bool, rot_written: bool).
    """
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

    # IMPORTANT:
    # Avoid rewriting the cursor transform when values are effectively unchanged.
    # Continuous no-op writes (timer + depsgraph) can disturb gizmo picking,
    # especially when Transform Orientation/Pivot are both set to Cursor.
    cur_loc = _cursor_world(scene)
    cur_rot = _cursor_world_quat(scene)

    loc_written = False
    rot_written = False

    if _loc_changed(cur_loc, out_loc):
        _set_cursor_world(scene, out_loc)
        loc_written = True
    if s.follow_rotation and _rot_changed(cur_rot, out_rot):
        _set_cursor_world_quat(scene, out_rot)
        rot_written = True

    _set_last_applied_cursor(scene, out_loc, out_rot)

    # update xform cache so Undo/Redo is detected properly next time
    if attach_obj is not None:
        _update_obj_xform_cache(attach_obj)

    return loc_written, rot_written


# ------------------------------------------------------------
# Main tick (shared by timer + depsgraph)
# ------------------------------------------------------------

def _auto_attach_tick(scene, depsgraph, source=""):
    s = _get_settings(scene)
    if not s or not s.auto_attach:
        return

    now = time.monotonic()
    if source == "TIMER":
        last_deps = float(_scene_last_depsgraph_tick.get(_scene_key(scene), 0.0))
        delta = (now - last_deps)
        if delta < _TIMER_AFTER_DEPSGRAPH_SKIP_SEC:
            _debug_log(scene, "timer_skip_after_depsgraph", dt=f"{delta:.6f}")
            return

    _scene_cursor_observed_changed(scene)

    force_follow = _consume_force_follow(scene)
    if force_follow:
        _scene_idle_clear(scene)

    if (source != "TIMER") or force_follow:
        _debug_log(scene, "tick_start", source=source or "UNKNOWN", force_follow=force_follow)

    if _consume_edit_skip(scene):
        _set_status(scene, "Auto Attach: edit update in progress (deferred).")
        _debug_log(scene, "tick_skip_edit_deferred", source=source or "UNKNOWN")
        return

    # Per-object cursor state swap on active object change (context scene only)
    _handle_active_object_switch(scene, depsgraph)

    obj = bpy.context.active_object
    if not obj or obj.type != "MESH":
        _clear_attachment(scene, "Auto Attach: no active Mesh object.")
        _debug_log(scene, "tick_no_active_mesh", source=source or "UNKNOWN")
        return

    in_edit_mesh = bool(obj.mode == "EDIT" and obj.data and obj.data.is_editmode)
    if in_edit_mesh and (not _is_safe_edit_mesh_context(scene, obj)):
        _schedule_edit_skip(scene, ticks=1)
        _set_status(scene, "Auto Attach: unsafe edit context, tick skipped.")
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
    if (source != "TIMER") or user_moved or user_rotated:
        _debug_log(scene, "tick_state", user_moved=user_moved, user_rotated=user_rotated, attached=_has_attachment(scene), active=obj.name)

    if user_moved or user_rotated:
        _scene_idle_clear(scene)
        _scene_stable_idle_clear(scene)

    # If cursor changed (manual or by another addon/operator), adapt offsets / reattach
    if (not _has_attachment(scene)) or (user_moved and not force_follow):
        tol = max(0.0, float(s.snap_tolerance))

        if in_edit_mesh:
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

        if mode == "EDIT" and (not _is_safe_edit_mesh_context(scene, obj)):
            _schedule_edit_skip(scene, ticks=1)
            _set_status(scene, "Auto Attach: edit topology update detected, deferred.")
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
            _debug_log(scene, "reattach", component=s.component_type, active=obj.name)

            _obj_save_state(scene, obj)
            _update_obj_xform_cache(obj)
            _scene_idle_clear(scene)
            _scene_stable_idle_clear(scene)

        finally:
            _free_mesh_access(mode, payload)

        return

    # Existing attachment follow
    attach_obj = _find_object(scene, s.object_name)
    if not attach_obj or attach_obj.type != "MESH":
        _clear_attachment(scene, "Auto Attach: attached object missing.")
        _scene_idle_clear(scene)
        _scene_stable_idle_clear(scene)
        return

    pre_obj_changed = None
    pre_obj_delta = None

    if (source == "TIMER") and (not force_follow) and (not user_moved) and (not user_rotated) and (attach_obj.mode != "EDIT"):
        pre_obj_changed, pre_obj_delta = _obj_xform_changed(attach_obj)
        if not pre_obj_changed:
            _scene_stable_idle_set(scene, now)
            return

    mode, payload = _get_mesh_access_for_follow(attach_obj, depsgraph)
    if mode == "NONE" or not payload:
        _clear_attachment(scene, "Auto Attach: cannot access mesh data.")
        _scene_idle_clear(scene)
        _scene_stable_idle_clear(scene)
        return

    if mode == "EDIT" and (not _is_safe_edit_mesh_context(scene, attach_obj)):
        _schedule_edit_skip(scene, ticks=1)
        _set_status(scene, "Auto Attach: attached mesh in unsafe edit state, deferred.")
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
            _obj_save_state(scene, attach_obj)
            _update_obj_xform_cache(attach_obj)
            _scene_stable_idle_clear(scene)
            return

        # NEW: if object transform changed (Undo/Redo etc.), force follow (unless user is moving cursor)
        if pre_obj_changed is None:
            obj_changed, obj_delta = _obj_xform_changed(attach_obj)
        else:
            obj_changed, obj_delta = pre_obj_changed, pre_obj_delta
        if force_follow:
            loc_written, rot_written = _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=attach_obj)
            if loc_written or rot_written:
                _obj_save_state(scene, attach_obj)
            _set_status(scene, "Auto Attach: follow resynced.")
            _scene_stable_idle_clear(scene)
            _debug_log(scene, "force_follow_applied", object=attach_obj.name, component=s.component_type, loc_written=loc_written, rot_written=rot_written)
            return

        if obj_changed and (not user_moved) and (not user_rotated):
            _scene_stable_idle_clear(scene)
            try:
                obj_ptr = attach_obj.as_pointer()
            except Exception:
                obj_ptr = id(attach_obj)
            streak = int(_obj_change_streak.get(obj_ptr, 0)) + 1
            _obj_change_streak[obj_ptr] = streak

            _debug_log(
                scene,
                "obj_changed_detected",
                object=attach_obj.name,
                streak=streak,
                loc_d2=f"{obj_delta.get('loc_d2', 0.0):.12g}",
                rot_d2=f"{obj_delta.get('rot_d2', 0.0):.12g}",
                scl_d2=f"{obj_delta.get('scl_d2', 0.0):.12g}",
            )

            if streak >= OBJ_CHANGE_CONFIRM_TICKS:
                loc_written, rot_written = _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=attach_obj)
                if loc_written or rot_written:
                    _obj_save_state(scene, attach_obj)
                _obj_change_streak[obj_ptr] = 0
                _debug_log(scene, "follow_obj_changed", object=attach_obj.name, component=s.component_type, confirm=streak, loc_written=loc_written, rot_written=rot_written)
                return
        else:
            try:
                obj_ptr = attach_obj.as_pointer()
            except Exception:
                obj_ptr = id(attach_obj)
            _obj_change_streak[obj_ptr] = 0

        # Distance-only freeze with anti-spike protection:
        # freeze only if both the current cursor and the predicted follow cursor
        # are farther than threshold from their nearest attachable components.
        freeze_dist = max(0.0, float(getattr(s, "freeze_distance", _DEFAULT_FREEZE_DISTANCE)))
        snap_tol = float(s.snap_tolerance)

        basis = comp_q.to_matrix()
        pos_off_local = _get_pos_offset(scene)
        predicted_loc = comp_point_world + (basis @ pos_off_local)

        dist_now = _nearest_component_distance(attach_obj, depsgraph, cur_loc, snap_tol)
        dist_pred = _nearest_component_distance(attach_obj, depsgraph, predicted_loc, snap_tol)

        if (dist_now is not None) and (dist_pred is not None) and (dist_now > freeze_dist) and (dist_pred > freeze_dist):
            _set_status(scene, "Auto Attach: distance too high (follow frozen).")
            now2 = time.monotonic()
            frozen_sig = (attach_obj.name, s.component_type, round(float(dist_now), 6), round(float(dist_pred), 6), round(float(freeze_dist), 6))
            prev_sig = _scene_last_frozen_sig.get(_scene_key(scene))
            _scene_idle_set(scene, now2, frozen_sig)
            if frozen_sig != prev_sig:
                _debug_log(scene, "follow_frozen", dist_now=f"{dist_now:.6f}", dist_pred=f"{dist_pred:.6f}", freeze=f"{freeze_dist:.6f}")
            return

        _scene_idle_clear(scene)
        _scene_stable_idle_clear(scene)

        # Follow: write cursor
        loc_written, rot_written = _apply_attachment_to_cursor(scene, comp_point_world, comp_q, attach_obj=attach_obj)
        if loc_written or rot_written:
            _obj_save_state(scene, attach_obj)
            _debug_log(scene, "follow_applied", object=attach_obj.name, component=s.component_type, loc_written=loc_written, rot_written=rot_written)

    finally:
        _free_mesh_access(mode, payload)


# ------------------------------------------------------------
# Depsgraph handler (mesh/object changes)
# ------------------------------------------------------------

def _depsgraph_handler(depsgraph):
    _depsgraph_handler.__name__ = _HANDLER_TAG

    if _has_sensitive_running_operator():
        for scene in bpy.data.scenes:
            _schedule_edit_skip(scene, ticks=2)
        return

    for scene in bpy.data.scenes:
        s = _get_settings(scene)
        if not s or not s.auto_attach:
            continue
        try:
            _scene_last_depsgraph_tick[_scene_key(scene)] = time.monotonic()
            _scene_idle_clear(scene)
            _scene_stable_idle_clear(scene)
            _auto_attach_tick(scene, depsgraph, source="DEPSGRAPH")
        except Exception as ex:
            # Never let the depsgraph callback propagate unexpected errors.
            _schedule_edit_skip(scene, ticks=2)
            _debug_log(scene, "depsgraph_exception", error=str(ex))


# ------------------------------------------------------------
# Properties
# ------------------------------------------------------------

class CursorAutoAttachSettings(PropertyGroup):
    auto_attach: BoolProperty(
        name="Auto Attach",
        description="Auto attach cursor to nearest component. Compatible with other cursor tools (Maya Pivot etc.).",
        default=True,
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
    freeze_distance: FloatProperty(
        name="Freeze Distance",
        description="Freeze auto-attach/follow when cursor is farther than this distance from the nearest attachable component",
        default=_DEFAULT_FREEZE_DISTANCE,
        min=0.0,
        soft_max=10.0,
        subtype="DISTANCE",
        unit="LENGTH",
    )

    debug_logging: BoolProperty(
        name="Debug Logging",
        description="Enable verbose diagnostic logs for follow instability analysis",
        default=False,
    )
    debug_log_to_file: BoolProperty(
        name="Log To File",
        description="Also append debug logs to a file",
        default=False,
    )
    debug_log_path: StringProperty(
        name="Log File",
        description="Path used when Log To File is enabled",
        default=_DEBUG_LOG_DEFAULT_PATH,
        subtype="FILE_PATH",
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
        layout.prop(s, "freeze_distance")

        dbg = layout.box()
        dbg.label(text="Debug")
        dbg.prop(s, "debug_logging", toggle=True)
        dbg.prop(s, "debug_log_to_file", toggle=True)
        if s.debug_log_to_file:
            dbg.prop(s, "debug_log_path")

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

        if s.status:
            layout.separator()
            layout.label(text=s.status, icon="INFO")


# ------------------------------------------------------------
# Register
# ------------------------------------------------------------

CLASSES = (
    CursorAutoAttachSettings,
    VIEW3D_PT_cursor_auto_attach,
)


def register():
    global _next_runtime_refresh_at

    for c in CLASSES:
        bpy.utils.register_class(c)

    bpy.types.Scene.cursor_auto_attach_settings = PointerProperty(type=CursorAutoAttachSettings)

    _restore_reload_state_if_any()

    _ensure_handler_registered()
    _ensure_timer_registered()

    _next_runtime_refresh_at = time.monotonic() + _RUNTIME_REFRESH_PERIOD

    # One true hard reload at session start (equivalent disable/enable), once per Blender session.
    flag = bpy.app.driver_namespace.get(_SESSION_RELOAD_FLAG, False)
    if not flag:
        bpy.app.driver_namespace[_SESSION_RELOAD_FLAG] = True
        _request_hard_reload(reason="session_start")


def unregister():
    _ensure_timer_unregistered()
    _ensure_handler_unregistered()

    if hasattr(bpy.types.Scene, "cursor_auto_attach_settings"):
        del bpy.types.Scene.cursor_auto_attach_settings

    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)

    _last_active_by_scene.clear()
    _last_obj_xform.clear()
    _scene_edit_skip_ticks.clear()
    _scene_force_follow_ticks.clear()
    _scene_last_depsgraph_tick.clear()
    _scene_idle_until.clear()
    _scene_frozen_streak.clear()
    _scene_last_frozen_sig.clear()
    _scene_last_cursor_obs.clear()
    _scene_last_active_obs.clear()
    _scene_stable_streak.clear()
    _obj_change_streak.clear()

    global _next_runtime_refresh_at, _hard_reload_pending, _hard_reload_in_progress
    _next_runtime_refresh_at = 0.0
    _hard_reload_pending = False
    _hard_reload_in_progress = False


if __name__ == "__main__":
    register()
