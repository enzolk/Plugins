# ELK_META {"label": "Quick UV Orient Mat", "short_name": "UVMat", "tooltip": "Assign a temporary UV Mat.", "source": "python", "icon_svg": "grid-4x4.svg", "icon_color": "#ff5d3b", "apply_elk_ui_style": true}
# -*- coding: utf-8 -*-
"""
UV Checker Preview + Orient + Smart Cut Finder Tool for Maya
Compatible Maya Python 3 / Maya 2022+.

Features:
- Creates a procedural viewport UV checker material with orange directional triangles.
- Temporarily assigns the checker material to selected meshes while saving material assignments per face.
- Restores original material assignments exactly, including multi-material face assignments.
- Orients UV shells so a priority face can define the expected "down" direction.
- Smart UV Cut Finder:
    * Analyzes mesh topology and local surface changes.
    * Scores edges as UV seam candidates.
    * Offers several iterations: Minimal, Balanced, Relax Friendly, Bevel Aware, Aggressive.
    * Previews candidate cut edges using a temporary curve overlay.
    * Applies selected edges as UV cuts.

Important:
- The Smart Cut Finder is intentionally heuristic. It proposes good candidates, but UVs are artistic/technical decisions.
- Always save your scene before applying cuts on production assets.
"""

import json
import math

import maya.cmds as cmds
import maya.api.OpenMaya as om

try:
    from PySide2 import QtWidgets, QtCore
    from shiboken2 import wrapInstance
except Exception:
    QtWidgets = None
    QtCore = None
    wrapInstance = None


# ============================================================
# CONSTANTS
# ============================================================

WINDOW_NAME = "uvCheckerPreviewOrientSmartCut_UI"
MAT_NAME = "TRI_ROT_CHECKER_REBUILD"
SG_NAME = MAT_NAME + "_SG"
FINAL_BLEND_NAME = "UV_CHECKER"
STORE_NODE = "UV_CHECKER_PREVIEW_RESTORE_DATA"
STORE_ATTR = "data"

PREVIEW_GRP = "UV_SMART_CUT_PREVIEW_GRP"
PREVIEW_CURVE_PREFIX = "UV_SMART_CUT_PREVIEW_EDGE_"
PREVIEW_SHADER = "UV_SMART_CUT_PREVIEW_SHADER"
PREVIEW_SG = PREVIEW_SHADER + "SG"

SNAP_CHECKBOX = "uvCheckerOrientSnap90_CB"
USE_SELECTED_FACE_CB = "uvCheckerUseSelectedFacePriority_CB"
ITERATION_OPTION = "uvSmartCutIteration_OM"
INCLUDE_HARD_EDGES_CB = "uvSmartCutIncludeHardEdges_CB"
INCLUDE_BOUNDARY_CB = "uvSmartCutIncludeBoundary_CB"
INCLUDE_BEVELS_CB = "uvSmartCutIncludeBevels_CB"
CUT_BEVEL_CHAINS_CB = "uvSmartCutCutBevelChains_CB"
ANGLE_WEIGHT_FF = "uvSmartCutAngleWeight_FF"
MIN_EDGE_SCORE_FF = "uvSmartCutMinScore_FF"
MAX_CUTS_IF = "uvSmartCutMaxCuts_IF"

SMART_CUT_CACHE = {}


# ============================================================
# GENERIC UTILS
# ============================================================

def log(msg):
    print("[UV Tool] {}".format(msg))


def warning(msg):
    cmds.warning("[UV Tool] {}".format(msg))


def safe_delete(nodes):
    if not nodes:
        return
    if isinstance(nodes, str):
        nodes = [nodes]
    for n in nodes:
        try:
            if cmds.objExists(n):
                cmds.delete(n)
        except Exception:
            pass


def unique_list(seq):
    result = []
    seen = set()
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def get_selected_mesh_transforms():
    sel = cmds.ls(selection=True, long=True) or []
    result = []

    for item in sel:
        obj = item.split(".")[0]
        if not cmds.objExists(obj):
            continue

        if cmds.nodeType(obj) == "mesh":
            parents = cmds.listRelatives(obj, parent=True, fullPath=True) or []
            if parents:
                obj = parents[0]

        shapes = cmds.listRelatives(obj, shapes=True, fullPath=True, type="mesh") or []
        if shapes and obj not in result:
            result.append(obj)

    return result


def get_shape(transform):
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True, type="mesh") or []
    return shapes[0] if shapes else None


