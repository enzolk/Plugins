# ELK_META {"label": "Select Similar Faces", "short_name": "SimFaces", "tooltip": "Select All the sames faces on the mesh", "source": "python", "icon_svg": "layers-selected-bottom.svg", "icon_color": "#ff5d3b"}
# -*- coding: utf-8 -*-
"""
Find Similar Face Groups
Maya 2022
Uses maya.api.OpenMaya for all heavy mesh work.
"""

from __future__ import print_function

import time
import math
from collections import defaultdict, deque

import maya.api.OpenMaya as om

from PySide2 import QtWidgets, QtCore
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance


WINDOW_TITLE = "Find Similar Face Groups"


# ----------------------------------------------------------------------
# Maya UI helpers
# ----------------------------------------------------------------------

def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


# ----------------------------------------------------------------------
# Selection
# ----------------------------------------------------------------------

def get_selected_face_component():
    """
    Reads active selection and returns:
        dagPath, sorted_face_ids
    Requires exactly one mesh face component selection.
    """
    sel = om.MGlobal.getActiveSelectionList()

    if sel.length() == 0:
        raise RuntimeError("Selection vide. Sélectionne exactement un groupe de faces.")

    mesh_dag = None
    face_ids = set()
    found_face_component = False

    it = om.MItSelectionList(sel)
    while not it.isDone():
        try:
            dag, comp = it.getComponent()
        except Exception:
            it.next()
            continue

        if comp.isNull():
            raise RuntimeError("Sélection non-face détectée. Sélectionne des faces uniquement.")

        if dag.apiType() == om.MFn.kTransform:
            dag.extendToShape()

        if not dag.hasFn(om.MFn.kMesh):
            raise RuntimeError("La sélection contient autre chose qu'un mesh.")

        comp_fn = om.MFnComponent(comp)
        if comp_fn.componentType != om.MFn.kMeshPolygonComponent:
            raise RuntimeError("Sélection non-face détectée. Sélectionne des faces uniquement.")

        single_fn = om.MFnSingleIndexedComponent(comp)
        ids = single_fn.getElements()

        if mesh_dag is None:
            mesh_dag = om.MDagPath(dag)
        elif mesh_dag.fullPathName() != dag.fullPathName():
            raise RuntimeError("Plusieurs meshes sélectionnés. Sélectionne des faces sur un seul mesh.")

        face_ids.update(ids)
        found_face_component = True
        it.next()

    if not found_face_component or not face_ids:
        raise RuntimeError("Aucune face valide trouvée dans la sélection.")

    return mesh_dag, sorted(face_ids)


# ----------------------------------------------------------------------
# Mesh cache
# ----------------------------------------------------------------------

