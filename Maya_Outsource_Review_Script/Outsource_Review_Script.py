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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import maya.cmds as cmds
import maya.mel as mel


WINDOW_NAME = "highPolyReviewAssistantWin"
WINDOW_TITLE = "Outsource Review Script"
MAX_UI_TEXT_LENGTH = 90
MAX_MENU_LABEL_LENGTH = 72
ROOT_SUFFIXES = {
    "high": "_high",
    "low": "_low",
    "placeholder": "_placeholder",
}
PLACEHOLDER_TOKEN = "placeholder"
LOW_UV_DISTORTION_THRESHOLD = 1.6
LOW_MAP2_TARGET_TD = 20.48
LOW_MAP2_TOLERANCE = 0.50


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
            "high_ma": "",
            "high_fbx": "",
            "bake_ma": "",
            "low_fbx": "",
            "final_scene_ma": "",
        }

        self.detected_files: Dict[str, List[str]] = {
            "high_ma": [],
            "high_fbx": [],
            "bake_ma": [],
            "low_fbx": [],
            "final_scene_ma": [],
        }

        self.detected_roots: Dict[str, List[str]] = {
            "high": [],
            "placeholder": [],
            "low": [],
            "bake_high": [],
            "bake_low": [],
            "final_asset_ma": [],
        }

        self.context = {
            "fbx_namespace": "High_FBX_File",
            "ma_namespace": "High_Ma_File",
            "bake_ma_namespace": "Bake_MA_File",
            "low_fbx_namespace": "Low_FBX_File",
            "final_asset_ma_namespace": "Final_Asset_MA_File",
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
        }

        self.check_states = {
            "ma_fbx_compared": {"status": "PENDING", "mode": "AUTO"},
            "ma_bake_compared": {"status": "PENDING", "mode": "AUTO"},
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
        }

        self.check_ui_map = {
            "ma_fbx_compared": "check_ma_fbx",
            "ma_bake_compared": "check_ma_bake",
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
        }

        self.detected_texture_sets: Dict[str, Dict[str, object]] = {}
        self.material_sets_by_context: Dict[str, Dict[str, Dict[str, object]]] = {"high": {}, "low": {}}
        self.texture_set_visibility: Dict[str, bool] = {}
        self.texture_set_label_to_key_by_context: Dict[str, Dict[str, str]] = {"high": {}, "low": {}}
        self.texture_set_section_headers_by_context: Dict[str, Set[str]] = {"high": set(), "low": set()}
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
            "low_fbx": [],
            "bake_ma": [],
            "final_scene_ma": [],
        }
        self.manual_root_menu_sources: Dict[str, str] = {}
        self.manual_root_menu_values: Dict[str, List[str]] = {}
        self.manual_root_overrides: Dict[str, List[str]] = {}

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
        self.refresh_manual_root_menus()
        self.refresh_summary()
        self.refresh_checklist_ui()

    def _build_file_section(self) -> None:
        cmds.frameLayout(label="1) Root Folder", collapsable=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        self.ui["root_field"] = cmds.textFieldButtonGrp(
            label="Root Folder",
            buttonLabel="Browse",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.pick_root_folder(),
        )
        cmds.button(label="Scan Delivery Folder", height=30, command=lambda *_: self.scan_delivery_folder())
        cmds.button(
            label="Load Everything",
            height=30,
            command=lambda *_: self.load_everything()
        )

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_technical_checks_section(self) -> None:
        cmds.frameLayout(label="Review 01 — High.ma", collapsable=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.text(label="Guided review of the High.ma delivery.", align="left")
        cmds.separator(style="in")
        cmds.text(label="Step 01 — Placeholder Match", align="left")
        self._build_manual_root_selector("placeholder_high_root_menu", "Select High Root", "high_ma")
        self._build_manual_root_selector("placeholder_placeholder_root_menu", "Select Placeholder Root", "placeholder_ma")
        cmds.rowLayout(numberOfColumns=5, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 6), (5, "both", 2)])
        self.ui["check_placeholder"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Verify that each high matches its placeholder", align="left")
        cmds.button(label="Run Placeholder Check", height=26, command=lambda *_: self.check_placeholder_match())
        cmds.text(label="Tolerance %", align="right")
        self.ui["placeholder_tolerance"] = cmds.floatField(minValue=0.0, value=7.0, precision=2, step=0.25, width=70)
        cmds.setParent("..")
        cmds.separator(style="in")
        cmds.text(label="Step 02 — Design Kit Review (manual)", align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui["check_design"] = cmds.checkBox(
            label="",
            value=False,
            changeCommand=lambda *_: self.on_manual_design_toggle(),
        )
        cmds.text(label="Visually verify high(s) against the design kit.", align="left")
        cmds.button(label="Mark Step as Reviewed", height=26, command=lambda *_: self.mark_design_reviewed())
        cmds.setParent("..")
        cmds.separator(style="in")
        cmds.text(label="Step 03 — Topology Check", align="left")
        self._build_manual_root_selector("topology_high_root_menu", "Select High Root for Topology Check", "high_ma")
        self._build_check_row("check_topology", "Topology", self.run_topology_checks)
        cmds.separator(style="in")
        cmds.text(label="Step 04 — Vertex Colors", align="left")
        self._build_manual_root_selector("vertex_high_root_menu", "Select High Root for Vertex Color Check", "high_ma")
        cmds.rowLayout(
            numberOfColumns=5,
            adjustableColumn=2,
            columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)],
        )
        self.ui["check_vtx"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Vertex Colors", align="left")
        cmds.button(label="Run Vertex Color Check", height=26, command=lambda *_: self.check_vertex_colors())
        cmds.button(label="Display Vertex Color", height=26, command=lambda *_: self.display_vertex_colors())
        cmds.button(label="Hide Vertex Color", height=26, command=lambda *_: self.hide_vertex_colors())
        cmds.setParent("..")
        cmds.text(label="Manual note: confirm Color ID readability for future bake.", align="left")
        cmds.separator(style="in")
        cmds.text(label="Step 05 — Namespaces", align="left")
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_ns"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Only tool namespaces should remain", align="left")
        cmds.button(label="Scan Namespaces", height=26, command=lambda *_: self.scan_namespaces())
        cmds.button(label="Remove Invalid Namespaces", height=26, command=lambda *_: self.remove_namespaces())
        cmds.setParent("..")
        cmds.separator(style="in")
        cmds.text(label="Step 06 — Materials / Texture Sets", align="left")
        self._build_manual_root_selector("materials_high_root_menu", "Select High Root for Materials / Texture Sets", "high_ma")
        self._build_check_row("check_texturesets", "Analyze Materials", lambda: self.analyze_texture_sets(mode="materials"))
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
        self.ui["check_ma_fbx"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.button(label="Run Compare", height=26, command=lambda *_: self.compare_ma_vs_fbx())
        cmds.separator(style="in")
        cmds.text(label="Step 08 — Compare High.ma vs Bake Scene High", align="left")
        self._build_manual_root_selector("compare_bake_ma_root_menu", "Select High.ma Root", "high_ma")
        self._build_manual_root_selector("compare_bake_high_root_menu", "Select Bake High Root", "bake_high")
        self.ui["check_ma_bake"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.button(label="Run Compare Bake", height=26, command=lambda *_: self.compare_ma_vs_bake_high())
        cmds.setParent("..")
        cmds.setParent("..")
    def _build_guided_high_review_section(self) -> None:
        self._build_technical_checks_section()
        self._build_global_action_section()

    def _build_review_tabs_section(self) -> None:
        cmds.frameLayout(label="2) Guided Reviews", collapsable=False, marginWidth=8)
        tabs = cmds.tabLayout(innerMarginWidth=6, innerMarginHeight=6)

        high_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_high_review_section()
        cmds.setParent("..")

        low_tab = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
        self._build_guided_low_review_section()
        cmds.setParent("..")

        cmds.tabLayout(tabs, edit=True, tabLabel=((high_tab, "Review 01 — High"), (low_tab, "Review 02 — Low")))
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_guided_low_review_section(self) -> None:
        cmds.frameLayout(label="Review 02 — Low", collapsable=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.text(label="Guided review of the Low.fbx delivery.", align="left")
        cmds.separator(style="in")
        cmds.text(label="Step 01 — Topology Check", align="left")
        self._build_manual_root_selector("low_topology_root_menu", "Select Low Root for Topology Check", "low_fbx")
        self._build_check_row("check_low_topology", "Topology", self.run_low_topology_checks)
        cmds.separator(style="in")

        cmds.text(label="Step 02 — Namespaces", align="left")
        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_low_ns"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Only low review namespaces should remain", align="left")
        cmds.button(label="Run Namespace Check", height=26, command=lambda *_: self.scan_low_namespaces())
        cmds.button(label="Remove Invalid Namespaces", height=26, command=lambda *_: self.remove_low_namespaces())
        cmds.setParent("..")
        cmds.separator(style="in")

        cmds.text(label="Step 03 — Materials / Texture Sets", align="left")
        self._build_manual_root_selector("low_materials_root_menu", "Select Low Root for Materials / Texture Sets", "low_fbx")
        self._build_check_row("check_low_materials", "Analyze Materials", self.analyze_low_materials)
        self.ui["low_texture_sets_list"] = cmds.textScrollList(
            allowMultiSelection=True,
            height=130,
            selectCommand=lambda *_: self.on_texture_set_selection_changed("low"),
        )
        cmds.button(label="Isolate Material", height=26, command=lambda *_: self.toggle_isolate_selected_material("low"))
        cmds.separator(style="in")

        cmds.text(label="Step 04 — UV Check map1", align="left")
        self._build_manual_root_selector("low_uv1_root_menu", "Select Low Root for UV map1 Check", "low_fbx")
        self._build_check_row("check_low_uv_map1", "UV Map1 Check", self.run_low_uv_map1_check)
        cmds.separator(style="in")

        cmds.text(label="Step 05 — UV map2 / Texel Density", align="left")
        self._build_manual_root_selector("low_uv2_root_menu", "Select Low Root for UV map2 / TD Check", "low_fbx")
        self._build_check_row("check_low_uv_map2", "UV Map2 Check", self.run_low_map2_density_check)
        cmds.separator(style="in")

        cmds.text(label="Step 06 — Compare Low.fbx vs Bake Scene Low", align="left")
        self._build_manual_root_selector("compare_low_bake_low_root_menu", "Select Low.fbx Root", "low_fbx")
        self._build_manual_root_selector("compare_low_bake_bake_root_menu", "Select Bake Low Root", "bake_low")
        self.ui["check_low_bake"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.button(label="Run Compare Bake", height=26, command=lambda *_: self.compare_low_vs_bake_low())
        cmds.separator(style="in")

        cmds.text(label="Step 07 — Compare Low.fbx vs Final Scene Asset", align="left")
        self._build_manual_root_selector("compare_low_final_low_root_menu", "Select Low.fbx Root", "low_fbx")
        self._build_manual_root_selector("compare_low_final_final_root_menu", "Select Final Scene Root", "final_ma")
        self.ui["check_low_final"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.button(label="Run Compare Final Asset", height=26, command=lambda *_: self.compare_low_vs_final_asset())

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_check_row(self, check_key_ui: str, label: str, command) -> None:
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui[check_key_ui] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label=label, align="left")
        cmds.button(label=f"Run {label}", height=26, command=lambda *_: command())
        cmds.setParent("..")

    def _build_manual_root_selector(self, menu_key: str, label: str, source_key: str) -> None:
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        cmds.text(label=label, align="left")
        self.ui[menu_key] = cmds.optionMenu(changeCommand=lambda *_: self.on_manual_root_changed(menu_key))
        cmds.menuItem(label="-- Aucun root --", parent=self.ui[menu_key])
        cmds.button(label="Use Selection", height=24, command=lambda *_: self.set_manual_root_from_selection(menu_key))
        cmds.setParent("..")
        self.manual_root_menu_sources[menu_key] = source_key

    def _build_global_action_section(self) -> None:
        cmds.frameLayout(label="Actions", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        cmds.button(label="Run All High Steps", height=30, command=lambda *_: self.run_all_checks())
        cmds.button(label="Clear Results", height=30, command=lambda *_: self.clear_results())
        cmds.setParent("..")
        cmds.button(label="Save Review Report", height=30, command=lambda *_: self.save_report())

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

    def _basename_from_path(self, path: str) -> str:
        return os.path.basename(path) if path else "N/A"

    def _preview_list(self, items: List[str], max_items: int = 4) -> str:
        _ = max_items
        if not items:
            return "-"
        return ", ".join(items)

    def _log_step_header(self, step_number: int, title: str, category: str = "Step") -> None:
        self.log("INFO", category, f"-- Step {step_number:02d}: {title} --")

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

    def log(self, level: str, category: str, message: str, objects: Optional[List[str]] = None) -> None:
        issue = ReviewIssue(level=level, category=category, message=message, objects=objects or [])
        self.result_items.append(issue)

        prefix = {
            "INFO": "[INFO]",
            "WARNING": "[WARN]",
            "FAIL": "[FAIL]",
        }.get(level, "[INFO]")

        display = f"{prefix} {category}: {message}"
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
            self._log_step_header(2, "Design Kit Review", category="DesignKit")
            self.log("INFO", "DesignKit", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
            self.log("INFO", "DesignKit", "Résultat : Revue design kit marquée comme effectuée (manuel).")

    def mark_design_reviewed(self) -> None:
        self.log("INFO", "DesignKit", "Action: Mark Design Kit Reviewed")
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
            for key in ["final_asset_ma", "high_ma", "bake_ma", "low_fbx"]:
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
        self.material_sets_by_context = {"high": {}, "low": {}}
        self.texture_set_visibility = {}
        self._disable_material_isolation()
        self._refresh_texture_sets_list_ui("high")
        self._refresh_texture_sets_list_ui("low")
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
                elif name_lower.endswith(".ma"):
                    found_files["final_scene_ma"].append(full_path)

        for key in found_files:
            found_files[key].sort()

        for key, files in found_files.items():
            self.detected_files[key] = files

        # Toujours synchroniser les chemins utilisables par les loaders,
        # même si les optionMenu ne sont pas présents dans l'UI courante.
        for file_key in ["high_ma", "high_fbx", "bake_ma", "low_fbx", "final_scene_ma"]:
            files = self.detected_files[file_key]
            previous = self.paths.get(file_key, "")
            if previous and previous in files:
                self.paths[file_key] = previous
            elif files:
                self.paths[file_key] = files[0]
            else:
                self.paths[file_key] = ""

        for file_key in ["high_ma", "high_fbx", "bake_ma", "low_fbx", "final_scene_ma"]:
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
        return []

    def refresh_manual_root_menus(self) -> None:
        for menu_key, source_key in self.manual_root_menu_sources.items():
            menu = self.ui.get(menu_key)
            if not menu or not cmds.optionMenu(menu, exists=True):
                continue
            current = self.get_manual_selected_root(menu_key)
            overrides = [n for n in self.manual_root_overrides.get(menu_key, []) if cmds.objExists(n)]
            detected = [n for n in self._manual_root_candidates(source_key) if cmds.objExists(n)]
            values: List[str] = []
            for node in overrides + detected:
                if node not in values:
                    values.append(node)
            self.manual_root_overrides[menu_key] = overrides
            self.manual_root_menu_values[menu_key] = values
            self._clear_option_menu(menu)
            if not values:
                cmds.menuItem(label="-- Aucun root --", parent=menu)
                continue
            for node in values:
                cmds.menuItem(label=self._format_node_menu_label(node), parent=menu)
            idx = values.index(current) + 1 if current in values else 1
            cmds.optionMenu(menu, e=True, select=idx)

    def get_manual_selected_root(self, menu_key: str) -> Optional[str]:
        values = self.manual_root_menu_values.get(menu_key, [])
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
            cmds.optionMenu(self.ui[menu_key], e=True, select=values.index(node) + 1)
        self.log("INFO", "RootSelect", f"Root manuel défini: {self._short_name(node)}", [node])

    def on_manual_root_changed(self, menu_key: str) -> None:
        root = self.get_manual_selected_root(menu_key)
        if root:
            self.log("INFO", "RootSelect", f"Root sélectionné: {self._short_name(root)}", [root])

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
        elif scope_key == "low_fbx":
            namespace = self.context["low_fbx_namespace"]
        elif scope_key == "bake_low":
            namespace = self.context["bake_ma_namespace"]
        elif scope_key == "final_asset_ma":
            namespace = self.context["final_asset_ma_namespace"]
        elif scope_key == "final_asset_fbx":
            namespace = self.context["final_asset_fbx_namespace"]

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
                    meshes, _ = self._collect_mesh_transforms_in_namespace(self.context["final_asset_fbx_namespace"])
                    meshes = [m for m in meshes if self._matches_asset_kind(m, "final")]
                    roots_by_scope[key] = [self.context["final_asset_fbx_namespace"]]
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

    def _list_ui_key_for_context(self, context_key: str) -> str:
        return "texture_sets_list" if context_key == "high" else "low_texture_sets_list"

    def _refresh_texture_sets_list_ui(self, context_key: str = "high") -> None:
        list_ui_key = self._list_ui_key_for_context(context_key)
        if list_ui_key not in self.ui:
            return
        previous_selection = self._selected_texture_set_names(context_key)
        self.texture_set_label_to_key_by_context[context_key] = {}
        self.texture_set_section_headers_by_context[context_key] = set()
        cmds.textScrollList(self.ui[list_ui_key], edit=True, removeAll=True)
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
            cmds.textScrollList(self.ui[list_ui_key], edit=True, append=header)
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
                cmds.textScrollList(self.ui[list_ui_key], edit=True, append=unique_label)
        self._restore_texture_set_selection(previous_selection, context_key)

    def _selected_texture_set_names(self, context_key: str = "high") -> List[str]:
        list_ui_key = self._list_ui_key_for_context(context_key)
        if list_ui_key not in self.ui:
            return []
        selected = cmds.textScrollList(self.ui[list_ui_key], query=True, selectItem=True) or []
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
            cmds.textScrollList(self.ui[list_ui_key], edit=True, selectItem=labels_to_select)

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
        self.detected_roots["high"] = self._find_root_candidates("high", namespace=namespace)
        self.detected_roots["placeholder"] = self._find_root_candidates("placeholder", namespace=namespace)
        self._log_root_detection("high", "High")
        self._log_root_detection("placeholder", "Placeholder")

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
        self.log("INFO", "Workflow", "Final review désactivée dans cette version High-only.")

    def load_everything(self) -> None:
        self.log("INFO", "Load", "Action: Load Everything")
        self.log("INFO", "Load", f"Root courant: {self.paths.get('root', '') or '-- non défini --'}")

        if not cmds.objExists("Outsourcing_Review"):
            cmds.group(empty=True, name="Outsourcing_Review")
            self.log("INFO", "Load", "Groupe Outsourcing_Review créé.")
        else:
            self.log("INFO", "Load", "Groupe Outsourcing_Review déjà présent.")
        cmds.setAttr("Outsourcing_Review.visibility", 0)
        self.log("INFO", "Load", "Groupe Outsourcing_Review masqué (visibility=0).")

        self.review_group_contents = {
            "high_ma": [],
            "high_fbx": [],
            "low_fbx": [],
            "bake_ma": [],
            "final_scene_ma": [],
        }

        load_plan = [
            ("high_ma", "High_Ma_File"),
            ("high_fbx", "High_FBX_File"),
            ("low_fbx", "Low_FBX_File"),
            ("bake_ma", "Bake_MA_File"),
            ("final_scene_ma", "Final_Asset_MA_File"),
        ]

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
            for node in top_nodes:
                if not cmds.objExists(node):
                    self.log("WARNING", "Load", f"Node ignoré (inexistant): {node}")
                    continue
                try:
                    cmds.parent(node, "Outsourcing_Review")
                    stored_nodes.append(node)
                except RuntimeError:
                    self.log("WARNING", "Load", f"Impossible de parent {node} -> Outsourcing_Review")
                    continue
            self.review_group_contents[file_key] = stored_nodes
            loaded_or_reused += 1
            self.log(
                "INFO",
                "Load",
                f"[{file_key}] top nodes parentés: {len(stored_nodes)} | "
                f"{self._preview_list(stored_nodes, max_items=8)}",
            )

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
            self.log("INFO", "Compare", f"Résultat : OK ({left_label} et {right_label} cohérents).")
            return True

        mismatch_count = len(missing_in_right) + len(missing_in_left) + len(topo_mismatch) + len(uv_mismatch)
        self.log("WARNING", "Compare", f"Résultat : mismatch détecté ({mismatch_count} catégorie(s) en écart).")
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
        self._log_step_header(7, "Compare High.ma vs High.fbx", category="Compare")
        self.log("INFO", "Compare", f"Source A : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Compare", f"Source B : {self._basename_from_path(self.paths.get('high_fbx', ''))}")
        ma_root = self.get_manual_selected_root("compare_ma_root_menu")
        fbx_root = self.get_manual_selected_root("compare_fbx_root_menu")
        if not ma_root or not fbx_root:
            self.log("FAIL", "Compare", "Sélection manuelle requise: choisir High.ma Root et High.fbx Root.")
            self.set_check_status("ma_fbx_compared", "FAIL")
            return
        ma_meshes = self._collect_mesh_transforms(ma_root)
        fbx_meshes = self._collect_mesh_transforms(fbx_root)
        self.log("INFO", "Compare", f"Root MA sélectionné : {ma_root}", [ma_root])
        self.log("INFO", "Compare", f"Root FBX sélectionné : {fbx_root}", [fbx_root])
        self.log("INFO", "Compare", f"Meshes analysés MA/FBX : {len(ma_meshes)}/{len(fbx_meshes)}")

        if not ma_meshes or not fbx_meshes:
            self.log("FAIL", "Compare", "Résultat : compare impossible (au moins une source sans mesh).")
            self.set_check_status("ma_fbx_compared", "FAIL")
            return

        ma_by_key = {self._normalized_relative_mesh_key(m, root=ma_root): self._mesh_data_signature(m) for m in ma_meshes}
        fbx_by_key = {self._normalized_relative_mesh_key(m, root=fbx_root): self._mesh_data_signature(m) for m in fbx_meshes}
        all_keys = sorted(set(ma_by_key.keys()) | set(fbx_by_key.keys()))
        self.log("INFO", "Compare", f"Paires comparées : {len(all_keys)}")

        pair_fail_count = 0
        for key in all_keys:
            ma_data = ma_by_key.get(key)
            fbx_data = fbx_by_key.get(key)
            ma_name = ma_data["path"] if ma_data else f"{self.context['ma_namespace']}:{key}"
            fbx_name = fbx_data["path"] if fbx_data else f"{self.context['fbx_namespace']}:{key}"

            presence_ok = bool(ma_data and fbx_data)
            topo_ok = bool(
                ma_data and fbx_data and
                (ma_data["v"], ma_data["e"], ma_data["f"]) == (fbx_data["v"], fbx_data["e"], fbx_data["f"])
            )
            uv_ok = bool(
                ma_data and fbx_data and
                ma_data["uv_total"] == fbx_data["uv_total"] and
                ma_data["uv_sets"] == fbx_data["uv_sets"]
            )
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

            self.log("INFO", "ComparePair", f"MA Mesh = {ma_name}")
            self.log("INFO", "ComparePair", f"FBX Mesh = {fbx_name}")
            self.log("INFO" if presence_ok else "FAIL", "ComparePair", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
            self.log("INFO" if topo_ok else "FAIL", "ComparePair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "ComparePair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "ComparePair", f"Bounding Box MA = {self._fmt_vec(bbox_dims_ma, precision=2)}")
            self.log("INFO", "ComparePair", f"Bounding Box FBX = {self._fmt_vec(bbox_dims_fbx, precision=2)}")
            self.log("INFO", "ComparePair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "ComparePair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "ComparePair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "ComparePair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        self.log("INFO" if ok else "FAIL", "Compare", f"Résultat final : {'OK' if ok else 'FAIL'}")
        self.set_check_status("ma_fbx_compared", "OK" if ok else "FAIL")

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
        ma_root = self.get_manual_selected_root("compare_bake_ma_root_menu")
        bake_root = self.get_manual_selected_root("compare_bake_high_root_menu")
        if not ma_root or not bake_root:
            self.log("FAIL", "CompareBake", "Sélection manuelle requise: choisir High.ma Root et Bake High Root.")
            self.set_check_status("ma_bake_compared", "FAIL")
            return
        ma_meshes = self._collect_mesh_transforms(ma_root)
        bake_meshes = self._collect_mesh_transforms(bake_root)

        self.log("INFO", "CompareBake", f"Source A : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "CompareBake", f"Source B : {self._basename_from_path(self.paths.get('bake_ma', ''))}")
        self.log("INFO", "CompareBake", f"Root High.ma sélectionné : {ma_root}", [ma_root])
        self.log("INFO", "CompareBake", f"Root Bake sélectionné : {bake_root}", [bake_root])
        self.log("INFO", "CompareBake", f"Meshes analysés High.ma / Bake High : {len(ma_meshes)} / {len(bake_meshes)}")
        ma_namespace = self.context["ma_namespace"]
        bake_namespace = self.context["bake_ma_namespace"]

        ma_by_key = {self._normalized_relative_mesh_key(m, root=ma_root): self._mesh_data_signature(m) for m in ma_meshes}
        bake_by_key = {self._normalized_relative_mesh_key(m, root=bake_root): self._mesh_data_signature(m) for m in bake_meshes}
        all_keys = sorted(set(ma_by_key.keys()) | set(bake_by_key.keys()))
        self.log("INFO", "CompareBake", f"Paires comparées : {len(all_keys)}")

        pair_fail_count = 0
        for key in all_keys:
            ma_data = ma_by_key.get(key)
            bake_data = bake_by_key.get(key)
            ma_name = ma_data["path"] if ma_data else f"{ma_namespace}:{key}"
            bake_name = bake_data["path"] if bake_data else f"{bake_namespace}:{key}"

            presence_ok = bool(ma_data and bake_data)
            topo_ok = bool(
                ma_data and bake_data and
                (ma_data["v"], ma_data["e"], ma_data["f"]) == (bake_data["v"], bake_data["e"], bake_data["f"])
            )
            uv_ok = bool(
                ma_data and bake_data and
                ma_data["uv_total"] == bake_data["uv_total"] and
                ma_data["uv_sets"] == bake_data["uv_sets"]
            )
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

            self.log("INFO", "CompareBakePair", f"High.ma Mesh = {ma_name}")
            self.log("INFO", "CompareBakePair", f"Bake High Mesh = {bake_name}")
            self.log("INFO" if presence_ok else "FAIL", "CompareBakePair", f"Mesh presence match = {'OK' if presence_ok else 'FAIL'}")
            self.log("INFO" if topo_ok else "FAIL", "CompareBakePair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "CompareBakePair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "CompareBakePair", f"Bounding Box High.ma = {self._fmt_vec(bbox_dims_ma, precision=2)}")
            self.log("INFO", "CompareBakePair", f"Bounding Box Bake = {self._fmt_vec(bbox_dims_bake, precision=2)}")
            self.log("INFO", "CompareBakePair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "CompareBakePair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "CompareBakePair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "CompareBakePair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        self.log("INFO" if ok else "FAIL", "CompareBake", f"Résultat final : {'OK' if ok else 'FAIL'}")
        self.set_check_status("ma_bake_compared", "OK" if ok else "FAIL")

    def _collect_low_meshes(self) -> List[str]:
        return self._collect_mesh_transforms_in_namespace(self.context["low_fbx_namespace"], exclude_placeholder_named=True)[0]

    def _resolve_low_roots_for_logs(self) -> List[str]:
        roots = self._find_root_candidates("low", namespace=self.context["low_fbx_namespace"])
        if roots:
            self.detected_roots["low"] = roots
            return roots
        return self.detected_roots.get("low", [])

    def run_low_topology_checks(self) -> None:
        self._log_step_header(1, "Topology Check", category="LowTopology")
        root = self.get_manual_selected_root("low_topology_root_menu")
        if not root:
            self.log("FAIL", "LowTopology", "Sélection manuelle requise: Select Low Root for Topology Check.")
            self.set_check_status("low_topology_checked", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "LowTopology", f"Fichier analysé : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "LowTopology", f"Root analysé : {root}", [root])
        self.log("INFO", "LowTopology", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "LowTopology", "Aucun mesh LOW chargé.")
            self.set_check_status("low_topology_checked", "FAIL")
            return

        ok_count = 0
        for m in meshes:
            nmv = cmds.polyInfo(m, nonManifoldVertices=True) or []
            nme = cmds.polyInfo(m, nonManifoldEdges=True) or []
            lam = cmds.polyInfo(m, laminaFaces=True) or []
            non_manifold_count = len(nmv) + len(nme)
            lamina_count = len(lam)
            ngon_count = 0
            face_count = int(cmds.polyEvaluate(m, face=True) or 0)
            for face_idx in range(face_count):
                vtx = cmds.polyInfo(f"{m}.f[{face_idx}]", faceToVertex=True) or []
                tokens = [tok for tok in (vtx[0].replace(":", " ").split() if vtx else []) if tok.isdigit()]
                if len(tokens) > 5:
                    ngon_count += 1
            mesh_ok = (ngon_count == 0 and non_manifold_count == 0 and lamina_count == 0)
            if mesh_ok:
                ok_count += 1

            self.log("INFO", "LowTopologyMesh", f"Mesh = {m}")
            self.log("INFO" if ngon_count == 0 else "FAIL", "LowTopologyMesh", f"N-gons = {'OK' if ngon_count == 0 else f'FAIL ({ngon_count} faces)'}")
            self.log("INFO" if non_manifold_count == 0 else "FAIL", "LowTopologyMesh", f"Non-manifold = {'OK' if non_manifold_count == 0 else f'FAIL ({non_manifold_count} éléments)'}")
            self.log("INFO" if lamina_count == 0 else "FAIL", "LowTopologyMesh", f"Lamina faces = {'OK' if lamina_count == 0 else f'FAIL ({lamina_count} faces)'}")
            self.log("INFO" if mesh_ok else "FAIL", "LowTopologyMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [m])

        fail_count = len(meshes) - ok_count
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", "LowTopology", f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        self.set_check_status("low_topology_checked", "OK" if ok else "FAIL")

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
        allowed = sorted({str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v})
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
        self.set_check_status("low_namespaces_checked", "OK" if ok else "FAIL")

    def remove_low_namespaces(self) -> None:
        allowed = {str(v) for k, v in self.context.items() if k.endswith("_namespace") and isinstance(v, str) and v}
        removable = [ns for ns in self.last_scanned_namespaces[:] if ns not in allowed]
        for ns in sorted(removable, key=lambda n: n.count(":"), reverse=True):
            try:
                cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            except RuntimeError as exc:
                self.log("WARNING", "LowNamespace", f"Suppression impossible pour {ns}: {exc}")
        self.scan_low_namespaces()

    def analyze_low_materials(self) -> None:
        self._log_step_header(3, "Materials Check", category="LowMaterials")
        root = self.get_manual_selected_root("low_materials_root_menu")
        if not root:
            self.log("FAIL", "LowMaterials", "Sélection manuelle requise: Select Low Root for Materials / Texture Sets.")
            self.set_check_status("low_materials_checked", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "LowMaterials", f"Fichier analysé : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "LowMaterials", f"Root analysé : {root}", [root])
        self.log("INFO", "LowMaterials", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "LowMaterials", "Aucun mesh LOW chargé.")
            self.set_check_status("low_materials_checked", "FAIL")
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
                self.log("WARNING", "LowMaterials", f"Aucun shape valide trouvé pour mesh : {mesh}", [mesh])
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

        self.material_sets_by_context["low"] = {}
        sorted_mats = sorted(mat_faces.items(), key=lambda x: x[1], reverse=True)
        self.log("INFO", "LowMaterials", f"Matériaux détectés : {len(sorted_mats)}")
        for mat, count in sorted_mats:
            pct = (count / float(total_faces) * 100.0) if total_faces else 0.0
            display = self._strip_namespaces_from_name(mat)
            has_prefix = display.startswith("QDS_")
            key = f"MAT::{mat}"
            self.material_sets_by_context["low"][key] = {
                "name": mat,
                "display_name": display,
                "objects": sorted(set(mat_objects.get(mat, []))),
                "full_objects": sorted(mat_full_objects.get(mat, set())),
                "components": sorted(mat_components.get(mat, set())),
                "percent_of_total": pct,
                "face_count": count,
                "is_qds": has_prefix,
            }
            self.log("INFO" if has_prefix else "FAIL", "LowMaterials", f"{display} | {pct:.2f}% faces ({count}/{total_faces})", self.material_sets_by_context["low"][key]["objects"][:80])
        if not sorted_mats:
            self.log("FAIL", "LowMaterials", "Aucun material valide trouvé.")
        self.detected_texture_sets = self.material_sets_by_context["low"]
        self._refresh_texture_sets_list_ui("low")
        ok = bool(self.material_sets_by_context["low"])
        self.log("INFO" if ok else "FAIL", "LowMaterials", f"Résultat final : {'OK' if ok else 'FAIL'}")
        self.set_check_status("low_materials_checked", "OK" if ok else "FAIL")

    def scan_namespaces(self) -> None:
        self._log_step_header(6, "Namespace Check", category="Namespace")
        user_ns = self._get_scan_namespaces()
        self.last_scanned_namespaces = user_ns[:]
        self.log("INFO", "Namespace", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Namespace", f"Namespaces utilisateur détectés : {len(user_ns)}")

        if not user_ns:
            self.log("INFO", "Namespace", "Résultat : OK (aucun namespace indésirable).")
            self.set_check_status("no_namespaces", "OK")
            return

        total_objs: List[str] = []
        for ns in user_ns:
            objs = cmds.ls(ns + ":*", long=True) or []
            if not objs:
                objs = [n for n in (cmds.ls(long=True) or []) if any(seg.startswith(ns + ":") for seg in n.split("|") if seg)]
            total_objs.extend(objs)
            self.log("WARNING", "Namespace", f"Namespace détecté: {ns} ({len(objs)} objets)", objs[:50])

        self.log("FAIL", "Namespace", f"Résultat : FAIL ({len(user_ns)} namespace(s) utilisateur détecté(s)).", total_objs[:200])
        self.set_check_status("no_namespaces", "FAIL")

    def remove_namespaces(self) -> None:
        self._log_step_header(6, "Namespace Check", category="Namespace")
        removable = self.last_scanned_namespaces[:] or self._get_scan_namespaces()
        removable = [ns for ns in removable if not self._is_allowed_namespace(ns)]
        self.log("INFO", "Namespace", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Namespace", f"Namespaces à supprimer : {len(removable)}")
        if not removable:
            self.log("INFO", "Namespace", "Résultat : OK (rien à supprimer).")
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
            self.set_check_status("placeholder_checked", "FAIL")
            return
        high_meshes = self._collect_mesh_transforms(high_root)
        placeholder_meshes = self._collect_mesh_transforms(placeholder_root)
        self.log("INFO", "Placeholder", f"High Root sélectionné : {high_root}", [high_root])
        self.log("INFO", "Placeholder", f"Placeholder Root sélectionné : {placeholder_root}", [placeholder_root])
        self.log("INFO", "Placeholder", f"Meshes analysés High/Placeholder : {len(high_meshes)}/{len(placeholder_meshes)}")
        if not high_meshes or not placeholder_meshes:
            self.log("FAIL", "Placeholder", "High/Placeholder non détectés dans High.ma.")
            self.set_check_status("placeholder_checked", "FAIL")
            return

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
        self.set_check_status("placeholder_checked", "OK" if fail_count == 0 else "FAIL")

    def run_topology_checks(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        _ = (scope_keys, source_label)
        self._log_step_header(3, "Topology Check", category="Topology")
        root = self.get_manual_selected_root("topology_high_root_menu")
        if not root:
            self.log("FAIL", "Topology", "Sélection manuelle requise: Select High Root for Topology Check.")
            self.set_check_status("topology_checked", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "Topology", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Topology", f"Root analysé : {root}", [root])
        self.log("INFO", "Topology", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "Topology", "Aucun mesh High.ma trouvé.")
            self.set_check_status("topology_checked", "FAIL")
            return

        ok_count = 0

        for m in meshes:
            nmv = cmds.polyInfo(m, nonManifoldVertices=True) or []
            nme = cmds.polyInfo(m, nonManifoldEdges=True) or []
            lam = cmds.polyInfo(m, laminaFaces=True) or []
            non_manifold_count = len(nmv) + len(nme)
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

            mesh_ok = (ngon_count == 0 and non_manifold_count == 0 and lamina_count == 0)
            if mesh_ok:
                ok_count += 1
            self.log("INFO", "TopologyMesh", f"Mesh = {m}")
            self.log("INFO" if ngon_count == 0 else "FAIL", "TopologyMesh", f"N-gons = {'OK' if ngon_count == 0 else f'FAIL ({ngon_count} faces)'}")
            self.log("INFO" if non_manifold_count == 0 else "FAIL", "TopologyMesh", f"Non-manifold = {'OK' if non_manifold_count == 0 else f'FAIL ({non_manifold_count} éléments)'}")
            self.log("INFO" if lamina_count == 0 else "FAIL", "TopologyMesh", f"Lamina faces = {'OK' if lamina_count == 0 else f'FAIL ({lamina_count} faces)'}")
            self.log("INFO" if mesh_ok else "FAIL", "TopologyMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [m])

        fail_count = len(meshes) - ok_count
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", "Topology", f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        self.set_check_status("topology_checked", "OK" if ok else "FAIL")

    def _count_faces_assigned_to_mesh(
        self,
        mesh: str,
        shape: str,
        shading_group: str,
        mesh_face_count: int,
    ) -> int:
        count, _, _ = self._material_assignment_details(mesh, shape, shading_group, mesh_face_count)
        return count

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
        panels = self._get_active_model_panels()
        for panel in panels:
            try:
                cmds.isolateSelect(panel, state=state)
            except RuntimeError:
                continue

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
            self.isolate_on_all_viewports(0)
            self.log("INFO", "Materials", "Isolate Material désactivé")
            return

        selected_key = self.select_objects_from_selected_material(context_key)
        if not selected_key:
            return

        self.isolate_on_all_viewports(1)
        self.material_isolation_state = {"context": context_key, "material_key": selected_key}
        self.log("INFO", "Materials", "Isolate Material activé")

    def analyze_texture_sets(self, mode: str = "materials", scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        _ = (mode, scope_keys, source_label)
        self._log_step_header(6, "Analyze Materials", category="Materials")
        root = self.get_manual_selected_root("materials_high_root_menu")
        if not root:
            self.log("FAIL", "Materials", "Sélection manuelle requise: Select High Root for Materials / Texture Sets.")
            self.set_check_status("texture_sets_analyzed", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "Materials", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "Materials", f"Root analysé : {root}", [root])
        self.log("INFO", "Materials", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "Materials", "Aucun mesh High.ma trouvé.")
            self.set_check_status("texture_sets_analyzed", "FAIL")
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
        self.set_check_status("texture_sets_analyzed", "OK" if ok else "FAIL")

    def check_vertex_colors(self, scope_keys: Optional[List[str]] = None, source_label: Optional[str] = None) -> None:
        _ = (scope_keys, source_label)
        self._log_step_header(4, "Vertex Color Check", category="VertexColor")
        root = self.get_manual_selected_root("vertex_high_root_menu")
        if not root:
            self.log("FAIL", "VertexColor", "Sélection manuelle requise: Select High Root for Vertex Color Check.")
            self.set_check_status("vertex_colors_checked", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "VertexColor", f"Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        self.log("INFO", "VertexColor", f"Root analysé : {root}", [root])
        self.log("INFO", "VertexColor", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "VertexColor", "Aucun mesh High.ma trouvé.")
            self.set_check_status("vertex_colors_checked", "FAIL")
            return

        ok_count = 0
        for m in meshes:
            shapes = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                continue
            shape = shapes[0]
            sets = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            fcount = int(cmds.polyEvaluate(shape, face=True) or 0)
            missing = fcount
            colored_faces = 0
            distinct_colors: Set[Tuple[float, float, float]] = set()
            for face_idx in range(fcount):
                rgb = cmds.polyColorPerVertex(f"{shape}.f[{face_idx}]", query=True, rgb=True) or []
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
            self.log("INFO", "VertexColorMesh", f"Groupes de vertex colors distincts = {len(distinct_colors)}")
            if not has_color_set:
                self.log("FAIL", "VertexColorMesh", "Aucun color set trouvé.")
            self.log("INFO" if mesh_ok else "FAIL", "VertexColorMesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [m])

        fail_count = len(meshes) - ok_count
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", "VertexColor", f"Résultat final : {ok_count} OK / {fail_count} FAIL")
        self.set_check_status("vertex_colors_checked", "OK" if ok else "FAIL")

    def display_vertex_colors(self) -> None:
        targets, _ = self._collect_mesh_transforms_in_namespace(self.context["ma_namespace"], exclude_placeholder_named=True)
        self.log("INFO", "VertexColor", f"Display: Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        if not targets:
            self.log("WARNING", "VertexColor", "Aucun high mesh High.ma trouvé.")
            return
        for tr in targets:
            shapes = cmds.listRelatives(tr, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            for shape in shapes:
                try:
                    cmds.setAttr(shape + ".displayColors", 1)
                except RuntimeError:
                    pass
        cmds.polyOptions(colorShadedDisplay=True)
        self.log("INFO", "VertexColor", f"Display: Meshes affectés : {len(targets)}")
        self.log("INFO", "VertexColor", "Display: Résultat : OK")

    def hide_vertex_colors(self) -> None:
        targets, _ = self._collect_mesh_transforms_in_namespace(self.context["ma_namespace"], exclude_placeholder_named=True)
        self.log("INFO", "VertexColor", f"Hide: Fichier analysé : {self._basename_from_path(self.paths.get('high_ma', ''))}")
        if not targets:
            self.log("WARNING", "VertexColor", "Aucun high mesh High.ma trouvé.")
            return
        for tr in targets:
            shapes = cmds.listRelatives(tr, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            for shape in shapes:
                try:
                    cmds.setAttr(shape + ".displayColors", 0)
                except RuntimeError:
                    pass
        self.log("INFO", "VertexColor", f"Hide: Meshes affectés : {len(targets)}")
        self.log("INFO", "VertexColor", "Hide: Résultat : OK")

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

    def run_low_uv_map1_check(self) -> None:
        self._log_step_header(4, "UV Map1 Check", category="LowUV1")
        root = self.get_manual_selected_root("low_uv1_root_menu")
        if not root:
            self.log("FAIL", "LowUV1", "Sélection manuelle requise: Select Low Root for UV map1 Check.")
            self.set_check_status("low_uv_map1_checked", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "LowUV1", f"Fichier analysé : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "LowUV1", f"Root analysé : {root}", [root])
        self.log("INFO", "LowUV1", f"Meshes analysés : {len(meshes)}")
        if not meshes:
            self.log("FAIL", "LowUV1", "Aucun mesh LOW chargé.")
            self.set_check_status("low_uv_map1_checked", "FAIL")
            return

        fail_count = 0
        for mesh in meshes:
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
            ratio = self._mesh_uv_distortion_ratio(mesh, uv_set="map1")
            distortion_ok = (ratio is None) or ratio <= LOW_UV_DISTORTION_THRESHOLD
            mesh_ok = overlap_ok and outside_ok
            if not mesh_ok:
                fail_count += 1

            self.log("INFO", "LowUV1Mesh", f"Mesh = {mesh}")
            self.log("INFO" if outside_ok else "FAIL", "LowUV1Mesh", f"UV shells hors 0-1 = {outside_count}")
            self.log("INFO" if overlap_ok else "FAIL", "LowUV1Mesh", f"UV overlap = {overlap_count}")
            self.log("INFO" if distortion_ok else "WARNING", "LowUV1Mesh", f"Distortion = {'OK' if distortion_ok else f'WARNING ({ratio:.3f})'}")
            self.log("INFO" if mesh_ok else "FAIL", "LowUV1Mesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [mesh])

        self.log("INFO", "LowUV1", f"Seuil distortion utilisé : {LOW_UV_DISTORTION_THRESHOLD:.2f}")
        ok = fail_count == 0
        self.log("INFO" if ok else "FAIL", "LowUV1", f"Résultat final : {'OK' if ok else 'FAIL'}")
        self.set_check_status("low_uv_map1_checked", "OK" if ok else "FAIL")

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

    def run_low_map2_density_check(self) -> None:
        self._log_step_header(5, "UV Map2 Check", category="LowUV2")
        root = self.get_manual_selected_root("low_uv2_root_menu")
        if not root:
            self.log("FAIL", "LowUV2", "Sélection manuelle requise: Select Low Root for UV map2 / TD Check.")
            self.set_check_status("low_uv_map2_checked", "FAIL")
            return
        meshes = self._collect_mesh_transforms(root)
        self.log("INFO", "LowUV2", f"Fichier analysé : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "LowUV2", f"Root analysé : {root}", [root])
        self.log("INFO", "LowUV2", f"Meshes analysés : {len(meshes)}")
        self.log("INFO", "LowUV2", "Map analysée : map2")
        if not meshes:
            self.log("FAIL", "LowUV2", "Aucun mesh LOW chargé.")
            self.set_check_status("low_uv_map2_checked", "FAIL")
            return

        valid_values: List[float] = []
        pair_fail_count = 0
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
            mesh_ok = abs(delta) <= LOW_MAP2_TOLERANCE
            if not mesh_ok:
                pair_fail_count += 1
            self.log("INFO", "LowUV2Mesh", f"Mesh = {mesh}")
            self.log("INFO", "LowUV2Mesh", f"TD mesurée = {td:.2f}")
            self.log("INFO", "LowUV2Mesh", f"TD cible = {LOW_MAP2_TARGET_TD:.2f}")
            self.log("INFO", "LowUV2Mesh", f"Delta = {delta:.2f}")
            self.log("INFO" if mesh_ok else "FAIL", "LowUV2Mesh", f"Result = {'OK' if mesh_ok else 'FAIL'}", [mesh])

        mean_td = (sum(valid_values) / len(valid_values)) if valid_values else 0.0
        self.log("INFO", "LowUV2", f"Texel density moyenne mesurée : {mean_td:.2f}")
        self.log("INFO", "LowUV2", f"Tolérance : ±{LOW_MAP2_TOLERANCE:.2f}")
        ok = bool(valid_values) and pair_fail_count == 0
        self.log("INFO" if ok else "FAIL", "LowUV2", f"Résultat global : {'OK' if ok else 'FAIL'}")
        self.set_check_status("low_uv_map2_checked", "OK" if ok else "FAIL")

    def compare_low_vs_bake_low(self) -> None:
        self._log_step_header(6, "Compare Low vs Bake Low", category="LowCompareBake")
        low_root = self.get_manual_selected_root("compare_low_bake_low_root_menu")
        bake_root = self.get_manual_selected_root("compare_low_bake_bake_root_menu")
        if not low_root or not bake_root:
            self.log("FAIL", "CompareLowBake", "Sélection manuelle requise: Select Low.fbx Root et Select Bake Low Root.")
            self.set_check_status("low_bake_compared", "FAIL")
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
            self.set_check_status("low_bake_compared", "FAIL")
            return

        low_by = {re.sub(r"_low$", "", self._normalized_relative_mesh_key(m, root=low_root)): self._mesh_data_signature(m) for m in low_meshes}
        bake_by = {re.sub(r"_low$", "", self._normalized_relative_mesh_key(m, root=bake_root)): self._mesh_data_signature(m) for m in bake_meshes}
        all_keys = sorted(set(low_by.keys()) | set(bake_by.keys()))
        self.log("INFO", "CompareLowBake", f"Paires comparées : {len(all_keys)}")

        pair_fail_count = 0
        for key in all_keys:
            low_data = low_by.get(key)
            bake_data = bake_by.get(key)
            low_name = low_data["path"] if low_data else f"{self.context['low_fbx_namespace']}:{key}"
            bake_name = bake_data["path"] if bake_data else f"{self.context['bake_ma_namespace']}:{key}"

            presence_ok = bool(low_data and bake_data)
            topo_ok = bool(low_data and bake_data and (low_data["v"], low_data["e"], low_data["f"]) == (bake_data["v"], bake_data["e"], bake_data["f"]))
            uv_ok = bool(low_data and bake_data and low_data["uv_total"] == bake_data["uv_total"] and low_data["uv_sets"] == bake_data["uv_sets"])
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

            self.log("INFO", "CompareLowBakePair", f"Low = {low_name}")
            self.log("INFO", "CompareLowBakePair", f"Bake Low = {bake_name}")
            self.log("INFO" if presence_ok else "FAIL", "CompareLowBakePair", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
            self.log("INFO" if topo_ok else "FAIL", "CompareLowBakePair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "CompareLowBakePair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box Low = {self._fmt_vec(bbox_dims_low, precision=2)}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box Bake Low = {self._fmt_vec(bbox_dims_bake, precision=2)}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "CompareLowBakePair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "CompareLowBakePair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "CompareLowBakePair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        self.log("INFO" if ok else "FAIL", "CompareLowBake", f"Résultat final : {'OK' if ok else 'FAIL'}")
        self.set_check_status("low_bake_compared", "OK" if ok else "FAIL")

    def compare_low_vs_final_asset(self) -> None:
        self._log_step_header(7, "Compare Low vs Final Asset", category="LowCompareFinal")
        low_root = self.get_manual_selected_root("compare_low_final_low_root_menu")
        final_root = self.get_manual_selected_root("compare_low_final_final_root_menu")
        if not low_root or not final_root:
            self.log("FAIL", "CompareLowFinal", "Sélection manuelle requise: Select Low.fbx Root et Select Final Scene Root.")
            self.set_check_status("low_final_compared", "FAIL")
            return
        low_meshes = self._collect_mesh_transforms(low_root)
        final_meshes = self._collect_mesh_transforms(final_root)
        self.log("INFO", "CompareLowFinal", f"Source A : {self._basename_from_path(self.paths.get('low_fbx', ''))}")
        self.log("INFO", "CompareLowFinal", f"Source B : {self._basename_from_path(self.paths.get('final_scene_ma', ''))}")
        self.log("INFO", "CompareLowFinal", f"Root Low sélectionné : {low_root}", [low_root])
        self.log("INFO", "CompareLowFinal", f"Root Final sélectionné : {final_root}", [final_root])
        self.log("INFO", "CompareLowFinal", f"Meshes analysés Low/Final : {len(low_meshes)} / {len(final_meshes)}")
        if not low_meshes or not final_meshes:
            self.log("FAIL", "CompareLowFinal", "Compare impossible : Low.fbx ou Final Scene non chargé.")
            self.set_check_status("low_final_compared", "FAIL")
            return

        low_by = {re.sub(r"_low$", "", self._normalized_relative_mesh_key(m, root=low_root)): self._mesh_data_signature(m) for m in low_meshes}
        final_by = {self._normalized_relative_mesh_key(m, root=final_root): self._mesh_data_signature(m) for m in final_meshes}
        all_keys = sorted(set(low_by.keys()) | set(final_by.keys()))
        self.log("INFO", "CompareLowFinal", f"Paires comparées : {len(all_keys)}")

        pair_fail_count = 0
        for key in all_keys:
            low_data = low_by.get(key)
            final_data = final_by.get(key)
            low_name = low_data["path"] if low_data else f"{self.context['low_fbx_namespace']}:{key}"
            final_name = final_data["path"] if final_data else f"{self.context['final_asset_ma_namespace']}:{key}"

            presence_ok = bool(low_data and final_data)
            topo_ok = bool(low_data and final_data and (low_data["v"], low_data["e"], low_data["f"]) == (final_data["v"], final_data["e"], final_data["f"]))
            uv_ok = bool(low_data and final_data and low_data["uv_total"] == final_data["uv_total"] and low_data["uv_sets"] == final_data["uv_sets"])
            bbox_dims_low = (0.0, 0.0, 0.0)
            bbox_dims_final = (0.0, 0.0, 0.0)
            bbox_delta = (0.0, 0.0, 0.0)
            bbox_center_delta = (0.0, 0.0, 0.0)
            bbox_ok = False
            if presence_ok:
                bbox_dims_low, bbox_center_low = self._mesh_bbox_dims_and_center_world(low_data["path"])
                bbox_dims_final, bbox_center_final = self._mesh_bbox_dims_and_center_world(final_data["path"])
                bbox_delta = tuple(abs(bbox_dims_low[i] - bbox_dims_final[i]) for i in range(3))
                bbox_center_delta = tuple(abs(bbox_center_low[i] - bbox_center_final[i]) for i in range(3))
                bbox_ok = all(v <= 1e-4 for v in bbox_delta) and all(v <= 1e-4 for v in bbox_center_delta)
            pair_ok = presence_ok and topo_ok and uv_ok and bbox_ok
            if not pair_ok:
                pair_fail_count += 1

            self.log("INFO", "CompareLowFinalPair", f"Low = {low_name}")
            self.log("INFO", "CompareLowFinalPair", f"Final = {final_name}")
            self.log("INFO" if presence_ok else "FAIL", "CompareLowFinalPair", f"Presence match = {'OK' if presence_ok else 'FAIL'}")
            self.log("INFO" if topo_ok else "FAIL", "CompareLowFinalPair", f"Topology match = {'OK' if topo_ok else 'FAIL'}")
            self.log("INFO" if uv_ok else "FAIL", "CompareLowFinalPair", f"UV match = {'OK' if uv_ok else 'FAIL'}")
            self.log("INFO", "CompareLowFinalPair", f"Bounding Box Low = {self._fmt_vec(bbox_dims_low, precision=2)}")
            self.log("INFO", "CompareLowFinalPair", f"Bounding Box Final = {self._fmt_vec(bbox_dims_final, precision=2)}")
            self.log("INFO", "CompareLowFinalPair", f"Bounding Box delta = {self._fmt_vec(bbox_delta, precision=4)}")
            self.log("INFO", "CompareLowFinalPair", f"Bounding Box center delta = {self._fmt_vec(bbox_center_delta, precision=4)}")
            self.log("INFO" if bbox_ok else "FAIL", "CompareLowFinalPair", f"Bounding Box match = {'OK' if bbox_ok else 'FAIL'}")
            self.log("INFO" if pair_ok else "FAIL", "CompareLowFinalPair", f"Result = {'OK' if pair_ok else 'FAIL'}")

        ok = pair_fail_count == 0
        self.log("INFO" if ok else "FAIL", "CompareLowFinal", f"Résultat final : {'OK' if ok else 'FAIL'}")
        self.set_check_status("low_final_compared", "OK" if ok else "FAIL")

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