def get_dag_path(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return sel.getDagPath(0)


def get_mesh_fn(shape):
    return om.MFnMesh(get_dag_path(shape))


def component_exists(comp):
    try:
        obj = comp.split(".")[0]
        return cmds.objExists(obj)
    except Exception:
        return False


# ============================================================
# MATERIAL CREATION
# ============================================================

def create_uv_checker_material():
    if cmds.objExists(MAT_NAME) and cmds.objExists(SG_NAME):
        log("Material already exists: {}".format(MAT_NAME))
        return MAT_NAME, SG_NAME

    for n in cmds.ls(MAT_NAME + "*") or []:
        safe_delete(n)

    if cmds.objExists(FINAL_BLEND_NAME):
        safe_delete(FINAL_BLEND_NAME)

    mat = cmds.shadingNode("lambert", asShader=True, name=MAT_NAME)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=SG_NAME)
    cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)

    checker_place = cmds.shadingNode("place2dTexture", asUtility=True, name=MAT_NAME + "_CheckerPlace")
    checker = cmds.shadingNode("checker", asTexture=True, name=MAT_NAME + "_Checker")
    cmds.connectAttr(checker_place + ".outUV", checker + ".uvCoord", force=True)
    cmds.connectAttr(checker_place + ".outUvFilterSize", checker + ".uvFilterSize", force=True)
    cmds.setAttr(checker_place + ".repeatU", 16)
    cmds.setAttr(checker_place + ".repeatV", 16)
    cmds.setAttr(checker + ".color1", 0.12, 0.12, 0.12, type="double3")
    cmds.setAttr(checker + ".color2", 0.22, 0.22, 0.22, type="double3")

    ramp_place = cmds.shadingNode("place2dTexture", asUtility=True, name=MAT_NAME + "_RampPlace")
    ramp = cmds.shadingNode("ramp", asTexture=True, name=MAT_NAME + "_Ramp")
    cmds.connectAttr(ramp_place + ".outUV", ramp + ".uvCoord", force=True)
    cmds.connectAttr(ramp_place + ".outUvFilterSize", ramp + ".uvFilterSize", force=True)
    cmds.setAttr(ramp_place + ".repeatU", 16)
    cmds.setAttr(ramp_place + ".repeatV", 16)
    cmds.setAttr(ramp_place + ".rotateUV", 45)
    cmds.setAttr(ramp + ".type", 7)
    cmds.setAttr(ramp + ".interpolation", 4)
    cmds.setAttr(ramp + ".invert", True)
    cmds.setAttr(ramp + ".colorEntryList[0].position", 0.0)
    cmds.setAttr(ramp + ".colorEntryList[0].color", 0, 0, 0, type="double3")
    cmds.setAttr(ramp + ".colorEntryList[1].position", 1.0)
    cmds.setAttr(ramp + ".colorEntryList[1].color", 1, 1, 1, type="double3")

    contrast1 = cmds.shadingNode("contrast", asUtility=True, name=MAT_NAME + "_Contrast01")
    contrast2 = cmds.shadingNode("contrast", asUtility=True, name=MAT_NAME + "_Contrast02")
    contrast3 = cmds.shadingNode("contrast", asUtility=True, name=MAT_NAME + "_Contrast03")
    for c in [contrast1, contrast2, contrast3]:
        cmds.setAttr(c + ".contrast", 10, 10, 10, type="double3")
        cmds.setAttr(c + ".bias", 0.5, 0.5, 0.5, type="double3")
    cmds.connectAttr(ramp + ".outColor", contrast1 + ".value", force=True)
    cmds.connectAttr(contrast1 + ".outValue", contrast3 + ".value", force=True)
    cmds.connectAttr(contrast3 + ".outValue", contrast2 + ".value", force=True)

    arrow_color = cmds.shadingNode("colorConstant", asUtility=True, name=MAT_NAME + "_ArrowColor")
    cmds.setAttr(arrow_color + ".inColor", 1.0, 0.2837833166, 0.0, type="double3")

    blend1 = cmds.shadingNode("blendColors", asUtility=True, name=MAT_NAME + "_Blend01")
    cmds.connectAttr(checker + ".outColor", blend1 + ".color1", force=True)
    cmds.connectAttr(arrow_color + ".outColor", blend1 + ".color2", force=True)
    cmds.connectAttr(contrast2 + ".outValueY", blend1 + ".blender", force=True)

    blend2 = cmds.shadingNode("blendColors", asUtility=True, name=FINAL_BLEND_NAME)
    cmds.connectAttr(checker + ".outColor", blend2 + ".color1", force=True)
    cmds.connectAttr(blend1 + ".output", blend2 + ".color2", force=True)
    cmds.setAttr(blend2 + ".blender", 0.35)
    cmds.connectAttr(blend2 + ".output", mat + ".color", force=True)

    log("Material created: {}".format(MAT_NAME))
    return mat, sg


# ============================================================
# MATERIAL ASSIGNMENT STORE / RESTORE
# ============================================================

def ensure_store_node():
    if not cmds.objExists(STORE_NODE):
        node = cmds.createNode("network", name=STORE_NODE)
        cmds.addAttr(node, longName=STORE_ATTR, dataType="string")
    elif not cmds.attributeQuery(STORE_ATTR, node=STORE_NODE, exists=True):
        cmds.addAttr(STORE_NODE, longName=STORE_ATTR, dataType="string")
    return STORE_NODE


def save_restore_data(data):
    node = ensure_store_node()
    cmds.setAttr(node + "." + STORE_ATTR, json.dumps(data), type="string")