class MeshCache(object):
    def __init__(self, dag_path):
        self.dag_path = om.MDagPath(dag_path)
        self.fn_mesh = om.MFnMesh(self.dag_path)

        self.num_faces = self.fn_mesh.numPolygons
        self.num_edges = self.fn_mesh.numEdges
        self.num_vertices = self.fn_mesh.numVertices

        self.points = self.fn_mesh.getPoints(om.MSpace.kWorld)

        self.face_edges = [[] for _ in range(self.num_faces)]
        self.face_vertices = [[] for _ in range(self.num_faces)]
        self.face_edge_count = [0] * self.num_faces
        self.face_area = [0.0] * self.num_faces
        self.face_normal = [om.MVector.kZaxisVector] * self.num_faces

        self.edge_faces = [[] for _ in range(self.num_edges)]
        self.edge_vertices = [None] * self.num_edges
        self.edge_length = [0.0] * self.num_edges

        self.face_neighbors = [set() for _ in range(self.num_faces)]
        self.boundary_edges = set()
        self.non_manifold_edges = set()

        self._build()

    def _build(self):
        poly_it = om.MItMeshPolygon(self.dag_path)

        while not poly_it.isDone():
            f = poly_it.index()

            edges = list(poly_it.getEdges())
            verts = list(poly_it.getVertices())

            self.face_edges[f] = edges
            self.face_vertices[f] = verts
            self.face_edge_count[f] = len(edges)

            try:
                self.face_area[f] = max(float(poly_it.getArea(om.MSpace.kWorld)), 1e-12)
            except Exception:
                self.face_area[f] = 1e-12

            try:
                n = poly_it.getNormal(om.MSpace.kWorld)
                n.normalize()
                self.face_normal[f] = n
            except Exception:
                self.face_normal[f] = om.MVector.kZaxisVector

            for e in edges:
                self.edge_faces[e].append(f)

            poly_it.next()

        edge_it = om.MItMeshEdge(self.dag_path)
        while not edge_it.isDone():
            e = edge_it.index()
            v0 = edge_it.vertexId(0)
            v1 = edge_it.vertexId(1)

            self.edge_vertices[e] = (v0, v1)

            p0 = self.points[v0]
            p1 = self.points[v1]
            self.edge_length[e] = max((p1 - p0).length(), 1e-12)

            faces = self.edge_faces[e]

            if len(faces) < 2:
                self.boundary_edges.add(e)
            elif len(faces) > 2:
                self.non_manifold_edges.add(e)

            for i in range(len(faces)):
                fi = faces[i]
                for j in range(i + 1, len(faces)):
                    fj = faces[j]
                    self.face_neighbors[fi].add(fj)
                    self.face_neighbors[fj].add(fi)

            edge_it.next()

        self.face_neighbors = [frozenset(x) for x in self.face_neighbors]

    def shared_edges(self, f_a, f_b):
        return set(self.face_edges[f_a]).intersection(self.face_edges[f_b])

    def are_adjacent(self, f_a, f_b):
        return f_b in self.face_neighbors[f_a]

    def centroid(self, face_id):
        verts = self.face_vertices[face_id]
        p = om.MVector()
        for v in verts:
            pt = self.points[v]
            p += om.MVector(pt.x, pt.y, pt.z)
        return p / max(len(verts), 1)


# ----------------------------------------------------------------------
# Patch signature
# ----------------------------------------------------------------------

class PatchSignature(object):
    def __init__(self, cache, faces):
        self.cache = cache
        self.faces = tuple(sorted(faces))
        self.face_set = set(self.faces)
        self.face_count = len(self.faces)

        self.internal_edges = []
        self.boundary_edges = []
        self.face_side_counts = []
        self.face_areas = []
        self.edge_lengths_internal = []
        self.edge_lengths_boundary = []
        self.normal_angles = []
        self.adjacency_pairs = set()

        self.is_connected = False
        self.mean_area = 1.0
        self.mean_edge = 1.0
        self.anchor_face = None

        self._build()

    def _build(self):
        edge_hit_count = defaultdict(int)

        for f in self.faces:
            self.face_side_counts.append(self.cache.face_edge_count[f])
            self.face_areas.append(self.cache.face_area[f])
            for e in self.cache.face_edges[f]:
                edge_hit_count[e] += 1

        for e, count in edge_hit_count.items():
            if count >= 2:
                self.internal_edges.append(e)
            else:
                self.boundary_edges.append(e)

        for e in self.internal_edges:
            self.edge_lengths_internal.append(self.cache.edge_length[e])

            patch_faces = [f for f in self.cache.edge_faces[e] if f in self.face_set]
            if len(patch_faces) >= 2:
                a, b = patch_faces[0], patch_faces[1]
                self.adjacency_pairs.add(tuple(sorted((a, b))))

                na = self.cache.face_normal[a]
                nb = self.cache.face_normal[b]
                dot = max(-1.0, min(1.0, na * nb))
                self.normal_angles.append(math.acos(dot))

        for e in self.boundary_edges:
            self.edge_lengths_boundary.append(self.cache.edge_length[e])

        self.mean_area = max(sum(self.face_areas) / max(len(self.face_areas), 1), 1e-12)

        all_lengths = self.edge_lengths_internal + self.edge_lengths_boundary
        self.mean_edge = max(sum(all_lengths) / max(len(all_lengths), 1), 1e-12)

        self.face_side_counts.sort()
        self.edge_lengths_internal.sort()
        self.edge_lengths_boundary.sort()
        self.face_areas.sort()
        self.normal_angles.sort()

        self.is_connected = self._check_connected()
        self.anchor_face = self._pick_anchor()

    def _check_connected(self):
        if not self.faces:
            return False

        start = self.faces[0]
        visited = set([start])
        stack = [start]

        while stack:
            f = stack.pop()
            for n in self.cache.face_neighbors[f]:
                if n in self.face_set and n not in visited:
                    visited.add(n)
                    stack.append(n)

        return len(visited) == len(self.face_set)

    def _pick_anchor(self):
        """
        Picks the most distinctive face in the patch.
        """
        best = None
        best_score = None

        for f in self.faces:
            patch_degree = 0
            boundary_count = 0
            internal_count = 0

            for e in self.cache.face_edges[f]:
                count = 0
                for ef in self.cache.edge_faces[e]:
                    if ef in self.face_set:
                        count += 1

                if count >= 2:
                    internal_count += 1
                else:
                    boundary_count += 1

            for n in self.cache.face_neighbors[f]:
                if n in self.face_set:
                    patch_degree += 1

            score = (
                self.cache.face_edge_count[f],
                patch_degree,
                boundary_count,
                internal_count,
                round(self.cache.face_area[f] / self.mean_area, 4),
            )

            if best_score is None or score > best_score:
                best_score = score
                best = f

        return best

    def quick_tuple(self):
        return (
            self.face_count,
            len(self.internal_edges),
            len(self.boundary_edges),
            tuple(self.face_side_counts),
        )


