# -*- coding: utf-8 -*-
"""
Smart UV Shell Grow / Cut Finder Ultimate for Maya
--------------------------------------------------

Workflow:
1. Enable Hover Seed Tracking.
2. Hover a mesh face in the viewport, or select a face directly.
3. Press U to detect the shell from that face.
4. Click "Cut Boundary Around Preview" to create UV cuts around the detected shell.

Main idea:
- Semi-automatic assistant:
  the user chooses a seed face, then the tool grows a coherent face region.
- Growth stops on strong angle changes / hard-surface-like transitions / max face count.
- The detected face region can then be used to create UV cuts around its boundary.

Compatibility:
- Maya 2022+
- Uses maya.cmds + maya.api.OpenMaya 2.0
- Avoids MFnMesh.getPolygonEdges(), which is missing in some Maya builds.
"""

from __future__ import print_function

import math
import json
import traceback
import time
from collections import deque

import maya.cmds as cmds
import maya.api.OpenMaya as om

try:
    import maya.api.OpenMayaUI as omui
except Exception:
    omui = None

try:
    import maya.OpenMayaUI as omui_legacy
except Exception:
    omui_legacy = None

if omui is None or not hasattr(omui, "MQtUtil"):
    omui = omui_legacy

try:
    import maya.OpenMaya as om1
except Exception:
    om1 = None

try:
    from PySide2 import QtCore, QtGui, QtWidgets
    import shiboken2
except Exception:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        import shiboken6 as shiboken2
    except Exception:
        QtCore = None
        QtGui = None
        QtWidgets = None
        shiboken2 = None


# ============================================================
# CONSTANTS
# ============================================================

WINDOW_NAME = "SmartUVShellGrowCutFinder_Ultimate_UI"
STATE_NODE = "SMART_UV_SHELL_GROW_STATE"
STATE_ATTR = "jsonData"

PREVIEW_SET = "SMART_UV_SHELL_PREVIEW_SET"
HOVER_PREVIEW_SET = "SMART_UV_SHELL_HOVER_PREVIEW_SET"
HOVER_STATUS_CONTROL = "smartUV_hoverStatus_TXT"

DEFAULTS = {
    "angle_threshold": 35.0,
    "hard_edge_blocks": True,
    "max_faces": 5000,
    "mode": "Balanced",
    "select_preview": True,
}

HOVER_STATE = {
    "enabled": False,
    "job": None,
    "event_filter": None,
    "panel_widgets": [],
    "widgets": [],
    "last_hit": None,
    "last_panel": None,
    "last_tick_time": 0.0,
    "graph_cache": {},
    "ray_mesh_cache": {},
}


# ============================================================
# BASIC UTILITIES
# ============================================================

def _safe_delete(node):
    try:
        if cmds.objExists(node):
            cmds.delete(node)
    except Exception:
        pass


def _warn(msg):
    cmds.warning("[Smart UV Shell] " + msg)


def _log(msg):
    print("[Smart UV Shell] " + msg)


def _set_hover_status(msg):
    if cmds.text(HOVER_STATUS_CONTROL, exists=True):
        cmds.text(HOVER_STATUS_CONTROL, edit=True, label=msg)


def _face_component(transform, face_id):
    return "{}.f[{}]".format(transform, int(face_id))


def _edge_component(transform, edge_id):
    return "{}.e[{}]".format(transform, int(edge_id))


def _angle_between_vectors_deg(a, b):
    try:
        la = a.length()
        lb = b.length()

        if la < 1e-8 or lb < 1e-8:
            return 0.0

        dot = max(-1.0, min(1.0, (a * b) / (la * lb)))
        return math.degrees(math.acos(dot))

    except Exception:
        return 0.0


def _get_selected_face():
    """
    Returns:
        (transform, shape, face_id) or (None, None, None)
    """
    sel = cmds.ls(selection=True, flatten=True, long=True) or []

    faces = []
    for item in sel:
        if ".f[" in item:
            faces.append(item)

    if not faces and sel:
        converted = cmds.polyListComponentConversion(sel, toFace=True)
        converted = cmds.ls(converted, flatten=True, long=True) or []
        faces = [f for f in converted if ".f[" in f]

    if not faces:
        return None, None, None

    face = faces[0]
    transform = face.split(".f[")[0]

    if not cmds.objExists(transform):
        return None, None, None

    # If selected node is a shape, get parent transform.
    if cmds.nodeType(transform) == "mesh":
        parents = cmds.listRelatives(transform, parent=True, fullPath=True) or []
        if parents:
            transform = parents[0]

    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True, type="mesh") or []
    if not shapes:
        return None, None, None

    shape = shapes[0]

    try:
        start = face.index(".f[") + 3
        end = face.index("]", start)
        face_id = int(face[start:end])
    except Exception:
        return None, None, None

    return transform, shape, face_id