def load_restore_data():
    if not cmds.objExists(STORE_NODE):
        return None
    if not cmds.attributeQuery(STORE_ATTR, node=STORE_NODE, exists=True):
        return None
    raw = cmds.getAttr(STORE_NODE + "." + STORE_ATTR)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def clear_restore_data():
    safe_delete(STORE_NODE)


def has_active_preview():
    data = load_restore_data()
    return bool(data and data.get("objects"))


def get_face_sg(face):
    sets = cmds.listSets(object=face) or []
    for s in sets:
        if cmds.objExists(s) and cmds.nodeType(s) == "shadingEngine":
            return s
    return "initialShadingGroup"


def capture_assignments(transforms):
    data = {"objects": [], "selection": cmds.ls(selection=True, long=True) or []}
    for transform in transforms:
        shape = get_shape(transform)
        if not shape:
            continue
        face_count = cmds.polyEvaluate(shape, face=True)
        sg_map = {}
        for i in range(face_count):
            face = "{}.f[{}]".format(transform, i)
            sg = get_face_sg(face)
            sg_map.setdefault(sg, []).append(face)
        data["objects"].append({"transform": transform, "shape": shape, "assignments": sg_map})
    return data


def assign_in_chunks(components, sg, chunk_size=500):
    if not cmds.objExists(sg):
        return
    for i in range(0, len(components), chunk_size):
        chunk = [c for c in components[i:i + chunk_size] if component_exists(c)]
        if chunk:
            try:
                cmds.sets(chunk, edit=True, forceElement=sg)
            except Exception as e:
                log("Restore failed for {}: {}".format(sg, e))


def assign_uv_checker_preview():
    if has_active_preview():
        result = cmds.confirmDialog(
            title="UV Checker Preview déjà actif",
            message="Un preview est déjà actif. Restaurer les matériaux originaux avant de continuer ?",
            button=["Restore puis continuer", "Annuler"],
            defaultButton="Restore puis continuer",
            cancelButton="Annuler",
            dismissString="Annuler"
        )
        if result != "Restore puis continuer":
            return
        restore_original_materials(silent=True)

    _, sg = create_uv_checker_material()
    transforms = get_selected_mesh_transforms()
    if not transforms:
        warning("Sélectionne au moins un mesh.")
        return

    data = capture_assignments(transforms)
    save_restore_data(data)
    for transform in transforms:
        try:
            cmds.sets(transform, edit=True, forceElement=sg)
        except Exception as e:
            log("Assign failed on {}: {}".format(transform, e))
    update_status()
    log("Preview assigned to selection.")


def restore_original_materials(silent=False):
    data = load_restore_data()
    if not data or not data.get("objects"):
        if not silent:
            warning("Aucune assignation sauvegardée.")
        return
    for obj_data in data.get("objects", []):
        for sg, comps in obj_data.get("assignments", {}).items():
            assign_in_chunks(comps, sg)
    old_sel = data.get("selection") or []
    existing = [s for s in old_sel if cmds.objExists(s.split(".")[0])]
    if existing:
        try:
            cmds.select(existing, replace=True)
        except Exception:
            pass
    clear_restore_data()
    update_status()
    if not silent:
        log("Original materials restored.")


# ============================================================
# UV ORIENT
# ============================================================

def get_uv_shell_ids(fn):
    result = fn.getUvShellsIds()
    a, b = result
    if isinstance(a, int):
        return list(b), a
    return list(a), b


def normalize_angle(deg):
    while deg > 180.0:
        deg -= 360.0
    while deg < -180.0:
        deg += 360.0
    return deg


def snap_angle_90(deg):
    return round(deg / 90.0) * 90.0


def get_selected_face_components():
    comps = cmds.filterExpand(cmds.ls(selection=True, flatten=True) or [], selectionMask=34) or []
    result = []
    for c in comps:
        try:
            obj = c.split(".")[0]
            idx = int(c.split("[")[-1].split("]")[0])
            result.append((cmds.ls(obj, long=True)[0] if cmds.objExists(obj) else obj, idx))
        except Exception:
            pass
    return result


def solve_uv_down_direction_for_face(fn, points, us, vs, face_id, world_down):
    normal = fn.getPolygonNormal(face_id, om.MSpace.kWorld)
    if normal.length() < 0.0001:
        return None
    normal.normalize()
    down = world_down - normal * (world_down * normal)
    if down.length() < 0.0001:
        return None
    down.normalize()
    side = normal ^ down
    if side.length() < 0.0001:
        return None
    side.normalize()

    verts = fn.getPolygonVertices(face_id)
    aa = ab = bb = au = bu = av = bv = 0.0
    valid_edges = 0
    for i in range(len(verts)):
        j = (i + 1) % len(verts)
        v0, v1 = verts[i], verts[j]
        e3 = points[v1] - points[v0]
        if e3.length() < 0.00001:
            continue
        try:
            uv0 = fn.getPolygonUVid(face_id, i)
            uv1 = fn.getPolygonUVid(face_id, j)
        except Exception:
            continue
        du = us[uv1] - us[uv0]
        dv = vs[uv1] - vs[uv0]
        if abs(du) < 0.000001 and abs(dv) < 0.000001:
            continue
        a = e3 * down
        b = e3 * side
        aa += a * a
        ab += a * b
        bb += b * b
        au += a * du
        bu += b * du
        av += a * dv
        bv += b * dv
        valid_edges += 1
    if valid_edges < 2:
        return None
    det = aa * bb - ab * ab
    if abs(det) < 0.0000001:
        return None
    inv00 = bb / det
    inv01 = -ab / det
    uv_down_u = inv00 * au + inv01 * bu
    uv_down_v = inv00 * av + inv01 * bv
    length = math.sqrt(uv_down_u * uv_down_u + uv_down_v * uv_down_v)
    if length < 0.000001:
        return None
    return uv_down_u / length, uv_down_v / length


