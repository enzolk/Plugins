# ELK_META {"label": "fill selection maya", "short_name": "FillBB", "tooltip": "Crée automatiquement une bounding box polygonale autour de la sélection actuelle.", "source": "python", "icon_svg": "box.svg", "icon_color": "#36d6ff", "apply_elk_ui_style": false, "quick_favorite": false, "secondary_scripts": []}
# -*- coding: utf-8 -*-
"""
Fill Selection Primitives - Maya version
---------------------------------------
Recréation Maya de l'add-on Blender "Fill Selection Primitives".

Fonctionnalités :
- Calcule la bounding box de la sélection active Maya.
- Fonctionne avec objets, vertices, edges, faces et CV/NURBS sélectionnés.
- Crée une primitive qui remplit la sélection : Cube, Cylinder, UV Sphere, Disc, Quad Sphere.
- Option Proportional Transform.
- Orientation AUTO / X / Y / Z pour Cylinder et Disc.
- Objets créés marqués avec attributs custom pour être reconstruits/modifiés.
- UI PySide2/PySide6 compatible Maya.

Installation rapide :
1. Place ce fichier dans ton dossier scripts Maya.
2. Lance dans Maya :

import importlib
import fill_selection_maya
importlib.reload(fill_selection_maya)
fill_selection_maya.show()
"""

from __future__ import print_function

import math
import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except Exception:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance


LOG_PREFIX = "[FillSelectionMaya]"
WINDOW_OBJECT_NAME = "FillSelectionMayaWindow"
EPSILON = 0.0001


# -----------------------------------------------------------------------------
# Logs / helpers
# -----------------------------------------------------------------------------

def log(message):
    print("{} {}".format(LOG_PREFIX, message))


def log_quad_sphere(message):
    log("[QuadSphere] {}".format(message))


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def build_unique_name(base_name):
    if not cmds.objExists(base_name):
        return base_name
    index = 1
    while True:
        candidate = "{}_{:03d}".format(base_name, index)
        if not cmds.objExists(candidate):
            return candidate
        index += 1



def maya_short_name(node):
    """Retourne le nom court d'un node Maya, sans chemin DAG."""
    if not node:
        return node
    return str(node).split("|")[-1]


def maya_safe_name(name, fallback="FillSelectionNode"):
    """Nettoie un nom pour qu'il soit utilisable dans cmds.rename / cmds.duplicate(name=...)."""
    raw = maya_short_name(name or fallback)
    raw = raw.split(".")[0]
    safe = []
    for char in raw:
        if char.isalnum() or char == "_":
            safe.append(char)
        else:
            safe.append("_")
    cleaned = "".join(safe).strip("_")
    return cleaned or fallback


def build_unique_safe_name(base_name):
    return build_unique_name(maya_safe_name(base_name))


def safe_delete_ui(object_name):
    for widget in QtWidgets.QApplication.allWidgets():
        try:
            if widget.objectName() == object_name:
                widget.close()
                widget.deleteLater()
        except Exception:
            pass


def vec_min(a, b):
    return om.MVector(min(a.x, b.x), min(a.y, b.y), min(a.z, b.z))


def vec_max(a, b):
    return om.MVector(max(a.x, b.x), max(a.y, b.y), max(a.z, b.z))


def tuple3(v):
    return (float(v.x), float(v.y), float(v.z))


def rounded_tuple(v):
    return tuple(round(value, 5) for value in tuple3(v))


