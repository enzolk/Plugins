# ELK_META {"label": "Select Faces By Material", "short_name": "MatSel", "tooltip": "Sélectionne toutes les faces utilisant un matériau donné.", "source": "python", "icon_svg": "palette.svg", "icon_color": "#f2c94c"}
import maya.cmds as cmds
import maya.api.OpenMaya as om2

# Qt import compatible Maya 2018 -> 2025
try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from shiboken6 import wrapInstance
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

import maya.OpenMayaUI as omui


def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def _warn(msg):
    cmds.warning("[MaterialSelector] " + str(msg))


class MaterialRowWidget(QtWidgets.QWidget):
    ACTIONS = ["Do Nothing", "To Delete", "To Mirror"]

    def __init__(self, material_name, swatch_icon=None, parent=None):
        super(MaterialRowWidget, self).__init__(parent)
        self.material_name = material_name

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(8)

        self.icon_lbl = QtWidgets.QLabel()
        self.icon_lbl.setFixedSize(18, 18)
        if swatch_icon:
            pix = swatch_icon.pixmap(14, 14)
            self.icon_lbl.setPixmap(pix)
        lay.addWidget(self.icon_lbl)

        self.name_lbl = QtWidgets.QLabel(material_name)
        self.name_lbl.setMinimumWidth(240)
        self.name_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        lay.addWidget(self.name_lbl, 1)

        self.action_combo = QtWidgets.QComboBox()
        self.action_combo.addItems(self.ACTIONS)
        self.action_combo.setFixedWidth(120)
        lay.addWidget(self.action_combo)

        self.pair_edit = QtWidgets.QLineEdit()
        self.pair_edit.setPlaceholderText("Pair (A)")
        self.pair_edit.setFixedWidth(70)
        self.pair_edit.setMaxLength(2)
        lay.addWidget(self.pair_edit)

    def get_action(self):
        return self.action_combo.currentText()

    def set_action(self, action_text):
        idx = self.action_combo.findText(action_text)
        if idx >= 0:
            self.action_combo.setCurrentIndex(idx)

    def get_pair(self):
        t = (self.pair_edit.text() or "").strip()
        if not t:
            return ""
        return t[0].upper()

    def set_pair(self, pair_text):
        t = (pair_text or "").strip()
        self.pair_edit.setText(t[:1].upper() if t else "")