def face_belongs_to_uv_set(fn, face_id, uv_set):
    verts = fn.getPolygonVertices(face_id)
    for local_id in range(len(verts)):
        try:
            uv_id = fn.getPolygonUVid(face_id, local_id)
            if uv_id in uv_set:
                return True
        except Exception:
            pass
    return False


def shell_for_face(fn, face_id, shell_ids):
    verts = fn.getPolygonVertices(face_id)
    shell_hits = []
    for local_id in range(len(verts)):
        try:
            uv_id = fn.getPolygonUVid(face_id, local_id)
            shell_hits.append(shell_ids[uv_id])
        except Exception:
            pass
    if not shell_hits:
        return None
    return max(set(shell_hits), key=shell_hits.count)


def orient_uv_shells_down_on_transform(transform, snap_90=True, use_selected_priority=True):
    shape = get_shape(transform)
    if not shape:
        return 0
    fn = get_mesh_fn(shape)
    points = fn.getPoints(om.MSpace.kWorld)
    us, vs = fn.getUVs()
    shell_ids, shell_count = get_uv_shell_ids(fn)
    shells = {}
    for uv_id, sid in enumerate(shell_ids):
        shells.setdefault(sid, []).append(uv_id)

    selected_faces = get_selected_face_components() if use_selected_priority else []
    priority_by_shell = {}
    for sel_obj, face_id in selected_faces:
        # Accept transform or shape matching.
        if sel_obj == transform or sel_obj == shape or sel_obj.endswith(transform.split("|")[-1]):
            sid = shell_for_face(fn, face_id, shell_ids)
            if sid is not None:
                priority_by_shell[sid] = face_id

    world_down = om.MVector(0.0, -1.0, 0.0)
    rotated_count = 0

    for shell_id, uv_ids in shells.items():
        uv_set = set(uv_ids)
        dirs = []

        if shell_id in priority_by_shell:
            result = solve_uv_down_direction_for_face(fn, points, us, vs, priority_by_shell[shell_id], world_down)
            if result:
                dirs.append(result)
        else:
            # Auto mode: larger faces contribute more, but only faces with a valid projected down.
            for face_id in range(fn.numPolygons):
                if not face_belongs_to_uv_set(fn, face_id, uv_set):
                    continue
                result = solve_uv_down_direction_for_face(fn, points, us, vs, face_id, world_down)
                if result:
                    area_weight = max(0.0001, fn.getPolygonArea(face_id, om.MSpace.kWorld))
                    dirs.append((result[0] * area_weight, result[1] * area_weight))

        if not dirs:
            continue

        dir_u = sum(d[0] for d in dirs)
        dir_v = sum(d[1] for d in dirs)
        length = math.sqrt(dir_u * dir_u + dir_v * dir_v)
        if length < 0.000001:
            continue
        dir_u /= length
        dir_v /= length

        current_angle = math.degrees(math.atan2(dir_v, dir_u))
        rotation = normalize_angle(-90.0 - current_angle)
        if snap_90:
            rotation = snap_angle_90(rotation)
        if abs(rotation) < 0.001:
            continue

        min_u = min(us[i] for i in uv_ids)
        max_u = max(us[i] for i in uv_ids)
        min_v = min(vs[i] for i in uv_ids)
        max_v = max(vs[i] for i in uv_ids)
        pivot_u = (min_u + max_u) * 0.5
        pivot_v = (min_v + max_v) * 0.5
        uv_components = ["{}.map[{}]".format(transform, i) for i in uv_ids]
        try:
            cmds.polyEditUV(uv_components, relative=True, rotation=True, angle=rotation, pivotU=pivot_u, pivotV=pivot_v)
            rotated_count += 1
            src = "priority face {}".format(priority_by_shell[shell_id]) if shell_id in priority_by_shell else "auto average"
            log("{} shell {} rotated {:.2f}° ({})".format(transform, shell_id, rotation, src))
        except Exception as e:
            log("Orient failed shell {}: {}".format(shell_id, e))

    return rotated_count