class SelectionBounds(object):
    def __init__(self, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum

    @property
    def center(self):
        return (self.minimum + self.maximum) * 0.5

    @property
    def size(self):
        return self.maximum - self.minimum



class OrientedSelectionBounds(SelectionBounds):
    """Bounding box calculée dans le repère local d'un objet, puis replacée en world."""

    def __init__(self, minimum, maximum, matrix):
        super(OrientedSelectionBounds, self).__init__(minimum, maximum)
        self.matrix = matrix
        self.inverse_matrix = matrix.inverse()
        self.is_oriented = True

    @property
    def world_center(self):
        local_center = om.MPoint(self.center.x, self.center.y, self.center.z)
        world_center = local_center * self.matrix
        return om.MVector(world_center.x, world_center.y, world_center.z)


def get_active_object_transform_matrix():
    raw_selection = cmds.ls(selection=True, long=True, flatten=True) or []
    if not raw_selection:
        return None

    active = raw_selection[0].split(".")[0]
    if not active or not cmds.objExists(active):
        return None

    if cmds.nodeType(active) not in ("transform", "joint"):
        parent = cmds.listRelatives(active, parent=True, fullPath=True) or []
        active = parent[0] if parent else active

    try:
        values = cmds.xform(active, query=True, matrix=True, worldSpace=True)
        return om.MMatrix(values)
    except Exception:
        return None


def build_oriented_bounds_from_points(points, matrix):
    if not points or matrix is None:
        return None

    inverse_matrix = matrix.inverse()
    local_points = []
    for point in points:
        p = om.MPoint(point.x, point.y, point.z) * inverse_matrix
        local_points.append(om.MVector(p.x, p.y, p.z))

    local_bounds = build_bounds(local_points)
    if not local_bounds:
        return None

    return OrientedSelectionBounds(local_bounds.minimum, local_bounds.maximum, matrix)



def _dot_tuple_matrix(vec, matrix):
    return (
        vec[0] * matrix[0][0] + vec[1] * matrix[1][0] + vec[2] * matrix[2][0],
        vec[0] * matrix[0][1] + vec[1] * matrix[1][1] + vec[2] * matrix[2][1],
        vec[0] * matrix[0][2] + vec[1] * matrix[1][2] + vec[2] * matrix[2][2],
    )


def _jacobi_eigen_symmetric_3x3(matrix, iterations=32):
    """Eigen decomposition simple pour matrice symétrique 3x3.

    Retourne les valeurs propres et les vecteurs propres en colonnes.
    Implémentation volontairement sans numpy pour rester compatible Maya.
    """
    a = [[float(matrix[r][c]) for c in range(3)] for r in range(3)]
    v = [[1.0 if r == c else 0.0 for c in range(3)] for r in range(3)]

    for _ in range(iterations):
        # Plus gros coefficient hors diagonale.
        p, q = 0, 1
        max_value = abs(a[p][q])
        for i, j in ((0, 2), (1, 2)):
            value = abs(a[i][j])
            if value > max_value:
                max_value = value
                p, q = i, j

        if max_value < 1e-12:
            break

        app = a[p][p]
        aqq = a[q][q]
        apq = a[p][q]

        if abs(apq) < 1e-12:
            continue

        tau = (aqq - app) / (2.0 * apq)
        t = 1.0 / (abs(tau) + math.sqrt(1.0 + tau * tau))
        if tau < 0.0:
            t = -t
        c = 1.0 / math.sqrt(1.0 + t * t)
        s = t * c

        for k in range(3):
            if k != p and k != q:
                aik = a[k][p]
                akq = a[k][q]
                a[k][p] = aik * c - akq * s
                a[p][k] = a[k][p]
                a[k][q] = akq * c + aik * s
                a[q][k] = a[k][q]

        a[p][p] = app * c * c + aqq * s * s - 2.0 * apq * s * c
        a[q][q] = app * s * s + aqq * c * c + 2.0 * apq * s * c
        a[p][q] = 0.0
        a[q][p] = 0.0

        for k in range(3):
            vip = v[k][p]
            viq = v[k][q]
            v[k][p] = vip * c - viq * s
            v[k][q] = viq * c + vip * s

    values = [a[0][0], a[1][1], a[2][2]]
    vectors = [
        om.MVector(v[0][0], v[1][0], v[2][0]),
        om.MVector(v[0][1], v[1][1], v[2][1]),
        om.MVector(v[0][2], v[1][2], v[2][2]),
    ]

    ordered = sorted(range(3), key=lambda idx: values[idx], reverse=True)
    values = [values[i] for i in ordered]
    vectors = [vectors[i].normal() if vectors[i].length() > 1e-8 else om.MVector(1, 0, 0) for i in ordered]
    return values, vectors


def _orthonormalize_axes(axes):
    x = axes[0].normal() if axes[0].length() > 1e-8 else om.MVector(1, 0, 0)

    y = axes[1] - x * (axes[1] * x)
    if y.length() < 1e-8:
        # Fallback : cherche un axe assez différent de X.
        fallback = om.MVector(0, 1, 0) if abs(x.y) < 0.9 else om.MVector(0, 0, 1)
        y = fallback - x * (fallback * x)
    y = y.normal()

    z = x ^ y
    if z.length() < 1e-8:
        z = om.MVector(0, 0, 1)
    z = z.normal()

    # Force un repère droit.
    y = z ^ x
    y = y.normal() if y.length() > 1e-8 else om.MVector(0, 1, 0)

    return x, y, z


def _build_matrix_from_axes_and_center(x_axis, y_axis, z_axis, center):
    return om.MMatrix([
        x_axis.x, x_axis.y, x_axis.z, 0.0,
        y_axis.x, y_axis.y, y_axis.z, 0.0,
        z_axis.x, z_axis.y, z_axis.z, 0.0,
        center.x, center.y, center.z, 1.0,
    ])


def _bounds_size_for_axes(points, matrix):
    inverse_matrix = matrix.inverse()
    local_points = []
    for point in points:
        p = om.MPoint(point.x, point.y, point.z) * inverse_matrix
        local_points.append(om.MVector(p.x, p.y, p.z))
    bounds = build_bounds(local_points)
    if not bounds:
        return None, None
    return bounds, bounds.size


def _optimize_minor_axes_roll(points, x_axis, y_axis, z_axis, center, steps=72):
    """Optimise la rotation des axes Y/Z autour de l'axe principal X.

    Le PCA trouve très bien l'axe long, mais sur une section symétrique ou presque
    symétrique, les axes secondaires peuvent être arbitraires. Cette fonction teste
    plusieurs rolls autour de X et garde la section la plus serrée.
    """
    x_axis = x_axis.normal() if x_axis.length() > 1e-8 else om.MVector(1, 0, 0)
    y_axis = y_axis.normal() if y_axis.length() > 1e-8 else om.MVector(0, 1, 0)
    z_axis = z_axis.normal() if z_axis.length() > 1e-8 else om.MVector(0, 0, 1)

    best_matrix = None
    best_bounds = None
    best_score = None

    # 180 degrés suffisent : au-delà, la bbox est équivalente.
    for index in range(max(4, int(steps))):
        angle = math.pi * (float(index) / float(max(4, int(steps))))
        c = math.cos(angle)
        s = math.sin(angle)

        candidate_y = (y_axis * c) + (z_axis * s)
        candidate_z = (z_axis * c) - (y_axis * s)

        candidate_y = candidate_y.normal() if candidate_y.length() > 1e-8 else y_axis
        candidate_z = candidate_z.normal() if candidate_z.length() > 1e-8 else z_axis

        matrix = _build_matrix_from_axes_and_center(x_axis, candidate_y, candidate_z, center)
        bounds, size = _bounds_size_for_axes(points, matrix)
        if not bounds or not size:
            continue

        # Priorité à la section la plus serrée, puis au volume.
        cross_area = abs(size.y * size.z)
        volume = abs(size.x * size.y * size.z)
        max_cross = max(abs(size.y), abs(size.z))
        score = (cross_area, max_cross, volume)

        if best_score is None or score < best_score:
            best_score = score
            best_matrix = matrix
            best_bounds = bounds

    if best_bounds and best_matrix:
        log("Geometry PCA tight roll score: cross_area={} max_cross={} volume={}".format(
            round(best_score[0], 6),
            round(best_score[1], 6),
            round(best_score[2], 6),
        ))
        return best_bounds, best_matrix

    fallback_matrix = _build_matrix_from_axes_and_center(x_axis, y_axis, z_axis, center)
    fallback_bounds, _ = _bounds_size_for_axes(points, fallback_matrix)
    return fallback_bounds, fallback_matrix


def build_pca_oriented_bounds_from_points(points):
    """Déduit une oriented bounding box depuis la géométrie world-space.

    Très utile quand l'objet est freeze transform : l'orientation est reconstruite
    depuis la distribution des points sélectionnés.
    """
    if not points or len(points) < 3:
        return None

    center = om.MVector(0.0, 0.0, 0.0)
    for p in points:
        center += p
    center /= float(len(points))

    cov = [[0.0, 0.0, 0.0] for _ in range(3)]
    for p in points:
        d = p - center
        vals = [d.x, d.y, d.z]
        for r in range(3):
            for c in range(3):
                cov[r][c] += vals[r] * vals[c]

    inv_count = 1.0 / max(1.0, float(len(points)))
    for r in range(3):
        for c in range(3):
            cov[r][c] *= inv_count

    eigen_values, axes = _jacobi_eigen_symmetric_3x3(cov)
    log("Geometry PCA eigen values: {}".format(tuple(round(v, 6) for v in eigen_values)))
    x_axis, y_axis, z_axis = _orthonormalize_axes(axes)

    local_bounds, matrix = _optimize_minor_axes_roll(points, x_axis, y_axis, z_axis, center, steps=90)
    if not local_bounds:
        return None

    return OrientedSelectionBounds(local_bounds.minimum, local_bounds.maximum, matrix)


# -----------------------------------------------------------------------------
# Selection bounds
# -----------------------------------------------------------------------------

def _selection_has_components(selection):
    return any("." in item for item in selection)


def _expand_components_to_points(selection):
    """Retourne une liste de points world-space pour vertices / edges / faces / CV."""
    points = []

    # Convert mesh components to vertices where possible.
    mesh_like = []
    curve_like = []
    for item in selection:
        if ".cv[" in item or ".ep[" in item or ".pt[" in item:
            curve_like.append(item)
        else:
            mesh_like.append(item)

    if mesh_like:
        try:
            verts = cmds.polyListComponentConversion(mesh_like, toVertex=True)
            verts = cmds.filterExpand(verts, selectionMask=31) or []
            for vert in verts:
                try:
                    pos = cmds.pointPosition(vert, world=True)
                    points.append(om.MVector(pos[0], pos[1], pos[2]))
                except Exception:
                    pass
        except Exception:
            pass

    # Curves/surfaces CV can be queried directly.
    for comp in curve_like:
        expanded = cmds.filterExpand(comp, expand=True) or [comp]
        for item in expanded:
            try:
                pos = cmds.pointPosition(item, world=True)
                points.append(om.MVector(pos[0], pos[1], pos[2]))
            except Exception:
                pass

    return points


def _object_bbox_points(selection):
    points = []
    for obj in selection:
        root = obj.split(".")[0]
        if not cmds.objExists(root):
            continue
        try:
            bbox = cmds.exactWorldBoundingBox(root)
            if len(bbox) == 6:
                minimum = om.MVector(bbox[0], bbox[1], bbox[2])
                maximum = om.MVector(bbox[3], bbox[4], bbox[5])
                points.extend([
                    om.MVector(minimum.x, minimum.y, minimum.z),
                    om.MVector(maximum.x, minimum.y, minimum.z),
                    om.MVector(minimum.x, maximum.y, minimum.z),
                    om.MVector(minimum.x, minimum.y, maximum.z),
                    om.MVector(maximum.x, maximum.y, minimum.z),
                    om.MVector(maximum.x, minimum.y, maximum.z),
                    om.MVector(minimum.x, maximum.y, maximum.z),
                    om.MVector(maximum.x, maximum.y, maximum.z),
                ])
        except Exception:
            pass
    return points



def _object_geometry_points(selection):
    """Retourne les vrais vertices world-space des meshes sélectionnés.

    Important pour Geometry PCA Bounds :
    utiliser une bbox world détruit déjà l'orientation. Ici on lit les positions
    réelles des vertices, donc ça fonctionne même sur un mesh freeze transform.
    """
    points = []
    mesh_transforms = []

    for item in selection:
        root = item.split(".")[0]
        if not root or not cmds.objExists(root):
            continue

        node_type = cmds.nodeType(root)
        if node_type == "mesh":
            parents = cmds.listRelatives(root, parent=True, fullPath=True) or []
            if parents:
                mesh_transforms.append(parents[0])
        else:
            shapes = cmds.listRelatives(root, shapes=True, noIntermediate=True, fullPath=True) or []
            if any(cmds.nodeType(shape) == "mesh" for shape in shapes):
                mesh_transforms.append(root)

            children = cmds.listRelatives(root, allDescendents=True, type="transform", fullPath=True) or []
            for child in children:
                child_shapes = cmds.listRelatives(child, shapes=True, noIntermediate=True, fullPath=True) or []
                if any(cmds.nodeType(shape) == "mesh" for shape in child_shapes):
                    mesh_transforms.append(child)

    # Déduplique en gardant l'ordre.
    seen = set()
    unique_transforms = []
    for transform in mesh_transforms:
        if transform not in seen:
            seen.add(transform)
            unique_transforms.append(transform)

    for transform in unique_transforms:
        shapes = cmds.listRelatives(transform, shapes=True, noIntermediate=True, fullPath=True) or []
        for shape in shapes:
            if cmds.nodeType(shape) != "mesh":
                continue
            try:
                sel = om.MSelectionList()
                sel.add(shape)
                dag = sel.getDagPath(0)
                fn_mesh = om.MFnMesh(dag)
                mesh_points = fn_mesh.getPoints(om.MSpace.kWorld)
                for p in mesh_points:
                    points.append(om.MVector(p.x, p.y, p.z))
            except Exception as exc:
                log("Geometry point extraction skipped for '{}': {}".format(shape, exc))

    return points


def build_bounds(points):
    if not points:
        return None
    minimum = om.MVector(points[0])
    maximum = om.MVector(points[0])
    for point in points[1:]:
        minimum = vec_min(minimum, point)
        maximum = vec_max(maximum, point)
    return SelectionBounds(minimum, maximum)


def compute_selection_bounds(use_oriented_bounds=False, bounds_mode=None):
    selection = cmds.ls(selection=True, long=True, flatten=True) or []
    if not selection:
        log("No selection.")
        return None

    if bounds_mode is None:
        bounds_mode = "OBJECT" if use_oriented_bounds else "WORLD"

    if _selection_has_components(selection):
        points = _expand_components_to_points(selection)
        if not points:
            # Fallback Maya bbox on components.
            try:
                bbox = cmds.exactWorldBoundingBox(selection)
                points = [om.MVector(bbox[0], bbox[1], bbox[2]), om.MVector(bbox[3], bbox[4], bbox[5])]
            except Exception:
                points = []
    else:
        if bounds_mode == "GEOMETRY":
            points = _object_geometry_points(selection)
            if points:
                log("Geometry PCA source points: {} real mesh vertices.".format(len(points)))
            else:
                log("Geometry PCA fallback: no mesh vertices found, using object world bbox.")
                points = _object_bbox_points(selection)
        else:
            points = _object_bbox_points(selection)

    bounds = None

    if bounds_mode == "GEOMETRY":
        bounds = build_pca_oriented_bounds_from_points(points)
        if bounds:
            log("Geometry PCA bounds computed local_min={} local_max={} world_center={} local_size={}".format(
                rounded_tuple(bounds.minimum),
                rounded_tuple(bounds.maximum),
                rounded_tuple(bounds.world_center),
                rounded_tuple(bounds.size),
            ))

    elif bounds_mode == "OBJECT" or use_oriented_bounds:
        matrix = get_active_object_transform_matrix()
        bounds = build_oriented_bounds_from_points(points, matrix)
        if bounds:
            log("Object oriented bounds computed local_min={} local_max={} world_center={} local_size={}".format(
                rounded_tuple(bounds.minimum),
                rounded_tuple(bounds.maximum),
                rounded_tuple(bounds.world_center),
                rounded_tuple(bounds.size),
            ))

    if bounds is None:
        bounds = build_bounds(points)
        if bounds:
            log("World bounds computed min={} max={} center={} size={}".format(
                rounded_tuple(bounds.minimum),
                rounded_tuple(bounds.maximum),
                rounded_tuple(bounds.center),
                rounded_tuple(bounds.size),
            ))
        else:
            log("No bounds computed from current selection.")

    return bounds


# -----------------------------------------------------------------------------
# Geometry creation
# -----------------------------------------------------------------------------

def largest_axis_index(vec):
    values = [abs(vec.x), abs(vec.y), abs(vec.z)]
    return values.index(max(values))


def resolve_target_axis(axis_mode, fallback_axis_index):
    axis_map = {"X": 0, "Y": 1, "Z": 2}
    return axis_map.get(axis_mode, fallback_axis_index)


def add_custom_attr(obj, attr, attr_type="bool", default=None, enum_names=None):
    if not cmds.objExists(obj):
        return
    if cmds.attributeQuery(attr, node=obj, exists=True):
        return

    if attr_type == "bool":
        cmds.addAttr(obj, longName=attr, attributeType="bool", defaultValue=bool(default))
        cmds.setAttr(obj + "." + attr, edit=True, keyable=True)
    elif attr_type == "long":
        cmds.addAttr(obj, longName=attr, attributeType="long", defaultValue=int(default or 0), minValue=0)
        cmds.setAttr(obj + "." + attr, edit=True, keyable=True)
    elif attr_type == "enum":
        cmds.addAttr(obj, longName=attr, attributeType="enum", enumName=enum_names or "cube:cylinder:sphere:disc:quad_sphere")
        cmds.setAttr(obj + "." + attr, int(default or 0))
        cmds.setAttr(obj + "." + attr, edit=True, keyable=True)
    elif attr_type == "string":
        cmds.addAttr(obj, longName=attr, dataType="string")
        if default is not None:
            cmds.setAttr(obj + "." + attr, default, type="string")


def mark_object_as_fill_selection_primitive(obj, primitive_kind, vertices=32, segments=32, rings=16, resolution=3, preserve_proportions=True, orientation_axis="AUTO", use_oriented_bounds=False, bounds_mode="WORLD"):
    kind_to_index = {"cube": 0, "cylinder": 1, "sphere": 2, "disc": 3, "quad_sphere": 4}
    axis_to_index = {"AUTO": 0, "X": 1, "Y": 2, "Z": 3}
    bounds_mode_to_index = {"WORLD": 0, "OBJECT": 1, "GEOMETRY": 2}
    add_custom_attr(obj, "fillSelectionManaged", "bool", True)
    add_custom_attr(obj, "fillSelectionPrimitiveKind", "enum", kind_to_index.get(primitive_kind, 0), "cube:cylinder:sphere:disc:quad_sphere")
    add_custom_attr(obj, "fillSelectionVertices", "long", vertices)
    add_custom_attr(obj, "fillSelectionSegments", "long", segments)
    add_custom_attr(obj, "fillSelectionRings", "long", rings)
    add_custom_attr(obj, "fillSelectionResolution", "long", resolution)
    add_custom_attr(obj, "fillSelectionPreserveProportions", "bool", preserve_proportions)
    add_custom_attr(obj, "fillSelectionOrientationAxis", "enum", axis_to_index.get(orientation_axis, 0), "AUTO:X:Y:Z")
    add_custom_attr(obj, "fillSelectionUseOrientedBounds", "bool", use_oriented_bounds)
    add_custom_attr(obj, "fillSelectionBoundsMode", "enum", bounds_mode_to_index.get(bounds_mode, 0), "WORLD:OBJECT:GEOMETRY")

    cmds.setAttr(obj + ".fillSelectionManaged", True)
    cmds.setAttr(obj + ".fillSelectionPrimitiveKind", kind_to_index.get(primitive_kind, 0))
    cmds.setAttr(obj + ".fillSelectionVertices", max(3, int(vertices)))
    cmds.setAttr(obj + ".fillSelectionSegments", max(3, int(segments)))
    cmds.setAttr(obj + ".fillSelectionRings", max(2, int(rings)))
    cmds.setAttr(obj + ".fillSelectionResolution", max(1, int(resolution)))
    cmds.setAttr(obj + ".fillSelectionPreserveProportions", bool(preserve_proportions))
    cmds.setAttr(obj + ".fillSelectionOrientationAxis", axis_to_index.get(orientation_axis, 0))
    cmds.setAttr(obj + ".fillSelectionUseOrientedBounds", bool(use_oriented_bounds or bounds_mode in ("OBJECT", "GEOMETRY")))
    cmds.setAttr(obj + ".fillSelectionBoundsMode", bounds_mode_to_index.get(bounds_mode, 0))


def get_managed_kind(obj):
    if not obj or not cmds.objExists(obj):
        return None
    if not cmds.attributeQuery("fillSelectionManaged", node=obj, exists=True):
        return None
    if not cmds.getAttr(obj + ".fillSelectionManaged"):
        return None
    index_to_kind = {0: "cube", 1: "cylinder", 2: "sphere", 3: "disc", 4: "quad_sphere"}
    try:
        return index_to_kind.get(cmds.getAttr(obj + ".fillSelectionPrimitiveKind"), None)
    except Exception:
        return None


def create_disc_mesh(vertices=32):
    vertices = max(3, int(vertices))
    mesh_name = build_unique_name("FillSelectionDiscShape")
    obj_name = build_unique_name("Fill_Selection_Disc")

    verts = [(0.0, 0.0, 0.0)]
    for i in range(vertices):
        angle = (math.pi * 2.0) * (float(i) / float(vertices))
        verts.append((math.cos(angle) * 0.5, 0.0, math.sin(angle) * 0.5))

    faces = [tuple(range(vertices, 0, -1))]
    mesh = cmds.polyCreateFacet(point=[verts[i] for i in faces[0]], name=obj_name)[0]
    mesh = cmds.rename(mesh, obj_name)
    try:
        shape = cmds.listRelatives(mesh, shapes=True, fullPath=True) or []
        if shape:
            cmds.rename(shape[0], mesh_name)
    except Exception:
        pass
    cmds.select(mesh, replace=True)
    return mesh


def create_quad_sphere_mesh(resolution=3):
    """Génère une sphere quad à partir des 6 faces d'un cube subdivisé/projeté."""
    resolution = max(1, int(resolution))
    log_quad_sphere("Generating mesh with resolution={}.".format(resolution))

    verts = []
    faces = []
    vert_map = {}

    def rounded_key(v):
        return (round(v.x, 8), round(v.y, 8), round(v.z, 8))

    def add_vertex(v):
        if v.length() > 0.0:
            n = v.normal()
        else:
            n = om.MVector(v)
        key = rounded_key(n)
        if key in vert_map:
            return vert_map[key]
        index = len(verts)
        verts.append((n.x * 0.5, n.y * 0.5, n.z * 0.5))
        vert_map[key] = index
        return index

    # Chaque entrée : normal axis fixe + deux axes de grille.
    face_defs = [
        (om.MVector(1, 0, 0), om.MVector(0, 1, 0), om.MVector(0, 0, 1)),
        (om.MVector(-1, 0, 0), om.MVector(0, 1, 0), om.MVector(0, 0, -1)),
        (om.MVector(0, 1, 0), om.MVector(0, 0, 1), om.MVector(1, 0, 0)),
        (om.MVector(0, -1, 0), om.MVector(0, 0, 1), om.MVector(-1, 0, 0)),
        (om.MVector(0, 0, 1), om.MVector(1, 0, 0), om.MVector(0, 1, 0)),
        (om.MVector(0, 0, -1), om.MVector(-1, 0, 0), om.MVector(0, 1, 0)),
    ]

    for fixed, u_axis, v_axis in face_defs:
        grid = []
        for y in range(resolution + 1):
            row = []
            v = -1.0 + 2.0 * (float(y) / float(resolution))
            for x in range(resolution + 1):
                u = -1.0 + 2.0 * (float(x) / float(resolution))
                cube_point = fixed + (u_axis * u) + (v_axis * v)
                row.append(add_vertex(cube_point))
            grid.append(row)

        for y in range(resolution):
            for x in range(resolution):
                faces.append((grid[y][x], grid[y][x + 1], grid[y + 1][x + 1], grid[y + 1][x]))

    obj_name = build_unique_name("Fill Selection Quad Sphere")
    mesh_name = build_unique_name("FillSelectionQuadSphereShape")
    obj = cmds.createNode("transform", name=obj_name)
    mesh_node = cmds.createNode("mesh", name=mesh_name, parent=obj)

    points = om.MPointArray([om.MPoint(x, y, z) for x, y, z in verts])
    counts = om.MIntArray([len(face) for face in faces])
    connects = om.MIntArray([index for face in faces for index in face])

    sel = om.MSelectionList()
    sel.add(mesh_node)
    dag = sel.getDagPath(0)
    fn_mesh = om.MFnMesh(dag)
    fn_mesh.create(points, counts, connects, parent=dag.transform())
    cmds.delete(mesh_node)

    # La création API génère un shape automatiquement sous le transform.
    shapes = cmds.listRelatives(obj, shapes=True, fullPath=True) or []
    if shapes:
        try:
            cmds.rename(shapes[0], mesh_name)
        except Exception:
            pass

    cmds.select(obj, replace=True)
    log_quad_sphere("Created verts={} faces={}.".format(len(verts), len(faces)))
    return obj


def create_primitive_object(primitive_kind, vertices=32, segments=32, rings=16, resolution=3):
    default_names = {
        "cube": "Fill Selection Cube",
        "cylinder": "Fill Selection Cylinder",
        "sphere": "Fill Selection UV Sphere",
        "disc": "Fill Selection Disc",
        "quad_sphere": "Fill Selection Quad Sphere",
    }

    if primitive_kind == "cube":
        obj = cmds.polyCube(name=build_unique_name(default_names[primitive_kind]), width=1.0, height=1.0, depth=1.0)[0]
    elif primitive_kind == "cylinder":
        obj = cmds.polyCylinder(
            name=build_unique_name(default_names[primitive_kind]),
            radius=0.5,
            height=1.0,
            subdivisionsAxis=max(3, int(vertices)),
            subdivisionsHeight=1,
            subdivisionsCaps=1,
            axis=(0, 1, 0),
        )[0]
    elif primitive_kind == "sphere":
        obj = cmds.polySphere(
            name=build_unique_name(default_names[primitive_kind]),
            radius=0.5,
            subdivisionsAxis=max(3, int(segments)),
            subdivisionsHeight=max(2, int(rings)),
            axis=(0, 1, 0),
        )[0]
    elif primitive_kind == "disc":
        obj = create_disc_mesh(vertices=max(3, int(vertices)))
    elif primitive_kind == "quad_sphere":
        obj = create_quad_sphere_mesh(max(1, int(resolution)))
    else:
        raise ValueError("Primitive inconnue : {}".format(primitive_kind))

    cmds.select(obj, replace=True)
    return obj


def set_rotation_for_target_axis(obj, target_axis_index):
    # Les cylindres/disques Maya sont construits avec leur axe principal sur Y.
    if target_axis_index == 0:      # X
        cmds.setAttr(obj + ".rotate", 0.0, 0.0, -90.0, type="double3")
    elif target_axis_index == 1:    # Y
        cmds.setAttr(obj + ".rotate", 0.0, 0.0, 0.0, type="double3")
    elif target_axis_index == 2:    # Z
        cmds.setAttr(obj + ".rotate", 90.0, 0.0, 0.0, type="double3")


def apply_fill_to_object(obj, primitive_kind, bounds, preserve_proportions=True, orientation_axis="AUTO"):
    is_oriented = bool(getattr(bounds, "is_oriented", False))
    center = bounds.world_center if is_oriented else bounds.center
    raw = bounds.size
    size = [max(abs(raw.x), EPSILON), max(abs(raw.y), EPSILON), max(abs(raw.z), EPSILON)]

    target_longest_axis = largest_axis_index(raw)
    target_axis_index = resolve_target_axis(orientation_axis, target_longest_axis)

    cmds.xform(obj, worldSpace=True, translation=tuple3(center))
    cmds.setAttr(obj + ".rotate", 0.0, 0.0, 0.0, type="double3")
    cmds.setAttr(obj + ".scale", 1.0, 1.0, 1.0, type="double3")

    if is_oriented:
        try:
            cmds.xform(obj, worldSpace=True, matrix=list(bounds.matrix))
        except Exception as exc:
            log("Could not apply oriented matrix: {}".format(exc))
        cmds.xform(obj, worldSpace=True, translation=tuple3(center))

    if primitive_kind == "cube":
        local_scale = size

    elif primitive_kind in {"sphere", "quad_sphere"}:
        if preserve_proportions:
            diameter = max(size)
            local_scale = [diameter, diameter, diameter]
        else:
            local_scale = size

    elif primitive_kind in {"cylinder", "disc"}:
        if is_oriented:
            if target_axis_index == 0:
                cmds.rotate(0.0, 0.0, -90.0, obj, objectSpace=True, relative=True)
            elif target_axis_index == 2:
                cmds.rotate(90.0, 0.0, 0.0, obj, objectSpace=True, relative=True)
        else:
            set_rotation_for_target_axis(obj, target_axis_index)

        if target_axis_index == 0:      # Longueur sur X, section sur Y/Z
            height = size[0]
            cross_a = size[1]
            cross_b = size[2]
            local_scale = [cross_a, height, cross_b]
        elif target_axis_index == 1:    # Longueur sur Y, section sur X/Z
            height = size[1]
            cross_a = size[0]
            cross_b = size[2]
            local_scale = [cross_a, height, cross_b]
        else:                           # Longueur sur Z, section sur X/Y
            height = size[2]
            cross_a = size[0]
            cross_b = size[1]
            local_scale = [cross_a, height, cross_b]

        if preserve_proportions:
            cross = max(cross_a, cross_b)
            local_scale[0] = cross
            local_scale[2] = cross

        if primitive_kind == "disc":
            # Le disque est plat sur son axe local Y : on garde une épaisseur quasi nulle.
            local_scale[1] = EPSILON

    else:
        local_scale = size

    cmds.setAttr(obj + ".scale", local_scale[0], local_scale[1], local_scale[2], type="double3")
    log("Transform applied to '{}': loc={} rot={} scale={}".format(
        obj,
        rounded_tuple(center),
        tuple(round(v, 5) for v in cmds.getAttr(obj + ".rotate")[0]),
        tuple(round(v, 5) for v in cmds.getAttr(obj + ".scale")[0]),
    ))


def create_fill_selection_primitive(primitive_kind, preserve_proportions=True, orientation_axis="AUTO", vertices=32, segments=32, rings=16, resolution=3, use_oriented_bounds=False, bounds_mode="WORLD"):
    original_selection = cmds.ls(selection=True, long=True, flatten=True) or []
    bounds = compute_selection_bounds(use_oriented_bounds=use_oriented_bounds, bounds_mode=bounds_mode)
    if not bounds:
        cmds.warning("Aucune sélection valide pour calculer la bounding box.")
        return None

    obj = create_primitive_object(
        primitive_kind,
        vertices=vertices,
        segments=segments,
        rings=rings,
        resolution=resolution,
    )
    apply_fill_to_object(obj, primitive_kind, bounds, preserve_proportions, orientation_axis)
    mark_object_as_fill_selection_primitive(obj, primitive_kind, vertices, segments, rings, resolution, preserve_proportions, orientation_axis, use_oriented_bounds, bounds_mode)
    set_managed_bounds(obj, bounds)
    cmds.select(obj, replace=True)
    log("Created {} as '{}'.".format(primitive_kind, obj))
    return obj


# -----------------------------------------------------------------------------
# Rebuild managed object mesh
# -----------------------------------------------------------------------------

def _get_int_attr(obj, attr, fallback):
    if cmds.attributeQuery(attr, node=obj, exists=True):
        try:
            return int(cmds.getAttr(obj + "." + attr))
        except Exception:
            pass
    return fallback


def _get_bool_attr(obj, attr, fallback):
    if cmds.attributeQuery(attr, node=obj, exists=True):
        try:
            return bool(cmds.getAttr(obj + "." + attr))
        except Exception:
            pass
    return fallback


def _get_string_attr(obj, attr, fallback):
    if cmds.attributeQuery(attr, node=obj, exists=True):
        try:
            value = cmds.getAttr(obj + "." + attr)
            return value if value else fallback
        except Exception:
            pass
    return fallback


def add_vector_attr(obj, attr_name, value):
    if not cmds.attributeQuery(attr_name, node=obj, exists=True):
        cmds.addAttr(obj, longName=attr_name, attributeType="double3")
        cmds.addAttr(obj, longName=attr_name + "X", attributeType="double", parent=attr_name)
        cmds.addAttr(obj, longName=attr_name + "Y", attributeType="double", parent=attr_name)
        cmds.addAttr(obj, longName=attr_name + "Z", attributeType="double", parent=attr_name)
    cmds.setAttr(obj + "." + attr_name, float(value[0]), float(value[1]), float(value[2]), type="double3")


def get_vector_attr(obj, attr_name, fallback=None):
    if cmds.attributeQuery(attr_name, node=obj, exists=True):
        try:
            return cmds.getAttr(obj + "." + attr_name)[0]
        except Exception:
            pass
    return fallback


def set_managed_bounds(obj, bounds):
    if not obj or not bounds:
        return
    add_vector_attr(obj, "fillSelectionBoundsMin", tuple3(bounds.minimum))
    add_vector_attr(obj, "fillSelectionBoundsMax", tuple3(bounds.maximum))

    if getattr(bounds, "is_oriented", False):
        values = ",".join(str(float(v)) for v in list(bounds.matrix))
        if not cmds.attributeQuery("fillSelectionBoundsMatrix", node=obj, exists=True):
            cmds.addAttr(obj, longName="fillSelectionBoundsMatrix", dataType="string")
        cmds.setAttr(obj + ".fillSelectionBoundsMatrix", values, type="string")


def get_managed_bounds(obj):
    minimum = get_vector_attr(obj, "fillSelectionBoundsMin")
    maximum = get_vector_attr(obj, "fillSelectionBoundsMax")
    if minimum is None or maximum is None:
        return None

    if cmds.attributeQuery("fillSelectionUseOrientedBounds", node=obj, exists=True):
        try:
            if cmds.getAttr(obj + ".fillSelectionUseOrientedBounds"):
                matrix_string = cmds.getAttr(obj + ".fillSelectionBoundsMatrix") if cmds.attributeQuery("fillSelectionBoundsMatrix", node=obj, exists=True) else ""
                values = [float(v) for v in matrix_string.split(",") if v.strip()]
                if len(values) == 16:
                    return OrientedSelectionBounds(om.MVector(*minimum), om.MVector(*maximum), om.MMatrix(values))
        except Exception:
            pass

    return SelectionBounds(om.MVector(*minimum), om.MVector(*maximum))


def replace_mesh_data(target_obj, source_obj):
    """Remplace la géométrie du target par celle d'un objet source temporaire.

    Important :
    target_obj peut être un long path Maya, ex: "|Fill_Selection_Cylinder_001".
    Les noms passés à duplicate/rename ne doivent jamais contenir "|".
    """
    if not target_obj or not source_obj:
        return False

    target_shapes = cmds.listRelatives(target_obj, shapes=True, noIntermediate=True, fullPath=True) or []
    source_shapes = cmds.listRelatives(source_obj, shapes=True, noIntermediate=True, fullPath=True) or []
    if not target_shapes or not source_shapes:
        return False

    target_short = maya_safe_name(target_obj, "FillSelectionTarget")
    temp_transform_name = build_unique_safe_name(target_short + "_ShapeTemp")
    final_shape_name = build_unique_safe_name(target_short + "Shape")

    old_shapes = list(target_shapes)
    source_shape = source_shapes[0]

    duplicated = cmds.duplicate(source_shape, name=temp_transform_name)[0]
    duplicated_shapes = cmds.listRelatives(duplicated, shapes=True, noIntermediate=True, fullPath=True) or []
    if not duplicated_shapes:
        cmds.delete(duplicated)
        return False

    new_shape = cmds.parent(duplicated_shapes[0], target_obj, shape=True, relative=True)[0]

    for shape in old_shapes:
        try:
            cmds.delete(shape)
        except Exception:
            pass

    try:
        cmds.delete(duplicated)
    except Exception:
        pass

    try:
        cmds.rename(new_shape, final_shape_name)
    except Exception as exc:
        log("Shape rename skipped: {}".format(exc))

    return True


def rebuild_selected_primitive():
    return update_selected_primitive_live(silent=False)





def update_selected_primitive_live(preserve_proportions=None, orientation_axis=None, vertices=None, segments=None, rings=None, resolution=None, use_oriented_bounds=None, bounds_mode=None, silent=True):
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        if not silent:
            cmds.warning("Sélectionne une primitive Fill Selection à mettre à jour.")
        return None

    obj = selection[0]
    kind = get_managed_kind(obj)
    if not kind:
        if not silent:
            cmds.warning("L'objet sélectionné n'est pas une primitive Fill Selection gérée.")
        return None

    axis_index_to_name = {0: "AUTO", 1: "X", 2: "Y", 3: "Z"}

    current_vertices = max(3, _get_int_attr(obj, "fillSelectionVertices", 32))
    current_segments = max(3, _get_int_attr(obj, "fillSelectionSegments", 32))
    current_rings = max(2, _get_int_attr(obj, "fillSelectionRings", 16))
    current_resolution = max(1, _get_int_attr(obj, "fillSelectionResolution", 3))
    current_preserve = _get_bool_attr(obj, "fillSelectionPreserveProportions", True)
    current_oriented = _get_bool_attr(obj, "fillSelectionUseOrientedBounds", False)
    bounds_index_to_name = {0: "WORLD", 1: "OBJECT", 2: "GEOMETRY"}
    current_bounds_mode = "OBJECT" if current_oriented else "WORLD"
    if cmds.attributeQuery("fillSelectionBoundsMode", node=obj, exists=True):
        try:
            current_bounds_mode = bounds_index_to_name.get(cmds.getAttr(obj + ".fillSelectionBoundsMode"), current_bounds_mode)
        except Exception:
            pass

    current_axis = "AUTO"
    if cmds.attributeQuery("fillSelectionOrientationAxis", node=obj, exists=True):
        try:
            current_axis = axis_index_to_name.get(cmds.getAttr(obj + ".fillSelectionOrientationAxis"), "AUTO")
        except Exception:
            current_axis = "AUTO"

    vertices = max(3, int(vertices if vertices is not None else current_vertices))
    segments = max(3, int(segments if segments is not None else current_segments))
    rings = max(2, int(rings if rings is not None else current_rings))
    resolution = max(1, int(resolution if resolution is not None else current_resolution))
    preserve_proportions = current_preserve if preserve_proportions is None else bool(preserve_proportions)
    orientation_axis = orientation_axis or current_axis
    bounds_mode = bounds_mode or current_bounds_mode
    use_oriented_bounds = current_oriented if use_oriented_bounds is None else bool(use_oriented_bounds or bounds_mode in ("OBJECT", "GEOMETRY"))

    bounds = get_managed_bounds(obj)
    if not bounds:
        # Fallback utile pour les objets créés avec une ancienne version du script.
        raw_scale = cmds.getAttr(obj + ".scale")[0]
        raw_translate = cmds.getAttr(obj + ".translate")[0]
        half = om.MVector(abs(raw_scale[0]) * 0.5, abs(raw_scale[1]) * 0.5, abs(raw_scale[2]) * 0.5)
        center = om.MVector(*raw_translate)
        bounds = SelectionBounds(center - half, center + half)
        set_managed_bounds(obj, bounds)

    # Reconstruit uniquement la géométrie nécessaire.
    if kind in {"cylinder", "sphere", "disc", "quad_sphere"}:
        old_selection = cmds.ls(selection=True, long=True) or []
        temp = create_primitive_object(kind, vertices, segments, rings, resolution)
        replace_mesh_data(obj, temp)
        try:
            cmds.delete(temp)
        except Exception:
            pass
        cmds.select(old_selection, replace=True)

    apply_fill_to_object(obj, kind, bounds, preserve_proportions, orientation_axis)
    mark_object_as_fill_selection_primitive(
        obj,
        kind,
        vertices,
        segments,
        rings,
        resolution,
        preserve_proportions,
        orientation_axis,
        use_oriented_bounds,
        bounds_mode,
    )
    set_managed_bounds(obj, bounds)
    cmds.select(obj, replace=True)
    log("Live updated {} '{}'.".format(kind, maya_short_name(obj)))
    return obj

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------

class FillSelectionWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        maya_parent = parent or maya_main_window()
        super(FillSelectionWindow, self).__init__(maya_parent)

        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("Fill Selection Primitives - Maya")
        self.setMinimumWidth(360)

        # Important pour Maya :
        # - Qt.Tool garde la fenêtre comme outil flottant au-dessus de Maya.
        # - WindowStaysOnTopHint évite qu'elle passe derrière le viewport.
        # - On garde le parent Maya pour éviter une fenêtre indépendante instable.
        flags = (
            QtCore.Qt.Tool
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.CustomizeWindowHint
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setWindowFlags(flags)

        self._is_creating_primitive = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        main = QtWidgets.QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        info = QtWidgets.QLabel(
            "Crée une primitive qui remplit la bounding box de la sélection active.\n"
            "Compatible objets, faces, edges, vertices et CV."
        )
        info.setWordWrap(True)
        main.addWidget(info)

        options_box = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QFormLayout(options_box)
        options_layout.setContentsMargins(10, 10, 10, 10)

        self.proportional_cb = QtWidgets.QCheckBox("Proportional Transform")
        self.proportional_cb.setChecked(True)
        options_layout.addRow(self.proportional_cb)

        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems(["AUTO", "X", "Y", "Z"])
        options_layout.addRow("Orientation Axis", self.axis_combo)

        self.bounds_mode_combo = QtWidgets.QComboBox()
        self.bounds_mode_combo.addItem("World Bounding Box", "WORLD")
        self.bounds_mode_combo.addItem("Object Oriented Bounds", "OBJECT")
        self.bounds_mode_combo.addItem("Geometry PCA Bounds", "GEOMETRY")
        self.bounds_mode_combo.setToolTip(
            "World = bounding box classique. Object = orientation du transform actif. "
            "Geometry PCA = orientation déduite des vertices, utile si le mesh est freeze transform."
        )
        options_layout.addRow("Bounds Mode", self.bounds_mode_combo)

        self.vertices_spin = QtWidgets.QSpinBox()
        self.vertices_spin.setRange(3, 512)
        self.vertices_spin.setValue(32)
        options_layout.addRow("Cylinder / Disc Vertices", self.vertices_spin)

        self.segments_spin = QtWidgets.QSpinBox()
        self.segments_spin.setRange(3, 512)
        self.segments_spin.setValue(32)
        options_layout.addRow("UV Sphere Segments", self.segments_spin)

        self.rings_spin = QtWidgets.QSpinBox()
        self.rings_spin.setRange(2, 512)
        self.rings_spin.setValue(16)
        options_layout.addRow("UV Sphere Rings", self.rings_spin)

        self.resolution_spin = QtWidgets.QSpinBox()
        self.resolution_spin.setRange(1, 64)
        self.resolution_spin.setValue(3)
        options_layout.addRow("Quad Sphere Resolution", self.resolution_spin)

        main.addWidget(options_box)

        primitive_box = QtWidgets.QGroupBox("Créer une primitive")
        grid = QtWidgets.QGridLayout(primitive_box)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(6)

        self.btn_cube = QtWidgets.QPushButton("Fill Selection Cube")
        self.btn_cylinder = QtWidgets.QPushButton("Fill Selection Cylinder")
        self.btn_sphere = QtWidgets.QPushButton("Fill Selection UV Sphere")
        self.btn_disc = QtWidgets.QPushButton("Fill Selection Disc")
        self.btn_quad_sphere = QtWidgets.QPushButton("Fill Selection Quad Sphere")

        grid.addWidget(self.btn_cube, 0, 0)
        grid.addWidget(self.btn_cylinder, 0, 1)
        grid.addWidget(self.btn_sphere, 1, 0)
        grid.addWidget(self.btn_disc, 1, 1)
        grid.addWidget(self.btn_quad_sphere, 2, 0, 1, 2)
        main.addWidget(primitive_box)

        rebuild_box = QtWidgets.QGroupBox("Objet Fill Selection sélectionné")
        rebuild_layout = QtWidgets.QVBoxLayout(rebuild_box)
        rebuild_layout.setContentsMargins(10, 10, 10, 10)
        self.btn_rebuild = QtWidgets.QPushButton("Force Rebuild Selected Primitive")
        rebuild_layout.addWidget(self.btn_rebuild)
        hint = QtWidgets.QLabel(
            "Sélectionne une primitive Fill Selection, puis modifie les paramètres ci-dessus : "
            "elle se reconstruit automatiquement en live."
        )
        hint.setWordWrap(True)
        rebuild_layout.addWidget(hint)
        main.addWidget(rebuild_box)

        main.addStretch(1)

    def _connect_signals(self):
        self.btn_cube.clicked.connect(lambda: self._create("cube"))
        self.btn_cylinder.clicked.connect(lambda: self._create("cylinder"))
        self.btn_sphere.clicked.connect(lambda: self._create("sphere"))
        self.btn_disc.clicked.connect(lambda: self._create("disc"))
        self.btn_quad_sphere.clicked.connect(lambda: self._create("quad_sphere"))
        self.btn_rebuild.clicked.connect(lambda: update_selected_primitive_live(silent=False))

        self.proportional_cb.toggled.connect(self._live_update_selected)
        self.axis_combo.currentTextChanged.connect(self._live_update_selected)
        self.bounds_mode_combo.currentIndexChanged.connect(self._live_update_selected)
        self.vertices_spin.valueChanged.connect(self._live_update_selected)
        self.segments_spin.valueChanged.connect(self._live_update_selected)
        self.rings_spin.valueChanged.connect(self._live_update_selected)
        self.resolution_spin.valueChanged.connect(self._live_update_selected)

    def _create(self, primitive_kind):
        self._is_creating_primitive = True
        try:
            create_fill_selection_primitive(
                primitive_kind,
                preserve_proportions=self.proportional_cb.isChecked(),
                orientation_axis=self.axis_combo.currentText(),
                vertices=self.vertices_spin.value(),
                segments=self.segments_spin.value(),
                rings=self.rings_spin.value(),
                resolution=self.resolution_spin.value(),
                use_oriented_bounds=(self.bounds_mode_combo.currentData() != "WORLD"),
                bounds_mode=self.bounds_mode_combo.currentData(),
            )
        finally:
            self._is_creating_primitive = False

    def _live_update_selected(self, *args):
        if getattr(self, '_is_creating_primitive', False):
            return
        update_selected_primitive_live(
            preserve_proportions=self.proportional_cb.isChecked(),
            orientation_axis=self.axis_combo.currentText(),
            vertices=self.vertices_spin.value(),
            segments=self.segments_spin.value(),
            rings=self.rings_spin.value(),
            resolution=self.resolution_spin.value(),
            use_oriented_bounds=(self.bounds_mode_combo.currentData() != "WORLD"),
                bounds_mode=self.bounds_mode_combo.currentData(),
            silent=True,
        )


def show():
    safe_delete_ui(WINDOW_OBJECT_NAME)
    win = FillSelectionWindow()
    win.show()
    win.raise_()
    win.activateWindow()
    return win


# Convenience functions for shelf buttons / scripts

def fill_selection_cube():
    return create_fill_selection_primitive("cube")


def fill_selection_cylinder():
    return create_fill_selection_primitive("cylinder")


def fill_selection_uv_sphere():
    return create_fill_selection_primitive("sphere")


def fill_selection_disc():
    return create_fill_selection_primitive("disc")


def fill_selection_quad_sphere():
    return create_fill_selection_primitive("quad_sphere")


if __name__ == "__main__":
    show()

