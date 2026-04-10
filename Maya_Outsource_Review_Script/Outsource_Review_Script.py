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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import maya.cmds as cmds


WINDOW_NAME = "highPolyReviewAssistantWin"
WINDOW_TITLE = "Outsource Review Script"
MAX_UI_TEXT_LENGTH = 90
MAX_MENU_LABEL_LENGTH = 72
ROOT_SUFFIXES = {
    "high": "_high",
    "placeholder": "_placeholder",
    "low": "_low",
}
PLACEHOLDER_TOKEN = "placeholder"
HIGH_REVIEW_SCOPE_ORDER = ["high_ma", "high_fbx", "bake_high"]


@dataclass
class ReviewIssue:
    level: str  # INFO, WARNING, FAIL
    category: str
    message: str
    objects: List[str] = field(default_factory=list)


class HighPolyReviewTool:
    """Main tool class for High Poly outsourcing review."""

    def __init__(self) -> None:
        self.ui = {}
        self.result_items: List[ReviewIssue] = []
        self.result_index_to_objects: Dict[int, List[str]] = {}

        self.paths = {
            "root": "",
            "ma": "",
            "fbx": "",
            "bake_ma": "",
            "low_fbx": "",
            "high_ma": "",
            "high_fbx": "",
            "final_asset_ma": "",
            "final_asset_fbx": "",
        }

        self.detected_files: Dict[str, List[str]] = {
            "ma": [],
            "fbx": [],
            "bake_ma": [],
            "low_fbx": [],
            "high_ma": [],
            "high_fbx": [],
            "final_asset_ma": [],
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
            "low_fbx_namespace": "Low_FBX_File",
            "bake_ma_namespace": "Bake_MA_File",
            "final_asset_ma_namespace": "FinalAsset_MA_File",
            "final_asset_fbx_namespace": "FinalAsset_FBX_File",
            "fbx_nodes": [],
            "fbx_meshes": [],
            "ma_nodes": [],
            "ma_meshes": [],
        }

        self.check_states = {
            "ma_fbx_compared": {"status": "PENDING", "mode": "AUTO"},
            "no_namespaces": {"status": "PENDING", "mode": "AUTO"},
            "placeholder_checked": {"status": "PENDING", "mode": "AUTO"},
            "design_kit_checked": {"status": "PENDING", "mode": "MANUAL"},
            "topology_checked": {"status": "PENDING", "mode": "AUTO"},
            "texture_sets_analyzed": {"status": "PENDING", "mode": "AUTO"},
            "vertex_colors_checked": {"status": "PENDING", "mode": "AUTO"},
        }

        self.check_ui_map = {
            "ma_fbx_compared": "check_ma_fbx",
            "no_namespaces": "check_ns",
            "placeholder_checked": "check_placeholder",
            "design_kit_checked": "check_design",
            "topology_checked": "check_topology",
            "texture_sets_analyzed": "check_texturesets",
            "vertex_colors_checked": "check_vtx",
        }

        self.detected_texture_sets: Dict[str, Dict[str, object]] = {}
        self.texture_set_visibility: Dict[str, bool] = {}
        self.texture_set_label_to_key: Dict[str, str] = {}
        self.texture_set_section_headers: Set[str] = set()
        self.last_scanned_namespaces: List[str] = []
        self.scope_keys = ["placeholder", "high_ma", "high_fbx", "bake_high"]
        self.scope_labels = {
            "placeholder": "Placeholder",
            "high_ma": "High MA",
            "high_fbx": "High FBX",
            "bake_high": "Bake High",
        }
        self.last_texture_scope: List[str] = []

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
        )

        root_layout = cmds.formLayout()
        self.ui["scroll"] = cmds.scrollLayout(
            childResizable=True,
            horizontalScrollBarThickness=12,
            verticalScrollBarThickness=12,
        )

        self.ui["content_col"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_file_section()
        self._build_general_checks_section()
        self._build_review_tabs_section()
        self._build_results_section()
        self._build_notes_section()
        self._build_summary_section()

        cmds.setParent(root_layout)
        cmds.formLayout(
            root_layout,
            edit=True,
            attachForm=[
                (self.ui["scroll"], "top", 0),
                (self.ui["scroll"], "left", 0),
                (self.ui["scroll"], "right", 0),
                (self.ui["scroll"], "bottom", 0),
            ],
        )

        cmds.window(self.ui["window"], edit=True, resizeToFitChildren=False)
        cmds.showWindow(self.ui["window"])

        if cmds.window(self.ui["window"], exists=True):
            cmds.window(self.ui["window"], edit=True, widthHeight=(860, 900))

        self.refresh_detected_file_labels()
        self.refresh_root_ui()
        self.refresh_summary()
        self.refresh_checklist_ui()

    def _build_file_section(self) -> None:
        cmds.frameLayout(label="1) Fichiers / Détection / Références", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        self.ui["root_field"] = cmds.textFieldButtonGrp(
            label="Root Folder",
            buttonLabel="Browse",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.pick_root_folder(),
        )
        cmds.button(label="Scan Delivery Folder", height=30, command=lambda *_: self.scan_delivery_folder())

        cmds.separator(style="in")

        cmds.text(label="High MA Found", align="left")
        self.ui["high_ma_status"] = cmds.text(label="Aucun fichier High MA détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["high_ma_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("high_ma"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["high_ma_menu"])
        cmds.button(label="Load MA (Reference)", height=28, command=lambda *_: self.load_ma_scene())
        cmds.setParent("..")

        cmds.text(label="High FBX Found", align="left")
        self.ui["high_fbx_status"] = cmds.text(label="Aucun fichier High FBX détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["high_fbx_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("high_fbx"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["high_fbx_menu"])
        cmds.button(label="Reference FBX", height=28, command=lambda *_: self.load_fbx_into_scene())
        cmds.setParent("..")

        cmds.text(label="Low FBX Found", align="left")
        self.ui["low_fbx_status"] = cmds.text(label="Aucun fichier Low FBX détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["low_fbx_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("low_fbx"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["low_fbx_menu"])
        cmds.button(label="Reference Low FBX", height=28, command=lambda *_: self.load_low_fbx_scene())
        cmds.setParent("..")

        cmds.text(label="Bake Scene Found", align="left")
        self.ui["bake_ma_status"] = cmds.text(label="Aucun fichier Bake Scene détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["bake_ma_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("bake_ma"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["bake_ma_menu"])
        cmds.button(label="Load Bake MA (Reference)", height=28, command=lambda *_: self.load_bake_ma_scene())
        cmds.setParent("..")

        cmds.text(label="Final Asset MA Found", align="left")
        self.ui["final_asset_ma_status"] = cmds.text(label="Aucun fichier Final Asset MA détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["final_asset_ma_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("final_asset_ma"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["final_asset_ma_menu"])
        cmds.button(label="Load Final MA (Reference)", height=28, command=lambda *_: self.load_final_asset_ma_scene())
        cmds.setParent("..")

        cmds.text(label="Final Asset FBX Found", align="left")
        self.ui["final_asset_fbx_status"] = cmds.text(label="Aucun fichier Final Asset FBX détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["final_asset_fbx_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("final_asset_fbx"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["final_asset_fbx_menu"])
        cmds.button(label="Reference Final FBX", height=28, command=lambda *_: self.load_final_asset_fbx_scene())
        cmds.setParent("..")

        cmds.separator(style="in")

        cmds.text(label="Detected High Root", align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6), (3, "both", 6)])
        self.ui["high_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("high"))
        cmds.menuItem(label="High root non détecté", parent=self.ui["high_root_menu"])
        cmds.button(label="Auto Detect", height=24, command=lambda *_: self.auto_detect_scene_roots())
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("high"))
        cmds.setParent("..")

        cmds.text(label="Detected Placeholder Root", align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6), (3, "both", 6)])
        self.ui["placeholder_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("placeholder"))
        cmds.menuItem(label="Placeholder root non détecté", parent=self.ui["placeholder_root_menu"])
        cmds.button(label="Auto Detect", height=24, command=lambda *_: self.auto_detect_scene_roots())
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("placeholder"))
        cmds.setParent("..")

        cmds.text(label="Detected Low Root", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["low_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("low"))
        cmds.menuItem(label="Low root non détecté", parent=self.ui["low_root_menu"])
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("low"))
        cmds.setParent("..")

        cmds.text(label="Detected Bake High Root", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["bake_high_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("bake_high"))
        cmds.menuItem(label="Bake High root non détecté", parent=self.ui["bake_high_root_menu"])
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("bake_high"))
        cmds.setParent("..")

        cmds.text(label="Detected Bake Low Root", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["bake_low_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("bake_low"))
        cmds.menuItem(label="Bake Low root non détecté", parent=self.ui["bake_low_root_menu"])
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("bake_low"))
        cmds.setParent("..")

        cmds.text(label="Detected Final Asset MA Root", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["final_asset_ma_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("final_asset_ma"))
        cmds.menuItem(label="Final Asset MA root non détecté", parent=self.ui["final_asset_ma_root_menu"])
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("final_asset_ma"))
        cmds.setParent("..")

        cmds.text(label="Detected Final Asset FBX Root", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["final_asset_fbx_root_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_root_selection_changed("final_asset_fbx"))
        cmds.menuItem(label="Final Asset FBX root non détecté", parent=self.ui["final_asset_fbx_root_menu"])
        cmds.button(label="From Selection", height=24, command=lambda *_: self.set_root_from_selection("final_asset_fbx"))
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_technical_checks_section(self) -> None:
        cmds.frameLayout(label="Checks techniques (High)", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui["check_ma_fbx"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Compare MA / FBX / BakeScene", align="left")
        cmds.button(label="Run Compare MA vs FBX vs BakeScene", height=26, command=lambda *_: self.compare_ma_vs_fbx())
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=5, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 6), (5, "both", 2)])
        self.ui["check_placeholder"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Placeholder match", align="left")
        cmds.button(label="Run Placeholder match", height=26, command=lambda *_: self.check_placeholder_match())
        cmds.text(label="Tolerance %", align="right")
        self.ui["placeholder_tolerance"] = cmds.floatField(minValue=0.0, value=7.0, precision=2, step=0.25, width=70)
        cmds.setParent("..")
        self._build_check_row("check_topology", "Topology", self.run_topology_checks)
        self._build_check_row("check_texturesets", "Texture Sets", lambda: self.analyze_texture_sets(mode="materials"))

        cmds.rowLayout(
            numberOfColumns=5,
            adjustableColumn=2,
            columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)],
        )
        self.ui["check_vtx"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Vertex Colors", align="left")
        cmds.button(label="Run Vertex Colors", height=26, command=lambda *_: self.check_vertex_colors())
        cmds.button(label="Display Vertex Color", height=26, command=lambda *_: self.display_vertex_colors())
        cmds.button(label="Hide Vertex Color", height=26, command=lambda *_: self.hide_vertex_colors())
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui["check_design"] = cmds.checkBox(
            label="",
            value=False,
            changeCommand=lambda *_: self.on_manual_design_toggle(),
        )
        cmds.text(label="Design kit review (manuel)", align="left")
        cmds.button(label="Mark as Reviewed", height=26, command=lambda *_: self.mark_design_reviewed())
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_texture_sets_section(self) -> None:
        cmds.frameLayout(label="Texture Sets / Contrôles visuels (High)", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
        cmds.button(label="Run Texture Sets", height=28, command=lambda *_: self.analyze_texture_sets(mode="materials"))
        cmds.button(label="Run Texture Sets (Groups Method)", height=28, command=lambda *_: self.analyze_texture_sets(mode="groups"))
        cmds.setParent("..")

        cmds.text(
            label="Liste des sets (sélection multiple possible) — séparée par source (High .ma / High .fbx / High _bake.ma).",
            align="left",
        )
        self.ui["texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=180,
            selectCommand=lambda *_: self.on_texture_set_selection_changed(),
        )

        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        cmds.button(label="Hide Selected Sets", height=26, command=lambda *_: self.set_texture_set_visibility(False, selected_only=True))
        cmds.button(label="Show Selected Sets", height=26, command=lambda *_: self.set_texture_set_visibility(True, selected_only=True))
        cmds.button(label="Toggle Selected Sets", height=26, command=lambda *_: self.toggle_selected_texture_sets())
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
        cmds.button(label="Isolate Selected Sets", height=26, command=lambda *_: self.isolate_selected_texture_sets())
        cmds.button(label="Show All Texture Sets", height=26, command=lambda *_: self.show_all_texture_sets())
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_general_checks_section(self) -> None:
        cmds.frameLayout(label="2) General Checks", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_ns"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Pas de namespaces (global scène)", align="left")
        cmds.button(label="Scan Namespaces", height=26, command=lambda *_: self.scan_namespaces())
        cmds.button(label="Remove Namespaces", height=26, command=lambda *_: self.remove_namespaces())
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_review_tabs_section(self) -> None:
        cmds.frameLayout(label="3) Review Tabs", collapsable=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True)
        self.ui["review_tabs"] = cmds.tabLayout(innerMarginWidth=8, innerMarginHeight=8)

        self.ui["high_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_technical_checks_section()
        self._build_texture_sets_section()
        self._build_global_action_section()
        cmds.setParent("..")

        self.ui["low_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label="Low review layout à venir.", align="left")
        cmds.setParent("..")

        self.ui["bake_scene_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label="Bake Scene review layout à venir.", align="left")
        cmds.setParent("..")

        self.ui["final_delivery_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label="Final Delivery review layout à venir.", align="left")
        cmds.setParent("..")

        cmds.tabLayout(
            self.ui["review_tabs"],
            edit=True,
            tabLabel=[
                (self.ui["high_tab"], "High"),
                (self.ui["low_tab"], "Low"),
                (self.ui["bake_scene_tab"], "Bake Scene"),
                (self.ui["final_delivery_tab"], "Final Delivery"),
            ],
        )
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_general_checks_section(self) -> None:
        cmds.frameLayout(label="2) General Checks", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_ns"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Pas de namespaces (global scène)", align="left")
        cmds.button(label="Scan Namespaces", height=26, command=lambda *_: self.scan_namespaces())
        cmds.button(label="Remove Namespaces", height=26, command=lambda *_: self.remove_namespaces())
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_review_tabs_section(self) -> None:
        cmds.frameLayout(label="3) Review Tabs", collapsable=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True)
        self.ui["review_tabs"] = cmds.tabLayout(innerMarginWidth=8, innerMarginHeight=8)

        self.ui["high_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_technical_checks_section()
        self._build_texture_sets_section()
        self._build_global_action_section()
        cmds.setParent("..")

        self.ui["low_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label="Low review layout à venir.", align="left")
        cmds.setParent("..")

        self.ui["bake_scene_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label="Bake Scene review layout à venir.", align="left")
        cmds.setParent("..")

        self.ui["final_delivery_tab"] = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        cmds.text(label="Final Delivery review layout à venir.", align="left")
        cmds.setParent("..")

        cmds.tabLayout(
            self.ui["review_tabs"],
            edit=True,
            tabLabel=[
                (self.ui["high_tab"], "High"),
                (self.ui["low_tab"], "Low"),
                (self.ui["bake_scene_tab"], "Bake Scene"),
                (self.ui["final_delivery_tab"], "Final Delivery"),
            ],
        )
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_check_row(self, check_key_ui: str, label: str, command) -> None:
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui[check_key_ui] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label=label, align="left")
        cmds.button(label=f"Run {label}", height=26, command=lambda *_: command())
        cmds.setParent("..")

    def _build_global_action_section(self) -> None:
        cmds.frameLayout(label="Actions (High)", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6), (3, "both", 6)])
        cmds.button(label="Run All High Checks", height=30, command=lambda *_: self.run_all_checks())
        cmds.button(label="Clear Results", height=30, command=lambda *_: self.clear_results())
        cmds.button(label="Save Review Report", height=30, command=lambda *_: self.save_report())
        cmds.setParent("..")

        cmds.button(
            label="Isolate meshes without VColor",
            height=28,
            command=lambda *_: self.isolate_meshes_without_vertex_color(),
        )

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_results_section(self) -> None:
        cmds.frameLayout(label="4) Résultats / Log", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["results_list"] = cmds.textScrollList(
            allowMultiSelection=False,
            height=260,
            selectCommand=lambda *_: self.on_result_selected(),
        )
        cmds.text(label="Tip: clique une ligne liée à des objets pour sélectionner en scène.")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_notes_section(self) -> None:
        cmds.frameLayout(label="5) Notes", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["notes_field"] = cmds.scrollField(wordWrap=True, height=130, text="")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_summary_section(self) -> None:
        cmds.frameLayout(label="6) Résumé global", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["summary_text"] = cmds.text(label="Pending checks", align="left", backgroundColor=(0.22, 0.22, 0.22))
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
        short = self._short_name(node)
        if len(node) <= MAX_MENU_LABEL_LENGTH:
            return node
        hint_max = max(12, MAX_MENU_LABEL_LENGTH - len(short) - 5)
        tail_hint = self._ellipsize_middle(node, max_length=hint_max)
        return f"{short} | {tail_hint}"

    def log(self, level: str, category: str, message: str, objects: Optional[List[str]] = None) -> None:
        issue = ReviewIssue(level=level, category=category, message=message, objects=objects or [])
        self.result_items.append(issue)

        prefix = {
            "INFO": "[INFO]",
            "WARNING": "[WARN]",
            "FAIL": "[FAIL]",
        }.get(level, "[INFO]")

        display = self._ellipsize_middle(f"{prefix} {category}: {message}", max_length=MAX_UI_TEXT_LENGTH)
        idx = cmds.textScrollList(self.ui["results_list"], q=True, numberOfItems=True) or 0
        cmds.textScrollList(self.ui["results_list"], e=True, append=display)
        self.result_index_to_objects[idx + 1] = issue.objects

    def clear_results(self) -> None:
        self.result_items = []
        self.result_index_to_objects = {}
        cmds.textScrollList(self.ui["results_list"], e=True, removeAll=True)
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

    def refresh_checklist_ui(self) -> None:
        for key, ctrl in self.check_ui_map.items():
            is_checked = self.check_states[key]["status"] == "OK"
            cmds.checkBox(self.ui[ctrl], e=True, value=is_checked)

        self.refresh_summary()

    def set_check_status(self, check_key: str, status: str) -> None:
        self.check_states[check_key]["status"] = status
        self.refresh_checklist_ui()

    def on_result_selected(self) -> None:
        selected = cmds.textScrollList(self.ui["results_list"], q=True, selectIndexedItem=True) or []
        if not selected:
            return
        idx = selected[0]
        targets = [o for o in self.result_index_to_objects.get(idx, []) if cmds.objExists(o)]
        if targets:
            cmds.select(targets, replace=True)

    def on_manual_design_toggle(self) -> None:
        checked = cmds.checkBox(self.ui["check_design"], q=True, value=True)
        self.set_check_status("design_kit_checked", "OK" if checked else "PENDING")
        if checked:
            self.log("INFO", "DesignKit", "Validation design kit cochée manuellement.")

    def mark_design_reviewed(self) -> None:
        cmds.checkBox(self.ui["check_design"], e=True, value=True)
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
            ("low_fbx", "low_fbx_status", "Low FBX"),
            ("bake_ma", "bake_ma_status", "Bake Scene"),
            ("final_asset_ma", "final_asset_ma_status", "Final Asset MA"),
            ("final_asset_fbx", "final_asset_fbx_status", "Final Asset FBX"),
        ]

        for file_key, status_widget, label in status_map:
            file_count = len(self.detected_files[file_key])
            text = f"Aucun fichier {label} détecté"
            if file_count == 1:
                text = f"1 fichier détecté: {os.path.basename(self.detected_files[file_key][0])}"
            elif file_count > 1:
                text = f"{file_count} fichiers détectés. Sélectionnez le bon fichier."
            cmds.text(self.ui[status_widget], e=True, label=text)

    def on_detected_file_selected(self, file_key: str) -> None:
        files = self.detected_files[file_key]
        if not files:
            self.paths[file_key] = ""
            if file_key == "high_ma":
                self.paths["ma"] = ""
            elif file_key == "high_fbx":
                self.paths["fbx"] = ""
            return

        index = cmds.optionMenu(self.ui[f"{file_key}_menu"], q=True, select=True) - 1
        index = max(0, min(index, len(files) - 1))
        self.paths[file_key] = files[index]
        if file_key == "high_ma":
            self.paths["ma"] = self.paths[file_key]
        elif file_key == "high_fbx":
            self.paths["fbx"] = self.paths[file_key]
        self.log("INFO", "Scan", f"{file_key.upper()} sélectionné: {self.paths[file_key]}")

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
            "bake_ma": [],
            "low_fbx": [],
            "high_fbx": [],
            "high_ma": [],
            "final_asset_ma": [],
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
                elif name_lower.endswith(".ma") and not name_lower.endswith(("_low.ma", "_high.ma", "_bake.ma")):
                    found_files["final_asset_ma"].append(full_path)
                elif name_lower.endswith(".fbx") and not name_lower.endswith(("_low.fbx", "_high.fbx", "_bake.fbx")):
                    found_files["final_asset_fbx"].append(full_path)

        for key in found_files:
            found_files[key].sort()

        for key, files in found_files.items():
            self.detected_files[key] = files
        self.detected_files["ma"] = found_files["high_ma"][:]
        self.detected_files["fbx"] = found_files["high_fbx"][:]

        for file_key in ["high_ma", "high_fbx", "low_fbx", "bake_ma", "final_asset_ma", "final_asset_fbx"]:
            self._populate_file_option_menu(file_key)
        self.paths["ma"] = self.paths.get("high_ma", "")
        self.paths["fbx"] = self.paths.get("high_fbx", "")
        self.refresh_detected_file_labels()

        scan_logs = [
            ("high_ma", "Aucun fichier High MA (*_HIGH.ma) trouvé."),
            ("high_fbx", "Aucun fichier High FBX (*_HIGH.fbx) trouvé."),
            ("low_fbx", "Aucun fichier Low FBX (*_LOW.fbx) trouvé."),
            ("bake_ma", "Aucun fichier Bake Scene (*_BAKE.ma) trouvé."),
            ("final_asset_ma", "Aucun fichier Final Asset MA (.ma sans suffix _low/_high/_bake) trouvé."),
            ("final_asset_fbx", "Aucun fichier Final Asset FBX (.fbx sans suffix _low/_high/_bake) trouvé."),
        ]
        for file_key, warning_msg in scan_logs:
            count = len(found_files[file_key])
            if not count:
                self.log("WARNING", "Scan", warning_msg)
            else:
                label = file_key.replace("_", " ").title()
                self.log("INFO", "Scan", f"{count} fichier(s) {label} détecté(s).")

    def _populate_root_option_menu(self, root_key: str) -> None:
        menu = self.ui[f"{root_key}_root_menu"]
        items = self.detected_roots[root_key]
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

    def on_root_selection_changed(self, root_key: str) -> None:
        root = self.get_detected_root(root_key)
        if root:
            self.log(
                "INFO",
                "RootDetect",
                f"{root_key.capitalize()} root sélectionné: {self._ellipsize_middle(root, max_length=MAX_UI_TEXT_LENGTH - 36)}",
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
            f"{root_key.capitalize()} root défini depuis la sélection: {self._ellipsize_middle(sel[0], max_length=MAX_UI_TEXT_LENGTH - 45)}",
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

        matching_meshes = [m for m in mesh_transforms if self._matches_asset_kind(m, asset_kind)]
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
            self.detected_roots["low"] = self._find_root_candidates("low", namespace=namespace)
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

        self.refresh_root_ui()

    def _log_root_detection(self, root_key: str, label: str) -> None:
        candidates = self.detected_roots.get(root_key, [])
        if not candidates:
            self.log("WARNING", "RootDetect", f"{label} root non détecté.")
            return
        self.log(
            "INFO",
            "RootDetect",
            f"{label} root détecté: {self._ellipsize_middle(candidates[0], max_length=MAX_UI_TEXT_LENGTH - 20)}",
            [candidates[0]],
        )
        if len(candidates) > 1:
            self.log("WARNING", "RootDetect", f"Plusieurs {label} roots détectés ({len(candidates)}). Sélection manuelle possible.")

    def auto_detect_scene_roots(self) -> None:
        high_candidates = self._find_root_candidates("high")
        placeholder_candidates = self._find_root_candidates("placeholder")

        self.detected_roots["high"] = high_candidates
        self.detected_roots["placeholder"] = placeholder_candidates
        self.refresh_root_ui()

        if high_candidates:
            self.log(
                "INFO",
                "RootDetect",
                f"High root détecté: {self._ellipsize_middle(high_candidates[0], max_length=MAX_UI_TEXT_LENGTH - 22)}",
                [high_candidates[0]],
            )
            if len(high_candidates) > 1:
                self.log("WARNING", "RootDetect", f"Plusieurs High roots détectés ({len(high_candidates)}). Sélection manuelle possible.")
        else:
            self.log("WARNING", "RootDetect", "High root non détecté.")

        if placeholder_candidates:
            self.log(
                "INFO",
                "RootDetect",
                f"Placeholder root détecté: {self._ellipsize_middle(placeholder_candidates[0], max_length=MAX_UI_TEXT_LENGTH - 29)}",
                [placeholder_candidates[0]],
            )
            if len(placeholder_candidates) > 1:
                self.log("WARNING", "RootDetect", f"Plusieurs Placeholder roots détectés ({len(placeholder_candidates)}). Sélection manuelle possible.")
        else:
            self.log("WARNING", "RootDetect", "Placeholder root non détecté.")

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

        return sorted(list(set(transforms)))

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
        return parts[-1] if parts else name

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

        shape = shape[0]
        uv_sets = cmds.polyUVSet(shape, query=True, allUVSets=True) or []
        uv_info: Dict[str, Dict[str, int]] = {}
        current_uv = cmds.polyUVSet(shape, query=True, currentUVSet=True) or []
        original_uv = current_uv[0] if current_uv else None

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
            uv_info[uv_set] = {"count": uv_count, "shells": shell_count}

        if original_uv:
            try:
                cmds.polyUVSet(shape, currentUVSet=True, uvSet=original_uv)
            except RuntimeError:
                pass

        return {
            "path": mesh_transform,
            "key": self._normalized_relative_mesh_key(mesh_transform, root),
            "v": int(cmds.polyEvaluate(shape, vertex=True) or 0),
            "e": int(cmds.polyEvaluate(shape, edge=True) or 0),
            "f": int(cmds.polyEvaluate(shape, face=True) or 0),
            "uv_total": int(cmds.polyEvaluate(shape, uvcoord=True) or 0),
            "uv_sets": uv_info,
            "parent_path": "/".join(self._normalized_segments(mesh_transform)[:-1]),
            "pivot_world": tuple(cmds.xform(mesh_transform, q=True, ws=True, rotatePivot=True)),
            "translate_world": tuple(cmds.xform(mesh_transform, q=True, ws=True, translation=True)),
        }

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
        if scope_key == "high_fbx":
            namespace = self.context["fbx_namespace"]
        elif scope_key == "high_ma":
            namespace = self.context["ma_namespace"]
        elif scope_key == "bake_high":
            namespace = self.context["bake_ma_namespace"]

        if scope_key == "placeholder":
            placeholder_root = self.get_placeholder_root()
            if placeholder_root and cmds.objExists(placeholder_root):
                return [placeholder_root]

        for mesh in scope_meshes:
            if not cmds.objExists(mesh):
                continue
            root = self._find_namespace_root_for_node(mesh, namespace) if namespace else None
            if not root:
                ancestors = self._path_ancestors(mesh)
                root = ancestors[0] if ancestors else None
            if root and cmds.objExists(root):
                roots.append(root)
        return sorted(set(roots))

    def _resolve_texture_scope_roots(self, resolution: Dict[str, Any]) -> Dict[str, Any]:
        scope_keys = resolution.get("scope_keys", [])
        per_scope = resolution.get("per_scope_meshes", {})
        all_scope_keys = ["placeholder", "high_ma", "high_fbx", "bake_high"]

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
        return sorted(set(transforms)), sorted(set(placeholder_excluded))

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
        allowed_namespaces = [self.context["fbx_namespace"], self.context["ma_namespace"]]
        for allowed in allowed_namespaces:
            if namespace == allowed or namespace.startswith(allowed + ":"):
                return True
        return False

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

    def _refresh_texture_sets_list_ui(self) -> None:
        if "texture_sets_list" not in self.ui:
            return
        previous_selection = self._selected_texture_set_names()
        self.texture_set_label_to_key = {}
        self.texture_set_section_headers = set()
        cmds.textScrollList(self.ui["texture_sets_list"], edit=True, removeAll=True)

        grouped_keys: Dict[str, List[str]] = {}
        source_order = ["high_ma", "high_fbx", "bake_high", "placeholder", "mixed", "unknown"]
        for set_key in sorted(self.detected_texture_sets.keys()):
            data = self.detected_texture_sets[set_key]
            sources = data.get("sources", []) or ["unknown"]
            source_key = "mixed" if len(sources) > 1 else sources[0]
            grouped_keys.setdefault(source_key, []).append(set_key)

        for source in source_order:
            set_keys = grouped_keys.get(source, [])
            if not set_keys:
                continue
            header = f"━━ {self.scope_labels.get(source, source.replace('_', ' ').title())} ━━"
            self.texture_set_section_headers.add(header)
            cmds.textScrollList(self.ui["texture_sets_list"], edit=True, append=header)
            for set_name in set_keys:
                data = self.detected_texture_sets[set_name]
                method = data.get("method", "unknown")
                count = len(data.get("objects", []))
                display_name = data.get("display_name", data.get("name", set_name))
                quad_count = int(data.get("quad_count", 0))
                percent_of_total = float(data.get("percent_of_total", 0.0))
                visible = self.texture_set_visibility.get(set_name, True)
                state = "Shown" if visible else "Hidden"
                label = f"  {display_name} - {quad_count} Quads - {percent_of_total:.1f}% | {method} | {count} obj(s) | {state}"
                unique_label = label
                duplicate_index = 2
                while unique_label in self.texture_set_label_to_key:
                    unique_label = f"{label} [{duplicate_index}]"
                    duplicate_index += 1
                self.texture_set_label_to_key[unique_label] = set_name
                cmds.textScrollList(self.ui["texture_sets_list"], edit=True, append=unique_label)
        self._restore_texture_set_selection(previous_selection)

    def _selected_texture_set_names(self) -> List[str]:
        selected = cmds.textScrollList(self.ui["texture_sets_list"], query=True, selectItem=True) or []
        names: List[str] = []
        for label in selected:
            if label in self.texture_set_section_headers:
                continue
            set_name = self.texture_set_label_to_key.get(label)
            if set_name in self.detected_texture_sets:
                names.append(set_name)
        return names

    def _restore_texture_set_selection(self, set_names: List[str]) -> None:
        if not set_names:
            return
        labels_to_select = [label for label, set_name in self.texture_set_label_to_key.items() if set_name in set_names]
        if labels_to_select:
            cmds.textScrollList(self.ui["texture_sets_list"], edit=True, selectItem=labels_to_select)

    def on_texture_set_selection_changed(self) -> None:
        selected_names = self._selected_texture_set_names()
        objects: List[str] = []
        for set_name in selected_names:
            objects.extend(self.detected_texture_sets[set_name].get("objects", []))
        objects = sorted(set([o for o in objects if cmds.objExists(o)]))
        if objects:
            cmds.select(objects, replace=True)

    def set_texture_set_visibility(self, visible: bool, selected_only: bool = False) -> None:
        target_sets = self._selected_texture_set_names() if selected_only else list(self.detected_texture_sets.keys())
        if not target_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set sélectionné.")
            return
        impacted_objects: List[str] = []
        for set_name in target_sets:
            objs = self.detected_texture_sets[set_name].get("objects", [])
            for obj in objs:
                if cmds.objExists(obj):
                    try:
                        cmds.setAttr(obj + ".visibility", visible)
                        impacted_objects.append(obj)
                    except RuntimeError:
                        pass
            self.texture_set_visibility[set_name] = visible
        self._refresh_texture_sets_list_ui()
        if selected_only:
            self._restore_texture_set_selection(target_sets)
        action = "affichés" if visible else "masqués"
        scope_label = self._scope_label(self.last_texture_scope) if self.last_texture_scope else "N/A"
        self.log("INFO", "TextureSets", f"Texture sets {action}: {', '.join(target_sets)} (scope source: {scope_label})", list(sorted(set(impacted_objects)))[:150])

    def toggle_selected_texture_sets(self) -> None:
        target_sets = self._selected_texture_set_names()
        if not target_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set sélectionné pour toggle.")
            return
        impacted_objects: List[str] = []
        for set_name in target_sets:
            current = self.texture_set_visibility.get(set_name, True)
            new_state = not current
            objs = self.detected_texture_sets[set_name].get("objects", [])
            for obj in objs:
                if cmds.objExists(obj):
                    try:
                        cmds.setAttr(obj + ".visibility", new_state)
                        impacted_objects.append(obj)
                    except RuntimeError:
                        pass
            self.texture_set_visibility[set_name] = new_state
        self._refresh_texture_sets_list_ui()
        self._restore_texture_set_selection(target_sets)
        self.log("INFO", "TextureSets", f"Toggle visibility appliqué à: {', '.join(target_sets)}", list(sorted(set(impacted_objects)))[:150])

    def isolate_selected_texture_sets(self) -> None:
        target_sets = self._selected_texture_set_names()
        if not target_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set sélectionné pour isolation.")
            return
        scene_transforms = cmds.ls(type="transform", long=True) or []
        default_camera_transforms = set(cmds.listRelatives(cmds.ls(type="camera") or [], parent=True, fullPath=True) or [])
        all_sets = list(self.detected_texture_sets.keys())
        hidden_objects: List[str] = []
        shown_objects: List[str] = []
        selected_objects: Set[str] = set()
        for set_name in all_sets:
            visible = set_name in target_sets
            objs = self.detected_texture_sets[set_name].get("objects", [])
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

        self._refresh_texture_sets_list_ui()
        self._restore_texture_set_selection(target_sets)
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
        if not self.detected_texture_sets:
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
        path = self.paths.get("ma", "")
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
        self.paths["ma"] = path
        self.log("INFO", "File", f"MA référencé sous namespace '{namespace}' ({len(self.context['ma_meshes'])} meshes détectés).")
        self._detect_and_store_roots_for_import("high_ma")
        self._log_root_detection("high", "High")
        self._log_root_detection("placeholder", "Placeholder")
        self.auto_detect_scene_roots()

    def load_fbx_into_scene(self) -> None:
        path = self.paths.get("fbx", "")
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

        self.paths["fbx"] = path
        self.log("INFO", "FBX", f"FBX référencé sous namespace '{namespace}' ({len(self.context['fbx_meshes'])} meshes détectés).")
        self._detect_and_store_roots_for_import("high_fbx")
        self._log_root_detection("high", "High")

    def load_low_fbx_scene(self) -> None:
        self._reference_fbx_file("low_fbx", "low_fbx_namespace", "Low FBX")

    def load_bake_ma_scene(self) -> None:
        self._reference_ma_file("bake_ma", "bake_ma_namespace", "Bake MA")

    def load_final_asset_ma_scene(self) -> None:
        self._reference_ma_file("final_asset_ma", "final_asset_ma_namespace", "Final Asset MA")

    def load_final_asset_fbx_scene(self) -> None:
        self._reference_fbx_file("final_asset_fbx", "final_asset_fbx_namespace", "Final Asset FBX")

    def _compare_mesh_sets(self, left_meshes: List[str], right_meshes: List[str], left_label: str, right_label: str) -> bool:
        left_by_key = {self._normalized_relative_mesh_key(m): self._mesh_data_signature(m) for m in left_meshes}
        right_by_key = {self._normalized_relative_mesh_key(m): self._mesh_data_signature(m) for m in right_meshes}
        left_keys = set(left_by_key.keys())
        right_keys = set(right_by_key.keys())
        missing_in_right = sorted(left_keys - right_keys)
        missing_in_left = sorted(right_keys - left_keys)
        topo_mismatch = []
        uv_mismatch = []

        for key in sorted(left_keys & right_keys):
            left_data = left_by_key[key]
            right_data = right_by_key[key]
            if (left_data["v"], left_data["e"], left_data["f"]) != (right_data["v"], right_data["e"], right_data["f"]):
                topo_mismatch.append(key)
            if left_data["uv_total"] != right_data["uv_total"] or left_data["uv_sets"] != right_data["uv_sets"]:
                uv_mismatch.append(key)

        if not missing_in_right and not missing_in_left and not topo_mismatch and not uv_mismatch:
            self.log("INFO", "Compare", f"OK: {left_label} et {right_label} sont cohérents.")
            return True

        self.log("WARNING", "Compare", f"Incohérences détectées entre {left_label} et {right_label}.")
        if missing_in_right:
            self.log("FAIL", "Compare", f"Présents dans {left_label} mais absents de {right_label}: {len(missing_in_right)}", [left_by_key[k]["path"] for k in missing_in_right][:150])
        if missing_in_left:
            self.log("FAIL", "Compare", f"Présents dans {right_label} mais absents de {left_label}: {len(missing_in_left)}", [right_by_key[k]["path"] for k in missing_in_left][:150])
        if topo_mismatch:
            self.log("FAIL", "Compare", f"Topologie différente: {len(topo_mismatch)}", [left_by_key[k]["path"] for k in topo_mismatch][:150])
        if uv_mismatch:
            self.log("FAIL", "Compare", f"UV différentes: {len(uv_mismatch)}", [left_by_key[k]["path"] for k in uv_mismatch][:150])
        return False

    def compare_ma_vs_fbx(self) -> None:
        self.log("INFO", "Compare", "----- Run Compare MA vs FBX vs BakeScene -----")
        per_scope: Dict[str, List[str]] = {}
        for key, label in self._high_scope_sequence():
            resolution = self.resolve_scope_targets(scope_keys=[key])
            meshes = resolution["per_scope_meshes"].get(key, [])
            per_scope[key] = meshes
            self.log("INFO", "Compare", f"━━ Source: {label} ━━")
            self.log("INFO", "Compare", f"Meshes détectés: {len(meshes)}")
            if not meshes:
                self.log("FAIL", "Compare", f"Aucun mesh trouvé pour {label}.")

        missing_sources = [k for k, _ in self._high_scope_sequence() if not per_scope.get(k)]
        if missing_sources:
            self.set_check_status("ma_fbx_compared", "FAIL")
            return

        all_ok = True
        pairs = [("high_ma", "high_fbx"), ("high_ma", "bake_high"), ("high_fbx", "bake_high")]
        for left_key, right_key in pairs:
            left_label = self.scope_labels.get(left_key, left_key)
            right_label = self.scope_labels.get(right_key, right_key)
            self.log("INFO", "Compare", f"━━ Compare: {left_label} vs {right_label} ━━")
            ok = self._compare_mesh_sets(per_scope[left_key], per_scope[right_key], left_label, right_label)
            all_ok = all_ok and ok

        self.set_check_status("ma_fbx_compared", "OK" if all_ok else "FAIL")

    def scan_namespaces(self) -> None:
        user_ns = self._get_scan_namespaces()
        self.last_scanned_namespaces = user_ns[:]

        if not user_ns:
            self.log("INFO", "Namespace", "Aucun namespace indésirable détecté (High_FBX_File/High_Ma_File ignorés volontairement).")
            self.set_check_status("no_namespaces", "OK")
            return

        total_objs: List[str] = []
        for ns in user_ns:
            objs = cmds.ls(ns + ":*", long=True) or []
            if not objs:
                objs = [n for n in (cmds.ls(long=True) or []) if any(seg.startswith(ns + ":") for seg in n.split("|") if seg)]
            total_objs.extend(objs)
            self.log("WARNING", "Namespace", f"Namespace détecté: {ns} ({len(objs)} objets)", objs[:50])

        self.log("FAIL", "Namespace", f"{len(user_ns)} namespace(s) utilisateur détecté(s).", total_objs[:200])
        self.set_check_status("no_namespaces", "FAIL")

    def remove_namespaces(self) -> None:
        removable = self.last_scanned_namespaces[:] or self._get_scan_namespaces()
        removable = [ns for ns in removable if not self._is_allowed_namespace(ns)]
        if not removable:
            self.log("INFO", "Namespace", "Aucun namespace à supprimer (High_FBX_File/High_Ma_File préservés).")
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
            self.set_check_status("no_namespaces", "FAIL")
        else:
            self.log("INFO", "Namespace", "Suppression des namespaces indésirables terminée (High_FBX_File/High_Ma_File conservés).")
            self.set_check_status("no_namespaces", "OK")
        self.last_scanned_namespaces = self._get_scan_namespaces()

    def check_placeholder_match(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        if scope_keys is None:
            statuses: List[str] = []
            self.log("INFO", "Placeholder", "----- Placeholder Match (ordre: MA -> FBX -> Bake) -----")
            for key, label in self._high_scope_sequence():
                self.log("INFO", "Placeholder", f"━━ Étape: {label} vs placeholder ━━")
                self.check_placeholder_match(scope_keys=[key], source_label=label)
                statuses.append(self.check_states["placeholder_checked"]["status"])
            final = "OK" if all(s == "OK" for s in statuses) else "FAIL"
            self.set_check_status("placeholder_checked", final)
            return
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        scope_keys = resolution["scope_keys"]
        self._log_scope_resolution("Placeholder", resolution)
        placeholder = self.get_placeholder_root()
        if not placeholder or not cmds.objExists(placeholder):
            self.log("FAIL", "Placeholder", "Placeholder root invalide/non détecté.")
            self.set_check_status("placeholder_checked", "FAIL")
            return

        per_scope = resolution["per_scope_meshes"]
        target_scope_keys = [k for k in scope_keys if k != "placeholder"]
        target_meshes = sorted(set([m for k in target_scope_keys for m in per_scope.get(k, [])]))
        if not target_meshes:
            self.log("FAIL", "Placeholder", f"Aucune cible High trouvée pour {source_label or self._scope_label(scope_keys)}.")
            self.set_check_status("placeholder_checked", "FAIL")
            return

        p_bb = cmds.exactWorldBoundingBox(placeholder)
        h_bb = cmds.exactWorldBoundingBox(target_meshes)
        p_dim = (p_bb[3] - p_bb[0], p_bb[4] - p_bb[1], p_bb[5] - p_bb[2])
        h_dim = (h_bb[3] - h_bb[0], h_bb[4] - h_bb[1], h_bb[5] - h_bb[2])
        p_piv = tuple(cmds.xform(placeholder, q=True, ws=True, rotatePivot=True))
        h_piv = self._bbox_center(h_bb)
        pivot_delta = tuple(h_piv[i] - p_piv[i] for i in range(3))

        ratio = tuple((h_dim[i] / p_dim[i]) if p_dim[i] else 0.0 for i in range(3))

        tolerance_percent = cmds.floatField(self.ui["placeholder_tolerance"], q=True, value=True) if "placeholder_tolerance" in self.ui else 7.0
        tolerance_percent = max(0.0, float(tolerance_percent))
        tolerance = tolerance_percent / 100.0
        axis_names = ["X", "Y", "Z"]
        axis_deviation_percent = [self._placeholder_axis_deviation(r) for r in ratio]
        max_deviation = max(axis_deviation_percent) if axis_deviation_percent else 0.0
        mean_deviation = (sum(axis_deviation_percent) / float(len(axis_deviation_percent))) if axis_deviation_percent else 0.0
        total_dims = max(sum(abs(v) for v in p_dim), 1e-6)
        weighted_deviation = sum(axis_deviation_percent[i] * (abs(p_dim[i]) / total_dims) for i in range(3))
        max_pivot_delta = max(abs(v) for v in pivot_delta)
        pivot_info_threshold = max(max(abs(v) for v in p_dim), 1e-6) * tolerance
        pivot_ok = max_pivot_delta <= pivot_info_threshold
        dimensions_ok = all(abs(r - 1.0) <= tolerance for r in ratio if r != 0.0)

        self.log("INFO", "Placeholder", "----- Placeholder Match -----")
        self.log("INFO", "Placeholder", f"Source analysée: {source_label or self._scope_label(scope_keys)}")
        self.log("INFO", "Placeholder", "Dimensions / proportions")
        self.log("INFO", "Placeholder", f"Placeholder dims: {self._fmt_vec(p_dim)}")
        self.log("INFO", "Placeholder", f"High dims: {self._fmt_vec(h_dim)}")
        for idx, axis in enumerate(axis_names):
            self.log(
                "INFO",
                "Placeholder",
                f"Ratio axe {axis}: {ratio[idx]:.4f} ({self._fmt_size_percent(ratio[idx])})",
            )
            self.log("INFO", "Placeholder", f"Écart axe {axis}: {axis_deviation_percent[idx]:.2f}%")
        self.log("INFO", "Placeholder", f"Écart maximal: {max_deviation:.2f}%")
        self.log("INFO", "Placeholder", f"Écart moyen: {mean_deviation:.2f}%")
        self.log("INFO", "Placeholder", f"Écart pondéré (dimensions): {weighted_deviation:.2f}%")
        self.log("INFO", "Placeholder", f"Seuil autorisé: {tolerance_percent:.2f}%")
        self.log("INFO", "Placeholder", "Critère principal (validation): Écart maximal par axe <= seuil.")
        self.log("INFO", "Placeholder", f"Décision proportions: {'OK' if dimensions_ok else 'FAIL'}")

        self.log("INFO", "Placeholder", "Pivot / position")
        self.log("INFO", "Placeholder", f"Pivot placeholder: {self._fmt_vec(p_piv)}")
        self.log("INFO", "Placeholder", f"Pivot high (centre bbox scope): {self._fmt_vec(h_piv)}")
        self.log("INFO", "Placeholder", f"Pivot delta: {self._fmt_vec(pivot_delta)}")
        self.log(
            "INFO",
            "Placeholder",
            (
                f"Décision pivot: {'OK' if pivot_ok else 'FAIL'} "
                f"(informatif, seuil={pivot_info_threshold:.4f}, max delta={max_pivot_delta:.4f})"
            ),
        )

        if dimensions_ok:
            self.log("INFO", "Placeholder", "Résultat final: OK (proportions validées).")
            self.set_check_status("placeholder_checked", "OK")
        else:
            worst_axis_idx = axis_deviation_percent.index(max_deviation) if axis_deviation_percent else 1
            reason = (
                f"Résultat final: FAIL | raison principale: l'axe {axis_names[worst_axis_idx]} "
                f"dépasse le seuil ({max_deviation:.2f}% > {tolerance_percent:.2f}%)."
            )
            self.log("WARNING", "Placeholder", reason, [placeholder] + target_meshes[:150])
            self.set_check_status("placeholder_checked", "FAIL")

    def run_topology_checks(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        if scope_keys is None:
            statuses: List[str] = []
            self.log("INFO", "Topology", "----- Run Topology (ordre: MA -> FBX -> Bake) -----")
            for key, label in self._high_scope_sequence():
                self.log("INFO", "Topology", f"━━ Étape: {label} ━━")
                self.run_topology_checks(scope_keys=[key], source_label=label)
                statuses.append(self.check_states["topology_checked"]["status"])
            final = "OK" if all(s == "OK" for s in statuses) else ("FAIL" if any(s == "FAIL" for s in statuses) else "PENDING")
            self.set_check_status("topology_checked", final)
            return
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        scope_keys = resolution["scope_keys"]
        meshes = resolution["meshes"]
        self._log_scope_resolution("Topology", resolution)
        if not meshes:
            self.log("FAIL", "Topology", f"Aucun objet trouvé pour {source_label or self._scope_label(scope_keys)}.")
            self.set_check_status("topology_checked", "FAIL")
            return

        self.log("INFO", "Topology", f"Source analysée: {source_label or self._scope_label(scope_keys)} | Meshes: {len(meshes)}")

        fail_count = 0
        warn_count = 0

        non_manifold_items = []
        lamina_items = []
        ngon_faces = []
        zero_length_edges = []
        zero_area_faces = []
        hidden_meshes = []
        meshes_with_history = []
        non_identity = []
        instances = []

        for m in meshes:
            nmv = cmds.polyInfo(m, nonManifoldVertices=True) or []
            nme = cmds.polyInfo(m, nonManifoldEdges=True) or []
            lam = cmds.polyInfo(m, laminaFaces=True) or []

            if nmv or nme:
                non_manifold_items.append(m)
            if lam:
                lamina_items.append(m)

            face_count = cmds.polyEvaluate(m, face=True) or 0
            for face_idx in range(face_count):
                vtx = cmds.polyInfo(f"{m}.f[{face_idx}]", faceToVertex=True) or []
                if not vtx:
                    continue
                # "FACE    0:    10 11 12 13" -> keep numeric tokens only.
                tokens = [tok for tok in vtx[0].replace(":", " ").split() if tok.isdigit()]
                if len(tokens) > 5:  # first numeric token is face id
                    ngon_faces.append(f"{m}.f[{face_idx}]")

            edge_count = cmds.polyEvaluate(m, edge=True) or 0
            for edge_idx in range(edge_count):
                edge_comp = f"{m}.e[{edge_idx}]"
                edge_info = cmds.polyInfo(edge_comp, edgeToVertex=True) or []
                if not edge_info:
                    continue
                # "EDGE   1:   3 7"
                verts = [tok for tok in edge_info[0].replace(":", " ").split() if tok.isdigit()]
                if len(verts) < 3:
                    continue
                v1 = f"{m}.vtx[{verts[-2]}]"
                v2 = f"{m}.vtx[{verts[-1]}]"
                p1 = cmds.pointPosition(v1, world=True)
                p2 = cmds.pointPosition(v2, world=True)
                length_sq = sum((p1[i] - p2[i]) ** 2 for i in range(3))
                if length_sq <= 1e-12:
                    zero_length_edges.append(edge_comp)

            face_area = cmds.polyEvaluate(f"{m}.f[*]", area=True) or 0.0
            if isinstance(face_area, list):
                for idx, area in enumerate(face_area):
                    if area <= 1e-12:
                        zero_area_faces.append(f"{m}.f[{idx}]")
            elif face_area <= 1e-12 and face_count > 0:
                # fallback when Maya returns one total area value
                zero_area_faces.extend([f"{m}.f[{i}]" for i in range(face_count)])

            if not cmds.getAttr(m + ".visibility"):
                hidden_meshes.append(m)

            hist = cmds.listHistory(m, pruneDagObjects=True) or []
            hist = [h for h in hist if cmds.nodeType(h) not in ("transform", "mesh", "groupId", "shadingEngine")]
            if hist:
                meshes_with_history.append(m)

            t = cmds.xform(m, q=True, os=True, translation=True)
            r = cmds.xform(m, q=True, os=True, rotation=True)
            s = cmds.xform(m, q=True, r=True, scale=True)
            if any(abs(v) > 1e-4 for v in (t + r)) or any(abs(v - 1.0) > 1e-4 for v in s):
                non_identity.append(m)

            shape = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
            if shape:
                parents = cmds.listRelatives(shape[0], allParents=True, fullPath=True) or []
                if len(parents) > 1:
                    instances.append(m)

        if ngon_faces:
            self.log("FAIL", "Topology", f"Faces avec plus de 4 côtés: {len(ngon_faces)}", ngon_faces[:200])
            fail_count += 1
        if lamina_items:
            self.log("FAIL", "Topology", f"Lamina faces détectées sur {len(lamina_items)} mesh(es).", lamina_items)
            fail_count += 1
        if non_manifold_items:
            self.log("FAIL", "Topology", f"Non-manifold détecté sur {len(non_manifold_items)} mesh(es).", non_manifold_items)
            fail_count += 1
        if zero_length_edges:
            self.log("FAIL", "Topology", f"Edges de longueur nulle détectées: {len(zero_length_edges)}", zero_length_edges[:200])
            fail_count += 1
        if zero_area_faces:
            self.log("FAIL", "Topology", f"Faces avec aire nulle détectées: {len(zero_area_faces)}", zero_area_faces[:200])
            fail_count += 1
        if meshes_with_history:
            self.log("WARNING", "Topology", f"Historique non supprimé sur {len(meshes_with_history)} mesh(es).", meshes_with_history)
            warn_count += 1
        if non_identity:
            self.log("WARNING", "Topology", f"Transforms non gelées/non identitaires sur {len(non_identity)} mesh(es).", non_identity)
            warn_count += 1
        if hidden_meshes:
            self.log("WARNING", "Topology", f"Géométrie cachée détectée: {len(hidden_meshes)} mesh(es).", hidden_meshes)
            warn_count += 1
        if instances:
            self.log("WARNING", "Topology", f"Instances détectées: {len(set(instances))} mesh(es).", list(set(instances)))
            warn_count += 1

        high_root = self.get_high_root()
        if high_root and "high_ma" in scope_keys:
            descendants = cmds.listRelatives(high_root, allDescendents=True, fullPath=True) or []
            non_mesh_desc = [d for d in descendants if cmds.nodeType(d) not in ("transform", "mesh")]
            if non_mesh_desc:
                self.log("INFO", "Topology", f"Objets non mesh sous High root: {len(non_mesh_desc)}", non_mesh_desc[:80])

            empty_transforms = []
            for tr in (cmds.listRelatives(high_root, allDescendents=True, fullPath=True, type="transform") or []):
                children = cmds.listRelatives(tr, children=True, fullPath=True) or []
                if not children:
                    empty_transforms.append(tr)
            if empty_transforms:
                self.log("WARNING", "Topology", f"Transforms vides détectées: {len(empty_transforms)}", empty_transforms[:80])
                warn_count += 1

        if fail_count == 0 and warn_count == 0:
            self.log("INFO", "Topology", "Aucun problème topologique majeur détecté.")
            self.set_check_status("topology_checked", "OK")
        elif fail_count == 0:
            self.log("WARNING", "Topology", "Checks topologie terminés avec warnings.")
            self.set_check_status("topology_checked", "PENDING")
        else:
            self.set_check_status("topology_checked", "FAIL")

    def analyze_texture_sets(self, mode: str = "materials", scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        if scope_keys is None:
            statuses: List[str] = []
            self.log("INFO", "TextureSets", "----- Run Texture Sets (ordre: MA -> FBX -> Bake) -----")
            for key, label in self._high_scope_sequence():
                self.log("INFO", "TextureSets", f"━━ Étape: {label} ━━")
                self.analyze_texture_sets(mode=mode, scope_keys=[key], source_label=label)
                statuses.append(self.check_states["texture_sets_analyzed"]["status"])
            final = "OK" if all(s == "OK" for s in statuses) else ("FAIL" if any(s == "FAIL" for s in statuses) else "PENDING")
            self.set_check_status("texture_sets_analyzed", final)
            return
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        scope_keys = resolution["scope_keys"]
        meshes = resolution["meshes"]
        per_scope_meshes = resolution["per_scope_meshes"]
        texture_scope_roots = self._resolve_texture_scope_roots(resolution)
        analysis_roots = texture_scope_roots["included_roots"]
        primary_root = texture_scope_roots["primary_root"]
        self._log_scope_resolution("TextureSets", resolution)
        if not meshes:
            self.log("FAIL", "TextureSets", f"Aucun objet trouvé pour {source_label or self._scope_label(scope_keys)}.")
            self.set_check_status("texture_sets_analyzed", "FAIL")
            return
        self.log("INFO", "TextureSets", f"Source analysée: {source_label or self._scope_label(scope_keys)}")
        self.log("INFO", "TextureSets", "Root(s) résolus pour Texture Sets :")
        if analysis_roots:
            for root in analysis_roots:
                self.log("INFO", "TextureSets", f"- {self._short_name(root)}")
        else:
            self.log("WARNING", "TextureSets", "- Aucun root explicite résolu pour le scope actif.")

        excluded_roots = texture_scope_roots.get("excluded_roots", {})
        excluded_lines: List[str] = []
        for key in ["placeholder", "high_ma", "high_fbx", "bake_high"]:
            for root in excluded_roots.get(key, []):
                reason = "hors scope"
                if key == "placeholder":
                    reason = "placeholder / hors scope"
                excluded_lines.append(f"- {self._short_name(root)} ({reason})")
        if excluded_lines:
            self.log("INFO", "TextureSets", "Root(s) exclus :")
            for line in excluded_lines:
                self.log("INFO", "TextureSets", line)

        detected: Dict[str, Dict[str, object]] = {}
        mode = (mode or "materials").lower().strip()
        include_material = mode in {"material", "materials"}
        include_groups = mode in {"groups", "group"}
        mat_to_meshes: Dict[str, List[str]] = {}
        if include_material:
            for m in meshes:
                shapes = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
                if not shapes:
                    continue
                shape = shapes[0]

                sgs = cmds.listConnections(shape, type="shadingEngine") or []
                if not sgs:
                    mat_to_meshes.setdefault("<NO_MATERIAL>", []).append(m)
                    continue

                mats_for_mesh = set()
                for sg in sgs:
                    mats = cmds.listConnections(sg + ".surfaceShader") or []
                    if mats:
                        mats_for_mesh.update(mats)
                    else:
                        mats_for_mesh.add("<UNBOUND_SURFACESHADER>")

                for mat in mats_for_mesh:
                    mat_to_meshes.setdefault(mat, []).append(m)

            for mat, mat_meshes in mat_to_meshes.items():
                detected[f"MAT::{mat}"] = {
                    "name": mat,
                    "display_name": self._strip_namespaces_from_name(mat),
                    "method": "material",
                    "objects": sorted(set(mat_meshes)),
                }

        group_method_log_lines: List[str] = []
        if include_groups:
            if mode in {"groups", "group"}:
                group_sets, group_method_log_lines = self._compute_root_children_texture_sets(analysis_roots, meshes)
                detected.update(group_sets)
            else:
                direct_children = [m for m in meshes if cmds.listRelatives(m, parent=True, fullPath=True)]
                grouped: Dict[str, List[str]] = {}
                for mesh in direct_children:
                    parent = cmds.listRelatives(mesh, parent=True, fullPath=True) or []
                    if not parent:
                        continue
                    grouped.setdefault(parent[0], []).append(mesh)
                for child, child_meshes in grouped.items():
                    if child_meshes:
                        key = f"GRP::{self._short_name(child)}"
                        display_name = self._clean_texture_set_display_name(self._short_name(child), primary_root)
                        detected[key] = {
                            "name": self._strip_namespaces_from_name(self._short_name(child)),
                            "display_name": display_name,
                            "method": "group",
                            "objects": sorted(set(child_meshes)),
                        }

        total_quads = 0
        mesh_quad_cache: Dict[str, Tuple[int, int]] = {}
        for mesh in meshes:
            quad_count, _ = self._mesh_quad_and_face_count(mesh)
            mesh_quad_cache[mesh] = (quad_count, 0)
            total_quads += quad_count

        for set_key, data in detected.items():
            unique_meshes = sorted(set(data.get("objects", [])))
            set_quads = sum(mesh_quad_cache.get(mesh, (0, 0))[0] for mesh in unique_meshes)
            percentage = (float(set_quads) / float(total_quads) * 100.0) if total_quads else 0.0
            data["quad_count"] = int(set_quads)
            data["percent_of_total"] = percentage
            data["objects"] = unique_meshes
            data["sources"] = self._infer_set_sources(unique_meshes, per_scope_meshes)

        self.detected_texture_sets = detected
        self.last_texture_scope = scope_keys[:]
        self.texture_set_visibility = {k: self.texture_set_visibility.get(k, True) for k in self.detected_texture_sets.keys()}
        for set_key in self.detected_texture_sets:
            self.texture_set_visibility.setdefault(set_key, True)
        self._refresh_texture_sets_list_ui()

        mode_label = {"groups": "groupes", "group": "groupes", "material": "matériaux", "materials": "matériaux"}.get(mode, mode)
        if group_method_log_lines:
            for line in group_method_log_lines:
                self.log("INFO", "TextureSets", line)
        if mode in {"groups", "group"}:
            cleaned_names = [
                data.get("display_name", data.get("name", set_key))
                for set_key, data in sorted(self.detected_texture_sets.items())
            ]
            self.log("INFO", "TextureSets", f"Nombre de texture sets détectés (1er niveau): {len(cleaned_names)}")
            if cleaned_names:
                self.log("INFO", "TextureSets", f"Texture sets lisibles: {', '.join(cleaned_names)}")
        self.log("INFO", "TextureSets", f"Texture sets détectés ({mode_label}): {len(self.detected_texture_sets)}")
        self.log("INFO", "TextureSets", f"Total High root: {total_quads} quads")
        for set_key in sorted(self.detected_texture_sets.keys()):
            data = self.detected_texture_sets[set_key]
            objs = data.get("objects", [])
            display_name = data.get("display_name", data.get("name", set_key))
            method = data.get("method", "unknown")
            quad_count = int(data.get("quad_count", 0))
            percent = float(data.get("percent_of_total", 0.0))
            self.log(
                "INFO",
                "TextureSets",
                f"{display_name} | méthode={method} | {quad_count} quads | {percent:.1f}% du High | {len(objs)} objet(s)",
                objs[:150],
            )

        if "<NO_MATERIAL>" in mat_to_meshes or "<UNBOUND_SURFACESHADER>" in mat_to_meshes:
            self.log("WARNING", "TextureSets", "Des meshes sans matériau valide ont été détectés.")
            self.set_check_status("texture_sets_analyzed", "PENDING")
        else:
            self.set_check_status("texture_sets_analyzed", "OK" if self.detected_texture_sets else "PENDING")
        if not self.detected_texture_sets:
            self.log("WARNING", "TextureSets", "Aucun texture set exploitable détecté via la méthode active.")
        else:
            self.log("INFO", "TextureSets", "Utilisez la liste et Hide/Show pour isoler visuellement chaque texture set.")

    def check_vertex_colors(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        if scope_keys is None:
            statuses: List[str] = []
            self.log("INFO", "VertexColor", "----- Run Vertex Colors (ordre: MA -> FBX -> Bake) -----")
            for key, label in self._high_scope_sequence():
                self.log("INFO", "VertexColor", f"━━ Étape: {label} ━━")
                self.check_vertex_colors(scope_keys=[key], source_label=label)
                statuses.append(self.check_states["vertex_colors_checked"]["status"])
            final = "OK" if all(s == "OK" for s in statuses) else "FAIL"
            self.set_check_status("vertex_colors_checked", final)
            return
        resolution = self.resolve_scope_targets(scope_keys=scope_keys)
        scope_keys = resolution["scope_keys"]
        meshes = resolution["meshes"]
        self._log_scope_resolution("VertexColor", resolution)
        if not meshes:
            self.log("FAIL", "VertexColor", f"Aucun objet trouvé pour {source_label or self._scope_label(scope_keys)}.")
            self.set_check_status("vertex_colors_checked", "FAIL")
            return
        self.log("INFO", "VertexColor", f"Source analysée: {source_label or self._scope_label(scope_keys)}")

        with_vc = []
        without_vc = []
        partial_missing: Dict[str, int] = {}

        for m in meshes:
            shapes = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                continue
            shape = shapes[0]
            color_sets = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            if color_sets:
                with_vc.append(m)
                face_count = int(cmds.polyEvaluate(shape, face=True) or 0)
                missing_faces = 0
                for face_idx in range(face_count):
                    face_comp = f"{shape}.f[{face_idx}]"
                    rgb = cmds.polyColorPerVertex(face_comp, query=True, rgb=True) or []
                    if not rgb:
                        missing_faces += 1
                if missing_faces > 0:
                    partial_missing[m] = missing_faces
            else:
                without_vc.append(m)

        self.log("INFO", "VertexColor", f"Meshes avec vertex colors: {len(with_vc)}", with_vc[:150])
        self.log("INFO", "VertexColor", f"Meshes sans vertex colors: {len(without_vc)}", without_vc[:150])

        if partial_missing:
            self.log("FAIL", "VertexColor", f"Faces sans vertex color détectées sur {len(partial_missing)} mesh(es).")
            for mesh, count in sorted(partial_missing.items())[:50]:
                self.log("INFO", "VertexColorDetail", f"{mesh}: {count} face(s) sans vertex color", [mesh])

        if without_vc:
            self.log("FAIL", "VertexColor", "Certains meshes n'ont pas de vertex color set.", without_vc)

        if without_vc or partial_missing:
            self.set_check_status("vertex_colors_checked", "FAIL")
        else:
            self.log("INFO", "VertexColor", "Tous les meshes analysés possèdent au moins un color set.")
            self.set_check_status("vertex_colors_checked", "OK")

    def display_vertex_colors(self) -> None:
        targets: List[str] = []
        for key, _ in self._high_scope_sequence():
            resolution = self.resolve_scope_targets(scope_keys=[key])
            targets.extend(resolution["meshes"])
        targets = sorted(set(targets))
        if not targets:
            self.log("WARNING", "VertexColor", "Aucun objet High MA/FBX/Bake trouvé. Action annulée.")
            return

        shown = []
        for tr in targets:
            shapes = cmds.listRelatives(tr, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            if not shapes:
                continue
            for shape in shapes:
                try:
                    cmds.setAttr(shape + ".displayColors", 1)
                    shown.append(tr)
                except RuntimeError:
                    continue

        cmds.polyOptions(colorShadedDisplay=True)
        self.log("INFO", "VertexColor", f"Display Vertex Color activé sur {len(set(shown))} objet(s) (High .ma + High .fbx + High _bake.ma).", list(sorted(set(shown)))[:150])

    def hide_vertex_colors(self) -> None:
        targets: List[str] = []
        for key, _ in self._high_scope_sequence():
            resolution = self.resolve_scope_targets(scope_keys=[key])
            targets.extend(resolution["meshes"])
        targets = sorted(set(targets))
        if not targets:
            self.log("WARNING", "VertexColor", "Aucun objet High MA/FBX/Bake trouvé. Action annulée.")
            return

        hidden = []
        for tr in targets:
            shapes = cmds.listRelatives(tr, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            if not shapes:
                continue
            for shape in shapes:
                try:
                    cmds.setAttr(shape + ".displayColors", 0)
                    hidden.append(tr)
                except RuntimeError:
                    continue

        self.log("INFO", "VertexColor", f"Hide Vertex Color appliqué sur {len(set(hidden))} objet(s) (High .ma + High .fbx + High _bake.ma).", list(sorted(set(hidden)))[:150])

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

    def run_all_checks(self) -> None:
        self.log("INFO", "RunAll", "Lancement des checks High Poly...")
        self.compare_ma_vs_fbx()
        self.scan_namespaces()
        self.check_placeholder_match()
        self.run_topology_checks()
        self.analyze_texture_sets(mode="materials")
        self.check_vertex_colors()
        self.log("INFO", "RunAll", "Checks High Poly terminés.")

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
        if self.paths.get("ma"):
            return os.path.splitext(os.path.basename(self.paths["ma"]))[0]
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