def orient_selected_uv_shells_down():
    transforms = get_selected_mesh_transforms()
    if not transforms:
        warning("Sélectionne au moins un mesh ou une face.")
        return
    snap_90 = cmds.checkBox(SNAP_CHECKBOX, query=True, value=True) if cmds.checkBox(SNAP_CHECKBOX, exists=True) else True
    use_prio = cmds.checkBox(USE_SELECTED_FACE_CB, query=True, value=True) if cmds.checkBox(USE_SELECTED_FACE_CB, exists=True) else True
    old_sel = cmds.ls(selection=True, long=True) or []
    total = 0
    for t in transforms:
        total += orient_uv_shells_down_on_transform(t, snap_90=snap_90, use_selected_priority=use_prio)
    if old_sel:
        try:
            cmds.select(old_sel, replace=True)
        except Exception:
            pass
    log("UV Orient done. Shells rotated: {}".format(total))


# ============================================================
# SMART UV CUT FINDER
# ============================================================

def edge_key(v0, v1):
    return tuple(sorted((int(v0), int(v1))))


def vec_angle_deg(a, b):
    if a.length() < 1e-8 or b.length() < 1e-8:
        return 0.0
    aa = om.MVector(a)
    bb = om.MVector(b)
    aa.normalize()
    bb.normalize()
    dot = max(-1.0, min(1.0, aa * bb))
    return math.degrees(math.acos(dot))


def is_edge_hard_by_normals(fn, edge_faces, face_normals, edge_id, threshold=1.0):
    faces = edge_faces.get(edge_id, [])
    if len(faces) != 2:
        return False
    return vec_angle_deg(face_normals[faces[0]], face_normals[faces[1]]) > threshold


def build_mesh_edge_data(transform):
    shape = get_shape(transform)
    if not shape:
        return None
    fn = get_mesh_fn(shape)
    points = fn.getPoints(om.MSpace.kWorld)
    face_normals = [fn.getPolygonNormal(i, om.MSpace.kWorld) for i in range(fn.numPolygons)]
    face_areas = []
    for i in range(fn.numPolygons):
        try:
            face_areas.append(fn.getPolygonArea(i, om.MSpace.kWorld))
        except Exception:
            face_areas.append(0.0)

    edge_to_faces = {}
    edge_to_verts = {}
    vert_pair_to_edge = {}

    for e_id in range(fn.numEdges):
        try:
            verts = fn.getEdgeVertices(e_id)
            edge_to_verts[e_id] = (verts[0], verts[1])
            vert_pair_to_edge[edge_key(verts[0], verts[1])] = e_id
        except Exception:
            pass

    for f_id in range(fn.numPolygons):
        verts = fn.getPolygonVertices(f_id)
        for i in range(len(verts)):
            v0 = verts[i]
            v1 = verts[(i + 1) % len(verts)]
            e_id = vert_pair_to_edge.get(edge_key(v0, v1))
            if e_id is not None:
                edge_to_faces.setdefault(e_id, []).append(f_id)

    avg_edge_len = 0.0
    lengths = []
    for e_id, (v0, v1) in edge_to_verts.items():
        length = (points[v1] - points[v0]).length()
        lengths.append(length)
    if lengths:
        avg_edge_len = sum(lengths) / float(len(lengths))

    return {
        "transform": transform,
        "shape": shape,
        "fn": fn,
        "points": points,
        "face_normals": face_normals,
        "face_areas": face_areas,
        "edge_to_faces": edge_to_faces,
        "edge_to_verts": edge_to_verts,
        "avg_edge_len": avg_edge_len,
    }


def edge_convexity(points, face_normals, edge_verts, faces):
    # Heuristic sign for concave/convex. Positive is treated as convex-ish, negative as concave-ish.
    if len(faces) != 2:
        return 0.0
    v0, v1 = edge_verts
    edge_vec = points[v1] - points[v0]
    if edge_vec.length() < 1e-8:
        return 0.0
    edge_vec.normalize()
    n0 = om.MVector(face_normals[faces[0]])
    n1 = om.MVector(face_normals[faces[1]])
    cross = n0 ^ n1
    return cross * edge_vec