def _get_single_selected_face():
    """
    Strict version for the U shortcut.
    Returns a selected seed only when exactly one face is selected, so an
    existing multi-face preview selection does not override the hover seed.
    """
    sel = cmds.ls(selection=True, flatten=True, long=True) or []
    faces = [item for item in sel if ".f[" in item]

    if not faces and sel:
        converted = cmds.polyListComponentConversion(sel, toFace=True)
        converted = cmds.ls(converted, flatten=True, long=True) or []
        faces = [f for f in converted if ".f[" in f]

    if len(faces) != 1:
        return None, None, None

    current_selection = cmds.ls(selection=True, long=True) or []

    try:
        cmds.select(faces[0], replace=True)
        return _get_selected_face()
    finally:
        try:
            if current_selection:
                cmds.select(current_selection, replace=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass


def _get_dag_path(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return sel.getDagPath(0)


def _get_mesh_fn(shape):
    dag = _get_dag_path(shape)
    return om.MFnMesh(dag)


def _get_transform_from_shape(shape):
    parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
    if parents:
        return parents[0]
    return shape


def _is_mesh_shape_pickable(shape):
    try:
        if not cmds.objExists(shape):
            return False
        if cmds.getAttr(shape + ".intermediateObject"):
            return False
        transform = _get_transform_from_shape(shape)
        if not cmds.getAttr(transform + ".visibility"):
            return False
        if not cmds.getAttr(shape + ".visibility"):
            return False
    except Exception:
        return False

    return True


def _api_point(value):
    return om.MFloatPoint(float(value.x), float(value.y), float(value.z))


def _api_vector(value):
    vec = om.MFloatVector(float(value.x), float(value.y), float(value.z))
    try:
        vec.normalize()
    except Exception:
        pass
    return vec


def _set_active_components_api(shape, component_type, indices):
    """
    Selects mesh components through OpenMaya 2.0 instead of building thousands
    of component strings for cmds.select().
    """
    if not indices:
        cmds.select(clear=True)
        return True

    try:
        dag = _get_dag_path(shape)
        component = om.MFnSingleIndexedComponent().create(component_type)
        component_fn = om.MFnSingleIndexedComponent(component)
        component_fn.addElements(om.MIntArray([int(i) for i in indices]))

        selection = om.MSelectionList()
        selection.add((dag, component))
        om.MGlobal.setActiveSelectionList(selection, om.MGlobal.kReplaceList)
        return True

    except Exception:
        return False


def _select_faces_api(shape, face_ids):
    return _set_active_components_api(shape, om.MFn.kMeshPolygonComponent, face_ids)


def _select_edges_api(shape, edge_ids):
    return _set_active_components_api(shape, om.MFn.kMeshEdgeComponent, edge_ids)


# ============================================================
# STATE STORAGE
# ============================================================

def _ensure_state_node():
    if not cmds.objExists(STATE_NODE):
        node = cmds.createNode("network", name=STATE_NODE)
        cmds.addAttr(node, longName=STATE_ATTR, dataType="string")
    elif not cmds.attributeQuery(STATE_ATTR, node=STATE_NODE, exists=True):
        cmds.addAttr(STATE_NODE, longName=STATE_ATTR, dataType="string")

    return STATE_NODE


def save_state(data):
    node = _ensure_state_node()
    cmds.setAttr(node + "." + STATE_ATTR, json.dumps(data), type="string")


def load_state():
    if not cmds.objExists(STATE_NODE):
        return {}

    if not cmds.attributeQuery(STATE_ATTR, node=STATE_NODE, exists=True):
        return {}

    raw = cmds.getAttr(STATE_NODE + "." + STATE_ATTR)

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except Exception:
        return {}


def clear_state():
    _safe_delete(STATE_NODE)


# ============================================================
# MESH GRAPH ANALYSIS
# ============================================================

class MeshGraph(object):
    """
    High-throughput mesh topology cache.

    The expensive Maya reads happen once through OpenMaya 2.0 iterators:
    - MItMeshPolygon feeds face normals and per-face edge IDs.
    - MItMeshEdge feeds edge -> connected faces.
    The grow step then works on compact Python adjacency lists backed by
    OpenMaya vector arrays, avoiding repeated cmds calls during calculation.
    """

    def __init__(self, transform, shape):
        self.transform = transform
        self.shape = shape

        self.dag = _get_dag_path(shape)
        self.fn = om.MFnMesh(self.dag)

        self.face_count = int(self.fn.numPolygons)
        self.edge_count = int(self.fn.numEdges)

        self.face_normals = om.MVectorArray()
        self.face_edges = [[] for _ in range(self.face_count)]
        self.edge_faces = [[] for _ in range(self.edge_count)]
        self.face_neighbors = [[] for _ in range(self.face_count)]
        self._edge_angle_cache = {}

        self._build()

    def _build(self):
        """
        Builds:
        - face normals as MVectorArray
        - face -> edge IDs
        - edge ID -> connected faces
        - face neighbor graph

        Important:
        We use MItMeshPolygon.getEdges() instead of MFnMesh.getPolygonEdges(),
        because getPolygonEdges does not exist in some Maya API 2.0 builds.
        """

        self._build_face_arrays()
        self._build_edge_arrays()
        self._build_neighbors()

    def _build_face_arrays(self):
        it_poly = om.MItMeshPolygon(self.dag)

        while not it_poly.isDone():
            face_id = int(it_poly.index())

            try:
                normal = self.fn.getPolygonNormal(face_id, om.MSpace.kWorld)
                if normal.length() > 1e-8:
                    normal.normalize()
            except Exception:
                normal = om.MVector(0.0, 1.0, 0.0)

            try:
                edges = [int(edge_id) for edge_id in it_poly.getEdges()]
            except Exception:
                edges = []

            self.face_normals.append(normal)
            self.face_edges[face_id] = edges
            it_poly.next()

    def _build_edge_arrays(self):
        it_edge = om.MItMeshEdge(self.dag)

        while not it_edge.isDone():
            edge_id = int(it_edge.index())

            try:
                faces = [int(face_id) for face_id in it_edge.getConnectedFaces()]
            except Exception:
                faces = []

            if 0 <= edge_id < self.edge_count:
                self.edge_faces[edge_id] = faces

            it_edge.next()

    def _build_neighbors(self):
        for edge_id, faces in enumerate(self.edge_faces):
            if len(faces) != 2:
                continue

            a, b = faces

            if 0 <= a < self.face_count and 0 <= b < self.face_count:
                self.face_neighbors[a].append((b, edge_id))
                self.face_neighbors[b].append((a, edge_id))

    def is_boundary_edge(self, edge_id):
        if edge_id is None or edge_id < 0 or edge_id >= self.edge_count:
            return True

        return len(self.edge_faces[edge_id]) < 2

    def edge_angle(self, face_a, face_b):
        cache_key = (face_a, face_b) if face_a < face_b else (face_b, face_a)
        cached = self._edge_angle_cache.get(cache_key)

        if cached is not None:
            return cached

        angle = _angle_between_vectors_deg(self.face_normals[face_a], self.face_normals[face_b])
        self._edge_angle_cache[cache_key] = angle
        return angle

    def edge_cross_cost(self, face_a, face_b, edge_id, settings):
        """
        Lower = easier to cross.
        Higher = likely shell boundary.
        """
        angle = self.edge_angle(face_a, face_b)
        cost = angle

        mode = settings.get("mode", "Balanced")

        if mode == "Planar":
            cost *= 1.50
        elif mode == "Organic":
            cost *= 0.65
        elif mode == "Hard Surface":
            cost *= 1.20
        elif mode == "Bevel Friendly":
            cost *= 0.80

        # Hard-surface-like boundary approximation.
        # Actual hard edge query is often too slow / unreliable with cmds.
        # This makes sharp angle transitions act like blockers in hard-surface modes.
        if settings.get("hard_edge_blocks", True):
            threshold = float(settings.get("angle_threshold", 35.0))

            if mode in ("Planar", "Hard Surface", "Balanced"):
                if angle >= max(25.0, threshold * 0.85):
                    cost += 1000.0

        return cost

    def grow_from_face(self, seed_face, settings):
        angle_threshold = float(settings.get("angle_threshold", 35.0))
        max_faces = int(settings.get("max_faces", 5000))

        seed_face = int(seed_face)

        visited = set([seed_face])
        accepted = set([seed_face])
        queue = deque([seed_face])

        while queue:
            current = queue.popleft()

            if len(accepted) >= max_faces:
                break

            for neighbor, edge_id in self.face_neighbors[current]:
                if neighbor in visited:
                    continue

                visited.add(neighbor)

                if self.is_boundary_edge(edge_id):
                    continue

                cost = self.edge_cross_cost(current, neighbor, edge_id, settings)

                if cost <= angle_threshold:
                    accepted.add(neighbor)
                    queue.append(neighbor)

        return sorted(accepted)

    def boundary_edges_of_faces(self, face_ids):
        face_set = set([int(f) for f in face_ids])
        boundary_edges = set()

        for face_id in face_set:
            for edge_id in self.face_edges[face_id]:
                if edge_id is None:
                    continue

                if edge_id < 0 or edge_id >= self.edge_count:
                    continue

                linked_faces = self.edge_faces[edge_id]

                if len(linked_faces) < 2:
                    boundary_edges.add(edge_id)
                else:
                    if any(linked_face not in face_set for linked_face in linked_faces):
                        boundary_edges.add(edge_id)

        return sorted(boundary_edges)


class LazyMeshGraph(object):
    """
    On-demand version used by hover seed detection.

    It avoids the expensive full-mesh topology scan. Only faces/edges touched
    by the grow operation are read from OpenMaya and cached.
    """

    def __init__(self, transform, shape):
        self.transform = transform
        self.shape = shape

        self.dag = _get_dag_path(shape)
        self.fn = om.MFnMesh(self.dag)

        self.face_count = int(self.fn.numPolygons)
        self.edge_count = int(self.fn.numEdges)

        self._poly_it = om.MItMeshPolygon(self.dag)
        self._edge_it = om.MItMeshEdge(self.dag)

        self._face_normals = {}
        self._face_edges = {}
        self._edge_faces = {}
        self._face_neighbors = {}
        self._edge_angle_cache = {}
        self._fallback_graph = None

    def _set_poly_index(self, face_id):
        try:
            self._poly_it.setIndex(int(face_id))
            return True
        except Exception:
            return False

    def _set_edge_index(self, edge_id):
        try:
            self._edge_it.setIndex(int(edge_id))
            return True
        except Exception:
            return False

    def _fallback(self):
        if self._fallback_graph is None:
            self._fallback_graph = MeshGraph(self.transform, self.shape)
        return self._fallback_graph

    def face_normal(self, face_id):
        face_id = int(face_id)
        cached = self._face_normals.get(face_id)
        if cached is not None:
            return cached

        try:
            normal = self.fn.getPolygonNormal(face_id, om.MSpace.kWorld)
            if normal.length() > 1e-8:
                normal.normalize()
        except Exception:
            normal = om.MVector(0.0, 1.0, 0.0)

        self._face_normals[face_id] = normal
        return normal

    def face_edges(self, face_id):
        face_id = int(face_id)
        cached = self._face_edges.get(face_id)
        if cached is not None:
            return cached

        if not self._set_poly_index(face_id):
            return self._fallback().face_edges[face_id]

        try:
            edges = [int(edge_id) for edge_id in self._poly_it.getEdges()]
        except Exception:
            edges = []

        self._face_edges[face_id] = edges
        return edges

    def edge_faces(self, edge_id):
        edge_id = int(edge_id)
        cached = self._edge_faces.get(edge_id)
        if cached is not None:
            return cached

        if edge_id < 0 or edge_id >= self.edge_count:
            return []

        if not self._set_edge_index(edge_id):
            return self._fallback().edge_faces[edge_id]

        try:
            faces = [int(face_id) for face_id in self._edge_it.getConnectedFaces()]
        except Exception:
            faces = []

        self._edge_faces[edge_id] = faces
        return faces

    def face_neighbors(self, face_id):
        face_id = int(face_id)
        cached = self._face_neighbors.get(face_id)
        if cached is not None:
            return cached

        neighbors = []

        for edge_id in self.face_edges(face_id):
            faces = self.edge_faces(edge_id)
            if len(faces) != 2:
                continue

            other = faces[1] if faces[0] == face_id else faces[0]
            if other != face_id:
                neighbors.append((other, edge_id))

        self._face_neighbors[face_id] = neighbors
        return neighbors

    def is_boundary_edge(self, edge_id):
        if edge_id is None or edge_id < 0 or edge_id >= self.edge_count:
            return True

        return len(self.edge_faces(edge_id)) < 2

    def edge_angle(self, face_a, face_b):
        cache_key = (face_a, face_b) if face_a < face_b else (face_b, face_a)
        cached = self._edge_angle_cache.get(cache_key)

        if cached is not None:
            return cached

        angle = _angle_between_vectors_deg(self.face_normal(face_a), self.face_normal(face_b))
        self._edge_angle_cache[cache_key] = angle
        return angle

    def edge_cross_cost(self, face_a, face_b, edge_id, settings):
        angle = self.edge_angle(face_a, face_b)
        cost = angle

        mode = settings.get("mode", "Balanced")

        if mode == "Planar":
            cost *= 1.50
        elif mode == "Organic":
            cost *= 0.65
        elif mode == "Hard Surface":
            cost *= 1.20
        elif mode == "Bevel Friendly":
            cost *= 0.80

        if settings.get("hard_edge_blocks", True):
            threshold = float(settings.get("angle_threshold", 35.0))

            if mode in ("Planar", "Hard Surface", "Balanced"):
                if angle >= max(25.0, threshold * 0.85):
                    cost += 1000.0

        return cost

    def grow_from_face(self, seed_face, settings):
        angle_threshold = float(settings.get("angle_threshold", 35.0))
        max_faces = int(settings.get("max_faces", 5000))

        seed_face = int(seed_face)

        visited = set([seed_face])
        accepted = set([seed_face])
        queue = deque([seed_face])

        while queue:
            current = queue.popleft()

            if len(accepted) >= max_faces:
                break

            for neighbor, edge_id in self.face_neighbors(current):
                if neighbor in visited:
                    continue

                visited.add(neighbor)

                if self.is_boundary_edge(edge_id):
                    continue

                cost = self.edge_cross_cost(current, neighbor, edge_id, settings)

                if cost <= angle_threshold:
                    accepted.add(neighbor)
                    queue.append(neighbor)

        return sorted(accepted)

    def boundary_edges_of_faces(self, face_ids):
        face_set = set([int(f) for f in face_ids])
        boundary_edges = set()

        for face_id in face_set:
            for edge_id in self.face_edges(face_id):
                linked_faces = self.edge_faces(edge_id)

                if len(linked_faces) < 2:
                    boundary_edges.add(edge_id)
                else:
                    if any(linked_face not in face_set for linked_face in linked_faces):
                        boundary_edges.add(edge_id)

        return sorted(boundary_edges)


# ============================================================
# HOVER RAYCAST PREVIEW
# ============================================================

class _HoverViewportEventFilter(QtCore.QObject if QtCore else object):
    def eventFilter(self, obj, event):
        if not HOVER_STATE.get("enabled"):
            return False

        try:
            event_type = event.type()

            if event_type == QtCore.QEvent.KeyPress:
                if event.key() == QtCore.Qt.Key_U and not event.isAutoRepeat():
                    detect_shell_from_hover_or_selection()
                    return True

            if event_type in (
                QtCore.QEvent.MouseMove,
                QtCore.QEvent.Enter,
                QtCore.QEvent.HoverMove,
            ):
                _hover_seed_tick()
        except Exception:
            traceback.print_exc()

        return False


def _widget_from_control(control_name):
    if omui is None or QtWidgets is None or shiboken2 is None:
        return None

    try:
        ptr = omui.MQtUtil.findControl(control_name)
    except Exception:
        ptr = None

    if not ptr:
        return None

    try:
        return shiboken2.wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        return None


def _get_view_from_model_panel(panel):
    if omui is None:
        return None

    try:
        view = omui.M3dView()
        omui.M3dView.getM3dViewFromModelPanel(panel, view)
        return view
    except Exception:
        pass

    try:
        return omui.M3dView.getM3dViewFromModelPanel(panel)
    except Exception:
        return None


def _find_viewport_coord_widget(widget):
    best = widget
    best_area = int(widget.width()) * int(widget.height())

    try:
        children = widget.findChildren(QtWidgets.QWidget)
    except Exception:
        children = []

    for child in children:
        try:
            class_name = child.metaObject().className()
            object_name = child.objectName()
            area = int(child.width()) * int(child.height())
        except Exception:
            continue

        if area <= 0:
            continue

        class_text = "{} {}".format(class_name, object_name).lower()
        if "gl" in class_text or "viewport" in class_text or "model" in class_text:
            if area >= best_area * 0.45:
                best = child
                best_area = area

    return best


def _install_hover_event_filter():
    if QtCore is None or QtWidgets is None:
        return False

    _remove_hover_event_filter()

    event_filter = _HoverViewportEventFilter()
    panel_widgets = []
    widgets = []

    for panel in cmds.getPanel(type="modelPanel") or []:
        try:
            control = cmds.modelPanel(panel, query=True, control=True)
        except Exception:
            control = None

        if not control:
            continue

        widget = _widget_from_control(control)
        if widget is None:
            continue

        coord_widget = _find_viewport_coord_widget(widget)
        panel_widgets.append((panel, coord_widget))

        candidates = [widget]
        try:
            candidates.extend(widget.findChildren(QtWidgets.QWidget))
        except Exception:
            pass

        for candidate in candidates:
            try:
                candidate.setMouseTracking(True)
                candidate.setAttribute(QtCore.Qt.WA_Hover, True)
                candidate.setFocusPolicy(QtCore.Qt.StrongFocus)
                candidate.installEventFilter(event_filter)
                widgets.append(candidate)
            except Exception:
                pass

    HOVER_STATE["event_filter"] = event_filter
    HOVER_STATE["panel_widgets"] = panel_widgets
    HOVER_STATE["widgets"] = widgets

    return bool(panel_widgets and widgets)


def _remove_hover_event_filter():
    event_filter = HOVER_STATE.get("event_filter")

    if event_filter is not None:
        for widget in HOVER_STATE.get("widgets", []):
            try:
                widget.removeEventFilter(event_filter)
            except Exception:
                pass

    HOVER_STATE["event_filter"] = None
    HOVER_STATE["panel_widgets"] = []
    HOVER_STATE["widgets"] = []


def _get_viewport_mouse_xy():
    if omui is None or QtGui is None or QtWidgets is None or shiboken2 is None:
        return None

    cursor_pos = QtGui.QCursor.pos()
    panels = HOVER_STATE.get("panel_widgets", [])

    try:
        panel_under_pointer = cmds.getPanel(underPointer=True)
    except Exception:
        panel_under_pointer = None

    if panel_under_pointer:
        prioritized = []
        remaining = []

        for panel_info in panels:
            panel, _ = panel_info
            if panel == panel_under_pointer:
                prioritized.append(panel_info)
            else:
                remaining.append(panel_info)

        panels = prioritized + remaining

    for panel, widget in panels:
        try:
            local_pos = widget.mapFromGlobal(cursor_pos)
            view = _get_view_from_model_panel(panel)
            if view is None:
                continue

            width = int(view.portWidth())
            height = int(view.portHeight())

            if local_pos.x() < 0 or local_pos.y() < 0:
                continue
            if local_pos.x() >= width or local_pos.y() >= height:
                continue

            HOVER_STATE["last_panel"] = panel

            # Qt is top-left origin; M3dView ray projection is bottom-left origin.
            return view, int(local_pos.x()), int(height - local_pos.y() - 1)

        except Exception:
            continue

    return None


def _view_ray_from_xy(view, x, y):
    try:
        source, direction = view.viewToWorld(int(x), int(y))
        return _api_point(source), _api_vector(direction)
    except Exception:
        pass

    if om1 is None:
        return None, None

    try:
        source = om1.MPoint()
        direction = om1.MVector()
        view.viewToWorld(int(x), int(y), source, direction)
        return _api_point(source), _api_vector(direction)
    except Exception:
        return None, None


def _iter_visible_mesh_shapes():
    for shape in cmds.ls(type="mesh", long=True) or []:
        if _is_mesh_shape_pickable(shape):
            yield shape


def _get_raycast_mesh_fn(shape):
    cached = HOVER_STATE["ray_mesh_cache"].get(shape)
    if cached is not None:
        return cached

    dag = _get_dag_path(shape)
    fn = om.MFnMesh(dag)
    HOVER_STATE["ray_mesh_cache"][shape] = fn
    return fn


def _raycast_viewport_face():
    mouse = _get_viewport_mouse_xy()
    if mouse is None:
        return None

    view, x, y = mouse
    ray_source, ray_direction = _view_ray_from_xy(view, x, y)
    if ray_source is None or ray_direction is None:
        return None

    best = None
    best_distance = None

    for shape in _iter_visible_mesh_shapes():
        try:
            fn = _get_raycast_mesh_fn(shape)
            hit = fn.closestIntersection(
                ray_source,
                ray_direction,
                om.MSpace.kWorld,
                1.0e10,
                False
            )
        except Exception:
            hit = None

        if not hit:
            continue

        try:
            distance = float(hit[1])
            face_id = int(hit[2])
        except Exception:
            continue

        if best_distance is None or distance < best_distance:
            best_distance = distance
            best = (_get_transform_from_shape(shape), shape, face_id)

    return best


def _get_hover_graph(transform, shape):
    cache_key = shape
    cached = HOVER_STATE["graph_cache"].get(cache_key)

    if cached is not None:
        return cached

    graph = LazyMeshGraph(transform, shape)
    HOVER_STATE["graph_cache"][cache_key] = graph
    return graph


def _apply_preview_result(transform, shape, seed_face, faces, edges, settings, preview_set, select_faces, create_set=True):
    save_state({
        "transform": transform,
        "shape": shape,
        "seed_face": seed_face,
        "faces": faces,
        "boundary_edges": edges,
        "settings": settings
    })

    face_components = None

    if create_set:
        face_components = [_face_component(transform, f) for f in faces]
        _safe_delete(preview_set)

        if face_components:
            try:
                cmds.sets(face_components, name=preview_set)
            except Exception:
                pass

    if select_faces:
        if not _select_faces_api(shape, faces):
            if face_components is None:
                face_components = [_face_component(transform, f) for f in faces]
            cmds.select(face_components, replace=True)


def _build_preview_from_face(transform, shape, seed_face, settings, preview_set, select_faces, use_cache=False, create_set=True):
    if use_cache:
        graph = _get_hover_graph(transform, shape)
    else:
        graph = MeshGraph(transform, shape)

    faces = graph.grow_from_face(seed_face, settings)
    edges = graph.boundary_edges_of_faces(faces)

    _apply_preview_result(
        transform,
        shape,
        seed_face,
        faces,
        edges,
        settings,
        preview_set,
        select_faces,
        create_set=create_set
    )

    return faces, edges


def _hover_seed_tick():
    if not HOVER_STATE.get("enabled"):
        return

    now = time.time()
    if now - HOVER_STATE.get("last_tick_time", 0.0) < 0.08:
        return
    HOVER_STATE["last_tick_time"] = now

    hit = _raycast_viewport_face()
    if hit is None:
        if HOVER_STATE.get("last_hit") is not None:
            _set_hover_status("Hover Seed: no mesh under mouse")
        return

    transform, shape, face_id = hit
    hit_key = (shape, int(face_id))

    if hit_key == HOVER_STATE.get("last_hit"):
        return

    HOVER_STATE["last_hit"] = hit_key

    _set_hover_status(
        "Hover Seed: face {} ready. Press U to detect shell.".format(face_id)
    )


def _current_hover_or_raycast_face():
    hit = _raycast_viewport_face()
    if hit is not None:
        transform, shape, face_id = hit
        HOVER_STATE["last_hit"] = (shape, int(face_id))
        return transform, shape, face_id

    last_hit = HOVER_STATE.get("last_hit")
    if not last_hit:
        return None, None, None

    shape, face_id = last_hit
    if not shape or not cmds.objExists(shape):
        return None, None, None

    return _get_transform_from_shape(shape), shape, int(face_id)


def detect_shell_from_hover_or_selection():
    transform, shape, seed_face = _get_single_selected_face()
    source = "selected"

    if transform is None:
        transform, shape, seed_face = _current_hover_or_raycast_face()
        source = "hover"

    if transform is None:
        _warn("Survole une face ou sélectionne une face, puis appuie sur U.")
        _set_hover_status("Hover Seed: no face available for U.")
        return

    settings = get_ui_settings()

    try:
        started = time.time()
        faces, edges = _build_preview_from_face(
            transform,
            shape,
            seed_face,
            settings,
            HOVER_PREVIEW_SET,
            settings.get("select_preview", True),
            use_cache=True,
            create_set=False
        )

        _set_hover_status(
            "Detected from {} face {}: {} shell faces, {} boundary edges, {:.0f} ms.".format(
                source,
                seed_face,
                len(faces),
                len(edges),
                (time.time() - started) * 1000.0
            )
        )

        _log(
            "Detected shell from {} face {}: {} faces, {} boundary edges.".format(
                source,
                seed_face,
                len(faces),
                len(edges)
            )
        )

    except Exception as e:
        traceback.print_exc()
        _warn("Detect failed: {}".format(e))
        _set_hover_status("Detect failed: {}".format(e))


def start_hover_preview():
    if HOVER_STATE.get("enabled"):
        _set_hover_status("Hover Seed: ON")
        return

    if omui is None or QtCore is None or QtGui is None:
        _warn("Hover Seed requires Maya OpenMayaUI + Qt.")
        return

    if not _install_hover_event_filter():
        _warn("Hover Seed could not find a Maya modelPanel viewport.")
        return

    HOVER_STATE["enabled"] = True
    HOVER_STATE["last_hit"] = None
    HOVER_STATE["last_panel"] = None
    HOVER_STATE["last_tick_time"] = 0.0
    HOVER_STATE["graph_cache"] = {}
    HOVER_STATE["ray_mesh_cache"] = {}

    _set_hover_status(
        "Hover Seed: ON ({} viewport widgets). Hover a face, then press U.".format(
            len(HOVER_STATE.get("widgets", []))
        )
    )
    _log("Hover Seed enabled. Press U over a face or with a face selected.")


def stop_hover_preview():
    job = HOVER_STATE.get("job")

    if job is not None:
        try:
            if cmds.scriptJob(exists=job):
                cmds.scriptJob(kill=job, force=True)
        except Exception:
            pass

    HOVER_STATE["enabled"] = False
    HOVER_STATE["job"] = None
    _remove_hover_event_filter()
    HOVER_STATE["last_hit"] = None
    HOVER_STATE["last_panel"] = None
    HOVER_STATE["last_tick_time"] = 0.0
    HOVER_STATE["graph_cache"] = {}
    HOVER_STATE["ray_mesh_cache"] = {}

    _set_hover_status("Hover Seed: OFF")
    _log("Hover Seed disabled.")


def toggle_hover_preview():
    if HOVER_STATE.get("enabled"):
        stop_hover_preview()
    else:
        start_hover_preview()


# ============================================================
# SMART PREVIEW / CUTS
# ============================================================

def get_ui_settings():
    settings = dict(DEFAULTS)

    if cmds.floatSliderGrp("smartUV_angleThreshold_FSG", exists=True):
        settings["angle_threshold"] = cmds.floatSliderGrp(
            "smartUV_angleThreshold_FSG",
            query=True,
            value=True
        )

    if cmds.checkBox("smartUV_hardEdge_CB", exists=True):
        settings["hard_edge_blocks"] = cmds.checkBox(
            "smartUV_hardEdge_CB",
            query=True,
            value=True
        )

    if cmds.intSliderGrp("smartUV_maxFaces_ISG", exists=True):
        settings["max_faces"] = cmds.intSliderGrp(
            "smartUV_maxFaces_ISG",
            query=True,
            value=True
        )

    if cmds.optionMenu("smartUV_mode_OM", exists=True):
        settings["mode"] = cmds.optionMenu(
            "smartUV_mode_OM",
            query=True,
            value=True
        )

    if cmds.checkBox("smartUV_selectPreview_CB", exists=True):
        settings["select_preview"] = cmds.checkBox(
            "smartUV_selectPreview_CB",
            query=True,
            value=True
        )

    return settings


def preview_smart_shell_from_selected_face():
    transform, shape, seed_face = _get_selected_face()

    if transform is None:
        _warn("Sélectionne une face seed sur un mesh.")
        return

    settings = get_ui_settings()

    try:
        faces, edges = _build_preview_from_face(
            transform,
            shape,
            seed_face,
            settings,
            PREVIEW_SET,
            settings.get("select_preview", True)
        )

        _log(
            "Preview shell: {} faces, {} boundary edges. Seed face: {}. Mode: {}.".format(
                len(faces),
                len(edges),
                seed_face,
                settings.get("mode")
            )
        )

    except Exception as e:
        traceback.print_exc()
        _warn("Preview failed: {}".format(e))


def select_boundary_edges_from_preview():
    state = load_state()

    if not state or not state.get("boundary_edges"):
        _warn("Aucun preview disponible. Lance d'abord Preview Smart Shell.")
        return

    transform = state.get("transform")
    shape = state.get("shape")
    edges = state.get("boundary_edges", [])

    if not transform or not cmds.objExists(transform):
        _warn("L'objet du preview n'existe plus.")
        return

    if not shape or not cmds.objExists(shape) or not _select_edges_api(shape, edges):
        components = [_edge_component(transform, e) for e in edges]
        cmds.select(components, replace=True)

    _log("Selected {} boundary edges.".format(len(edges)))


def select_preview_faces():
    state = load_state()

    if not state or not state.get("faces"):
        _warn("Aucun preview disponible.")
        return

    transform = state.get("transform")
    shape = state.get("shape")
    faces = state.get("faces", [])

    if not transform or not cmds.objExists(transform):
        _warn("L'objet du preview n'existe plus.")
        return

    if not shape or not cmds.objExists(shape) or not _select_faces_api(shape, faces):
        components = [_face_component(transform, f) for f in faces]
        cmds.select(components, replace=True)

    _log("Selected {} preview faces.".format(len(faces)))


def cut_boundary_around_preview():
    state = load_state()

    if not state or not state.get("boundary_edges"):
        _warn("Aucun boundary edge disponible. Lance d'abord Preview Smart Shell.")
        return

    transform = state.get("transform")
    edges = state.get("boundary_edges", [])

    if not transform or not cmds.objExists(transform):
        _warn("L'objet du preview n'existe plus.")
        return

    components = [_edge_component(transform, e) for e in edges]

    try:
        cmds.select(components, replace=True)
        cmds.polyMapCut(components)

        _log("UV cut applied on {} boundary edges.".format(len(components)))

    except Exception as e:
        traceback.print_exc()
        _warn("Cut failed: {}".format(e))


def clear_preview():
    _safe_delete(PREVIEW_SET)
    _safe_delete(HOVER_PREVIEW_SET)
    HOVER_STATE["last_hit"] = None
    HOVER_STATE["graph_cache"] = {}
    HOVER_STATE["ray_mesh_cache"] = {}
    clear_state()
    _log("Preview cleared.")


# ============================================================
# PRESETS
# ============================================================

def apply_preset(name):
    if name == "Planar":
        angle = 15.0
        max_faces = 3000
        hard = True
    elif name == "Hard Surface":
        angle = 32.0
        max_faces = 5000
        hard = True
    elif name == "Bevel Friendly":
        angle = 50.0
        max_faces = 7000
        hard = False
    elif name == "Organic":
        angle = 65.0
        max_faces = 10000
        hard = False
    else:
        name = "Balanced"
        angle = 35.0
        max_faces = 5000
        hard = True

    if cmds.optionMenu("smartUV_mode_OM", exists=True):
        cmds.optionMenu("smartUV_mode_OM", edit=True, value=name)

    if cmds.floatSliderGrp("smartUV_angleThreshold_FSG", exists=True):
        cmds.floatSliderGrp("smartUV_angleThreshold_FSG", edit=True, value=angle)

    if cmds.intSliderGrp("smartUV_maxFaces_ISG", exists=True):
        cmds.intSliderGrp("smartUV_maxFaces_ISG", edit=True, value=max_faces)

    if cmds.checkBox("smartUV_hardEdge_CB", exists=True):
        cmds.checkBox("smartUV_hardEdge_CB", edit=True, value=hard)


# ============================================================
# UI
# ============================================================

def show_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        stop_hover_preview()
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(
        WINDOW_NAME,
        title="Smart UV Shell Grow / Cut Finder Ultimate",
        sizeable=True,
        widthHeight=(430, 520),
        closeCommand=lambda *_: stop_hover_preview()
    )

    root = cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=8,
        columnOffset=("both", 10)
    )

    cmds.text(
        label="Smart UV Shell Grow / Cut Finder Ultimate",
        align="center",
        height=28,
        font="boldLabelFont"
    )

    cmds.text(
        label="Engine: OpenMaya 2.0 topology + vector arrays",
        align="center"
    )

    cmds.text(
        label=(
            "1. Active Hover Seed Tracking\n"
            "2. Survole une face ou sélectionne une face\n"
            "3. Appuie sur U pour détecter le shell\n"
            "4. Cut Boundary Around Preview"
        ),
        align="center"
    )

    cmds.separator(height=10, style="in")

    cmds.rowLayout(numberOfColumns=5, adjustableColumn=5)

    cmds.button(label="Balanced", command=lambda *_: apply_preset("Balanced"))
    cmds.button(label="Planar", command=lambda *_: apply_preset("Planar"))
    cmds.button(label="Hard Surface", command=lambda *_: apply_preset("Hard Surface"))
    cmds.button(label="Bevel Friendly", command=lambda *_: apply_preset("Bevel Friendly"))
    cmds.button(label="Organic", command=lambda *_: apply_preset("Organic"))

    cmds.setParent(root)

    cmds.optionMenu("smartUV_mode_OM", label="Mode")
    cmds.menuItem(label="Balanced")
    cmds.menuItem(label="Planar")
    cmds.menuItem(label="Hard Surface")
    cmds.menuItem(label="Bevel Friendly")
    cmds.menuItem(label="Organic")
    cmds.optionMenu("smartUV_mode_OM", edit=True, value=DEFAULTS["mode"])

    cmds.floatSliderGrp(
        "smartUV_angleThreshold_FSG",
        label="Angle threshold",
        field=True,
        minValue=1.0,
        maxValue=120.0,
        fieldMinValue=0.0,
        fieldMaxValue=180.0,
        value=DEFAULTS["angle_threshold"]
    )

    cmds.checkBox(
        "smartUV_hardEdge_CB",
        label="Block strong hard-surface angle changes",
        value=DEFAULTS["hard_edge_blocks"]
    )

    cmds.intSliderGrp(
        "smartUV_maxFaces_ISG",
        label="Max faces",
        field=True,
        minValue=10,
        maxValue=20000,
        fieldMinValue=1,
        fieldMaxValue=100000,
        value=DEFAULTS["max_faces"]
    )

    cmds.checkBox(
        "smartUV_selectPreview_CB",
        label="Select detected shell faces",
        value=DEFAULTS["select_preview"]
    )

    cmds.separator(height=10, style="in")

    cmds.button(
        label="Toggle Hover Seed Tracking",
        height=38,
        backgroundColor=(0.18, 0.38, 0.28),
        command=lambda *_: toggle_hover_preview()
    )

    cmds.text(
        HOVER_STATUS_CONTROL,
        label="Hover Seed: OFF",
        align="center"
    )

    cmds.button(
        label="Detect Shell From Hover / Selection (U)",
        height=34,
        backgroundColor=(0.24, 0.34, 0.28),
        command=lambda *_: detect_shell_from_hover_or_selection()
    )

    cmds.separator(height=10, style="in")

    cmds.button(
        label="Preview Smart Shell From Selected Face",
        height=38,
        backgroundColor=(0.25, 0.32, 0.42),
        command=lambda *_: preview_smart_shell_from_selected_face()
    )

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)

    cmds.button(
        label="Select Preview Faces",
        height=30,
        command=lambda *_: select_preview_faces()
    )

    cmds.button(
        label="Select Boundary Edges",
        height=30,
        command=lambda *_: select_boundary_edges_from_preview()
    )

    cmds.setParent(root)

    cmds.button(
        label="Cut Boundary Around Preview",
        height=38,
        backgroundColor=(0.38, 0.22, 0.16),
        command=lambda *_: cut_boundary_around_preview()
    )

    cmds.button(
        label="Clear Preview Data",
        height=28,
        command=lambda *_: clear_preview()
    )

    cmds.separator(height=10, style="in")

    cmds.text(
        label=(
            "Notes:\n"
            "- Le hover prépare seulement la face seed ; U lance la détection.\n"
            "- Si une face est sélectionnée, U utilise la sélection en priorité.\n"
            "- Planar / Hard Surface = plus strict.\n"
            "- Bevel Friendly / Organic = propagation plus large.\n"
            "- Le cut est créé autour du groupe de faces preview."
        ),
        align="center"
    )

    cmds.separator(height=10, style="none")

    cmds.button(
        label="Close",
        height=28,
        command=lambda *_: cmds.deleteUI(WINDOW_NAME)
    )

    cmds.showWindow(WINDOW_NAME)


# ============================================================
# RUN
# ============================================================

show_ui()
