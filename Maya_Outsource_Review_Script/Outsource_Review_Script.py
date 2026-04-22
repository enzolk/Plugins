# -*- coding: utf-8 -*-
"""
High Poly Review Assistant (Maya)
---------------------------------
Production-oriented review helper for outsourcing High Poly deliveries.

Usage in Maya Script Editor (Python tab):
    import Maya_Outsource_Review_Script.Outsource_Review_Script as ors
    ors.show_outsource_review_tool()
"""

from __future__ import annotations

import json
import os
import re
import textwrap
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui

QT_BINDING = ""
QT_AVAILABLE = False
try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from shiboken2 import wrapInstance

    QT_BINDING = "PySide2"
    QT_AVAILABLE = True
except Exception:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        from shiboken6 import wrapInstance

        QT_BINDING = "PySide6"
        QT_AVAILABLE = True
    except Exception:
        QtCore = QtGui = QtWidgets = None  # type: ignore[assignment]
        wrapInstance = None  # type: ignore[assignment]

if QT_AVAILABLE and QtWidgets is not None and QtCore is not None:
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)


def get_ui_scale() -> float:
    if not QT_AVAILABLE or QtWidgets is None:
        return 1.0
    app = QtWidgets.QApplication.instance()
    if app is None:
        return 1.0
    screen = app.primaryScreen() or QtWidgets.QApplication.primaryScreen()
    if screen is None:
        return 1.0
    dpi = screen.logicalDotsPerInch()
    return dpi / 96.0 if dpi > 0 else 1.0


UI_SCALE_OVERRIDE = 0.8
UI_SCALE = get_ui_scale() * UI_SCALE_OVERRIDE


def s(value: float) -> int:
    return max(1, int(round(value * UI_SCALE)))


WINDOW_NAME = "highPolyReviewAssistantWin"
WINDOW_TITLE = "Outsource Review Script"
MAX_UI_TEXT_LENGTH = 90
MAX_MENU_LABEL_LENGTH = 72
UI_COLOR_BG_WINDOW = (0.17, 0.17, 0.18)
UI_COLOR_BG_SECTION = (0.20, 0.20, 0.22)
UI_COLOR_BG_SUBSECTION = (0.23, 0.23, 0.25)
UI_COLOR_BG_ACCENT = (0.25, 0.37, 0.56)
UI_COLOR_BG_ACCENT_SOFT = (0.28, 0.32, 0.38)
UI_COLOR_BG_WARNING = (0.34, 0.27, 0.16)
UI_COLOR_BG_LOG = (0.15, 0.15, 0.16)
UI_COLOR_TEXT_MUTED = (0.77, 0.77, 0.79)
UI_COLOR_VIS_ON = (0.22, 0.44, 0.30)
UI_COLOR_VIS_OFF = (0.30, 0.30, 0.32)
UI_BUTTON_HEIGHT = 28
UI_PRIMARY_BUTTON_HEIGHT = 32
ROOT_SUFFIXES = {
    "high": "_high",
    "low": "_low",
    "placeholder": "_placeholder",
}
PLACEHOLDER_TOKEN = "placeholder"
LOW_UV_DISTORTION_THRESHOLD = 1.6
LOW_MAP2_TARGET_TD = 20.48
LOW_MAP2_TOLERANCE = 0.50
INTEGRATION_QDTOOLS_CATEGORIES = ["Props", "SetDress", "Environment"]
INTEGRATION_QDTOOLS_PREFIXES = ("ACC_", "ARC_", "LIB_", "VEH_", "WEP_")


@dataclass
class ReviewIssue:
    level: str  # INFO, WARNING, FAIL
    category: str
    message: str
    objects: List[str] = field(default_factory=list)


@dataclass
class DetailedLogRowRef:
    """Stable UI references for one Detailed Logs row."""

    log_index: int
    order: int
    row_layout: str
    main_text_control: str
    measured_height: int


def _resolve_scaled_tokens(qss: str) -> str:
    return re.sub(r"\{s\((\d+)\)\}", lambda match: str(s(int(match.group(1)))), qss)


STEP01_QSS = _resolve_scaled_tokens("""
QFrame#Step01Card {
    background-color: #151f31;
    border: 1px solid #273854;
    border-radius: {s(12)}px;
}
QFrame#StepCard {
    background-color: #151f31;
    border: 1px solid #273854;
    border-radius: {s(12)}px;
}
QFrame#StepBadge {
    background-color: #121b2c;
    border: 1px solid #2a4670;
    border-radius: {s(8)}px;
}
QLabel#StepBadgeTop {
    color: #72b1ff;
    font-size: {s(10)}px;
    font-weight: 700;
    letter-spacing: 0.8px;
}
QLabel#StepBadgeBottom {
    color: #72b1ff;
    font-size: {s(38)}px;
    font-weight: 700;
}
QLabel#StepTitle {
    color: #edf2ff;
    font-size: {s(33)}px;
    font-weight: 700;
}
QToolButton#InfoButton, QToolButton#CollapseButton {
    border: none;
    color: #8ea2c0;
    background: transparent;
    font-size: {s(16)}px;
}
QToolButton#InfoButton {
    min-width: {s(24)}px;
    min-height: {s(24)}px;
    border-radius: {s(12)}px;
    color: #b9cff5;
    font-weight: 700;
}
QToolButton#InfoButton:hover {
    background-color: #1c2a41;
    color: #e9f2ff;
}
QToolButton#CollapseButton {
    min-width: {s(40)}px;
    min-height: {s(40)}px;
    padding: {s(2)}px;
    border-radius: {s(10)}px;
    font-size: {s(28)}px;
    font-weight: 700;
    color: #c9dbfb;
}
QToolButton#CollapseButton:hover {
    background-color: #1d2b42;
    color: #eef4ff;
}
QToolButton#CollapseButton:pressed {
    background-color: #162236;
    color: #ffffff;
}
QFrame#RootLabelFrame {
    background-color: #1a2539;
    border: 1px solid #25374f;
    border-radius: {s(8)}px;
}
QLabel#RootLabelIcon, QLabel#RootLabelText {
    color: #dde7fb;
    font-size: {s(16)}px;
    font-weight: 600;
}
QComboBox#RootPathCombo {
    background-color: #0d1422;
    border: 1px solid #2b3f5f;
    border-radius: {s(8)}px;
    color: #e9f1ff;
    padding: 0 {s(34)}px 0 {s(12)}px;
    min-height: {s(40)}px;
    font-size: {s(16)}px;
}
QComboBox#RootPathCombo::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    border: none;
    background: transparent;
    width: {s(30)}px;
}
QComboBox#RootPathCombo::down-arrow {
    image: none;
    width: 0;
    height: 0;
}
QPushButton#PrimaryBlueButton {
    background-color: #2b6fd4;
    border: 1px solid #3a7ce0;
    border-radius: {s(8)}px;
    color: #ffffff;
    min-height: {s(40)}px;
    padding-left: {s(16)}px;
    padding-right: {s(16)}px;
    font-size: {s(16)}px;
    font-weight: 700;
}
QPushButton#PrimaryBlueButton:hover {
    background-color: #3380f4;
}
QToolButton#SquareIconButton {
    background-color: #1f2a3e;
    border: 1px solid #31435f;
    border-radius: {s(8)}px;
    color: #dce9ff;
    min-width: {s(40)}px;
    min-height: {s(40)}px;
    font-size: {s(15)}px;
}
QFrame#SubChecksBand {
    background-color: #182335;
    border: 1px solid #243751;
    border-radius: {s(10)}px;
}
QListWidget#StepListWidget {
    background-color: #0f1727;
    border: 1px solid #2f4360;
    border-radius: {s(8)}px;
    color: #dce9ff;
    font-size: {s(13)}px;
    padding: {s(4)}px;
}
QCheckBox#GlobalToggleBox {
    color: #c7d8f3;
    font-size: {s(13)}px;
    font-weight: 600;
}
QCheckBox#StepSubCheckBox {
    color: #eaf2ff;
    font-size: {s(16)}px;
    font-weight: 700;
    spacing: {s(8)}px;
}
QCheckBox#StepSubCheckBox::indicator {
    width: {s(19)}px;
    height: {s(19)}px;
    border-radius: {s(4)}px;
    border: 1px solid #3a4f6d;
    background-color: #0f1727;
}
QCheckBox#StepSubCheckBox::indicator:checked {
    background-color: #14331f;
    border: 1px solid #34aa5f;
    image: none;
}
QCheckBox#StepSubCheckBox[resultState="FAIL"]::indicator {
    background-color: #3a1414;
    border: 1px solid #d75d5d;
}
QCheckBox#StepSubCheckBox[resultState="PENDING"]::indicator {
    background-color: #0f1727;
    border: 1px solid #3a4f6d;
}
QLabel#SubCheckDesc {
    color: #a8b6cc;
    font-size: {s(14)}px;
}
QFrame#ThinDivider {
    background-color: #2a3d57;
    max-width: 1px;
    min-width: 1px;
}
QPushButton#RunCheckButton {
    background-color: #2b6fd4;
    border: 1px solid #3a7ce0;
    border-radius: {s(8)}px;
    color: white;
    min-height: {s(40)}px;
    padding: 0 {s(18)}px;
    font-size: {s(16)}px;
    font-weight: 700;
}
QPushButton#RunCheckButton:hover {
    background-color: #3d8cff;
    border: 1px solid #69a9ff;
}
QPushButton#RunCheckButton:pressed {
    background-color: #225cb5;
    border: 1px solid #1d4e99;
    padding-top: {s(1)}px;
    padding-left: {s(1)}px;
}
QLabel#ToleranceLabel {
    color: #e0e8f7;
    font-size: {s(16)}px;
    font-weight: 600;
}
QDoubleSpinBox#ToleranceSpin {
    background-color: #0f1727;
    border: 1px solid #2f4360;
    border-radius: {s(8)}px;
    color: #f1f6ff;
    min-height: {s(40)}px;
    min-width: {s(90)}px;
    padding-right: {s(16)}px;
    font-size: {s(16)}px;
    font-weight: 600;
}
QDoubleSpinBox#ToleranceSpin::up-button,
QDoubleSpinBox#ToleranceSpin::down-button {
    width: {s(18)}px;
    border: none;
    background-color: #101b2d;
}
""")


if QT_AVAILABLE and QtWidgets is not None:
    class StepInfoToolTipPopup(QtWidgets.QFrame):
        def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
            super().__init__(parent, QtCore.Qt.ToolTip)
            self.setObjectName("StepInfoToolTipPopup")
            self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            self.setWindowFlag(QtCore.Qt.FramelessWindowHint, True)
            self.setStyleSheet(
                "QFrame#StepInfoToolTipPopup {"
                "background-color: #132238;"
                "border: 1px solid #34506f;"
                f"border-radius: {s(10)}px;"
                "}" 
                "QLabel {"
                "color: #eaf2ff;"
                f"font-size: {s(12)}px;"
                "line-height: 1.35em;"
                "}"
            )
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(s(12), s(10), s(12), s(10))
            self.label = QtWidgets.QLabel()
            self.label.setWordWrap(True)
            self.label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            layout.addWidget(self.label)

        def show_text(self, anchor_widget: QtWidgets.QWidget, message: str) -> None:
            self.label.setText(message)
            self.adjustSize()
            global_pos = anchor_widget.mapToGlobal(QtCore.QPoint(0, anchor_widget.height() + s(8)))
            self.move(global_pos)
            self.show()
            self.raise_()


    class ModernInfoButton(QtWidgets.QToolButton):
        def __init__(self, tooltip_text: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
            super().__init__(parent)
            self._tooltip_text = tooltip_text
            self._tooltip_popup = StepInfoToolTipPopup(parent)
            self._tooltip_timer = QtCore.QTimer(self)
            self._tooltip_timer.setSingleShot(True)
            self._tooltip_timer.timeout.connect(self._show_tooltip)

        def _show_tooltip(self) -> None:
            self._tooltip_popup.show_text(self, self._tooltip_text)

        def enterEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
            self._tooltip_timer.start(s(140))
            super().enterEvent(event)

        def leaveEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
            self._tooltip_timer.stop()
            self._tooltip_popup.hide()
            super().leaveEvent(event)

        def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:  # type: ignore[override]
            self._tooltip_popup.hide()
            super().mousePressEvent(event)


    class ModernRootComboBox(QtWidgets.QComboBox):
        def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # type: ignore[override]
            super().paintEvent(event)
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            arrow_color = QtGui.QColor("#e8efff") if self.isEnabled() else QtGui.QColor("#90a0b8")
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(arrow_color)
            center_x = self.width() - s(16)
            center_y = self.height() // 2 + s(1)
            triangle = QtGui.QPolygon([
                QtCore.QPoint(center_x - s(5), center_y - s(2)),
                QtCore.QPoint(center_x + s(5), center_y - s(2)),
                QtCore.QPoint(center_x, center_y + s(4)),
            ])
            painter.drawPolygon(triangle)
            painter.end()


if QT_AVAILABLE and QtWidgets is not None:
    class StepRootSelectorRow(QtWidgets.QWidget):
        def __init__(self, label_text: str, menu_key: str, parent: Optional[QtWidgets.QWidget] = None) -> None:
            super().__init__(parent)
            self.menu_key = menu_key
            self._compact_mode = False
            self._root_layout = QtWidgets.QGridLayout(self)
            self._root_layout.setContentsMargins(0, 0, 0, 0)
            self._root_layout.setHorizontalSpacing(s(10))
            self._root_layout.setVerticalSpacing(s(8))

            label_frame = QtWidgets.QFrame()
            label_frame.setObjectName("RootLabelFrame")
            label_frame.setMinimumWidth(s(140))
            label_frame.setMaximumWidth(s(260))
            label_frame.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
            label_layout = QtWidgets.QHBoxLayout(label_frame)
            label_layout.setContentsMargins(s(14), s(8), s(14), s(8))
            label_layout.setSpacing(s(8))
            icon_lbl = QtWidgets.QLabel("◈")
            icon_lbl.setObjectName("RootLabelIcon")
            txt_lbl = QtWidgets.QLabel(label_text)
            txt_lbl.setObjectName("RootLabelText")
            label_layout.addWidget(icon_lbl)
            label_layout.addWidget(txt_lbl)
            label_layout.addStretch(1)

            self.path_combo = ModernRootComboBox()
            self.path_combo.setObjectName("RootPathCombo")
            self.path_combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            self.path_combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
            self.path_combo.setMaxVisibleItems(20)
            self.path_combo.setMinimumWidth(s(180))

            self.use_selection_btn = QtWidgets.QPushButton("Use Selection")
            self.use_selection_btn.setObjectName("PrimaryBlueButton")
            self.use_selection_btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            button_text_width = self.use_selection_btn.fontMetrics().horizontalAdvance(self.use_selection_btn.text())
            self.use_selection_btn.setMinimumWidth(button_text_width + s(30))

            self._label_frame = label_frame
            self._refresh_layout()

        def _clear_layout(self) -> None:
            while self._root_layout.count():
                item = self._root_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(self)

        def _refresh_layout(self) -> None:
            self._clear_layout()
            if self._compact_mode:
                self._root_layout.addWidget(self._label_frame, 0, 0, 1, 2)
                self._root_layout.addWidget(self.path_combo, 1, 0, 1, 1)
                self._root_layout.addWidget(self.use_selection_btn, 1, 1, 1, 1)
                self._root_layout.setColumnStretch(0, 1)
                self._root_layout.setColumnStretch(1, 0)
            else:
                self._root_layout.addWidget(self._label_frame, 0, 0, 1, 1)
                self._root_layout.addWidget(self.path_combo, 0, 1, 1, 1)
                self._root_layout.addWidget(self.use_selection_btn, 0, 2, 1, 1)
                self._root_layout.setColumnStretch(0, 0)
                self._root_layout.setColumnStretch(1, 1)
                self._root_layout.setColumnStretch(2, 0)

        def resizeEvent(self, event: QtGui.QResizeEvent) -> None:  # type: ignore[override]
            compact = self.width() < s(620)
            if compact != self._compact_mode:
                self._compact_mode = compact
                self._refresh_layout()
            super().resizeEvent(event)
else:
    class StepRootSelectorRow:  # type: ignore[no-redef]
        pass


if QT_AVAILABLE and QtWidgets is not None:
    class ReviewStepCard(QtWidgets.QFrame):
        def __init__(self, step_num: int, title: str, info_text: str = "", parent: Optional[QtWidgets.QWidget] = None) -> None:
            super().__init__(parent)
            self.setObjectName("StepCard")
            self.setStyleSheet(STEP01_QSS)
            self.body_widget = QtWidgets.QWidget()
            root = QtWidgets.QVBoxLayout(self)
            root.setContentsMargins(s(14), s(12), s(14), s(12))
            root.setSpacing(s(10))

            header = QtWidgets.QHBoxLayout()
            header.setSpacing(s(10))
            badge = QtWidgets.QFrame()
            badge.setObjectName("StepBadge")
            badge.setFixedSize(s(52), s(52))
            b_l = QtWidgets.QVBoxLayout(badge)
            b_l.setContentsMargins(0, s(7), 0, s(6))
            b_l.setSpacing(0)
            b_l.setAlignment(QtCore.Qt.AlignCenter)
            t = QtWidgets.QLabel("STEP")
            t.setObjectName("StepBadgeTop")
            t.setAlignment(QtCore.Qt.AlignCenter)
            n = QtWidgets.QLabel(f"{step_num:02d}")
            n.setObjectName("StepBadgeBottom")
            n.setAlignment(QtCore.Qt.AlignCenter)
            n.setStyleSheet(f"font-size: {s(24)}px;")
            b_l.addWidget(t)
            b_l.addWidget(n)

            title_lbl = QtWidgets.QLabel(title)
            title_lbl.setObjectName("StepTitle")
            title_lbl.setStyleSheet(f"font-size: {s(18)}px;")
            header.addWidget(badge, 0, QtCore.Qt.AlignVCenter)
            header.addWidget(title_lbl, 0, QtCore.Qt.AlignVCenter)
            if info_text:
                info_btn = ModernInfoButton(info_text)
                info_btn.setObjectName("InfoButton")
                info_btn.setText("ⓘ")
                header.addWidget(info_btn, 0, QtCore.Qt.AlignVCenter)
            header.addStretch(1)
            self.collapse_btn = QtWidgets.QToolButton()
            self.collapse_btn.setObjectName("CollapseButton")
            self.collapse_btn.setText("▾")
            self.collapse_btn.clicked.connect(self._toggle_body)
            header.addWidget(self.collapse_btn, 0, QtCore.Qt.AlignVCenter)
            root.addLayout(header)

            body_l = QtWidgets.QVBoxLayout(self.body_widget)
            body_l.setContentsMargins(0, 0, 0, 0)
            body_l.setSpacing(s(8))
            root.addWidget(self.body_widget)

        def body_layout(self) -> QtWidgets.QVBoxLayout:
            return self.body_widget.layout()  # type: ignore[return-value]

        def _toggle_body(self) -> None:
            visible = self.body_widget.isVisible()
            self.body_widget.setVisible(not visible)
            self.collapse_btn.setText("▸" if visible else "▾")
else:
    class ReviewStepCard:  # type: ignore[no-redef]
        pass


class HighPolyReviewTool:
    """Main tool class for High Poly outsourcing review."""

    def __init__(self) -> None:
        self.ui = {}
        self.result_items: List[ReviewIssue] = []
        self.result_index_to_objects: Dict[int, List[str]] = {}
        self.result_control_to_objects: Dict[str, List[str]] = {}

        self.paths = {
            "root": "",
            "high_ma": "",
            "high_fbx": "",
            "bake_ma": "",
            "low_fbx": "",
            "final_scene_ma": "",
            "final_asset_fbx": "",
        }

        self.detected_files: Dict[str, List[str]] = {
            "high_ma": [],
            "high_fbx": [],
            "bake_ma": [],
            "low_fbx": [],
            "final_scene_ma": [],
            "final_asset_fbx": [],
        }

        self.detected_roots: Dict[str, List[str]] = {
            "high": [],
            "placeholder": [],
            "low": [],
            "bake_high": [],
            "bake_low": [],
            "final_asset_ma": [],
            "final_asset_fbx": [],
        }

        self.context = {
            "fbx_namespace": "High_FBX_File",
            "ma_namespace": "High_Ma_File",
            "bake_ma_namespace": "Bake_MA_File",
            "low_fbx_namespace": "Low_FBX_File",
            "final_asset_ma_namespace": "Final_Asset_MA_File",
            "final_asset_fbx_namespace": "Final_Asset_FBX_File",
            "final_asset_fbx_namespaces": [],
            "fbx_nodes": [],
            "fbx_meshes": [],
            "ma_nodes": [],
            "ma_meshes": [],
            "bake_ma_nodes": [],
            "bake_ma_meshes": [],
            "low_fbx_nodes": [],
            "low_fbx_meshes": [],
            "final_asset_ma_nodes": [],
            "final_asset_ma_meshes": [],
            "final_asset_fbx_nodes": [],
            "final_asset_fbx_meshes": [],
        }
        self.allowed_review_namespaces: Set[str] = {
            "High_Ma_File",
            "High_FBX_File",
            "Low_FBX_File",
            "Bake_MA_File",
            "Final_Asset_MA",
            "Final_Asset_MA_File",
            "Final_Asset_FBX_File",
        }
        self.review_subgroups_by_file = {
            "high_ma": "High_MA_GRP",
            "high_fbx": "High_FBX_GRP",
            "placeholder": "Placeholder_GRP",
            "low_fbx": "Low_FBX_GRP",
            "bake_ma": "Bake_MA_GRP",
            "final_scene_ma": "Final_Asset_MA_GRP",
            "final_asset_fbx": "Final_Asset_FBX_GRP",
        }

        self.check_states = {
            "ma_fbx_compared": {"status": "PENDING", "mode": "AUTO"},
            "ma_bake_compared": {"status": "PENDING", "mode": "AUTO"},
            "bake_structure_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_low_topology_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_high_vertex_colors_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_high_materials_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_low_materials_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_low_uv_map1_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_low_uv_map2_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_pairing_checked": {"status": "PENDING", "mode": "AUTO"},
            "bake_ready_checked": {"status": "PENDING", "mode": "AUTO"},
            "no_namespaces": {"status": "PENDING", "mode": "AUTO"},
            "placeholder_checked": {"status": "PENDING", "mode": "AUTO"},
            "design_kit_checked": {"status": "PENDING", "mode": "MANUAL"},
            "topology_checked": {"status": "PENDING", "mode": "AUTO"},
            "texture_sets_analyzed": {"status": "PENDING", "mode": "AUTO"},
            "vertex_colors_checked": {"status": "PENDING", "mode": "AUTO"},
            "low_topology_checked": {"status": "PENDING", "mode": "AUTO"},
            "low_namespaces_checked": {"status": "PENDING", "mode": "AUTO"},
            "low_materials_checked": {"status": "PENDING", "mode": "AUTO"},
            "low_uv_map1_checked": {"status": "PENDING", "mode": "AUTO"},
            "low_uv_map2_checked": {"status": "PENDING", "mode": "AUTO"},
            "low_bake_compared": {"status": "PENDING", "mode": "AUTO"},
            "low_final_compared": {"status": "PENDING", "mode": "AUTO"},
            "final_topology_checked": {"status": "PENDING", "mode": "AUTO"},
            "final_namespaces_checked": {"status": "PENDING", "mode": "AUTO"},
            "final_materials_checked": {"status": "PENDING", "mode": "AUTO"},
            "final_uv_map1_checked": {"status": "PENDING", "mode": "AUTO"},
            "final_uv_map2_checked": {"status": "PENDING", "mode": "AUTO"},
            "final_ma_fbx_compared": {"status": "PENDING", "mode": "AUTO"},
        }

        self.check_ui_map = {
            "ma_fbx_compared": "check_ma_fbx",
            "ma_bake_compared": "check_ma_bake",
            "bake_structure_checked": "check_bake_structure",
            "bake_low_topology_checked": "check_bake_low_topology",
            "bake_high_vertex_colors_checked": "check_bake_high_vertex_colors",
            "bake_high_materials_checked": "check_bake_high_materials",
            "bake_low_materials_checked": "check_bake_low_materials",
            "bake_low_uv_map1_checked": "check_bake_low_uv_map1",
            "bake_low_uv_map2_checked": "check_bake_low_uv_map2",
            "bake_pairing_checked": "check_bake_pairing",
            "bake_ready_checked": "check_bake_ready",
            "no_namespaces": "check_ns",
            "placeholder_checked": "check_placeholder",
            "design_kit_checked": "check_design",
            "topology_checked": "check_topology",
            "texture_sets_analyzed": "check_texturesets",
            "vertex_colors_checked": "check_vtx",
            "low_topology_checked": "check_low_topology",
            "low_namespaces_checked": "check_low_ns",
            "low_materials_checked": "check_low_materials",
            "low_uv_map1_checked": "check_low_uv_map1",
            "low_uv_map2_checked": "check_low_uv_map2",
            "low_bake_compared": "check_low_bake",
            "low_final_compared": "check_low_final",
            "final_topology_checked": "check_final_topology",
            "final_namespaces_checked": "check_final_ns",
            "final_materials_checked": "check_final_materials",
            "final_uv_map1_checked": "check_final_uv_map1",
            "final_uv_map2_checked": "check_final_uv_map2",
            "final_ma_fbx_compared": "check_final_compare",
        }
        self.subcheck_definitions: Dict[str, List[Tuple[str, str]]] = {
            "placeholder_checked": [("bbox", "BBox"), ("pivot", "Pivot")],
            "design_kit_checked": [("reviewed", "Design Kit Reviewed")],
            "topology_checked": [("non_manifold_geometry", "Non Manifold Geometry"), ("non_manifold_uv", "Non Manifold UV"), ("lamina_faces", "Lamina Faces"), ("ngons", "N-Gons")],
            "vertex_colors_checked": [("vertex_colors_present", "Vertex Colors Present")],
            "no_namespaces": [("authorized_namespaces_only", "Authorized Namespaces Only")],
            "texture_sets_analyzed": [("materials_texture_sets_analyzed", "Materials / Texture Sets Analyzed")],
            "ma_fbx_compared": [("presence", "Presence"), ("topology", "Topology"), ("uv", "UV"), ("bounding_box", "Bounding Box"), ("pivot", "Pivot")],
            "ma_bake_compared": [("presence", "Presence"), ("topology", "Topology"), ("uv", "UV"), ("bounding_box", "Bounding Box"), ("pivot", "Pivot")],
            "low_topology_checked": [("non_manifold_geometry", "Non Manifold Geometry"), ("non_manifold_uv", "Non Manifold UV"), ("lamina_faces", "Lamina Faces"), ("ngons", "N-Gons")],
            "low_namespaces_checked": [("authorized_namespaces_only", "Authorized Namespaces Only")],
            "low_materials_checked": [("materials_texture_sets_analyzed", "Materials / Texture Sets Analyzed")],
            "low_uv_map1_checked": [("overlap_outside", "Overlap / Outside 0-1"), ("zero_space_uv_shells", "Zero-Space UV Shells")],
            "low_uv_map2_checked": [("map2_present", "Map2 Present"), ("texel_density", "Texel Density"), ("zero_space_uv_shells", "Zero-Space UV Shells")],
            "low_bake_compared": [("presence", "Presence"), ("topology", "Topology"), ("uv", "UV"), ("bounding_box", "Bounding Box")],
            "low_final_compared": [("presence", "Presence"), ("topology", "Topology"), ("uv", "UV"), ("bounding_box", "Bounding Box"), ("pivot", "Pivot")],
            "bake_structure_checked": [("bake_high_present", "Bake High Present"), ("bake_low_present", "Bake Low Present"), ("structure_valid", "Structure Valid")],
            "bake_low_topology_checked": [("non_manifold_geometry", "Non Manifold Geometry"), ("non_manifold_uv", "Non Manifold UV"), ("lamina_faces", "Lamina Faces"), ("ngons", "N-Gons")],
            "bake_high_vertex_colors_checked": [("vertex_colors_present", "Vertex Colors Present")],
            "bake_high_materials_checked": [("materials_texture_sets_analyzed", "Materials / Texture Sets Analyzed")],
            "bake_low_materials_checked": [("materials_texture_sets_analyzed", "Materials / Texture Sets Analyzed")],
            "bake_low_uv_map1_checked": [("overlap_outside", "Overlap / Outside 0-1"), ("zero_space_uv_shells", "Zero-Space UV Shells")],
            "bake_low_uv_map2_checked": [("map2_present", "Map2 Present"), ("texel_density", "Texel Density"), ("zero_space_uv_shells", "Zero-Space UV Shells")],
            "bake_pairing_checked": [("naming", "Naming"), ("pairing", "Pairing"), ("bounding_box", "Bounding Box")],
            "bake_ready_checked": [("bake_ready", "Bake Ready")],
            "final_topology_checked": [("non_manifold_geometry", "Non Manifold Geometry"), ("non_manifold_uv", "Non Manifold UV"), ("lamina_faces", "Lamina Faces"), ("ngons", "N-Gons")],
            "final_namespaces_checked": [("authorized_namespaces_only", "Authorized Namespaces Only")],
            "final_materials_checked": [("materials_texture_sets_analyzed", "Materials / Texture Sets Analyzed")],
            "final_uv_map1_checked": [("overlap_outside", "Overlap / Outside 0-1"), ("zero_space_uv_shells", "Zero-Space UV Shells")],
            "final_uv_map2_checked": [("map2_present", "Map2 Present"), ("texel_density", "Texel Density"), ("zero_space_uv_shells", "Zero-Space UV Shells")],
            "final_ma_fbx_compared": [("presence", "Presence"), ("topology", "Topology"), ("uv", "UV"), ("bounding_box", "Bounding Box"), ("pivot", "Pivot")],
        }
        self.subcheck_states: Dict[str, Dict[str, str]] = {
            step_key: {sub_key: "PENDING" for sub_key, _ in subchecks}
            for step_key, subchecks in self.subcheck_definitions.items()
        }
        self.subcheck_ui_map: Dict[str, Dict[str, str]] = {}

        self.detected_texture_sets: Dict[str, Dict[str, object]] = {}
        self.material_sets_by_context: Dict[str, Dict[str, Dict[str, object]]] = {"high": {}, "low": {}, "bake_high": {}, "bake_low": {}, "final_asset": {}}
        self.texture_set_visibility: Dict[str, bool] = {}
        self.texture_set_label_to_key_by_context: Dict[str, Dict[str, str]] = {"high": {}, "low": {}, "bake_high": {}, "bake_low": {}, "final_asset": {}}
        self.texture_set_section_headers_by_context: Dict[str, Set[str]] = {"high": set(), "low": set(), "bake_high": set(), "bake_low": set(), "final_asset": set()}
        self.material_isolation_state: Dict[str, str] = {"context": "", "material_key": ""}
        self.last_scanned_namespaces: List[str] = []
        self.detected_assets: List[str] = []
        self.asset_to_final_fbx: Dict[str, str] = {}
        self.active_asset: str = ""
        self.scope_keys = ["placeholder", "high_ma", "high_fbx"]
        self.scope_labels = {"placeholder": "Placeholder", "high_ma": "High MA", "high_fbx": "High FBX"}
        self.last_texture_scope: List[str] = []
        self.review_group_contents = {
            "high_ma": [],
            "high_fbx": [],
            "placeholder": [],
            "low_fbx": [],
            "bake_ma": [],
            "final_scene_ma": [],
            "final_asset_fbx": [],
        }
        self.summary_items: List[ReviewIssue] = []
        self.summary_row_ranges: List[Tuple[int, int]] = []
        self.summary_row_fail_targets: Dict[int, List[int]] = {}
        self.summary_row_fail_cursor: Dict[int, int] = {}
        self.log_rows_by_index: Dict[int, DetailedLogRowRef] = {}
        self.log_row_order: List[int] = []
        self.manual_root_menu_sources: Dict[str, str] = {}
        self.manual_root_menu_values: Dict[str, List[str]] = {}
        self.manual_root_overrides: Dict[str, List[str]] = {}
        self.manual_root_fulltext_controls: Dict[str, str] = {}
        self.manual_root_fulltext_layouts: Dict[str, str] = {}
        self.manual_root_fulltext_toggles: Dict[str, str] = {}
        self.manual_root_qt_rows: Dict[str, StepRootSelectorRow] = {}
        self.step01_placeholder_widget: Optional[QtWidgets.QWidget] = None
        self.step01_placeholder_body_widget: Optional[QtWidgets.QWidget] = None
        self.step01_collapse_button: Optional[QtWidgets.QToolButton] = None
        self.step01_qt_subcheck_widgets: Dict[str, QtWidgets.QCheckBox] = {}
        self.qt_check_widgets: Dict[str, QtWidgets.QCheckBox] = {}
        self.qt_subcheck_widgets: Dict[str, Dict[str, QtWidgets.QCheckBox]] = {}
        self.qt_global_toggles: Dict[str, QtWidgets.QCheckBox] = {}
        self.qt_list_widgets: Dict[str, QtWidgets.QListWidget] = {}
        self.scene_visibility_groups_by_context: Dict[str, List[Dict[str, Any]]] = {}
        self.scene_visibility_controls: Dict[str, str] = {}
        self.integration_catalog_assets: List[str] = []
        self.integration_main_catalog_assets: List[str] = []
        self.integration_annexe_catalog_assets: List[str] = []
        self.integration_detection_sources: Dict[str, Set[str]] = {}
        self.integration_annexe_sources: Dict[str, Set[str]] = {}
        self.integration_last_results: List[Tuple[str, bool, str]] = []
        self.integration_rights_confirmed: bool = False
        self.review_nav_buttons: Dict[str, QtWidgets.QPushButton] = {}
        self.review_tab_children: Dict[str, str] = {}
        self.review_tab_order: List[str] = []
        self.sidebar_summary_labels: Dict[str, QtWidgets.QLabel] = {}

    # --------------------------- UI BUILD ---------------------------
    def build(self) -> None:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        self.ui["window"] = cmds.window(
            WINDOW_NAME,
            title=WINDOW_TITLE,
            sizeable=True,
            widthHeight=(860, 900),
            minimizeButton=True,
            maximizeButton=True,
            backgroundColor=UI_COLOR_BG_WINDOW,
        )

        root_layout = cmds.formLayout()
        self.ui["content_col"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
        self._build_file_section()
        self._build_review_tabs_section()
        self._build_results_section()
        self._build_notes_section()
        self._build_summary_section()

        cmds.setParent(root_layout)
        cmds.formLayout(
            root_layout,
            edit=True,
            attachForm=[
                (self.ui["content_col"], "top", 0),
                (self.ui["content_col"], "left", 0),
                (self.ui["content_col"], "right", 0),
                (self.ui["content_col"], "bottom", 0),
            ],
        )

        cmds.window(self.ui["window"], edit=True, resizeToFitChildren=False)
        cmds.showWindow(self.ui["window"])

        if cmds.window(self.ui["window"], exists=True):
            cmds.window(self.ui["window"], edit=True, widthHeight=(860, 900))

        self.refresh_detected_file_labels()
        self.refresh_root_ui()
        self.refresh_manual_root_menus()
        self.refresh_summary()
        self.refresh_checklist_ui()

    def _build_file_section(self) -> None:
        cmds.frameLayout(label="1) Root Folder", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

        self.ui["root_field"] = cmds.textFieldButtonGrp(
            label="Root Folder",
            buttonLabel="Browse",
            adjustableColumn=2,
            columnWidth=[(1, 90), (3, 90)],
            buttonCommand=lambda *_: self.pick_root_folder(),
        )
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
        cmds.button(
            label="Scan Delivery Folder",
            height=UI_PRIMARY_BUTTON_HEIGHT,
            backgroundColor=UI_COLOR_BG_ACCENT_SOFT,
            command=lambda *_: self.scan_delivery_folder(),
        )
        cmds.button(
            label="Load Everything",
            height=UI_PRIMARY_BUTTON_HEIGHT,
            backgroundColor=UI_COLOR_BG_ACCENT,
            command=lambda *_: self.load_everything(),
        )
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_technical_checks_section(self) -> None:
        if QT_AVAILABLE and QtWidgets is not None:
            cmds.frameLayout(label="Review 01 — High.ma", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
            cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
            self._build_tab_visibility_controls("high")
            cmds.text(label="Guided review of the High.ma delivery.", align="left")
            self._build_step01_placeholder_match_qt()

            self._build_qt_step_card(
                2,
                "Design Kit Review",
                lambda body: (
                    body.addWidget(self._create_qt_subcheck_band("design_kit_checked")[0]),
                    body.addWidget(self._make_qt_run_button("Mark Step as Reviewed", self.mark_design_reviewed)),
                ),
            )

            def _high_topology_body(body):
                self._add_qt_root_selector_row(body, "topology_high_root_menu", "High Root (Topology)", "high_ma")
                band, lay = self._create_qt_subcheck_band("topology_checked")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Run Topology", self.run_topology_checks))
                body.addWidget(band)
            self._build_qt_step_card(3, "Topology Check", _high_topology_body)

            def _high_vcolor_body(body):
                self._add_qt_root_selector_row(body, "vertex_high_root_menu", "High Root (Vertex Colors)", "high_ma")
                band, lay = self._create_qt_subcheck_band("vertex_colors_checked")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Run Vertex Color Check", self.check_vertex_colors))
                lay.addWidget(self._make_qt_run_button("Display Vertex Color", self.display_vertex_colors))
                lay.addWidget(self._make_qt_run_button("Hide Vertex Color", self.hide_vertex_colors))
                body.addWidget(band)
            self._build_qt_step_card(4, "Vertex Colors", _high_vcolor_body)

            def _high_ns_body(body):
                band, lay = self._create_qt_subcheck_band("no_namespaces")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Scan Namespaces", self.scan_namespaces))
                lay.addWidget(self._make_qt_run_button("Remove Invalid Namespaces", self.remove_namespaces))
                body.addWidget(band)
            self._build_qt_step_card(5, "Namespaces", _high_ns_body)

            def _high_materials_body(body):
                self._add_qt_root_selector_row(body, "materials_high_root_menu", "High Root (Materials)", "high_ma")
                band, lay = self._create_qt_subcheck_band("texture_sets_analyzed")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Analyze Materials", lambda: self.analyze_texture_sets(mode="materials")))
                body.addWidget(band)
                lst = QtWidgets.QListWidget()
                lst.setObjectName("StepListWidget")
                lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                lst.itemSelectionChanged.connect(lambda: self.on_texture_set_selection_changed("high"))
                self.ui["texture_sets_list"] = lst
                body.addWidget(lst)
                body.addWidget(self._make_qt_run_button("Isolate Material", lambda: self.toggle_isolate_selected_material("high")))
            self._build_qt_step_card(6, "Materials / Texture Sets", _high_materials_body)

            def _high_cmp_fbx_body(body):
                self._add_qt_root_selector_row(body, "compare_ma_root_menu", "High.ma Root", "high_ma")
                self._add_qt_root_selector_row(body, "compare_fbx_root_menu", "High.fbx Root", "high_fbx")
                band, lay = self._create_qt_subcheck_band("ma_fbx_compared")
                lay.addStretch(1)
                glb = QtWidgets.QCheckBox("Global")
                glb.setObjectName("GlobalToggleBox")
                glb.setChecked(False)
                self.ui["compare_ma_fbx_global_mode"] = glb
                lay.addWidget(glb)
                lay.addWidget(self._make_qt_run_button("Run Compare", self.compare_ma_vs_fbx))
                body.addWidget(band)
            self._build_qt_step_card(7, "Compare High.ma vs High.fbx", _high_cmp_fbx_body)

            def _high_cmp_bake_body(body):
                self._add_qt_root_selector_row(body, "compare_bake_ma_root_menu", "High.ma Root", "high_ma")
                self._add_qt_root_selector_row(body, "compare_bake_high_root_menu", "Bake High Root", "bake_high")
                band, lay = self._create_qt_subcheck_band("ma_bake_compared")
                lay.addStretch(1)
                glb = QtWidgets.QCheckBox("Global")
                glb.setObjectName("GlobalToggleBox")
                glb.setChecked(False)
                self.ui["compare_ma_bake_global_mode"] = glb
                lay.addWidget(glb)
                lay.addWidget(self._make_qt_run_button("Run Compare Bake", self.compare_ma_vs_bake_high))
                body.addWidget(band)
            self._build_qt_step_card(8, "Compare High.ma vs Bake Scene High", _high_cmp_bake_body)

            cmds.setParent("..")
            cmds.setParent("..")
            return
        cmds.frameLayout(label="Review 01 — High.ma", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self._build_tab_visibility_controls("high")
        cmds.text(label="Guided review of the High.ma delivery.", align="left")
        cmds.separator(style="in")
        self._build_step01_placeholder_match_qt()
        cmds.separator(style="in")
        cmds.text(label="Step 02 — Design Kit Review (manual)", align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self._build_subcheck_boxes("design_kit_checked")
        cmds.text(label="Visually verify high(s) against the design kit.", align="left")
        cmds.button(label="Mark Step as Reviewed", height=26, command=lambda *_: self.mark_design_reviewed())
        cmds.setParent("..")
        cmds.separator(style="in")
        cmds.text(label="Step 03 — Topology Check", align="left")
        self._build_manual_root_selector("topology_high_root_menu", "Select High Root for Topology Check", "high_ma")
        self._build_subcheck_boxes("topology_checked")
        cmds.button(label="Run Topology", height=26, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.run_topology_checks())
        cmds.separator(style="in")
        cmds.text(label="Step 04 — Vertex Colors", align="left")
        self._build_manual_root_selector("vertex_high_root_menu", "Select High Root for Vertex Color Check", "high_ma")
        cmds.rowLayout(
            numberOfColumns=5,
            adjustableColumn=2,
            columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)],
        )
        self._build_subcheck_boxes("vertex_colors_checked")
        cmds.text(label="Vertex Colors", align="left")
        cmds.button(label="Run Vertex Color Check", height=26, command=lambda *_: self.check_vertex_colors())
        cmds.button(label="Display Vertex Color", height=26, command=lambda *_: self.display_vertex_colors())
        cmds.button(label="Hide Vertex Color", height=26, command=lambda *_: self.hide_vertex_colors())
        cmds.setParent("..")
        cmds.text(label="Manual note: confirm Color ID readability for future bake.", align="left")
        cmds.separator(style="in")
        cmds.text(label="Step 05 — Namespaces", align="left")
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self._build_subcheck_boxes("no_namespaces")
        cmds.text(label="Only tool namespaces should remain", align="left")
        cmds.button(label="Scan Namespaces", height=26, command=lambda *_: self.scan_namespaces())
        cmds.button(label="Remove Invalid Namespaces", height=26, command=lambda *_: self.remove_namespaces())
        cmds.setParent("..")
        cmds.separator(style="in")
        cmds.text(label="Step 06 — Materials / Texture Sets", align="left")
        self._build_manual_root_selector("materials_high_root_menu", "Select High Root for Materials / Texture Sets", "high_ma")
        self._build_subcheck_boxes("texture_sets_analyzed")
        cmds.button(label="Run Analyze Materials", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.analyze_texture_sets(mode="materials"))
        self.ui["texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=130,
            selectCommand=lambda *_: self.on_texture_set_selection_changed("high"),
        )
        cmds.button(label="Isolate Material", height=26, command=lambda *_: self.toggle_isolate_selected_material("high"))
        cmds.separator(style="in")
        cmds.text(label="Step 07 — Compare High.ma vs High.fbx", align="left")
        self._build_manual_root_selector("compare_ma_root_menu", "Select High.ma Root", "high_ma")
        self._build_manual_root_selector("compare_fbx_root_menu", "Select High.fbx Root", "high_fbx")
        self._build_subcheck_boxes("ma_fbx_compared")
        self.ui["compare_ma_fbx_global_mode"] = cmds.checkBox(label="Global", value=False)
        cmds.button(label="Run Compare", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.compare_ma_vs_fbx())
        cmds.separator(style="in")
        cmds.text(label="Step 08 — Compare High.ma vs Bake Scene High", align="left")
        self._build_manual_root_selector("compare_bake_ma_root_menu", "Select High.ma Root", "high_ma")
        self._build_manual_root_selector("compare_bake_high_root_menu", "Select Bake High Root", "bake_high")
        self._build_subcheck_boxes("ma_bake_compared")
        self.ui["compare_ma_bake_global_mode"] = cmds.checkBox(label="Global", value=False)
        cmds.button(label="Run Compare Bake", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.compare_ma_vs_bake_high())
        cmds.setParent("..")
        cmds.setParent("..")
    def _build_guided_high_review_section(self) -> None:
        self._build_technical_checks_section()
        self._build_global_action_section()

    def _build_review_tabs_section(self) -> None:
        cmds.frameLayout(label="2) Guided Reviews", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SECTION)
        split = cmds.formLayout()
        sidebar_host = cmds.columnLayout(adjustableColumn=True, width=250)
        cmds.setParent(split)
        self.ui["review_scroll"] = cmds.scrollLayout(
            childResizable=True,
            horizontalScrollBarThickness=0,
            verticalScrollBarThickness=12,
        )
        tabs_host = cmds.columnLayout(adjustableColumn=True)
        tabs = cmds.tabLayout(innerMarginWidth=6, innerMarginHeight=6, changeCommand=lambda *_: self._on_review_tab_changed())
        self.ui["review_tabs"] = tabs

        high_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_high_review_section()
        cmds.setParent("..")

        low_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_low_review_section()
        cmds.setParent("..")

        bake_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_bake_review_section()
        cmds.setParent("..")

        final_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_final_asset_review_section()
        cmds.setParent("..")

        integration_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_integration_review_section()
        cmds.setParent("..")

        cmds.tabLayout(
            tabs,
            edit=True,
            tabsVisible=False,
            tabLabel=(
                (high_tab, "Review 01 — High"),
                (low_tab, "Review 02 — Low"),
                (bake_tab, "Review 03 — Bake Scene"),
                (final_tab, "Review 04 — Final Asset"),
                (integration_tab, "Review 05 — Integration"),
            ),
        )
        self.review_tab_children = {
            "high": high_tab,
            "low": low_tab,
            "bake": bake_tab,
            "final_asset": final_tab,
            "integration": integration_tab,
        }
        self.review_tab_order = ["high", "low", "bake", "final_asset", "integration"]
        self._build_qt_sidebar(sidebar_host)
        self._set_active_review_button("high")
        cmds.formLayout(
            split,
            edit=True,
            attachForm=[
                (sidebar_host, "top", 0),
                (sidebar_host, "left", 0),
                (sidebar_host, "bottom", 0),
                (self.ui["review_scroll"], "top", 0),
                (self.ui["review_scroll"], "right", 0),
                (self.ui["review_scroll"], "bottom", 0),
            ],
            attachControl=[(self.ui["review_scroll"], "left", 10, sidebar_host)],
        )
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_qt_sidebar(self, qt_host_layout: str) -> None:
        if not QT_AVAILABLE or QtWidgets is None or wrapInstance is None:
            return
        host_ptr = omui.MQtUtil.findLayout(qt_host_layout)
        if not host_ptr:
            return
        host_widget = wrapInstance(int(host_ptr), QtWidgets.QWidget)
        if host_widget is None:
            return
        host_layout = host_widget.layout()
        if host_layout is None:
            host_layout = QtWidgets.QVBoxLayout(host_widget)
        while host_layout.count():
            item = host_layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.deleteLater()

        panel = QtWidgets.QFrame()
        panel.setObjectName("MainSidebarPanel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(s(12), s(14), s(12), s(14))
        panel_layout.setSpacing(s(12))

        section_review = QtWidgets.QLabel("REVIEW")
        section_review.setObjectName("SidebarSectionLabel")
        panel_layout.addWidget(section_review)

        self.review_nav_buttons = {}
        nav_entries = [
            ("high", "High"),
            ("low", "Low"),
            ("bake", "Bake"),
            ("final_asset", "Final Asset"),
            ("integration", "Integration"),
        ]
        for key, label in nav_entries:
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("SidebarReviewButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, k=key: self._on_sidebar_review_clicked(k))
            self.review_nav_buttons[key] = btn
            panel_layout.addWidget(btn)

        panel_layout.addSpacing(s(6))
        tools_label = QtWidgets.QLabel("TOOLS")
        tools_label.setObjectName("SidebarSectionLabel")
        panel_layout.addWidget(tools_label)
        for label in ("Scene Visibility", "Logs & Report"):
            tool_btn = QtWidgets.QPushButton(label)
            tool_btn.setObjectName("SidebarToolButton")
            tool_btn.setEnabled(False)
            panel_layout.addWidget(tool_btn)

        panel_layout.addSpacing(s(6))
        summary_header = QtWidgets.QLabel("REVIEW SUMMARY")
        summary_header.setObjectName("SidebarSectionLabel")
        panel_layout.addWidget(summary_header)

        self.sidebar_summary_labels = {}
        summary_rows = [
            ("passed", "Passed"),
            ("warnings", "Warnings"),
            ("failed", "Failed"),
            ("pending", "Pending"),
            ("total", "Total Checks"),
        ]
        for key, label in summary_rows:
            row = QtWidgets.QHBoxLayout()
            name = QtWidgets.QLabel(label)
            name.setObjectName("SidebarSummaryName")
            value = QtWidgets.QLabel("0")
            value.setObjectName("SidebarSummaryValue")
            value.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            row.addWidget(name)
            row.addStretch(1)
            row.addWidget(value)
            panel_layout.addLayout(row)
            self.sidebar_summary_labels[key] = value

        panel_layout.addStretch(1)
        panel.setStyleSheet(
            _resolve_scaled_tokens(
                """
QFrame#MainSidebarPanel {
    background-color: #0b1320;
    border: 1px solid #1b2a40;
    border-radius: {s(12)}px;
}
QLabel#SidebarSectionLabel {
    color: #7186a8;
    font-size: {s(12)}px;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding-top: {s(2)}px;
}
QPushButton#SidebarReviewButton {
    text-align: left;
    padding: {s(10)}px {s(12)}px;
    border-radius: {s(8)}px;
    border: 1px solid transparent;
    background-color: #121d2e;
    color: #c2d4ef;
    font-size: {s(14)}px;
    font-weight: 600;
}
QPushButton#SidebarReviewButton:hover {
    background-color: #1a2a42;
}
QPushButton#SidebarReviewButton:checked {
    background-color: #2b6fd4;
    border: 1px solid #4d87dd;
    color: #ffffff;
}
QPushButton#SidebarToolButton {
    text-align: left;
    padding: {s(8)}px {s(12)}px;
    border-radius: {s(8)}px;
    border: 1px solid #1d2d45;
    background-color: #101a2a;
    color: #8fa3c4;
    font-size: {s(13)}px;
}
QLabel#SidebarSummaryName {
    color: #a9bddc;
    font-size: {s(13)}px;
}
QLabel#SidebarSummaryValue {
    color: #d8e6ff;
    font-size: {s(13)}px;
    font-weight: 700;
}
"""
            )
        )
        host_layout.addWidget(panel, 0, QtCore.Qt.AlignTop)

    def _on_sidebar_review_clicked(self, review_key: str) -> None:
        tabs = self.ui.get("review_tabs")
        child = self.review_tab_children.get(review_key)
        if not tabs or not child:
            return
        if cmds.tabLayout(tabs, exists=True):
            cmds.tabLayout(tabs, edit=True, selectTab=child)
        self._set_active_review_button(review_key)
        self._reset_main_scroll_to_top()

    def _on_review_tab_changed(self) -> None:
        tabs = self.ui.get("review_tabs")
        if not tabs or not cmds.tabLayout(tabs, exists=True):
            return
        active_child = cmds.tabLayout(tabs, query=True, selectTab=True)
        if active_child:
            for key, child in self.review_tab_children.items():
                if child == active_child:
                    self._set_active_review_button(key)
                    break
        self._reset_main_scroll_to_top()

    def _set_active_review_button(self, active_key: str) -> None:
        for key, button in self.review_nav_buttons.items():
            button.setChecked(key == active_key)

    def _reset_main_scroll_to_top(self) -> None:
        """Reset the Guided Review scrollLayout to the top after tab changes."""
        scroll_layout = self.ui.get("review_scroll")
        if scroll_layout and cmds.scrollLayout(scroll_layout, exists=True):
            cmds.scrollLayout(scroll_layout, edit=True, scrollByPixel=("up", 99999999))

    def _build_guided_low_review_section(self) -> None:
        if QT_AVAILABLE and QtWidgets is not None:
            cmds.frameLayout(label="Review 02 — Low", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
            cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
            self._build_tab_visibility_controls("low")
            cmds.text(label="Guided review of the Low.fbx delivery.", align="left")

            self._build_qt_step_card(1, "Topology Check", lambda body: (
                self._add_qt_root_selector_row(body, "low_topology_root_menu", "Low Root (Topology)", "low_fbx"),
                body.addWidget(self._create_qt_subcheck_band("low_topology_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run Topology", self.run_low_topology_checks)),
            ))

            def _low_ns_body(body):
                band, lay = self._create_qt_subcheck_band("low_namespaces_checked")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Run Namespace Check", self.scan_low_namespaces))
                lay.addWidget(self._make_qt_run_button("Remove Invalid Namespaces", self.remove_low_namespaces))
                body.addWidget(band)
            self._build_qt_step_card(2, "Namespaces", _low_ns_body)

            def _low_mat_body(body):
                self._add_qt_root_selector_row(body, "low_materials_root_menu", "Low Root (Materials)", "low_fbx")
                band, lay = self._create_qt_subcheck_band("low_materials_checked")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Analyze Materials", self.analyze_low_materials))
                body.addWidget(band)
                lst = QtWidgets.QListWidget()
                lst.setObjectName("StepListWidget")
                lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                lst.itemSelectionChanged.connect(lambda: self.on_texture_set_selection_changed("low"))
                self.ui["low_texture_sets_list"] = lst
                body.addWidget(lst)
                body.addWidget(self._make_qt_run_button("Isolate Material", lambda: self.toggle_isolate_selected_material("low")))
            self._build_qt_step_card(3, "Materials / Texture Sets", _low_mat_body)

            self._build_qt_step_card(4, "UV Check map1", lambda body: (
                self._add_qt_root_selector_row(body, "low_uv1_root_menu", "Low Root (UV map1)", "low_fbx"),
                body.addWidget(self._create_qt_subcheck_band("low_uv_map1_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run UV Map1 Check", self.run_low_uv_map1_check)),
            ))
            self._build_qt_step_card(5, "UV map2 / Texel Density", lambda body: (
                self._add_qt_root_selector_row(body, "low_uv2_root_menu", "Low Root (UV map2)", "low_fbx"),
                body.addWidget(self._create_qt_subcheck_band("low_uv_map2_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run UV Map2 Check", self.run_low_map2_density_check)),
            ))

            def _low_bake_cmp(body):
                self._add_qt_root_selector_row(body, "compare_low_bake_low_root_menu", "Low.fbx Root", "low_fbx")
                self._add_qt_root_selector_row(body, "compare_low_bake_bake_root_menu", "Bake Low Root", "bake_low")
                band, lay = self._create_qt_subcheck_band("low_bake_compared")
                lay.addStretch(1)
                glb = QtWidgets.QCheckBox("Global")
                glb.setObjectName("GlobalToggleBox")
                glb.setChecked(False)
                self.ui["compare_low_bake_global_mode"] = glb
                lay.addWidget(glb)
                lay.addWidget(self._make_qt_run_button("Run Compare Bake", self.compare_low_vs_bake_low))
                body.addWidget(band)
            self._build_qt_step_card(6, "Compare Low.fbx vs Bake Scene Low", _low_bake_cmp)

            def _low_final_cmp(body):
                self._add_qt_root_selector_row(body, "compare_low_final_low_root_menu", "Low.fbx Root", "low_fbx")
                self._add_qt_root_selector_row(body, "compare_low_final_final_root_menu", "Final Scene Root", "final_ma")
                band, lay = self._create_qt_subcheck_band("low_final_compared")
                lay.addStretch(1)
                glb = QtWidgets.QCheckBox("Global")
                glb.setObjectName("GlobalToggleBox")
                glb.setChecked(True)
                self.ui["compare_low_final_global_mode"] = glb
                lay.addWidget(glb)
                lay.addWidget(self._make_qt_run_button("Run Compare Final Asset", self.compare_low_vs_final_asset))
                body.addWidget(band)
            self._build_qt_step_card(7, "Compare Low.fbx vs Final Scene Asset", _low_final_cmp)
            cmds.setParent("..")
            cmds.setParent("..")
            return
        cmds.frameLayout(label="Review 02 — Low", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self._build_tab_visibility_controls("low")
        cmds.text(label="Guided review of the Low.fbx delivery.", align="left")
        cmds.separator(style="in")
        cmds.text(label="Step 01 — Topology Check", align="left")
        self._build_manual_root_selector("low_topology_root_menu", "Select Low Root for Topology Check", "low_fbx")
        self._build_check_row("check_low_topology", "low_topology_checked", "Topology", self.run_low_topology_checks)
        cmds.separator(style="in")

        cmds.text(label="Step 02 — Namespaces", align="left")
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_low_ns"] = cmds.checkBox(label="", value=False, changeCommand=lambda *_: self.on_manual_check_toggle("low_namespaces_checked"))
        cmds.text(label="Only low review namespaces should remain", align="left")
        cmds.button(label="Run Namespace Check", height=26, command=lambda *_: self.scan_low_namespaces())
        cmds.button(label="Remove Invalid Namespaces", height=26, command=lambda *_: self.remove_low_namespaces())
        cmds.setParent("..")
        cmds.separator(style="in")

        cmds.text(label="Step 03 — Materials / Texture Sets", align="left")
        self._build_manual_root_selector("low_materials_root_menu", "Select Low Root for Materials / Texture Sets", "low_fbx")
        self._build_check_row("check_low_materials", "low_materials_checked", "Analyze Materials", self.analyze_low_materials)
        self.ui["low_texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=130,
            selectCommand=lambda *_: self.on_texture_set_selection_changed("low"),
        )
        cmds.button(label="Isolate Material", height=26, command=lambda *_: self.toggle_isolate_selected_material("low"))
        cmds.separator(style="in")

        cmds.text(label="Step 04 — UV Check map1", align="left")
        self._build_manual_root_selector("low_uv1_root_menu", "Select Low Root for UV map1 Check", "low_fbx")
        self._build_check_row("check_low_uv_map1", "low_uv_map1_checked", "UV Map1 Check", self.run_low_uv_map1_check)
        cmds.separator(style="in")

        cmds.text(label="Step 05 — UV map2 / Texel Density", align="left")
        self._build_manual_root_selector("low_uv2_root_menu", "Select Low Root for UV map2 / TD Check", "low_fbx")
        self._build_check_row("check_low_uv_map2", "low_uv_map2_checked", "UV Map2 Check", self.run_low_map2_density_check)
        cmds.separator(style="in")

        cmds.text(label="Step 06 — Compare Low.fbx vs Bake Scene Low", align="left")
        self._build_manual_root_selector("compare_low_bake_low_root_menu", "Select Low.fbx Root", "low_fbx")
        self._build_manual_root_selector("compare_low_bake_bake_root_menu", "Select Bake Low Root", "bake_low")
        self._build_compare_row(
            "check_low_bake",
            "low_bake_compared",
            "Run Compare Bake",
            self.compare_low_vs_bake_low,
            "compare_low_bake_global_mode",
            default_global=False,
        )
        cmds.separator(style="in")

        cmds.text(label="Step 07 — Compare Low.fbx vs Final Scene Asset", align="left")
        self._build_manual_root_selector("compare_low_final_low_root_menu", "Select Low.fbx Root", "low_fbx")
        self._build_manual_root_selector("compare_low_final_final_root_menu", "Select Final Scene Root", "final_ma")
        self._build_compare_row(
            "check_low_final",
            "low_final_compared",
            "Run Compare Final Asset",
            self.compare_low_vs_final_asset,
            "compare_low_final_global_mode",
            default_global=True,
        )

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_guided_bake_review_section(self) -> None:
        if QT_AVAILABLE and QtWidgets is not None:
            cmds.frameLayout(label="Review 03 — Bake Scene", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
            cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
            self._build_tab_visibility_controls("bake")
            cmds.text(label="Guided review of the Bake Scene.", align="left")
            self._build_qt_step_card(1, "Bake Scene Structure", lambda body: (
                self._add_qt_root_selector_row(body, "bake_structure_high_root_menu", "Bake High Root", "bake_high"),
                self._add_qt_root_selector_row(body, "bake_structure_low_root_menu", "Bake Low Root", "bake_low"),
                body.addWidget(self._create_qt_subcheck_band("bake_structure_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run Structure Check", self.check_bake_scene_structure)),
            ))
            self._build_qt_step_card(2, "Low Topology Check", lambda body: (
                self._add_qt_root_selector_row(body, "bake_low_topology_root_menu", "Bake Low Root (Topology)", "bake_low"),
                body.addWidget(self._create_qt_subcheck_band("bake_low_topology_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run Low Topology Check", self.run_bake_low_topology_checks)),
            ))
            self._build_qt_step_card(3, "Vertex Colors on Bake High", lambda body: (
                self._add_qt_root_selector_row(body, "bake_high_vertex_root_menu", "Bake High Root (Vertex Colors)", "bake_high"),
                body.addWidget(self._create_qt_subcheck_band("bake_high_vertex_colors_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run Vertex Color Check", self.run_bake_high_vertex_color_check)),
                body.addWidget(self._make_qt_run_button("Display Vertex Color", self.display_vertex_colors)),
                body.addWidget(self._make_qt_run_button("Hide Vertex Color", self.hide_vertex_colors)),
            ))

            def _bake_mat_high(body):
                self._add_qt_root_selector_row(body, "bake_high_materials_root_menu", "Bake High Root (Materials)", "bake_high")
                body.addWidget(self._create_qt_subcheck_band("bake_high_materials_checked")[0])
                body.addWidget(self._make_qt_run_button("Analyze Materials", self.analyze_bake_high_materials))
                lst = QtWidgets.QListWidget()
                lst.setObjectName("StepListWidget")
                lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                lst.itemSelectionChanged.connect(lambda: self.on_texture_set_selection_changed("bake_high"))
                self.ui["bake_high_texture_sets_list"] = lst
                body.addWidget(lst)
                body.addWidget(self._make_qt_run_button("Isolate Material", lambda: self.toggle_isolate_selected_material("bake_high")))
            self._build_qt_step_card(4, "Materials on Bake High", _bake_mat_high)

            def _bake_mat_low(body):
                self._add_qt_root_selector_row(body, "bake_low_materials_root_menu", "Bake Low Root (Materials)", "bake_low")
                body.addWidget(self._create_qt_subcheck_band("bake_low_materials_checked")[0])
                body.addWidget(self._make_qt_run_button("Analyze Materials", self.analyze_bake_low_materials))
                lst = QtWidgets.QListWidget()
                lst.setObjectName("StepListWidget")
                lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                lst.itemSelectionChanged.connect(lambda: self.on_texture_set_selection_changed("bake_low"))
                self.ui["bake_low_texture_sets_list"] = lst
                body.addWidget(lst)
                body.addWidget(self._make_qt_run_button("Isolate Material", lambda: self.toggle_isolate_selected_material("bake_low")))
            self._build_qt_step_card(5, "Materials on Bake Low", _bake_mat_low)

            self._build_qt_step_card(6, "UV Check Map 1 on Bake Low", lambda body: (
                self._add_qt_root_selector_row(body, "bake_low_uv1_root_menu", "Bake Low Root (UV map1)", "bake_low"),
                body.addWidget(self._create_qt_subcheck_band("bake_low_uv_map1_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run UV Map1 Check", self.run_bake_low_uv_map1_check)),
            ))
            self._build_qt_step_card(7, "UV Check Map 2 on Bake Low", lambda body: (
                self._add_qt_root_selector_row(body, "bake_low_uv2_root_menu", "Bake Low Root (UV map2)", "bake_low"),
                body.addWidget(self._create_qt_subcheck_band("bake_low_uv_map2_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run UV Map2 Check", self.run_bake_low_uv_map2_check)),
            ))

            def _pairing_body(body):
                self._add_qt_root_selector_row(body, "bake_pairing_high_root_menu", "Bake High Root", "bake_high")
                self._add_qt_root_selector_row(body, "bake_pairing_low_root_menu", "Bake Low Root", "bake_low")
                body.addWidget(self._create_qt_subcheck_band("bake_pairing_checked")[0])
                row = QtWidgets.QHBoxLayout()
                row.addWidget(self._make_qt_run_button("Check Pairing", self.check_bake_pairing))
                row.addWidget(QtWidgets.QLabel("BBox Scale"))
                spin = QtWidgets.QDoubleSpinBox()
                spin.setObjectName("ToleranceSpin")
                spin.setRange(1.0, 10.0)
                spin.setDecimals(3)
                spin.setSingleStep(0.01)
                spin.setValue(1.05)
                self.ui["bake_pairing_bbox_scale"] = spin
                row.addWidget(spin)
                row.addStretch(1)
                body.addLayout(row)
            self._build_qt_step_card(8, "Naming & Pairing", _pairing_body)

            self._build_qt_step_card(9, "Bake Readiness", lambda body: (
                self._add_qt_root_selector_row(body, "bake_ready_high_root_menu", "Bake High Root", "bake_high"),
                self._add_qt_root_selector_row(body, "bake_ready_low_root_menu", "Bake Low Root", "bake_low"),
                body.addWidget(self._create_qt_subcheck_band("bake_ready_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run Bake Validation", self.check_bake_readiness)),
            ))
            cmds.setParent("..")
            cmds.setParent("..")
            return
        cmds.frameLayout(label="Review 03 — Bake Scene", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self._build_tab_visibility_controls("bake")

        cmds.text(label="Guided review of the Bake Scene.", align="left")
        cmds.separator(style="in")

        cmds.text(label="Step 01 — Bake Scene Structure", align="left")
        self._build_manual_root_selector("bake_structure_high_root_menu", "Select Bake High Root", "bake_high")
        self._build_manual_root_selector("bake_structure_low_root_menu", "Select Bake Low Root", "bake_low")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui["check_bake_structure"] = cmds.checkBox(label="", value=False, changeCommand=lambda *_: self.on_manual_check_toggle("bake_structure_checked"))
        cmds.text(label="Bake High / Low structure", align="left")
        cmds.button(label="Run Structure Check", height=26, command=lambda *_: self.check_bake_scene_structure())
        cmds.setParent("..")

        cmds.separator(style="in")
        cmds.text(label="Step 02 — Low Topology Check", align="left")
        self._build_manual_root_selector("bake_low_topology_root_menu", "Select Bake Low Root for Topology Check", "bake_low")
        self._build_check_row("check_bake_low_topology", "bake_low_topology_checked", "Low Topology Check", self.run_bake_low_topology_checks)

        cmds.separator(style="in")
        cmds.text(label="Step 03 — Vertex Colors on Bake High", align="left")
        self._build_manual_root_selector("bake_high_vertex_root_menu", "Select Bake High Root for Vertex Color Check", "bake_high")
        cmds.rowLayout(
            numberOfColumns=5,
            adjustableColumn=2,
            columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)],
        )
        self.ui["check_bake_high_vertex_colors"] = cmds.checkBox(
            label="",
            value=False,
            changeCommand=lambda *_: self.on_manual_check_toggle("bake_high_vertex_colors_checked"),
        )
        cmds.text(label="Vertex Colors (Bake High)", align="left")
        cmds.button(label="Run Vertex Color Check", height=26, command=lambda *_: self.run_bake_high_vertex_color_check())
        cmds.button(label="Display Vertex Color", height=26, command=lambda *_: self.display_vertex_colors())
        cmds.button(label="Hide Vertex Color", height=26, command=lambda *_: self.hide_vertex_colors())
        cmds.setParent("..")

        cmds.separator(style="in")
        cmds.text(label="Step 04 — Materials on Bake High", align="left")
        self._build_manual_root_selector("bake_high_materials_root_menu", "Select Bake High Root for Materials / Texture Sets", "bake_high")
        self._build_check_row("check_bake_high_materials", "bake_high_materials_checked", "Analyze Materials", self.analyze_bake_high_materials)
        self.ui["bake_high_texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=130,
            selectCommand=lambda *_: self.on_texture_set_selection_changed("bake_high"),
        )
        cmds.button(label="Isolate Material", height=26, command=lambda *_: self.toggle_isolate_selected_material("bake_high"))

        cmds.separator(style="in")
        cmds.text(label="Step 05 — Materials on Bake Low", align="left")
        self._build_manual_root_selector("bake_low_materials_root_menu", "Select Bake Low Root for Materials / Texture Sets", "bake_low")
        self._build_check_row("check_bake_low_materials", "bake_low_materials_checked", "Analyze Materials", self.analyze_bake_low_materials)
        self.ui["bake_low_texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=130,
            selectCommand=lambda *_: self.on_texture_set_selection_changed("bake_low"),
        )
        cmds.button(label="Isolate Material", height=26, command=lambda *_: self.toggle_isolate_selected_material("bake_low"))

        cmds.separator(style="in")
        cmds.text(label="Step 06 — UV Check Map 1 on Bake Low", align="left")
        self._build_manual_root_selector("bake_low_uv1_root_menu", "Select Bake Low Root for UV map1 Check", "bake_low")
        self._build_check_row("check_bake_low_uv_map1", "bake_low_uv_map1_checked", "UV Map1 Check", self.run_bake_low_uv_map1_check)

        cmds.separator(style="in")
        cmds.text(label="Step 07 — UV Check Map 2 on Bake Low", align="left")
        self._build_manual_root_selector("bake_low_uv2_root_menu", "Select Bake Low Root for UV map2 / TD Check", "bake_low")
        self._build_check_row("check_bake_low_uv_map2", "bake_low_uv_map2_checked", "UV Map2 Check", self.run_bake_low_uv_map2_check)

        cmds.separator(style="in")
        cmds.text(label="Step 08 — Naming & Pairing", align="left")
        self._build_manual_root_selector("bake_pairing_high_root_menu", "Select Bake High Root", "bake_high")
        self._build_manual_root_selector("bake_pairing_low_root_menu", "Select Bake Low Root", "bake_low")
        cmds.rowLayout(
            numberOfColumns=5,
            adjustableColumn=2,
            columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)],
        )
        self.ui["check_bake_pairing"] = cmds.checkBox(label="", value=False, changeCommand=lambda *_: self.on_manual_check_toggle("bake_pairing_checked"))
        cmds.text(label="High ↔ Low pairing", align="left")
        cmds.button(label="Check Pairing", height=26, command=lambda *_: self.check_bake_pairing())
        cmds.text(label="BBox Scale", align="right")
        self.ui["bake_pairing_bbox_scale"] = cmds.floatField(
            minValue=1.0,
            value=1.05,
            precision=3,
            step=0.01,
            width=70,
        )
        cmds.setParent("..")

        cmds.separator(style="in")
        cmds.text(label="Step 09 — Bake Readiness", align="left")
        self._build_manual_root_selector("bake_ready_high_root_menu", "Select Bake High Root", "bake_high")
        self._build_manual_root_selector("bake_ready_low_root_menu", "Select Bake Low Root", "bake_low")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui["check_bake_ready"] = cmds.checkBox(label="", value=False, changeCommand=lambda *_: self.on_manual_check_toggle("bake_ready_checked"))
        cmds.text(label="Bake validation", align="left")
        cmds.button(label="Run Bake Validation", height=26, command=lambda *_: self.check_bake_readiness())
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_guided_final_asset_review_section(self) -> None:
        if QT_AVAILABLE and QtWidgets is not None:
            cmds.frameLayout(label="Review 04 — Final Asset", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
            cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
            self._build_tab_visibility_controls("final_asset")
            cmds.text(label="Guided review of the Final Asset delivery.", align="left")
            self._build_qt_step_card(1, "Topology Check", lambda body: (
                self._add_qt_root_selector_row(body, "final_topology_root_menu", "Final Asset MA Root (Topology)", "final_ma"),
                body.addWidget(self._create_qt_subcheck_band("final_topology_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run Topology", self.run_final_asset_topology_checks)),
            ))

            def _final_ns_body(body):
                band, lay = self._create_qt_subcheck_band("final_namespaces_checked")
                lay.addStretch(1)
                lay.addWidget(self._make_qt_run_button("Run Namespace Check", self.scan_final_asset_namespaces))
                lay.addWidget(self._make_qt_run_button("Remove Invalid Namespaces", self.remove_final_asset_namespaces))
                body.addWidget(band)
            self._build_qt_step_card(2, "Namespaces", _final_ns_body)

            def _final_mat_body(body):
                self._add_qt_root_selector_row(body, "final_materials_root_menu", "Final Asset MA Root (Materials)", "final_ma")
                body.addWidget(self._create_qt_subcheck_band("final_materials_checked")[0])
                body.addWidget(self._make_qt_run_button("Analyze Materials", self.analyze_final_asset_materials))
                lst = QtWidgets.QListWidget()
                lst.setObjectName("StepListWidget")
                lst.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
                lst.itemSelectionChanged.connect(lambda: self.on_texture_set_selection_changed("final_asset"))
                self.ui["final_texture_sets_list"] = lst
                body.addWidget(lst)
                body.addWidget(self._make_qt_run_button("Isolate Material", lambda: self.toggle_isolate_selected_material("final_asset")))
            self._build_qt_step_card(3, "Materials / Texture Sets", _final_mat_body)

            self._build_qt_step_card(4, "UV Check Map 1", lambda body: (
                self._add_qt_root_selector_row(body, "final_uv1_root_menu", "Final Asset MA Root (UV map1)", "final_ma"),
                body.addWidget(self._create_qt_subcheck_band("final_uv_map1_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run UV Map1 Check", self.run_final_asset_uv_map1_check)),
            ))
            self._build_qt_step_card(5, "UV Check Map 2", lambda body: (
                self._add_qt_root_selector_row(body, "final_uv2_root_menu", "Final Asset MA Root (UV map2)", "final_ma"),
                body.addWidget(self._create_qt_subcheck_band("final_uv_map2_checked")[0]),
                body.addWidget(self._make_qt_run_button("Run UV Map2 Check", self.run_final_asset_uv_map2_check)),
            ))

            def _final_cmp(body):
                self._add_qt_root_selector_row(body, "compare_final_ma_root_menu", "Final Asset .ma Root", "final_ma")
                self._add_qt_root_selector_row(body, "compare_final_fbx_root_menu", "Final Asset .fbx Root", "final_fbx")
                band, lay = self._create_qt_subcheck_band("final_ma_fbx_compared")
                lay.addStretch(1)
                glb = QtWidgets.QCheckBox("Global")
                glb.setObjectName("GlobalToggleBox")
                glb.setChecked(True)
                self.ui["compare_final_ma_fbx_global_mode"] = glb
                lay.addWidget(glb)
                lay.addWidget(self._make_qt_run_button("Run Compare", self.compare_final_asset_ma_vs_fbx))
                body.addWidget(band)
            self._build_qt_step_card(6, "Compare Final Asset .ma vs Final Asset .fbx", _final_cmp)
            cmds.setParent("..")
            cmds.setParent("..")
            return
        cmds.frameLayout(label="Review 04 — Final Asset", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self._build_tab_visibility_controls("final_asset")
        cmds.text(label="Guided review of the Final Asset delivery.", align="left")
        cmds.separator(style="in")

        cmds.text(label="Step 01 — Topology Check", align="left")
        self._build_manual_root_selector("final_topology_root_menu", "Select Final Asset MA Root for Topology Check", "final_ma")
        self._build_check_row("check_final_topology", "final_topology_checked", "Topology", self.run_final_asset_topology_checks)
        cmds.separator(style="in")

        cmds.text(label="Step 02 — Namespaces", align="left")
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_final_ns"] = cmds.checkBox(label="", value=False, changeCommand=lambda *_: self.on_manual_check_toggle("final_namespaces_checked"))
        cmds.text(label="Only final asset review namespaces should remain", align="left")
        cmds.button(label="Run Namespace Check", height=26, command=lambda *_: self.scan_final_asset_namespaces())
        cmds.button(label="Remove Invalid Namespaces", height=26, command=lambda *_: self.remove_final_asset_namespaces())
        cmds.setParent("..")
        cmds.separator(style="in")

        cmds.text(label="Step 03 — Materials / Texture Sets", align="left")
        self._build_manual_root_selector("final_materials_root_menu", "Select Final Asset MA Root for Materials / Texture Sets", "final_ma")
        self._build_check_row("check_final_materials", "final_materials_checked", "Analyze Materials", self.analyze_final_asset_materials)
        self.ui["final_texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=130,
            selectCommand=lambda *_: self.on_texture_set_selection_changed("final_asset"),
        )
        cmds.button(label="Isolate Material", height=26, command=lambda *_: self.toggle_isolate_selected_material("final_asset"))
        cmds.separator(style="in")

        cmds.text(label="Step 04 — UV Check Map 1", align="left")
        self._build_manual_root_selector("final_uv1_root_menu", "Select Final Asset MA Root for UV map1 Check", "final_ma")
        self._build_check_row("check_final_uv_map1", "final_uv_map1_checked", "UV Map1 Check", self.run_final_asset_uv_map1_check)
        cmds.separator(style="in")

        cmds.text(label="Step 05 — UV Check Map 2", align="left")
        self._build_manual_root_selector("final_uv2_root_menu", "Select Final Asset MA Root for UV map2 / TD Check", "final_ma")
        self._build_check_row("check_final_uv_map2", "final_uv_map2_checked", "UV Map2 Check", self.run_final_asset_uv_map2_check)
        cmds.separator(style="in")

        cmds.text(label="Step 06 — Compare Final Asset .ma vs Final Asset .fbx", align="left")
        self._build_manual_root_selector("compare_final_ma_root_menu", "Select Final Asset .ma Root", "final_ma")
        self._build_manual_root_selector("compare_final_fbx_root_menu", "Select Final Asset .fbx Root", "final_fbx")
        self._build_compare_row(
            "check_final_compare",
            "final_ma_fbx_compared",
            "Run Compare",
            self.compare_final_asset_ma_vs_fbx,
            "compare_final_ma_fbx_global_mode",
            default_global=True,
        )

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_guided_integration_review_section(self) -> None:
        cmds.frameLayout(label="Review 05 — Integration", collapsable=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_tab_visibility_controls("final_asset")
        cmds.text(label="Detect catalog assets and update them from Perforce via qdTools.", align="left")
        cmds.separator(style="in")

        cmds.text(label="Step 01 — Detect Scene Assets", align="left")
        cmds.text(label="Scan the full Maya scene and extract principal + annexe asset names.", align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=3, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        cmds.button(label="Detect / Refresh Scene Assets", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.detect_catalog_assets_for_integration())
        cmds.button(label="Select All", height=UI_BUTTON_HEIGHT, command=lambda *_: self.select_all_integration_catalog_assets())
        cmds.button(label="Clear Selection", height=UI_BUTTON_HEIGHT, command=lambda *_: self.clear_integration_catalog_selection())
        cmds.setParent("..")
        cmds.text(label="Main Assets", align="left")
        self.ui["integration_catalog_list"] = cmds.textScrollList(allowMultiSelection=True, height=160)
        cmds.text(label="Annexe", align="left")
        self.ui["integration_annexe_catalog_list"] = cmds.textScrollList(allowMultiSelection=True, height=120)
        cmds.separator(style="in")

        cmds.text(label="Step 02 — Load Selected Asset(s) from P4", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8)])
        cmds.text(label="qdTools category", align="left")
        self.ui["integration_qd_category_menu"] = cmds.optionMenu()
        for category in INTEGRATION_QDTOOLS_CATEGORIES:
            cmds.menuItem(label=category)
        cmds.setParent("..")
        cmds.button(label="Load / Update from P4 (Selected Scene Asset(s))", height=UI_PRIMARY_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT, command=lambda *_: self.update_selected_catalog_assets_from_p4())
        cmds.separator(style="in")

        cmds.text(label="Step 03 — Checkout / Take Rights (manual)", align="left")
        cmds.text(
            label="Before replacing meshes, manually take rights / checkout the loaded P4 assets. Once all loaded assets are writable, validate this step.",
            align="left",
            wordWrap=True,
        )
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
        self.ui["integration_step03_rights_taken"] = cmds.checkBox(label="Rights taken / assets writable", value=False)
        cmds.button(label="Confirm Rights Taken", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.confirm_integration_rights_taken())
        cmds.setParent("..")
        cmds.separator(style="in")

        cmds.text(label="Step 04 — Replace Imported Meshes into P4 Assets", align="left")
        cmds.text(
            label="Replace mesh content from source scene assets (non-prefixed) into loaded P4 assets (prefixed).",
            align="left",
            wordWrap=True,
        )
        cmds.button(
            label="Replace Meshes Into Loaded P4 Assets",
            height=UI_PRIMARY_BUTTON_HEIGHT,
            backgroundColor=UI_COLOR_BG_ACCENT,
            command=lambda *_: self.replace_meshes_into_loaded_p4_assets(),
        )
        cmds.separator(style="in")

        cmds.text(label="Step 05 — Logs / Result", align="left")
        self.ui["integration_logs"] = cmds.textScrollList(allowMultiSelection=False, height=200)

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_check_row(self, check_key_ui: str, check_key: str, label: str, command) -> None:
        if check_key in self.subcheck_definitions:
            cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
            self._build_subcheck_boxes(check_key)
            cmds.button(label=f"Run {label}", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: command())
            cmds.setParent("..")
            return
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui[check_key_ui] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label=label, align="left")
        cmds.button(label=f"Run {label}", height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: command())
        cmds.setParent("..")

    def _build_subcheck_boxes(self, check_key: str) -> None:
        defs = self.subcheck_definitions.get(check_key, [])
        if not defs:
            return
        self.subcheck_ui_map.setdefault(check_key, {})
        cmds.flowLayout(wrap=True, columnSpacing=14)
        for sub_key, sub_label in defs:
            control_key = f"subcheck_{check_key}_{sub_key}"
            cmds.rowLayout(
                numberOfColumns=2,
                adjustableColumn=2,
                columnAttach=[(1, "both", 0), (2, "both", 4)],
            )
            self.ui[control_key] = cmds.checkBox(label="", value=False, enable=False)
            cmds.text(label=sub_label, align="left")
            self.subcheck_ui_map[check_key][sub_key] = control_key
            cmds.setParent("..")
        cmds.setParent("..")

    def _set_boolean_control_value(self, control_key: str, value: bool) -> None:
        control = self.ui.get(control_key)
        if control is None:
            return
        if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QCheckBox):
            control.blockSignals(True)
            control.setChecked(bool(value))
            control.blockSignals(False)
            return
        cmds.checkBox(control, e=True, value=bool(value))

    def _query_boolean_control_value(self, control_key: str, default: bool = False) -> bool:
        control = self.ui.get(control_key)
        if control is None:
            return default
        if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QCheckBox):
            return bool(control.isChecked())
        try:
            return bool(cmds.checkBox(control, q=True, value=True))
        except RuntimeError:
            return default

    def _clear_list_control(self, list_ui_key: str) -> None:
        control = self.ui.get(list_ui_key)
        if control is None:
            return
        if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QListWidget):
            control.clear()
            return
        cmds.textScrollList(control, edit=True, removeAll=True)

    def _append_list_control_item(self, list_ui_key: str, label: str) -> None:
        control = self.ui.get(list_ui_key)
        if control is None:
            return
        if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QListWidget):
            control.addItem(label)
            return
        cmds.textScrollList(control, edit=True, append=label)

    def _selected_list_control_items(self, list_ui_key: str) -> List[str]:
        control = self.ui.get(list_ui_key)
        if control is None:
            return []
        if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QListWidget):
            return [it.text() for it in control.selectedItems()]
        return cmds.textScrollList(control, query=True, selectItem=True) or []

    def _set_selected_list_control_items(self, list_ui_key: str, labels: List[str]) -> None:
        control = self.ui.get(list_ui_key)
        if control is None or not labels:
            return
        if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QListWidget):
            lookup = set(labels)
            for i in range(control.count()):
                item = control.item(i)
                item.setSelected(item.text() in lookup)
            return
        cmds.textScrollList(control, edit=True, selectItem=labels)

    def _set_subcheck_results(self, check_key: str, results: Dict[str, bool]) -> None:
        if check_key not in self.subcheck_states:
            return
        for sub_key in self.subcheck_states[check_key]:
            if sub_key in results:
                self.subcheck_states[check_key][sub_key] = "OK" if results[sub_key] else "FAIL"
        states = list(self.subcheck_states[check_key].values())
        if states and all(state == "OK" for state in states):
            self.check_states[check_key]["status"] = "OK"
        elif any(state == "FAIL" for state in states):
            self.check_states[check_key]["status"] = "FAIL"
        else:
            self.check_states[check_key]["status"] = "PENDING"
        self.refresh_checklist_ui()

    # --------------------------- Integration (Review 05) ---------------------------
    def _extract_catalog_asset_from_name(self, name: str) -> Optional[str]:
        if not name:
            return None
        short_name = self._short_name(name)
        cleaned = self._strip_namespaces_from_name(short_name).strip("_ ")
        if not cleaned or "_" not in cleaned:
            return None
        cleaned_upper = cleaned.upper()
        if cleaned_upper.endswith(("_HIGH", "_LOW", "_PLACEHOLDER")):
            return None
        if not re.fullmatch(r"[A-Z0-9_]+_[A-Z]", cleaned_upper):
            return None
        return cleaned_upper

    def _refresh_integration_catalog_list_ui(self) -> None:
        self._clear_list_control("integration_catalog_list")
        self._clear_list_control("integration_annexe_catalog_list")
        for catalog_name in self.integration_main_catalog_assets:
            self._append_list_control_item("integration_catalog_list", catalog_name)
        for catalog_name in self.integration_annexe_catalog_assets:
            self._append_list_control_item("integration_annexe_catalog_list", catalog_name)
        if self.integration_main_catalog_assets:
            self._set_selected_list_control_items("integration_catalog_list", self.integration_main_catalog_assets)
        if self.integration_annexe_catalog_assets:
            self._set_selected_list_control_items("integration_annexe_catalog_list", self.integration_annexe_catalog_assets)

    def _append_integration_log(self, message: str) -> None:
        self._append_list_control_item("integration_logs", message)
        self.log("INFO", "Integration", message)

    def _is_prefixed_catalog_asset(self, catalog_name: str) -> bool:
        return bool(catalog_name and catalog_name.startswith(INTEGRATION_QDTOOLS_PREFIXES))

    @staticmethod
    def _is_in_transform_branch(node: str, branch_root: str) -> bool:
        if not node or not branch_root:
            return False
        return node == branch_root or node.startswith(f"{branch_root}|")

    def detect_catalog_assets_for_integration(self) -> List[str]:
        detected: Dict[str, Set[str]] = {}
        annexe_sources: Dict[str, Set[str]] = {}
        skipped_prefixed_branches: Set[str] = set()
        blocked_prefixed_branches: List[str] = []
        transforms = cmds.ls(type="transform", long=True) or []
        transforms.sort(key=lambda path: (path.count("|"), path))
        for node in transforms:
            if not cmds.objExists(node):
                continue
            if any(self._is_in_transform_branch(node, blocked_branch) for blocked_branch in blocked_prefixed_branches):
                continue
            catalog_name = self._extract_catalog_asset_from_name(node)
            if catalog_name:
                if self._is_prefixed_catalog_asset(catalog_name):
                    blocked_prefixed_branches.append(node)
                    skipped_prefixed_branches.add(self._strip_namespaces_from_name(self._short_name(node)))
                    continue
                detected.setdefault(catalog_name, set()).add(node)

        annexe_assets: Set[str] = set()
        for catalog_name, source_nodes in detected.items():
            for source_node in source_nodes:
                pending_children = cmds.listRelatives(source_node, children=True, fullPath=True, type="transform") or []
                while pending_children:
                    child = pending_children.pop()
                    child_catalog = self._extract_catalog_asset_from_name(child)
                    if child_catalog and self._is_prefixed_catalog_asset(child_catalog):
                        skipped_prefixed_branches.add(self._strip_namespaces_from_name(self._short_name(child)))
                        continue
                    if not child_catalog or child_catalog == catalog_name:
                        pending_children.extend(cmds.listRelatives(child, children=True, fullPath=True, type="transform") or [])
                        continue
                    if child_catalog.startswith(f"{catalog_name}_"):
                        # Technical child naming variation of the main asset.
                        pending_children.extend(cmds.listRelatives(child, children=True, fullPath=True, type="transform") or [])
                        continue
                    if child_catalog not in detected:
                        pending_children.extend(cmds.listRelatives(child, children=True, fullPath=True, type="transform") or [])
                        continue
                    annexe_assets.add(child_catalog)
                    annexe_sources.setdefault(child_catalog, set()).add(catalog_name)
                    pending_children.extend(cmds.listRelatives(child, children=True, fullPath=True, type="transform") or [])

        self.integration_catalog_assets = sorted(detected.keys())
        self.integration_annexe_catalog_assets = sorted(annexe_assets)
        self.integration_main_catalog_assets = sorted(set(self.integration_catalog_assets) - annexe_assets)
        self.integration_detection_sources = detected
        self.integration_annexe_sources = annexe_sources
        self._refresh_integration_catalog_list_ui()
        self._clear_list_control("integration_logs")

        for skipped_branch in sorted(skipped_prefixed_branches):
            self._append_integration_log(f"Skipping prefixed loaded branch: {skipped_branch}")

        if not self.integration_main_catalog_assets and not self.integration_annexe_catalog_assets:
            self._append_integration_log("No catalog asset detected in current scene.")
            return []

        self._append_integration_log("Detected main assets:")
        for catalog_name in self.integration_main_catalog_assets:
            self._append_integration_log(f"- {catalog_name}")
        self._append_integration_log("")
        self._append_integration_log("Detected annexe assets:")
        for catalog_name in self.integration_annexe_catalog_assets:
            self._append_integration_log(f"- {catalog_name}")
        return self.integration_catalog_assets[:]

    def _integration_catalog_candidates(self, scene_asset: str) -> List[str]:
        cleaned = self._strip_namespaces_from_name(scene_asset).strip("_ ").upper()
        if not cleaned:
            return []
        return [f"{prefix}{cleaned}" for prefix in INTEGRATION_QDTOOLS_PREFIXES]

    def _integration_remove_prefix(self, catalog_name: str) -> str:
        cleaned = self._strip_namespaces_from_name(catalog_name).strip("_ ").upper()
        for prefix in INTEGRATION_QDTOOLS_PREFIXES:
            if cleaned.startswith(prefix):
                return cleaned[len(prefix):]
        return cleaned

    def _integration_best_asset_root(self, nodes: List[str]) -> Optional[str]:
        existing = [node for node in nodes if node and cmds.objExists(node)]
        if not existing:
            return None
        existing.sort(key=lambda node: (node.count("|"), len(node), node))
        return existing[0]

    def _integration_collect_asset_roots(self, prefixed: bool) -> Dict[str, str]:
        asset_to_nodes: Dict[str, List[str]] = {}
        transforms = cmds.ls(type="transform", long=True) or []
        for node in transforms:
            catalog_name = self._extract_catalog_asset_from_name(node)
            if not catalog_name:
                continue
            is_prefixed = self._is_prefixed_catalog_asset(catalog_name)
            if is_prefixed != prefixed:
                continue
            key = self._integration_remove_prefix(catalog_name) if prefixed else catalog_name
            asset_to_nodes.setdefault(key, []).append(node)
        resolved: Dict[str, str] = {}
        for asset_name, nodes in asset_to_nodes.items():
            best = self._integration_best_asset_root(nodes)
            if best:
                resolved[asset_name] = best
        return resolved

    def _integration_find_mesh_parent(self, loaded_asset_root: str, source_asset_name: str) -> Optional[str]:
        if not loaded_asset_root or not cmds.objExists(loaded_asset_root):
            return None
        target_name = f"{source_asset_name}_MESH".upper()
        candidates = [loaded_asset_root]
        candidates.extend(cmds.listRelatives(loaded_asset_root, allDescendents=True, type="transform", fullPath=True) or [])
        matches: List[str] = []
        for node in candidates:
            short = self._strip_namespaces_from_name(self._short_name(node)).upper()
            if short == target_name:
                matches.append(node)
        if matches:
            matches.sort(key=lambda node: (node.count("|"), len(node), node))
            return matches[0]
        return None

    def _integration_choose_target_container(self, mesh_parent: str) -> Tuple[str, Optional[str]]:
        children = cmds.listRelatives(mesh_parent, children=True, type="transform", fullPath=True) or []
        if not children:
            return mesh_parent, None
        relevant_children: List[str] = []
        for child in children:
            descendants = cmds.listRelatives(child, allDescendents=True, type="transform", fullPath=True) or []
            child_meshes = cmds.listRelatives(child, allDescendents=True, type="mesh", noIntermediate=True, fullPath=True) or []
            direct_meshes = cmds.listRelatives(child, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
            if descendants or child_meshes or direct_meshes:
                relevant_children.append(child)
        if len(relevant_children) == 1:
            selected = relevant_children[0]
            return selected, self._strip_namespaces_from_name(self._short_name(selected))
        hull_candidates = [
            child
            for child in relevant_children
            if self._strip_namespaces_from_name(self._short_name(child)).upper() in {"HULL", "GEO", "GEOMETRY", "MESH"}
        ]
        if len(hull_candidates) == 1:
            selected = hull_candidates[0]
            return selected, self._strip_namespaces_from_name(self._short_name(selected))
        return mesh_parent, None

    def _integration_clear_target_content(self, target_container: str) -> None:
        descendants = cmds.listRelatives(target_container, allDescendents=True, type="transform", fullPath=True) or []
        descendants.sort(key=lambda node: node.count("|"), reverse=True)
        for node in descendants:
            if cmds.objExists(node):
                try:
                    cmds.delete(node)
                except Exception:
                    continue
        direct_mesh_shapes = cmds.listRelatives(target_container, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
        for shape in direct_mesh_shapes:
            if cmds.objExists(shape):
                try:
                    cmds.delete(shape)
                except Exception:
                    continue

    def _integration_copy_source_content(self, source_asset_root: str, target_container: str) -> bool:
        def _mesh_shapes_under(node: str) -> List[str]:
            direct = cmds.listRelatives(node, shapes=True, type="mesh", noIntermediate=True, fullPath=True) or []
            descendants = cmds.listRelatives(node, allDescendents=True, type="mesh", noIntermediate=True, fullPath=True) or []
            merged: List[str] = []
            seen: Set[str] = set()
            for shape in direct + descendants:
                if shape not in seen:
                    seen.add(shape)
                    merged.append(shape)
            return merged

        def _mesh_transforms_under(node: str) -> List[str]:
            transforms: List[str] = []
            seen: Set[str] = set()
            for shape in _mesh_shapes_under(node):
                parents = cmds.listRelatives(shape, parent=True, type="transform", fullPath=True) or []
                for parent in parents:
                    if parent not in seen:
                        seen.add(parent)
                        transforms.append(parent)
            return transforms

        source_mesh_transforms = _mesh_transforms_under(source_asset_root)
        self._append_integration_log(f"[INFO] Source mesh transforms found: {len(source_mesh_transforms)}")
        if not source_mesh_transforms:
            self._append_integration_log("[FAIL] No source mesh transforms found under source asset root.")
            return False

        source_root_prefix = f"{source_asset_root}|"
        copy_roots: Set[str] = set()
        for mesh_transform in source_mesh_transforms:
            if mesh_transform == source_asset_root:
                copy_roots.add(mesh_transform)
                continue
            if not mesh_transform.startswith(source_root_prefix):
                continue
            relative = mesh_transform[len(source_root_prefix):]
            if not relative:
                continue
            first_segment = relative.split("|", 1)[0]
            copy_roots.add(f"{source_asset_root}|{first_segment}")

        ordered_copy_roots = sorted(copy_roots, key=lambda node: (node.count("|"), len(node), node))
        self._append_integration_log(f"[INFO] Source copy roots selected: {len(ordered_copy_roots)}")
        if not ordered_copy_roots:
            self._append_integration_log("[FAIL] Could not resolve source copy roots for mesh duplication.")
            return False

        self._append_integration_log(f"[INFO] Target container found: {target_container}")
        self._append_integration_log("[INFO] Reusing existing target transform without creating nested duplicate")

        copied_nodes = 0
        copied_shapes = 0
        for source_node in ordered_copy_roots:
            if not cmds.objExists(source_node):
                self._append_integration_log(f"[FAIL] Source node no longer exists before duplication: {source_node}")
                continue

            source_shape_count = len(_mesh_shapes_under(source_node))
            self._append_integration_log(f"[INFO] Duplicating source node: {source_node}")
            self._append_integration_log(f"[INFO] Mesh shapes found on source node before copy: {source_shape_count}")
            if source_shape_count == 0:
                self._append_integration_log(f"[WARN] Skipping source node with no mesh shapes: {source_node}")
                continue

            try:
                duplicated = cmds.duplicate(source_node, renameChildren=True) or []
            except Exception as exc:
                self._append_integration_log(f"[FAIL] Could not duplicate source node {source_node}: {exc}")
                continue
            if not duplicated:
                self._append_integration_log(f"[FAIL] Duplicate command returned no nodes for source: {source_node}")
                continue

            dup_root = duplicated[0]
            self._append_integration_log(f"[INFO] Duplicated source node for shape transfer: {dup_root}")

            duplicate_shapes = _mesh_shapes_under(dup_root)
            if not duplicate_shapes:
                self._append_integration_log(f"[WARN] No mesh shape found on duplicated node: {dup_root}")
                try:
                    cmds.delete(dup_root)
                except Exception:
                    pass
                continue

            transferred_from_node = 0
            for dup_shape in duplicate_shapes:
                if not cmds.objExists(dup_shape):
                    continue
                try:
                    parented_shapes = cmds.parent(dup_shape, target_container, shape=True, relative=True) or []
                except Exception as exc:
                    self._append_integration_log(
                        f"[FAIL] Could not inject duplicated shape into target transform ({dup_shape}): {exc}"
                    )
                    continue
                if parented_shapes:
                    transferred_from_node += 1
                    copied_shapes += 1

            try:
                cmds.delete(dup_root)
            except Exception:
                pass

            if transferred_from_node == 0:
                self._append_integration_log(
                    f"[FAIL] Could not inject any mesh shape from duplicated source node: {source_node}"
                )
                continue

            copied_nodes += 1

        if copied_nodes == 0:
            self._append_integration_log("[FAIL] No source mesh content was successfully copied into target.")
            return False
        self._append_integration_log("[INFO] Injecting source mesh content directly into target transform")
        self._append_integration_log(f"[INFO] Total mesh shapes injected: {copied_shapes}")
        return True

    def confirm_integration_rights_taken(self) -> None:
        self.integration_rights_confirmed = True
        self._set_boolean_control_value("integration_step03_rights_taken", True)
        self._append_integration_log("[OK] Step 03 confirmed: rights/checkout taken on loaded P4 assets.")

    def replace_meshes_into_loaded_p4_assets(self) -> None:
        rights_checked = self._query_boolean_control_value("integration_step03_rights_taken", default=False)
        self.integration_rights_confirmed = bool(rights_checked)
        if not rights_checked:
            self._append_integration_log("[WARN] Step 03 is not confirmed. Please take rights/checkout before replacing meshes.")
            return

        source_roots = self._integration_collect_asset_roots(prefixed=False)
        loaded_roots = self._integration_collect_asset_roots(prefixed=True)
        if not loaded_roots:
            self._append_integration_log("[WARN] No loaded P4 prefixed assets found for replacement.")
            return

        replaced_count = 0
        for base_asset_name in sorted(loaded_roots.keys()):
            source_asset_root = source_roots.get(base_asset_name)
            loaded_asset_root = loaded_roots.get(base_asset_name)
            loaded_asset_short = self._strip_namespaces_from_name(self._short_name(loaded_asset_root)) if loaded_asset_root else ""

            if not source_asset_root:
                self._append_integration_log(f"[WARN] No source asset found for loaded P4 asset: {loaded_asset_short}")
                continue
            if not loaded_asset_root:
                continue

            self._append_integration_log(f"[INFO] Source asset found: {base_asset_name}")
            self._append_integration_log(f"[INFO] Loaded P4 asset found: {loaded_asset_short}")
            mesh_parent = self._integration_find_mesh_parent(loaded_asset_root, base_asset_name)
            if not mesh_parent:
                self._append_integration_log(f"[WARN] Target mesh parent not found: {base_asset_name}_MESH")
                continue

            mesh_parent_short = self._strip_namespaces_from_name(self._short_name(mesh_parent))
            self._append_integration_log(f"[INFO] Target mesh parent found: {mesh_parent_short}")
            target_container, sub_parent_name = self._integration_choose_target_container(mesh_parent)
            if sub_parent_name:
                self._append_integration_log(f"[INFO] Target sub-parent found: {sub_parent_name}")
            else:
                self._append_integration_log("[INFO] No dedicated sub-parent found, replacing directly in _MESH")

            self._append_integration_log("[INFO] Removing old mesh content from existing target transform")
            self._integration_clear_target_content(target_container)
            copied = self._integration_copy_source_content(source_asset_root, target_container)
            if copied:
                self._append_integration_log("[OK] Replacement completed while preserving hierarchy")
                self._append_integration_log(f"[OK] Replacement completed for {base_asset_name}")
                replaced_count += 1
            else:
                self._append_integration_log(f"[FAIL] Replacement failed for {base_asset_name}")

        self._append_integration_log(f"[INFO] Mesh replacement finished. Assets replaced: {replaced_count}")

    def select_all_integration_catalog_assets(self) -> None:
        if not self.integration_main_catalog_assets and not self.integration_annexe_catalog_assets:
            return
        self._set_selected_list_control_items("integration_catalog_list", self.integration_main_catalog_assets)
        self._set_selected_list_control_items("integration_annexe_catalog_list", self.integration_annexe_catalog_assets)

    def clear_integration_catalog_selection(self) -> None:
        for ui_key in ("integration_catalog_list", "integration_annexe_catalog_list"):
            control = self.ui.get(ui_key)
            if control is None:
                continue
            if QT_AVAILABLE and QtWidgets is not None and isinstance(control, QtWidgets.QListWidget):
                control.clearSelection()
                continue
            cmds.textScrollList(control, edit=True, deselectAll=True)

    def _selected_integration_qd_category(self) -> str:
        control = self.ui.get("integration_qd_category_menu")
        fallback = INTEGRATION_QDTOOLS_CATEGORIES[0]
        if not control:
            return fallback
        try:
            selected = cmds.optionMenu(control, query=True, value=True)
        except RuntimeError:
            return fallback
        return selected or fallback

    def _ensure_integration_parent_group(self, group_name: str) -> str:
        if cmds.objExists(group_name):
            return group_name
        created = cmds.group(empty=True, name=group_name, world=True)
        self._append_integration_log(f"[INFO] Created group: {created}")
        return created

    def _snapshot_scene_transforms(self) -> Set[str]:
        return set(cmds.ls(type="transform", long=True) or [])

    def _find_loaded_top_nodes(self, before_transforms: Set[str], after_transforms: Set[str]) -> List[str]:
        new_transforms = after_transforms - before_transforms
        if not new_transforms:
            return []
        top_nodes: List[str] = []
        for node in sorted(new_transforms):
            parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
            if not parents or parents[0] not in new_transforms:
                top_nodes.append(node)
        return top_nodes

    def _top_world_transform(self, node: str) -> Optional[str]:
        if not node or not cmds.objExists(node):
            return None
        current = node
        visited: Set[str] = set()
        while current and current not in visited:
            visited.add(current)
            parents = cmds.listRelatives(current, parent=True, fullPath=True) or []
            if not parents:
                return current
            current = parents[0]
        return None

    def _is_integration_parent_group(self, node: str) -> bool:
        short = self._strip_namespaces_from_name(self._short_name(node))
        return short in {"Main_Assets", "Annexes"}

    def _normalize_loaded_roots(self, nodes: List[str]) -> List[str]:
        roots: List[str] = []
        seen: Set[str] = set()
        for node in nodes:
            root = self._top_world_transform(node)
            if not root or root in seen:
                continue
            if self._is_integration_parent_group(root):
                continue
            seen.add(root)
            roots.append(root)
        return sorted(roots)

    def _resolve_loaded_roots_with_fallback(
        self,
        scene_asset: str,
        catalog_name: str,
        before_transforms: Set[str],
        after_transforms: Set[str],
    ) -> List[str]:
        loaded_top_nodes = self._find_loaded_top_nodes(before_transforms, after_transforms)
        if loaded_top_nodes:
            return self._normalize_loaded_roots(loaded_top_nodes)

        self._append_integration_log("[INFO] No newly created top nodes detected, using fallback resolution")

        world_roots = cmds.ls(assemblies=True, long=True) or []
        before_world_roots = {node for node in before_transforms if node.count("|") == 1}
        after_world_roots = {node for node in after_transforms if node.count("|") == 1}
        newly_visible_world_roots = sorted(after_world_roots - before_world_roots)

        normalized_scene_asset = self._strip_namespaces_from_name(scene_asset).upper()
        tokens = {
            catalog_name.upper(),
            self._strip_namespaces_from_name(catalog_name).upper(),
            normalized_scene_asset,
        }
        tokens = {token for token in tokens if token}

        prefix_candidates = [prefix for prefix in INTEGRATION_QDTOOLS_PREFIXES if catalog_name.upper().startswith(prefix)]
        if normalized_scene_asset:
            prefix_candidates.extend([f"{prefix}{normalized_scene_asset}" for prefix in INTEGRATION_QDTOOLS_PREFIXES])

        scored: List[Tuple[int, str]] = []
        for root in world_roots:
            if not cmds.objExists(root):
                continue
            if self._is_integration_parent_group(root):
                continue
            short = self._strip_namespaces_from_name(self._short_name(root)).upper()
            score = 0
            if root in newly_visible_world_roots:
                score += 100
            if short in tokens:
                score += 80
            if any(token and token in short for token in tokens):
                score += 50
            if any(candidate and short.startswith(candidate) for candidate in prefix_candidates):
                score += 35
            if score > 0:
                scored.append((score, root))

        if not scored:
            return []

        scored.sort(key=lambda item: (-item[0], item[1]))
        top_score = scored[0][0]
        resolved = [node for score, node in scored if score == top_score]
        resolved = self._normalize_loaded_roots(resolved)
        for node in resolved:
            self._append_integration_log(f"[INFO] Resolved loaded root: {node}")
        return resolved

    def _parent_loaded_nodes_for_asset_kind(self, asset_kind: str, loaded_top_nodes: List[str]) -> None:
        if not loaded_top_nodes:
            return
        target_group = "Main_Assets" if asset_kind == "main asset" else "Annexes"
        target_group = self._ensure_integration_parent_group(target_group)
        self._append_integration_log(f"[INFO] Parenting loaded asset under {target_group}")
        for node in loaded_top_nodes:
            if not cmds.objExists(node):
                continue
            if self._strip_namespaces_from_name(self._short_name(node)) == target_group:
                continue
            try:
                current_parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
                if current_parent and self._strip_namespaces_from_name(self._short_name(current_parent[0])) == target_group:
                    continue
                cmds.parent(node, target_group)
            except Exception as exc:
                self._append_integration_log(f"[WARN] Could not parent {node} under {target_group}: {exc}")

    def update_selected_catalog_assets_from_p4(self) -> None:
        selected_main_assets = self._selected_list_control_items("integration_catalog_list")
        selected_annexe_assets = self._selected_list_control_items("integration_annexe_catalog_list")
        if not selected_main_assets and not selected_annexe_assets:
            self._append_integration_log("Nothing selected. Select at least one catalog asset.")
            return
        category = self._selected_integration_qd_category()

        try:
            from qdTools.qdAssembly.qdUtils.qdLoad import QDLoad
        except Exception as exc:
            self._append_integration_log(f"[ERROR] qdTools import failed: {exc}")
            self._append_integration_log(traceback.format_exc().rstrip())
            return

        self.integration_last_results = []
        total_selected_assets = len(selected_main_assets) + len(selected_annexe_assets)
        self._append_integration_log(f"Launching P4 update for {total_selected_assets} asset(s) with category='{category}'...")
        for asset_kind, selected_assets in (("main asset", selected_main_assets), ("annexe asset", selected_annexe_assets)):
            for scene_asset in selected_assets:
                self._append_integration_log(f"Trying P4 load for {asset_kind} {scene_asset}")
                catalog_candidates = self._integration_catalog_candidates(scene_asset)
                asset_loaded = False

                for catalog_name in catalog_candidates:
                    self._append_integration_log(f"[INFO] Trying {catalog_name}")
                    try:
                        loader = QDLoad.by_catalog(catalog_name, category)
                        if loader is None:
                            raise RuntimeError("QDLoad.by_catalog returned None")

                        update_callable = getattr(loader, "update_status", None)
                        if not callable(update_callable):
                            raise RuntimeError("Resolved loader has no callable update_status method")

                        before_transforms = self._snapshot_scene_transforms()
                        update_result = update_callable(b_recursive=True)
                        after_transforms = self._snapshot_scene_transforms()
                        if update_result is None and not hasattr(loader, "items"):
                            # Keep compatibility with loaders returning None while still guarding obviously empty resolutions.
                            self._append_integration_log(
                                f"[WARN] {catalog_name} update_status returned None (continuing, loader resolved successfully)."
                            )

                        self.integration_last_results.append((scene_asset, True, f"Loaded with {catalog_name}"))
                        self._append_integration_log(f"[OK] Loaded with {catalog_name}")
                        loaded_top_nodes = self._resolve_loaded_roots_with_fallback(
                            scene_asset=scene_asset,
                            catalog_name=catalog_name,
                            before_transforms=before_transforms,
                            after_transforms=after_transforms,
                        )
                        if not loaded_top_nodes:
                            self._append_integration_log("[WARN] Could not resolve loaded roots for parenting.")
                        else:
                            self._parent_loaded_nodes_for_asset_kind(asset_kind, loaded_top_nodes)
                        asset_loaded = True
                        break
                    except Exception as exc:
                        self._append_integration_log(f"[FAIL] {catalog_name} failed")
                        self._append_integration_log(f"[DEBUG] {catalog_name}: {exc}")
                        continue

                if not asset_loaded:
                    message = f"{scene_asset} could not be loaded with any known prefix"
                    self.integration_last_results.append((scene_asset, False, message))
                    self._append_integration_log(f"[FAIL] {message}")

    def _build_compare_row(
        self,
        check_key_ui: str,
        check_key: str,
        button_label: str,
        command,
        global_toggle_key: str,
        default_global: bool = False,
    ) -> None:
        if check_key in self.subcheck_definitions:
            cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 4)])
            self._build_subcheck_boxes(check_key)
            self.ui[global_toggle_key] = cmds.checkBox(label="Global", value=default_global)
            cmds.button(label=button_label, height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: command())
            cmds.setParent("..")
            return
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 4)])
        self.ui[check_key_ui] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="", align="left")
        self.ui[global_toggle_key] = cmds.checkBox(label="Global", value=default_global)
        cmds.button(label=button_label, height=UI_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: command())
        cmds.setParent("..")

    def _build_tab_visibility_controls(self, context_key: str) -> None:
        groups = {
            "high": [
                {"key": "High_MA_GRP", "label": "High MA", "handler": lambda visible: self._set_group_visibility("High_MA_GRP", visible), "getter": lambda: self._is_group_visible("High_MA_GRP")},
                {"key": "High_FBX_GRP", "label": "High FBX", "handler": lambda visible: self._set_group_visibility("High_FBX_GRP", visible), "getter": lambda: self._is_group_visible("High_FBX_GRP")},
                {"key": "Placeholder_GRP", "label": "Placeholder", "handler": lambda visible: self._set_group_visibility("Placeholder_GRP", visible), "getter": lambda: self._is_group_visible("Placeholder_GRP")},
            ],
            "low": [
                {"key": "Low_FBX_GRP", "label": "Low FBX", "handler": lambda visible: self._set_group_visibility("Low_FBX_GRP", visible), "getter": lambda: self._is_group_visible("Low_FBX_GRP")},
                {"key": "Final_Asset_MA_GRP", "label": "Final MA", "handler": lambda visible: self._set_group_visibility("Final_Asset_MA_GRP", visible), "getter": lambda: self._is_group_visible("Final_Asset_MA_GRP")},
                {"key": "Final_Asset_FBX_GRP", "label": "Final FBX", "handler": lambda visible: self._set_group_visibility("Final_Asset_FBX_GRP", visible), "getter": lambda: self._is_group_visible("Final_Asset_FBX_GRP")},
            ],
            "bake": [
                {"key": "Bake_High", "label": "Bake High", "handler": lambda visible: self._set_bake_kind_visibility("high", visible), "getter": lambda: self._is_bake_kind_visible("high")},
                {"key": "Bake_Low", "label": "Bake Low", "handler": lambda visible: self._set_bake_kind_visibility("low", visible), "getter": lambda: self._is_bake_kind_visible("low")},
            ],
            "final_asset": [
                {"key": "Final_Asset_MA_GRP", "label": "Final MA", "handler": lambda visible: self._set_group_visibility("Final_Asset_MA_GRP", visible), "getter": lambda: self._is_group_visible("Final_Asset_MA_GRP")},
                {"key": "Final_Asset_FBX_GRP", "label": "Final FBX", "handler": lambda visible: self._set_group_visibility("Final_Asset_FBX_GRP", visible), "getter": lambda: self._is_group_visible("Final_Asset_FBX_GRP")},
            ],
        }.get(context_key, [])
        if not groups:
            return
        self.scene_visibility_groups_by_context[context_key] = groups
        cmds.frameLayout(label="Scene Visibility", collapsable=True, collapse=False, marginWidth=8, marginHeight=6, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        cmds.button(
            label="Show All",
            height=24,
            backgroundColor=UI_COLOR_BG_ACCENT_SOFT,
            command=lambda *_args, ck=context_key: self._set_scene_visibility_all(ck, True),
        )
        cmds.button(
            label="Hide All",
            height=24,
            backgroundColor=UI_COLOR_BG_WARNING,
            command=lambda *_args, ck=context_key: self._set_scene_visibility_all(ck, False),
        )
        cmds.setParent("..")
        cols = max(1, min(3, len(groups)))
        cmds.gridLayout(numberOfColumns=cols, cellWidthHeight=(140, 30))
        for group_data in groups:
            button_key = f"vis_{context_key}_{group_data['key']}"
            self.ui[button_key] = cmds.iconTextCheckBox(
                style="textOnly",
                label=group_data["label"],
                value=bool(group_data["getter"]()),
                height=28,
                backgroundColor=UI_COLOR_VIS_OFF,
                changeCommand=lambda val, ck=context_key, gk=group_data["key"]: self._on_scene_visibility_toggled(ck, gk, bool(val)),
            )
            self.scene_visibility_controls[f"{context_key}:{group_data['key']}"] = self.ui[button_key]
            self._refresh_scene_visibility_button(context_key, group_data["key"])
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _on_scene_visibility_toggled(self, context_key: str, group_key: str, visible: bool) -> None:
        self._set_scene_visibility_item(context_key, group_key, visible)
        self._refresh_scene_visibility_button(context_key, group_key)

    def _set_scene_visibility_item(self, context_key: str, group_key: str, visible: bool) -> None:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            if group_data["key"] != group_key:
                continue
            group_data["handler"](visible)
            return

    def _set_scene_visibility_all(self, context_key: str, visible: bool) -> None:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            self._set_scene_visibility_item(context_key, group_data["key"], visible)
            self._refresh_scene_visibility_button(context_key, group_data["key"])

    def _refresh_scene_visibility_button(self, context_key: str, group_key: str) -> None:
        control = self.scene_visibility_controls.get(f"{context_key}:{group_key}")
        if not control or not cmds.iconTextCheckBox(control, exists=True):
            return
        state = self._get_scene_visibility_state(context_key, group_key)
        label = self._get_scene_visibility_label(context_key, group_key)
        status = "ON" if state else "OFF"
        cmds.iconTextCheckBox(
            control,
            edit=True,
            value=state,
            label=f"{label}  {status}",
            backgroundColor=UI_COLOR_VIS_ON if state else UI_COLOR_VIS_OFF,
        )

    def _get_scene_visibility_state(self, context_key: str, group_key: str) -> bool:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            if group_data["key"] == group_key:
                return bool(group_data["getter"]())
        return False

    def _get_scene_visibility_label(self, context_key: str, group_key: str) -> str:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            if group_data["key"] == group_key:
                return str(group_data["label"])
        return group_key

    def _on_scene_visibility_toggled(self, context_key: str, group_key: str, visible: bool) -> None:
        self._set_scene_visibility_item(context_key, group_key, visible)
        self._refresh_scene_visibility_button(context_key, group_key)

    def _set_scene_visibility_item(self, context_key: str, group_key: str, visible: bool) -> None:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            if group_data["key"] != group_key:
                continue
            group_data["handler"](visible)
            return

    def _set_scene_visibility_all(self, context_key: str, visible: bool) -> None:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            self._set_scene_visibility_item(context_key, group_data["key"], visible)
            self._refresh_scene_visibility_button(context_key, group_data["key"])

    def _refresh_scene_visibility_button(self, context_key: str, group_key: str) -> None:
        control = self.scene_visibility_controls.get(f"{context_key}:{group_key}")
        if not control or not cmds.iconTextCheckBox(control, exists=True):
            return
        state = self._get_scene_visibility_state(context_key, group_key)
        label = self._get_scene_visibility_label(context_key, group_key)
        status = "ON" if state else "OFF"
        cmds.iconTextCheckBox(
            control,
            edit=True,
            value=state,
            label=f"{label}  {status}",
            backgroundColor=UI_COLOR_VIS_ON if state else UI_COLOR_VIS_OFF,
        )

    def _get_scene_visibility_state(self, context_key: str, group_key: str) -> bool:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            if group_data["key"] == group_key:
                return bool(group_data["getter"]())
        return False

    def _get_scene_visibility_label(self, context_key: str, group_key: str) -> str:
        for group_data in self.scene_visibility_groups_by_context.get(context_key, []):
            if group_data["key"] == group_key:
                return str(group_data["label"])
        return group_key

    def _build_manual_root_selector(self, menu_key: str, label: str, source_key: str) -> None:
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(
            numberOfColumns=4,
            adjustableColumn=2,
            columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 4)],
        )
        cmds.text(label=label, align="left")
        self.ui[menu_key] = cmds.optionMenu(changeCommand=lambda *_: self.on_manual_root_changed(menu_key))
        cmds.menuItem(label="-- Aucun root --", parent=self.ui[menu_key])
        cmds.button(label="Use Selection", height=24, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.set_manual_root_from_selection(menu_key))
        toggle_key = f"{menu_key}_fulltext_toggle"
        self.ui[toggle_key] = cmds.button(
            label="▶",
            width=22,
            height=22,
            command=lambda *_args, mk=menu_key: self._toggle_manual_root_fulltext_visibility(mk),
        )
        cmds.setParent("..")

        fulltext_layout_key = f"{menu_key}_fulltext_layout"
        self.ui[fulltext_layout_key] = cmds.columnLayout(adjustableColumn=True, visible=False)
        fulltext_key = f"{menu_key}_fulltext"
        self.ui[fulltext_key] = cmds.scrollField(
            editable=False,
            wordWrap=True,
            height=38,
            text="-- Aucun root --",
        )
        cmds.setParent("..")
        cmds.setParent("..")

        self.manual_root_menu_sources[menu_key] = source_key
        self.manual_root_fulltext_controls[menu_key] = fulltext_key
        self.manual_root_fulltext_layouts[menu_key] = fulltext_layout_key
        self.manual_root_fulltext_toggles[menu_key] = toggle_key

    def _set_step01_collapsed(self, collapsed: bool) -> None:
        if not self.step01_placeholder_body_widget or not self.step01_collapse_button:
            return
        self.step01_placeholder_body_widget.setVisible(not collapsed)
        self.step01_collapse_button.setText("▸" if collapsed else "▾")
        self.step01_collapse_button.setToolTip("Expand Step 01" if collapsed else "Collapse Step 01")

    def _sync_step01_qt_subchecks(self) -> None:
        if not self.step01_qt_subcheck_widgets:
            return
        states = self.subcheck_states.get("placeholder_checked", {})
        for sub_key, widget in self.step01_qt_subcheck_widgets.items():
            status = states.get(sub_key, "PENDING")
            widget.setChecked(status == "OK")
            widget.setProperty("resultState", status)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def _build_step01_placeholder_match_qt(self) -> None:
        if not QT_AVAILABLE or QtWidgets is None or wrapInstance is None:
            self.log("WARNING", "UI", "Qt indisponible (PySide2/PySide6). Fallback Maya UI pour Step 01.")
            self._build_step01_placeholder_match_cmds_fallback()
            return
        qt_host_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=0)
        host_ptr = omui.MQtUtil.findLayout(qt_host_layout)
        if not host_ptr:
            cmds.warning("Impossible de construire Step 01 en Qt: layout Maya introuvable.")
            self._build_step01_placeholder_match_cmds_fallback()
            return
        host_widget = wrapInstance(int(host_ptr), QtWidgets.QWidget)
        host_widget.setObjectName("step01_placeholder_host")
        if host_widget.layout() is None:
            host_widget.setLayout(QtWidgets.QVBoxLayout())
        host_widget.layout().setContentsMargins(0, 0, 0, 0)
        host_widget.layout().setSpacing(0)

        step_card = QtWidgets.QFrame()
        step_card.setObjectName("Step01Card")
        step_card.setStyleSheet(STEP01_QSS)
        card_layout = QtWidgets.QVBoxLayout(step_card)
        card_layout.setContentsMargins(s(14), s(12), s(14), s(12))
        card_layout.setSpacing(s(10))

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(s(10))

        badge = QtWidgets.QFrame()
        badge.setObjectName("StepBadge")
        badge.setFixedSize(s(52), s(52))
        badge_layout = QtWidgets.QVBoxLayout(badge)
        badge_layout.setContentsMargins(0, s(7), 0, s(6))
        badge_layout.setSpacing(0)
        badge_layout.setAlignment(QtCore.Qt.AlignCenter)
        badge_top = QtWidgets.QLabel("STEP")
        badge_top.setObjectName("StepBadgeTop")
        badge_top.setAlignment(QtCore.Qt.AlignCenter)
        badge_bottom = QtWidgets.QLabel("01")
        badge_bottom.setObjectName("StepBadgeBottom")
        badge_bottom.setAlignment(QtCore.Qt.AlignCenter)
        badge_bottom.setStyleSheet(f"font-size: {s(24)}px;")
        badge_layout.addWidget(badge_top)
        badge_layout.addWidget(badge_bottom)

        title_lbl = QtWidgets.QLabel("Placeholder Match")
        title_lbl.setObjectName("StepTitle")
        title_lbl.setStyleSheet(f"font-size: {s(18)}px;")
        info_btn = ModernInfoButton(
            "Cette étape vérifie qu’un High correspond bien à son Placeholder.\n\n"
            "• BBox compare la cohérence globale du volume et des dimensions.\n"
            "• Pivot vérifie que le pivot du High correspond à celui du Placeholder.\n\n"
            "Elle permet de détecter rapidement un mauvais placeholder, un mauvais scale global\n"
            "ou un pivot mal positionné avant de continuer la review."
        )
        info_btn.setObjectName("InfoButton")
        info_btn.setText("ⓘ")
        collapse_btn = QtWidgets.QToolButton()
        collapse_btn.setObjectName("CollapseButton")
        collapse_btn.setText("▾")
        collapse_btn.setToolTip("Collapse Step 01")

        header_layout.addWidget(badge, 0, QtCore.Qt.AlignVCenter)
        header_layout.addWidget(title_lbl, 0, QtCore.Qt.AlignVCenter)
        header_layout.addWidget(info_btn, 0, QtCore.Qt.AlignVCenter)
        header_layout.addStretch(1)
        header_layout.addWidget(collapse_btn, 0, QtCore.Qt.AlignVCenter)
        card_layout.addLayout(header_layout)

        body_widget = QtWidgets.QWidget()
        body_layout = QtWidgets.QVBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(s(8))

        self.manual_root_menu_sources["placeholder_high_root_menu"] = "high_ma"
        self.manual_root_menu_sources["placeholder_placeholder_root_menu"] = "placeholder_ma"
        high_row = StepRootSelectorRow("High Root", "placeholder_high_root_menu")
        placeholder_row = StepRootSelectorRow("Placeholder Root", "placeholder_placeholder_root_menu")
        self.manual_root_qt_rows["placeholder_high_root_menu"] = high_row
        self.manual_root_qt_rows["placeholder_placeholder_root_menu"] = placeholder_row
        high_row.path_combo.currentIndexChanged.connect(lambda *_: self.on_manual_root_changed("placeholder_high_root_menu"))
        placeholder_row.path_combo.currentIndexChanged.connect(lambda *_: self.on_manual_root_changed("placeholder_placeholder_root_menu"))
        high_row.use_selection_btn.clicked.connect(lambda *_: self.set_manual_root_from_selection("placeholder_high_root_menu"))
        placeholder_row.use_selection_btn.clicked.connect(lambda *_: self.set_manual_root_from_selection("placeholder_placeholder_root_menu"))
        body_layout.addWidget(high_row)
        body_layout.addWidget(placeholder_row)

        sub_band = QtWidgets.QFrame()
        sub_band.setObjectName("SubChecksBand")
        sub_layout = QtWidgets.QHBoxLayout(sub_band)
        sub_layout.setContentsMargins(s(12), s(10), s(12), s(10))
        sub_layout.setSpacing(s(10))

        bbox_check = QtWidgets.QCheckBox("BBox")
        bbox_check.setObjectName("StepSubCheckBox")
        bbox_check.setChecked(False)
        bbox_check.setEnabled(False)
        bbox_check.setProperty("resultState", "PENDING")
        bbox_desc = QtWidgets.QLabel("Verify that each high\nmatches its placeholder")
        bbox_desc.setObjectName("SubCheckDesc")
        bbox_desc.setWordWrap(True)
        bbox_group = QtWidgets.QHBoxLayout()
        bbox_group.setSpacing(s(10))
        bbox_group.addWidget(bbox_check, 0, QtCore.Qt.AlignVCenter)
        bbox_group.addWidget(bbox_desc, 0, QtCore.Qt.AlignVCenter)
        bbox_wrap = QtWidgets.QWidget()
        bbox_wrap.setLayout(bbox_group)

        pivot_check = QtWidgets.QCheckBox("Pivot")
        pivot_check.setObjectName("StepSubCheckBox")
        pivot_check.setChecked(False)
        pivot_check.setEnabled(False)
        pivot_check.setProperty("resultState", "PENDING")
        pivot_desc = QtWidgets.QLabel("Verify that each high\nmatches its placeholder pivot")
        pivot_desc.setObjectName("SubCheckDesc")
        pivot_desc.setWordWrap(True)
        pivot_group = QtWidgets.QHBoxLayout()
        pivot_group.setSpacing(s(10))
        pivot_group.addWidget(pivot_check, 0, QtCore.Qt.AlignVCenter)
        pivot_group.addWidget(pivot_desc, 0, QtCore.Qt.AlignVCenter)
        pivot_wrap = QtWidgets.QWidget()
        pivot_wrap.setLayout(pivot_group)

        checks_container = QtWidgets.QWidget()
        checks_layout = QtWidgets.QHBoxLayout(checks_container)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        checks_layout.setSpacing(s(8))
        div_1 = QtWidgets.QFrame()
        div_1.setObjectName("ThinDivider")

        run_btn = QtWidgets.QPushButton("▶  Run Placeholder Check")
        run_btn.setObjectName("RunCheckButton")
        run_btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        run_btn.clicked.connect(lambda *_: self.check_placeholder_match())
        tolerance_lbl = QtWidgets.QLabel("Tolerance %")
        tolerance_lbl.setObjectName("ToleranceLabel")
        tolerance_spin = QtWidgets.QDoubleSpinBox()
        tolerance_spin.setObjectName("ToleranceSpin")
        tolerance_spin.setRange(0.0, 100.0)
        tolerance_spin.setDecimals(2)
        tolerance_spin.setSingleStep(0.25)
        tolerance_spin.setValue(7.00)
        tolerance_spin.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.ui["placeholder_tolerance_qt"] = tolerance_spin

        checks_layout.addWidget(bbox_wrap, 0, QtCore.Qt.AlignVCenter)
        checks_layout.addWidget(div_1)
        checks_layout.addWidget(pivot_wrap, 0, QtCore.Qt.AlignVCenter)
        checks_layout.addStretch(1)
        sub_layout.addWidget(checks_container, 1)

        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setSpacing(s(8))
        actions_layout.addWidget(run_btn, 0, QtCore.Qt.AlignVCenter)
        actions_layout.addWidget(tolerance_lbl, 0, QtCore.Qt.AlignVCenter)
        actions_layout.addWidget(tolerance_spin, 0, QtCore.Qt.AlignVCenter)
        sub_layout.addLayout(actions_layout, 0)

        body_layout.addWidget(sub_band)
        card_layout.addWidget(body_widget)
        host_widget.layout().addWidget(step_card)
        self.step01_placeholder_widget = step_card
        self.step01_placeholder_body_widget = body_widget
        self.step01_collapse_button = collapse_btn
        self.step01_qt_subcheck_widgets = {"bbox": bbox_check, "pivot": pivot_check}
        collapse_btn.clicked.connect(lambda *_: self._set_step01_collapsed(body_widget.isVisible()))
        self._sync_step01_qt_subchecks()
        cmds.setParent("..")

    def _build_step01_placeholder_match_cmds_fallback(self) -> None:
        cmds.text(label="Step 01 — Placeholder Match", align="left")
        self._build_manual_root_selector("placeholder_high_root_menu", "Select High Root", "high_ma")
        self._build_manual_root_selector("placeholder_placeholder_root_menu", "Select Placeholder Root", "placeholder_ma")
        cmds.rowLayout(numberOfColumns=5, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 6), (4, "both", 2), (5, "both", 2)])
        self._build_subcheck_boxes("placeholder_checked")
        cmds.text(label="Verify that each high matches its placeholder", align="left")
        cmds.button(label="Run Placeholder Check", height=26, command=lambda *_: self.check_placeholder_match())
        cmds.text(label="Tolerance %", align="right")
        self.ui["placeholder_tolerance"] = cmds.floatField(minValue=0.0, value=7.0, precision=2, step=0.25, width=70)
        cmds.setParent("..")

    def _build_qt_step_card(self, step_number: int, title: str, build_body_fn, info_text: str = "") -> None:
        if not QT_AVAILABLE or QtWidgets is None or wrapInstance is None:
            return
        qt_host_layout = cmds.columnLayout(adjustableColumn=True, rowSpacing=0)
        host_ptr = omui.MQtUtil.findLayout(qt_host_layout)
        if not host_ptr:
            cmds.warning(f"Impossible de construire Step {step_number:02d} en Qt: layout Maya introuvable.")
            cmds.setParent("..")
            return
        host_widget = wrapInstance(int(host_ptr), QtWidgets.QWidget)
        if host_widget.layout() is None:
            host_widget.setLayout(QtWidgets.QVBoxLayout())
        host_widget.layout().setContentsMargins(0, 0, 0, 0)
        host_widget.layout().setSpacing(0)
        card = ReviewStepCard(step_number, title, info_text)
        build_body_fn(card.body_layout())
        host_widget.layout().addWidget(card)
        cmds.setParent("..")

    def _add_qt_root_selector_row(self, parent_layout, menu_key: str, label: str, source_key: str):
        row = StepRootSelectorRow(label, menu_key)
        self.manual_root_menu_sources[menu_key] = source_key
        self.manual_root_qt_rows[menu_key] = row
        row.path_combo.currentIndexChanged.connect(lambda *_: self.on_manual_root_changed(menu_key))
        row.use_selection_btn.clicked.connect(lambda *_: self.set_manual_root_from_selection(menu_key))
        parent_layout.addWidget(row)
        return row

    def _create_qt_subcheck_band(self, check_key: str, desc_map: Optional[Dict[str, str]] = None):
        desc_map = desc_map or {}
        band = QtWidgets.QFrame()
        band.setObjectName("SubChecksBand")
        root_layout = QtWidgets.QHBoxLayout(band)
        root_layout.setContentsMargins(s(12), s(8), s(12), s(8))
        root_layout.setSpacing(s(10))
        checks_container = QtWidgets.QWidget()
        checks_layout = QtWidgets.QHBoxLayout(checks_container)
        checks_layout.setContentsMargins(0, 0, 0, 0)
        checks_layout.setSpacing(s(8))
        defs = self.subcheck_definitions.get(check_key, [])
        self.qt_subcheck_widgets.setdefault(check_key, {})
        for idx, (sub_key, sub_label) in enumerate(defs):
            chk = QtWidgets.QCheckBox(sub_label)
            chk.setObjectName("StepSubCheckBox")
            chk.setEnabled(False)
            chk.setProperty("resultState", "PENDING")
            self.qt_subcheck_widgets[check_key][sub_key] = chk
            wrap = QtWidgets.QWidget()
            wlay = QtWidgets.QVBoxLayout(wrap)
            wlay.setContentsMargins(0, 0, 0, 0)
            wlay.setSpacing(s(2))
            wlay.addWidget(chk)
            desc = desc_map.get(sub_key, "")
            if desc:
                lbl = QtWidgets.QLabel(desc)
                lbl.setObjectName("SubCheckDesc")
                lbl.setWordWrap(True)
                wlay.addWidget(lbl)
            checks_layout.addWidget(wrap, 0, QtCore.Qt.AlignVCenter)
            if idx < len(defs) - 1:
                divider = QtWidgets.QFrame()
                divider.setObjectName("ThinDivider")
                checks_layout.addWidget(divider)
        checks_layout.addStretch(1)
        root_layout.addWidget(checks_container, 1)

        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.setSpacing(s(8))
        root_layout.addLayout(actions_layout, 0)
        return band, actions_layout

    def _make_qt_run_button(self, label: str, callback):
        btn = QtWidgets.QPushButton(label)
        btn.setObjectName("RunCheckButton")
        btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        btn.setMinimumWidth(btn.sizeHint().width() + s(6))
        btn.clicked.connect(lambda *_: callback())
        return btn

    def _build_global_action_section(self) -> None:
        cmds.frameLayout(label="Actions", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        cmds.button(label="Run All High Steps", height=UI_PRIMARY_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT, command=lambda *_: self.run_all_checks())
        cmds.button(label="Clear Results", height=UI_PRIMARY_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_WARNING, command=lambda *_: self.clear_results())
        cmds.setParent("..")
        cmds.button(label="Save Review Report", height=UI_PRIMARY_BUTTON_HEIGHT, backgroundColor=UI_COLOR_BG_ACCENT_SOFT, command=lambda *_: self.save_report())

        cmds.button(
            label="Isolate meshes without VColor",
            height=UI_BUTTON_HEIGHT,
            backgroundColor=UI_COLOR_BG_ACCENT_SOFT,
            command=lambda *_: self.isolate_meshes_without_vertex_color(),
        )

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_results_section(self) -> None:
        cmds.frameLayout(label="4) Résultats / Log", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        cmds.frameLayout(label="Quick Summary", collapsable=False, marginWidth=8, marginHeight=6, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        self.ui["summary_scroll"] = cmds.scrollLayout(
            childResizable=True,
            height=120,
            verticalScrollBarThickness=14,
        )
        self.ui["summary_results_column"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

        cmds.frameLayout(label="Detailed Logs", collapsable=False, marginWidth=8, marginHeight=6, backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        self.ui["results_scroll"] = cmds.scrollLayout(
            childResizable=True,
            height=380,
            verticalScrollBarThickness=16,
            backgroundColor=UI_COLOR_BG_LOG,
        )
        self.ui["results_column"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
        cmds.setParent("..")
        cmds.text(label="Tip: clique une ligne liée à des objets pour sélectionner en scène.", align="left")
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_notes_section(self) -> None:
        cmds.frameLayout(label="5) Notes", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["notes_field"] = cmds.scrollField(wordWrap=True, height=130, text="", backgroundColor=UI_COLOR_BG_LOG)
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_summary_section(self) -> None:
        cmds.frameLayout(label="6) Résumé global", collapsable=True, collapse=False, marginWidth=10, marginHeight=8, backgroundColor=UI_COLOR_BG_SECTION)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["summary_text"] = cmds.text(label="Pending checks", align="left", backgroundColor=UI_COLOR_BG_SUBSECTION)
        cmds.setParent("..")
        cmds.setParent("..")

    # ------------------------- Utility methods -------------------------
    def _ellipsize_middle(self, text: str, max_length: int = MAX_UI_TEXT_LENGTH) -> str:
        if len(text) <= max_length:
            return text
        if max_length < 8:
            return text[:max_length]
        keep = (max_length - 3) // 2
        return f"{text[:keep]}...{text[-(max_length - 3 - keep):]}"

    def _format_node_menu_label(self, node: str) -> str:
        return node

    def _basename_from_path(self, path: str) -> str:
        return os.path.basename(path) if path else "N/A"

    def _preview_list(self, items: List[str], max_items: int = 4) -> str:
        _ = max_items
        if not items:
            return "-"
        return ", ".join(items)

    def _log_step_header(self, step_number: int, title: str, category: str = "Step") -> None:
        self.log("INFO", category, f"-- Step {step_number:02d}: {title} --")

    def _ensure_outsourcing_review_group(self) -> str:
        if not cmds.objExists("Outsourcing_Review"):
            cmds.group(empty=True, name="Outsourcing_Review")
            self.log("INFO", "Load", "Groupe Outsourcing_Review créé.")
        try:
            cmds.setAttr("Outsourcing_Review.visibility", 1)
        except RuntimeError:
            pass
        return "Outsourcing_Review"

    def _ensure_review_subgroup(self, file_key: str) -> str:
        parent = self._ensure_outsourcing_review_group()
        group_name = self.review_subgroups_by_file.get(file_key, f"{file_key}_GRP")
        if not cmds.objExists(group_name):
            cmds.group(empty=True, name=group_name, parent=parent)
            self.log("INFO", "Load", f"Sous-groupe créé: {group_name}")
        else:
            parent_current = (cmds.listRelatives(group_name, parent=True, fullPath=False) or [""])[0]
            if parent_current != parent:
                try:
                    cmds.parent(group_name, parent)
                except RuntimeError:
                    pass
        self._set_group_visibility(group_name, False)
        return group_name

    def _set_group_visibility(self, group_name: str, visible: bool) -> None:
        if not cmds.objExists(group_name):
            self.log("WARNING", "Visibility", f"Groupe introuvable: {group_name}")
            return
        state = 1 if visible else 0
        targets = [group_name]
        descendants = cmds.listRelatives(group_name, allDescendents=True, fullPath=True, type="transform") or []
        targets.extend(descendants)

        updated_count = 0
        for node in set(targets):
            if not cmds.objExists(node):
                continue
            try:
                cmds.setAttr(node + ".visibility", state)
                updated_count += 1
            except RuntimeError:
                continue

        child_count = max(0, updated_count - 1)
        state_label = "visible" if visible else "hidden"
        self.log(
            "INFO",
            "Visibility",
            f"{group_name} and {child_count} child transforms set to {state_label}",
        )

    def _is_group_visible(self, group_name: str) -> bool:
        if not cmds.objExists(group_name):
            return False
        try:
            return bool(cmds.getAttr(group_name + ".visibility"))
        except RuntimeError:
            return False

    def _toggle_group_visibility(self, group_name: str) -> None:
        if not cmds.objExists(group_name):
            return
        current = bool(cmds.getAttr(group_name + ".visibility"))
        self._set_group_visibility(group_name, not current)

    def _set_bake_kind_visibility(self, kind: str, visible: bool) -> None:
        namespace = self.context.get("bake_ma_namespace", "")
        detected_key = "bake_high" if kind == "high" else "bake_low"
        suffix = "_high" if kind == "high" else "_low"

        roots = [r for r in self.detected_roots.get(detected_key, []) if cmds.objExists(r)]
        if not roots:
            roots = [r for r in self._find_root_candidates(kind, namespace=namespace) if cmds.objExists(r)]

        if not roots:
            self.log("WARNING", "Visibility", f"Aucun root Bake {kind.title()} trouvé pour la visibilité.")
            return

        if visible:
            self._ensure_parent_visibility_for_bake_roots(roots)

        for root in roots:
            self._set_group_visibility(root, visible)

        state_label = "visible" if visible else "hidden"
        self.log("INFO", "Visibility", f"Bake {kind.title()} roots ({suffix}) set to {state_label}: {len(roots)} root(s)")

    def _is_bake_kind_visible(self, kind: str) -> bool:
        namespace = self.context.get("bake_ma_namespace", "")
        detected_key = "bake_high" if kind == "high" else "bake_low"
        roots = [r for r in self.detected_roots.get(detected_key, []) if cmds.objExists(r)]
        if not roots:
            roots = [r for r in self._find_root_candidates(kind, namespace=namespace) if cmds.objExists(r)]
        if not roots:
            return False
        for root in roots:
            try:
                if bool(cmds.getAttr(root + ".visibility")):
                    return True
            except RuntimeError:
                continue
        return False

    def _ensure_parent_visibility_for_bake_roots(self, roots: List[str]) -> None:
        parent_updated = 0
        for root in roots:
            parent = root
            while parent and cmds.objExists(parent):
                short_name = parent.split("|")[-1]
                if short_name == "Bake_MA_GRP":
                    try:
                        cmds.setAttr(parent + ".visibility", 1)
                        parent_updated += 1
                    except RuntimeError:
                        pass
                    break
                parent_list = cmds.listRelatives(parent, parent=True, fullPath=True) or []
                parent = parent_list[0] if parent_list else ""
        if parent_updated:
            self.log("INFO", "Visibility", "Bake_MA_GRP forced visible to keep shown Bake roots actually visible.")

    def _toggle_manual_root_fulltext_visibility(self, menu_key: str) -> None:
        layout_key = self.manual_root_fulltext_layouts.get(menu_key)
        layout_control = self.ui.get(layout_key) if layout_key else None
        current = False
        if layout_control and cmds.columnLayout(layout_control, exists=True):
            current = bool(cmds.columnLayout(layout_control, q=True, visible=True))
        self._set_manual_root_fulltext_visibility(menu_key, not current)

    def _set_manual_root_fulltext_visibility(self, menu_key: str, visible: bool) -> None:
        layout_key = self.manual_root_fulltext_layouts.get(menu_key)
        layout_control = self.ui.get(layout_key) if layout_key else None
        if layout_control and cmds.columnLayout(layout_control, exists=True):
            cmds.columnLayout(layout_control, e=True, visible=visible)
        toggle_key = self.manual_root_fulltext_toggles.get(menu_key)
        toggle_control = self.ui.get(toggle_key) if toggle_key else None
        if toggle_control and cmds.button(toggle_control, exists=True):
            cmds.button(toggle_control, e=True, label="▼" if visible else "▶")

    def _organize_high_ma_loaded_roots(self) -> None:
        namespace = self.context["ma_namespace"]
        placeholder_group_name = self.review_subgroups_by_file.get("placeholder", "Placeholder_GRP")
        placeholder_group_exists = cmds.objExists(placeholder_group_name)
        high_group = self._ensure_review_subgroup("high_ma")
        placeholder_group = self._ensure_review_subgroup("placeholder")
        if not placeholder_group_exists and cmds.objExists(placeholder_group):
            self.log("INFO", "Load", f"Placeholder group created: {placeholder_group}")

        self.detected_roots["high"] = self._find_root_candidates("high", namespace=namespace)
        self.detected_roots["placeholder"] = self._find_root_candidates("placeholder", namespace=namespace)
        self._log_root_detection("high", "High")
        self._log_root_detection("placeholder", "Placeholder")

        high_parented = 0
        for root in self.detected_roots.get("high", []):
            if not cmds.objExists(root):
                continue
            try:
                cmds.parent(root, high_group)
                high_parented += 1
            except RuntimeError:
                continue

        placeholder_parented = 0
        for root in self.detected_roots.get("placeholder", []):
            if not cmds.objExists(root):
                continue
            try:
                cmds.parent(root, placeholder_group)
                placeholder_parented += 1
            except RuntimeError:
                continue

        self.review_group_contents["high_ma"] = cmds.listRelatives(high_group, children=True, fullPath=True) or []
        self.review_group_contents["placeholder"] = cmds.listRelatives(placeholder_group, children=True, fullPath=True) or []

        if not self.detected_roots.get("placeholder", []):
            self.log("INFO", "Load", "No placeholder root detected for High.ma")
        self.log("INFO", "Load", f"{placeholder_parented} placeholder roots parented under {placeholder_group}")
        self.log("INFO", "Load", f"{high_parented} high roots kept under {high_group}")

    def _scalar_from_maya_result(self, value: Any, default: float = 0.0) -> float:
        raw = value
        if isinstance(raw, list):
            raw = raw[0] if raw else default
        if raw is None:
            raw = default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(default)

    def _is_success_info_message(self, message: str) -> bool:
        text = (message or "").strip().lower()
        if not text:
            return False

        success_markers = [
            " = ok",
            "result = ok",
            "result: ok",
            "only authorized namespaces found",
            "within tolerance",
            "pass uv/topology",
            "meshes clean",
            "assignments validated",
            "vertex colors present",
            "match",
            "matches",
            "valid",
        ]
        return any(marker in text for marker in success_markers)

    def _get_log_row_style(self, level: str, message: str, style: Optional[str] = None) -> str:
        normalized = (style or "").strip().lower()
        if normalized in {"neutral", "success", "warning", "fail"}:
            return normalized
        if level == "FAIL":
            return "fail"
        if level == "WARNING":
            return "warning"
        if level == "INFO" and self._is_success_info_message(message):
            return "success"
        return "neutral"

    def _append_detailed_log_row(
        self,
        log_index: int,
        level: str,
        category: str,
        message: str,
        objects: Optional[List[str]] = None,
        style: Optional[str] = None,
    ) -> None:
        if "results_column" not in self.ui:
            return

        prefix = {
            "INFO": "[INFO]",
            "WARNING": "[WARN]",
            "FAIL": "[FAIL]",
        }.get(level, "[INFO]")
        display = f"{prefix} {category}: {message}"
        wrapped_lines = textwrap.wrap(
            display,
            width=120,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [display]
        wrapped_display = "\n".join(wrapped_lines)
        row_height = max(24, len(wrapped_lines) * 18)
        row_style = self._get_log_row_style(level, message, style=style)
        style_to_color = {
            "fail": (0.35, 0.18, 0.18),
            "success": (0.16, 0.32, 0.20),
            "warning": (0.35, 0.28, 0.16),
        }
        row_color = style_to_color.get(row_style)
        row_objects = list(objects or [])

        cmds.setParent(self.ui["results_column"])
        row_layout = cmds.rowLayout(
            numberOfColumns=2,
            adjustableColumn=1,
            columnAttach=[(1, "both", 0), (2, "both", 6)],
        )
        text_kwargs: Dict[str, Any] = {
            "label": wrapped_display,
            "align": "left",
            "wordWrap": False,
            "height": row_height,
        }
        if row_color:
            text_kwargs["backgroundColor"] = row_color
            text_kwargs["enableBackground"] = True
        else:
            text_kwargs["enableBackground"] = False
        row_control = cmds.text(**text_kwargs)
        self.result_control_to_objects[row_control] = row_objects

        select_enabled = bool(row_objects)
        cmds.button(
            label="Select",
            height=row_height,
            enable=select_enabled,
            command=lambda *_: self.on_result_selected_from_control(row_control),
        )
        cmds.setParent("..")
        self.log_rows_by_index[log_index] = DetailedLogRowRef(
            log_index=log_index,
            order=len(self.log_row_order),
            row_layout=row_layout,
            main_text_control=row_control,
            measured_height=row_height,
        )
        self.log_row_order.append(log_index)

    def _ui_element_exists(self, ui_name: str) -> bool:
        if not ui_name:
            return False
        return bool(cmds.control(ui_name, exists=True) or cmds.layout(ui_name, exists=True))

    def _resolve_log_target_control(self, log_index: int) -> Optional[str]:
        row_ref = self.log_rows_by_index.get(log_index)
        if not row_ref:
            return None
        if self._ui_element_exists(row_ref.row_layout):
            return row_ref.row_layout
        if self._ui_element_exists(row_ref.main_text_control):
            return row_ref.main_text_control
        return None

    def _get_results_row_height(self, log_index: int) -> int:
        row_ref = self.log_rows_by_index.get(log_index)
        if not row_ref:
            return 24

        row_control = row_ref.row_layout
        try:
            if cmds.layout(row_control, exists=True):
                row_height = int(cmds.layout(row_control, q=True, height=True) or 0)
                if row_height > 0:
                    row_ref.measured_height = row_height
                    return row_height
        except Exception:
            pass

        label_control = row_ref.main_text_control
        try:
            if label_control and cmds.control(label_control, exists=True):
                label_height = int(cmds.control(label_control, q=True, height=True) or 0)
                if label_height > 0:
                    row_ref.measured_height = label_height
                    return label_height
        except Exception:
            pass

        return max(24, int(row_ref.measured_height or 24))

    def _get_results_visible_height(self) -> int:
        scroll_name = self.ui.get("results_scroll", "")
        if not self._ui_element_exists(scroll_name):
            return 0
        try:
            visible_height = int(cmds.scrollLayout(scroll_name, q=True, height=True) or 0)
            return max(0, visible_height)
        except Exception:
            return 0

    def _compute_results_scroll_offset_for_log(self, log_index: int) -> Optional[int]:
        if "results_column" not in self.ui or "results_scroll" not in self.ui:
            return None

        content_height = 0
        target_center_y: Optional[float] = None

        for row_idx in self.log_row_order:
            row_ref = self.log_rows_by_index.get(row_idx)
            if not row_ref:
                continue
            if not self._resolve_log_target_control(row_idx):
                continue

            row_height = self._get_results_row_height(row_idx)
            if row_idx == log_index:
                target_center_y = content_height + (row_height * 0.5)
            content_height += row_height

        if target_center_y is None:
            return None

        visible_height = self._get_results_visible_height()
        if visible_height <= 0:
            return None

        desired_offset = int(round(target_center_y - (visible_height * 0.5)))
        max_offset = max(0, content_height - visible_height)
        return max(0, min(max_offset, desired_offset))

    def _get_valid_fail_targets(self, summary_index: int) -> List[int]:
        raw_targets = self.summary_row_fail_targets.get(summary_index, [])
        valid_targets = [idx for idx in raw_targets if self._resolve_log_target_control(idx)]
        if valid_targets:
            return valid_targets
        fallback_targets = [
            idx
            for idx, item in enumerate(self.result_items, start=1)
            if item.level == "FAIL" and self._resolve_log_target_control(idx)
        ]
        if fallback_targets:
            self.summary_row_fail_targets[summary_index] = fallback_targets
        return fallback_targets

    def _scroll_results_to_log_index(self, log_index: int) -> bool:
        if not self._resolve_log_target_control(log_index):
            return False

        cmds.refresh(force=True)
        target_offset = self._compute_results_scroll_offset_for_log(log_index)
        if target_offset is None:
            return False
        self._scroll_results_to_offset(target_offset)
        return True

    def _scroll_results_to_offset(self, offset: int) -> None:
        if "results_scroll" not in self.ui:
            return
        clamped = max(0, int(offset))
        try:
            cmds.scrollLayout(self.ui["results_scroll"], edit=True, scrollByPixel=("up", 99999999))
            if clamped > 0:
                cmds.scrollLayout(self.ui["results_scroll"], edit=True, scrollByPixel=("down", clamped))
        except TypeError:
            try:
                cmds.scrollLayout(self.ui["results_scroll"], edit=True, scrollByLine=("up", 99999999))
                if clamped > 0:
                    cmds.scrollLayout(self.ui["results_scroll"], edit=True, scrollByLine=("down", clamped))
            except TypeError:
                pass

    def _go_to_summary_fail(self, summary_index: int) -> None:
        targets = self._get_valid_fail_targets(summary_index)
        if not targets:
            cmds.warning("Go To Error: aucune erreur navigable trouvée dans Detailed Logs.")
            return
        cursor = self.summary_row_fail_cursor.get(summary_index, 0)
        target_log_index = targets[cursor % len(targets)]
        self.summary_row_fail_cursor[summary_index] = (cursor + 1) % len(targets)
        if not self._scroll_results_to_log_index(target_log_index):
            cmds.warning("Go To Error: cible introuvable, retour au début des Detailed Logs.")

    def log(
        self,
        level: str,
        category: str,
        message: str,
        objects: Optional[List[str]] = None,
        style: Optional[str] = None,
    ) -> None:
        issue = ReviewIssue(level=level, category=category, message=message, objects=objects or [])
        self.result_items.append(issue)

        idx = len(self.result_items)
        self.result_index_to_objects[idx] = issue.objects
        self._append_detailed_log_row(idx, level, category, message, objects=issue.objects, style=style)

    def log_success(self, category: str, message: str, objects: Optional[List[str]] = None) -> None:
        self.log("INFO", category, message, objects=objects, style="success")

    def log_summary(self, level: str, category: str, message: str, objects: Optional[List[str]] = None) -> None:
        issue = ReviewIssue(level=level, category=category, message=message, objects=objects or [])
        summary_index = len(self.summary_items)
        prev_end = self.summary_row_ranges[-1][1] if self.summary_row_ranges else 0
        current_end = len(self.result_items)
        self.summary_items.append(issue)
        self.summary_row_ranges.append((prev_end + 1, current_end))
        if "summary_results_column" not in self.ui:
            return

        prefix = {"INFO": "[INFO]", "WARNING": "[WARN]", "FAIL": "[FAIL]"}.get(level, "[INFO]")
        display = f"{prefix} {category}: {message}"

        cmds.setParent(self.ui["summary_results_column"])
        if level == "FAIL":
            cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
            cmds.text(label=display, align="left")
            fail_targets: List[int] = []
            start_idx, end_idx = self.summary_row_ranges[summary_index]
            if start_idx <= end_idx:
                for idx in range(start_idx, end_idx + 1):
                    if idx <= len(self.result_items) and self.result_items[idx - 1].level == "FAIL":
                        fail_targets.append(idx)
            if not fail_targets:
                fallback = [idx for idx, item in enumerate(self.result_items, start=1) if item.level == "FAIL"]
                fail_targets = fallback
            self.summary_row_fail_targets[summary_index] = fail_targets
            self.summary_row_fail_cursor[summary_index] = 0
            cmds.button(label="Go To Error", height=22, enable=bool(fail_targets), command=lambda *_ , i=summary_index: self._go_to_summary_fail(i))
            cmds.setParent("..")
        else:
            cmds.text(label=display, align="left")

    def clear_results(self) -> None:
        self.result_items = []
        self.summary_items = []
        self.result_index_to_objects = {}
        self.result_control_to_objects = {}
        self.summary_row_ranges = []
        self.summary_row_fail_targets = {}
        self.summary_row_fail_cursor = {}
        self.log_rows_by_index = {}
        self.log_row_order = []
        rows = cmds.columnLayout(self.ui["results_column"], q=True, childArray=True) or []
        for row in rows:
            if cmds.control(row, exists=True):
                cmds.deleteUI(row)
        summary_rows = cmds.columnLayout(self.ui["summary_results_column"], q=True, childArray=True) or []
        for row in summary_rows:
            if cmds.control(row, exists=True):
                cmds.deleteUI(row)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        ok_count = sum(1 for c in self.check_states.values() if c["status"] == "OK")
        warn_count = sum(1 for i in self.result_items if i.level == "WARNING")
        fail_count = sum(1 for i in self.result_items if i.level == "FAIL")
        pending = sum(1 for c in self.check_states.values() if c["status"] == "PENDING")

        if fail_count > 0:
            color = (0.35, 0.18, 0.18)
            global_state = "FAIL"
        elif warn_count > 0:
            color = (0.35, 0.28, 0.16)
            global_state = "WARNING"
        elif pending == 0:
            color = (0.16, 0.32, 0.20)
            global_state = "OK"
        else:
            color = (0.22, 0.22, 0.22)
            global_state = "IN PROGRESS"

        text = (
            f"Global: {global_state} | Checks OK: {ok_count}/{len(self.check_states)} | "
            f"Warnings: {warn_count} | Fails: {fail_count} | Pending: {pending}"
        )
        cmds.text(self.ui["summary_text"], e=True, label=text, backgroundColor=color)
        if self.sidebar_summary_labels:
            mapping = {
                "passed": ok_count,
                "warnings": warn_count,
                "failed": fail_count,
                "pending": pending,
                "total": len(self.check_states),
            }
            for key, value in mapping.items():
                label = self.sidebar_summary_labels.get(key)
                if label is not None:
                    label.setText(str(value))

    def refresh_checklist_ui(self) -> None:
        for key, ctrl in self.check_ui_map.items():
            if ctrl not in self.ui:
                continue
            is_checked = self.check_states[key]["status"] == "OK"
            self._set_boolean_control_value(ctrl, is_checked)
        for check_key, sub_controls in self.subcheck_ui_map.items():
            for sub_key, ctrl in sub_controls.items():
                status = self.subcheck_states.get(check_key, {}).get(sub_key, "PENDING")
                self._set_boolean_control_value(ctrl, status == "OK")
        for check_key, sub_widgets in self.qt_subcheck_widgets.items():
            for sub_key, widget in sub_widgets.items():
                status = self.subcheck_states.get(check_key, {}).get(sub_key, "PENDING")
                widget.setChecked(status == "OK")
                widget.setProperty("resultState", status)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
        self._sync_step01_qt_subchecks()

        self.refresh_summary()

    def set_check_status(self, check_key: str, status: str) -> None:
        self.check_states[check_key]["status"] = status
        self.refresh_checklist_ui()

    def log_check_result(
        self,
        check_key: str,
        level: str,
        short_title: str,
        reason: str,
        objects: Optional[List[str]] = None,
    ) -> None:
        status = "OK" if level == "INFO" else "FAIL"
        self.set_check_status(check_key, status)
        defs = self.subcheck_definitions.get(check_key, [])
        if len(defs) == 1:
            self._set_subcheck_results(check_key, {defs[0][0]: level == "INFO"})
        self.log_summary(level, short_title, reason, objects)

    def on_manual_check_toggle(self, check_key: str) -> None:
        if check_key in self.subcheck_definitions:
            return
        ui_key = self.check_ui_map.get(check_key)
        if not ui_key or ui_key not in self.ui:
            return
        checked = self._query_boolean_control_value(ui_key, default=False)
        status = "OK" if checked else "PENDING"
        self.check_states[check_key]["status"] = status
        self.log_summary("INFO", "Manual", f"{check_key} défini manuellement à {status}")
        self.refresh_checklist_ui()

    def on_result_selected_from_control(self, control_name: str) -> None:
        targets = [o for o in self.result_control_to_objects.get(control_name, []) if cmds.objExists(o)]
        if targets:
            cmds.select(targets, replace=True)

    def on_manual_design_toggle(self) -> None:
        self.set_check_status("design_kit_checked", "OK")
        self._set_subcheck_results("design_kit_checked", {"reviewed": True})
        self._log_step_header(2, "Design Kit Review", category="DesignKit")
        self.log("INFO", "DesignKit", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "DesignKit", "Résultat : Revue design kit marquée comme effectuée (manuel).")

    def mark_design_reviewed(self) -> None:
        self.log("INFO", "DesignKit", "Action: Mark Design Kit Reviewed")
        self.on_manual_design_toggle()

    def _set_root_folder(self, path: str) -> None:
        self.paths["root"] = path
        cmds.textFieldButtonGrp(self.ui["root_field"], e=True, text=path)

    def pick_root_folder(self) -> None:
        picked = cmds.fileDialog2(dialogStyle=2, fileMode=3, caption="Select Asset Delivery Root Folder")
        if not picked:
            return
        self._set_root_folder(picked[0])

    def _clear_option_menu(self, menu: str) -> None:
        items = cmds.optionMenu(menu, q=True, itemListLong=True) or []
        for item in items:
            cmds.deleteUI(item)

    def _populate_file_option_menu(self, file_key: str) -> None:
        menu = self.ui[f"{file_key}_menu"]
        files = self.detected_files[file_key]
        self._clear_option_menu(menu)

        if not files:
            cmds.menuItem(label="-- Aucun --", parent=menu)
            self.paths[file_key] = ""
            return

        for p in files:
            cmds.menuItem(label=os.path.basename(p), parent=menu)

        self.paths[file_key] = files[0]
        cmds.optionMenu(menu, edit=True, select=1)

    def refresh_detected_file_labels(self) -> None:
        status_map = [
            ("high_ma", "high_ma_status", "High MA"),
            ("high_fbx", "high_fbx_status", "High FBX"),
            ("bake_ma", "bake_ma_status", "Bake MA"),
            ("low_fbx", "low_fbx_status", "Low FBX"),
            ("bake_ma", "bake_ma_status_low", "Bake MA"),
            ("final_scene_ma", "final_scene_ma_status", "Final Scene MA"),
        ]

        for file_key, status_widget, label in status_map:
            file_count = len(self.detected_files[file_key])
            text = f"Aucun fichier {label} détecté"
            if file_count == 1:
                text = f"1 fichier détecté: {os.path.basename(self.detected_files[file_key][0])}"
            elif file_count > 1:
                text = f"{file_count} fichiers détectés. Sélectionnez le bon fichier."
            if status_widget in self.ui and cmds.text(self.ui[status_widget], exists=True):
                cmds.text(self.ui[status_widget], e=True, label=text)

    def on_detected_file_selected(self, file_key: str, menu_key: Optional[str] = None) -> None:
        files = self.detected_files[file_key]
        if not files:
            self.paths[file_key] = ""
            return

        widget_key = menu_key or f"{file_key}_menu"
        index = cmds.optionMenu(self.ui[widget_key], q=True, select=True) - 1
        index = max(0, min(index, len(files) - 1))
        self.paths[file_key] = files[index]
        self.log("INFO", "Scan", f"{file_key.upper()} sélectionné: {self._basename_from_path(self.paths[file_key])}")

    def _normalize_asset_token(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    def _asset_tokens_from_path(self, path: str) -> List[str]:
        base = os.path.splitext(os.path.basename(path))[0].lower()
        cleaned = re.sub(r"_(high|low|bake)$", "", base)
        return [t for t in re.split(r"[^a-z0-9]+", cleaned) if t]

    def _asset_name_from_path(self, path: str) -> str:
        base = os.path.splitext(os.path.basename(path))[0].lower()
        return re.sub(r"_(high|low|bake)$", "", base)

    def _populate_active_asset_menu(self) -> None:
        menu = self.ui.get("active_asset_menu")
        if not menu or not cmds.optionMenu(menu, exists=True):
            return
        self._clear_option_menu(menu)
        if not self.detected_assets:
            cmds.menuItem(label="-- Aucun asset détecté --", parent=menu)
            self.active_asset = ""
            cmds.text(self.ui["assets_detected_label"], e=True, label="Available: -")
            return
        for asset in self.detected_assets:
            cmds.menuItem(label=asset, parent=menu)
        cmds.optionMenu(menu, e=True, select=1)
        self.active_asset = self.detected_assets[0]
        cmds.text(self.ui["assets_detected_label"], e=True, label=f"Available: {', '.join(self.detected_assets)}")

    def _sync_active_asset_from_final_fbx_path(self, path: str) -> None:
        if not path:
            return
        path_asset = self._asset_name_from_path(path)
        if not path_asset:
            return
        for asset in self.detected_assets:
            if self._normalize_asset_token(asset) == self._normalize_asset_token(path_asset):
                self.active_asset = asset
                idx = self.detected_assets.index(asset) + 1
                cmds.optionMenu(self.ui["active_asset_menu"], e=True, select=idx)
                break

    def _detect_assets_from_scan(self) -> None:
        assets: Set[str] = set()
        # Primary source: final per-asset FBX files.
        for fbx_path in self.detected_files.get("final_asset_fbx", []):
            name = self._asset_name_from_path(fbx_path)
            if name:
                assets.add(name)

        # Fallback: token extraction from shared files.
        if not assets:
            all_paths = []
            for key in ["final_scene_ma", "high_ma", "bake_ma", "low_fbx", "final_asset_fbx"]:
                all_paths.extend(self.detected_files.get(key, []))
            tokens: Set[str] = set()
            for path in all_paths:
                for token in self._asset_tokens_from_path(path):
                    if len(token) > 1 and token not in {"high", "low", "bake", "final", "scene"}:
                        tokens.add(token)
            assets = tokens

        self.detected_assets = sorted(assets)
        self.asset_to_final_fbx = {}
        for fbx_path in self.detected_files.get("final_asset_fbx", []):
            asset_name = self._asset_name_from_path(fbx_path)
            if asset_name in self.detected_assets:
                self.asset_to_final_fbx[asset_name] = fbx_path
        self._populate_active_asset_menu()
        self._auto_match_final_fbx_for_active_asset()

    def _auto_match_final_fbx_for_active_asset(self) -> None:
        if not self.active_asset:
            return
        target = self.asset_to_final_fbx.get(self.active_asset.lower()) or self.asset_to_final_fbx.get(self.active_asset)
        files = self.detected_files.get("final_asset_fbx", [])
        if not files or not target:
            return
        if target in files:
            index = files.index(target) + 1
            cmds.optionMenu(self.ui["final_asset_fbx_menu"], e=True, select=index)
            self.paths["final_asset_fbx"] = target

    def on_active_asset_changed(self) -> None:
        if not self.detected_assets:
            self.active_asset = ""
            return
        index = cmds.optionMenu(self.ui["active_asset_menu"], q=True, select=True) - 1
        index = max(0, min(index, len(self.detected_assets) - 1))
        self.active_asset = self.detected_assets[index]
        self._auto_match_final_fbx_for_active_asset()
        self.auto_detect_scene_roots()
        self.refresh_root_ui()
        for key in self.check_states:
            if self.check_states[key]["mode"] == "AUTO":
                self.check_states[key]["status"] = "PENDING"
        self.refresh_checklist_ui()
        self.detected_texture_sets = {}
        self.material_sets_by_context = {"high": {}, "low": {}, "bake_high": {}, "bake_low": {}, "final_asset": {}}
        self.texture_set_visibility = {}
        self._disable_material_isolation()
        self._refresh_texture_sets_list_ui("high")
        self._refresh_texture_sets_list_ui("low")
        self._refresh_texture_sets_list_ui("bake_high")
        self._refresh_texture_sets_list_ui("bake_low")
        self._refresh_texture_sets_list_ui("final_asset")
        self.log("INFO", "Asset", f"Active Asset: {self.active_asset}")

    def scan_delivery_folder(self) -> None:
        root = cmds.textFieldButtonGrp(self.ui["root_field"], q=True, text=True).strip()
        if not root:
            self.log("FAIL", "Scan", "Aucun dossier racine renseigné.")
            return
        if not os.path.isdir(root):
            self.log("FAIL", "Scan", f"Dossier introuvable: {root}")
            return

        self._set_root_folder(root)
        found_files: Dict[str, List[str]] = {
            "high_fbx": [],
            "high_ma": [],
            "bake_ma": [],
            "low_fbx": [],
            "final_scene_ma": [],
            "final_asset_fbx": [],
        }

        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                name_lower = filename.lower()
                full_path = os.path.join(dirpath, filename)
                if name_lower.endswith("_bake.ma"):
                    found_files["bake_ma"].append(full_path)
                elif name_lower.endswith("_low.fbx"):
                    found_files["low_fbx"].append(full_path)
                elif name_lower.endswith("_high.fbx"):
                    found_files["high_fbx"].append(full_path)
                elif name_lower.endswith("_high.ma"):
                    found_files["high_ma"].append(full_path)
                elif name_lower.endswith(".fbx"):
                    found_files["final_asset_fbx"].append(full_path)
                elif name_lower.endswith(".ma"):
                    found_files["final_scene_ma"].append(full_path)

        for key in found_files:
            found_files[key].sort()

        for key, files in found_files.items():
            self.detected_files[key] = files

        # Toujours synchroniser les chemins utilisables par les loaders,
        # même si les optionMenu ne sont pas présents dans l'UI courante.
        for file_key in ["high_ma", "high_fbx", "bake_ma", "low_fbx", "final_scene_ma", "final_asset_fbx"]:
            files = self.detected_files[file_key]
            previous = self.paths.get(file_key, "")
            if previous and previous in files:
                self.paths[file_key] = previous
            elif files:
                self.paths[file_key] = files[0]
            else:
                self.paths[file_key] = ""

        for file_key in ["high_ma", "high_fbx", "bake_ma", "low_fbx", "final_scene_ma", "final_asset_fbx"]:
            if f"{file_key}_menu" in self.ui:
                self._populate_file_option_menu(file_key)
                current = self.paths.get(file_key, "")
                if current in self.detected_files[file_key]:
                    index = self.detected_files[file_key].index(current) + 1
                    cmds.optionMenu(self.ui[f"{file_key}_menu"], edit=True, select=index)
        if "bake_ma_menu_low" in self.ui:
            self._clear_option_menu(self.ui["bake_ma_menu_low"])
            for p in self.detected_files["bake_ma"] or []:
                cmds.menuItem(label=os.path.basename(p), parent=self.ui["bake_ma_menu_low"])
            if not self.detected_files["bake_ma"]:
                cmds.menuItem(label="-- Aucun --", parent=self.ui["bake_ma_menu_low"])
        self.refresh_detected_file_labels()

        scan_logs = [
            ("high_ma", "Aucun fichier High MA (*_HIGH.ma) trouvé."),
            ("high_fbx", "Aucun fichier High FBX (*_HIGH.fbx) trouvé."),
            ("bake_ma", "Aucun fichier Bake MA (*_BAKE.ma) trouvé."),
            ("low_fbx", "Aucun fichier Low FBX (*_LOW.fbx) trouvé."),
            ("final_scene_ma", "Aucune final scene MA (fichier .ma sans suffixe) trouvée."),
            ("final_asset_fbx", "Aucun Final Asset FBX (fichier .fbx sans suffixe _high/_low) trouvé."),
        ]
        for file_key, warning_msg in scan_logs:
            count = len(found_files[file_key])
            if not count:
                self.log("WARNING", "Scan", warning_msg)
            else:
                label = file_key.replace("_", " ").title()
                self.log("INFO", "Scan", f"{count} fichier(s) {label} détecté(s).")
                self.log("INFO", "Scan", f"{file_key.upper()} actif: {self.paths.get(file_key, '-- vide --')}")

    def _populate_root_option_menu(self, root_key: str) -> None:
        menu = self.ui[f"{root_key}_root_menu"]
        items = [n for n in self.detected_roots[root_key] if cmds.objExists(n)]
        preferred_group = self._preferred_group_root_for_detected(root_key)
        items = self._inject_preferred_root(items, preferred_group, append_only=True)
        self.detected_roots[root_key] = items
        self._clear_option_menu(menu)

        if not items:
            label_map = {
                "high": "High root non détecté",
                "placeholder": "Placeholder root non détecté",
                "low": "Low root non détecté",
                "bake_high": "Bake High root non détecté",
                "bake_low": "Bake Low root non détecté",
                "final_asset_ma": "Final Asset MA root non détecté",
                "final_asset_fbx": "Final Asset FBX root non détecté",
            }
            label = label_map.get(root_key, f"{root_key} root non détecté")
            cmds.menuItem(label=label, parent=menu)
            return

        for node in items:
            cmds.menuItem(label=self._format_node_menu_label(node), parent=menu)

        cmds.optionMenu(menu, edit=True, select=1)

    def refresh_root_ui(self) -> None:
        for root_key in ["high", "placeholder", "low", "bake_high", "bake_low", "final_asset_ma", "final_asset_fbx"]:
            if f"{root_key}_root_menu" in self.ui:
                self._populate_root_option_menu(root_key)
        self.refresh_manual_root_menus()

    def _manual_root_candidates(self, source_key: str) -> List[str]:
        if source_key == "high_ma":
            return self._find_root_candidates("high", namespace=self.context["ma_namespace"])
        if source_key == "placeholder_ma":
            return self._find_root_candidates("placeholder", namespace=self.context["ma_namespace"])
        if source_key == "high_fbx":
            return self._find_root_candidates("high", namespace=self.context["fbx_namespace"])
        if source_key == "bake_high":
            return self._find_root_candidates("high", namespace=self.context["bake_ma_namespace"])
        if source_key == "low_fbx":
            return self._find_root_candidates("low", namespace=self.context["low_fbx_namespace"])
        if source_key == "bake_low":
            return self._find_root_candidates("low", namespace=self.context["bake_ma_namespace"])
        if source_key == "final_ma":
            return self._find_root_candidates("final", namespace=self.context["final_asset_ma_namespace"])
        if source_key == "final_fbx":
            roots: Set[str] = set()
            for namespace in self._final_asset_fbx_namespaces():
                roots.update(self._find_root_candidates("final", namespace=namespace))
            return sorted(roots, key=lambda x: self._candidate_root_score(x), reverse=True)
        return []

    def _preferred_group_root_for_source(self, source_key: str) -> Optional[str]:
        preferred_by_source = {
            "high_ma": "High_MA_GRP",
            "high_fbx": "High_FBX_GRP",
            "placeholder_ma": "Placeholder_GRP",
            "low_fbx": "Low_FBX_GRP",
            "bake_high": "Bake_MA_GRP",
            "bake_low": "Bake_MA_GRP",
            "final_ma": "Final_Asset_MA_GRP",
            "final_fbx": "Final_Asset_FBX_GRP",
        }
        return self._resolve_existing_group_node(preferred_by_source.get(source_key, ""))

    def _preferred_group_root_for_detected(self, root_key: str) -> Optional[str]:
        source_by_root_key = {
            "high": "high_ma",
            "placeholder": "placeholder_ma",
            "low": "low_fbx",
            "bake_high": "bake_high",
            "bake_low": "bake_low",
            "final_asset_ma": "final_ma",
            "final_asset_fbx": "final_fbx",
        }
        source_key = source_by_root_key.get(root_key, "")
        if not source_key:
            return None
        return self._preferred_group_root_for_source(source_key)

    def _resolve_existing_group_node(self, group_name: str) -> Optional[str]:
        if not group_name:
            return None
        if not cmds.objExists(group_name):
            return None
        long_names = cmds.ls(group_name, long=True, type="transform") or []
        return long_names[0] if long_names else group_name

    def _inject_preferred_root(self, values: List[str], preferred: Optional[str], append_only: bool = False) -> List[str]:
        ordered: List[str] = []
        if preferred and cmds.objExists(preferred) and not append_only:
            ordered.append(preferred)
        for node in values:
            if node and cmds.objExists(node) and node not in ordered:
                ordered.append(node)
        if preferred and cmds.objExists(preferred) and append_only and preferred not in ordered:
            ordered.append(preferred)
        return ordered

    def refresh_manual_root_menus(self) -> None:
        for menu_key, source_key in self.manual_root_menu_sources.items():
            menu = self.ui.get(menu_key)
            qt_row = self.manual_root_qt_rows.get(menu_key)
            if qt_row is None and (not menu or not cmds.optionMenu(menu, exists=True)):
                continue
            current = self.get_manual_selected_root(menu_key)
            overrides = [n for n in self.manual_root_overrides.get(menu_key, []) if cmds.objExists(n)]
            detected = [n for n in self._manual_root_candidates(source_key) if cmds.objExists(n)]
            preferred_group = self._preferred_group_root_for_source(source_key)
            values = self._inject_preferred_root(overrides + detected, preferred_group, append_only=True)
            self.manual_root_overrides[menu_key] = overrides
            self.manual_root_menu_values[menu_key] = values
            if qt_row is not None:
                combo = qt_row.path_combo
                combo.blockSignals(True)
                combo.clear()
                if not values:
                    combo.addItem("-- Aucun root --")
                    combo.setEnabled(False)
                else:
                    for node in values:
                        combo.addItem(self._format_node_menu_label(node), node)
                    idx = values.index(current) if current in values else 0
                    combo.setCurrentIndex(idx)
                    combo.setEnabled(True)
                combo.blockSignals(False)
                continue
            self._clear_option_menu(menu)
            if not values:
                cmds.menuItem(label="-- Aucun root --", parent=menu)
                self._update_manual_root_fulltext(menu_key)
                continue
            for node in values:
                cmds.menuItem(label=self._format_node_menu_label(node), parent=menu)
            idx = values.index(current) + 1 if current in values else 1
            cmds.optionMenu(menu, e=True, select=idx)
            self._update_manual_root_fulltext(menu_key)

    def _update_manual_root_fulltext(self, menu_key: str) -> None:
        fulltext_key = self.manual_root_fulltext_controls.get(menu_key)
        fulltext_control = self.ui.get(fulltext_key) if fulltext_key else None
        if not fulltext_control or not cmds.scrollField(fulltext_control, exists=True):
            return
        root = self.get_manual_selected_root(menu_key)
        text = root if root else "-- Aucun root --"
        cmds.scrollField(fulltext_control, e=True, text=text)

    def get_manual_selected_root(self, menu_key: str) -> Optional[str]:
        values = self.manual_root_menu_values.get(menu_key, [])
        qt_row = self.manual_root_qt_rows.get(menu_key)
        if qt_row is not None:
            if not values:
                return None
            idx = max(0, min(qt_row.path_combo.currentIndex(), len(values) - 1))
            root = values[idx]
            return root if cmds.objExists(root) else None
        menu = self.ui.get(menu_key)
        if not values or not menu or not cmds.optionMenu(menu, exists=True):
            return None
        index = max(1, cmds.optionMenu(menu, q=True, select=True)) - 1
        index = max(0, min(index, len(values) - 1))
        root = values[index]
        return root if cmds.objExists(root) else None

    def set_manual_root_from_selection(self, menu_key: str) -> None:
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            self.log("WARNING", "Selection", "Aucun objet sélectionné.")
            return
        node = sel[0]
        if cmds.nodeType(node) == "mesh":
            parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
            if parent:
                node = parent[0]
        overrides = self.manual_root_overrides.setdefault(menu_key, [])
        if node in overrides:
            overrides.remove(node)
        overrides.insert(0, node)
        self.refresh_manual_root_menus()
        values = self.manual_root_menu_values.get(menu_key, [])
        if node in values:
            qt_row = self.manual_root_qt_rows.get(menu_key)
            if qt_row is not None:
                qt_row.path_combo.setCurrentIndex(values.index(node))
            elif menu_key in self.ui:
                cmds.optionMenu(self.ui[menu_key], e=True, select=values.index(node) + 1)
        self._update_manual_root_fulltext(menu_key)
        self.log("INFO", "RootSelect", f"Root manuel défini: {node}", [node])

    def on_manual_root_changed(self, menu_key: str) -> None:
        self._update_manual_root_fulltext(menu_key)
        root = self.get_manual_selected_root(menu_key)
        if root:
            self.log("INFO", "RootSelect", f"Root sélectionné: {root}", [root])

    def on_root_selection_changed(self, root_key: str) -> None:
        root = self.get_detected_root(root_key)
        if root:
            self.log(
                "INFO",
                "RootDetect",
                f"{root_key.capitalize()} root sélectionné: {root}",
                [root],
            )

    def get_detected_root(self, root_key: str) -> Optional[str]:
        candidates = self.detected_roots[root_key]
        if not candidates:
            return None
        menu_name = self.ui.get(f"{root_key}_root_menu")
        if menu_name and cmds.optionMenu(menu_name, exists=True):
            index = cmds.optionMenu(menu_name, q=True, select=True) - 1
            index = max(0, min(index, len(candidates) - 1))
        else:
            index = 0
        root = candidates[index]
        return root if cmds.objExists(root) else None

    def set_root_from_selection(self, root_key: str) -> None:
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            self.log("WARNING", "Selection", "Aucun objet sélectionné.")
            return
        if root_key == "high" and self._is_placeholder_node(sel[0]):
            self.log(
                "WARNING",
                "RootDetect",
                "Sélection ignorée pour High root : nom contenant 'placeholder' détecté (priorité Placeholder).",
                [sel[0]],
            )
            return

        current = self.detected_roots[root_key][:]
        if sel[0] not in current:
            current.insert(0, sel[0])
        self.detected_roots[root_key] = current
        self.refresh_root_ui()
        self.log(
            "INFO",
            "RootDetect",
            f"{root_key.capitalize()} root défini depuis la sélection: {sel[0]}",
            [sel[0]],
        )

    def _candidate_root_score(self, node: str) -> Tuple[int, int, int]:
        descendants = cmds.listRelatives(node, allDescendents=True, fullPath=True) or []
        mesh_shapes = cmds.listRelatives(node, allDescendents=True, fullPath=True, type="mesh") or []
        mesh_shapes = [m for m in mesh_shapes if not cmds.getAttr(m + ".intermediateObject")]

        depth = node.count("|")
        has_shape = 1 if (cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []) else 0
        return (len(mesh_shapes), len(descendants) + has_shape, -depth)

    def _transform_namespace(self, node: str) -> str:
        short = self._short_name(node)
        if ":" not in short:
            return ""
        return short.split(":")[0]

    def _list_mesh_transforms_in_namespace(self, namespace: str) -> List[str]:
        shapes = cmds.ls(f"{namespace}:*", long=True, type="mesh") or []
        transforms: List[str] = []
        for shape in shapes:
            if cmds.getAttr(shape + ".intermediateObject"):
                continue
            parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parent:
                transforms.append(parent[0])
        return sorted(set(transforms))

    def _matches_asset_kind(self, node: str, asset_kind: str) -> bool:
        short_name = self._short_name(node)
        short_without_ns = self._strip_namespaces_from_name(short_name).lower()
        if asset_kind == "placeholder":
            return (
                short_without_ns.endswith(ROOT_SUFFIXES["placeholder"])
                or self._is_placeholder_node(node)
                or self._path_contains_placeholder_token(node)
            )
        if asset_kind == "high":
            return self._path_matches_suffix(node, ROOT_SUFFIXES["high"]) and not self._path_contains_placeholder_token(node)
        if asset_kind == "low":
            return self._path_matches_suffix(node, ROOT_SUFFIXES["low"]) and not self._path_contains_placeholder_token(node)
        if asset_kind == "final":
            return not self._path_has_any_suffix(node, ("_high", "_low", "_placeholder", "_bake"))
        return False

    def _mesh_matches_active_asset(self, node: str) -> bool:
        if not self.active_asset:
            return True
        normalized_asset = self._normalize_asset_token(self.active_asset)
        if not normalized_asset:
            return True
        short = self._normalize_asset_token(self._strip_namespaces_from_name(self._short_name(node)))
        if short.startswith(normalized_asset) or normalized_asset in short:
            return True
        for segment in [seg for seg in node.split("|") if seg]:
            cleaned = self._normalize_asset_token(self._strip_namespaces_from_name(segment))
            if cleaned.startswith(normalized_asset) or normalized_asset in cleaned:
                return True
        return False

    def _resolve_functional_root_from_mesh(self, mesh_transform: str, asset_kind: str) -> str:
        current = mesh_transform
        while True:
            parent = cmds.listRelatives(current, parent=True, fullPath=True, type="transform") or []
            if not parent:
                return current
            parent = parent[0]
            if self._transform_namespace(parent) != self._transform_namespace(mesh_transform):
                return current

            parent_mesh_shapes = cmds.listRelatives(parent, allDescendents=True, fullPath=True, type="mesh") or []
            parent_mesh_transforms: Set[str] = set()
            for shape in parent_mesh_shapes:
                if cmds.getAttr(shape + ".intermediateObject"):
                    continue
                parent_tr = cmds.listRelatives(shape, parent=True, fullPath=True) or []
                if parent_tr:
                    parent_mesh_transforms.add(parent_tr[0])
            if not parent_mesh_transforms:
                return current

            if all(self._matches_asset_kind(tr, asset_kind) for tr in parent_mesh_transforms):
                current = parent
                continue
            return current

    def _find_root_candidates(self, asset_kind: str, namespace: Optional[str] = None) -> List[str]:
        if namespace:
            mesh_transforms = self._list_mesh_transforms_in_namespace(namespace)
        else:
            shapes = cmds.ls(type="mesh", long=True) or []
            mesh_transforms = []
            for shape in shapes:
                if cmds.getAttr(shape + ".intermediateObject"):
                    continue
                parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
                if parent:
                    mesh_transforms.append(parent[0])
            mesh_transforms = sorted(set(mesh_transforms))

        matching_meshes = [m for m in mesh_transforms if self._matches_asset_kind(m, asset_kind) and self._mesh_matches_active_asset(m)]
        roots = [self._resolve_functional_root_from_mesh(mesh, asset_kind) for mesh in matching_meshes]
        return sorted(set(roots), key=lambda x: self._candidate_root_score(x), reverse=True)

    def _detect_and_store_roots_for_import(self, import_key: str) -> None:
        if import_key == "high_ma":
            namespace = self.context["ma_namespace"]
            self.detected_roots["high"] = self._find_root_candidates("high", namespace=namespace)
            self.detected_roots["placeholder"] = self._find_root_candidates("placeholder", namespace=namespace)
        elif import_key == "high_fbx":
            namespace = self.context["fbx_namespace"]
            self.detected_roots["high"] = self._find_root_candidates("high", namespace=namespace)
        elif import_key == "low_fbx":
            namespace = self.context["low_fbx_namespace"]
            self.detected_roots["low"] = self._resolve_low_roots_for_logs()
        elif import_key == "bake_ma":
            namespace = self.context["bake_ma_namespace"]
            self.detected_roots["bake_high"] = self._find_root_candidates("high", namespace=namespace)
            self.detected_roots["bake_low"] = self._find_root_candidates("low", namespace=namespace)
        elif import_key == "final_asset_ma":
            namespace = self.context["final_asset_ma_namespace"]
            self.detected_roots["final_asset_ma"] = self._find_root_candidates("final", namespace=namespace)
        elif import_key == "final_asset_fbx":
            namespace = self.context["final_asset_fbx_namespace"]
            self.detected_roots["final_asset_fbx"] = self._find_root_candidates("final", namespace=namespace)
            self.context["final_asset_fbx_namespaces"] = [namespace]

        self.refresh_root_ui()

    def _log_root_detection(self, root_key: str, label: str) -> None:
        candidates = self.detected_roots.get(root_key, [])
        if not candidates:
            self.log("WARNING", "RootDetect", f"{label} root non détecté.")
            return
        self.log("INFO", "RootDetect", f"{label} roots détectés : {len(candidates)}")
        self.log("INFO", "RootDetect", f"{label} root(s) : {self._preview_list(candidates)}", candidates[:80])
        if len(candidates) > 1:
            self.log("INFO", "RootDetect", f"{label}: sélection manuelle possible via le menu de roots.")

    def auto_detect_scene_roots(self) -> None:
        high_candidates = self._find_root_candidates("high")
        placeholder_candidates = self._find_root_candidates("placeholder")

        self.detected_roots["high"] = high_candidates
        self.detected_roots["placeholder"] = placeholder_candidates
        self.refresh_root_ui()
        self._log_root_detection("high", "High")
        self._log_root_detection("placeholder", "Placeholder")

    def get_high_root(self) -> Optional[str]:
        return self.get_detected_root("high")

    def get_placeholder_root(self) -> Optional[str]:
        return self.get_detected_root("placeholder")

    def _collect_mesh_transforms(self, root: Optional[str] = None) -> List[str]:
        if root and cmds.objExists(root):
            shapes = cmds.listRelatives(root, allDescendents=True, fullPath=True, type="mesh") or []
            direct_shape = cmds.listRelatives(root, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            shapes.extend(direct_shape)
        else:
            shapes = cmds.ls(type="mesh", long=True) or []

        transforms = []
        for shape in shapes:
            if cmds.getAttr(shape + ".intermediateObject"):
                continue
            parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parent:
                transforms.append(parent[0])

        transforms = sorted(list(set(transforms)))
        return [m for m in transforms if self._mesh_matches_active_asset(m)]

    def _mesh_signature(self, mesh_transform: str) -> Tuple[int, int, int]:
        shape = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
        if not shape:
            return 0, 0, 0
        shape = shape[0]
        return (
            cmds.polyEvaluate(shape, vertex=True),
            cmds.polyEvaluate(shape, edge=True),
            cmds.polyEvaluate(shape, face=True),
        )

    def _short_name(self, node: str) -> str:
        return node.split("|")[-1]

    def _strip_namespaces_from_name(self, name: str) -> str:
        parts = name.split(":")
        return (parts[-1] if parts else name).strip()

    def _contains_placeholder_token(self, text: str) -> bool:
        return PLACEHOLDER_TOKEN in text.lower()

    def _is_placeholder_node(self, node: str) -> bool:
        short_name = self._short_name(node)
        short_without_ns = self._strip_namespaces_from_name(short_name)
        return self._contains_placeholder_token(short_without_ns) or self._contains_placeholder_token(short_name)

    def _path_contains_placeholder_token(self, node: str) -> bool:
        for segment in [seg for seg in node.split("|") if seg]:
            if self._contains_placeholder_token(self._strip_namespaces_from_name(segment)):
                return True
            if self._contains_placeholder_token(segment):
                return True
        return False

    def _path_matches_suffix(self, node: str, suffix: str) -> bool:
        suffix = suffix.lower()
        for segment in [seg for seg in node.split("|") if seg]:
            normalized = self._strip_namespaces_from_name(segment).lower()
            if normalized.endswith(suffix):
                return True
        return False

    def _path_has_any_suffix(self, node: str, suffixes: Tuple[str, ...]) -> bool:
        lowered_suffixes = tuple(s.lower() for s in suffixes)
        for segment in [seg for seg in node.split("|") if seg]:
            normalized = self._strip_namespaces_from_name(segment).lower()
            if normalized.endswith(lowered_suffixes):
                return True
        return False

    def _normalized_segments(self, path: str) -> List[str]:
        return [self._strip_namespaces_from_name(seg) for seg in path.split("|") if seg]

    def _normalized_relative_mesh_key(self, mesh_transform: str, root: Optional[str] = None) -> str:
        mesh_segments = self._normalized_segments(mesh_transform)
        if root and cmds.objExists(root):
            root_segments = self._normalized_segments(root)
            if mesh_segments[: len(root_segments)] == root_segments:
                mesh_segments = mesh_segments[len(root_segments):]
        elif len(mesh_segments) > 1:
            mesh_segments = mesh_segments[1:]
        return "/".join(mesh_segments)

    def _normalized_mesh_leaf_key(self, mesh_transform: str) -> str:
        short_name = self._short_name(mesh_transform)
        leaf = self._strip_namespaces_from_name(short_name).lower().strip()
        leaf = re.sub(r"[\s_\-]+", "_", leaf)
        leaf = re.sub(r"(_high|_low|_placeholder)$", "", leaf)
        return leaf.strip("_")

    def _build_mesh_match_pairs(
        self,
        source_meshes_a: List[str],
        source_meshes_b: List[str],
        label_a: str,
        label_b: str,
    ) -> Dict[str, object]:
        grouped_a: Dict[str, List[str]] = {}
        grouped_b: Dict[str, List[str]] = {}
        for mesh in source_meshes_a:
            key = self._normalized_mesh_leaf_key(mesh)
            grouped_a.setdefault(key, []).append(mesh)
            self.log("INFO", "MeshMatch", f"Matching key {label_a} = {key} | {mesh}")
        for mesh in source_meshes_b:
            key = self._normalized_mesh_leaf_key(mesh)
            grouped_b.setdefault(key, []).append(mesh)
            self.log("INFO", "MeshMatch", f"Matching key {label_b} = {key} | {mesh}")

        all_keys = sorted(set(grouped_a.keys()) | set(grouped_b.keys()))
        pairs: List[Tuple[str, str]] = []
        unmatched_a: List[str] = []
        unmatched_b: List[str] = []
        ambiguous_keys: List[str] = []

        for key in all_keys:
            a_candidates = grouped_a.get(key, [])
            b_candidates = grouped_b.get(key, [])
            if len(a_candidates) == 1 and len(b_candidates) == 1:
                pairs.append((a_candidates[0], b_candidates[0]))
                continue

            if len(a_candidates) > 1 or len(b_candidates) > 1:
                ambiguous_keys.append(key)
                self.log(
                    "WARNING",
                    "MeshMatch",
                    f"Ambiguous leaf key: {key} ({label_a}={len(a_candidates)}, {label_b}={len(b_candidates)}).",
                )

            remaining_b: Set[str] = set(b_candidates)
            for mesh_a in a_candidates:
                a_data = self._mesh_data_signature(mesh_a)
                a_dims, a_center = self._mesh_bbox_dims_and_center_world(mesh_a)
                scored: List[Tuple[Tuple[float, float, float, float], str]] = []
                for mesh_b in remaining_b:
                    b_data = self._mesh_data_signature(mesh_b)
                    b_dims, b_center = self._mesh_bbox_dims_and_center_world(mesh_b)
                    topo_delta = float(
                        abs(int(a_data["v"]) - int(b_data["v"])) +
                        abs(int(a_data["e"]) - int(b_data["e"])) +
                        abs(int(a_data["f"]) - int(b_data["f"]))
                    )
                    bbox_delta = tuple(abs(a_dims[i] - b_dims[i]) for i in range(3))
                    center_delta = tuple(abs(a_center[i] - b_center[i]) for i in range(3))
                    score = (
                        topo_delta,
                        sum(bbox_delta) + sum(center_delta),
                        max(bbox_delta),
                        max(center_delta),
                    )
                    scored.append((score, mesh_b))

                if not scored:
                    unmatched_a.append(mesh_a)
                    continue

                scored.sort(key=lambda item: item[0])
                best_score, best_mesh_b = scored[0]
                if len(scored) > 1 and scored[1][0] == best_score:
                    self.log("WARNING", "MeshMatch", f"Ambiguous mesh match for key: {key}. Unable to match meshes despite similar leaf names.")
                    unmatched_a.append(mesh_a)
                    continue

                if best_score[0] == 0.0:
                    self.log("INFO", "MeshMatch", f"Fallback by bbox/topology used for: {key} ({mesh_a} -> {best_mesh_b})")
                else:
                    self.log("WARNING", "MeshMatch", f"Fallback pairing with topology delta for key '{key}': {mesh_a} -> {best_mesh_b}")
                pairs.append((mesh_a, best_mesh_b))
                remaining_b.remove(best_mesh_b)

            unmatched_b.extend(sorted(remaining_b))

        return {
            "pairs": pairs,
            "unmatched_a": unmatched_a,
            "unmatched_b": unmatched_b,
            "ambiguous_keys": sorted(set(ambiguous_keys)),
        }

    def _mesh_data_signature(self, mesh_transform: str, root: Optional[str] = None) -> Dict[str, object]:
        shape = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
        if not shape:
            return {
                "path": mesh_transform,
                "key": self._normalized_relative_mesh_key(mesh_transform, root),
                "v": 0,
                "e": 0,
                "f": 0,
                "uv_total": 0,
                "uv_sets": {},
                "parent_path": "/".join(self._normalized_segments(mesh_transform)[:-1]),
                "pivot_world": tuple(cmds.xform(mesh_transform, q=True, ws=True, rotatePivot=True)),
                "translate_world": tuple(cmds.xform(mesh_transform, q=True, ws=True, translation=True)),
            }

        uv_info = self._mesh_uv_signature_by_set(mesh_transform)
        total_uv = sum(int(data.get("count", 0)) for data in uv_info.values())
        shape = shape[0]

        return {
            "path": mesh_transform,
            "key": self._normalized_relative_mesh_key(mesh_transform, root),
            "v": int(cmds.polyEvaluate(shape, vertex=True) or 0),
            "e": int(cmds.polyEvaluate(shape, edge=True) or 0),
            "f": int(cmds.polyEvaluate(shape, face=True) or 0),
            "uv_total": int(total_uv),
            "uv_sets": uv_info,
            "parent_path": "/".join(self._normalized_segments(mesh_transform)[:-1]),
            "pivot_world": tuple(cmds.xform(mesh_transform, q=True, ws=True, rotatePivot=True)),
            "translate_world": tuple(cmds.xform(mesh_transform, q=True, ws=True, translation=True)),
        }

    def _mesh_uv_signature_by_set(self, mesh_transform: str) -> Dict[str, Dict[str, Any]]:
        shape = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
        if not shape:
            return {}

        shape = shape[0]
        uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True) or []
        current_uv = cmds.polyUVSet(shape, query=True, currentUVSet=True) or []
        original_uv = current_uv[0] if current_uv else None
        uv_info: Dict[str, Dict[str, Any]] = {}

        for uv_set in uv_sets:
            try:
                cmds.polyUVSet(shape, currentUVSet=True, uvSet=uv_set)
            except RuntimeError:
                continue

            uv_count = int(cmds.polyEvaluate(shape, uvcoord=True) or 0)
            try:
                shell_count = int(cmds.polyEvaluate(shape, uvShell=True) or 0)
            except RuntimeError:
                shell_count = 0
            bbox_raw = cmds.polyEvaluate(shape, boundingBox2d=True) or ()
            bbox_values: List[float] = []
            for value in bbox_raw:
                if isinstance(value, (tuple, list)):
                    bbox_values.extend(float(v) for v in value)
                else:
                    bbox_values.append(float(value))
            uvs_raw = cmds.polyEditUV(f"{shape}.map[*]", query=True) or []
            uv_pairs = [
                (round(float(uvs_raw[i]), 6), round(float(uvs_raw[i + 1]), 6))
                for i in range(0, len(uvs_raw), 2)
            ]
            uv_info[uv_set] = {
                "count": uv_count,
                "shells": shell_count,
                "bbox": tuple(round(v, 6) for v in bbox_values),
                "uvs": tuple(sorted(uv_pairs)),
            }

        if original_uv and original_uv in uv_sets:
            try:
                cmds.polyUVSet(shape, currentUVSet=True, uvSet=original_uv)
            except RuntimeError:
                pass

        return uv_info

    def _compare_uv_set_signatures(
        self,
        uv_a: Dict[str, Dict[str, Any]],
        uv_b: Dict[str, Dict[str, Any]],
        category: str = "CompareUV",
    ) -> Tuple[bool, Dict[str, Any]]:
        details: Dict[str, Any] = {"missing_in_a": [], "missing_in_b": [], "set_mismatches": {}}
        all_sets = sorted(set(uv_a.keys()) | set(uv_b.keys()), key=lambda name: (0 if name == "map1" else 1 if name == "map2" else 2, name))

        for uv_set in all_sets:
            if uv_set not in uv_a:
                details["missing_in_a"].append(uv_set)
                continue
            if uv_set not in uv_b:
                details["missing_in_b"].append(uv_set)
                continue

            set_a = uv_a[uv_set]
            set_b = uv_b[uv_set]
            set_issues: List[str] = []
            if int(set_a.get("count", 0)) != int(set_b.get("count", 0)):
                set_issues.append("count differs")
            if int(set_a.get("shells", 0)) != int(set_b.get("shells", 0)):
                set_issues.append("shells differ")
            if tuple(set_a.get("bbox", ())) != tuple(set_b.get("bbox", ())):
                set_issues.append("bbox differs")
            if tuple(set_a.get("uvs", ())) != tuple(set_b.get("uvs", ())):
                set_issues.append("uv coordinates differ")
            if set_issues:
                details["set_mismatches"][uv_set] = set_issues

        uv_ok = not details["missing_in_a"] and not details["missing_in_b"] and not details["set_mismatches"]
        if not uv_ok:
            for uv_set in details["missing_in_a"]:
                self.log("FAIL", category, f"UV mismatch: {uv_set} missing on mesh A")
            for uv_set in details["missing_in_b"]:
                self.log("FAIL", category, f"UV mismatch: {uv_set} missing on mesh B")
            for uv_set, issues in details["set_mismatches"].items():
                for issue in issues:
                    self.log("FAIL", category, f"UV mismatch: {uv_set} {issue}")
        else:
            compared_sets = sorted(uv_a.keys(), key=lambda name: (0 if name == "map1" else 1 if name == "map2" else 2, name))
            if compared_sets:
                self.log("INFO", category, f"UV match OK: {', '.join(compared_sets)} correspond")
            else:
                self.log("INFO", category, "UV match OK: no UV sets found on either side")
        return uv_ok, details

    def _compare_mesh_uv_sets(
        self,
        mesh_a: str,
        mesh_b: str,
        category: str = "CompareUV",
    ) -> Tuple[bool, Dict[str, Any]]:
        uv_a = self._mesh_uv_signature_by_set(mesh_a)
        uv_b = self._mesh_uv_signature_by_set(mesh_b)
        return self._compare_uv_set_signatures(uv_a, uv_b, category=category)

    def _mesh_center_world(self, mesh_transform: str) -> Tuple[float, float, float]:
        bb = cmds.exactWorldBoundingBox(mesh_transform)
        return (
            (bb[0] + bb[3]) * 0.5,
            (bb[1] + bb[4]) * 0.5,
            (bb[2] + bb[5]) * 0.5,
        )

    def _mesh_bbox_dims_world(self, mesh_transform: str) -> Tuple[float, float, float]:
        bb = cmds.exactWorldBoundingBox(mesh_transform)
        return (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])

    def _mesh_bbox_dims_and_center_world(self, mesh_transform: str) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        bb = cmds.exactWorldBoundingBox(mesh_transform)
        dims = (bb[3] - bb[0], bb[4] - bb[1], bb[5] - bb[2])
        center = ((bb[0] + bb[3]) * 0.5, (bb[1] + bb[4]) * 0.5, (bb[2] + bb[5]) * 0.5)
        return dims, center

    def _world_union_bbox(self, nodes: List[str]) -> Optional[Tuple[float, float, float, float, float, float]]:
        existing = [n for n in nodes if cmds.objExists(n)]
        if not existing:
            return None
        bb = cmds.exactWorldBoundingBox(existing)
        return (bb[0], bb[1], bb[2], bb[3], bb[4], bb[5])

    def _bbox_dims(self, bbox: Tuple[float, float, float, float, float, float]) -> Tuple[float, float, float]:
        return (bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2])

    def _bbox_center(self, bbox: Tuple[float, float, float, float, float, float]) -> Tuple[float, float, float]:
        return ((bbox[0] + bbox[3]) * 0.5, (bbox[1] + bbox[4]) * 0.5, (bbox[2] + bbox[5]) * 0.5)

    def _vector_distance(self, a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5

    def _strip_suffix_ci(self, text: str, suffix: str) -> str:
        if text.lower().endswith(suffix.lower()):
            return text[: -len(suffix)]
        return text

    def _clean_texture_set_display_name(self, raw_name: str, high_root: Optional[str]) -> str:
        cleaned = self._strip_namespaces_from_name(raw_name)
        cleaned = self._strip_suffix_ci(cleaned, "_high").strip("_")
        if high_root and cmds.objExists(high_root):
            root_name = self._strip_namespaces_from_name(self._short_name(high_root))
            root_base = self._strip_suffix_ci(root_name, "_high").strip("_")
            root_base_ci = root_base.lower()
            cleaned_ci = cleaned.lower()
            if cleaned_ci.startswith(root_base_ci + "_"):
                cleaned = cleaned[len(root_base) + 1 :]
            elif cleaned_ci == root_base_ci:
                cleaned = root_base
        return cleaned.strip("_- ") or self._strip_namespaces_from_name(raw_name)

    def _mesh_quad_and_face_count(self, mesh_transform: str) -> Tuple[int, int]:
        face_count = int(cmds.polyEvaluate(mesh_transform, face=True) or 0)
        quad_count = 0
        for face_idx in range(face_count):
            face_info = cmds.polyInfo(f"{mesh_transform}.f[{face_idx}]", faceToVertex=True) or []
            if not face_info:
                continue
            tokens = [tok for tok in face_info[0].replace(":", " ").split() if tok.isdigit()]
            vertex_count = max(0, len(tokens) - 1)
            if vertex_count == 4:
                quad_count += 1
        return quad_count, face_count

    def _count_non_manifold_uv_components(self, mesh: str) -> int:
        count = 0
        for flag in ("nonManifoldUVEdges", "nonManifoldUVs", "nonManifoldUVVertices"):
            try:
                issues = cmds.polyInfo(mesh, **{flag: True}) or []
            except (TypeError, RuntimeError):
                continue
            count += len(issues)
        return count

    def _count_zero_space_uv_shells(self, mesh: str, uv_set: str) -> int:
        shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
        if not shapes:
            return 0
        shape = shapes[0]
        if not self._uv_set_on_shape(shape, uv_set):
            return 0
        try:
            cmds.polyUVSet(shape, currentUVSet=True, uvSet=uv_set)
        except RuntimeError:
            return 0
        try:
            shell_ids = cmds.polyEvaluate(shape, uvShellIds=True) or []
        except RuntimeError:
            return 0
        uvs_raw = cmds.polyEditUV(f"{shape}.map[*]", query=True) or []
        uv_count = min(len(shell_ids), len(uvs_raw) // 2)
        if uv_count <= 0:
            return 0

        shell_bounds: Dict[int, List[float]] = {}
        for idx in range(uv_count):
            shell_id = int(shell_ids[idx])
            u_val = float(uvs_raw[idx * 2])
            v_val = float(uvs_raw[idx * 2 + 1])
            if shell_id not in shell_bounds:
                shell_bounds[shell_id] = [u_val, u_val, v_val, v_val]
            else:
                b = shell_bounds[shell_id]
                b[0] = min(b[0], u_val)
                b[1] = max(b[1], u_val)
                b[2] = min(b[2], v_val)
                b[3] = max(b[3], v_val)
        eps = 1e-8
        return sum(1 for b in shell_bounds.values() if abs(b[1] - b[0]) <= eps or abs(b[3] - b[2]) <= eps)

    def _namespace_from_node(self, node: str) -> str:
        short = node.split("|")[-1]
        if ":" not in short:
            return ""
        return short.rsplit(":", 1)[0]

    def _node_is_in_namespace(self, node: str, namespace: str) -> bool:
        ns = self._namespace_from_node(node)
        return ns == namespace or ns.startswith(namespace + ":")

    def _path_ancestors(self, node: str) -> List[str]:
        parts = [p for p in node.split("|") if p]
        ancestors: List[str] = []
        for i in range(len(parts)):
            ancestors.append("|" + "|".join(parts[: i + 1]))
        return ancestors

    def _find_namespace_root_for_node(self, node: str, namespace: str) -> Optional[str]:
        for ancestor in self._path_ancestors(node):
            short = self._short_name(ancestor)
            if short == namespace or short.startswith(namespace + ":"):
                return ancestor
        return None

    def _roots_from_scope_meshes(self, scope_key: str, scope_meshes: List[str]) -> List[str]:
        roots: List[str] = []
        namespace = ""
        namespace_list: List[str] = []
        if scope_key == "high_fbx":
            namespace = self.context["fbx_namespace"]
        elif scope_key == "high_ma":
            namespace = self.context["ma_namespace"]
        elif scope_key == "bake_high":
            namespace = self.context["bake_ma_namespace"]
        elif scope_key == "low_fbx":
            namespace = self.context["low_fbx_namespace"]
        elif scope_key == "bake_low":
            namespace = self.context["bake_ma_namespace"]
        elif scope_key == "final_asset_ma":
            namespace = self.context["final_asset_ma_namespace"]
        elif scope_key == "final_asset_fbx":
            namespace_list = self._final_asset_fbx_namespaces()

        if scope_key == "placeholder":
            placeholder_root = self.get_placeholder_root()
            if placeholder_root and cmds.objExists(placeholder_root):
                return [placeholder_root]

        for mesh in scope_meshes:
            if not cmds.objExists(mesh):
                continue
            root = None
            if namespace_list:
                for candidate_ns in namespace_list:
                    root = self._find_namespace_root_for_node(mesh, candidate_ns)
                    if root:
                        break
            elif namespace:
                root = self._find_namespace_root_for_node(mesh, namespace)
            if not root:
                ancestors = self._path_ancestors(mesh)
                root = ancestors[0] if ancestors else None
            if root and cmds.objExists(root):
                roots.append(root)
        return sorted(set(roots))

    def _resolve_texture_scope_roots(self, resolution: Dict[str, Any]) -> Dict[str, Any]:
        scope_keys = resolution.get("scope_keys", [])
        per_scope = resolution.get("per_scope_meshes", {})
        all_scope_keys = ["placeholder", "high_ma", "high_fbx", "bake_high", "low_fbx", "bake_low", "final_asset_ma", "final_asset_fbx"]

        roots_per_scope: Dict[str, List[str]] = {}
        for key in all_scope_keys:
            meshes_for_key = per_scope.get(key, [])
            if not meshes_for_key:
                key_resolution = self.resolve_scope_targets(scope_keys=[key])
                meshes_for_key = key_resolution.get("per_scope_meshes", {}).get(key, [])
            roots_per_scope[key] = self._roots_from_scope_meshes(key, meshes_for_key)

        included_roots: List[str] = []
        for key in scope_keys:
            included_roots.extend(roots_per_scope.get(key, []))
        included_roots = sorted(set(included_roots))

        excluded_roots: Dict[str, List[str]] = {}
        for key in all_scope_keys:
            if key in scope_keys:
                continue
            excluded_roots[key] = roots_per_scope.get(key, [])

        primary_root = included_roots[0] if included_roots else None
        return {
            "roots_per_scope": roots_per_scope,
            "included_roots": included_roots,
            "excluded_roots": excluded_roots,
            "primary_root": primary_root,
        }

    def _collect_mesh_transforms_in_namespace(
        self,
        namespace: str,
        *,
        exclude_placeholder_named: bool = False,
    ) -> Tuple[List[str], List[str]]:
        if not namespace:
            return [], []
        shapes = cmds.ls(namespace + ":*", type="mesh", long=True) or []
        transforms = []
        placeholder_excluded: List[str] = []
        for shape in shapes:
            if cmds.getAttr(shape + ".intermediateObject"):
                continue
            parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parent:
                parent_transform = parent[0]
                if exclude_placeholder_named and (
                    self._is_placeholder_node(parent_transform) or self._path_contains_placeholder_token(parent_transform)
                ):
                    placeholder_excluded.append(parent_transform)
                    continue
                transforms.append(parent_transform)
        transforms = sorted(set(transforms))
        transforms = [m for m in transforms if self._mesh_matches_active_asset(m)]
        return transforms, sorted(set(placeholder_excluded))

    def _get_selected_scope_keys(self) -> List[str]:
        return HIGH_REVIEW_SCOPE_ORDER[:]

    def _resolve_scope_meshes(self, scope_keys: Optional[List[str]] = None) -> Tuple[List[str], Dict[str, List[str]]]:
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        return resolution["meshes"], resolution["per_scope_meshes"]

    def resolve_scope_targets(self, scope_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        scope_keys = scope_keys if scope_keys is not None else self._get_selected_scope_keys()
        normalized_scope_keys = [k for k in self.scope_keys if k in scope_keys]
        per_scope: Dict[str, List[str]] = {}
        roots_by_scope: Dict[str, List[str]] = {}
        classification_notes: Dict[str, List[str]] = {}
        for key in normalized_scope_keys:
            meshes: List[str] = []
            if key == "placeholder":
                placeholder_root = self.get_placeholder_root()
                meshes = self._collect_mesh_transforms(root=placeholder_root)
                roots_by_scope[key] = [placeholder_root] if placeholder_root else []
            elif key == "high_fbx":
                meshes, _ = self._collect_mesh_transforms_in_namespace(self.context["fbx_namespace"])
                roots_by_scope[key] = [self.context["fbx_namespace"]]
            elif key == "high_ma":
                meshes, placeholder_excluded = self._collect_mesh_transforms_in_namespace(
                    self.context["ma_namespace"],
                    exclude_placeholder_named=True,
                )
                high_root = self.get_high_root()
                roots_by_scope[key] = [high_root] if high_root else [self.context["ma_namespace"]]
                classification_notes[key] = placeholder_excluded
            elif key == "bake_high":
                bake_high_root = self.get_detected_root("bake_high")
                if bake_high_root and cmds.objExists(bake_high_root):
                    meshes = self._collect_mesh_transforms(root=bake_high_root)
                    roots_by_scope[key] = [bake_high_root]
                else:
                    bake_meshes, _ = self._collect_mesh_transforms_in_namespace(self.context["bake_ma_namespace"])
                    meshes = [m for m in bake_meshes if self._matches_asset_kind(m, "high")]
                    roots_by_scope[key] = [self.context["bake_ma_namespace"]]
            elif key == "low_fbx":
                low_root = self.get_detected_root("low")
                if low_root and cmds.objExists(low_root):
                    meshes = self._collect_mesh_transforms(root=low_root)
                    roots_by_scope[key] = [low_root]
                else:
                    meshes, _ = self._collect_mesh_transforms_in_namespace(self.context["low_fbx_namespace"])
                    meshes = [m for m in meshes if self._matches_asset_kind(m, "low")]
                    roots_by_scope[key] = [self.context["low_fbx_namespace"]]
            elif key == "bake_low":
                bake_low_root = self.get_detected_root("bake_low")
                if bake_low_root and cmds.objExists(bake_low_root):
                    meshes = self._collect_mesh_transforms(root=bake_low_root)
                    roots_by_scope[key] = [bake_low_root]
                else:
                    bake_meshes, _ = self._collect_mesh_transforms_in_namespace(self.context["bake_ma_namespace"])
                    meshes = [m for m in bake_meshes if self._matches_asset_kind(m, "low")]
                    roots_by_scope[key] = [self.context["bake_ma_namespace"]]
            elif key == "final_asset_ma":
                final_ma_root = self.get_detected_root("final_asset_ma")
                if final_ma_root and cmds.objExists(final_ma_root):
                    meshes = self._collect_mesh_transforms(root=final_ma_root)
                    roots_by_scope[key] = [final_ma_root]
                else:
                    meshes, _ = self._collect_mesh_transforms_in_namespace(self.context["final_asset_ma_namespace"])
                    meshes = [m for m in meshes if self._matches_asset_kind(m, "final")]
                    roots_by_scope[key] = [self.context["final_asset_ma_namespace"]]
            elif key == "final_asset_fbx":
                final_fbx_root = self.get_detected_root("final_asset_fbx")
                if final_fbx_root and cmds.objExists(final_fbx_root):
                    meshes = self._collect_mesh_transforms(root=final_fbx_root)
                    roots_by_scope[key] = [final_fbx_root]
                else:
                    merged_meshes: List[str] = []
                    namespaces = self._final_asset_fbx_namespaces()
                    for ns in namespaces:
                        ns_meshes, _ = self._collect_mesh_transforms_in_namespace(ns)
                        merged_meshes.extend(ns_meshes)
                    meshes = [m for m in sorted(set(merged_meshes)) if self._matches_asset_kind(m, "final")]
                    roots_by_scope[key] = namespaces
            per_scope[key] = sorted(set(meshes))
        merged = sorted(set([m for meshes in per_scope.values() for m in meshes]))
        return {
            "scope_keys": normalized_scope_keys,
            "per_scope_meshes": per_scope,
            "meshes": merged,
            "roots_by_scope": roots_by_scope,
            "classification_notes": classification_notes,
        }

    def _scope_label(self, scope_keys: List[str]) -> str:
        return ", ".join([self.scope_labels.get(k, k) for k in scope_keys])

    def _high_scope_sequence(self) -> List[Tuple[str, str]]:
        return [
            ("high_ma", "High .ma"),
            ("high_fbx", "High .fbx"),
            ("bake_high", "High du _bake.ma"),
        ]

    def _log_scope_resolution(self, category: str, resolution: Dict[str, Any]) -> None:
        scope_keys = resolution.get("scope_keys", [])
        per_scope = resolution.get("per_scope_meshes", {})
        roots_by_scope = resolution.get("roots_by_scope", {})
        classification_notes = resolution.get("classification_notes", {})
        merged = resolution.get("meshes", [])
        scope_label = self._scope_label(scope_keys) if scope_keys else "(aucun scope)"
        self.log("INFO", category, f"Scope demandé: {scope_label}")
        if not scope_keys:
            self.log("WARNING", category, "Aucun scope sélectionné dans l'UI.")
            return
        for key in scope_keys:
            roots = roots_by_scope.get(key, [])
            meshes = per_scope.get(key, [])
            pretty_roots = ", ".join([self._short_name(r) for r in roots if r]) if roots else "Aucun root résolu"
            self.log(
                "INFO",
                category,
                f"- {self.scope_labels.get(key, key)} | roots: {pretty_roots} | meshes: {len(meshes)}",
            )
            if key == "high_ma":
                excluded = classification_notes.get(key, [])
                if excluded:
                    self.log(
                        "INFO",
                        category,
                        f"- Priorité Placeholder active: {len(excluded)} objet(s) sous {self.context['ma_namespace']} exclus du scope High MA.",
                    )
                    for node in excluded[:20]:
                        self.log(
                            "INFO",
                            category,
                            "Objet détecté sous High_Ma_File | Nom contient PLACEHOLDER | Classé comme : Placeholder | Exclu de : High MA",
                            [node],
                        )
        self.log("INFO", category, f"Meshes ciblés (union des scopes): {len(merged)}")
        self.log("INFO", category, f"Placeholder inclus: {'Oui' if 'placeholder' in scope_keys else 'Non'}")
        self.log("INFO", category, f"High FBX inclus: {'Oui' if 'high_fbx' in scope_keys else 'Non'}")
        self.log("INFO", category, f"High MA inclus: {'Oui' if 'high_ma' in scope_keys else 'Non'}")
        self.log("INFO", category, f"Bake High inclus: {'Oui' if 'bake_high' in scope_keys else 'Non'}")

    def _fmt_vec(self, values: Tuple[float, float, float], precision: int = 4) -> str:
        rounded = tuple(round(v, precision) for v in values)
        return f"({rounded[0]}, {rounded[1]}, {rounded[2]})"

    def _fmt_size_percent(self, ratio: float) -> str:
        return f"{ratio * 100.0:.2f}% de la taille placeholder"

    def _placeholder_axis_deviation(self, ratio: float) -> float:
        return (abs(ratio - 1.0) * 100.0) if ratio != 0.0 else 100.0

    def _compute_root_children_texture_sets(
        self,
        analysis_roots: List[str],
        scope_meshes: List[str],
    ) -> Tuple[Dict[str, Dict[str, object]], List[str]]:
        sets: Dict[str, Dict[str, object]] = {}
        log_lines: List[str] = []
        valid_roots = [r for r in analysis_roots if r and cmds.objExists(r)]
        if not valid_roots:
            log_lines.append("Méthode groupes: aucun root valide résolu pour le scope actif.")
            return sets, log_lines

        scope_set = set(scope_meshes)
        for analysis_root in valid_roots:
            direct_children = cmds.listRelatives(analysis_root, children=True, fullPath=True, type="transform") or []
            log_lines.append(f"Root analysé : {self._short_name(analysis_root)}")
            log_lines.append("Éléments de premier niveau détectés :")

            for child in direct_children:
                child_meshes = [m for m in self._collect_mesh_transforms(root=child) if m in scope_set]
                if not child_meshes:
                    continue
                child_shapes = cmds.listRelatives(child, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
                child_kind = "mesh" if child_shapes else "group"
                child_name = self._short_name(child)
                log_lines.append(f"- {child_name} ({child_kind})")

                key = f"GRP_CHILD::{analysis_root}::{child}"
                display_name = self._clean_texture_set_display_name(child_name, analysis_root)
                sets[key] = {
                    "name": self._strip_namespaces_from_name(child_name),
                    "display_name": display_name,
                    "method": "group_root_children",
                    "objects": sorted(set(child_meshes)),
                }

        return sets, log_lines

    def _extract_namespaces_from_path(self, node_path: str) -> Set[str]:
        found: Set[str] = set()
        for segment in [s for s in node_path.split("|") if s]:
            if ":" not in segment:
                continue
            ns_chain = segment.rsplit(":", 1)[0]
            chain_parts = [p for p in ns_chain.split(":") if p]
            for i in range(len(chain_parts)):
                found.add(":".join(chain_parts[: i + 1]))
        return found

    def _is_allowed_namespace(self, namespace: str) -> bool:
        allowed_namespaces = sorted(set(self.allowed_review_namespaces).union({
            str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v
        }))
        for allowed in allowed_namespaces:
            if (
                namespace == allowed
                or namespace.startswith(allowed + ":")
                or namespace.startswith(allowed + "__")
            ):
                return True
        return False

    def _final_asset_fbx_namespaces(self) -> List[str]:
        namespaces = self.context.get("final_asset_fbx_namespaces", [])
        if namespaces:
            return [ns for ns in namespaces if isinstance(ns, str) and ns]
        fallback = self.context.get("final_asset_fbx_namespace", "")
        return [fallback] if isinstance(fallback, str) and fallback else []

    def _get_scan_namespaces(self) -> List[str]:
        all_nodes = cmds.ls(long=True) or []
        dag_ns: Set[str] = set()
        for node in all_nodes:
            dag_ns.update(self._extract_namespaces_from_path(node))

        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        dag_ns.update({n for n in namespaces if n and n not in {":", "UI", "shared"}})
        filtered = [n for n in dag_ns if not self._is_allowed_namespace(n) and n not in {"UI", "shared", ":"}]
        return sorted(filtered, key=lambda x: (x.count(":"), x))

    def _infer_set_sources(self, objects: List[str], per_scope_meshes: Dict[str, List[str]]) -> List[str]:
        candidate_sources = ["high_ma", "high_fbx", "bake_high", "placeholder"]
        obj_set = set(objects)
        sources: List[str] = []
        for source in candidate_sources:
            meshes = set(per_scope_meshes.get(source, []))
            if meshes and obj_set.intersection(meshes):
                sources.append(source)
        if not sources:
            return ["unknown"]
        return sources

    def _list_ui_key_for_context(self, context_key: str) -> str:
        if context_key == "high":
            return "texture_sets_list"
        if context_key == "bake_high":
            return "bake_high_texture_sets_list"
        if context_key == "bake_low":
            return "bake_low_texture_sets_list"
        if context_key == "final_asset":
            return "final_texture_sets_list"
        return "low_texture_sets_list"

    def _refresh_texture_sets_list_ui(self, context_key: str = "high") -> None:
        list_ui_key = self._list_ui_key_for_context(context_key)
        if list_ui_key not in self.ui:
            return
        previous_selection = self._selected_texture_set_names(context_key)
        self.texture_set_label_to_key_by_context[context_key] = {}
        self.texture_set_section_headers_by_context[context_key] = set()
        self._clear_list_control(list_ui_key)
        material_sets = self.material_sets_by_context.get(context_key, {})

        grouped_keys: Dict[str, List[str]] = {}
        source_order = ["high_ma", "high_fbx", "bake_high", "placeholder", "mixed", "unknown"]
        for set_key in sorted(material_sets.keys()):
            data = material_sets[set_key]
            sources = data.get("sources", []) or ["unknown"]
            source_key = "mixed" if len(sources) > 1 else sources[0]
            grouped_keys.setdefault(source_key, []).append(set_key)

        for source in source_order:
            set_keys = grouped_keys.get(source, [])
            if not set_keys:
                continue
            header = f"━━ {self.scope_labels.get(source, source.replace('_', ' ').title())} ━━"
            self.texture_set_section_headers_by_context[context_key].add(header)
            self._append_list_control_item(list_ui_key, header)
            for set_name in set_keys:
                data = material_sets[set_name]
                method = data.get("method", "unknown")
                count = len(data.get("objects", []))
                display_name = data.get("display_name", data.get("name", set_name))
                quad_count = int(data.get("quad_count", 0))
                percent_of_total = float(data.get("percent_of_total", 0.0))
                visible = self.texture_set_visibility.get(set_name, True)
                state = "Shown" if visible else "Hidden"
                if set_name.startswith("MAT::"):
                    is_qds = display_name.startswith("QDS_")
                    qds_prefix = "[OK-QDS]" if is_qds else "[NON-QDS]"
                    face_count = int(data.get("face_count", 0))
                    label = f"  {qds_prefix} {display_name} - {percent_of_total:.1f}% faces ({face_count}) | {count} obj(s) | {state}"
                else:
                    label = f"  {display_name} - {quad_count} Quads - {percent_of_total:.1f}% | {method} | {count} obj(s) | {state}"
                unique_label = label
                duplicate_index = 2
                while unique_label in self.texture_set_label_to_key_by_context[context_key]:
                    unique_label = f"{label} [{duplicate_index}]"
                    duplicate_index += 1
                self.texture_set_label_to_key_by_context[context_key][unique_label] = set_name
                self._append_list_control_item(list_ui_key, unique_label)
        self._restore_texture_set_selection(previous_selection, context_key)

    def _selected_texture_set_names(self, context_key: str = "high") -> List[str]:
        list_ui_key = self._list_ui_key_for_context(context_key)
        if list_ui_key not in self.ui:
            return []
        selected = self._selected_list_control_items(list_ui_key)
        names: List[str] = []
        labels_map = self.texture_set_label_to_key_by_context.get(context_key, {})
        headers = self.texture_set_section_headers_by_context.get(context_key, set())
        material_sets = self.material_sets_by_context.get(context_key, {})
        for label in selected:
            if label in headers:
                continue
            set_name = labels_map.get(label)
            if set_name in material_sets:
                names.append(set_name)
        return names

    def _restore_texture_set_selection(self, set_names: List[str], context_key: str = "high") -> None:
        if not set_names:
            return
        list_ui_key = self._list_ui_key_for_context(context_key)
        if list_ui_key not in self.ui:
            return
        labels_to_select = [label for label, set_name in self.texture_set_label_to_key_by_context.get(context_key, {}).items() if set_name in set_names]
        if labels_to_select:
            self._set_selected_list_control_items(list_ui_key, labels_to_select)

    def on_texture_set_selection_changed(self, context_key: str = "high") -> None:
        _ = context_key
        # IMPORTANT UX: selecting an entry in the materials list must not trigger
        # any scene selection or isolate action. Isolation is button-driven only.
        return

    def set_texture_set_visibility(self, visible: bool, selected_only: bool = False) -> None:
        material_sets = self.material_sets_by_context.get("high", {})
        target_sets = self._selected_texture_set_names("high") if selected_only else list(material_sets.keys())
        if not target_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set sélectionné.")
            return
        impacted_objects: List[str] = []
        for set_name in target_sets:
            objs = material_sets[set_name].get("objects", [])
            for obj in objs:
                if cmds.objExists(obj):
                    try:
                        cmds.setAttr(obj + ".visibility", visible)
                        impacted_objects.append(obj)
                    except RuntimeError:
                        pass
            self.texture_set_visibility[set_name] = visible
        self._refresh_texture_sets_list_ui("high")
        if selected_only:
            self._restore_texture_set_selection(target_sets, "high")
        action = "affichés" if visible else "masqués"
        scope_label = self._scope_label(self.last_texture_scope) if self.last_texture_scope else "N/A"
        self.log("INFO", "TextureSets", f"Texture sets {action}: {', '.join(target_sets)} (scope source: {scope_label})", list(sorted(set(impacted_objects)))[:150])

    def toggle_selected_texture_sets(self) -> None:
        material_sets = self.material_sets_by_context.get("high", {})
        target_sets = self._selected_texture_set_names("high")
        if not target_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set sélectionné pour toggle.")
            return
        impacted_objects: List[str] = []
        for set_name in target_sets:
            current = self.texture_set_visibility.get(set_name, True)
            new_state = not current
            objs = material_sets[set_name].get("objects", [])
            for obj in objs:
                if cmds.objExists(obj):
                    try:
                        cmds.setAttr(obj + ".visibility", new_state)
                        impacted_objects.append(obj)
                    except RuntimeError:
                        pass
            self.texture_set_visibility[set_name] = new_state
        self._refresh_texture_sets_list_ui("high")
        self._restore_texture_set_selection(target_sets, "high")
        self.log("INFO", "TextureSets", f"Toggle visibility appliqué à: {', '.join(target_sets)}", list(sorted(set(impacted_objects)))[:150])

    def isolate_selected_texture_sets(self) -> None:
        material_sets = self.material_sets_by_context.get("high", {})
        target_sets = self._selected_texture_set_names("high")
        if not target_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set sélectionné pour isolation.")
            return
        scene_transforms = cmds.ls(type="transform", long=True) or []
        default_camera_transforms = set(cmds.listRelatives(cmds.ls(type="camera") or [], parent=True, fullPath=True) or [])
        all_sets = list(material_sets.keys())
        hidden_objects: List[str] = []
        shown_objects: List[str] = []
        selected_objects: Set[str] = set()
        for set_name in all_sets:
            visible = set_name in target_sets
            objs = material_sets[set_name].get("objects", [])
            for obj in objs:
                if not cmds.objExists(obj):
                    continue
                if visible:
                    selected_objects.add(obj)
                try:
                    cmds.setAttr(obj + ".visibility", visible)
                    if visible:
                        shown_objects.append(obj)
                    else:
                        hidden_objects.append(obj)
                except RuntimeError:
                    continue
            self.texture_set_visibility[set_name] = visible

        keep_visible: Set[str] = set()
        for obj in selected_objects:
            keep_visible.update(self._path_ancestors(obj))
        for tr in scene_transforms:
            if tr in default_camera_transforms:
                continue
            target_visibility = tr in keep_visible
            try:
                if cmds.getAttr(tr + ".visibility", settable=True):
                    cmds.setAttr(tr + ".visibility", target_visibility)
            except RuntimeError:
                continue

        self._refresh_texture_sets_list_ui("high")
        self._restore_texture_set_selection(target_sets, "high")
        self.log(
            "INFO",
            "TextureSets",
            (
                f"Isolate Selected Sets appliqué à l'échelle scène "
                f"({len(target_sets)} set(s) visibles, scope source: {self._scope_label(self.last_texture_scope or self._get_selected_scope_keys())})."
            ),
            list(sorted(set(shown_objects + hidden_objects)))[:200],
        )

    def show_all_texture_sets(self) -> None:
        if not self.material_sets_by_context.get("high"):
            self.log("WARNING", "TextureSets", "Aucun texture set détecté. Lancez d'abord Run Texture Sets.")
            return
        for tr in cmds.ls(type="transform", long=True) or []:
            try:
                if cmds.getAttr(tr + ".visibility", settable=True):
                    cmds.setAttr(tr + ".visibility", True)
            except RuntimeError:
                continue
        self.set_texture_set_visibility(True, selected_only=False)

    # ----------------------------- Actions -----------------------------
    def _reference_ma_file(self, file_key: str, namespace_key: str, category_label: str) -> None:
        path = self.paths.get(file_key, "")
        if not path:
            self.log("FAIL", "File", f"Aucun fichier {category_label} sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier {category_label} introuvable: {path}")
            return

        namespace = self.context[namespace_key]
        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError as exc:
                self.log("WARNING", "File", f"Namespace {namespace} déjà présent (merge impossible): {exc}")

        cmds.file(path, reference=True, type="mayaAscii", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        self.log("INFO", "File", f"{category_label} référencé sous namespace '{namespace}'.")
        self._detect_and_store_roots_for_import(file_key)
        if file_key == "bake_ma":
            self._log_root_detection("bake_high", "Bake High")
            self._log_root_detection("bake_low", "Bake Low")
        elif file_key == "final_asset_ma":
            self._log_root_detection("final_asset_ma", "Final Asset MA")

    def _reference_fbx_file(self, file_key: str, namespace_key: str, category_label: str) -> None:
        path = self.paths.get(file_key, "")
        if not path:
            self.log("FAIL", "File", f"Aucun fichier {category_label} sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier {category_label} introuvable: {path}")
            return

        namespace = self.context[namespace_key]
        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError:
                self.log("WARNING", "FBX", f"Namespace {namespace} déjà présent, merge impossible automatiquement.")

        cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        self.log("INFO", "FBX", f"{category_label} référencé sous namespace '{namespace}'.")
        self._detect_and_store_roots_for_import(file_key)
        if file_key == "low_fbx":
            self._log_root_detection("low", "Low")
        elif file_key == "final_asset_fbx":
            self._log_root_detection("final_asset_fbx", "Final Asset FBX")

    def load_ma_scene(self) -> None:
        self._log_step_header(1, "Load High.ma", category="Load")
        path = self.paths.get("high_ma", "")
        if not path:
            self.log("FAIL", "File", "Aucun fichier .ma sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier .ma introuvable: {path}")
            return

        namespace = self.context["ma_namespace"]
        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError as exc:
                self.log("WARNING", "File", f"Namespace {namespace} déjà présent (merge impossible): {exc}")

        before = set(cmds.ls(long=True) or [])
        cmds.file(path, reference=True, type="mayaAscii", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["ma_nodes"] = new_nodes
        self.context["ma_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]
        self.paths["high_ma"] = path
        self.log("INFO", "Load", f"High.ma référencé : {self._basename_from_path(path)}")
        self.log("INFO", "Load", f"Namespace utilisé : {namespace}")
        self.log("INFO", "Load", f"Meshes importés : {len(self.context['ma_meshes'])}")
        self._organize_high_ma_loaded_roots()

    def load_fbx_into_scene(self) -> None:
        path = self.paths.get("high_fbx", "")
        if not path:
            self.log("FAIL", "File", "Aucun fichier .fbx sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier .fbx introuvable: {path}")
            return

        namespace = self.context["fbx_namespace"]

        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError:
                self.log("WARNING", "FBX", f"Namespace {namespace} déjà présent, merge impossible automatiquement.")

        before = set(cmds.ls(long=True) or [])
        cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)

        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["fbx_nodes"] = new_nodes
        self.context["fbx_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]

        self.paths["high_fbx"] = path
        self.log("INFO", "Load", f"High.fbx référencé : {self._basename_from_path(path)}")
        self.log("INFO", "Load", f"Namespace utilisé : {namespace}")
        self.log("INFO", "Load", f"Meshes importés : {len(self.context['fbx_meshes'])}")
        self.detected_roots["high"] = self._find_root_candidates("high", namespace=namespace)
        self._log_root_detection("high", "High(FBX)")

    def load_low_fbx_scene(self) -> None:
        self._log_step_header(1, "Load Low.fbx", category="LowLoad")
        path = self.paths.get("low_fbx", "")
        if not path:
            self.log("FAIL", "LoadLow", "Aucun fichier _LOW.fbx sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "LoadLow", f"Fichier _LOW.fbx introuvable: {path}")
            return

        unload_map = [
            ("ma_namespace", "High.ma"),
            ("fbx_namespace", "High.fbx"),
            ("bake_ma_namespace", "Bake.ma"),
            ("final_asset_ma_namespace", "Final Scene.ma"),
        ]
        unloaded_labels = []
        for ns_key, label in unload_map:
            ns = self.context.get(ns_key, "")
            if ns and cmds.namespace(exists=ns):
                if self._unload_namespace_references(ns):
                    unloaded_labels.append(label)
        for ns in self._final_asset_fbx_namespaces():
            if ns and cmds.namespace(exists=ns):
                if self._unload_namespace_references(ns):
                    unloaded_labels.append(f"Final Asset.fbx ({ns})")
        self.log("INFO", "LoadLow", f"Références déchargées avant chargement : {', '.join(unloaded_labels) if unloaded_labels else 'Aucune'}")

        namespace = self.context["low_fbx_namespace"]
        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError:
                pass

        before = set(cmds.ls(long=True) or [])
        cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["low_fbx_nodes"] = new_nodes
        self.context["low_fbx_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]
        self.paths["low_fbx"] = path
        self.detected_roots["low"] = self._resolve_low_roots_for_logs()
        self.log("INFO", "LoadLow", f"Low.fbx référencé : {self._basename_from_path(path)}")
        self.log("INFO", "LoadLow", f"Namespace utilisé : {namespace}")
        self.log("INFO", "LoadLow", f"Meshes importés : {len(self.context['low_fbx_meshes'])}")
        self.log("INFO", "LoadLow", f"Low roots détectés : {self._preview_list(self.detected_roots['low'], max_items=20)}")
        self.refresh_root_ui()

    def load_bake_ma_scene(self) -> None:
        path = self.paths.get("bake_ma", "")
        if not path:
            self.log("FAIL", "File", "Aucun fichier _BAKE.ma sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier _BAKE.ma introuvable: {path}")
            return

        fbx_namespace = self.context["fbx_namespace"]
        if cmds.namespace(exists=fbx_namespace):
            self.log("INFO", "Scene", "High.fbx détecté en scène")
            self.log("INFO", "Scene", "Unload High.fbx avant chargement de Bake.ma")
            unload_ok = self._unload_namespace_references(fbx_namespace)
            if unload_ok:
                self.log("INFO", "Scene", "Résultat final : OK")
            else:
                self.log("FAIL", "Scene", "Résultat final : FAIL")
            self.context["fbx_nodes"] = []
            self.context["fbx_meshes"] = []
        else:
            self.log("INFO", "Scene", "Aucun High.fbx chargé, unload inutile")

        namespace = self.context["bake_ma_namespace"]
        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError as exc:
                self.log("WARNING", "File", f"Namespace {namespace} déjà présent (merge impossible): {exc}")

        before = set(cmds.ls(long=True) or [])
        cmds.file(path, reference=True, type="mayaAscii", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["bake_ma_nodes"] = new_nodes
        self.context["bake_ma_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]
        self.paths["bake_ma"] = path
        self.log("INFO", "Load", f"Bake Scene référencée : {self._basename_from_path(path)}")
        self.log("INFO", "Load", f"Namespace utilisé : {namespace}")
        self.log("INFO", "Load", f"Meshes importés : {len(self.context['bake_ma_meshes'])}")
        self.detected_roots["bake_high"] = self._find_root_candidates("high", namespace=namespace)
        self.detected_roots["bake_low"] = self._find_root_candidates("low", namespace=namespace)
        self._log_root_detection("bake_high", "Bake High")
        self._log_root_detection("bake_low", "Bake Low")

    def load_final_asset_ma_scene(self) -> None:
        path = self.paths.get("final_scene_ma", "")
        if not path:
            self.log("FAIL", "LoadFinal", "Aucun fichier Final Scene.ma sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "LoadFinal", f"Fichier Final Scene.ma introuvable: {path}")
            return

        namespace = self.context["final_asset_ma_namespace"]
        if cmds.namespace(exists=namespace):
            self._unload_namespace_references(namespace)
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError:
                pass

        before = set(cmds.ls(long=True) or [])
        cmds.file(path, reference=True, type="mayaAscii", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["final_asset_ma_nodes"] = new_nodes
        self.context["final_asset_ma_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]
        self.paths["final_scene_ma"] = path
        self.detected_roots["final_asset_ma"] = self._find_root_candidates("final", namespace=namespace)
        self.log("INFO", "LoadFinal", f"Final Scene référencée : {self._basename_from_path(path)}")
        self.log("INFO", "LoadFinal", f"Namespace utilisé : {namespace}")
        self.log("INFO", "LoadFinal", f"Meshes importés : {len(self.context['final_asset_ma_meshes'])}")
        self.log("INFO", "LoadFinal", f"Final roots détectés : {self._preview_list(self.detected_roots['final_asset_ma'], max_items=20)}")
        self.refresh_root_ui()

    def load_final_asset_fbx_scene(self) -> None:
        path = self.paths.get("final_asset_fbx", "")
        if not path:
            self.log("FAIL", "LoadFinal", "Aucun fichier Final Asset FBX sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "LoadFinal", f"Fichier Final Asset FBX introuvable: {path}")
            return
        namespace = self.context["final_asset_fbx_namespace"]
        if cmds.namespace(exists=namespace):
            self._unload_namespace_references(namespace)
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError:
                pass
        before = set(cmds.ls(long=True) or [])
        cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["final_asset_fbx_nodes"] = new_nodes
        self.context["final_asset_fbx_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]
        self.detected_roots["final_asset_fbx"] = self._find_root_candidates("final", namespace=namespace)
        self.context["final_asset_fbx_namespaces"] = [namespace]
        self.log("INFO", "LoadFinal", f"Final Asset FBX référencé : {self._basename_from_path(path)}")
        self.log("INFO", "LoadFinal", f"Namespace utilisé : {namespace}")
        self.log("INFO", "LoadFinal", f"Meshes importés : {len(self.context['final_asset_fbx_meshes'])}")
        self._log_root_detection("final_asset_fbx", "Final Asset FBX")
        self.refresh_root_ui()

    def load_all_final_asset_fbx_scenes(self) -> None:
        files = [p for p in self.detected_files.get("final_asset_fbx", []) if p]
        if not files:
            single = self.paths.get("final_asset_fbx", "")
            files = [single] if single else []
        total = len(files)
        if total == 0:
            self.log("WARNING", "LoadFinal", "Aucun Final Asset FBX détecté pour chargement multiple.")
            self.log_summary("FAIL", "Final Asset FBX Load", "0/0 files referenced, no final FBX detected")
            return

        subgroup = self._ensure_review_subgroup("final_asset_fbx")
        base_namespace = self.context.get("final_asset_fbx_namespace", "Final_Asset_FBX_File")
        loaded_namespaces: List[str] = []
        aggregated_nodes: List[str] = []
        aggregated_meshes: List[str] = []
        aggregated_roots: Set[str] = set()
        failed_paths: List[str] = []
        referenced_count = 0

        for index, path in enumerate(files, start=1):
            if not os.path.isfile(path):
                failed_paths.append(path)
                self.log("FAIL", "LoadFinal", f"Final Asset FBX introuvable: {path}")
                continue

            namespace = f"{base_namespace}__{index:03d}"
            if cmds.namespace(exists=namespace):
                self._unload_namespace_references(namespace)
                try:
                    cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
                except RuntimeError:
                    pass

            before = set(cmds.ls(long=True) or [])
            try:
                cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
            except RuntimeError as exc:
                failed_paths.append(path)
                self.log("FAIL", "LoadFinal", f"Référence impossible ({self._basename_from_path(path)}): {exc}")
                continue

            after = set(cmds.ls(long=True) or [])
            new_nodes = sorted(list(after - before))
            new_meshes = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]
            top_nodes = cmds.ls(new_nodes, assemblies=True, long=True) or []
            stored_nodes: List[str] = []
            for node in top_nodes:
                if not cmds.objExists(node):
                    continue
                try:
                    cmds.parent(node, subgroup)
                    stored_nodes.append(node)
                except RuntimeError:
                    self.log("WARNING", "LoadFinal", f"Impossible de parent {node} -> {subgroup}")

            roots = self._find_root_candidates("final", namespace=namespace)
            aggregated_nodes.extend(new_nodes)
            aggregated_meshes.extend(new_meshes)
            aggregated_roots.update(roots)
            loaded_namespaces.append(namespace)
            referenced_count += 1
            self.log("INFO", "LoadFinal", f"Final Asset FBX référencé : {self._basename_from_path(path)} (ns={namespace}, meshes={len(new_meshes)})")
            self.log("INFO", "LoadFinal", f"Top nodes parentés sous {subgroup}: {len(stored_nodes)}")

        self.context["final_asset_fbx_nodes"] = sorted(set(aggregated_nodes))
        self.context["final_asset_fbx_meshes"] = sorted(set(aggregated_meshes))
        self.context["final_asset_fbx_namespaces"] = loaded_namespaces
        self.detected_roots["final_asset_fbx"] = sorted(aggregated_roots, key=lambda x: self._candidate_root_score(x), reverse=True)
        self.review_group_contents["final_asset_fbx"] = cmds.listRelatives(subgroup, children=True, fullPath=True) or []
        self._log_root_detection("final_asset_fbx", "Final Asset FBX")
        self.refresh_root_ui()

        if referenced_count == total:
            self.log_summary("INFO", "Final Asset FBX Load", f"{referenced_count} files referenced into Final_Asset_FBX_GRP")
        else:
            self.log_summary("FAIL", "Final Asset FBX Load", f"{referenced_count}/{total} files referenced, {len(failed_paths)} failed", failed_paths[:40])

    def load_everything(self) -> None:
        self.log("INFO", "Load", "Action: Load Everything")
        self.log("INFO", "Load", f"Root courant: {self.paths.get('root', '') or '-- non défini --'}")

        self._ensure_outsourcing_review_group()
        self.log("INFO", "Load", "Groupe Outsourcing_Review visible (visibility=1).")

        self.review_group_contents = {
            "high_ma": [],
            "high_fbx": [],
            "placeholder": [],
            "low_fbx": [],
            "bake_ma": [],
            "final_scene_ma": [],
            "final_asset_fbx": [],
        }

        load_plan = [
            ("high_ma", "High_Ma_File"),
            ("high_fbx", "High_FBX_File"),
            ("low_fbx", "Low_FBX_File"),
            ("bake_ma", "Bake_MA_File"),
            ("final_scene_ma", "Final_Asset_MA_File"),
        ]
        for file_key, _ in load_plan:
            self._ensure_review_subgroup(file_key)

        attempted = 0
        skipped = 0
        loaded_or_reused = 0

        for file_key, namespace in load_plan:
            path = self.paths.get(file_key, "")
            self.log(
                "INFO",
                "Load",
                f"Préparation [{file_key}] namespace={namespace} | path={path or '-- vide --'}",
            )
            if not path or not os.path.isfile(path):
                reason = "path vide/non sélectionné" if not path else "fichier introuvable"
                self.log("WARNING", "Load", f"Skip [{file_key}] : {reason}.")
                skipped += 1
                continue

            attempted += 1
            top_nodes: List[str] = []
            if cmds.namespace(exists=namespace):
                top_nodes = cmds.ls(namespace + ":*", assemblies=True, long=True) or []
                self.log(
                    "INFO",
                    "Load",
                    f"Namespace existant [{namespace}] détecté, réutilisation de {len(top_nodes)} top node(s).",
                )
            else:
                new_nodes = cmds.file(path, reference=True, namespace=namespace, returnNewNodes=True) or []
                top_nodes = cmds.ls(new_nodes, assemblies=True, long=True) or []
                self.log(
                    "INFO",
                    "Load",
                    f"Référence créée [{file_key}] : {self._basename_from_path(path)} | "
                    f"newNodes={len(new_nodes)} | topNodes={len(top_nodes)}",
                )

            stored_nodes: List[str] = []
            subgroup = self._ensure_review_subgroup(file_key)
            for node in top_nodes:
                if not cmds.objExists(node):
                    self.log("WARNING", "Load", f"Node ignoré (inexistant): {node}")
                    continue
                try:
                    cmds.parent(node, subgroup)
                    stored_nodes.append(node)
                except RuntimeError:
                    self.log("WARNING", "Load", f"Impossible de parent {node} -> {subgroup}")
                    continue
            self.review_group_contents[file_key] = stored_nodes
            loaded_or_reused += 1
            self.log(
                "INFO",
                "Load",
                f"[{file_key}] top nodes parentés sous {subgroup}: {len(stored_nodes)} | "
                f"{self._preview_list(stored_nodes, max_items=8)}",
            )
            if file_key == "high_ma":
                self._organize_high_ma_loaded_roots()

        self.load_all_final_asset_fbx_scenes()

        total_parented = sum(len(nodes) for nodes in self.review_group_contents.values())
        self.log(
            "INFO",
            "Load",
            f"Load Everything terminé | attempted={attempted} | skipped={skipped} | "
            f"loaded_or_reused={loaded_or_reused} | total_parented={total_parented}",
        )
        if attempted == 0:
            self.log(
                "WARNING",
                "Load",
                "Aucune référence chargée: vérifier le scan, la sélection des fichiers et l'existence des chemins.",
            )
        self.log_summary("INFO", "Load Everything", f"Loaded/reused {loaded_or_reused}, parented nodes {total_parented}")

    def _compare_mesh_sets(self, left_meshes: List[str], right_meshes: List[str], left_label: str, right_label: str) -> bool:
        match_data = self._build_mesh_match_pairs(left_meshes, right_meshes, left_label, right_label)
        pairs = match_data["pairs"]
        unmatched_left = match_data["unmatched_a"]
        unmatched_right = match_data["unmatched_b"]
        topo_mismatch = []
        uv_mismatch = []

        for left_mesh, right_mesh in pairs:
            left_data = self._mesh_data_signature(left_mesh)
            right_data = self._mesh_data_signature(right_mesh)
            if (left_data["v"], left_data["e"], left_data["f"]) != (right_data["v"], right_data["e"], right_data["f"]):
                topo_mismatch.append(left_mesh)
            uv_ok, _uv_details = self._compare_mesh_uv_sets(left_mesh, right_mesh, category="CompareUV")
            if not uv_ok:
                uv_mismatch.append(left_mesh)

        if not unmatched_left and not unmatched_right and not topo_mismatch and not uv_mismatch:
            self.log("INFO", "Compare", f"Résultat : OK ({left_label} et {right_label} cohérents).")
            return True

        mismatch_count = len(unmatched_left) + len(unmatched_right) + len(topo_mismatch) + len(uv_mismatch)
        self.log("WARNING", "Compare", f"Résultat : mismatch détecté ({mismatch_count} catégorie(s) en écart).")
        if unmatched_left:
            self.log("FAIL", "Compare", f"Présents dans {left_label} mais absents de {right_label}: {len(unmatched_left)}", unmatched_left[:150])
            self.log("WARNING", "Compare", "Mesh presence mismatch likely caused by hierarchy/key mismatch.")
        if unmatched_right:
            self.log("FAIL", "Compare", f"Présents dans {right_label} mais absents de {left_label}: {len(unmatched_right)}", unmatched_right[:150])
            self.log("WARNING", "Compare", "Unable to match meshes despite similar leaf names.")
        if topo_mismatch:
            self.log("FAIL", "Compare", f"Topologie différente: {len(topo_mismatch)}", topo_mismatch[:150])
        if uv_mismatch:
            self.log("FAIL", "Compare", f"UV différentes: {len(uv_mismatch)}", uv_mismatch[:150])
        return False

    def _is_global_compare_enabled(self, toggle_key: str, default: bool = False) -> bool:
        return self._query_boolean_control_value(toggle_key, default=default)

    def _run_pair_compare(
        self,
        *,
        category: str,
        pair_category: str,
        uv_category: str,
        check_state_key: str,
        check_label: str,
        left_root: str,
        right_root: str,
        left_label: str,
        right_label: str,
        left_meshes: List[str],
        right_meshes: List[str],
    ) -> None:
        match_data = self._build_mesh_match_pairs(left_meshes, right_meshes, left_label, right_label)
        matched_pairs: List[Tuple[str, str]] = match_data["pairs"]
        unmatched_left: List[str] = match_data["unmatched_a"]
        unmatched_right: List[str] = match_data["unmatched_b"]
        pair_rows: List[Tuple[Optional[Dict[str, object]], Optional[Dict[str, object]]]] = []
        for left_mesh, right_mesh in matched_pairs:
            pair_rows.append((self._mesh_data_signature(left_mesh, root=left_root), self._mesh_data_signature(right_mesh, root=right_root)))
        for left_mesh in unmatched_left:
            pair_rows.append((self._mesh_data_signature(left_mesh, root=left_root), None))
        for right_mesh in unmatched_right:
            pair_rows.append((None, self._mesh_data_signature(right_mesh, root=right_root)))

        self.log("INFO", category, "Compare mode = Pair")
        self.log("INFO", category, f"Paires comparées : {len(pair_rows)}")
        pair_fail_count = 0
        presence_all = True
        topology_all = True
        uv_all = True
        bbox_all = True
        for left_data, right_data in pair_rows:
            left_name = left_data["path"] if left_data else f"UNMATCHED {left_label} mesh"
            right_name = right_data["path"] if right_data else f"UNMATCHED {right_label} mesh"
            left_key = self._normalized_mesh_leaf_key(left_data["path"]) if left_data else "n/a"
            right_key = self._normalized_mesh_leaf_key(right_data["path"]) if right_data else "n/a"
            presence_ok = bool(left_data and right_data)
            topo_ok = bool(left_data and right_data and (left_data["v"], left_data["e"], left_data["f"]) == (right_data["v"], right_data["e"], right_data["f"]))
            uv_ok = False
            if left_data and right_data:
                uv_ok, _uv_details = self._compare_mesh_uv_sets(left_data["path"], right_data["path"], category=uv_category)
            bbox_dims_left = (0.0, 0.0, 0.0)
            bbox_dims_right = (0.0, 0.0, 0.0)
            bbox_delta = (0.0, 0.0, 0.0)
            bbox_center_delta = (0.0, 0.0, 0.0)
            bbox_ok = False
            if presence_ok:
                bbox_dims_left, bbox_center_left = self._mesh_bbox_dims_and_center_world(left_data["path"])
                bbox_dims_right, bbox_center_right = self._mesh_bbox_dims_and_center_world(right_data["path"])
                bbox_delta = tuple(abs(bbox_dims_left[i] - bbox_dims_right[i]) for i in range(3))
                bbox_center_delta = tuple(abs(bbox_center_left[i] - bbox_center_right[i]) for i in range(3))
                bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
            pair_ok = presence_ok and topo_ok and uv_ok and bbox_ok
            if not pair_ok:
                pair_fail_count += 1
            presence_all = presence_all and presence_ok
            topology_all = topology_all and topo_ok
            uv_all = uv_all and uv_ok
            bbox_all = bbox_all and bbox_ok

            self.log("INFO", pair_category, f"{left_label} Mesh = {left_name}")
            self.log("INFO", pair_category, f"{right_label} Mesh = {right_name}")
            self.log("INFO", pair_category, f"Matching key A = {left_key}")
            self.log("INFO", pair_category, f"Matching key B = {right_key}")
            self.log("INFO" if presence_ok else "FAIL", pair_category, f"Presence match = {'OK' if presence_ok else 'FAIL'}")
            self.log("INFO" if topo_ok else "FAIL", pair_category, f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", pair_category, f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", pair_category, f"Bounding Box A = {self._fmt_vec(bbox_dims_left, precision=2)}")
            self.log("INFO", pair_category, f"Bounding Box B = {self._fmt_vec(bbox_dims_right, precision=2)}")
            self.log("INFO", pair_category, f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", pair_category, f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", pair_category, f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", pair_category, f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        sub_results = {"presence": presence_all, "topology": topology_all, "uv": uv_all, "bounding_box": bbox_all}
        if any(sub_key == "pivot" for sub_key, _ in self.subcheck_definitions.get(check_state_key, [])):
            left_pivot = tuple(cmds.xform(left_root, q=True, ws=True, rotatePivot=True) or [0.0, 0.0, 0.0])
            right_pivot = tuple(cmds.xform(right_root, q=True, ws=True, rotatePivot=True) or [0.0, 0.0, 0.0])
            sub_results["pivot"] = all(abs(left_pivot[i] - right_pivot[i]) <= 1e-4 for i in range(3))
        self._set_subcheck_results(check_state_key, sub_results)
        self.log("INFO" if ok else "FAIL", category, f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result(check_state_key, "INFO", check_label, "pair compare: topology, UVs and bbox match")
        else:
            self.log_check_result(check_state_key, "FAIL", check_label, f"{pair_fail_count}/{len(pair_rows)} mesh pairs mismatched")

    def _run_global_compare(
        self,
        *,
        category: str,
        uv_category: str,
        check_state_key: str,
        check_label: str,
        left_root: str,
        right_root: str,
        left_label: str,
        right_label: str,
    ) -> None:
        left_data = self._root_aggregate_signature(left_root)
        right_data = self._root_aggregate_signature(right_root)
        self.log("INFO", category, "Compare mode = Global")
        self.log("INFO", category, f"Meshes analysés {left_label}/{right_label} : {left_data['mesh_count']} / {right_data['mesh_count']}")

        presence_ok = bool(left_data["mesh_count"] > 0 and right_data["mesh_count"] > 0)
        topo_ok = (left_data["v"], left_data["e"], left_data["f"]) == (right_data["v"], right_data["e"], right_data["f"])
        uv_ok, _uv_details = self._compare_uv_set_signatures(left_data["uv_sets"], right_data["uv_sets"], category=uv_category)
        bbox_delta = tuple(abs(left_data["bbox_dims"][i] - right_data["bbox_dims"][i]) for i in range(3))
        bbox_center_delta = tuple(abs(left_data["bbox_center"][i] - right_data["bbox_center"][i]) for i in range(3))
        bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
        pivot_delta = tuple(abs(left_data["pivot_world"][i] - right_data["pivot_world"][i]) for i in range(3))
        pivot_ok = all(v <= 1e-4 for v in pivot_delta)
        ok = presence_ok and topo_ok and uv_ok and bbox_ok and pivot_ok
        self._set_subcheck_results(
            check_state_key,
            {"presence": presence_ok, "topology": topo_ok, "uv": uv_ok, "bounding_box": bbox_ok, "pivot": pivot_ok},
        )

        self.log("INFO" if presence_ok else "FAIL", category, f"Presence match = {'OK' if presence_ok else 'FAIL'}")
        self.log("INFO" if topo_ok else "FAIL", category, "Topology match (totaux root) = {}".format("OK" if topo_ok else "FAIL"))
        self.log("INFO" if uv_ok else "FAIL", category, "UV match (totaux root) = {}".format("OK" if uv_ok else "FAIL"))
        self.log("INFO", category, f"Bounding Box {left_label} (root) = {self._fmt_vec(left_data['bbox_dims'], precision=2)}")
        self.log("INFO", category, f"Bounding Box {right_label} (root) = {self._fmt_vec(right_data['bbox_dims'], precision=2)}")
        self.log("INFO", category, f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
        self.log("INFO", category, f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
        self.log("INFO" if bbox_ok else "FAIL", category, f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
        self.log("INFO", category, f"Pivot {left_label} (root) = {self._fmt_vec(left_data['pivot_world'], precision=4)}")
        self.log("INFO", category, f"Pivot {right_label} (root) = {self._fmt_vec(right_data['pivot_world'], precision=4)}")
        self.log("INFO", category, f"Pivot delta = {self._fmt_vec(pivot_delta, precision=4)}")
        self.log("INFO" if pivot_ok else "FAIL", category, f"Pivot match = {'OK' if pivot_ok else 'FAIL'}")
        self.log("INFO" if ok else "FAIL", category, f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result(check_state_key, "INFO", check_label, "global compare: topology, UVs, bbox and pivot match")
        else:
            mismatch_flags = int(not presence_ok) + int(not topo_ok) + int(not uv_ok) + int(not bbox_ok) + int(not pivot_ok)
            self.log_check_result(check_state_key, "FAIL", check_label, f"{mismatch_flags} global mismatch type(s) detected")

    def compare_ma_vs_fbx(self) -> None:
        self._log_step_header(7, "Compare High.ma vs High.fbx", category="Compare")
        use_global_mode = self._is_global_compare_enabled("compare_ma_fbx_global_mode", default=False)
        self.log("INFO", "Compare", f"Source A : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Compare", f"Source B : {self._basename_from_path(self.paths.get('high_fbx', ''))}")
        ma_root = self.get_manual_selected_root("compare_ma_root_menu")
        fbx_root = self.get_manual_selected_root("compare_fbx_root_menu")
        if not ma_root or not fbx_root:
            self.log("FAIL", "Compare", "Sélection manuelle requise: choisir High.ma Root et High.fbx Root.")
            self.log_check_result("ma_fbx_compared", "FAIL", "Compare High vs FBX", "manual root selection missing")
            return
        ma_meshes = self._collect_mesh_transforms(ma_root)
        fbx_meshes = self._collect_mesh_transforms(fbx_root)
        self.log("INFO", "Compare", f"Root MA sélectionné : {ma_root}", [ma_root])
        self.log("INFO", "Compare", f"Root FBX sélectionné : {fbx_root}", [fbx_root])
        self.log("INFO", "Compare", f"Meshes analysés MA/FBX : {len(ma_meshes)}/{len(fbx_meshes)}")

        if not ma_meshes or not fbx_meshes:
            self.log("FAIL", "Compare", "Résultat : compare impossible (au moins une source sans mesh).")
            self.log_check_result("ma_fbx_compared", "FAIL", "Compare High vs FBX", "compare aborted: one root has no meshes")
            return
        if use_global_mode:
            self._run_global_compare(
                category="Compare",
                uv_category="CompareGlobalUV",
                check_state_key="ma_fbx_compared",
                check_label="Compare High vs FBX",
                left_root=ma_root,
                right_root=fbx_root,
                left_label="MA",
                right_label="FBX",
            )
            return

        self.log("INFO", "Compare", "Compare mode = Pair")
        match_data = self._build_mesh_match_pairs(ma_meshes, fbx_meshes, "High.ma", "High.fbx")
        matched_pairs: List[Tuple[str, str]] = match_data["pairs"]
        unmatched_ma: List[str] = match_data["unmatched_a"]
        unmatched_fbx: List[str] = match_data["unmatched_b"]
        self.log("INFO", "Compare", f"Paires comparées : {len(matched_pairs) + len(unmatched_ma) + len(unmatched_fbx)}")

        pair_rows: List[Tuple[Optional[Dict[str, object]], Optional[Dict[str, object]]]] = []
        for ma_mesh, fbx_mesh in matched_pairs:
            pair_rows.append((self._mesh_data_signature(ma_mesh, root=ma_root), self._mesh_data_signature(fbx_mesh, root=fbx_root)))
        for ma_mesh in unmatched_ma:
            pair_rows.append((self._mesh_data_signature(ma_mesh, root=ma_root), None))
        for fbx_mesh in unmatched_fbx:
            pair_rows.append((None, self._mesh_data_signature(fbx_mesh, root=fbx_root)))

        pair_fail_count = 0
        presence_all = True
        topology_all = True
        uv_all = True
        bbox_all = True
        for ma_data, fbx_data in pair_rows:
            ma_name = ma_data["path"] if ma_data else "UNMATCHED High.ma mesh"
            fbx_name = fbx_data["path"] if fbx_data else "UNMATCHED High.fbx mesh"
            ma_key = self._normalized_mesh_leaf_key(ma_data["path"]) if ma_data else "n/a"
            fbx_key = self._normalized_mesh_leaf_key(fbx_data["path"]) if fbx_data else "n/a"

            presence_ok = bool(ma_data and fbx_data)
            topo_ok = bool(
                ma_data and fbx_data and
                (ma_data["v"], ma_data["e"], ma_data["f"]) == (fbx_data["v"], fbx_data["e"], fbx_data["f"])
            )
            uv_ok = False
            if ma_data and fbx_data:
                uv_ok, _uv_details = self._compare_mesh_uv_sets(ma_data["path"], fbx_data["path"], category="ComparePairUV")
            bbox_dims_ma = (0.0, 0.0, 0.0)
            bbox_dims_fbx = (0.0, 0.0, 0.0)
            bbox_delta = (0.0, 0.0, 0.0)
            bbox_center_delta = (0.0, 0.0, 0.0)
            bbox_ok = False
            if presence_ok:
                bbox_dims_ma, bbox_center_ma = self._mesh_bbox_dims_and_center_world(ma_data["path"])
                bbox_dims_fbx, bbox_center_fbx = self._mesh_bbox_dims_and_center_world(fbx_data["path"])
                bbox_delta = tuple(abs(bbox_dims_ma[i] - bbox_dims_fbx[i]) for i in range(3))
                bbox_center_delta = tuple(abs(bbox_center_ma[i] - bbox_center_fbx[i]) for i in range(3))
                bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
            pair_ok = presence_ok and topo_ok and uv_ok and bbox_ok
            if not pair_ok:
                pair_fail_count += 1
            presence_all = presence_all and presence_ok
            topology_all = topology_all and topo_ok
            uv_all = uv_all and uv_ok
            bbox_all = bbox_all and bbox_ok

            self.log("INFO", "ComparePair", f"MA Mesh = {ma_name}")
            self.log("INFO", "ComparePair", f"FBX Mesh = {fbx_name}")
            self.log("INFO", "ComparePair", f"Matching key A = {ma_key}")
            self.log("INFO", "ComparePair", f"Matching key B = {fbx_key}")
            self.log("INFO" if presence_ok else "FAIL", "ComparePair", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
            if not presence_ok:
                self.log("WARNING", "ComparePair", "Mesh presence mismatch likely caused by hierarchy/key mismatch.")
            self.log("INFO" if topo_ok else "FAIL", "ComparePair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "ComparePair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "ComparePair", f"Bounding Box MA = {self._fmt_vec(bbox_dims_ma, precision=2)}")
            self.log("INFO", "ComparePair", f"Bounding Box FBX = {self._fmt_vec(bbox_dims_fbx, precision=2)}")
            self.log("INFO", "ComparePair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "ComparePair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "ComparePair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "ComparePair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        ma_pivot = tuple(cmds.xform(ma_root, q=True, ws=True, rotatePivot=True) or [0.0, 0.0, 0.0])
        fbx_pivot = tuple(cmds.xform(fbx_root, q=True, ws=True, rotatePivot=True) or [0.0, 0.0, 0.0])
        self._set_subcheck_results("ma_fbx_compared", {"presence": presence_all, "topology": topology_all, "uv": uv_all, "bounding_box": bbox_all, "pivot": all(abs(ma_pivot[i] - fbx_pivot[i]) <= 1e-4 for i in range(3))})
        self.log("INFO" if ok else "FAIL", "Compare", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("ma_fbx_compared", "INFO", "Compare High vs FBX", "aggregated topology, UVs and bbox match")
        else:
            self.log_check_result("ma_fbx_compared", "FAIL", "Compare High vs FBX", f"{pair_fail_count}/{len(pair_rows)} mesh pairs mismatched")

    def _unload_namespace_references(self, namespace: str) -> bool:
        if not cmds.namespace(exists=namespace):
            return True
        namespace_nodes = cmds.ls(namespace + ":*", long=True) or []
        ref_nodes: Set[str] = set()
        for node in namespace_nodes:
            try:
                ref_nodes.add(cmds.referenceQuery(node, referenceNode=True))
            except RuntimeError:
                continue
        if not ref_nodes:
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
                return True
            except RuntimeError:
                return False

        ok = True
        for ref_node in sorted(ref_nodes):
            try:
                cmds.file(unloadReference=ref_node)
            except RuntimeError as exc:
                ok = False
                self.log("WARNING", "Scene", f"Impossible de décharger la référence '{ref_node}': {exc}")
        return ok

    def compare_ma_vs_bake_high(self) -> None:
        self._log_step_header(8, "Compare High.ma vs Bake High", category="CompareBake")
        use_global_mode = self._is_global_compare_enabled("compare_ma_bake_global_mode", default=False)
        ma_root = self.get_manual_selected_root("compare_bake_ma_root_menu")
        bake_root = self.get_manual_selected_root("compare_bake_high_root_menu")
        if not ma_root or not bake_root:
            self.log("FAIL", "CompareBake", "Sélection manuelle requise: choisir High.ma Root et Bake High Root.")
            self.log_check_result("ma_bake_compared", "FAIL", "Compare High vs Bake", "manual root selection missing")
            return
        ma_meshes = self._collect_mesh_transforms(ma_root)
        bake_meshes = self._collect_mesh_transforms(bake_root)

        self.log("INFO", "CompareBake", f"Source A : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "CompareBake", f"Source B : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        self.log("INFO", "CompareBake", f"Root High.ma sélectionné : {ma_root}", [ma_root])
        self.log("INFO", "CompareBake", f"Root Bake sélectionné : {bake_root}", [bake_root])
        self.log("INFO", "CompareBake", f"Meshes analysés High.ma / Bake High : {len(ma_meshes)} / {len(bake_meshes)}")
        if not ma_meshes or not bake_meshes:
            self.log("FAIL", "CompareBake", "Compare impossible : High.ma ou Bake High non chargé.")
            self.log_check_result("ma_bake_compared", "FAIL", "Compare High vs Bake", "compare aborted: one root has no meshes")
            return
        if use_global_mode:
            self._run_global_compare(
                category="CompareBake",
                uv_category="CompareBakeGlobalUV",
                check_state_key="ma_bake_compared",
                check_label="Compare High vs Bake",
                left_root=ma_root,
                right_root=bake_root,
                left_label="High.ma",
                right_label="Bake",
            )
            return
        self.log("INFO", "CompareBake", "Compare mode = Pair")
        match_data = self._build_mesh_match_pairs(ma_meshes, bake_meshes, "High.ma", "Bake High")
        matched_pairs: List[Tuple[str, str]] = match_data["pairs"]
        unmatched_ma: List[str] = match_data["unmatched_a"]
        unmatched_bake: List[str] = match_data["unmatched_b"]

        pairings: List[Tuple[Optional[Dict[str, object]], Optional[Dict[str, object]]]] = []
        for ma_mesh, bake_mesh in matched_pairs:
            pairings.append((self._mesh_data_signature(ma_mesh, root=ma_root), self._mesh_data_signature(bake_mesh, root=bake_root)))
        for ma_mesh in unmatched_ma:
            pairings.append((self._mesh_data_signature(ma_mesh, root=ma_root), None))
        for bake_mesh in unmatched_bake:
            pairings.append((None, self._mesh_data_signature(bake_mesh, root=bake_root)))

        self.log("INFO", "CompareBake", f"Paires comparées : {len(pairings)}")

        pair_fail_count = 0
        presence_all = True
        topology_all = True
        uv_all = True
        bbox_all = True
        for ma_data, bake_data in pairings:
            ma_name = ma_data["path"] if ma_data else "UNMATCHED High.ma mesh"
            bake_name = bake_data["path"] if bake_data else "UNMATCHED Bake High mesh"
            high_key = self._normalized_mesh_leaf_key(ma_data["path"]) if ma_data else "n/a"
            bake_key = self._normalized_mesh_leaf_key(bake_data["path"]) if bake_data else "n/a"

            presence_ok = bool(ma_data and bake_data)
            topo_ok = bool(
                ma_data and bake_data and
                (ma_data["v"], ma_data["e"], ma_data["f"]) == (bake_data["v"], bake_data["e"], bake_data["f"])
            )
            uv_ok = False
            if ma_data and bake_data:
                uv_ok, _uv_details = self._compare_mesh_uv_sets(ma_data["path"], bake_data["path"], category="CompareBakePairUV")
            bbox_dims_ma = (0.0, 0.0, 0.0)
            bbox_dims_bake = (0.0, 0.0, 0.0)
            bbox_delta = (0.0, 0.0, 0.0)
            bbox_center_delta = (0.0, 0.0, 0.0)
            bbox_ok = False
            if presence_ok:
                bbox_dims_ma, bbox_center_ma = self._mesh_bbox_dims_and_center_world(ma_data["path"])
                bbox_dims_bake, bbox_center_bake = self._mesh_bbox_dims_and_center_world(bake_data["path"])
                bbox_delta = tuple(abs(bbox_dims_ma[i] - bbox_dims_bake[i]) for i in range(3))
                bbox_center_delta = tuple(abs(bbox_center_ma[i] - bbox_center_bake[i]) for i in range(3))
                bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
            pair_ok = presence_ok and topo_ok and uv_ok and bbox_ok
            if not pair_ok:
                pair_fail_count += 1
            presence_all = presence_all and presence_ok
            topology_all = topology_all and topo_ok
            uv_all = uv_all and uv_ok
            bbox_all = bbox_all and bbox_ok

            self.log("INFO", "CompareBakePair", f"High.ma Mesh = {ma_name}")
            self.log("INFO", "CompareBakePair", f"Bake High Mesh = {bake_name}")
            self.log("INFO", "CompareBakePair", f"Matching key High = {high_key}")
            self.log("INFO", "CompareBakePair", f"Matching key Bake = {bake_key}")
            self.log("INFO" if presence_ok else "FAIL", "CompareBakePair", f"Mesh presence match = {'OK' if presence_ok else 'FAIL'}")
            if not presence_ok:
                self.log("WARNING", "CompareBakePair", "Mesh presence mismatch likely caused by hierarchy/key mismatch.")
            self.log("INFO" if topo_ok else "FAIL", "CompareBakePair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "CompareBakePair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "CompareBakePair", f"Bounding Box High.ma = {self._fmt_vec(bbox_dims_ma, precision=2)}")
            self.log("INFO", "CompareBakePair", f"Bounding Box Bake = {self._fmt_vec(bbox_dims_bake, precision=2)}")
            self.log("INFO", "CompareBakePair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "CompareBakePair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "CompareBakePair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "CompareBakePair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        ma_pivot = tuple(cmds.xform(ma_root, q=True, ws=True, rotatePivot=True) or [0.0, 0.0, 0.0])
        bake_pivot = tuple(cmds.xform(bake_root, q=True, ws=True, rotatePivot=True) or [0.0, 0.0, 0.0])
        self._set_subcheck_results("ma_bake_compared", {"presence": presence_all, "topology": topology_all, "uv": uv_all, "bounding_box": bbox_all, "pivot": all(abs(ma_pivot[i] - bake_pivot[i]) <= 1e-4 for i in range(3))})
        self.log("INFO" if ok else "FAIL", "CompareBake", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("ma_bake_compared", "INFO", "Compare High vs Bake", "aggregated topology, UVs and bbox match")
        else:
            self.log_check_result("ma_bake_compared", "FAIL", "Compare High vs Bake", f"{pair_fail_count}/{len(pairings)} mesh pairs mismatched")

    def check_bake_scene_structure(self) -> None:
        self._log_step_header(1, "Bake Scene Structure", category="BakeStructure")
        namespace = self.context.get("bake_ma_namespace", "")
        high_root = self.get_manual_selected_root("bake_structure_high_root_menu")
        low_root = self.get_manual_selected_root("bake_structure_low_root_menu")

        self.log("INFO", "BakeStructure", f"Fichier analysé : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        self.log("INFO", "BakeStructure", f"Namespace attendu : {namespace or 'N/A'}")
        self.log("INFO", "BakeStructure", f"Bake High détectés : {len(self.detected_roots.get('bake_high', []))}")
        self.log("INFO", "BakeStructure", f"Bake Low détectés : {len(self.detected_roots.get('bake_low', []))}")

        if not high_root:
            candidates = [r for r in self.detected_roots.get("bake_high", []) if cmds.objExists(r)]
            high_root = candidates[0] if candidates else None
        if not low_root:
            candidates = [r for r in self.detected_roots.get("bake_low", []) if cmds.objExists(r)]
            low_root = candidates[0] if candidates else None

        if not high_root or not low_root:
            self.log("FAIL", "BakeStructure", "Bake High et/ou Bake Low introuvable(s).")
            self.log_check_result("bake_structure_checked", "FAIL", "Bake Structure", "missing Bake High or Bake Low root")
            return

        self.log("INFO", "BakeStructure", f"Root Bake High : {high_root}", [high_root])
        self.log("INFO", "BakeStructure", f"Root Bake Low : {low_root}", [low_root])
        high_meshes = self._collect_mesh_transforms(high_root)
        low_meshes = self._collect_mesh_transforms(low_root)
        self.log("INFO", "BakeStructure", f"Meshes High/Low : {len(high_meshes)} / {len(low_meshes)}")

        high_ok = bool(high_meshes)
        low_ok = bool(low_meshes)
        namespace_ok = True
        if namespace:
            namespace_ok = (
                f"|{namespace}:" in high_root and
                f"|{namespace}:" in low_root
            )

        overlap_objects = sorted(set(high_meshes) & set(low_meshes))
        overlap_ok = len(overlap_objects) == 0

        mixed_low_in_high = [m for m in high_meshes if self._strip_namespaces_from_name(self._short_name(m)).lower().endswith("_low")]
        mixed_high_in_low = [m for m in low_meshes if self._strip_namespaces_from_name(self._short_name(m)).lower().endswith("_high")]
        naming_split_ok = not mixed_low_in_high and not mixed_high_in_low

        self.log("INFO" if high_ok else "FAIL", "BakeStructure", f"Bake High présent = {'OK' if high_ok else 'FAIL'}")
        self.log("INFO" if low_ok else "FAIL", "BakeStructure", f"Bake Low présent = {'OK' if low_ok else 'FAIL'}")
        self.log("INFO" if namespace_ok else "FAIL", "BakeStructure", f"Namespace bake cohérent = {'OK' if namespace_ok else 'FAIL'}")
        self.log("INFO" if overlap_ok else "FAIL", "BakeStructure", f"High/Low séparés (pas de meshes partagés) = {'OK' if overlap_ok else 'FAIL'}", overlap_objects[:120])
        self.log(
            "INFO" if naming_split_ok else "FAIL",
            "BakeStructure",
            f"Pas de mélange _high/_low = {'OK' if naming_split_ok else 'FAIL'}",
            (mixed_low_in_high + mixed_high_in_low)[:120],
        )

        ok = high_ok and low_ok and namespace_ok and overlap_ok and naming_split_ok
        self._set_subcheck_results(
            "bake_structure_checked",
            {
                "bake_high_present": high_ok,
                "bake_low_present": low_ok,
                "structure_valid": namespace_ok and overlap_ok and naming_split_ok,
            },
        )
        self.log("INFO" if ok else "FAIL", "BakeStructure", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("bake_structure_checked", "INFO", "Bake Structure", "high/low roots valid, separated and namespace-consistent")
        else:
            self.log_check_result(
                "bake_structure_checked",
                "FAIL",
                "Bake Structure",
                f"issues: high={len(high_meshes)}, low={len(low_meshes)}, overlap={len(overlap_objects)}, mixed={len(mixed_low_in_high) + len(mixed_high_in_low)}",
            )

    def _bake_pair_key(self, mesh: str, root: str, expected_suffix: str) -> Tuple[str, bool]:
        del root
        suffix = expected_suffix.lower()
        short_name = self._short_name(mesh)
        raw_leaf = self._strip_namespaces_from_name(short_name).lower().strip()
        raw_leaf = re.sub(r"[\s_\-]+", "_", raw_leaf)
        has_suffix = raw_leaf.endswith(suffix)

        key = self._normalized_mesh_leaf_key(mesh)
        return key.strip("_"), has_suffix

    def check_bake_pairing(self) -> None:
        self._log_step_header(2, "Naming & Pairing", category="BakePairing")
        self.log("INFO", "BakePairing", "Entrée dans check_bake_pairing().")
        high_root = self.get_manual_selected_root("bake_pairing_high_root_menu")
        low_root = self.get_manual_selected_root("bake_pairing_low_root_menu")
        bbox_scale = 1.05
        if "bake_pairing_bbox_scale" in self.ui:
            bbox_scale_control = self.ui["bake_pairing_bbox_scale"]
            if QT_AVAILABLE and QtWidgets is not None and isinstance(bbox_scale_control, QtWidgets.QDoubleSpinBox):
                bbox_scale = max(1.0, float(bbox_scale_control.value()))
            else:
                bbox_scale = max(1.0, float(cmds.floatField(bbox_scale_control, q=True, value=True)))
        self.log("INFO", "BakePairing", f"BBox scale utilisée : {bbox_scale:.3f}")
        self.log("INFO", "BakePairing", f"Root Bake High (sélection) : {high_root or '<None>'}")
        self.log("INFO", "BakePairing", f"Root Bake Low (sélection) : {low_root or '<None>'}")
        if not high_root or not low_root:
            self.log("FAIL", "BakePairing", "Sélection manuelle requise: Select Bake High Root et Select Bake Low Root.")
            self.log_check_result("bake_pairing_checked", "FAIL", "Bake Pairing", "manual root selection missing")
            return

        high_meshes = self._collect_mesh_transforms(high_root)
        low_meshes = self._collect_mesh_transforms(low_root)
        self.log("INFO", "BakePairing", f"Fichier analysé : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        self.log("INFO", "BakePairing", f"Root Bake High : {high_root}", [high_root])
        self.log("INFO", "BakePairing", f"Root Bake Low : {low_root}", [low_root])
        self.log("INFO", "BakePairing", f"Meshes High/Low : {len(high_meshes)} / {len(low_meshes)}")
        if not high_meshes or not low_meshes:
            self.log("FAIL", "BakePairing", "Pairing impossible: Bake High ou Bake Low vide.")
            self.log_check_result("bake_pairing_checked", "FAIL", "Bake Pairing", "pairing aborted: one root has no meshes")
            return

        high_by_key: Dict[str, List[str]] = {}
        low_by_key: Dict[str, List[str]] = {}
        invalid_high_suffix: List[str] = []
        invalid_low_suffix: List[str] = []
        for mesh in high_meshes:
            key, has_suffix = self._bake_pair_key(mesh, high_root, "_high")
            high_by_key.setdefault(key, []).append(mesh)
            if not has_suffix:
                invalid_high_suffix.append(mesh)
        for mesh in low_meshes:
            key, has_suffix = self._bake_pair_key(mesh, low_root, "_low")
            low_by_key.setdefault(key, []).append(mesh)
            if not has_suffix:
                invalid_low_suffix.append(mesh)

        all_keys = sorted(set(high_by_key.keys()) | set(low_by_key.keys()))
        orphan_high_keys = [k for k in all_keys if k in high_by_key and k not in low_by_key]
        orphan_low_keys = [k for k in all_keys if k in low_by_key and k not in high_by_key]
        duplicate_high = {k: v for k, v in high_by_key.items() if len(v) > 1}
        duplicate_low = {k: v for k, v in low_by_key.items() if len(v) > 1}
        orphan_high_meshes = sum([high_by_key[k] for k in orphan_high_keys], [])
        orphan_low_meshes = sum([low_by_key[k] for k in orphan_low_keys], [])
        bbox_pivot_mismatch_keys: List[str] = []
        bbox_pivot_mismatch_meshes: List[str] = []

        shared_unique_keys = [
            k for k in all_keys
            if k in high_by_key and k in low_by_key and len(high_by_key[k]) == 1 and len(low_by_key[k]) == 1
        ]
        bbox_pivot_pass_count = 0
        for key in shared_unique_keys:
            high_mesh = high_by_key[key][0]
            low_mesh = low_by_key[key][0]
            bbox_dims_high, bbox_center_high = self._mesh_bbox_dims_and_center_world(high_mesh)
            bbox_dims_low, bbox_center_low = self._mesh_bbox_dims_and_center_world(low_mesh)
            bbox_delta = tuple(abs(bbox_dims_high[i] - bbox_dims_low[i]) for i in range(3))
            bbox_center_delta = tuple(abs(bbox_center_high[i] - bbox_center_low[i]) for i in range(3))
            max_bbox_dim = max(max(bbox_dims_high), max(bbox_dims_low), 1e-6)
            bbox_tolerance = max(1e-4, max_bbox_dim * (bbox_scale - 1.0))
            bbox_ok = all(v <= bbox_tolerance for v in bbox_delta) and all(v <= bbox_tolerance for v in bbox_center_delta)

            pivot_high = tuple(cmds.xform(high_mesh, query=True, worldSpace=True, rotatePivot=True) or [0.0, 0.0, 0.0])
            pivot_low = tuple(cmds.xform(low_mesh, query=True, worldSpace=True, rotatePivot=True) or [0.0, 0.0, 0.0])
            pivot_delta = tuple(abs(pivot_high[i] - pivot_low[i]) for i in range(3))
            pivot_ok = all(v <= 1e-4 for v in pivot_delta)

            self.log(
                "INFO" if (bbox_ok and pivot_ok) else "FAIL",
                "BakePairing",
                f"Pair '{key}' bbox/pivot test = {'OK' if (bbox_ok and pivot_ok) else 'FAIL'} (bbox={'OK' if bbox_ok else 'FAIL'}, pivot={'OK' if pivot_ok else 'FAIL'})",
                [high_mesh, low_mesh],
            )

            if not (bbox_ok and pivot_ok):
                bbox_pivot_mismatch_keys.append(key)
                bbox_pivot_mismatch_meshes.extend([high_mesh, low_mesh])
                self.log("FAIL", "BakePairing", f"Pair '{key}' bbox/pivot mismatch", [high_mesh, low_mesh])
                self.log("INFO", "BakePairing", f"  BBox High/Low = {self._fmt_vec(bbox_dims_high, precision=2)} / {self._fmt_vec(bbox_dims_low, precision=2)}")
                self.log(
                    "INFO",
                    "BakePairing",
                    f"  BBox delta dims/center = {self._fmt_vec(bbox_delta, precision=4)} / {self._fmt_vec(bbox_center_delta, precision=4)} (tol={bbox_tolerance:.4f}, scale={bbox_scale:.3f})",
                )
                self.log("INFO", "BakePairing", f"  Pivot delta = {self._fmt_vec(pivot_delta, precision=4)}")
            else:
                bbox_pivot_pass_count += 1

        self.log("INFO", "BakePairing", f"Paires détectées : {len(all_keys)}")
        self.log("INFO" if not invalid_high_suffix else "FAIL", "BakePairing", f"Naming _high cohérent = {'OK' if not invalid_high_suffix else 'FAIL'}", invalid_high_suffix[:120])
        self.log("INFO" if not invalid_low_suffix else "FAIL", "BakePairing", f"Naming _low cohérent = {'OK' if not invalid_low_suffix else 'FAIL'}", invalid_low_suffix[:120])
        self.log("INFO" if not orphan_high_keys else "FAIL", "BakePairing", f"Orphelins HIGH = {len(orphan_high_keys)}", orphan_high_meshes[:120])
        if orphan_high_keys:
            orphan_high_preview = ", ".join(orphan_high_keys[:20])
            self.log("FAIL", "BakePairing", f"Clés HIGH sans LOW correspondant: {orphan_high_preview}", orphan_high_meshes[:120])
        self.log("INFO" if not orphan_low_keys else "FAIL", "BakePairing", f"Orphelins LOW = {len(orphan_low_keys)}", orphan_low_meshes[:120])
        if orphan_low_keys:
            orphan_low_preview = ", ".join(orphan_low_keys[:20])
            self.log("FAIL", "BakePairing", f"Clés LOW sans HIGH correspondant: {orphan_low_preview}", orphan_low_meshes[:120])
        self.log("INFO" if not duplicate_high else "FAIL", "BakePairing", f"Doublons HIGH = {len(duplicate_high)}")
        if duplicate_high:
            for key, meshes_for_key in sorted(duplicate_high.items()):
                self.log("FAIL", "BakePairing", f"Doublon HIGH sur '{key}' ({len(meshes_for_key)} meshes)", meshes_for_key[:120])
        self.log("INFO" if not duplicate_low else "FAIL", "BakePairing", f"Doublons LOW = {len(duplicate_low)}")
        if duplicate_low:
            for key, meshes_for_key in sorted(duplicate_low.items()):
                self.log("FAIL", "BakePairing", f"Doublon LOW sur '{key}' ({len(meshes_for_key)} meshes)", meshes_for_key[:120])
        self.log("INFO", "BakePairing", f"Paires bbox/pivot testées = {len(shared_unique_keys)}")
        self.log("INFO", "BakePairing", f"Paires bbox/pivot conformes = {bbox_pivot_pass_count}")
        self.log("INFO" if not bbox_pivot_mismatch_keys else "FAIL", "BakePairing", f"Paires bbox/pivot non conformes = {len(bbox_pivot_mismatch_keys)}", bbox_pivot_mismatch_meshes[:120])
        self.log("INFO", "BakePairing", f"Résumé pairing avec bbox scale {bbox_scale:.3f} : {bbox_pivot_pass_count}/{len(shared_unique_keys)} paires conformes")

        ok = not any([
            invalid_high_suffix,
            invalid_low_suffix,
            orphan_high_keys,
            orphan_low_keys,
            duplicate_high,
            duplicate_low,
            bbox_pivot_mismatch_keys,
        ])
        self._set_subcheck_results(
            "bake_pairing_checked",
            {
                "naming": not invalid_high_suffix and not invalid_low_suffix,
                "pairing": not orphan_high_keys and not orphan_low_keys and not duplicate_high and not duplicate_low,
                "bounding_box": not bbox_pivot_mismatch_keys,
            },
        )
        self.log("INFO" if ok else "FAIL", "BakePairing", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("bake_pairing_checked", "INFO", "Bake Pairing", f"{len(shared_unique_keys)} pairs matched, suffix/pivot/bbox valid with bbox scale {bbox_scale:.3f}")
        else:
            total_fail = (
                len(invalid_high_suffix) + len(invalid_low_suffix) + len(orphan_high_keys) + len(orphan_low_keys)
                + len(duplicate_high) + len(duplicate_low) + len(bbox_pivot_mismatch_keys)
            )
            self.log_check_result("bake_pairing_checked", "FAIL", "Bake Pairing", f"{total_fail} pairing issue(s) detected with bbox scale {bbox_scale:.3f}")

    def check_bake_readiness(self) -> None:
        self._log_step_header(3, "Bake Readiness", category="BakeReady")
        high_root = self.get_manual_selected_root("bake_ready_high_root_menu")
        low_root = self.get_manual_selected_root("bake_ready_low_root_menu")
        if not high_root or not low_root:
            self.log("FAIL", "BakeReady", "Sélection manuelle requise: Select Bake High Root et Select Bake Low Root.")
            self.log_check_result("bake_ready_checked", "FAIL", "Bake Readiness", "manual root selection missing")
            return

        high_meshes = self._collect_mesh_transforms(high_root)
        low_meshes = self._collect_mesh_transforms(low_root)
        meshes = high_meshes + low_meshes
        self.log("INFO", "BakeReady", f"Fichier analysé : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        self.log("INFO", "BakeReady", f"Root Bake High : {high_root}", [high_root])
        self.log("INFO", "BakeReady", f"Root Bake Low : {low_root}", [low_root])
        self.log("INFO", "BakeReady", f"Meshes analysés High/Low : {len(high_meshes)} / {len(low_meshes)}")
        if not meshes:
            self.log("FAIL", "BakeReady", "Aucun mesh dans Bake Scene.")
            self.log_check_result("bake_ready_checked", "FAIL", "Bake Readiness", "no meshes found in Bake scene")
            return

        high_color_flags: List[bool] = []
        for mesh in high_meshes:
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                high_color_flags.append(False)
                continue
            high_color_flags.append(bool(cmds.polyColorSet(shapes[0], query=True, allColorSets=True) or []))
        require_vertex_color = any(high_color_flags)
        self.log("INFO", "BakeReady", f"Vertex color requis = {'Oui' if require_vertex_color else 'Non'}")

        fail_count = 0
        for mesh in meshes:
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            shape = shapes[0] if shapes else None
            uv_sets = cmds.polyUVSet(shape, q=True, allUVSets=True) if shape else []
            has_uv = bool(uv_sets)
            vertex_count = int(cmds.polyEvaluate(mesh, vertex=True) or 0)
            face_count = int(cmds.polyEvaluate(mesh, face=True) or 0)
            non_manifold = len(cmds.polyInfo(mesh, nonManifoldVertices=True) or []) + len(cmds.polyInfo(mesh, nonManifoldEdges=True) or [])
            lamina = len(cmds.polyInfo(mesh, laminaFaces=True) or [])
            has_color = bool(cmds.polyColorSet(shape, query=True, allColorSets=True) or []) if shape else False
            is_high_mesh = mesh in high_meshes
            color_ok = True if not is_high_mesh else ((not require_vertex_color) or has_color)
            non_empty_ok = vertex_count > 0 and face_count > 0
            healthy_ok = (non_manifold == 0 and lamina == 0)
            mesh_ok = has_uv and non_empty_ok and healthy_ok and color_ok
            if not mesh_ok:
                fail_count += 1

            self.log("INFO", "BakeReadyMesh", f"Mesh = {mesh}")
            self.log("INFO" if has_uv else "FAIL", "BakeReadyMesh", f"UV sets présents = {'OK' if has_uv else 'FAIL'}")
            self.log("INFO" if non_empty_ok else "FAIL", "BakeReadyMesh", f"Mesh non vide = {'OK' if non_empty_ok else 'FAIL'} (v={vertex_count}, f={face_count})")
            self.log("INFO" if healthy_ok else "FAIL", "BakeReadyMesh", f"Mesh sain (non-manifold/lamina) = {'OK' if healthy_ok else 'FAIL'} ({non_manifold}/{lamina})")
            color_label = "Vertex color HIGH" if is_high_mesh else "Vertex color LOW (optionnel)"
            self.log("INFO" if color_ok else "FAIL", "BakeReadyMesh", f"{color_label} = {'OK' if color_ok else 'FAIL'}")
            self.log("INFO" if mesh_ok else "FAIL", "BakeReadyMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [mesh])

        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", "BakeReady", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("bake_ready_checked", "INFO", "Bake Readiness", f"{len(meshes)} meshes pass UV/topology/vertex-color requirements")
        else:
            self.log_check_result("bake_ready_checked", "FAIL", "Bake Readiness", f"{fail_count}/{len(meshes)} meshes failed readiness checks")

    def _collect_low_meshes(self) -> List[str]:
        return self._collect_mesh_transforms_in_namespace(self.context["low_fbx_namespace"], exclude_placeholder_named=True)[0]

    def _resolve_low_roots_for_logs(self) -> List[str]:
        roots = self._find_root_candidates("low", namespace=self.context["low_fbx_namespace"])
        if roots:
            self.detected_roots["low"] = roots
            return roots
        return self.detected_roots.get("low", [])

    def run_low_topology_checks(
        self,
        root_menu_key: str = "low_topology_root_menu",
        check_state_key: str = "low_topology_checked",
        category: str = "LowTopology",
        step_index: int = 1,
        step_label: str = "Topology Check",
        source_file_key: str = "low_fbx",
    ) -> None:
        self._log_step_header(step_index, step_label, category=category)
        root = self.get_manual_selected_root(root_menu_key)
        if not root:
            self.log("FAIL", category, "Sélection manuelle requise: Select Low Root for Topology Check.")
            self.log_check_result(check_state_key, "FAIL", "Low Topology Check", "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", category, f"Fichier analysé : {self._basename_from_path(self.paths.get(source_file_key, ''))}")
        self.log("INFO", category, f"Root analysé : {root}", [root])
        self.log("INFO", category, f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", category, "Aucun mesh LOW chargé.")
            self.log_check_result(check_state_key, "FAIL", "Low Topology Check", "no low meshes found on selected root")
            return

        ok_count = 0
        for m in meshes:
            nmv = cmds.polyInfo(m, nonManifoldVertices=True) or []
            nme = cmds.polyInfo(m, nonManifoldEdges=True) or []
            lam = cmds.polyInfo(m, laminaFaces=True) or []
            non_manifold_count = len(nmv) + len(nme)
            non_manifold_uv_count = self._count_non_manifold_uv_components(m)
            lamina_count = len(lam)
            ngon_count = self._mesh_ngon_count(m)
            mesh_ok = (ngon_count == 0 and non_manifold_count == 0 and non_manifold_uv_count == 0 and lamina_count == 0)
            if mesh_ok:
                ok_count += 1

            self.log("INFO", "LowTopologyMesh", f"Mesh = {m}")
            self.log("INFO" if ngon_count == 0 else "FAIL", "LowTopologyMesh", f"N-gons = {'OK' if ngon_count == 0 else f'FAIL ({ngon_count} faces)'}")
            self.log("INFO" if non_manifold_count == 0 else "FAIL", "LowTopologyMesh", f"Non-manifold = {'OK' if non_manifold_count == 0 else f'FAIL ({non_manifold_count} éléments)'}")
            self.log("INFO" if non_manifold_uv_count == 0 else "FAIL", "LowTopologyMesh", f"Non-manifold UV = {'OK' if non_manifold_uv_count == 0 else f'FAIL ({non_manifold_uv_count} éléments)'}")
            self.log("INFO" if lamina_count == 0 else "FAIL", "LowTopologyMesh", f"Lamina faces = {'OK' if lamina_count == 0 else f'FAIL ({lamina_count} faces)'}")
            self.log("INFO" if mesh_ok else "FAIL", "LowTopologyMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [m])

        fail_count = len(meshes) - ok_count
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", category, f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        if ok:
            self._set_subcheck_results(check_state_key, {"non_manifold_geometry": True, "non_manifold_uv": True, "lamina_faces": True, "ngons": True})
            self.log_check_result(check_state_key, "INFO", "Low Topology Check", f"{len(meshes)} meshes clean: no ngons, non-manifold, non-manifold UV or lamina")
        else:
            self._set_subcheck_results(check_state_key, self._topology_subcheck_results(meshes))
            self.log_check_result(check_state_key, "FAIL", "Low Topology Check", f"{fail_count}/{len(meshes)} meshes have topology issues")

    def _scan_namespaces_with_allowed(self, allowed: List[str]) -> List[str]:
        dag_ns: Set[str] = set()
        for node in cmds.ls(long=True) or []:
            dag_ns.update(self._extract_namespaces_from_path(node))
        all_ns = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        dag_ns.update({n for n in all_ns if n and n not in {":", "UI", "shared"}})
        out = []
        for ns in sorted(dag_ns):
            if ns in {"UI", "shared", ":"}:
                continue
            if any(ns == ok or ns.startswith(ok + ":") for ok in allowed):
                continue
            out.append(ns)
        return out

    def scan_low_namespaces(self) -> None:
        self._log_step_header(3, "Namespace Check", category="LowNamespace")
        allowed = sorted(set(self.allowed_review_namespaces).union({
            str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v
        }))
        invalid = self._scan_namespaces_with_allowed(allowed)
        roots = self._resolve_low_roots_for_logs()
        meshes = self._collect_low_meshes()
        self.last_scanned_namespaces = invalid[:]
        self.log("INFO", "LowNamespace", f"Fichier analysé : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "LowNamespace", f"Roots analysés : {self._preview_list(roots, max_items=20)}")
        self.log("INFO", "LowNamespace", f"Meshes analysés : {len(meshes)}")
        self.log("INFO", "LowNamespace", f"Namespaces autorisés : {', '.join(allowed)}")
        self.log("INFO", "LowNamespace", f"Namespaces détectés : {len((cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []))}")
        self.log("INFO", "LowNamespace", f"Namespaces parasites détectés : {len(invalid)}")
        if invalid:
            self.log("WARNING", "LowNamespace", f"Liste : {', '.join(invalid)}")
        ok = not invalid
        self.log("INFO" if ok else "FAIL", "LowNamespace", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("low_namespaces_checked", "INFO", "Low Namespace Scan", "only authorized namespaces found")
        else:
            self.log_check_result("low_namespaces_checked", "FAIL", "Low Namespace Scan", f"{len(invalid)} unauthorized namespace(s) detected", invalid[:30])

    def remove_low_namespaces(self) -> None:
        allowed = set(self.allowed_review_namespaces).union({
            str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v
        })
        removable = [ns for ns in self.last_scanned_namespaces[:] if ns not in allowed]
        for ns in sorted(removable, key=lambda n: n.count(":"), reverse=True):
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            except RuntimeError as exc:
                self.log("WARNING", "LowNamespace", f"Suppression impossible pour {ns}: {exc}")
        self.scan_low_namespaces()

    def analyze_low_materials(
        self,
        root_menu_key: str = "low_materials_root_menu",
        check_state_key: str = "low_materials_checked",
        category: str = "LowMaterials",
        step_index: int = 3,
        step_label: str = "Materials Check",
        source_file_key: str = "low_fbx",
        material_context_key: str = "low",
    ) -> None:
        self._log_step_header(step_index, step_label, category=category)
        root = self.get_manual_selected_root(root_menu_key)
        if not root:
            self.log("FAIL", category, "Sélection manuelle requise: Select Low Root for Materials / Texture Sets.")
            self.log_check_result(check_state_key, "FAIL", "Low Materials Check", "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", category, f"Fichier analysé : {self._basename_from_path(self.paths.get(source_file_key, ''))}")
        self.log("INFO", category, f"Root analysé : {root}", [root])
        self.log("INFO", category, f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", category, "Aucun mesh LOW chargé.")
            self.log_check_result(check_state_key, "FAIL", "Low Materials Check", "no low meshes found on selected root")
            return

        mat_faces: Dict[str, int] = {}
        mat_objects: Dict[str, List[str]] = {}
        mat_full_objects: Dict[str, Set[str]] = {}
        mat_components: Dict[str, Set[str]] = {}
        total_faces = 0
        for mesh in meshes:
            fcount = int(cmds.polyEvaluate(mesh, face=True) or 0)
            total_faces += fcount
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                self.log("WARNING", category, f"Aucun shape valide trouvé pour mesh : {mesh}", [mesh])
                continue
            shape = shapes[0]
            sgs = sorted(set(cmds.listConnections(shape, type="shadingEngine") or []))
            for sg in sgs:
                mats = cmds.ls(cmds.listConnections(sg + ".surfaceShader") or [], materials=True) or []
                if not mats:
                    continue
                mat = mats[0]
                mesh_face_count, object_assigned, component_faces = self._material_assignment_details(mesh, shape, sg, fcount)
                if mesh_face_count <= 0:
                    continue
                mat_faces[mat] = mat_faces.get(mat, 0) + mesh_face_count
                mat_objects.setdefault(mat, []).append(mesh)
                if object_assigned:
                    mat_full_objects.setdefault(mat, set()).add(mesh)
                else:
                    mat_components.setdefault(mat, set()).update(component_faces)

        self.material_sets_by_context[material_context_key] = {}
        sorted_mats = sorted(mat_faces.items(), key=lambda x: x[1], reverse=True)
        self.log("INFO", category, f"Matériaux détectés : {len(sorted_mats)}")
        for mat, count in sorted_mats:
            pct = (count / float(total_faces) * 100.0) if total_faces else 0.0
            display = self._strip_namespaces_from_name(mat)
            has_prefix = display.startswith("QDS_")
            key = f"MAT::{mat}"
            self.material_sets_by_context[material_context_key][key] = {
                "name": mat,
                "display_name": display,
                "objects": sorted(set(mat_objects.get(mat, []))),
                "full_objects": sorted(mat_full_objects.get(mat, set())),
                "components": sorted(mat_components.get(mat, set())),
                "percent_of_total": pct,
                "face_count": count,
                "is_qds": has_prefix,
            }
            self.log("INFO" if has_prefix else "FAIL", category, f"{display} | {pct:.2f}% faces ({count}/{total_faces})", self.material_sets_by_context[material_context_key][key]["objects"][:80])
        if not sorted_mats:
            self.log("FAIL", category, "Aucun material valide trouvé.")
        self.detected_texture_sets = self.material_sets_by_context[material_context_key]
        self._refresh_texture_sets_list_ui(material_context_key)
        ok = bool(self.material_sets_by_context[material_context_key])
        self.log("INFO" if ok else "FAIL", category, f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result(check_state_key, "INFO", "Low Materials Check", f"{len(sorted_mats)} materials detected, assignments validated")
        else:
            self.log_check_result(check_state_key, "FAIL", "Low Materials Check", "no valid material assignment detected")

    def run_final_asset_topology_checks(self) -> None:
        self.run_low_topology_checks(
            root_menu_key="final_topology_root_menu",
            check_state_key="final_topology_checked",
            category="FinalAssetTopology",
            step_index=1,
            step_label="Final Asset Topology Check",
            source_file_key="final_scene_ma",
        )
        root = self.get_manual_selected_root("final_topology_root_menu")
        meshes = self._collect_mesh_transforms(root) if root and cmds.objExists(root) else []
        ngon_total = 0
        for mesh in meshes:
            face_count = int(cmds.polyEvaluate(mesh, face=True) or 0)
            for face_idx in range(face_count):
                vtx = cmds.polyInfo(f"{mesh}.f[{face_idx}]", faceToVertex=True) or []
                tokens = [tok for tok in (vtx[0].replace(":", " ").split() if vtx else []) if tok.isdigit()]
                if len(tokens) > 5:
                    ngon_total += 1
        self.log("INFO", "FinalAssetTopology", f"Final Asset Topology Check: {ngon_total} ngon found")

    def scan_final_asset_namespaces(self) -> None:
        self._log_step_header(2, "Namespace Check", category="FinalAssetNamespace")
        allowed = sorted(set(self.allowed_review_namespaces).union({
            str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v
        }))
        invalid = self._scan_namespaces_with_allowed(allowed)
        self.last_scanned_namespaces = invalid[:]
        meshes = self._collect_mesh_transforms(self.get_manual_selected_root("final_topology_root_menu") or "")
        self.log("INFO", "FinalAssetNamespace", f"Fichier analysé : {self._basename_from_path(self.paths.get('final_scene_ma', ''))}")
        self.log("INFO", "FinalAssetNamespace", f"Meshes analysés : {len(meshes)}")
        self.log("INFO", "FinalAssetNamespace", f"Namespaces parasites détectés : {len(invalid)}")
        if invalid:
            self.log("WARNING", "FinalAssetNamespace", f"Liste : {', '.join(invalid)}")
            self.log_check_result("final_namespaces_checked", "FAIL", "Final Asset Namespace Scan", f"{len(invalid)} unauthorized namespace(s) detected", invalid[:30])
        else:
            self.log_check_result("final_namespaces_checked", "INFO", "Final Asset Namespace Scan", "only authorized namespaces found")

    def remove_final_asset_namespaces(self) -> None:
        allowed = set(self.allowed_review_namespaces).union({
            str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v
        })
        removable = [ns for ns in self.last_scanned_namespaces[:] if ns not in allowed]
        for ns in sorted(removable, key=lambda n: n.count(":"), reverse=True):
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            except RuntimeError as exc:
                self.log("WARNING", "FinalAssetNamespace", f"Suppression impossible pour {ns}: {exc}")
        self.scan_final_asset_namespaces()

    def analyze_final_asset_materials(self) -> None:
        self.analyze_low_materials(
            root_menu_key="final_materials_root_menu",
            check_state_key="final_materials_checked",
            category="FinalAssetMaterials",
            step_index=3,
            step_label="Final Asset Materials Check",
            source_file_key="final_scene_ma",
            material_context_key="final_asset",
        )
        mat_count = len(self.material_sets_by_context.get("final_asset", {}))
        self.log("INFO", "FinalAssetMaterials", f"Final Asset Materials Check: {mat_count} materials detected")

    def run_final_asset_uv_map1_check(self) -> None:
        self.run_low_uv_map1_check(
            root_menu_key="final_uv1_root_menu",
            check_state_key="final_uv_map1_checked",
            category="FinalAssetUV1",
            step_index=4,
            step_label="Final Asset UV Check Map 1",
            source_file_key="final_scene_ma",
        )
        self.log("INFO", "FinalAssetUV1", "Final Asset UV Map1 Check complete: visual confirmation required")

    def run_final_asset_uv_map2_check(self) -> None:
        self.run_low_map2_density_check(
            root_menu_key="final_uv2_root_menu",
            check_state_key="final_uv_map2_checked",
            category="FinalAssetUV2",
            step_index=5,
            step_label="Final Asset UV Check Map 2",
            source_file_key="final_scene_ma",
        )
        self.log("INFO", "FinalAssetUV2", "Final Asset UV Map2 Check complete: visual confirmation required")

    def run_bake_low_topology_checks(self) -> None:
        self.run_low_topology_checks(
            root_menu_key="bake_low_topology_root_menu",
            check_state_key="bake_low_topology_checked",
            category="BakeLowTopology",
            step_index=2,
            step_label="Low Topology Check",
            source_file_key="bake_ma",
        )

    def run_bake_high_vertex_color_check(self) -> None:
        self.check_vertex_colors(
            root_menu_key="bake_high_vertex_root_menu",
            check_state_key="bake_high_vertex_colors_checked",
            category="BakeHighVertexColor",
            step_index=3,
            step_label="Bake High Vertex Color Check",
            source_file_key="bake_ma",
            result_label="Bake High Vertex Color Check",
        )

    def analyze_bake_high_materials(self) -> None:
        self._log_step_header(4, "Bake High Materials", category="BakeHighMaterials")
        root = self.get_manual_selected_root("bake_high_materials_root_menu")
        if not root:
            self.log("FAIL", "BakeHighMaterials", "Sélection manuelle requise: Select Bake High Root for Materials / Texture Sets.")
            self.set_check_status("bake_high_materials_checked", "FAIL")
            return

        original_menu = None
        if "materials_high_root_menu" in self.ui:
            original_menu = self.get_manual_selected_root("materials_high_root_menu")
            self.manual_root_overrides["materials_high_root_menu"] = [root]
            self.refresh_manual_root_menus()
        try:
            self.analyze_texture_sets(mode="materials")
        finally:
            if "materials_high_root_menu" in self.ui:
                if original_menu:
                    self.manual_root_overrides["materials_high_root_menu"] = [original_menu]
                else:
                    self.manual_root_overrides.pop("materials_high_root_menu", None)
                self.refresh_manual_root_menus()

        self.material_sets_by_context["bake_high"] = dict(self.material_sets_by_context.get("high", {}))
        self.detected_texture_sets = self.material_sets_by_context["bake_high"]
        self._refresh_texture_sets_list_ui("bake_high")
        status = self.check_states.get("texture_sets_analyzed", {}).get("status", "PENDING")
        self.set_check_status("bake_high_materials_checked", status)
        self.log("INFO" if status == "OK" else "FAIL", "BakeHighMaterials", f"Résultat final : {status}")

    def analyze_bake_low_materials(self) -> None:
        self.analyze_low_materials(
            root_menu_key="bake_low_materials_root_menu",
            check_state_key="bake_low_materials_checked",
            category="BakeLowMaterials",
            step_index=5,
            step_label="Bake Low Materials",
            source_file_key="bake_ma",
            material_context_key="bake_low",
        )

    def run_bake_low_uv_map1_check(self) -> None:
        self.run_low_uv_map1_check(
            root_menu_key="bake_low_uv1_root_menu",
            check_state_key="bake_low_uv_map1_checked",
            category="BakeLowUV1",
            step_index=6,
            step_label="UV Check Map 1 on Bake Low",
            source_file_key="bake_ma",
        )

    def run_bake_low_uv_map2_check(self) -> None:
        self.run_low_map2_density_check(
            root_menu_key="bake_low_uv2_root_menu",
            check_state_key="bake_low_uv_map2_checked",
            category="BakeLowUV2",
            step_index=7,
            step_label="UV Check Map 2 on Bake Low",
            source_file_key="bake_ma",
        )

    def scan_namespaces(self) -> None:
        self._log_step_header(6, "Namespace Check", category="Namespace")
        user_ns = self._get_scan_namespaces()
        self.last_scanned_namespaces = user_ns[:]
        self.log("INFO", "Namespace", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Namespace", f"Namespaces utilisateur détectés : {len(user_ns)}")

        if not user_ns:
            self.log("INFO", "Namespace", "Résultat : OK (aucun namespace indésirable).")
            self.log_check_result("no_namespaces", "INFO", "Namespace Scan", "only authorized namespaces found")
            return

        total_objs: List[str] = []
        for ns in user_ns:
            objs = cmds.ls(ns + ":*", long=True) or []
            if not objs:
                objs = [n for n in (cmds.ls(long=True) or []) if any(seg.startswith(ns + ":") for seg in n.split("|") if seg)]
            total_objs.extend(objs)
            self.log("WARNING", "Namespace", f"Namespace détecté: {ns} ({len(objs)} objets)", objs[:50])

        self.log("FAIL", "Namespace", f"Résultat : FAIL ({len(user_ns)} namespace(s) utilisateur détecté(s)).", total_objs[:200])
        self.log_check_result("no_namespaces", "FAIL", "Namespace Scan", f"{len(user_ns)} unauthorized namespace(s) detected", total_objs[:30])

    def remove_namespaces(self) -> None:
        self._log_step_header(6, "Namespace Check", category="Namespace")
        removable = self.last_scanned_namespaces[:] or self._get_scan_namespaces()
        removable = [ns for ns in removable if not self._is_allowed_namespace(ns)]
        self.log("INFO", "Namespace", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Namespace", f"Namespaces à supprimer : {len(removable)}")
        if not removable:
            self.log("INFO", "Namespace", "Résultat : OK (rien à supprimer).")
            self.log_summary("INFO", "Namespace Cleanup", "nothing to remove")
            self.set_check_status("no_namespaces", "OK")
            return

        impacted_before = {ns: (cmds.ls(ns + ":*", long=True) or []) for ns in removable}
        removed = []
        failed = []
        # remove deepest first to avoid parent/child namespace conflicts
        for ns in sorted(removable, key=lambda n: n.count(":"), reverse=True):
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
                removed.append(ns)
            except RuntimeError as exc:
                failed.append((ns, str(exc)))

        if removed:
            impacted_objs = []
            for ns in removed:
                impacted_objs.extend(impacted_before.get(ns, []))
            self.log("INFO", "Namespace", f"Namespaces supprimés (merge vers root): {', '.join(removed)}", impacted_objs[:200])

        if failed:
            for ns, err in failed:
                self.log("WARNING", "Namespace", f"Suppression impossible pour {ns}: {err}")
            self.log("FAIL", "Namespace", f"Résultat : FAIL ({len(failed)} namespace(s) non supprimé(s)).")
            self.set_check_status("no_namespaces", "FAIL")
        else:
            self.log("INFO", "Namespace", "Résultat : OK (suppression terminée).")
            self.log_summary("INFO", "Namespace Cleanup", f"removed {len(removed)} namespace(s)")
            self.set_check_status("no_namespaces", "OK")
        self.last_scanned_namespaces = self._get_scan_namespaces()

    def check_placeholder_match(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        _ = (scope_keys, source_label)
        self._log_step_header(1, "Placeholder Check", category="Placeholder")
        file_label = self._basename_from_path(self.paths.get("high_ma", ""))
        self.log("INFO", "Placeholder", f"Analyse du fichier High.ma : {file_label}")
        high_root = self.get_manual_selected_root("placeholder_high_root_menu")
        placeholder_root = self.get_manual_selected_root("placeholder_placeholder_root_menu")
        if not high_root or not placeholder_root:
            self.log("FAIL", "Placeholder", "Sélection manuelle requise: Select High Root et Select Placeholder Root.")
            self.log_check_result("placeholder_checked", "FAIL", "Placeholder Check", "manual root selection missing")
            return
        high_meshes = self._collect_mesh_transforms(high_root)
        placeholder_meshes = self._collect_mesh_transforms(placeholder_root)
        self.log("INFO", "Placeholder", f"High Root sélectionné : {high_root}", [high_root])
        self.log("INFO", "Placeholder", f"Placeholder Root sélectionné : {placeholder_root}", [placeholder_root])
        self.log("INFO", "Placeholder", f"Meshes analysés High/Placeholder : {len(high_meshes)}/{len(placeholder_meshes)}")
        if not high_meshes or not placeholder_meshes:
            self.log("FAIL", "Placeholder", "High/Placeholder non détectés dans High.ma.")
            self.log_check_result("placeholder_checked", "FAIL", "Placeholder Check", "high or placeholder root has no meshes")
            return

        if "placeholder_tolerance_qt" in self.ui and self.ui["placeholder_tolerance_qt"] is not None:
            tolerance_percent = float(self.ui["placeholder_tolerance_qt"].value())
        else:
            tolerance_percent = cmds.floatField(self.ui["placeholder_tolerance"], q=True, value=True) if "placeholder_tolerance" in self.ui else 7.0
        tolerance = max(0.0, float(tolerance_percent)) / 100.0

        def _bbox_dims_for_root(root: str) -> Tuple[float, float, float]:
            bbox = cmds.exactWorldBoundingBox(root) or [0.0] * 6
            if len(bbox) < 6:
                return (0.0, 0.0, 0.0)
            return (
                float(bbox[3] - bbox[0]),
                float(bbox[4] - bbox[1]),
                float(bbox[5] - bbox[2]),
            )

        h_dim = _bbox_dims_for_root(high_root)
        p_dim = _bbox_dims_for_root(placeholder_root)
        bbox_delta = tuple(abs(h_dim[i] - p_dim[i]) for i in range(3))
        ratio = tuple((h_dim[i] / p_dim[i]) if p_dim[i] else 0.0 for i in range(3))
        bbox_ok = all(abs(r - 1.0) <= tolerance for r in ratio if r != 0.0)

        high_pivot = tuple(cmds.xform(high_root, query=True, worldSpace=True, rotatePivot=True) or [0.0, 0.0, 0.0])
        placeholder_pivot = tuple(cmds.xform(placeholder_root, query=True, worldSpace=True, rotatePivot=True) or [0.0, 0.0, 0.0])
        pivot_delta = tuple(abs(high_pivot[i] - placeholder_pivot[i]) for i in range(3))
        pivot_ok = all(v <= 1e-4 for v in pivot_delta)
        pair_ok = bbox_ok and pivot_ok

        self.log("INFO", "PlaceholderPair", "Mode ensemble: aucun matching de sous-mesh par nom.")
        self.log("INFO", "PlaceholderPair", f"High ensemble = {high_root} ({len(high_meshes)} sous-mesh)", [high_root])
        self.log("INFO", "PlaceholderPair", f"Placeholder ensemble = {placeholder_root} ({len(placeholder_meshes)} sous-mesh)", [placeholder_root])
        self.log("INFO", "PlaceholderPair", f"High bbox (ensemble) = {self._fmt_vec(h_dim, precision=2)}")
        self.log("INFO", "PlaceholderPair", f"Placeholder bbox (ensemble) = {self._fmt_vec(p_dim, precision=2)}")
        self.log("INFO", "PlaceholderPair", f"BBox delta (ensemble) = {self._fmt_vec(bbox_delta, precision=2)}")
        self.log("INFO", "PlaceholderPair", f"High pivot (root) = {self._fmt_vec(high_pivot, precision=4)}")
        self.log("INFO", "PlaceholderPair", f"Placeholder pivot (root) = {self._fmt_vec(placeholder_pivot, precision=4)}")
        self.log("INFO", "PlaceholderPair", f"Pivot delta (root) = {self._fmt_vec(pivot_delta, precision=4)}")
        self.log("INFO" if pair_ok else "FAIL", "PlaceholderPair", f"Result = {'OK' if pair_ok else 'FAIL'}", [high_root, placeholder_root])

        ok_count = 1 if pair_ok else 0
        fail_count = 0 if pair_ok else 1
        self.log("INFO" if fail_count == 0 else "FAIL", "Placeholder", f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        if pair_ok:
            self._set_subcheck_results("placeholder_checked", {"bbox": True, "pivot": True})
            self.log_check_result("placeholder_checked", "INFO", "Placeholder Check", "aggregated bbox and pivot are within tolerance")
        else:
            self._set_subcheck_results("placeholder_checked", {"bbox": bbox_ok, "pivot": pivot_ok})
            self.log_check_result(
                "placeholder_checked",
                "FAIL",
                "Placeholder Check",
                f"bbox/pivot mismatch (max bbox delta {max(bbox_delta):.2f}, max pivot delta {max(pivot_delta):.4f})",
                [high_root, placeholder_root],
            )

    def run_topology_checks(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        _ = (scope_keys, source_label)
        self._log_step_header(3, "Topology Check", category="Topology")
        root = self.get_manual_selected_root("topology_high_root_menu")
        if not root:
            self.log("FAIL", "Topology", "Sélection manuelle requise: Select High Root for Topology Check.")
            self.log_check_result("topology_checked", "FAIL", "Topology Check", "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "Topology", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Topology", f"Root analysé : {root}", [root])
        self.log("INFO", "Topology", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "Topology", "Aucun mesh High.ma trouvé.")
            self.log_check_result("topology_checked", "FAIL", "Topology Check", "no high meshes found on selected root")
            return

        ok_count = 0

        for m in meshes:
            nmv = cmds.polyInfo(m, nonManifoldVertices=True) or []
            nme = cmds.polyInfo(m, nonManifoldEdges=True) or []
            lam = cmds.polyInfo(m, laminaFaces=True) or []
            non_manifold_count = len(nmv) + len(nme)
            non_manifold_uv_count = self._count_non_manifold_uv_components(m)
            lamina_count = len(lam)
            ngon_count = 0
            face_count = int(cmds.polyEvaluate(m, face=True) or 0)
            for face_idx in range(face_count):
                vtx = cmds.polyInfo(f"{m}.f[{face_idx}]", faceToVertex=True) or []
                if not vtx:
                    continue
                tokens = [tok for tok in vtx[0].replace(":", " ").split() if tok.isdigit()]
                if len(tokens) > 5:
                    ngon_count += 1

            mesh_ok = (ngon_count == 0 and non_manifold_count == 0 and non_manifold_uv_count == 0 and lamina_count == 0)
            if mesh_ok:
                ok_count += 1
            self.log("INFO", "TopologyMesh", f"Mesh = {m}")
            self.log("INFO" if ngon_count == 0 else "FAIL", "TopologyMesh", f"N-gons = {'OK' if ngon_count == 0 else f'FAIL ({ngon_count} faces)'}")
            self.log("INFO" if non_manifold_count == 0 else "FAIL", "TopologyMesh", f"Non-manifold = {'OK' if non_manifold_count == 0 else f'FAIL ({non_manifold_count} éléments)'}")
            self.log("INFO" if non_manifold_uv_count == 0 else "FAIL", "TopologyMesh", f"Non-manifold UV = {'OK' if non_manifold_uv_count == 0 else f'FAIL ({non_manifold_uv_count} éléments)'}")
            self.log("INFO" if lamina_count == 0 else "FAIL", "TopologyMesh", f"Lamina faces = {'OK' if lamina_count == 0 else f'FAIL ({lamina_count} faces)'}")
            self.log("INFO" if mesh_ok else "FAIL", "TopologyMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [m])

        fail_count = len(meshes) - ok_count
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", "Topology", f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        if ok:
            self._set_subcheck_results("topology_checked", {"non_manifold_geometry": True, "non_manifold_uv": True, "lamina_faces": True, "ngons": True})
            self.log_check_result("topology_checked", "INFO", "Topology Check", f"{len(meshes)} meshes clean: no ngons, non-manifold, non-manifold UV or lamina")
        else:
            self._set_subcheck_results(
                "topology_checked",
                {
                    "non_manifold_geometry": all((len(cmds.polyInfo(m, nonManifoldVertices=True) or []) + len(cmds.polyInfo(m, nonManifoldEdges=True) or [])) == 0 for m in meshes),
                    "non_manifold_uv": all(self._count_non_manifold_uv_components(m) == 0 for m in meshes),
                    "lamina_faces": all(len(cmds.polyInfo(m, laminaFaces=True) or []) == 0 for m in meshes),
                    "ngons": all(self._mesh_ngon_count(m) == 0 for m in meshes),
                },
            )
            self.log_check_result("topology_checked", "FAIL", "Topology Check", f"{fail_count}/{len(meshes)} meshes have topology defects")

    def _count_faces_assigned_to_mesh(
        self,
        mesh: str,
        shape: str,
        shading_group: str,
        mesh_face_count: int,
    ) -> int:
        count, _, _ = self._material_assignment_details(mesh, shape, shading_group, mesh_face_count)
        return count

    def _mesh_ngon_count(self, mesh: str) -> int:
        ngon_count = 0
        face_count = int(cmds.polyEvaluate(mesh, face=True) or 0)
        for face_idx in range(face_count):
            vtx = cmds.polyInfo(f"{mesh}.f[{face_idx}]", faceToVertex=True) or []
            if not vtx:
                continue
            tokens = [tok for tok in vtx[0].replace(":", " ").split() if tok.isdigit()]
            if len(tokens) > 5:
                ngon_count += 1
        return ngon_count

    def _topology_subcheck_results(self, meshes: List[str]) -> Dict[str, bool]:
        return {
            "non_manifold_geometry": all((len(cmds.polyInfo(m, nonManifoldVertices=True) or []) + len(cmds.polyInfo(m, nonManifoldEdges=True) or [])) == 0 for m in meshes),
            "non_manifold_uv": all(self._count_non_manifold_uv_components(m) == 0 for m in meshes),
            "lamina_faces": all(len(cmds.polyInfo(m, laminaFaces=True) or []) == 0 for m in meshes),
            "ngons": all(self._mesh_ngon_count(m) == 0 for m in meshes),
        }

    def _material_assignment_details(
        self,
        mesh: str,
        shape: str,
        shading_group: str,
        mesh_face_count: int,
    ) -> Tuple[int, bool, List[str]]:
        members = cmds.sets(shading_group, query=True) or []
        if not members:
            return 0, False, []

        mesh_short = mesh.split("|")[-1]
        shape_short = shape.split("|")[-1]
        prefixes = (mesh, shape, mesh_short, shape_short)

        object_assigned = False
        face_components: List[str] = []
        for member in members:
            if not isinstance(member, str):
                continue
            if not any(member == p or member.startswith(f"{p}.") for p in prefixes):
                continue
            if ".f[" in member:
                face_components.append(member)
            else:
                object_assigned = True

        if object_assigned:
            return mesh_face_count, True, []
        if not face_components:
            return 0, False, []

        expanded = cmds.ls(face_components, flatten=True) or []
        face_indices: Set[int] = set()
        clean_components: List[str] = []
        for face in expanded:
            if not isinstance(face, str):
                continue
            if not any(face.startswith(f"{p}.f[") for p in prefixes):
                continue
            match = re.search(r"\.f\[(\d+)\]", face)
            if match:
                face_indices.add(int(match.group(1)))
                clean_components.append(face)
        return len(face_indices), False, sorted(set(clean_components))

    def _get_active_model_panels(self) -> List[str]:
        model_panels = cmds.getPanel(type="modelPanel") or []
        return [panel for panel in model_panels if cmds.modelEditor(panel, exists=True)]

    def _disable_material_isolation(self) -> None:
        for panel in self._get_active_model_panels():
            try:
                if cmds.isolateSelect(panel, query=True, state=True):
                    cmds.isolateSelect(panel, state=False)
            except RuntimeError:
                continue
        self.material_isolation_state = {"context": "", "material_key": ""}

    def isolate_on_all_viewports(self, state: int = 1) -> None:
        _ = state
        mel.eval(
            """
string $currentPanel = `paneLayout -q -pane1 viewPanes`;
int $x = `isolateSelect -q -state $currentPanel`;

if ($x == 0)
    enableIsolateSelect $currentPanel 1;
else
    enableIsolateSelect $currentPanel 0;
"""
        )

    def select_objects_from_selected_material(self, context_key: str) -> Optional[str]:
        selected = self._selected_texture_set_names(context_key)
        if not selected:
            self.log("WARNING", "Materials", "Aucun material sélectionné.")
            return None

        material_sets = self.material_sets_by_context.get(context_key, {})
        selected_key = selected[0]
        material_data = material_sets.get(selected_key, {})
        material_name = str(material_data.get("name", "") or "")
        if not material_name or not cmds.objExists(material_name):
            self.log("FAIL", "Materials", "Le nœud sélectionné n'est pas un material valide.")
            return None

        shading_groups = cmds.listConnections(material_name, type="shadingEngine") or []
        if not shading_groups:
            self.log("FAIL", "Materials", "Le nœud sélectionné n'est pas un material valide.")
            return None

        objects = cmds.sets(shading_groups[0], query=True) or []
        if not objects:
            self.log("FAIL", "Materials", "Aucun objet assigné à ce material.")
            return None

        cmds.select(objects, replace=True)
        return selected_key

    def toggle_isolate_selected_material(self, context_key: str) -> None:
        active_key = self.material_isolation_state.get("material_key", "")
        active_context = self.material_isolation_state.get("context", "")
        if active_key and active_context:
            self._disable_material_isolation()
            self.log("INFO", "Materials", "Isolate Material désactivé")
            return

        selected_key = self.select_objects_from_selected_material(context_key)
        if not selected_key:
            return

        self.isolate_on_all_viewports()
        self.material_isolation_state = {"context": context_key, "material_key": selected_key}
        self.log("INFO", "Materials", "Isolate Material activé")

    def analyze_texture_sets(self, mode: str = "materials", scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        _ = (mode, scope_keys, source_label)
        self._log_step_header(6, "Analyze Materials", category="Materials")
        root = self.get_manual_selected_root("materials_high_root_menu")
        if not root:
            self.log("FAIL", "Materials", "Sélection manuelle requise: Select High Root for Materials / Texture Sets.")
            self.log_check_result("texture_sets_analyzed", "FAIL", "Materials Check", "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "Materials", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Materials", f"Root analysé : {root}", [root])
        self.log("INFO", "Materials", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "Materials", "Aucun mesh High.ma trouvé.")
            self.log_check_result("texture_sets_analyzed", "FAIL", "Materials Check", "no high meshes found on selected root")
            return

        mat_faces: Dict[str, int] = {}
        mat_objects: Dict[str, List[str]] = {}
        mat_full_objects: Dict[str, Set[str]] = {}
        mat_components: Dict[str, Set[str]] = {}
        total_faces = 0
        for mesh in meshes:
            fcount = int(cmds.polyEvaluate(mesh, face=True) or 0)
            total_faces += fcount
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                self.log("WARNING", "Materials", f"Aucun shape valide trouvé pour mesh : {mesh}", [mesh])
                continue

            shape = shapes[0]
            sgs = sorted(set(cmds.listConnections(shape, type="shadingEngine") or []))
            mesh_material_faces: Dict[str, int] = {}
            for sg in sgs:
                mats = cmds.ls(cmds.listConnections(f"{sg}.surfaceShader") or [], materials=True) or []
                if not mats:
                    continue
                mat = mats[0]
                assigned_count, object_assigned, component_faces = self._material_assignment_details(mesh, shape, sg, fcount)
                if assigned_count <= 0:
                    continue
                mesh_material_faces[mat] = mesh_material_faces.get(mat, 0) + assigned_count
                if object_assigned:
                    mat_full_objects.setdefault(mat, set()).add(mesh)
                else:
                    mat_components.setdefault(mat, set()).update(component_faces)

            self.log("INFO", "MaterialsMesh", f"Mesh = {mesh}")
            if not mesh_material_faces:
                if fcount > 0:
                    self.log("WARNING", "Materials", f"Aucun material valide trouvé pour mesh : {mesh}", [mesh])
                self.log("FAIL", "MaterialsMesh", "Result = FAIL", [mesh])
                continue

            display_materials = ", ".join(self._strip_namespaces_from_name(m) for m in sorted(mesh_material_faces.keys()))
            self.log("INFO", "MaterialsMesh", f"Materials trouvés = {display_materials}", [mesh])
            for mat, count in sorted(mesh_material_faces.items(), key=lambda item: item[1], reverse=True):
                display_name = self._strip_namespaces_from_name(mat)
                pct = (count / float(fcount) * 100.0) if fcount else 0.0
                level = "INFO" if display_name.startswith("QDS_") else "FAIL"
                self.log(level, "MaterialsMesh", f"{display_name} | {pct:.2f}% faces", [mesh])
                mat_faces[mat] = mat_faces.get(mat, 0) + count
                mat_objects.setdefault(mat, []).append(mesh)
            self.log("INFO", "MaterialsMesh", "Result = OK", [mesh])

        self.detected_texture_sets = {}
        self.material_sets_by_context["high"] = {}
        sorted_mats = sorted(mat_faces.items(), key=lambda x: x[1], reverse=True)
        self.log("INFO", "Materials", f"Matériaux détectés au total : {len(sorted_mats)}")
        for mat, count in sorted_mats:
            pct = (count / float(total_faces) * 100.0) if total_faces else 0.0
            display_name = self._strip_namespaces_from_name(mat)
            key = f"MAT::{mat}"
            self.material_sets_by_context["high"][key] = {
                "name": mat,
                "display_name": display_name,
                "objects": sorted(set(mat_objects.get(mat, []))),
                "full_objects": sorted(mat_full_objects.get(mat, set())),
                "components": sorted(mat_components.get(mat, set())),
                "percent_of_total": pct,
                "face_count": count,
                "is_qds": display_name.startswith("QDS_"),
            }
            level = "INFO" if display_name.startswith("QDS_") else "FAIL"
            self.log(level, "Materials", f"{display_name} | {pct:.2f}% faces ({count}/{total_faces})", self.material_sets_by_context["high"][key]["objects"][:80])
        if not sorted_mats:
            self.log("FAIL", "Materials", "Aucun material valide trouvé.")

        self.detected_texture_sets = self.material_sets_by_context["high"]
        self._refresh_texture_sets_list_ui("high")
        ok = bool(self.material_sets_by_context["high"])
        self.log("INFO" if ok else "FAIL", "Materials", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("texture_sets_analyzed", "INFO", "Materials Check", f"{len(sorted_mats)} material slots detected, assignments validated")
        else:
            self.log_check_result("texture_sets_analyzed", "FAIL", "Materials Check", "no valid material assignment detected")

    def check_vertex_colors(
        self,
        scope_keys: Optional[List[str]] = None,
        source_label: Optional[str] = None,
        root_menu_key: str = "vertex_high_root_menu",
        check_state_key: str = "vertex_colors_checked",
        category: str = "VertexColor",
        step_index: int = 4,
        step_label: str = "Vertex Color Check",
        source_file_key: str = "high_ma",
        result_label: str = "Vertex Color Check",
    ) -> None:
        _ = (scope_keys, source_label)
        self._log_step_header(step_index, step_label, category=category)
        root = self.get_manual_selected_root(root_menu_key)
        if not root:
            self.log("FAIL", category, "Sélection manuelle requise: Select High Root for Vertex Color Check.")
            self.log_check_result(check_state_key, "FAIL", result_label, "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", category, f"Fichier analysé : {self._basename_from_path(self.paths.get(source_file_key, ''))}")
        self.log("INFO", category, f"Root analysé : {root}", [root])
        self.log("INFO", category, f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", category, "Aucun mesh High.ma trouvé.")
            self.log_check_result(check_state_key, "FAIL", result_label, "no high meshes found on selected root")
            return

        ok_count = 0
        for m in meshes:
            shapes = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                continue
            shape = shapes[0]
            sets = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            fcount = int(cmds.polyEvaluate(m, face=True) or 0)
            missing = fcount
            colored_faces = 0
            unqueryable_faces = 0
            distinct_colors: Set[Tuple[float, float, float]] = set()
            for face_idx in range(fcount):
                face_component = f"{m}.f[{face_idx}]"
                try:
                    rgb = cmds.polyColorPerVertex(face_component, query=True, rgb=True) or []
                except RuntimeError:
                    unqueryable_faces += 1
                    rgb = []
                if not rgb:
                    continue
                colored_faces += 1
                chunk_count = len(rgb) // 3
                for idx in range(chunk_count):
                    color = (
                        round(float(rgb[idx * 3 + 0]), 4),
                        round(float(rgb[idx * 3 + 1]), 4),
                        round(float(rgb[idx * 3 + 2]), 4),
                    )
                    distinct_colors.add(color)
            missing = max(0, fcount - colored_faces)
            has_color_set = bool(sets)
            mesh_ok = has_color_set and missing == 0
            if mesh_ok:
                ok_count += 1

            self.log("INFO", "VertexColorMesh", f"Mesh = {m}")
            self.log("INFO", "VertexColorMesh", f"Faces total = {fcount}")
            self.log("INFO", "VertexColorMesh", f"Faces avec vertex color = {colored_faces}")
            self.log("INFO", "VertexColorMesh", f"Faces sans vertex color = {missing}")
            if unqueryable_faces:
                self.log("WARNING", "VertexColorMesh", f"{unqueryable_faces} faces could not be queried on {m}")
            self.log("INFO", "VertexColorMesh", f"Groupes de vertex colors distincts = {len(distinct_colors)}")
            if not has_color_set:
                self.log("FAIL", "VertexColorMesh", "Aucun color set trouvé.")
            self.log("INFO" if mesh_ok else "FAIL", "VertexColorMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [m])

        fail_count = len(meshes) - ok_count
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", category, f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        if ok:
            self.log_check_result(check_state_key, "INFO", result_label, "vertex colors present on all checked meshes")
        else:
            self.log_check_result(check_state_key, "FAIL", result_label, f"{fail_count}/{len(meshes)} meshes missing vertex colors")

    def display_vertex_colors(self) -> None:
        shapes = self._collect_all_scene_mesh_shapes()
        self.log("INFO", "VertexColor", "Display: portée scène Maya complète.")
        if not shapes:
            self.log("WARNING", "VertexColor", "Aucun mesh trouvé dans la scène Maya ouverte.")
            return
        for shape in shapes:
            try:
                cmds.setAttr(shape + ".displayColors", 1)
            except RuntimeError:
                pass
        cmds.polyOptions(colorShadedDisplay=True)
        self.log("INFO", "VertexColor", f"Display: Shapes affectés : {len(shapes)}")
        self.log("INFO", "VertexColor", "Display: Résultat : OK")
        self.log_summary("INFO", "Vertex Colors", f"display enabled on {len(shapes)} mesh shapes (scene-wide)")

    def hide_vertex_colors(self) -> None:
        shapes = self._collect_all_scene_mesh_shapes()
        self.log("INFO", "VertexColor", "Hide: portée scène Maya complète.")
        if not shapes:
            self.log("WARNING", "VertexColor", "Aucun mesh trouvé dans la scène Maya ouverte.")
            return
        for shape in shapes:
            try:
                cmds.setAttr(shape + ".displayColors", 0)
            except RuntimeError:
                pass
        self.log("INFO", "VertexColor", f"Hide: Shapes affectés : {len(shapes)}")
        self.log("INFO", "VertexColor", "Hide: Résultat : OK")
        self.log_summary("INFO", "Vertex Colors", f"display disabled on {len(shapes)} mesh shapes (scene-wide)")

    def _collect_all_scene_mesh_shapes(self) -> List[str]:
        shapes = cmds.ls(type="mesh", long=True) or []
        visible_shapes: List[str] = []
        for shape in shapes:
            if not cmds.objExists(shape):
                continue
            try:
                is_intermediate = bool(cmds.getAttr(shape + ".intermediateObject"))
            except RuntimeError:
                is_intermediate = False
            if not is_intermediate:
                visible_shapes.append(shape)
        return sorted(set(visible_shapes))

    def _collect_all_review_mesh_shapes(self) -> List[str]:
        if not cmds.objExists("Outsourcing_Review"):
            return []
        descendants = cmds.listRelatives("Outsourcing_Review", allDescendents=True, fullPath=True) or []
        shapes = [n for n in descendants if cmds.nodeType(n) == "mesh"]
        return sorted(set(shapes))

    def isolate_meshes_without_vertex_color(self) -> None:
        high_root = self.get_high_root()
        meshes = self._collect_mesh_transforms(root=high_root)

        without_vc = []
        for m in meshes:
            shapes = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                continue
            color_sets = cmds.polyColorSet(shapes[0], query=True, allColorSets=True) or []
            if not color_sets:
                without_vc.append(m)

        if not without_vc:
            self.log("INFO", "VertexColor", "Aucun mesh sans vertex color à isoler.")
            return

        cmds.select(without_vc, replace=True)
        cmds.isolateSelect("modelPanel4", state=True)
        self.log("INFO", "VertexColor", f"Isolation activée pour {len(without_vc)} mesh(es) sans vertex colors.", without_vc)

    def check_required_uv_sets(self, scope_keys: List[str], required_set: str, label: str) -> None:
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        meshes = resolution["meshes"]
        if not meshes:
            self.log("FAIL", "UV", f"Aucun mesh pour check {label}.")
            return
        missing: List[str] = []
        for mesh in meshes:
            shapes = cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                continue
            uv_sets = cmds.polyUVSet(shapes[0], q=True, allUVSets=True) or []
            if required_set not in uv_sets:
                missing.append(mesh)
        if missing:
            self.log("FAIL", "UV", f"{label}: {len(missing)} mesh(es) sans UV set '{required_set}'.", missing[:200])
        else:
            self.log("INFO", "UV", f"{label}: OK ({len(meshes)} mesh(es) avec '{required_set}').")

    def check_final_naming_no_low_suffix(self, scope_keys: List[str]) -> None:
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        meshes = resolution["meshes"]
        invalid = [m for m in meshes if self._strip_namespaces_from_name(self._short_name(m)).lower().endswith("_low")]
        if invalid:
            self.log("FAIL", "Naming", f"Noms finaux invalides avec suffix _low: {len(invalid)}", invalid[:200])
        else:
            self.log("INFO", "Naming", "Naming final OK (aucun suffix _low détecté).")

    def _uv_set_on_shape(self, shape: str, uv_set: str) -> bool:
        sets = cmds.polyUVSet(shape, q=True, allUVSets=True) or []
        return uv_set in sets

    def _set_uv_set_on_meshes(self, meshes: List[str], uv_set: str) -> List[str]:
        switched: List[str] = []
        for mesh in meshes:
            shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [None])[0]
            if not shape or not self._uv_set_on_shape(shape, uv_set):
                continue
            try:
                cmds.polyUVSet(shape, currentUVSet=True, uvSet=uv_set)
                switched.append(mesh)
            except RuntimeError:
                continue
        return switched

    def _open_uv_editor_floating(self) -> None:
        try:
            mel.eval("TextureViewWindow;")
            panels = cmds.getPanel(scriptType="polyTexturePlacementPanel") or []
            if panels:
                panel = panels[-1]
                win = cmds.panel(panel, q=True, control=True)
                if win and cmds.window(win, exists=True):
                    cmds.window(win, e=True, sizeable=True, widthHeight=(900, 700))
        except RuntimeError as exc:
            self.log("WARNING", "UV", f"Impossible d'ouvrir UV Editor flottant: {exc}")

    def _mesh_uv_distortion_ratio(self, mesh: str, uv_set: str = "map1") -> Optional[float]:
        shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [None])[0]
        if not shape or not self._uv_set_on_shape(shape, uv_set):
            return None
        try:
            cmds.polyUVSet(shape, currentUVSet=True, uvSet=uv_set)
        except RuntimeError:
            return None
        face_count = int(cmds.polyEvaluate(mesh, face=True) or 0)
        ratios: List[float] = []
        for i in range(face_count):
            comp = f"{mesh}.f[{i}]"
            try:
                w_area = self._scalar_from_maya_result(cmds.polyEvaluate(comp, worldArea=True), default=0.0)
                uv_area = self._scalar_from_maya_result(cmds.polyEvaluate(comp, uvFaceArea=True), default=0.0)
            except RuntimeError:
                continue
            if w_area <= 1e-12 or uv_area <= 1e-12:
                continue
            ratios.append(max(w_area / uv_area, uv_area / w_area))
        if not ratios:
            return None
        return sum(ratios) / float(len(ratios))

    def run_low_uv_map1_check(
        self,
        root_menu_key: str = "low_uv1_root_menu",
        check_state_key: str = "low_uv_map1_checked",
        category: str = "LowUV1",
        step_index: int = 4,
        step_label: str = "UV Map1 Check",
        source_file_key: str = "low_fbx",
    ) -> None:
        self._log_step_header(step_index, step_label, category=category)
        root = self.get_manual_selected_root(root_menu_key)
        if not root:
            self.log("FAIL", category, "Sélection manuelle requise: Select Low Root for UV map1 Check.")
            self.log_check_result(check_state_key, "FAIL", "UV Map1 Check", "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", category, f"Fichier analysé : {self._basename_from_path(self.paths.get(source_file_key, ''))}")
        self.log("INFO", category, f"Root analysé : {root}", [root])
        self.log("INFO", category, f"Meshes analysés : {len(meshes)}")
        self.log("INFO", category, "Map analysée : map1")
        if not meshes:
            self.log("FAIL", category, "Aucun mesh LOW chargé.")
            self.log_check_result(check_state_key, "FAIL", "UV Map1 Check", "no low meshes found on selected root")
            return

        fail_count = 0
        map1_missing_count = 0
        zero_space_fail_count = 0
        for mesh in meshes:
            shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [None])[0]
            if not shape:
                fail_count += 1
                map1_missing_count += 1
                self.log("INFO", "LowUV1Mesh", f"Mesh = {mesh}")
                self.log("FAIL", "LowUV1Mesh", "Shape introuvable")
                self.log("FAIL", "LowUV1Mesh", "Result = FAIL", [mesh])
                continue
            if not self._uv_set_on_shape(shape, "map1"):
                fail_count += 1
                map1_missing_count += 1
                self.log("INFO", "LowUV1Mesh", f"Mesh = {mesh}")
                self.log("FAIL", "LowUV1Mesh", "UV set map1 manquant")
                self.log("FAIL", "LowUV1Mesh", "Result = FAIL", [mesh])
                continue
            try:
                cmds.polyUVSet(shape, currentUVSet=True, uvSet="map1")
            except RuntimeError:
                fail_count += 1
                map1_missing_count += 1
                self.log("INFO", "LowUV1Mesh", f"Mesh = {mesh}")
                self.log("FAIL", "LowUV1Mesh", "Impossible de forcer map1")
                self.log("FAIL", "LowUV1Mesh", "Result = FAIL", [mesh])
                continue

            overlap_data = cmds.polyUVOverlap(mesh, oc=True) or []
            overlap_count = len(overlap_data) if isinstance(overlap_data, list) else int(bool(overlap_data))
            overlap_ok = overlap_count == 0
            outside_count = 0
            try:
                bbox = cmds.polyEvaluate(mesh, boundingBox2d=True) or []
                if bbox:
                    (u_min, u_max), (v_min, v_max) = bbox
                    if u_min < 0.0 or v_min < 0.0 or u_max > 1.0 or v_max > 1.0:
                        outside_count = 1
            except RuntimeError:
                pass
            outside_ok = outside_count == 0
            zero_space_shells = self._count_zero_space_uv_shells(mesh, "map1")
            zero_space_ok = zero_space_shells == 0
            mesh_ok = overlap_ok and outside_ok and zero_space_ok
            if not mesh_ok:
                fail_count += 1
            if not zero_space_ok:
                zero_space_fail_count += 1

            self.log("INFO", "LowUV1Mesh", f"Mesh = {mesh}")
            self.log("INFO" if outside_ok else "FAIL", "LowUV1Mesh", f"UV shells hors 0-1 = {outside_count}")
            self.log("INFO" if overlap_ok else "FAIL", "LowUV1Mesh", f"UV overlap = {overlap_count}")
            self.log("INFO" if zero_space_ok else "FAIL", "LowUV1Mesh", f"UV shells zero space = {zero_space_shells}")
            self.log("INFO" if mesh_ok else "FAIL", "LowUV1Mesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [mesh])

        ok = fail_count == 0
        overlap_outside_ok = (fail_count - map1_missing_count - zero_space_fail_count) <= 0 and map1_missing_count == 0
        zero_space_ok = zero_space_fail_count == 0 and map1_missing_count == 0
        self._set_subcheck_results(check_state_key, {"overlap_outside": overlap_outside_ok, "zero_space_uv_shells": zero_space_ok})
        self.log("INFO" if ok else "FAIL", category, f"Résultat final : {'OK' if ok else 'FAIL'}")
        self._set_uv_set_on_meshes(meshes, "map1")
        try:
            cmds.select(meshes, replace=True)
        except RuntimeError:
            pass
        if ok:
            self.log_check_result(check_state_key, "INFO", "UV Map1 Check", "UV Map1 Check: map1 validated, visual confirmation requested")
        else:
            fail_message = f"UV Map1 Check: map1 missing or invalid on {map1_missing_count} meshes"
            if fail_count > map1_missing_count:
                fail_message = f"{fail_message}; {fail_count}/{len(meshes)} meshes have overlap or shells outside 0-1"
            if zero_space_fail_count:
                fail_message = f"{fail_message}; {zero_space_fail_count}/{len(meshes)} meshes have zero-space UV shells"
            self.log_check_result(check_state_key, "FAIL", "UV Map1 Check", fail_message)
        self._open_uv_editor_floating()

    def _low_asset_key(self, mesh: str) -> str:
        name = self._strip_namespaces_from_name(self._short_name(mesh)).lower()
        return re.sub(r"_low$", "", name)

    def _estimate_texel_density(self, mesh: str, uv_set: str = "map2", tex_size: int = 2048) -> Optional[float]:
        """Measure texel density with Maya's native UV Toolkit calculation.

        This mirrors the artist workflow: activate UV set, select all UVs of the mesh,
        then run the same MEL command used by Maya's texel density UI.
        """
        shape = (cmds.listRelatives(mesh, shapes=True, noIntermediate=True, fullPath=True) or [None])[0]
        if not shape or not self._uv_set_on_shape(shape, uv_set):
            return None

        previous_selection = cmds.ls(selection=True, long=True) or []
        current_uv_set = cmds.polyUVSet(shape, query=True, currentUVSet=True) or []

        try:
            cmds.polyUVSet(shape, currentUVSet=True, uvSet=uv_set)
            uv_count = int(self._scalar_from_maya_result(cmds.polyEvaluate(shape, uvcoord=True), default=0.0))
            if uv_count <= 0:
                return None

            cmds.select(clear=True)
            cmds.select(f"{mesh}.map[*]", replace=True)
            td_value = mel.eval(f"texGetTexelDensity {int(tex_size)}")
            td = self._scalar_from_maya_result(td_value, default=-1.0)
            return td if td > 0.0 else None
        except RuntimeError:
            return None
        finally:
            if current_uv_set:
                try:
                    cmds.polyUVSet(shape, currentUVSet=True, uvSet=current_uv_set[0])
                except RuntimeError:
                    pass
            try:
                if previous_selection:
                    cmds.select(previous_selection, replace=True)
                else:
                    cmds.select(clear=True)
            except RuntimeError:
                pass

    def run_low_map2_density_check(
        self,
        root_menu_key: str = "low_uv2_root_menu",
        check_state_key: str = "low_uv_map2_checked",
        category: str = "LowUV2",
        step_index: int = 5,
        step_label: str = "UV Map2 Check",
        source_file_key: str = "low_fbx",
    ) -> None:
        self._log_step_header(step_index, step_label, category=category)
        root = self.get_manual_selected_root(root_menu_key)
        if not root:
            self.log("FAIL", category, "Sélection manuelle requise: Select Low Root for UV map2 / TD Check.")
            self.log_check_result(check_state_key, "FAIL", "UV Map2 Check", "manual root selection missing")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", category, f"Fichier analysé : {self._basename_from_path(self.paths.get(source_file_key, ''))}")
        self.log("INFO", category, f"Root analysé : {root}", [root])
        self.log("INFO", category, f"Meshes analysés : {len(meshes)}")
        self.log("INFO", category, "Map analysée : map2")
        if not meshes:
            self.log("FAIL", category, "Aucun mesh LOW chargé.")
            self.log_check_result(check_state_key, "FAIL", "UV Map2 Check", "no low meshes found on selected root")
            return

        valid_values: List[float] = []
        pair_fail_count = 0
        zero_space_fail_count = 0
        for mesh in meshes:
            td = self._estimate_texel_density(mesh, uv_set="map2", tex_size=2048)
            if td is None:
                pair_fail_count += 1
                self.log("INFO", "LowUV2Mesh", f"Mesh = {mesh}")
                self.log("FAIL", "LowUV2Mesh", "TD mesurée = N/A")
                self.log("INFO", "LowUV2Mesh", f"TD cible = {LOW_MAP2_TARGET_TD:.2f}")
                self.log("FAIL", "LowUV2Mesh", "Result = FAIL", [mesh])
                continue

            valid_values.append(td)
            delta = td - LOW_MAP2_TARGET_TD
            zero_space_shells = self._count_zero_space_uv_shells(mesh, "map2")
            zero_space_ok = zero_space_shells == 0
            mesh_ok = abs(delta) <= LOW_MAP2_TOLERANCE and zero_space_ok
            if not mesh_ok:
                pair_fail_count += 1
            if not zero_space_ok:
                zero_space_fail_count += 1
            self.log("INFO", "LowUV2Mesh", f"Mesh = {mesh}")
            self.log("INFO", "LowUV2Mesh", f"TD mesurée = {td:.2f}")
            self.log("INFO", "LowUV2Mesh", f"TD cible = {LOW_MAP2_TARGET_TD:.2f}")
            self.log("INFO", "LowUV2Mesh", f"Delta = {delta:.2f}")
            self.log("INFO" if zero_space_ok else "FAIL", "LowUV2Mesh", f"UV shells zero space = {zero_space_shells}")
            self.log("INFO" if mesh_ok else "FAIL", "LowUV2Mesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [mesh])

        mean_td = (sum(valid_values) / len(valid_values)) if valid_values else 0.0
        self.log("INFO", category, f"Texel density moyenne mesurée : {mean_td:.2f}")
        self.log("INFO", category, f"Tolérance : ±{LOW_MAP2_TOLERANCE:.2f}")
        ok = bool(valid_values) and pair_fail_count == 0
        map2_present_ok = len(valid_values) == len(meshes)
        texel_ok = bool(valid_values) and (pair_fail_count - zero_space_fail_count) == 0
        self._set_subcheck_results(check_state_key, {"map2_present": map2_present_ok, "texel_density": texel_ok, "zero_space_uv_shells": zero_space_fail_count == 0 and map2_present_ok})
        self.log("INFO" if ok else "FAIL", category, f"Résultat global : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result(check_state_key, "INFO", "UV Map2 Check", f"texel density in tolerance on {len(valid_values)} meshes (mean {mean_td:.2f})")
        else:
            msg = f"texel density out of tolerance on {pair_fail_count}/{len(meshes)} meshes"
            if zero_space_fail_count:
                msg = f"{msg}; zero-space UV shells on {zero_space_fail_count}/{len(meshes)} meshes"
            self.log_check_result(check_state_key, "FAIL", "UV Map2 Check", msg)
        self._set_uv_set_on_meshes(meshes, "map2")
        try:
            cmds.select(meshes, replace=True)
        except RuntimeError:
            pass
        self.log("INFO", category, "Affichage UV Editor forcé sur map2")
        self._open_uv_editor_floating()

    def compare_low_vs_bake_low(self) -> None:
        self._log_step_header(6, "Compare Low vs Bake Low", category="LowCompareBake")
        use_global_mode = self._is_global_compare_enabled("compare_low_bake_global_mode", default=False)
        low_root = self.get_manual_selected_root("compare_low_bake_low_root_menu")
        bake_root = self.get_manual_selected_root("compare_low_bake_bake_root_menu")
        if not low_root or not bake_root:
            self.log("FAIL", "CompareLowBake", "Sélection manuelle requise: Select Low.fbx Root et Select Bake Low Root.")
            self.log_check_result("low_bake_compared", "FAIL", "Compare Low vs Bake", "manual root selection missing")
            return
        low_meshes = self._collect_mesh_transforms(low_root)
        bake_meshes = self._collect_mesh_transforms(bake_root)
        self.log("INFO", "CompareLowBake", f"Source A : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "CompareLowBake", f"Source B : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        self.log("INFO", "CompareLowBake", f"Root Low sélectionné : {low_root}", [low_root])
        self.log("INFO", "CompareLowBake", f"Root Bake Low sélectionné : {bake_root}", [bake_root])
        self.log("INFO", "CompareLowBake", f"Meshes analysés Low/BakeLow : {len(low_meshes)} / {len(bake_meshes)}")
        if not low_meshes or not bake_meshes:
            self.log("FAIL", "CompareLowBake", "Compare impossible : Low.fbx ou Bake Low non chargé.")
            self.log_check_result("low_bake_compared", "FAIL", "Compare Low vs Bake", "compare aborted: one root has no meshes")
            return
        if use_global_mode:
            self._run_global_compare(
                category="CompareLowBake",
                uv_category="CompareLowBakeGlobalUV",
                check_state_key="low_bake_compared",
                check_label="Compare Low vs Bake",
                left_root=low_root,
                right_root=bake_root,
                left_label="Low",
                right_label="Bake Low",
            )
            return

        self.log("INFO", "CompareLowBake", "Compare mode = Pair")
        match_data = self._build_mesh_match_pairs(low_meshes, bake_meshes, "Low.fbx", "Bake Low")
        matched_pairs: List[Tuple[str, str]] = match_data["pairs"]
        unmatched_low: List[str] = match_data["unmatched_a"]
        unmatched_bake: List[str] = match_data["unmatched_b"]
        pair_rows: List[Tuple[Optional[Dict[str, object]], Optional[Dict[str, object]]]] = []
        for low_mesh, bake_mesh in matched_pairs:
            pair_rows.append((self._mesh_data_signature(low_mesh, root=low_root), self._mesh_data_signature(bake_mesh, root=bake_root)))
        for low_mesh in unmatched_low:
            pair_rows.append((self._mesh_data_signature(low_mesh, root=low_root), None))
        for bake_mesh in unmatched_bake:
            pair_rows.append((None, self._mesh_data_signature(bake_mesh, root=bake_root)))
        self.log("INFO", "CompareLowBake", f"Paires comparées : {len(pair_rows)}")

        pair_fail_count = 0
        presence_all = True
        topology_all = True
        uv_all = True
        bbox_all = True
        for low_data, bake_data in pair_rows:
            low_name = low_data["path"] if low_data else "UNMATCHED Low.fbx mesh"
            bake_name = bake_data["path"] if bake_data else "UNMATCHED Bake Low mesh"
            low_key = self._normalized_mesh_leaf_key(low_data["path"]) if low_data else "n/a"
            bake_key = self._normalized_mesh_leaf_key(bake_data["path"]) if bake_data else "n/a"

            presence_ok = bool(low_data and bake_data)
            topo_ok = bool(low_data and bake_data and (low_data["v"], low_data["e"], low_data["f"]) == (bake_data["v"], bake_data["e"], bake_data["f"]))
            uv_ok = False
            if low_data and bake_data:
                uv_ok, _uv_details = self._compare_mesh_uv_sets(low_data["path"], bake_data["path"], category="CompareLowBakePairUV")
            bbox_dims_low = (0.0, 0.0, 0.0)
            bbox_dims_bake = (0.0, 0.0, 0.0)
            bbox_delta = (0.0, 0.0, 0.0)
            bbox_center_delta = (0.0, 0.0, 0.0)
            bbox_ok = False
            if presence_ok:
                bbox_dims_low, bbox_center_low = self._mesh_bbox_dims_and_center_world(low_data["path"])
                bbox_dims_bake, bbox_center_bake = self._mesh_bbox_dims_and_center_world(bake_data["path"])
                bbox_delta = tuple(abs(bbox_dims_low[i] - bbox_dims_bake[i]) for i in range(3))
                bbox_center_delta = tuple(abs(bbox_center_low[i] - bbox_center_bake[i]) for i in range(3))
                bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
            pair_ok = presence_ok and topo_ok and uv_ok and bbox_ok
            if not pair_ok:
                pair_fail_count += 1
            presence_all = presence_all and presence_ok
            topology_all = topology_all and topo_ok
            uv_all = uv_all and uv_ok
            bbox_all = bbox_all and bbox_ok

            self.log("INFO", "CompareLowBakePair", f"Low = {low_name}")
            self.log("INFO", "CompareLowBakePair", f"Bake Low = {bake_name}")
            self.log("INFO", "CompareLowBakePair", f"Matching key A = {low_key}")
            self.log("INFO", "CompareLowBakePair", f"Matching key B = {bake_key}")
            self.log("INFO" if presence_ok else "FAIL", "CompareLowBakePair", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
            if not presence_ok:
                self.log("WARNING", "CompareLowBakePair", "Mesh presence mismatch likely caused by hierarchy/key mismatch.")
            self.log("INFO" if topo_ok else "FAIL", "CompareLowBakePair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "CompareLowBakePair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box Low = {self._fmt_vec(bbox_dims_low, precision=2)}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box Bake Low = {self._fmt_vec(bbox_dims_bake, precision=2)}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "CompareLowBakePair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "CompareLowBakePair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        self._set_subcheck_results("low_bake_compared", {"presence": presence_all, "topology": topology_all, "uv": uv_all, "bounding_box": bbox_all})
        self.log("INFO" if ok else "FAIL", "CompareLowBake", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("low_bake_compared", "INFO", "Compare Low vs Bake", "aggregated topology, UVs and bbox match")
        else:
            self.log_check_result("low_bake_compared", "FAIL", "Compare Low vs Bake", f"{pair_fail_count}/{len(pair_rows)} mesh pairs mismatched")

    def compare_low_vs_final_asset(self) -> None:
        self._log_step_header(7, "Compare Low vs Final Asset", category="LowCompareFinal")
        use_global_mode = self._is_global_compare_enabled("compare_low_final_global_mode", default=True)
        low_root = self.get_manual_selected_root("compare_low_final_low_root_menu")
        final_root = self.get_manual_selected_root("compare_low_final_final_root_menu")
        if not low_root or not final_root:
            self.log("FAIL", "CompareLowFinal", "Sélection manuelle requise: Select Low.fbx Root et Select Final Scene Root.")
            self.log_check_result("low_final_compared", "FAIL", "Compare Low vs Final", "manual root selection missing")
            return

        if not cmds.objExists(low_root) or not cmds.objExists(final_root):
            self.log("FAIL", "CompareLowFinal", "Compare impossible : un des roots sélectionnés n'existe plus dans la scène.")
            self.log_check_result("low_final_compared", "FAIL", "Compare Low vs Final", "compare aborted: one selected root no longer exists")
            return

        self.log("INFO", "CompareLowFinal", f"Source A : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "CompareLowFinal", f"Source B : {self._basename_from_path(self.paths.get('final_scene_ma', ''))}")
        self.log("INFO", "CompareLowFinal", f"Root Low sélectionné : {low_root}", [low_root])
        self.log("INFO", "CompareLowFinal", f"Root Final sélectionné : {final_root}", [final_root])
        low_meshes = self._collect_mesh_transforms(low_root)
        final_meshes = self._collect_mesh_transforms(final_root)
        if not low_meshes or not final_meshes:
            self.log("FAIL", "CompareLowFinal", "Compare impossible : Low.fbx ou Final Scene non chargé.")
            self.log_check_result("low_final_compared", "FAIL", "Compare Low vs Final", "compare aborted: one root has no meshes")
            return
        if not use_global_mode:
            self._run_pair_compare(
                category="CompareLowFinal",
                pair_category="CompareLowFinalPair",
                uv_category="CompareLowFinalPairUV",
                check_state_key="low_final_compared",
                check_label="Compare Low vs Final",
                left_root=low_root,
                right_root=final_root,
                left_label="Low.fbx",
                right_label="Final",
                left_meshes=low_meshes,
                right_meshes=final_meshes,
            )
            return
        self.log("INFO", "CompareLowFinal", "Compare mode = Global")
        low_data = self._root_aggregate_signature(low_root)
        final_data = self._root_aggregate_signature(final_root)
        self.log("INFO", "CompareLowFinal", f"Meshes analysés Low/Final : {low_data['mesh_count']} / {final_data['mesh_count']}")

        presence_ok = bool(low_data["mesh_count"] > 0 and final_data["mesh_count"] > 0)
        topo_ok = (low_data["v"], low_data["e"], low_data["f"]) == (final_data["v"], final_data["e"], final_data["f"])
        uv_ok, _uv_details = self._compare_uv_set_signatures(low_data["uv_sets"], final_data["uv_sets"], category="CompareLowFinalUV")
        bbox_delta = tuple(abs(low_data["bbox_dims"][i] - final_data["bbox_dims"][i]) for i in range(3))
        bbox_center_delta = tuple(abs(low_data["bbox_center"][i] - final_data["bbox_center"][i]) for i in range(3))
        bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
        pivot_delta = tuple(abs(low_data["pivot_world"][i] - final_data["pivot_world"][i]) for i in range(3))
        pivot_ok = all(v <= 1e-4 for v in pivot_delta)
        ok = presence_ok and topo_ok and uv_ok and bbox_ok and pivot_ok
        self._set_subcheck_results("low_final_compared", {"presence": presence_ok, "topology": topo_ok, "uv": uv_ok, "bounding_box": bbox_ok, "pivot": pivot_ok})

        self.log("INFO" if presence_ok else "FAIL", "CompareLowFinal", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
        self.log("INFO" if topo_ok else "FAIL", "CompareLowFinal", f"Topology match (totaux root) = {'OK' if topo_ok else 'FAIL'}")
        self.log("INFO" if uv_ok else "FAIL", "CompareLowFinal", f"UV match (totaux root) = {'OK' if uv_ok else 'FAIL'}")
        self.log("INFO", "CompareLowFinal", f"Bounding Box Low (root) = {self._fmt_vec(low_data['bbox_dims'], precision=2)}")
        self.log("INFO", "CompareLowFinal", f"Bounding Box Final (root) = {self._fmt_vec(final_data['bbox_dims'], precision=2)}")
        self.log("INFO", "CompareLowFinal", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
        self.log("INFO", "CompareLowFinal", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
        self.log("INFO" if bbox_ok else "FAIL", "CompareLowFinal", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
        self.log("INFO", "CompareLowFinal", f"Pivot Low (root) = {self._fmt_vec(low_data['pivot_world'], precision=4)}")
        self.log("INFO", "CompareLowFinal", f"Pivot Final (root) = {self._fmt_vec(final_data['pivot_world'], precision=4)}")
        self.log("INFO", "CompareLowFinal", f"Pivot delta = {self._fmt_vec(pivot_delta, precision=4)}")
        self.log("INFO" if pivot_ok else "FAIL", "CompareLowFinal", f"Pivot match = {'OK' if pivot_ok else 'FAIL'}")
        self.log("INFO" if ok else "FAIL", "CompareLowFinal", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log_check_result("low_final_compared", "INFO", "Compare Low vs Final", "aggregated root matches on topology, UVs, bbox and pivot")
        else:
            mismatch_flags = int(not presence_ok) + int(not topo_ok) + int(not uv_ok) + int(not bbox_ok) + int(not pivot_ok)
            self.log_check_result("low_final_compared", "FAIL", "Compare Low vs Final", f"{mismatch_flags} aggregated mismatch type(s) detected")

    def compare_final_asset_ma_vs_fbx(self) -> None:
        self._log_step_header(6, "Compare Final Asset MA vs FBX", category="FinalAssetCompare")
        use_global_mode = self._is_global_compare_enabled("compare_final_ma_fbx_global_mode", default=True)
        ma_root = self.get_manual_selected_root("compare_final_ma_root_menu")
        fbx_root = self.get_manual_selected_root("compare_final_fbx_root_menu")
        if not ma_root or not fbx_root:
            self.log("FAIL", "FinalAssetCompare", "Sélection manuelle requise: Select Final Asset .ma Root et Select Final Asset .fbx Root.")
            self.log_check_result("final_ma_fbx_compared", "FAIL", "Compare Final Asset MA vs FBX", "manual root selection missing")
            return

        if not cmds.objExists(ma_root) or not cmds.objExists(fbx_root):
            self.log("FAIL", "FinalAssetCompare", "Compare impossible : un des roots sélectionnés n'existe plus dans la scène.")
            self.log_check_result("final_ma_fbx_compared", "FAIL", "Compare Final Asset MA vs FBX", "compare aborted: one selected root no longer exists")
            return

        self.log("INFO", "FinalAssetCompare", f"Source A : {self._basename_from_path(self.paths.get('final_scene_ma', ''))}")
        self.log("INFO", "FinalAssetCompare", f"Source B : {self._basename_from_path(self.paths.get('final_asset_fbx', ''))}")
        self.log("INFO", "FinalAssetCompare", f"Root Final Asset MA sélectionné : {ma_root}", [ma_root])
        self.log("INFO", "FinalAssetCompare", f"Root Final Asset FBX sélectionné : {fbx_root}", [fbx_root])
        ma_meshes = self._collect_mesh_transforms(ma_root)
        fbx_meshes = self._collect_mesh_transforms(fbx_root)
        if not ma_meshes or not fbx_meshes:
            self.log("FAIL", "FinalAssetCompare", "Compare impossible : Final Asset MA ou FBX non chargé.")
            self.log_check_result("final_ma_fbx_compared", "FAIL", "Compare Final Asset MA vs FBX", "compare aborted: one root has no meshes")
            return
        if not use_global_mode:
            self._run_pair_compare(
                category="FinalAssetCompare",
                pair_category="FinalAssetComparePair",
                uv_category="FinalAssetComparePairUV",
                check_state_key="final_ma_fbx_compared",
                check_label="Compare Final Asset MA vs FBX",
                left_root=ma_root,
                right_root=fbx_root,
                left_label="Final MA",
                right_label="Final FBX",
                left_meshes=ma_meshes,
                right_meshes=fbx_meshes,
            )
            return
        self.log("INFO", "FinalAssetCompare", "Compare mode = Global")

        ma_data = self._root_aggregate_signature(ma_root)
        fbx_data = self._root_aggregate_signature(fbx_root)
        self.log("INFO", "FinalAssetCompare", f"Meshes analysés MA/FBX : {ma_data['mesh_count']} / {fbx_data['mesh_count']}")

        presence_ok = bool(ma_data["mesh_count"] > 0 and fbx_data["mesh_count"] > 0)
        topo_ok = (ma_data["v"], ma_data["e"], ma_data["f"]) == (fbx_data["v"], fbx_data["e"], fbx_data["f"])
        uv_ok, _uv_details = self._compare_uv_set_signatures(ma_data["uv_sets"], fbx_data["uv_sets"], category="FinalAssetCompareUV")
        bbox_delta = tuple(abs(ma_data["bbox_dims"][i] - fbx_data["bbox_dims"][i]) for i in range(3))
        bbox_center_delta = tuple(abs(ma_data["bbox_center"][i] - fbx_data["bbox_center"][i]) for i in range(3))
        bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
        pivot_delta = tuple(abs(ma_data["pivot_world"][i] - fbx_data["pivot_world"][i]) for i in range(3))
        pivot_ok = all(v <= 1e-4 for v in pivot_delta)
        ok = presence_ok and topo_ok and uv_ok and bbox_ok and pivot_ok
        self._set_subcheck_results("final_ma_fbx_compared", {"presence": presence_ok, "topology": topo_ok, "uv": uv_ok, "bounding_box": bbox_ok, "pivot": pivot_ok})

        self.log("INFO" if presence_ok else "FAIL", "FinalAssetCompare", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
        self.log("INFO" if topo_ok else "FAIL", "FinalAssetCompare", f"Topology match (totaux root) = {'OK' if topo_ok else 'FAIL'}")
        self.log("INFO" if uv_ok else "FAIL", "FinalAssetCompare", f"UV match (totaux root) = {'OK' if uv_ok else 'FAIL'}")
        self.log("INFO", "FinalAssetCompare", f"Bounding Box MA (root) = {self._fmt_vec(ma_data['bbox_dims'], precision=2)}")
        self.log("INFO", "FinalAssetCompare", f"Bounding Box FBX (root) = {self._fmt_vec(fbx_data['bbox_dims'], precision=2)}")
        self.log("INFO", "FinalAssetCompare", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
        self.log("INFO", "FinalAssetCompare", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
        self.log("INFO" if bbox_ok else "FAIL", "FinalAssetCompare", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
        self.log("INFO", "FinalAssetCompare", f"Pivot MA (root) = {self._fmt_vec(ma_data['pivot_world'], precision=4)}")
        self.log("INFO", "FinalAssetCompare", f"Pivot FBX (root) = {self._fmt_vec(fbx_data['pivot_world'], precision=4)}")
        self.log("INFO", "FinalAssetCompare", f"Pivot delta = {self._fmt_vec(pivot_delta, precision=4)}")
        self.log("INFO" if pivot_ok else "FAIL", "FinalAssetCompare", f"Pivot match = {'OK' if pivot_ok else 'FAIL'}")
        self.log("INFO" if ok else "FAIL", "FinalAssetCompare", f"Résultat final : {'OK' if ok else 'FAIL'}")
        if ok:
            self.log("INFO", "FinalAssetCompare", "Final Asset Compare: aggregated root match between MA and FBX")
            self.log_check_result("final_ma_fbx_compared", "INFO", "Compare Final Asset MA vs FBX", "aggregated root matches on topology, UVs, bbox and pivot")
        else:
            self.log("FAIL", "FinalAssetCompare", "Final Asset Compare: aggregated root mismatch between MA and FBX")
            mismatch_flags = int(not presence_ok) + int(not topo_ok) + int(not uv_ok) + int(not bbox_ok) + int(not pivot_ok)
            self.log_check_result("final_ma_fbx_compared", "FAIL", "Compare Final Asset MA vs FBX", f"{mismatch_flags} aggregated mismatch type(s) detected")

    def _root_aggregate_signature(self, root: str) -> Dict[str, object]:
        meshes = self._collect_mesh_transforms(root) if root and cmds.objExists(root) else []
        total_v = 0
        total_e = 0
        total_f = 0
        total_uv = 0
        uv_sets: Dict[str, Dict[str, int]] = {}

        for mesh in meshes:
            data = self._mesh_data_signature(mesh, root=root)
            total_v += int(data.get("v", 0))
            total_e += int(data.get("e", 0))
            total_f += int(data.get("f", 0))
            total_uv += int(data.get("uv_total", 0))
            for uv_name, uv_data in (data.get("uv_sets", {}) or {}).items():
                bucket = uv_sets.setdefault(uv_name, {"count": 0, "shells": 0})
                bucket["count"] += int(uv_data.get("count", 0))
                bucket["shells"] += int(uv_data.get("shells", 0))

        bbox = self._world_union_bbox(meshes)
        bbox_dims = self._bbox_dims(bbox) if bbox else (0.0, 0.0, 0.0)
        bbox_center = self._bbox_center(bbox) if bbox else (0.0, 0.0, 0.0)
        pivot_world = tuple(cmds.xform(root, q=True, ws=True, rotatePivot=True)) if cmds.objExists(root) else (0.0, 0.0, 0.0)

        return {
            "mesh_count": len(meshes),
            "v": total_v,
            "e": total_e,
            "f": total_f,
            "uv_total": total_uv,
            "uv_sets": uv_sets,
            "bbox_dims": bbox_dims,
            "bbox_center": bbox_center,
            "pivot_world": pivot_world,
            "meshes": meshes,
        }

    def run_low_review_checks(self) -> None:
        self.log("INFO", "RunAllLow", "----- Run All Low Steps (01 -> 07) -----")
        if not self._collect_low_meshes():
            self.load_low_fbx_scene()
        self.run_low_topology_checks()
        self.scan_low_namespaces()
        self.analyze_low_materials()
        self.run_low_uv_map1_check()
        self.run_low_map2_density_check()
        self.compare_low_vs_bake_low()
        self.compare_low_vs_final_asset()
        self.log("INFO", "RunAllLow", "Résultat : Run All Low Steps terminé.")

    def run_final_review_checks(self) -> None:
        self.log("INFO", "RunAll", "Final Review désactivée dans cette version High-only.")

    def run_all_checks(self) -> None:
        self.log("INFO", "RunAll", "----- Run All High Steps (01 -> 08) -----")
        self.log("INFO", "RunAll", f"Source High.ma : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "RunAll", f"Source High.fbx : {self._basename_from_path(self.paths.get('high_fbx', ''))}")
        self.log("INFO", "RunAll", f"Source Bake.ma : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        if not (self.context.get("ma_meshes") or []):
            self.load_ma_scene()

        self.check_placeholder_match()
        self.log("INFO", "DesignKit", "Step 02 manuel: vérifiez le design kit puis cliquez 'Mark Step as Reviewed'.")
        self.run_topology_checks()
        self.check_vertex_colors()
        self.scan_namespaces()
        self.analyze_texture_sets(mode="materials")

        if not (self.context.get("fbx_meshes") or []):
            self.load_fbx_into_scene()
        self.compare_ma_vs_fbx()
        self.compare_ma_vs_bake_high()
        self.log("INFO", "RunAll", "Résultat : Run All High Steps terminé.")

    def build_report_payload(self) -> Dict:
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "asset_name": self._detect_asset_name(),
            "file_paths": self.paths,
            "checklist": self.check_states,
            "summary": self._summary_dict(),
            "notes": cmds.scrollField(self.ui["notes_field"], q=True, text=True),
            "results": [
                {
                    "level": i.level,
                    "category": i.category,
                    "message": i.message,
                    "objects": i.objects,
                }
                for i in self.result_items
            ],
        }

    def _summary_dict(self) -> Dict[str, int]:
        return {
            "ok_checks": sum(1 for c in self.check_states.values() if c["status"] == "OK"),
            "warning_count": sum(1 for i in self.result_items if i.level == "WARNING"),
            "fail_count": sum(1 for i in self.result_items if i.level == "FAIL"),
            "pending_checks": sum(1 for c in self.check_states.values() if c["status"] == "PENDING"),
        }

    def _detect_asset_name(self) -> str:
        if self.paths.get("high_ma"):
            return os.path.splitext(os.path.basename(self.paths["high_ma"]))[0]
        scene = cmds.file(query=True, sceneName=True) or ""
        if scene:
            return os.path.splitext(os.path.basename(scene))[0]
        return "UNKNOWN_ASSET"

    def save_report(self) -> None:
        payload = self.build_report_payload()
        out = cmds.fileDialog2(
            fileFilter="JSON (*.json);;Text (*.txt)",
            dialogStyle=2,
            fileMode=0,
            caption="Save High Poly Review Report"
        )
        if not out:
            return

        path = out[0]
        ext = os.path.splitext(path)[1].lower()
        if ext == ".json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._format_text_report(payload))

        self.log("INFO", "Report", f"Rapport sauvegardé: {path}")

    def _format_text_report(self, payload: Dict) -> str:
        lines = []
        lines.append("=== High Poly Review Report ===")
        lines.append(f"Date: {payload['timestamp']}")
        lines.append(f"Asset: {payload['asset_name']}")
        lines.append("")

        lines.append("--- File Paths ---")
        for key, value in payload["file_paths"].items():
            lines.append(f"{key}: {value}")
        lines.append("")

        lines.append("--- Checklist ---")
        for key, data in payload["checklist"].items():
            lines.append(f"{key}: {data['status']} ({data['mode']})")
        lines.append("")

        lines.append("--- Summary ---")
        for key, value in payload["summary"].items():
            lines.append(f"{key}: {value}")
        lines.append("")

        lines.append("--- Notes ---")
        lines.append(payload.get("notes", ""))
        lines.append("")

        lines.append("--- Results ---")
        for item in payload["results"]:
            lines.append(f"[{item['level']}] {item['category']}: {item['message']}")
            if item["objects"]:
                lines.append(f"  objects: {', '.join(item['objects'][:20])}")
        lines.append("")

        return "\n".join(lines)


_TOOL_INSTANCE: Optional[HighPolyReviewTool] = None


def show_outsource_review_tool() -> HighPolyReviewTool:
    """Launch tool window and keep a live instance in module scope."""
    global _TOOL_INSTANCE
    _TOOL_INSTANCE = HighPolyReviewTool()
    _TOOL_INSTANCE.build()
    return _TOOL_INSTANCE


def launch_highpoly_review_tool() -> HighPolyReviewTool:
    """Backward-compatible launcher."""
    return show_outsource_review_tool()


if __name__ == "__main__":
    # Running the file directly inside Maya Script Editor now opens the window immediately.
    show_outsource_review_tool()