def score_edge_for_cut(mesh_data, edge_id, strategy):
    points = mesh_data["points"]
    normals = mesh_data["face_normals"]
    areas = mesh_data["face_areas"]
    edge_to_faces = mesh_data["edge_to_faces"]
    edge_to_verts = mesh_data["edge_to_verts"]
    avg_len = max(mesh_data["avg_edge_len"], 1e-6)

    faces = edge_to_faces.get(edge_id, [])
    v0, v1 = edge_to_verts[edge_id]
    length = (points[v1] - points[v0]).length()
    length_ratio = min(3.0, length / avg_len)
    boundary = len(faces) == 1
    nonmanifold = len(faces) > 2

    score = 0.0
    reasons = []

    if boundary:
        score += strategy["boundary"]
        reasons.append("boundary")
    if nonmanifold:
        score += 100.0
        reasons.append("nonmanifold")

    angle = 0.0
    if len(faces) == 2:
        angle = vec_angle_deg(normals[faces[0]], normals[faces[1]])
        angle_norm = min(1.0, angle / 90.0)
        score += angle_norm * strategy["angle"]
        if angle > strategy["hard_angle"]:
            score += strategy["hard_bonus"]
            reasons.append("hard-angle {:.1f}".format(angle))

        conv = edge_convexity(points, normals, (v0, v1), faces)
        if conv < -0.01:
            score += strategy["concave_bonus"]
            reasons.append("concave")
        else:
            score += strategy["convex_bonus"]

        small_area = min(areas[faces[0]], areas[faces[1]])
        big_area = max(areas[faces[0]], areas[faces[1]], 1e-6)
        area_ratio = small_area / big_area
        if area_ratio < strategy["bevel_area_ratio"] and angle > strategy["bevel_min_angle"]:
            score += strategy["bevel_bonus"]
            reasons.append("bevel-transition")

    score += length_ratio * strategy["length"]

    # Penalize very short edges unless strategy wants bevel detail.
    if length_ratio < 0.35:
        score -= strategy["short_penalty"]
        reasons.append("short")

    return {
        "edge_id": edge_id,
        "score": score,
        "angle": angle,
        "boundary": boundary,
        "faces": list(faces),
        "verts": [int(v0), int(v1)],
        "reasons": reasons,
    }


def smart_cut_strategy(name):
    strategies = {
        "Minimal": {
            "threshold": 72.0, "max_cuts": 250, "angle": 70.0, "hard_angle": 55.0, "hard_bonus": 30.0,
            "boundary": 5.0, "concave_bonus": 18.0, "convex_bonus": 2.0, "length": 4.0,
            "short_penalty": 18.0, "bevel_area_ratio": 0.18, "bevel_min_angle": 35.0, "bevel_bonus": 2.0,
        },
        "Balanced": {
            "threshold": 52.0, "max_cuts": 600, "angle": 65.0, "hard_angle": 38.0, "hard_bonus": 26.0,
            "boundary": 8.0, "concave_bonus": 22.0, "convex_bonus": 4.0, "length": 5.0,
            "short_penalty": 12.0, "bevel_area_ratio": 0.22, "bevel_min_angle": 25.0, "bevel_bonus": 10.0,
        },
        "Relax Friendly": {
            "threshold": 38.0, "max_cuts": 1200, "angle": 58.0, "hard_angle": 25.0, "hard_bonus": 20.0,
            "boundary": 10.0, "concave_bonus": 20.0, "convex_bonus": 6.0, "length": 5.0,
            "short_penalty": 8.0, "bevel_area_ratio": 0.28, "bevel_min_angle": 18.0, "bevel_bonus": 14.0,
        },
        "Bevel Aware": {
            "threshold": 44.0, "max_cuts": 900, "angle": 55.0, "hard_angle": 32.0, "hard_bonus": 22.0,
            "boundary": 8.0, "concave_bonus": 18.0, "convex_bonus": 3.0, "length": 4.0,
            "short_penalty": 4.0, "bevel_area_ratio": 0.35, "bevel_min_angle": 15.0, "bevel_bonus": 24.0,
        },
        "Aggressive": {
            "threshold": 28.0, "max_cuts": 2500, "angle": 52.0, "hard_angle": 18.0, "hard_bonus": 18.0,
            "boundary": 12.0, "concave_bonus": 18.0, "convex_bonus": 8.0, "length": 6.0,
            "short_penalty": 2.0, "bevel_area_ratio": 0.45, "bevel_min_angle": 10.0, "bevel_bonus": 20.0,
        },
    }
    return strategies.get(name, strategies["Balanced"]).copy()


def get_ui_strategy():
    name = "Balanced"
    if cmds.optionMenu(ITERATION_OPTION, exists=True):
        name = cmds.optionMenu(ITERATION_OPTION, query=True, value=True)
    s = smart_cut_strategy(name)

    if cmds.floatField(MIN_EDGE_SCORE_FF, exists=True):
        val = cmds.floatField(MIN_EDGE_SCORE_FF, query=True, value=True)
        if val > 0:
            s["threshold"] = val
    if cmds.intField(MAX_CUTS_IF, exists=True):
        val = cmds.intField(MAX_CUTS_IF, query=True, value=True)
        if val > 0:
            s["max_cuts"] = val
    if cmds.floatField(ANGLE_WEIGHT_FF, exists=True):
        val = cmds.floatField(ANGLE_WEIGHT_FF, query=True, value=True)
        if val >= 0:
            s["angle"] = val
    return name, s


def analyze_smart_cuts_for_transform(transform, strategy):
    data = build_mesh_edge_data(transform)
    if not data:
        return []
    candidates = []
    for e_id in range(data["fn"].numEdges):
        item = score_edge_for_cut(data, e_id, strategy)
        if item["score"] >= strategy["threshold"]:
            candidates.append(item)
    candidates.sort(key=lambda x: x["score"], reverse=True)
    candidates = candidates[:int(strategy["max_cuts"])]
    return candidates