# ----------------------------------------------------------------------
# Matching
# ----------------------------------------------------------------------

class SimilarFaceGroupFinder(object):
    def __init__(self, cache, source_faces, tolerance=0.05, max_candidates=5000, include_source=False, debug=False):
        self.cache = cache
        self.source_faces = tuple(sorted(source_faces))
        self.source_set = set(self.source_faces)
        self.tolerance = max(float(tolerance), 0.0)
        self.max_candidates = max(int(max_candidates), 1)
        self.include_source = bool(include_source)
        self.debug = bool(debug)

        self.source_sig = PatchSignature(cache, self.source_faces)

        if not self.source_sig.is_connected:
            raise RuntimeError(
                "Le patch source n'est pas connecté. "
                "Ce script cherche un groupe de faces connecté de même taille."
            )

        self.source_order = self._build_source_order()
        self.source_anchor = self.source_sig.anchor_face

        self.candidates_tested = 0
        self.matches = set()

    def log(self, msg):
        if self.debug:
            print("[Find Similar Face Groups] " + msg)

    def _build_source_order(self):
        """
        BFS from anchor.
        Connected source patch only.
        """
        order = []
        visited = set([self.source_sig.anchor_face])
        q = deque([self.source_sig.anchor_face])

        while q:
            f = q.popleft()
            order.append(f)

            neigh = [
                n for n in self.cache.face_neighbors[f]
                if n in self.source_set and n not in visited
            ]

            neigh.sort(key=lambda x: (
                -self.cache.face_edge_count[x],
                -len(self.cache.face_neighbors[x]),
                x,
            ))

            for n in neigh:
                visited.add(n)
                q.append(n)

        return order

    def _face_fast_compatible(self, src_f, dst_f):
        if self.cache.face_edge_count[src_f] != self.cache.face_edge_count[dst_f]:
            return False

        src_area = self.cache.face_area[src_f] / self.source_sig.mean_area
        dst_area = self.cache.face_area[dst_f] / self.source_sig.mean_area

        if not self._close(src_area, dst_area, self.tolerance * 2.0):
            return False

        return True

    @staticmethod
    def _close(a, b, tol):
        scale = max(abs(a), abs(b), 1e-12)
        return abs(a - b) <= tol * scale

    def _list_close(self, a, b, norm_a, norm_b, tol):
        if len(a) != len(b):
            return False

        for x, y in zip(a, b):
            nx = x / norm_a
            ny = y / norm_b
            if not self._close(nx, ny, tol):
                return False

        return True

    def _candidate_anchor_faces(self):
        src = self.source_anchor
        src_sides = self.cache.face_edge_count[src]

        for f in range(self.cache.num_faces):
            if self.cache.face_edge_count[f] != src_sides:
                continue
            yield f

    def find(self):
        if self.source_sig.quick_tuple()[0] == 0:
            return []

        for dst_anchor in self._candidate_anchor_faces():
            if self.candidates_tested >= self.max_candidates:
                break

            if not self._face_fast_compatible(self.source_anchor, dst_anchor):
                continue

            mapping = {self.source_anchor: dst_anchor}
            used_dst = set([dst_anchor])

            self._backtrack(mapping, used_dst)

        result = sorted(self.matches, key=lambda x: tuple(x))
        return [tuple(sorted(x)) for x in result]

    def _backtrack(self, mapping, used_dst):
        if self.candidates_tested >= self.max_candidates:
            return

        if len(mapping) == len(self.source_order):
            self.candidates_tested += 1
            patch = frozenset(used_dst)

            if not self.include_source and patch == frozenset(self.source_set):
                return

            if self._final_compare(mapping, patch):
                self.matches.add(patch)
            return

        src_f = self.source_order[len(mapping)]

        mapped_src_neighbors = [
            n for n in self.cache.face_neighbors[src_f]
            if n in mapping
        ]

        if mapped_src_neighbors:
            candidate_pool = None
            for src_n in mapped_src_neighbors:
                dst_n = mapping[src_n]
                neigh = self.cache.face_neighbors[dst_n]

                if candidate_pool is None:
                    candidate_pool = set(neigh)
                else:
                    candidate_pool.intersection_update(neigh)

            if candidate_pool is None:
                return
        else:
            candidate_pool = set(range(self.cache.num_faces))

        for dst_f in candidate_pool:
            if dst_f in used_dst:
                continue

            if not self._face_fast_compatible(src_f, dst_f):
                continue

            if not self._partial_topology_ok(src_f, dst_f, mapping):
                continue

            mapping[src_f] = dst_f
            used_dst.add(dst_f)

            self._backtrack(mapping, used_dst)

            used_dst.remove(dst_f)
            del mapping[src_f]

            if self.candidates_tested >= self.max_candidates:
                return

    def _partial_topology_ok(self, src_f, dst_f, mapping):
        """
        Preserves adjacency and non-adjacency among already mapped faces.
        """
        for src_other, dst_other in mapping.items():
            src_adj = self.cache.are_adjacent(src_f, src_other)
            dst_adj = self.cache.are_adjacent(dst_f, dst_other)

            if src_adj != dst_adj:
                return False

            if src_adj:
                src_shared = self.cache.shared_edges(src_f, src_other)
                dst_shared = self.cache.shared_edges(dst_f, dst_other)

                if len(src_shared) != len(dst_shared):
                    return False

        return True

    def _final_compare(self, mapping, patch):
        dst_sig = PatchSignature(self.cache, patch)

        if dst_sig.quick_tuple() != self.source_sig.quick_tuple():
            return False

        if not dst_sig.is_connected:
            return False

        if not self._list_close(
            self.source_sig.face_areas,
            dst_sig.face_areas,
            self.source_sig.mean_area,
            dst_sig.mean_area,
            self.tolerance,
        ):
            return False

        if not self._list_close(
            self.source_sig.edge_lengths_internal,
            dst_sig.edge_lengths_internal,
            self.source_sig.mean_edge,
            dst_sig.mean_edge,
            self.tolerance,
        ):
            return False

        if not self._list_close(
            self.source_sig.edge_lengths_boundary,
            dst_sig.edge_lengths_boundary,
            self.source_sig.mean_edge,
            dst_sig.mean_edge,
            self.tolerance,
        ):
            return False

        if not self._list_close(
            self.source_sig.normal_angles,
            dst_sig.normal_angles,
            1.0,
            1.0,
            self.tolerance * 2.0,
        ):
            return False

        return True


