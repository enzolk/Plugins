# ELK_META {"label": "Weighted Normals Pro", "short_name": "WNorm", "tooltip": "Outil avancé de weighted normals avec live preview, hard edge detection, UV seam support, smoothing et blending configurable en temps réel.", "source": "python", "icon_svg": "border-corner-rounded.svg", "icon_color": "#ff5d3b"}
# -*- coding: utf-8 -*-

import math

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtCore, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtWidgets
    from shiboken2 import wrapInstance


# ---------------------------------------------------------------------------
# Collapsible section widget
# ---------------------------------------------------------------------------
class CollapsibleSection(QtWidgets.QWidget):
    toggled = QtCore.Signal(bool)

    def __init__(self, title, parent=None, expanded=False):
        super(CollapsibleSection, self).__init__(parent)
        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow
        )

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content.setVisible(expanded)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content)

        self.toggle_button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        self.content.setVisible(checked)
        self.toggle_button.setArrowType(
            QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow
        )
        self.toggled.emit(checked)


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------
class WeightedNormalsTool(QtWidgets.QDialog):
    WINDOW_NAME = "WeightedNormalsUI_PowerSnap"

    def __init__(self, parent=None):
        super(WeightedNormalsTool, self).__init__(parent)
        self.setObjectName(self.WINDOW_NAME)
        self.setWindowTitle("Weighted Normals Pro")
        self.resize(380, 330)
        self.setMinimumWidth(360)
        self.setMinimumHeight(240)
        self._ui_scale = 1.0
        self._base_font_size = max(float(self.font().pointSizeF()), 10.0)
        self._section_widgets = []

        self._live_active = False
        self._live_meshes = []
        self._live_timer = QtCore.QTimer(self)
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(16)
        self._live_timer.timeout.connect(self._live_apply)

        self._build_ui()
        self.update_ui_states()

    # =========================================================
    # UI BUILD
    # =========================================================
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        root.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)

        self._build_header_controls(root)
        self._build_weighting_section(root)
        self._build_hard_edges_section(root)
        self._build_smoothing_section(root)
        self._build_display_section(root)

        root.addSpacing(4)

        self.btn_apply = QtWidgets.QPushButton("APPLY WEIGHTED NORMALS")
        self.btn_apply.setMinimumHeight(34)
        self.btn_apply.clicked.connect(self.apply_normals)

        self.btn_live = QtWidgets.QPushButton("LIVE PREVIEW")
        self.btn_live.setCheckable(True)
        self.btn_live.setMinimumHeight(28)
        self.btn_live.setObjectName("live_btn")
        self.btn_live.clicked.connect(self._on_live_toggled)

        bottom_row = QtWidgets.QHBoxLayout()
        self.btn_deselect = QtWidgets.QPushButton("Deselect (keep)")
        self.btn_deselect.setMinimumHeight(26)
        self.btn_deselect.clicked.connect(self._deselect_keep)

        self.btn_unfreeze = QtWidgets.QPushButton("Unfreeze Normals")
        self.btn_unfreeze.setMinimumHeight(26)
        self.btn_unfreeze.clicked.connect(self.unfreeze_normals)

        bottom_row.addWidget(self.btn_deselect)
        bottom_row.addWidget(self.btn_unfreeze)

        root.addWidget(self.btn_apply)
        root.addWidget(self.btn_live)
        root.addLayout(bottom_row)
        root.addStretch(1)

        self.setStyleSheet("""
            QDialog  { background: #1f1f1f; color: #ececec; }
            QToolButton {
                background: #2c2c2c; border: 1px solid #434343;
                border-radius: 6px; padding: 5px;
                font-weight: 600; text-align: left;
            }
            QGroupBox {
                border: 1px solid #3f3f3f; border-radius: 8px;
                margin-top: 10px; padding-top: 12px; background: #242424;
            }
            QLabel { color: #d2d2d2; }
            QCheckBox, QRadioButton, QPushButton { font-size: 11px; }
            QDoubleSpinBox, QSpinBox {
                background: #202020; border: 1px solid #4a4a4a;
                border-radius: 4px; min-height: 20px; padding: 0px 4px;
            }
            QSlider::groove:horizontal { height: 6px; background: #808080; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: #c7c7c7; border: 1px solid #9b9b9b;
                width: 12px; margin: -4px 0; border-radius: 6px;
            }
            QPushButton {
                background: #353535; border: 1px solid #505050;
                border-radius: 6px; padding: 5px;
            }
            QPushButton:hover { background: #424242; }
            QPushButton#apply_btn {
                background: #8f2f2f; border-color: #b44a4a; font-weight: 700;
            }
            QPushButton#apply_btn:hover { background: #9c3737; }
            QPushButton#live_btn {
                background: #2a3a2a; border: 1px solid #4a6a4a; color: #88bb88;
            }
            QPushButton#live_btn:checked {
                background: #1a5c1a; border: 1px solid #44bb44;
                color: #aaffaa; font-weight: 700;
            }
            QPushButton#live_btn:hover { background: #334433; }
            QPushButton[stepBtn="true"] {
                min-width: 22px; max-width: 22px; padding: 0px;
                font-weight: 700; background: #3b3b3b; border: 1px solid #5b5b5b;
            }
            QPushButton[stepBtn="true"]:hover { background: #4a4a4a; }
            QPushButton[modeBtn="true"] { background: #3c3c3c; border: 1px solid #606060; }
            QPushButton[modeBtn="true"]:checked {
                background: #8b2c2c; border: 1px solid #b34949;
                color: #ffffff; font-weight: 700;
            }
        """)
        self.btn_apply.setObjectName("apply_btn")
        self._apply_ui_scale(1.0)

    def _build_header_controls(self, parent_layout):
        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch(1)
        header.addWidget(QtWidgets.QLabel("UI Scale"))
        self.scale_combo = QtWidgets.QComboBox()
        for pct in (100, 90, 80, 50):
            self.scale_combo.addItem("{}%".format(pct), pct / 100.0)
        self.scale_combo.currentIndexChanged.connect(self._on_ui_scale_changed)
        header.addWidget(self.scale_combo)
        parent_layout.addLayout(header)

    def _build_weighting_section(self, parent_layout):
        section = CollapsibleSection("Weighting", expanded=True)
        section.toggled.connect(self._refresh_dialog_size)
        self._section_widgets.append(section)
        parent_layout.addWidget(section)
        layout = section.content_layout

        mode_row = QtWidgets.QHBoxLayout()
        mode_row.setSpacing(5)
        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.rb_area = QtWidgets.QPushButton("Area")
        self.rb_angle = QtWidgets.QPushButton("Angle")
        self.rb_both = QtWidgets.QPushButton("Area + Angle")

        for btn, mode in [(self.rb_area, "area"), (self.rb_angle, "angle"), (self.rb_both, "both")]:
            btn.setCheckable(True)
            btn.setProperty("modeBtn", True)
            btn.setProperty("mode", mode)
            self.mode_group.addButton(btn)
            mode_row.addWidget(btn)
            btn.toggled.connect(self._on_live_param_changed)

        self.rb_area.setChecked(True)
        layout.addLayout(mode_row)

        self.chk_convex = QtWidgets.QCheckBox("Use Convex Corner Angle")
        self.chk_convex.setChecked(True)
        self.chk_convex.toggled.connect(self._on_live_param_changed)
        layout.addWidget(self.chk_convex)

        self.chk_snap = QtWidgets.QCheckBox("Snap To Largest Face")
        self.chk_snap.setChecked(True)
        self.chk_snap.toggled.connect(self.update_ui_states)
        self.chk_snap.toggled.connect(self._on_live_param_changed)
        layout.addWidget(self.chk_snap)

        self.snap_strength = self._add_slider_row(layout, "Snap Strength", 0.0, 1.0, 0.9, decimals=2)
        self.snap_power = self._add_slider_row(layout, "Snap Power", 1, 128, 15, is_int=True)
        self.blending = self._add_slider_row(layout, "Blending", 0.0, 1.0, 1.0, decimals=2)

    def _build_hard_edges_section(self, parent_layout):
        section = CollapsibleSection("Hard Edge Detection", expanded=True)
        section.toggled.connect(self._refresh_dialog_size)
        self._section_widgets.append(section)
        parent_layout.addWidget(section)
        layout = section.content_layout

        self.chk_keep_existing_hard_edges = QtWidgets.QCheckBox("Keep Existing Hard Edges")
        self.chk_keep_existing_hard_edges.setChecked(True)
        self.chk_keep_existing_hard_edges.setToolTip(
            "Conserve les hard edges déjà présents sur le mesh avant d'appliquer les weighted normals."
        )
        self.chk_keep_existing_hard_edges.toggled.connect(self._on_live_param_changed)
        layout.addWidget(self.chk_keep_existing_hard_edges)

        self.chk_edge_angle = QtWidgets.QCheckBox("By Edge Angle")
        self.chk_edge_angle.setChecked(True)
        self.chk_edge_angle.toggled.connect(self.update_ui_states)
        self.chk_edge_angle.toggled.connect(self._on_live_param_changed)
        layout.addWidget(self.chk_edge_angle)

        self.edge_angle = self._add_slider_row(layout, "Edge Angle", 0.0, 180.0, 80, decimals=1)

        self.chk_harden_uv_seams = QtWidgets.QCheckBox("Harden UV Seams")
        self.chk_harden_uv_seams.setChecked(True)
        self.chk_harden_uv_seams.setToolTip(
            "Detect UV seam edges and apply hard edges on them. The weighted-normal averaging stays driven by the Edge Angle setting."
        )
        self.chk_harden_uv_seams.toggled.connect(self._on_live_param_changed)
        layout.addWidget(self.chk_harden_uv_seams)

    def _build_smoothing_section(self, parent_layout):
        section = CollapsibleSection("Smoothing", expanded=False)
        section.toggled.connect(self._refresh_dialog_size)
        self._section_widgets.append(section)
        parent_layout.addWidget(section)
        layout = section.content_layout

        self.smoothing = self._add_slider_row(layout, "Smoothing", 0.0, 1.0, 0.0, decimals=2)
        self.iterations = self._add_slider_row(layout, "Iterations", 1, 100, 1, is_int=True)

    def _build_display_section(self, parent_layout):
        section = CollapsibleSection("Display Normals", expanded=False)
        section.toggled.connect(self._refresh_dialog_size)
        self._section_widgets.append(section)
        parent_layout.addWidget(section)
        layout = section.content_layout

        self.chk_display = QtWidgets.QCheckBox("Display Normals")
        self.chk_display.setChecked(False)
        self.chk_display.toggled.connect(self.toggle_display)
        layout.addWidget(self.chk_display)

        self.display_length = self._add_slider_row(layout, "Display Length", 0.1, 50.0, 10.0, decimals=2)

    def _add_slider_row(self, parent_layout, label, minimum, maximum, value, is_int=False, decimals=2):
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)

        text = QtWidgets.QLabel(label)
        text.setMinimumWidth(96)
        row.addWidget(text)

        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(1000)
        row.addWidget(slider, 1)

        if is_int:
            spin = QtWidgets.QSpinBox()
            spin.setRange(int(minimum), int(maximum))
            spin.setValue(int(value))
        else:
            spin = QtWidgets.QDoubleSpinBox()
            spin.setDecimals(decimals)
            spin.setRange(float(minimum), float(maximum))
            spin.setValue(float(value))

        minus_btn = QtWidgets.QPushButton("-")
        minus_btn.setProperty("stepBtn", True)
        plus_btn = QtWidgets.QPushButton("+")
        plus_btn.setProperty("stepBtn", True)

        spin.setMinimumWidth(70)
        row.addWidget(minus_btn)
        row.addWidget(spin)
        row.addWidget(plus_btn)
        parent_layout.addLayout(row)

        widget = {
            "slider": slider,
            "spin": spin,
            "min": float(minimum),
            "max": float(maximum),
            "is_int": is_int,
        }

        def spin_to_slider(v):
            ratio = 0.0 if widget["max"] <= widget["min"] else (float(v) - widget["min"]) / (widget["max"] - widget["min"])
            slider.blockSignals(True)
            slider.setValue(int(max(0.0, min(1.0, ratio)) * 1000.0))
            slider.blockSignals(False)

        def slider_to_spin(v):
            ratio = float(v) / 1000.0
            out = widget["min"] + (widget["max"] - widget["min"]) * ratio
            spin.blockSignals(True)
            spin.setValue(int(round(out)) if widget["is_int"] else float(out))
            spin.blockSignals(False)

        spin.valueChanged.connect(spin_to_slider)
        slider.valueChanged.connect(slider_to_spin)
        spin.valueChanged.connect(self._on_live_param_changed)
        slider.valueChanged.connect(self._on_live_param_changed)
        slider.sliderMoved.connect(self._on_live_param_changed)

        def step_spin(delta):
            step = 1 if widget["is_int"] else 10 ** (-spin.decimals())
            spin.setValue(spin.value() + step * delta)

        minus_btn.clicked.connect(lambda: step_spin(-1))
        plus_btn.clicked.connect(lambda: step_spin(1))
        spin_to_slider(spin.value())

        return widget

    # ------------------------------------------------------------------
    # UI state helpers
    # ------------------------------------------------------------------
    def _value(self, control):
        return control["spin"].value()

    def _set_enabled(self, control, enabled):
        control["slider"].setEnabled(enabled)
        control["spin"].setEnabled(enabled)

    def update_ui_states(self, *args):
        use_snap = self.chk_snap.isChecked()
        use_edge = self.chk_edge_angle.isChecked()
        show_norm = self.chk_display.isChecked()
        self._set_enabled(self.snap_strength, use_snap)
        self._set_enabled(self.snap_power, use_snap)
        self._set_enabled(self.edge_angle, use_edge)
        self._set_enabled(self.display_length, show_norm)

    def _on_ui_scale_changed(self, index):
        if index < 0:
            return
        self._apply_ui_scale(float(self.scale_combo.itemData(index)))

    def _apply_ui_scale(self, factor):
        self._ui_scale = max(0.5, min(2.0, float(factor)))
        font = self.font()
        font.setPointSizeF(self._base_font_size * self._ui_scale)
        self.setFont(font)
        self.btn_apply.setMinimumHeight(max(24, int(round(34 * self._ui_scale))))
        self.btn_unfreeze.setMinimumHeight(max(20, int(round(26 * self._ui_scale))))
        self._refresh_dialog_size()

    def _refresh_dialog_size(self, *args):
        self.layout().activate()
        self.adjustSize()

    # =========================================================
    # LIVE PREVIEW
    # =========================================================
    def _on_live_toggled(self, checked):
        self._live_active = checked
        if checked:
            self._live_meshes = self.get_selected_meshes()
            if not self._live_meshes:
                om.MGlobal.displayWarning("Live Preview : sélectionne un mesh d'abord.")
                self.btn_live.setChecked(False)
                self._live_active = False
                return
            self.btn_live.setText("LIVE PREVIEW  (ON)")
            self._live_apply()
        else:
            self._live_timer.stop()
            self._live_meshes = []
            self.btn_live.setText("LIVE PREVIEW")

    def _on_live_param_changed(self, *args):
        if self._live_active:
            self._live_timer.start()

    def _live_apply(self):
        if not self._live_active or not self._live_meshes:
            return
        valid = []
        for dp in self._live_meshes:
            try:
                if dp.isValid():
                    valid.append(dp)
            except Exception:
                pass
        if not valid:
            om.MGlobal.displayWarning("Live Preview : les meshes capturés n'existent plus.")
            self.btn_live.setChecked(False)
            self._live_active = False
            self._live_meshes = []
            self.btn_live.setText("LIVE PREVIEW")
            return
        self._compute_and_apply(valid)

    def _deselect_keep(self, *args):
        if not self._live_meshes:
            self._live_meshes = self.get_selected_meshes()

        cmds.select(clear=True)

        if self._live_meshes:
            om.MGlobal.displayInfo(
                "Deselected — {} mesh(es) still tracked for Apply / Live.".format(len(self._live_meshes))
            )
        else:
            om.MGlobal.displayWarning("Deselect (keep) : aucun mesh à mémoriser.")

    # =========================================================
    # MESH SELECTION HELPERS
    # =========================================================
    def get_selected_meshes(self):
        raw_sel = cmds.ls(sl=True, long=True, flatten=True) or []
        if not raw_sel:
            return []

        obj_sel = cmds.ls(raw_sel, objectsOnly=True, long=True) or []
        candidates = list(raw_sel) + list(obj_sel)

        shape_paths = []
        seen_shapes = set()

        def _is_intermediate(shape):
            try:
                return bool(cmds.getAttr(shape + ".intermediateObject"))
            except Exception:
                return False

        def _add_shape(shape):
            if not shape or shape in seen_shapes:
                return
            try:
                if cmds.nodeType(shape) != "mesh":
                    return
                if _is_intermediate(shape):
                    return
            except Exception:
                return
            seen_shapes.add(shape)
            shape_paths.append(shape)

        for node in candidates:
            base_node = node.split(".")[0] if "." in node else node
            try:
                node_type = cmds.nodeType(base_node)
            except Exception:
                continue

            if node_type == "mesh":
                _add_shape(base_node)
                continue

            direct_shapes = cmds.listRelatives(
                base_node, shapes=True, noIntermediate=True, type="mesh", fullPath=True
            ) or []
            descendant_shapes = cmds.listRelatives(
                base_node, allDescendents=True, shapes=True, noIntermediate=True,
                type="mesh", fullPath=True
            ) or []

            for shape in direct_shapes + descendant_shapes:
                _add_shape(shape)

        meshes = []
        seen_dag = set()
        sel_list = om.MSelectionList()
        for path in shape_paths:
            try:
                sel_list.clear()
                sel_list.add(path)
                dag_path = sel_list.getDagPath(0)
                full_path = dag_path.fullPathName()
                if full_path in seen_dag:
                    continue
                if dag_path.hasFn(om.MFn.kMesh):
                    seen_dag.add(full_path)
                    meshes.append(dag_path)
            except Exception:
                pass

        return meshes

    def _get_effective_meshes(self):
        sel = self.get_selected_meshes()
        if sel:
            return sel
        if self._live_meshes:
            return self._live_meshes
        return []

    # =========================================================
    # EDGE HELPERS
    # =========================================================
    def _mesh_transform_path_from_dag(self, dag_path):
        shape_path = dag_path.fullPathName()
        if "|" in shape_path:
            transform_path = shape_path.rsplit("|", 1)[0]
            if transform_path:
                return transform_path

        parents = cmds.listRelatives(shape_path, parent=True, fullPath=True) or []
        return parents[0] if parents else shape_path

    def _edge_is_smooth(self, edge_it):
        try:
            value = edge_it.isSmooth
            return value() if callable(value) else bool(value)
        except Exception:
            try:
                return bool(edge_it.isSmooth())
            except Exception:
                return True

    def _get_existing_hard_edges(self, dag_path):
        transform_path = self._mesh_transform_path_from_dag(dag_path)
        edge_it = om.MItMeshEdge(dag_path)
        hard_edges = []

        while not edge_it.isDone():
            edge_index = edge_it.index()
            try:
                if not self._edge_is_smooth(edge_it):
                    hard_edges.append("{}.e[{}]".format(transform_path, edge_index))
            except Exception:
                pass
            edge_it.next()

        return hard_edges

    def _get_uv_seam_data(self, dag_path):
        transform_path = self._mesh_transform_path_from_dag(dag_path)
        mesh_fn = om.MFnMesh(dag_path)
        edge_it = om.MItMeshEdge(dag_path)

        seam_edges = []

        while not edge_it.isDone():
            edge_index = edge_it.index()
            connected_faces = list(edge_it.getConnectedFaces())

            if len(connected_faces) == 2:
                v1 = edge_it.vertexId(0)
                v2 = edge_it.vertexId(1)
                uv_pairs = []

                for face_id in connected_faces:
                    try:
                        face_vertices = list(mesh_fn.getPolygonVertices(face_id))
                        local_indices = [i for i, vid in enumerate(face_vertices) if vid == v1 or vid == v2]

                        if len(local_indices) != 2:
                            continue

                        uv_a = mesh_fn.getPolygonUVid(face_id, local_indices[0])
                        uv_b = mesh_fn.getPolygonUVid(face_id, local_indices[1])
                        uv_pairs.append(tuple(sorted((int(uv_a), int(uv_b)))))
                    except Exception:
                        pass

                if len(uv_pairs) == 2 and uv_pairs[0] != uv_pairs[1]:
                    seam_edges.append("{}.e[{}]".format(transform_path, edge_index))

            edge_it.next()

        return seam_edges

    def _harden_edges(self, edge_components):
        if not edge_components:
            return 0

        current_selection = cmds.ls(sl=True, long=True) or []
        clean_edges = sorted(set(edge_components))
        total = 0

        for start in range(0, len(clean_edges), 5000):
            batch = clean_edges[start:start + 5000]
            try:
                cmds.polySoftEdge(batch, angle=0, constructionHistory=False)
                total += len(batch)
            except TypeError:
                cmds.polySoftEdge(batch, a=0, ch=False)
                total += len(batch)
            except Exception as e:
                om.MGlobal.displayWarning("Hard edge apply error: {}".format(e))

        try:
            if current_selection:
                cmds.select(current_selection, r=True)
            else:
                cmds.select(clear=True)
        except Exception:
            pass

        return total

    # =========================================================
    # MATH HELPERS
    # =========================================================
    def safe_normalize(self, vec):
        out = om.MVector(vec)
        if out.length() > 1e-8:
            out.normalize()
            return out
        return om.MVector(0.0, 1.0, 0.0)

    def nlerp(self, a, b, t):
        t = max(0.0, min(1.0, t))
        return self.safe_normalize(a * (1.0 - t) + b * t)

    def get_polygon_area(self, pts, n_verts):
        cross_sum = om.MVector(0.0, 0.0, 0.0)
        for i in range(n_verts):
            cross_sum += pts[i] ^ pts[(i + 1) % n_verts]
        return cross_sum.length() * 0.5

    def get_corner_angle(self, all_pts, mesh_fn, face_id, vertex_id, use_convex):
        verts = list(mesh_fn.getPolygonVertices(face_id))
        if vertex_id not in verts:
            return 0.0
        count = len(verts)
        local_idx = verts.index(vertex_id)
        prev_id = verts[(local_idx - 1) % count]
        next_id = verts[(local_idx + 1) % count]

        p_current = all_pts[vertex_id]
        p_prev = all_pts[prev_id]
        p_next = all_pts[next_id]

        vec_a = p_prev - p_current
        vec_b = p_next - p_current
        if vec_a.length() < 1e-8 or vec_b.length() < 1e-8:
            return 0.0

        vec_a = self.safe_normalize(vec_a)
        vec_b = self.safe_normalize(vec_b)
        dotv = max(-1.0, min(1.0, vec_a * vec_b))
        angle = math.acos(dotv)

        if use_convex:
            try:
                face_normal = self.safe_normalize(om.MVector(mesh_fn.getPolygonNormal(face_id, om.MSpace.kObject)))
                cross_vec = vec_a ^ vec_b
                if (cross_vec * face_normal) < 0.0:
                    angle = max(0.0, (2.0 * math.pi) - angle)
                    if angle > math.pi:
                        angle = (2.0 * math.pi) - angle
            except Exception:
                pass

        return max(0.0, angle)

    def get_weight_mode(self):
        checked = self.mode_group.checkedButton()
        return checked.property("mode") if checked else "area"

    def get_face_weight(self, all_pts, mesh_fn, face_id, vertex_id, weight_mode, use_convex):
        verts = mesh_fn.getPolygonVertices(face_id)
        pts = [all_pts[v] for v in verts]
        area = self.get_polygon_area(pts, len(verts))
        angle = self.get_corner_angle(all_pts, mesh_fn, face_id, vertex_id, use_convex)
        if weight_mode == "area":
            return area
        if weight_mode == "angle":
            return angle
        return area * angle

    def build_face_cache(self, mesh_fn):
        face_normals = {}
        for f_id in range(mesh_fn.numPolygons):
            try:
                face_normals[f_id] = self.safe_normalize(om.MVector(mesh_fn.getPolygonNormal(f_id, om.MSpace.kObject)))
            except Exception:
                pass
        return face_normals

    def apply_power_snap_weight(self, weight, max_weight, snap_strength, snap_power):
        if max_weight <= 1e-8:
            return weight
        ratio = max(0.0, min(1.0, weight / max_weight))
        exponent = 1.0 + max(0.0, min(1.0, snap_strength)) * float(snap_power)
        return weight * (ratio ** exponent)

    def get_filtered_neighbor_faces(self, target_face_id, connected_faces, face_normals, use_edge_angle, limit_dot):
        if not use_edge_angle:
            return list(connected_faces)

        target_normal = face_normals.get(target_face_id)
        if target_normal is None:
            return [target_face_id]

        valid_faces = [
            fid for fid in connected_faces
            if face_normals.get(fid) is not None and (target_normal * face_normals[fid]) >= limit_dot
        ]
        return valid_faces or [target_face_id]

    def apply_soft_smoothing(self, result_normal, ref_normal, smoothing, iterations):
        if smoothing <= 0.0 or iterations <= 1:
            return self.safe_normalize(result_normal)
        out = om.MVector(result_normal)
        blend_step = max(0.0, min(1.0, smoothing)) * 0.15
        for _ in range(iterations - 1):
            out = self.nlerp(out, ref_normal, blend_step)
        return self.safe_normalize(out)

    # =========================================================
    # CORE COMPUTATION
    # =========================================================
    def _compute_and_apply(self, meshes):
        weight_mode = self.get_weight_mode()
        use_convex = self.chk_convex.isChecked()
        use_snap = self.chk_snap.isChecked()
        snap_strength = self._value(self.snap_strength)
        snap_power = self._value(self.snap_power)
        blending = self._value(self.blending)
        keep_existing_hard_edges = self.chk_keep_existing_hard_edges.isChecked()
        use_edge_angle = self.chk_edge_angle.isChecked()
        edge_angle_lim = self._value(self.edge_angle)
        harden_uv_seams = self.chk_harden_uv_seams.isChecked()
        smoothing = self._value(self.smoothing)
        iterations = self._value(self.iterations)

        limit_dot = math.cos(math.radians(edge_angle_lim)) - 1e-5

        preserved_hard_edges = []
        if keep_existing_hard_edges:
            for dag_path in meshes:
                try:
                    preserved_hard_edges.extend(self._get_existing_hard_edges(dag_path))
                except Exception as e:
                    om.MGlobal.displayWarning(
                        "Existing hard edge detection error on {}: {}".format(dag_path.fullPathName(), e)
                    )

        uv_seam_edges = []
        if harden_uv_seams:
            for dag_path in meshes:
                try:
                    uv_seam_edges.extend(self._get_uv_seam_data(dag_path))
                except Exception as e:
                    om.MGlobal.displayWarning(
                        "UV seam detection error on {}: {}".format(dag_path.fullPathName(), e)
                    )

        mesh_paths = [dp.fullPathName() for dp in meshes]
        try:
            cmds.polyNormalPerVertex(mesh_paths, unFreezeNormal=True)
        except Exception as e:
            om.MGlobal.displayWarning("Unfreeze error: {}".format(e))

        for dag_path in meshes:
            mesh_fn = om.MFnMesh(dag_path)
            face_normals = self.build_face_cache(mesh_fn)
            raw_pts = mesh_fn.getPoints(om.MSpace.kObject)
            all_pts = [om.MVector(p) for p in raw_pts]

            vert_iter = om.MItMeshVertex(dag_path)
            new_normals = []
            face_ids = []
            vert_ids = []

            while not vert_iter.isDone():
                v_id = vert_iter.index()
                connected_faces = list(vert_iter.getConnectedFaces())

                if not connected_faces:
                    vert_iter.next()
                    continue

                base_weights = {}
                for f_id in connected_faces:
                    try:
                        base_weights[f_id] = self.get_face_weight(all_pts, mesh_fn, f_id, v_id, weight_mode, use_convex)
                    except Exception:
                        base_weights[f_id] = 0.0

                for current_face_id in connected_faces:
                    current_face_normal = face_normals.get(current_face_id)
                    if current_face_normal is None:
                        continue

                    valid_faces = self.get_filtered_neighbor_faces(
                        current_face_id, connected_faces, face_normals, use_edge_angle, limit_dot
                    )

                    max_weight = max((base_weights.get(fid, 0.0) for fid in valid_faces), default=0.0)
                    weighted_sum = om.MVector(0.0, 0.0, 0.0)
                    ref_sum = om.MVector(0.0, 0.0, 0.0)

                    for other_face_id in valid_faces:
                        other_normal = face_normals.get(other_face_id)
                        if other_normal is None:
                            continue
                        base_w = base_weights.get(other_face_id, 0.0)
                        if base_w <= 1e-8:
                            continue
                        final_w = self.apply_power_snap_weight(base_w, max_weight, snap_strength, snap_power) if use_snap else base_w
                        weighted_sum += other_normal * final_w
                        ref_sum += other_normal

                    result_normal = self.safe_normalize(weighted_sum) if weighted_sum.length() > 1e-8 else om.MVector(current_face_normal)

                    if ref_sum.length() > 1e-8:
                        result_normal = self.apply_soft_smoothing(result_normal, self.safe_normalize(ref_sum), smoothing, iterations)

                    try:
                        current_fv_normal = om.MVector(mesh_fn.getFaceVertexNormal(current_face_id, v_id, om.MSpace.kObject))
                    except Exception:
                        current_fv_normal = om.MVector(result_normal)

                    out_normal = self.nlerp(current_fv_normal, result_normal, blending)
                    new_normals.append(self.safe_normalize(out_normal))
                    face_ids.append(current_face_id)
                    vert_ids.append(v_id)

                vert_iter.next()

            if new_normals:
                try:
                    mesh_fn.setFaceVertexNormals(new_normals, face_ids, vert_ids, om.MSpace.kObject)
                except Exception as e:
                    om.MGlobal.displayWarning(
                        "Cannot apply normals on {} : {}".format(dag_path.fullPathName(), e)
                    )

        edges_to_harden = []
        if keep_existing_hard_edges and preserved_hard_edges:
            edges_to_harden.extend(preserved_hard_edges)
        if harden_uv_seams and uv_seam_edges:
            edges_to_harden.extend(uv_seam_edges)

        if edges_to_harden:
            self._harden_edges(edges_to_harden)

    # =========================================================
    # PUBLIC ACTIONS
    # =========================================================
    def unfreeze_normals(self, *args):
        meshes = self._get_effective_meshes()
        if not meshes:
            om.MGlobal.displayWarning("Sélectionne un mesh.")
            return
        mesh_paths = [dp.fullPathName() for dp in meshes]
        try:
            cmds.polyNormalPerVertex(mesh_paths, unFreezeNormal=True)
            om.MGlobal.displayInfo("Normals déverrouillées.")
        except Exception as e:
            om.MGlobal.displayWarning("Erreur: {}".format(e))

    def toggle_display(self, *args):
        self.update_ui_states()
        val = self.chk_display.isChecked()
        length = self._value(self.display_length)
        meshes = self._get_effective_meshes()
        if not meshes:
            return
        mesh_paths = [dp.fullPathName() for dp in meshes]
        if val:
            cmds.polyOptions(mesh_paths, displayNormal=True, sizeNormal=length)
        else:
            cmds.polyOptions(mesh_paths, displayNormal=False)

    def apply_normals(self, *args):
        meshes = self._get_effective_meshes()
        if not meshes:
            om.MGlobal.displayWarning("Sélectionne un maillage polygonal d'abord !")
            return

        cmds.undoInfo(openChunk=True, chunkName="WeightedNormalsPro")
        try:
            self._compute_and_apply(meshes)
            om.MGlobal.displayInfo("Weighted Normals Pro appliquées.")
            if self.chk_display.isChecked():
                self.toggle_display()
        finally:
            cmds.undoInfo(closeChunk=True)

    def closeEvent(self, event):
        self._live_timer.stop()
        self._live_active = False
        super(WeightedNormalsTool, self).closeEvent(event)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def show_weighted_normals_tool():
    app = QtWidgets.QApplication.instance()

    if app:
        for widget in app.allWidgets():
            try:
                if widget.objectName() == WeightedNormalsTool.WINDOW_NAME:
                    widget.close()
                    widget.deleteLater()
            except Exception:
                pass

    tool = WeightedNormalsTool(parent=maya_main_window())
    tool.show()
    return tool


show_weighted_normals_tool()