def analyze_smart_cuts_selected():
    transforms = get_selected_mesh_transforms()
    if not transforms:
        warning("Sélectionne au moins un mesh.")
        return {}
    iteration, strategy = get_ui_strategy()
    result = {}
    for t in transforms:
        result[t] = analyze_smart_cuts_for_transform(t, strategy)
        log("{}: {} candidate cuts found using '{}'".format(t, len(result[t]), iteration))
    SMART_CUT_CACHE.clear()
    SMART_CUT_CACHE.update(result)
    return result


def ensure_preview_shader():
    if cmds.objExists(PREVIEW_SHADER) and cmds.objExists(PREVIEW_SG):
        return PREVIEW_SHADER, PREVIEW_SG
    safe_delete([PREVIEW_SHADER, PREVIEW_SG])
    shader = cmds.shadingNode("lambert", asShader=True, name=PREVIEW_SHADER)
    sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=PREVIEW_SG)
    cmds.connectAttr(shader + ".outColor", sg + ".surfaceShader", force=True)
    cmds.setAttr(shader + ".color", 0.0, 1.0, 1.0, type="double3")
    cmds.setAttr(shader + ".incandescence", 0.0, 0.35, 0.35, type="double3")
    return shader, sg


def clear_smart_cut_preview():
    safe_delete(PREVIEW_GRP)


def preview_smart_cuts():
    if not SMART_CUT_CACHE:
        analyze_smart_cuts_selected()
    clear_smart_cut_preview()
    _, sg = ensure_preview_shader()
    grp = cmds.group(empty=True, name=PREVIEW_GRP)

    total = 0
    for transform, candidates in SMART_CUT_CACHE.items():
        shape = get_shape(transform)
        if not shape:
            continue
        data = build_mesh_edge_data(transform)
        points = data["points"]
        for item in candidates:
            e_id = item["edge_id"]
            v0, v1 = data["edge_to_verts"][e_id]
            p0 = points[v0]
            p1 = points[v1]
            name = PREVIEW_CURVE_PREFIX + str(total)
            crv = cmds.curve(d=1, p=[(p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)], name=name)
            try:
                cmds.sets(crv, edit=True, forceElement=sg)
                cmds.setAttr(crv + ".overrideEnabled", 1)
                cmds.setAttr(crv + ".overrideColor", 18)
                cmds.setAttr(crv + ".lineWidth", 3)
            except Exception:
                pass
            try:
                cmds.parent(crv, grp)
            except Exception:
                pass
            total += 1
    log("Preview created: {} candidate edges.".format(total))


def edge_components_from_cache():
    comps = []
    for transform, candidates in SMART_CUT_CACHE.items():
        for item in candidates:
            comps.append("{}.e[{}]".format(transform, item["edge_id"]))
    return comps


def select_smart_cut_edges():
    if not SMART_CUT_CACHE:
        analyze_smart_cuts_selected()
    comps = edge_components_from_cache()
    if comps:
        cmds.select(comps, replace=True)
        log("Selected {} candidate edges.".format(len(comps)))
    else:
        warning("Aucun edge candidat trouvé.")


def apply_smart_cuts():
    if not SMART_CUT_CACHE:
        analyze_smart_cuts_selected()
    comps = edge_components_from_cache()
    if not comps:
        warning("Aucun edge candidat à couper.")
        return
    result = cmds.confirmDialog(
        title="Apply Smart UV Cuts",
        message="Appliquer {} UV cuts ?\n\nConseil : sauvegarde ta scène avant sur un asset important.".format(len(comps)),
        button=["Apply", "Cancel"],
        defaultButton="Apply",
        cancelButton="Cancel",
        dismissString="Cancel"
    )
    if result != "Apply":
        return
    old_sel = cmds.ls(selection=True, long=True) or []
    try:
        cmds.select(comps, replace=True)
        # polyMapCut applies cuts to selected edges.
        cmds.polyMapCut()
        log("Applied {} UV cuts.".format(len(comps)))
    except Exception as e:
        warning("polyMapCut failed: {}".format(e))
    finally:
        if old_sel:
            try:
                cmds.select(old_sel, replace=True)
            except Exception:
                pass


def analyze_preview_smart_cuts():
    analyze_smart_cuts_selected()
    preview_smart_cuts()


# ============================================================
# UI
# ============================================================

STATUS_TEXT = None
SCRIPT_JOBS = []


def update_status():
    global STATUS_TEXT
    if not STATUS_TEXT or not cmds.control(STATUS_TEXT, exists=True):
        return
    if has_active_preview():
        data = load_restore_data()
        count = len(data.get("objects", [])) if data else 0
        cmds.text(STATUS_TEXT, edit=True, label="Status : Preview actif sur {} objet(s).".format(count), backgroundColor=(0.35, 0.22, 0.05))
    else:
        cmds.text(STATUS_TEXT, edit=True, label="Status : Aucun preview actif.", backgroundColor=(0.18, 0.18, 0.18))