# ----------------------------------------------------------------------
# Selection output
# ----------------------------------------------------------------------

def select_faces(dag_path, face_ids):
    comp_fn = om.MFnSingleIndexedComponent()
    comp = comp_fn.create(om.MFn.kMeshPolygonComponent)
    comp_fn.addElements(list(face_ids))

    sel = om.MSelectionList()
    sel.add((dag_path, comp))

    om.MGlobal.setActiveSelectionList(sel, om.MGlobal.kReplaceList)

    try:
        om.MGlobal.setSelectionMode(om.MGlobal.kSelectComponentMode)
        om.MGlobal.setComponentSelectionMask(om.MSelectionMask.kSelectMeshFaces)
    except Exception:
        pass


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

class FindSimilarFaceGroupsUI(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(FindSimilarFaceGroupsUI, self).__init__(parent)

        self.setWindowTitle(WINDOW_TITLE)
        self.setObjectName("FindSimilarFaceGroupsUI")
        self.setMinimumWidth(520)
        self.setMinimumHeight(420)

        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()

        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setRange(0.001, 100.0)
        self.tol_spin.setDecimals(3)
        self.tol_spin.setValue(3.0)
        self.tol_spin.setSuffix(" %")

        self.max_candidates_spin = QtWidgets.QSpinBox()
        self.max_candidates_spin.setRange(1, 1000000)
        self.max_candidates_spin.setValue(5000)

        self.include_source_cb = QtWidgets.QCheckBox()
        self.include_source_cb.setChecked(False)

        self.debug_cb = QtWidgets.QCheckBox()
        self.debug_cb.setChecked(False)

        form.addRow("Tolerance (%)", self.tol_spin)
        form.addRow("Max candidates", self.max_candidates_spin)
        form.addRow("Include source patch", self.include_source_cb)
        form.addRow("Debug logs", self.debug_cb)

        layout.addLayout(form)

        self.run_btn = QtWidgets.QPushButton("Find Similar Face Groups")
        self.run_btn.setMinimumHeight(34)
        layout.addWidget(self.run_btn)

        self.logs = QtWidgets.QPlainTextEdit()
        self.logs.setReadOnly(True)
        layout.addWidget(self.logs)

    def _connect(self):
        self.run_btn.clicked.connect(self.run)

    def log(self, msg):
        self.logs.appendPlainText(msg)
        QtWidgets.QApplication.processEvents()

    def run(self):
        self.logs.clear()
        self.run_btn.setEnabled(False)

        t0 = time.time()

        try:
            dag, source_faces = get_selected_face_component()

            self.log("Mesh: {}".format(dag.fullPathName()))
            self.log("Faces source: {}".format(len(source_faces)))
            self.log("Construction du cache mesh...")

            cache_t0 = time.time()
            cache = MeshCache(dag)
            cache_dt = time.time() - cache_t0

            self.log(
                "Cache OK: {} faces, {} edges, {} vertices en {:.3f}s".format(
                    cache.num_faces,
                    cache.num_edges,
                    cache.num_vertices,
                    cache_dt,
                )
            )

            finder = SimilarFaceGroupFinder(
                cache=cache,
                source_faces=source_faces,
                tolerance=self.tol_spin.value() / 100.0,
                max_candidates=self.max_candidates_spin.value(),
                include_source=self.include_source_cb.isChecked(),
                debug=self.debug_cb.isChecked(),
            )

            self.log("Recherche des patches similaires...")

            matches = finder.find()

            all_faces = set()
            for patch in matches:
                all_faces.update(patch)

            if all_faces:
                select_faces(dag, sorted(all_faces))
            else:
                select_faces(dag, [])

            total_dt = time.time() - t0

            self.log("")
            self.log("Candidats testés: {}".format(finder.candidates_tested))
            self.log("Patches trouvés: {}".format(len(matches)))
            self.log("Faces sélectionnées: {}".format(len(all_faces)))
            self.log("Temps total: {:.3f}s".format(total_dt))

        except Exception as exc:
            self.log("ERREUR: {}".format(exc))
            om.MGlobal.displayError(str(exc))

        finally:
            self.run_btn.setEnabled(True)


# ----------------------------------------------------------------------
# Launcher
# ----------------------------------------------------------------------

_FIND_SIMILAR_FACE_GROUPS_UI = None


def show_find_similar_face_groups():
    global _FIND_SIMILAR_FACE_GROUPS_UI

    try:
        if _FIND_SIMILAR_FACE_GROUPS_UI is not None:
            _FIND_SIMILAR_FACE_GROUPS_UI.close()
            _FIND_SIMILAR_FACE_GROUPS_UI.deleteLater()
    except Exception:
        pass

    _FIND_SIMILAR_FACE_GROUPS_UI = FindSimilarFaceGroupsUI()
    _FIND_SIMILAR_FACE_GROUPS_UI.show()
    return _FIND_SIMILAR_FACE_GROUPS_UI


show_find_similar_face_groups()