class MaterialSelectorUI(QtWidgets.QDialog):
    def __init__(self, parent=get_maya_main_window()):
        super(MaterialSelectorUI, self).__init__(parent)

        self.setWindowTitle("Material Selector")
        self.setMinimumWidth(720)
        self.setMinimumHeight(950)

        self._script_job = None
        self._swatch_cache = {}
        self._action_cache = {}

        self.build_ui()
        self.create_connections()
        self.install_script_job()
        self.refresh_materials()

    # -------------------------
    # UI
    # -------------------------
    def build_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Sorting
        sort_group = QtWidgets.QGroupBox("Sorting")
        sort_layout = QtWidgets.QVBoxLayout(sort_group)
        sort_layout.setContentsMargins(10, 10, 10, 10)
        sort_layout.setSpacing(8)

        sort_layout.addWidget(QtWidgets.QLabel("Sort materials list by:"))
        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems([
            "Name (A ? Z)",
            "Name (Z ? A)",
            "Polygons (Low ? High)",
            "Polygons (High ? Low)",
        ])
        sort_layout.addWidget(self.sort_combo)

        # Symmetry tools (kept)
        sym_group = QtWidgets.QGroupBox("Side selection / Symmetry check (Object space)")
        sym_layout = QtWidgets.QGridLayout(sym_group)
        sym_layout.setContentsMargins(10, 10, 10, 10)
        sym_layout.setHorizontalSpacing(10)
        sym_layout.setVerticalSpacing(8)

        self.axis_combo = QtWidgets.QComboBox()
        self.axis_combo.addItems(["X", "Y", "Z"])

        self.side_combo = QtWidgets.QComboBox()
        self.side_combo.addItems(["+", "-"])

        self.side_tol_spin = QtWidgets.QDoubleSpinBox()
        self.side_tol_spin.setDecimals(6)
        self.side_tol_spin.setRange(0.0, 100000.0)
        self.side_tol_spin.setSingleStep(0.001)
        self.side_tol_spin.setValue(0.0001)

        self.match_tol_spin = QtWidgets.QDoubleSpinBox()
        self.match_tol_spin.setDecimals(6)
        self.match_tol_spin.setRange(0.0, 100000.0)
        self.match_tol_spin.setSingleStep(0.001)
        self.match_tol_spin.setValue(0.001)

        sym_layout.addWidget(QtWidgets.QLabel("Axis:"), 0, 0)
        sym_layout.addWidget(self.axis_combo, 0, 1)
        sym_layout.addWidget(QtWidgets.QLabel("Side (for select):"), 0, 2)
        sym_layout.addWidget(self.side_combo, 0, 3)

        sym_layout.addWidget(QtWidgets.QLabel("Side tolerance:"), 1, 0)
        sym_layout.addWidget(self.side_tol_spin, 1, 1, 1, 3)

        sym_layout.addWidget(QtWidgets.QLabel("Match tolerance (mirror):"), 2, 0)
        sym_layout.addWidget(self.match_tol_spin, 2, 1, 1, 3)

        self.select_side_btn = QtWidgets.QPushButton("Select Faces (Side)")
        self.find_sym_mismatch_btn = QtWidgets.QPushButton("Find Symmetry Mismatch")

        sym_layout.addWidget(self.select_side_btn, 3, 0, 1, 4)
        sym_layout.addWidget(self.find_sym_mismatch_btn, 4, 0, 1, 4)

        # Batch actions
        batch_group = QtWidgets.QGroupBox("Batch Actions (Delete / Mirror by Pair)")
        batch_layout = QtWidgets.QVBoxLayout(batch_group)
        batch_layout.setContentsMargins(10, 10, 10, 10)
        batch_layout.setSpacing(10)

        # --- polyMirrorFace settings
        pm_group = QtWidgets.QGroupBox("polyMirrorFace settings")
        pm_layout = QtWidgets.QGridLayout(pm_group)
        pm_layout.setContentsMargins(10, 10, 10, 10)
        pm_layout.setHorizontalSpacing(10)
        pm_layout.setVerticalSpacing(8)

        self.pm_cutMesh = QtWidgets.QComboBox()
        self.pm_cutMesh.addItems(["0", "1"])
        self.pm_cutMesh.setCurrentText("1")

        self.pm_axis = QtWidgets.QComboBox()
        self.pm_axis.addItems(["0 (X)", "1 (Y)", "2 (Z)"])
        self.pm_axis.setCurrentIndex(0)

        self.pm_axisDir = QtWidgets.QComboBox()
        self.pm_axisDir.addItems(["0", "1"])
        self.pm_axisDir.setCurrentText("0")

        self.pm_mergeMode = QtWidgets.QComboBox()
        self.pm_mergeMode.addItems(["0", "1", "2", "3"])
        self.pm_mergeMode.setCurrentText("3")

        self.pm_mergeThresholdType = QtWidgets.QComboBox()
        self.pm_mergeThresholdType.addItems(["0", "1"])
        self.pm_mergeThresholdType.setCurrentText("0")

        self.pm_mergeThreshold = QtWidgets.QDoubleSpinBox()
        self.pm_mergeThreshold.setDecimals(6)
        self.pm_mergeThreshold.setRange(0.0, 100000.0)
        self.pm_mergeThreshold.setSingleStep(0.001)
        self.pm_mergeThreshold.setValue(0.001)

        self.pm_mirrorAxis = QtWidgets.QComboBox()
        self.pm_mirrorAxis.addItems(["0", "1", "2"])
        self.pm_mirrorAxis.setCurrentText("1")

        self.pm_mirrorPosition = QtWidgets.QDoubleSpinBox()
        self.pm_mirrorPosition.setDecimals(6)
        self.pm_mirrorPosition.setRange(-100000.0, 100000.0)
        self.pm_mirrorPosition.setSingleStep(0.1)
        self.pm_mirrorPosition.setValue(0.0)

        self.pm_smoothingAngle = QtWidgets.QDoubleSpinBox()
        self.pm_smoothingAngle.setDecimals(3)
        self.pm_smoothingAngle.setRange(0.0, 180.0)
        self.pm_smoothingAngle.setSingleStep(1.0)
        self.pm_smoothingAngle.setValue(30.0)

        self.pm_flipUVs = QtWidgets.QComboBox()
        self.pm_flipUVs.addItems(["0", "1"])
        self.pm_flipUVs.setCurrentText("0")

        self.pm_ch = QtWidgets.QComboBox()
        self.pm_ch.addItems(["0", "1"])
        self.pm_ch.setCurrentText("1")

        pm_layout.addWidget(QtWidgets.QLabel("cutMesh:"), 0, 0)
        pm_layout.addWidget(self.pm_cutMesh, 0, 1)
        pm_layout.addWidget(QtWidgets.QLabel("axis:"), 0, 2)
        pm_layout.addWidget(self.pm_axis, 0, 3)

        pm_layout.addWidget(QtWidgets.QLabel("axisDirection:"), 1, 0)
        pm_layout.addWidget(self.pm_axisDir, 1, 1)
        pm_layout.addWidget(QtWidgets.QLabel("mergeMode:"), 1, 2)
        pm_layout.addWidget(self.pm_mergeMode, 1, 3)

        pm_layout.addWidget(QtWidgets.QLabel("mergeThresholdType:"), 2, 0)
        pm_layout.addWidget(self.pm_mergeThresholdType, 2, 1)
        pm_layout.addWidget(QtWidgets.QLabel("mergeThreshold:"), 2, 2)
        pm_layout.addWidget(self.pm_mergeThreshold, 2, 3)

        pm_layout.addWidget(QtWidgets.QLabel("mirrorAxis:"), 3, 0)
        pm_layout.addWidget(self.pm_mirrorAxis, 3, 1)
        pm_layout.addWidget(QtWidgets.QLabel("mirrorPosition:"), 3, 2)
        pm_layout.addWidget(self.pm_mirrorPosition, 3, 3)

        pm_layout.addWidget(QtWidgets.QLabel("smoothingAngle:"), 4, 0)
        pm_layout.addWidget(self.pm_smoothingAngle, 4, 1)
        pm_layout.addWidget(QtWidgets.QLabel("flipUVs:"), 4, 2)
        pm_layout.addWidget(self.pm_flipUVs, 4, 3)

        pm_layout.addWidget(QtWidgets.QLabel("ch:"), 5, 0)
        pm_layout.addWidget(self.pm_ch, 5, 1)

        batch_layout.addWidget(pm_group)

        merge_group = QtWidgets.QGroupBox("Final border merge")
        merge_layout = QtWidgets.QGridLayout(merge_group)
        merge_layout.setContentsMargins(10, 10, 10, 10)
        merge_layout.setHorizontalSpacing(10)
        merge_layout.setVerticalSpacing(8)

        self.final_merge_thresh = QtWidgets.QDoubleSpinBox()
        self.final_merge_thresh.setDecimals(6)
        self.final_merge_thresh.setRange(0.0, 100000.0)
        self.final_merge_thresh.setSingleStep(0.001)
        self.final_merge_thresh.setValue(0.001)

        merge_layout.addWidget(QtWidgets.QLabel("polyMergeVertex threshold:"), 0, 0)
        merge_layout.addWidget(self.final_merge_thresh, 0, 1)

        batch_layout.addWidget(merge_group)

        self.apply_actions_btn = QtWidgets.QPushButton("Apply Actions (Delete / Mirror + Merge Borders)")
        self.apply_actions_btn.setMinimumHeight(44)
        batch_layout.addWidget(self.apply_actions_btn)

        # Material list
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list_widget.setUniformItemSizes(False)
        self.list_widget.setSpacing(2)

        # Buttons bottom
        btn_layout = QtWidgets.QVBoxLayout()
        btn_layout.setSpacing(8)

        self.refresh_btn = QtWidgets.QPushButton("Refresh Materials")
        self.select_faces_btn = QtWidgets.QPushButton("Select Faces")
        self.select_faces_edges_btn = QtWidgets.QPushButton("Select Faces and Convert to Edges")

        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.select_faces_btn)
        btn_layout.addWidget(self.select_faces_edges_btn)

        main_layout.addWidget(sort_group)
        main_layout.addWidget(sym_group)
        main_layout.addWidget(batch_group)
        main_layout.addWidget(self.list_widget, 1)
        main_layout.addLayout(btn_layout)

    def create_connections(self):
        self.refresh_btn.clicked.connect(self.refresh_materials)
        self.select_faces_btn.clicked.connect(self.on_select_faces_clicked)
        self.select_faces_edges_btn.clicked.connect(self.on_select_faces_and_convert_edges_clicked)

        self.select_side_btn.clicked.connect(self.on_select_faces_side_clicked)
        self.find_sym_mismatch_btn.clicked.connect(self.on_find_symmetry_mismatch_clicked)

        self.apply_actions_btn.clicked.connect(self.on_apply_actions_clicked)
        self.sort_combo.currentIndexChanged.connect(self.refresh_materials)

    # -------------------------
    # scriptJob
    # -------------------------
    def install_script_job(self):
        if self._script_job and cmds.scriptJob(exists=self._script_job):
            try:
                cmds.scriptJob(kill=self._script_job, force=True)
            except Exception:
                pass
        self._script_job = cmds.scriptJob(event=("SelectionChanged", self.refresh_materials), protected=True)

    def closeEvent(self, event):
        try:
            if self._script_job and cmds.scriptJob(exists=self._script_job):
                cmds.scriptJob(kill=self._script_job, force=True)
        except Exception:
            pass
        super(MaterialSelectorUI, self).closeEvent(event)

    # -------------------------
    # Sorting
    # -------------------------
    def sort_items(self, items):
        mode = self.sort_combo.currentText()
        if mode == "Name (A ? Z)":
            return sorted(items, key=lambda x: x["name"].lower())
        if mode == "Name (Z ? A)":
            return sorted(items, key=lambda x: x["name"].lower(), reverse=True)
        if mode == "Polygons (Low ? High)":
            return sorted(items, key=lambda x: (x["count"], x["name"].lower()))
        if mode == "Polygons (High ? Low)":
            return sorted(items, key=lambda x: (-x["count"], x["name"].lower()))
        return sorted(items, key=lambda x: x["name"].lower())

    # -------------------------
    # Swatch
    # -------------------------
    def get_material_base_color(self, material):
        candidates = ["baseColor", "base_color", "base_color_color", "color"]
        for attr in candidates:
            if cmds.attributeQuery(attr, node=material, exists=True):
                try:
                    val = cmds.getAttr("{}.{}".format(material, attr))
                    if isinstance(val, (list, tuple)) and len(val) > 0:
                        rgb = val[0]
                        if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
                            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
                            return (max(0.0, min(1.0, r)),
                                    max(0.0, min(1.0, g)),
                                    max(0.0, min(1.0, b)))
                except Exception:
                    pass
        return (0.5, 0.5, 0.5)

    def make_swatch_icon(self, rgb, size=14):
        key = (round(rgb[0], 3), round(rgb[1], 3), round(rgb[2], 3), size)
        if key in self._swatch_cache:
            return self._swatch_cache[key]

        pix = QtGui.QPixmap(size, size)
        pix.fill(QtCore.Qt.transparent)

        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)

        color = QtGui.QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40)))
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()

        icon = QtGui.QIcon(pix)
        self._swatch_cache[key] = icon
        return icon

    # -------------------------
    # Refresh list (kept)
    # -------------------------
    def refresh_materials(self, *args):
        self.list_widget.clear()

        materials = cmds.ls(materials=True) or []
        selected_objects = cmds.ls(selection=True, type="transform") or []

        if not selected_objects:
            items = [{"name": m, "count": 0, "display": m, "color": self.get_material_base_color(m)}
                     for m in materials]
            items = self.sort_items(items)
            for it in items:
                self._add_material_row(it["name"], it["display"], it["color"])
            return

        material_face_counts = {m: 0 for m in materials}

        for obj in selected_objects:
            shapes = cmds.listRelatives(obj, shapes=True, type='mesh', fullPath=True) or []
            if not shapes:
                continue

            for material in materials:
                shading_groups = cmds.listConnections(material, type='shadingEngine') or []
                for sg in shading_groups:
                    faces = cmds.sets(sg, query=True) or []
                    for face in faces:
                        if face.startswith(obj):
                            material_face_counts[material] += self._count_faces_from_component(face)

        items = []
        for m, count in material_face_counts.items():
            rgb = self.get_material_base_color(m)
            items.append({"name": m, "count": int(count),
                          "display": "{} ({} polygons)".format(m, int(count)),
                          "color": rgb})
        items = self.sort_items(items)
        for it in items:
            self._add_material_row(it["name"], it["display"], it["color"])

    def _count_faces_from_component(self, face_component):
        # face_component can be "obj.f[12]" or "obj.f[3:10]"
        try:
            face_part = face_component.split("[")[1].split("]")[0]
        except Exception:
            return 0
        if ":" in face_part:
            a, b = face_part.split(":")
            return int(b) - int(a) + 1
        return 1

    def _add_material_row(self, material_name, display_text, color_rgb):
        cached = self._action_cache.get(material_name, {"action": "Do Nothing", "pair": ""})
        icon = self.make_swatch_icon(color_rgb)

        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(QtCore.QSize(10, 28))
        item.setData(QtCore.Qt.UserRole, material_name)
        self.list_widget.addItem(item)

        row = MaterialRowWidget(material_name, swatch_icon=icon)
        row.name_lbl.setText(display_text)
        row.set_action(cached.get("action", "Do Nothing"))
        row.set_pair(cached.get("pair", ""))

        def _on_action_changed(_idx):
            self._action_cache.setdefault(material_name, {})
            self._action_cache[material_name]["action"] = row.get_action()

        def _on_pair_changed(_text):
            self._action_cache.setdefault(material_name, {})
            self._action_cache[material_name]["pair"] = row.get_pair()

        row.action_combo.currentIndexChanged.connect(_on_action_changed)
        row.pair_edit.textChanged.connect(_on_pair_changed)

        self.list_widget.setItemWidget(item, row)

        self._action_cache.setdefault(material_name, {})
        self._action_cache[material_name]["action"] = row.get_action()
        self._action_cache[material_name]["pair"] = row.get_pair()

    # -------------------------
    # State helpers
    # -------------------------
    def get_selected_material_names(self):
        mats = []
        for item in self.list_widget.selectedItems():
            mat_name = item.data(QtCore.Qt.UserRole)
            if mat_name:
                mats.append(mat_name)
        return mats

    def get_selected_transforms(self):
        return cmds.ls(selection=True, type="transform") or []

    def get_all_material_rows_state(self):
        state = dict(self._action_cache)
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            mat = it.data(QtCore.Qt.UserRole)
            w = self.list_widget.itemWidget(it)
            if mat and w:
                state.setdefault(mat, {})
                state[mat]["action"] = w.get_action()
                state[mat]["pair"] = w.get_pair()
        return state

    # -------------------------
    # OpenMaya mesh/shader helpers
    # -------------------------
    def _get_mesh_dagpath(self, transform):
        sel = om2.MSelectionList()
        try:
            sel.add(transform)
        except Exception:
            return None

        dag = sel.getDagPath(0)
        if not dag.isValid():
            return None

        fnDag = om2.MFnDagNode(dag)
        for i in range(fnDag.childCount()):
            child = fnDag.child(i)
            if child.hasFn(om2.MFn.kMesh):
                return om2.MDagPath.getAPathTo(child)
        return None

    def _get_shader_assignment_cache(self, mesh_fn, material):
        material_sgs = set(cmds.listConnections(material, type="shadingEngine") or [])
        sgs, face_shader_ids = mesh_fn.getConnectedShaders(0)

        sg_names = []
        for sg_obj in sgs:
            try:
                sg_names.append(om2.MFnDependencyNode(sg_obj).name())
            except Exception:
                sg_names.append("")

        material_sg_indices = {i for i, name in enumerate(sg_names) if name in material_sgs}
        return face_shader_ids, material_sg_indices

    def _face_has_material(self, face_id, face_shader_ids, material_sg_indices):
        if face_id < 0 or face_id >= len(face_shader_ids):
            return False
        return face_shader_ids[face_id] in material_sg_indices

    def _collect_faces_for_material_on_obj(self, obj, material):
        mesh_path = self._get_mesh_dagpath(obj)
        if not mesh_path:
            return []

        mesh_fn = om2.MFnMesh(mesh_path)
        face_shader_ids, material_sg_indices = self._get_shader_assignment_cache(mesh_fn, material)

        out = []
        for fid in range(mesh_fn.numPolygons):
            if self._face_has_material(fid, face_shader_ids, material_sg_indices):
                out.append("{}.f[{}]".format(obj, fid))
        return out

    def _get_sg_for_material(self, material):
        sgs = cmds.listConnections(material, type="shadingEngine") or []
        # pick first non-initial if possible
        for sg in sgs:
            if sg != "initialShadingGroup":
                return sg
        return sgs[0] if sgs else None

    # -------------------------
    # Select Faces (FIX)
    # -------------------------
    def on_select_faces_clicked(self, *args):
        selected_materials = self.get_selected_material_names()
        selected_objects = self.get_selected_transforms()

        if not selected_objects:
            cmds.warning("Please select at least one object.")
            return
        if not selected_materials:
            cmds.warning("Please select at least one material in the list.")
            return

        all_faces = []
        for obj in selected_objects:
            if not self._get_mesh_dagpath(obj):
                continue
            for material in selected_materials:
                all_faces.extend(self._collect_faces_for_material_on_obj(obj, material))

        all_faces = cmds.ls(all_faces, fl=True) or []
        if not all_faces:
            cmds.warning("No faces with the selected materials found on the selected objects.")
            return

        cmds.selectMode(component=True)
        cmds.selectType(facet=True)
        cmds.select(all_faces, replace=True)

    def on_select_faces_and_convert_edges_clicked(self, *args):
        self.on_select_faces_clicked(*args)
        cmds.ConvertSelectionToEdgePerimeter()

    # -------------------------
    # Side selection (kept)
    # -------------------------
    def _axis_index(self, axis):
        axis = axis.upper()
        return {"X": 0, "Y": 1, "Z": 2}.get(axis, 0)

    def _classify_side(self, v, tol):
        if v > tol:
            return "+"
        if v < -tol:
            return "-"
        return "0"

    def _compute_face_center_object_space(self, mesh_fn, face_id, points_obj):
        vtx_ids = mesh_fn.getPolygonVertices(face_id)
        if not vtx_ids:
            return om2.MPoint(0.0, 0.0, 0.0)
        cx = cy = cz = 0.0
        count = float(len(vtx_ids))
        for vid in vtx_ids:
            p = points_obj[vid]
            cx += p.x
            cy += p.y
            cz += p.z
        return om2.MPoint(cx / count, cy / count, cz / count)

    def on_select_faces_side_clicked(self, *args):
        selected_materials = self.get_selected_material_names()
        selected_objects = self.get_selected_transforms()

        if not selected_objects:
            cmds.warning("Please select at least one object.")
            return
        if not selected_materials:
            cmds.warning("Please select at least one material in the list.")
            return

        axis = self.axis_combo.currentText()
        side = self.side_combo.currentText()
        tol = float(self.side_tol_spin.value())
        axis_idx = self._axis_index(axis)

        faces_to_select = []
        for obj in selected_objects:
            mesh_path = self._get_mesh_dagpath(obj)
            if not mesh_path:
                continue
            mesh_fn = om2.MFnMesh(mesh_path)
            points_obj = mesh_fn.getPoints(om2.MSpace.kObject)

            for material in selected_materials:
                face_shader_ids, material_sg_indices = self._get_shader_assignment_cache(mesh_fn, material)
                for fid in range(mesh_fn.numPolygons):
                    if not self._face_has_material(fid, face_shader_ids, material_sg_indices):
                        continue
                    c = self._compute_face_center_object_space(mesh_fn, fid, points_obj)
                    v = (c.x, c.y, c.z)[axis_idx]
                    if self._classify_side(v, tol) == side:
                        faces_to_select.append("{}.f[{}]".format(obj, fid))

        faces_to_select = cmds.ls(faces_to_select, fl=True) or []
        if not faces_to_select:
            cmds.warning("No faces found for the chosen material(s) on that side.")
            return

        cmds.selectMode(component=True)
        cmds.selectType(facet=True)
        cmds.select(faces_to_select, replace=True)

    # -------------------------
    # Symmetry mismatch (pas inclus ici, garde ta version si tu l'avais)
    # -------------------------
    def on_find_sym_mismatch_clicked_stub(self, *args):
        cmds.warning("Not implemented in this paste. (Keep your existing mismatch function if you had one.)")

    def on_find_sym_mismatch_clicked(self, *args):
        # keep button working if you didn't paste mismatch implementation
        self.on_find_sym_mismatch_clicked_stub(*args)

    # -------------------------
    # polyMirrorFace exact settings
    # -------------------------
    def _get_polyMirrorFace_settings(self):
        axis = int(self.pm_axis.currentText().split()[0])  # "0 (X)" -> 0
        return {
            "cutMesh": int(self.pm_cutMesh.currentText()),
            "axis": axis,
            "axisDirection": int(self.pm_axisDir.currentText()),
            "mergeMode": int(self.pm_mergeMode.currentText()),
            "mergeThresholdType": int(self.pm_mergeThresholdType.currentText()),
            "mergeThreshold": float(self.pm_mergeThreshold.value()),
            "mirrorAxis": int(self.pm_mirrorAxis.currentText()),
            "mirrorPosition": float(self.pm_mirrorPosition.value()),
            "smoothingAngle": float(self.pm_smoothingAngle.value()),
            "flipUVs": int(self.pm_flipUVs.currentText()),
            "ch": int(self.pm_ch.currentText()),
        }

    def _poly_mirror_faces_exact(self, faces, pm):
        """
        Runs polyMirrorFace with exact flags from UI.
        Returns created faces (best-effort).
        """
        if not faces:
            return []

        obj = faces[0].split(".f[")[0]
        shapes = cmds.listRelatives(obj, shapes=True, type="mesh", fullPath=True) or []
        shape = shapes[0] if shapes else None

        before_count = None
        if shape:
            try:
                before_count = cmds.polyEvaluate(shape, face=True)
            except Exception:
                before_count = None

        cmds.select(faces, r=True)

        try:
            cmds.polyMirrorFace(
                cutMesh=pm["cutMesh"],
                axis=pm["axis"],
                axisDirection=pm["axisDirection"],
                mergeMode=pm["mergeMode"],
                mergeThresholdType=pm["mergeThresholdType"],
                mergeThreshold=pm["mergeThreshold"],
                mirrorAxis=pm["mirrorAxis"],
                mirrorPosition=pm["mirrorPosition"],
                smoothingAngle=pm["smoothingAngle"],
                flipUVs=pm["flipUVs"],
                ch=pm["ch"],
            )
        except Exception as e:
            _warn("polyMirrorFace failed: {}".format(e))
            return []

        created = []
        if shape and before_count is not None:
            try:
                after_count = cmds.polyEvaluate(shape, face=True)
                if after_count and after_count > before_count:
                    created = ["{}.f[{}]".format(obj, i) for i in range(before_count, after_count)]
            except Exception:
                created = []

        # Fallback: grab current selection (sometimes it leaves created faces selected)
        if not created:
            sel = cmds.ls(sl=True, fl=True) or []
            created = [s for s in sel if s.startswith(obj + ".f[")]

        return created

    def _merge_open_border_verts(self, obj, threshold=0.001):
        border_edges = cmds.polyListComponentConversion(obj, toEdge=True, border=True) or []
        border_edges = cmds.ls(border_edges, fl=True) or []
        if not border_edges:
            return

        verts = cmds.polyListComponentConversion(border_edges, toVertex=True) or []
        verts = cmds.ls(verts, fl=True) or []
        if not verts:
            return

        try:
            cmds.polyMergeVertex(verts, d=threshold, am=True, ch=False)
        except Exception as e:
            _warn("polyMergeVertex failed on {}: {}".format(obj, e))

    # -------------------------
    # APPLY ACTIONS (REAL IMPLEMENTATION)
    # -------------------------
    def on_apply_actions_clicked(self, *args):
        selected_objects = self.get_selected_transforms()
        if not selected_objects:
            cmds.warning("Please select at least one object.")
            return

        state = self.get_all_material_rows_state()

        delete_mats = set()
        mirror_by_pair = {}
        delete_by_pair = {}

        for mat, info in state.items():
            action = (info.get("action") or "Do Nothing").strip()
            pair = (info.get("pair") or "").strip().upper()

            if action == "To Delete":
                delete_mats.add(mat)
                if pair:
                    delete_by_pair.setdefault(pair, []).append(mat)

            elif action == "To Mirror":
                if pair:
                    mirror_by_pair.setdefault(pair, []).append(mat)

        if not delete_mats and not mirror_by_pair:
            cmds.warning("Nothing to do: no materials set to To Delete or To Mirror.")
            return

        pm = self._get_polyMirrorFace_settings()
        final_merge = float(self.final_merge_thresh.value())

        # Process each selected object independently
        for obj in selected_objects:
            if not self._get_mesh_dagpath(obj):
                continue

            # 1) Delete faces assigned to materials marked "To Delete"
            faces_to_delete = []
            for mat in delete_mats:
                faces_to_delete.extend(self._collect_faces_for_material_on_obj(obj, mat))

            faces_to_delete = cmds.ls(faces_to_delete, fl=True) or []
            if faces_to_delete:
                try:
                    cmds.delete(faces_to_delete)
                except Exception as e:
                    _warn("Delete failed on {}: {}".format(obj, e))

            # 2) For each pair: mirror sources -> assign to first delete material in same pair
            all_pairs = sorted(set(list(mirror_by_pair.keys()) + list(delete_by_pair.keys())))
            for pair in all_pairs:
                mirrors = mirror_by_pair.get(pair, [])
                deletes = delete_by_pair.get(pair, [])

                if not mirrors:
                    continue
                if not deletes:
                    _warn("Pair '{}' has To Mirror but no To Delete receiver material.".format(pair))
                    continue

                src_mat = mirrors[0]
                dst_mat = deletes[0]

                dst_sg = self._get_sg_for_material(dst_mat)
                if not dst_sg:
                    _warn("Cannot find shadingEngine for '{}'. Pair '{}' skipped.".format(dst_mat, pair))
                    continue

                src_faces = self._collect_faces_for_material_on_obj(obj, src_mat)
                src_faces = cmds.ls(src_faces, fl=True) or []
                if not src_faces:
                    continue

                created_faces = self._poly_mirror_faces_exact(src_faces, pm)
                created_faces = cmds.ls(created_faces, fl=True) or []
                created_faces = [f for f in created_faces if f.startswith(obj + ".f[")]

                if not created_faces:
                    _warn("Pair '{}': mirror produced no detectable faces on {}.".format(pair, obj))
                    continue

                try:
                    cmds.sets(created_faces, e=True, forceElement=dst_sg)
                except Exception as e:
                    _warn("Assign failed (pair {} / {}): {}".format(pair, obj, e))

            # 3) Merge open border verts
            self._merge_open_border_verts(obj, threshold=final_merge)

        cmds.inViewMessage(
            amg="<hl>Batch Actions</hl> done (Delete / Mirror + Merge Borders).",
            pos='midCenterTop',
            fade=True
        )
        
        
    # -------------------------
    # Symmetry mismatch detection (stub / safe)
    # -------------------------
    def on_find_symmetry_mismatch_clicked(self, *args):
        """
        Safe placeholder so the UI doesn't crash if you haven't pasted
        the full symmetry mismatch implementation.
        """
        _warn("Symmetry mismatch tool is not implemented in this version of the script.")


# Run / show
def show_material_selector_ui():
    for w in QtWidgets.QApplication.allWidgets():
        if isinstance(w, QtWidgets.QDialog) and w.windowTitle() == "Material Selector":
            try:
                w.close()
            except Exception:
                pass

    dlg = MaterialSelectorUI()
    dlg.show()
    return dlg


show_material_selector_ui()