def ask_restore_if_active(reason=""):
    if not has_active_preview():
        return
    msg = "Un UV Checker Preview est encore actif."
    if reason:
        msg += "\n\nRaison : " + reason
    msg += "\n\nRéassigner les matériaux d'origine maintenant ?"
    result = cmds.confirmDialog(
        title="Restore UV Checker Preview ?",
        message=msg,
        button=["Oui, restore", "Non"],
        defaultButton="Oui, restore",
        cancelButton="Non",
        dismissString="Non"
    )
    if result == "Oui, restore":
        restore_original_materials()


def kill_script_jobs():
    global SCRIPT_JOBS
    for job in SCRIPT_JOBS:
        try:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        except Exception:
            pass
    SCRIPT_JOBS = []


def on_ui_close():
    ask_restore_if_active("fermeture de l'UI")
    kill_script_jobs()


def on_uv_editor_closed():
    ask_restore_if_active("fermeture/collapse de l'UV Editor")


def install_script_jobs():
    global SCRIPT_JOBS
    kill_script_jobs()
    if not cmds.window(WINDOW_NAME, exists=True):
        return
    if cmds.control("polyTexturePlacementPanel1Window", exists=True):
        SCRIPT_JOBS.append(cmds.scriptJob(uiDeleted=["polyTexturePlacementPanel1Window", on_uv_editor_closed], parent=WINDOW_NAME))
    if cmds.control("polyTexturePlacementPanel1", exists=True):
        SCRIPT_JOBS.append(cmds.scriptJob(uiDeleted=["polyTexturePlacementPanel1", on_uv_editor_closed], parent=WINDOW_NAME))
    SCRIPT_JOBS.append(cmds.scriptJob(event=["NewSceneOpened", lambda: ask_restore_if_active("changement de scène")], parent=WINDOW_NAME))


def show_ui():
    global STATUS_TEXT
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="UV Checker Preview + Orient + Smart Cuts", sizeable=True, widthHeight=(380, 620), closeCommand=on_ui_close)
    cmds.scrollLayout(horizontalScrollBarThickness=0)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnOffset=("both", 10))

    cmds.text(label="UV Checker Preview", align="center", height=28, font="boldLabelFont")
    cmds.button(label="Create / Assign UV Checker to Selection", height=34, command=lambda *_: assign_uv_checker_preview())
    cmds.button(label="Restore Original Materials", height=34, command=lambda *_: restore_original_materials())
    STATUS_TEXT = cmds.text(label="Status :", align="center", height=28, backgroundColor=(0.18, 0.18, 0.18))

    cmds.separator(height=10, style="in")
    cmds.text(label="UV Orient", align="center", height=24, font="boldLabelFont")
    cmds.checkBox(SNAP_CHECKBOX, label="Snap rotation to 90°", value=True)
    cmds.checkBox(USE_SELECTED_FACE_CB, label="Use selected face as shell priority", value=True)
    cmds.button(label="Orient UV Shells Down", height=34, command=lambda *_: orient_selected_uv_shells_down())
    cmds.text(label="Tip : sélectionne une face prioritaire si un shell contient plusieurs faces 3D.", align="center")

    cmds.separator(height=10, style="in")
    cmds.text(label="Smart UV Cut Finder", align="center", height=24, font="boldLabelFont")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(120, 220))
    cmds.text(label="Iteration")
    cmds.optionMenu(ITERATION_OPTION)
    for item in ["Minimal", "Balanced", "Relax Friendly", "Bevel Aware", "Aggressive"]:
        cmds.menuItem(label=item)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(160, 160))
    cmds.text(label="Angle Weight")
    cmds.floatField(ANGLE_WEIGHT_FF, value=65.0, minValue=0.0, precision=2)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(160, 160))
    cmds.text(label="Min Score Override (0=auto)")
    cmds.floatField(MIN_EDGE_SCORE_FF, value=0.0, minValue=0.0, precision=2)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnWidth2=(160, 160))
    cmds.text(label="Max Cuts Override (0=auto)")
    cmds.intField(MAX_CUTS_IF, value=0, minValue=0)
    cmds.setParent("..")

    cmds.button(label="Analyze + Preview Smart Cuts", height=34, command=lambda *_: analyze_preview_smart_cuts())
    cmds.button(label="Select Candidate Edges", height=30, command=lambda *_: select_smart_cut_edges())
    cmds.button(label="Apply UV Cuts", height=34, backgroundColor=(0.35, 0.22, 0.05), command=lambda *_: apply_smart_cuts())
    cmds.button(label="Clear Cut Preview", height=28, command=lambda *_: clear_smart_cut_preview())

    cmds.text(
        label="Smart Cuts analyse les edges selon angle, concavité, boundaries, bevel-like transitions et longueur.\nLes itérations changent les seuils/scoring. Toujours vérifier la preview avant Apply.",
        align="center"
    )

    cmds.separator(height=10, style="none")
    cmds.button(label="Close", height=28, command=lambda *_: cmds.deleteUI(WINDOW_NAME))

    cmds.showWindow(WINDOW_NAME)
    update_status()
    install_script_jobs()


show_ui()
