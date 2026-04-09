# -*- coding: utf-8 -*-
"""
Outsource Review Script (Maya)
-----------------------------
Pipeline-aware review assistant for outsourcing deliveries.

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

WINDOW_NAME = "outsourceReviewAssistantWin"
WINDOW_TITLE = "Outsource Review Script"
MAX_UI_TEXT_LENGTH = 110
PLACEHOLDER_TOKEN = "placeholder"


@dataclass
class ReviewIssue:
    level: str
    category: str
    message: str
    objects: List[str] = field(default_factory=list)


@dataclass
class TabConfig:
    key: str
    label: str
    subtitle: str
    files: List[Tuple[str, str, str]]  # (key, label, type)
    roots: List[Tuple[str, str, str]]  # (key, label, suffix_kind)
    checks: List[Tuple[str, str, str]]  # (key, label, handler)
    run_all_label: str


class OutsourceReviewTool:
    def __init__(self) -> None:
        self.ui: Dict[str, Any] = {}
        self.tab_ui: Dict[str, Dict[str, Any]] = {}
        self.tab_issues: Dict[str, List[ReviewIssue]] = {}
        self.tab_result_index_to_objects: Dict[str, Dict[int, List[str]]] = {}
        self.tab_paths: Dict[str, Dict[str, str]] = {}
        self.tab_detected_files: Dict[str, Dict[str, List[str]]] = {}
        self.tab_detected_roots: Dict[str, Dict[str, List[str]]] = {}
        self.tab_check_states: Dict[str, Dict[str, str]] = {}
        self.tab_texture_sets: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.tab_texture_map: Dict[str, Dict[str, str]] = {}
        self.last_scanned_namespaces: List[str] = []

        self.reference_namespaces = {
            "high_ma": "High_Ma_File",
            "high_fbx": "High_FBX_File",
            "low_fbx": "Low_FBX_File",
            "bakescene": "BakeScene_File",
            "final_ma": "Final_MA_File",
        }

        self.tab_configs = self._build_tab_configs()
        for tab_key, cfg in self.tab_configs.items():
            self.tab_issues[tab_key] = []
            self.tab_result_index_to_objects[tab_key] = {}
            self.tab_paths[tab_key] = {"root": ""}
            self.tab_detected_files[tab_key] = {file_key: [] for file_key, _, _ in cfg.files}
            self.tab_detected_roots[tab_key] = {root_key: [] for root_key, _, _ in cfg.roots}
            self.tab_texture_sets[tab_key] = {}
            self.tab_texture_map[tab_key] = {}
            self.tab_check_states[tab_key] = {check_key: "PENDING" for check_key, _, _ in cfg.checks}

    def _build_tab_configs(self) -> Dict[str, TabConfig]:
        return {
            "high": TabConfig(
                key="high",
                label="High",
                subtitle="Validation du High livré + cohérence avec le High de la Bake Scene",
                files=[
                    ("high_ma", "High MA Found", "ma"),
                    ("high_fbx", "High FBX Found", "fbx"),
                    ("bakescene", "Bake Scene Found", "ma"),
                ],
                roots=[
                    ("high_ma_root", "Detected High MA Root", "high"),
                    ("high_fbx_root", "Detected High FBX Root", "high"),
                    ("bake_high_root", "Detected BakeScene High", "high"),
                    ("placeholder_root", "Detected Placeholder Root", "placeholder"),
                ],
                checks=[
                    ("compare", "Compare High MA vs High FBX vs BakeScene High", "check_compare"),
                    ("namespaces", "Pas de namespaces", "check_namespaces"),
                    ("placeholder", "Placeholder Match", "check_placeholder"),
                    ("topology", "Topology", "check_topology"),
                    ("tex_mats", "Texture Sets (Materials)", "check_texture_sets_materials"),
                    ("tex_groups", "Texture Sets (Groups Method)", "check_texture_sets_groups"),
                    ("vcolor", "Vertex Colors", "check_vertex_colors"),
                    ("design", "Design Kit Review (manuel)", "check_design_manual"),
                ],
                run_all_label="Run All High Checks",
            ),
            "low": TabConfig(
                key="low",
                label="Low",
                subtitle="Validation du Low livré + cohérence avec BakeScene Low et Final MA",
                files=[
                    ("low_fbx", "Low FBX Found", "fbx"),
                    ("bakescene", "Bake Scene Found", "ma"),
                    ("final_ma", "Final Asset MA Found", "ma"),
                ],
                roots=[
                    ("low_fbx_root", "Detected Low FBX Root", "low"),
                    ("bake_low_root", "Detected BakeScene Low", "low"),
                    ("final_root", "Detected Final Asset Root", "final"),
                    ("placeholder_root", "Detected Placeholder Root", "placeholder"),
                ],
                checks=[
                    ("compare", "Compare Low FBX vs BakeScene Low vs Final MA", "check_compare"),
                    ("namespaces", "Pas de namespaces", "check_namespaces"),
                    ("placeholder", "Placeholder Match", "check_placeholder"),
                    ("topology", "Topology", "check_topology"),
                    ("uv01", "UV01 Setup for Bake", "check_uv01"),
                    ("uv02", "UV02 Setup for Texture 20.48", "check_uv02"),
                    ("tex_mats", "Texture Sets (Materials)", "check_texture_sets_materials"),
                    ("tex_groups", "Texture Sets (Groups Method)", "check_texture_sets_groups"),
                    ("vcolor", "Vertex Colors", "check_vertex_colors"),
                    ("design", "Design Kit Review (manuel)", "check_design_manual"),
                ],
                run_all_label="Run All Low Checks",
            ),
            "bakescene": TabConfig(
                key="bakescene",
                label="Bake Scene",
                subtitle="Validation de la scène de bake et cohérence avec les livrables High / Low",
                files=[
                    ("bakescene", "Bake Scene Found", "ma"),
                    ("high_ma", "High MA Found", "ma"),
                    ("high_fbx", "High FBX Found", "fbx"),
                    ("low_fbx", "Low FBX Found", "fbx"),
                ],
                roots=[
                    ("bake_high_root", "Detected Bake High Root", "high"),
                    ("bake_low_root", "Detected Bake Low Root", "low"),
                    ("ref_high_root", "Detected Ref High Root", "high"),
                    ("ref_low_root", "Detected Ref Low Root", "low"),
                ],
                checks=[
                    ("compare", "Bake Scene = mêmes fichiers que High / Low livrés", "check_compare"),
                    ("namespaces", "Pas de namespaces", "check_namespaces"),
                    ("presence", "High / Low bien présents dans la scène", "check_bake_presence"),
                    ("align", "High / Low bien alignés pour bake", "check_bake_alignment"),
                    ("topology", "Topology", "check_topology"),
                    ("uv01", "UV01 Setup for Bake", "check_uv01"),
                    ("uv02", "UV02 Setup for Texture 20.48", "check_uv02"),
                    ("tex_mats", "Texture Sets (Materials)", "check_texture_sets_materials"),
                    ("tex_groups", "Texture Sets (Groups Method)", "check_texture_sets_groups"),
                    ("vcolor", "Vertex Colors", "check_vertex_colors"),
                    ("naming", "Naming Meshes + Mats", "check_naming_bake"),
                ],
                run_all_label="Run All Bake Scene Checks",
            ),
            "final": TabConfig(
                key="final",
                label="Final Asset",
                subtitle="Validation du livrable final .ma + cohérence avec Low FBX et BakeScene Low",
                files=[
                    ("final_ma", "Final Asset MA Found", "ma"),
                    ("low_fbx", "Low FBX Found", "fbx"),
                    ("bakescene", "Bake Scene Found", "ma"),
                ],
                roots=[
                    ("final_root", "Detected Final Root", "final"),
                    ("low_fbx_root", "Detected Low FBX Root", "low"),
                    ("bake_low_root", "Detected BakeScene Low", "low"),
                ],
                checks=[
                    ("compare", "Compare Final MA vs Low FBX vs BakeScene Low", "check_compare"),
                    ("namespaces", "Pas de namespaces", "check_namespaces"),
                    ("naming", "Naming final sans suffix _low", "check_naming_final"),
                    ("topology", "Topology", "check_topology"),
                    ("uv01", "UV01 Setup for Bake", "check_uv01"),
                    ("uv02", "UV02 Setup for Texture 20.48", "check_uv02"),
                    ("tex_mats", "Texture Sets (Materials)", "check_texture_sets_materials"),
                    ("tex_groups", "Texture Sets (Groups Method)", "check_texture_sets_groups"),
                    ("vcolor", "Vertex Colors", "check_vertex_colors"),
                ],
                run_all_label="Run All Final Asset Checks",
            ),
        }

    # ---------------- UI ----------------
    def build(self) -> None:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)
        self.ui["window"] = cmds.window(WINDOW_NAME, title=WINDOW_TITLE, sizeable=True, widthHeight=(1200, 900))
        root = cmds.formLayout()
        tabs = cmds.tabLayout(innerMarginWidth=6, innerMarginHeight=6)
        self.ui["tabs"] = tabs

        for tab_key, cfg in self.tab_configs.items():
            child = cmds.scrollLayout(childResizable=True, horizontalScrollBarThickness=12, verticalScrollBarThickness=12)
            col = cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
            self.tab_ui[tab_key] = {"root_col": col}
            cmds.frameLayout(label=f"{cfg.label.upper()} REVIEW", collapsable=False, marginWidth=8)
            cmds.columnLayout(adjustableColumn=True)
            cmds.text(label=cfg.subtitle, align="left")
            cmds.setParent("..")
            cmds.setParent("..")
            self._build_file_block(tab_key, cfg)
            self._build_context_block(tab_key, cfg)
            self._build_checks_block(tab_key, cfg)
            self._build_texture_block(tab_key)
            self._build_actions_block(tab_key, cfg)
            self._build_results_block(tab_key)
            self._build_notes_block(tab_key)
            self._build_summary_block(tab_key)
            cmds.setParent("..")
            cmds.setParent(tabs)
            cmds.tabLayout(tabs, edit=True, tabLabel=(child, cfg.label))

        cmds.formLayout(root, e=True, attachForm=[(tabs, "top", 0), (tabs, "left", 0), (tabs, "right", 0), (tabs, "bottom", 0)])
        cmds.showWindow(self.ui["window"])
        self.refresh_all_ui()

    def _build_file_block(self, tab_key: str, cfg: TabConfig) -> None:
        cmds.frameLayout(label="1) Fichiers / Détection", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        t = self.tab_ui[tab_key]
        t["root_field"] = cmds.textFieldButtonGrp(
            label="Root Folder",
            buttonLabel="Browse",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.pick_root_folder(tab_key),
        )
        cmds.button(label="Scan Delivery Folder", height=30, command=lambda *_: self.scan_delivery_folder(tab_key))
        cmds.separator(style="in")

        for file_key, file_label, file_type in cfg.files:
            cmds.text(label=file_label, align="left")
            t[f"{file_key}_status"] = cmds.text(label="Aucun fichier détecté", align="left")
            cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
            t[f"{file_key}_menu"] = cmds.optionMenu(changeCommand=lambda *_f, tk=tab_key, fk=file_key: self.on_file_selected(tk, fk))
            cmds.menuItem(label="-- Aucun --", parent=t[f"{file_key}_menu"])
            label = "Reference MA" if file_type == "ma" else "Reference FBX"
            cmds.button(label=label, height=26, command=lambda *_f, tk=tab_key, fk=file_key: self.reference_file(tk, fk))
            cmds.setParent("..")

        cmds.separator(style="in")
        for root_key, root_label, _ in cfg.roots:
            cmds.text(label=root_label, align="left")
            cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
            t[f"{root_key}_menu"] = cmds.optionMenu(changeCommand=lambda *_f, tk=tab_key, rk=root_key: self.on_root_selected(tk, rk))
            cmds.menuItem(label="Root non détecté", parent=t[f"{root_key}_menu"])
            cmds.button(label="Auto", height=24, command=lambda *_f, tk=tab_key: self.auto_detect_roots(tk))
            cmds.button(label="From Sel", height=24, command=lambda *_f, tk=tab_key, rk=root_key: self.set_root_from_selection(tk, rk))
            cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_context_block(self, tab_key: str, cfg: TabConfig) -> None:
        cmds.frameLayout(label="2) Contexte détecté", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True)
        bullets = "\n".join([f"• {f[1].replace(' Found', '')}" for f in cfg.files])
        self.tab_ui[tab_key]["context_text"] = cmds.text(label=f"Scope implicite actif :\n{bullets}", align="left")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_checks_block(self, tab_key: str, cfg: TabConfig) -> None:
        cmds.frameLayout(label="3) Checks techniques", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        t = self.tab_ui[tab_key]
        t["check_boxes"] = {}
        for check_key, label, handler in cfg.checks:
            if check_key == "namespaces":
                cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
                t["check_boxes"][check_key] = cmds.checkBox(label="", value=False, enable=False)
                cmds.text(label=label, align="left")
                cmds.button(label="Scan", height=24, command=lambda *_f, tk=tab_key: self.scan_namespaces(tk))
                cmds.button(label="Remove", height=24, command=lambda *_f, tk=tab_key: self.remove_namespaces(tk))
                cmds.setParent("..")
                continue
            if check_key == "placeholder":
                cmds.rowLayout(numberOfColumns=5, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)])
                t["check_boxes"][check_key] = cmds.checkBox(label="", value=False, enable=False)
                cmds.text(label=label, align="left")
                cmds.button(label="Run", height=24, command=lambda *_f, tk=tab_key, hk=handler: self._run_handler(tk, hk))
                cmds.text(label="Tolérance %", align="right")
                t["placeholder_tol"] = cmds.floatField(value=7.0, minValue=0.0, precision=2, width=70)
                cmds.setParent("..")
                continue
            if check_key == "vcolor":
                cmds.rowLayout(numberOfColumns=5, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8), (5, "both", 8)])
                t["check_boxes"][check_key] = cmds.checkBox(label="", value=False, enable=False)
                cmds.text(label=label, align="left")
                cmds.button(label="Run", height=24, command=lambda *_f, tk=tab_key, hk=handler: self._run_handler(tk, hk))
                cmds.button(label="Display", height=24, command=lambda *_f, tk=tab_key: self.display_vertex_colors(tk))
                cmds.button(label="Hide", height=24, command=lambda *_f, tk=tab_key: self.hide_vertex_colors(tk))
                cmds.setParent("..")
                continue
            if check_key == "design":
                cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
                t["check_boxes"][check_key] = cmds.checkBox(label="", value=False, changeCommand=lambda *_f, tk=tab_key: self.check_design_manual(tk))
                cmds.text(label=label, align="left")
                cmds.button(label="Mark as Reviewed", height=24, command=lambda *_f, tk=tab_key: self.mark_design_reviewed(tk))
                cmds.setParent("..")
                continue
            cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
            t["check_boxes"][check_key] = cmds.checkBox(label="", value=False, enable=False)
            cmds.text(label=label, align="left")
            cmds.button(label="Run", height=24, command=lambda *_f, tk=tab_key, hk=handler: self._run_handler(tk, hk))
            cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_texture_block(self, tab_key: str) -> None:
        cmds.frameLayout(label="4) Texture Sets / Contrôles visuels", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5)
        t = self.tab_ui[tab_key]
        t["texture_list"] = cmds.textScrollList(allowMultiSelection=True, height=160)
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        cmds.button(label="Hide Selected", height=24, command=lambda *_: self.set_texture_visibility(tab_key, False, True))
        cmds.button(label="Show Selected", height=24, command=lambda *_: self.set_texture_visibility(tab_key, True, True))
        cmds.button(label="Toggle Selected", height=24, command=lambda *_: self.toggle_selected_texture(tab_key))
        cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8)])
        cmds.button(label="Isolate Selected", height=24, command=lambda *_: self.isolate_selected_texture(tab_key))
        cmds.button(label="Show All", height=24, command=lambda *_: self.show_all_texture(tab_key))
        cmds.setParent("..")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_actions_block(self, tab_key: str, cfg: TabConfig) -> None:
        cmds.frameLayout(label="5) Actions globales", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        cmds.button(label=cfg.run_all_label, height=30, command=lambda *_: self.run_all_checks(tab_key))
        cmds.button(label="Clear Results", height=30, command=lambda *_: self.clear_results(tab_key))
        cmds.button(label="Save Report", height=30, command=lambda *_: self.save_report(tab_key))
        cmds.setParent("..")
        cmds.button(label="Isolate Meshes Without VColor", height=26, command=lambda *_: self.isolate_meshes_without_vcolor(tab_key))
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_results_block(self, tab_key: str) -> None:
        cmds.frameLayout(label="6) Résultats / Log", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True)
        self.tab_ui[tab_key]["results"] = cmds.textScrollList(allowMultiSelection=False, height=220, selectCommand=lambda *_: self.on_result_selected(tab_key))
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_notes_block(self, tab_key: str) -> None:
        cmds.frameLayout(label="7) Notes", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True)
        self.tab_ui[tab_key]["notes"] = cmds.scrollField(wordWrap=True, height=110, text="")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_summary_block(self, tab_key: str) -> None:
        cmds.frameLayout(label="8) Résumé", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True)
        self.tab_ui[tab_key]["summary"] = cmds.text(label="Pending checks", align="left", backgroundColor=(0.22, 0.22, 0.22))
        cmds.setParent("..")
        cmds.setParent("..")

    # ---------------- shared helpers ----------------
    def refresh_all_ui(self) -> None:
        for tab_key in self.tab_configs:
            self.refresh_file_labels(tab_key)
            self.refresh_root_ui(tab_key)
            self.refresh_checklist_ui(tab_key)

    def _short(self, node: str) -> str:
        return node.split("|")[-1]

    def _strip_ns(self, name: str) -> str:
        return name.split(":")[-1]

    def _ellipsize(self, text: str, max_len: int = MAX_UI_TEXT_LENGTH) -> str:
        if len(text) <= max_len:
            return text
        keep = (max_len - 3) // 2
        return f"{text[:keep]}...{text[-(max_len - 3 - keep):]}"

    def _is_placeholder_name(self, text: str) -> bool:
        return PLACEHOLDER_TOKEN in text.lower()

    def _check_done(self, tab_key: str, check_key: str, ok: bool) -> None:
        self.tab_check_states[tab_key][check_key] = "OK" if ok else "PENDING"
        self.refresh_checklist_ui(tab_key)

    def log(self, tab_key: str, level: str, category: str, message: str, objects: Optional[List[str]] = None) -> None:
        issue = ReviewIssue(level=level, category=category, message=message, objects=objects or [])
        self.tab_issues[tab_key].append(issue)
        idx = cmds.textScrollList(self.tab_ui[tab_key]["results"], q=True, numberOfItems=True) or 0
        prefix = {"INFO": "[INFO]", "WARNING": "[WARN]", "FAIL": "[FAIL]"}.get(level, "[INFO]")
        display = self._ellipsize(f"{prefix} {category}: {message}")
        cmds.textScrollList(self.tab_ui[tab_key]["results"], e=True, append=display)
        self.tab_result_index_to_objects[tab_key][idx + 1] = issue.objects

    def clear_results(self, tab_key: str) -> None:
        self.tab_issues[tab_key] = []
        self.tab_result_index_to_objects[tab_key] = {}
        cmds.textScrollList(self.tab_ui[tab_key]["results"], e=True, removeAll=True)
        self.refresh_checklist_ui(tab_key)

    def refresh_checklist_ui(self, tab_key: str) -> None:
        check_boxes = self.tab_ui[tab_key].get("check_boxes", {})
        for check_key, cb in check_boxes.items():
            cmds.checkBox(cb, e=True, value=self.tab_check_states[tab_key].get(check_key) == "OK")
        self.refresh_summary(tab_key)

    def refresh_summary(self, tab_key: str) -> None:
        checks = self.tab_check_states[tab_key]
        ok_count = sum(1 for v in checks.values() if v == "OK")
        pending = sum(1 for v in checks.values() if v == "PENDING")
        warns = sum(1 for i in self.tab_issues[tab_key] if i.level == "WARNING")
        fails = sum(1 for i in self.tab_issues[tab_key] if i.level == "FAIL")
        if fails:
            state, color = "FAIL", (0.35, 0.18, 0.18)
        elif warns:
            state, color = "WARNING", (0.35, 0.28, 0.16)
        elif pending == 0:
            state, color = "OK", (0.16, 0.32, 0.20)
        else:
            state, color = "IN PROGRESS", (0.22, 0.22, 0.22)
        text = f"Global: {state} | Checks OK: {ok_count}/{len(checks)} | Warnings: {warns} | Fails: {fails} | Pending: {pending}"
        cmds.text(self.tab_ui[tab_key]["summary"], e=True, label=text, backgroundColor=color)

    def on_result_selected(self, tab_key: str) -> None:
        selected = cmds.textScrollList(self.tab_ui[tab_key]["results"], q=True, selectIndexedItem=True) or []
        if not selected:
            return
        nodes = [n for n in self.tab_result_index_to_objects[tab_key].get(selected[0], []) if cmds.objExists(n)]
        if nodes:
            cmds.select(nodes, r=True)

    # ---------------- file scan/reference ----------------
    def pick_root_folder(self, tab_key: str) -> None:
        picked = cmds.fileDialog2(dialogStyle=2, fileMode=3, caption="Select Delivery Root Folder")
        if not picked:
            return
        self.tab_paths[tab_key]["root"] = picked[0]
        cmds.textFieldButtonGrp(self.tab_ui[tab_key]["root_field"], e=True, text=picked[0])

    def _detect_file_role(self, filename_lower: str) -> Optional[str]:
        if filename_lower.endswith(".ma") and "bakescene" in filename_lower:
            return "bakescene"
        if filename_lower.endswith(".ma") and "finalasset" in filename_lower:
            return "final_ma"
        if filename_lower.endswith(".ma") and "high" in filename_lower and "bakescene" not in filename_lower:
            return "high_ma"
        if filename_lower.endswith(".fbx") and "high" in filename_lower:
            return "high_fbx"
        if filename_lower.endswith(".fbx") and "low" in filename_lower:
            return "low_fbx"
        return None

    def scan_delivery_folder(self, tab_key: str) -> None:
        root = cmds.textFieldButtonGrp(self.tab_ui[tab_key]["root_field"], q=True, text=True).strip()
        if not root or not os.path.isdir(root):
            self.log(tab_key, "FAIL", "Scan", f"Root folder invalide: {root or '(vide)'}")
            return
        self.tab_paths[tab_key]["root"] = root
        all_found: Dict[str, List[str]] = {k: [] for k in self.tab_detected_files[tab_key]}
        for d, _, files in os.walk(root):
            for name in files:
                role = self._detect_file_role(name.lower())
                if role in all_found:
                    all_found[role].append(os.path.join(d, name))
        for k, arr in all_found.items():
            arr.sort()
            self.tab_detected_files[tab_key][k] = arr
            self._populate_file_menu(tab_key, k)
        self.refresh_file_labels(tab_key)
        self.log(tab_key, "INFO", "Scan", f"Scan terminé pour {self.tab_configs[tab_key].label}.")

    def _clear_menu(self, menu: str) -> None:
        for item in cmds.optionMenu(menu, q=True, itemListLong=True) or []:
            cmds.deleteUI(item)

    def _populate_file_menu(self, tab_key: str, file_key: str) -> None:
        menu = self.tab_ui[tab_key].get(f"{file_key}_menu")
        if not menu:
            return
        self._clear_menu(menu)
        files = self.tab_detected_files[tab_key][file_key]
        if not files:
            cmds.menuItem(label="-- Aucun --", parent=menu)
            self.tab_paths[tab_key][file_key] = ""
            return
        for path in files:
            cmds.menuItem(label=os.path.basename(path), parent=menu)
        cmds.optionMenu(menu, e=True, select=1)
        self.tab_paths[tab_key][file_key] = files[0]

    def refresh_file_labels(self, tab_key: str) -> None:
        for file_key, label, _ in self.tab_configs[tab_key].files:
            count = len(self.tab_detected_files[tab_key][file_key])
            if count == 0:
                txt = f"Aucun fichier pour {label}"
            elif count == 1:
                txt = f"1 fichier: {os.path.basename(self.tab_detected_files[tab_key][file_key][0])}"
            else:
                txt = f"{count} fichiers détectés. Sélectionnez le bon fichier."
            cmds.text(self.tab_ui[tab_key][f"{file_key}_status"], e=True, label=txt)

    def on_file_selected(self, tab_key: str, file_key: str) -> None:
        files = self.tab_detected_files[tab_key].get(file_key, [])
        if not files:
            return
        idx = (cmds.optionMenu(self.tab_ui[tab_key][f"{file_key}_menu"], q=True, select=True) or 1) - 1
        self.tab_paths[tab_key][file_key] = files[max(0, min(idx, len(files) - 1))]

    def reference_file(self, tab_key: str, file_key: str) -> None:
        path = self.tab_paths[tab_key].get(file_key, "")
        if not path or not os.path.exists(path):
            self.log(tab_key, "FAIL", "Reference", f"Fichier introuvable pour {file_key}.")
            return
        ns = self.reference_namespaces.get(file_key, f"{file_key}_File")
        try:
            if path.lower().endswith(".fbx"):
                try:
                    if not cmds.pluginInfo("fbxmaya", query=True, loaded=True):
                        cmds.loadPlugin("fbxmaya", quiet=True)
                except Exception:
                    pass
                cmds.file(path, reference=True, namespace=ns, options="v=0", type="FBX")
            else:
                cmds.file(path, reference=True, namespace=ns, ignoreVersion=True, mergeNamespacesOnClash=False)
            self.log(tab_key, "INFO", "Reference", f"Référence chargée: {os.path.basename(path)} ({ns})")
            self.auto_detect_roots(tab_key)
        except Exception as exc:
            self.log(tab_key, "FAIL", "Reference", f"Erreur de référence: {exc}")

    # ---------------- root detection ----------------
    def _collect_mesh_transforms(self, root: Optional[str] = None) -> List[str]:
        if root and cmds.objExists(root):
            shapes = cmds.listRelatives(root, allDescendents=True, fullPath=True, type="mesh") or []
            direct = cmds.listRelatives(root, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
            shapes += direct
        else:
            shapes = cmds.ls(type="mesh", long=True) or []
        out = []
        for s in shapes:
            if cmds.getAttr(s + ".intermediateObject"):
                continue
            p = cmds.listRelatives(s, p=True, fullPath=True) or []
            if p:
                out.append(p[0])
        return sorted(set(out))

    def _find_candidates(self, suffix_kind: str) -> List[str]:
        transforms = cmds.ls(type="transform", long=True) or []
        out: List[str] = []
        for node in transforms:
            base = self._strip_ns(self._short(node)).lower()
            if suffix_kind == "placeholder" and (base.endswith("_placeholder") or self._is_placeholder_name(base)):
                out.append(node)
            elif suffix_kind == "high" and base.endswith("_high") and not self._is_placeholder_name(base):
                out.append(node)
            elif suffix_kind == "low" and base.endswith("_low"):
                out.append(node)
            elif suffix_kind == "final" and (not base.endswith("_low") and not base.endswith("_high") and "placeholder" not in base):
                if self._collect_mesh_transforms(node):
                    out.append(node)
        return sorted(set(out), key=lambda n: len(self._collect_mesh_transforms(n)), reverse=True)

    def auto_detect_roots(self, tab_key: str) -> None:
        for root_key, _, suffix_kind in self.tab_configs[tab_key].roots:
            self.tab_detected_roots[tab_key][root_key] = self._find_candidates(suffix_kind)
        self.refresh_root_ui(tab_key)
        self.log(tab_key, "INFO", "RootDetect", f"Auto-detect roots terminé pour {self.tab_configs[tab_key].label}.")

    def refresh_root_ui(self, tab_key: str) -> None:
        for root_key, _, _ in self.tab_configs[tab_key].roots:
            menu = self.tab_ui[tab_key][f"{root_key}_menu"]
            self._clear_menu(menu)
            candidates = self.tab_detected_roots[tab_key][root_key]
            if not candidates:
                cmds.menuItem(label="Root non détecté", parent=menu)
                continue
            for node in candidates:
                cmds.menuItem(label=self._ellipsize(node, 80), parent=menu)
            cmds.optionMenu(menu, e=True, select=1)

    def get_selected_root(self, tab_key: str, root_key: str) -> Optional[str]:
        arr = self.tab_detected_roots[tab_key].get(root_key, [])
        if not arr:
            return None
        idx = (cmds.optionMenu(self.tab_ui[tab_key][f"{root_key}_menu"], q=True, select=True) or 1) - 1
        node = arr[max(0, min(idx, len(arr) - 1))]
        return node if cmds.objExists(node) else None

    def on_root_selected(self, tab_key: str, root_key: str) -> None:
        root = self.get_selected_root(tab_key, root_key)
        if root:
            self.log(tab_key, "INFO", "RootDetect", f"{root_key} sélectionné: {self._short(root)}", [root])

    def set_root_from_selection(self, tab_key: str, root_key: str) -> None:
        sel = cmds.ls(sl=True, long=True) or []
        if not sel:
            self.log(tab_key, "WARNING", "RootDetect", "Aucune sélection.")
            return
        arr = self.tab_detected_roots[tab_key][root_key]
        if sel[0] not in arr:
            arr.insert(0, sel[0])
        self.refresh_root_ui(tab_key)
        self.log(tab_key, "INFO", "RootDetect", f"{root_key} défini depuis sélection.", [sel[0]])

    # ---------------- checks ----------------
    def _run_handler(self, tab_key: str, handler: str) -> None:
        getattr(self, handler)(tab_key)

    def _mesh_key(self, mesh: str, root: Optional[str]) -> str:
        segs = [self._strip_ns(s) for s in mesh.split("|") if s]
        if root and cmds.objExists(root):
            rsegs = [self._strip_ns(s) for s in root.split("|") if s]
            if segs[: len(rsegs)] == rsegs:
                segs = segs[len(rsegs):]
        return "/".join(segs)

    def _mesh_sig(self, mesh: str) -> Tuple[int, int, int]:
        shape = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
        if not shape:
            return (0, 0, 0)
        s = shape[0]
        return (
            int(cmds.polyEvaluate(s, vertex=True) or 0),
            int(cmds.polyEvaluate(s, edge=True) or 0),
            int(cmds.polyEvaluate(s, face=True) or 0),
        )

    def _bbox_center(self, node: str) -> Tuple[float, float, float]:
        bb = cmds.exactWorldBoundingBox(node)
        return ((bb[0] + bb[3]) * 0.5, (bb[1] + bb[4]) * 0.5, (bb[2] + bb[5]) * 0.5)

    def _dist(self, a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5

    def _active_mesh_sets(self, tab_key: str) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for root_key, _, _ in self.tab_configs[tab_key].roots:
            root = self.get_selected_root(tab_key, root_key)
            if root:
                out[root_key] = self._collect_mesh_transforms(root)
        return out

    def check_compare(self, tab_key: str) -> None:
        scopes = self._active_mesh_sets(tab_key)
        if len(scopes) < 2:
            self.log(tab_key, "FAIL", "Compare", "Pas assez de roots valides pour comparer.")
            self._check_done(tab_key, "compare", False)
            return
        ref_name = list(scopes.keys())[0]
        ref_root = self.get_selected_root(tab_key, ref_name)
        ref = {self._mesh_key(m, ref_root): self._mesh_sig(m) for m in scopes[ref_name]}
        ok = True
        for scope_name, meshes in scopes.items():
            root = self.get_selected_root(tab_key, scope_name)
            current = {self._mesh_key(m, root): self._mesh_sig(m) for m in meshes}
            missing = sorted(set(ref) - set(current))
            extra = sorted(set(current) - set(ref))
            if missing:
                ok = False
                self.log(tab_key, "FAIL", "Compare", f"{scope_name}: meshes manquants ({len(missing)})")
            if extra:
                ok = False
                self.log(tab_key, "WARNING", "Compare", f"{scope_name}: meshes supplémentaires ({len(extra)})")
            for k in sorted(set(ref).intersection(current)):
                if ref[k] != current[k]:
                    ok = False
                    self.log(tab_key, "FAIL", "Compare", f"{scope_name}: topo différente sur {k}")
                    break
        if ok:
            self.log(tab_key, "INFO", "Compare", "Comparaison multi-sources OK.")
        self._check_done(tab_key, "compare", ok)

    def scan_namespaces(self, tab_key: str) -> None:
        ns = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        allowed = set(self.reference_namespaces.values())
        bad = [n for n in ns if n not in {":", "UI", "shared"} and n not in allowed and not any(n.startswith(a + ":") for a in allowed)]
        self.last_scanned_namespaces = sorted(set(bad))
        if bad:
            self.log(tab_key, "WARNING", "Namespaces", f"Namespaces non autorisés: {', '.join(self.last_scanned_namespaces[:8])}")
            self._check_done(tab_key, "namespaces", False)
        else:
            self.log(tab_key, "INFO", "Namespaces", "Aucun namespace non autorisé.")
            self._check_done(tab_key, "namespaces", True)

    def remove_namespaces(self, tab_key: str) -> None:
        if not self.last_scanned_namespaces:
            self.scan_namespaces(tab_key)
        removed = 0
        for ns in sorted(self.last_scanned_namespaces, key=lambda x: x.count(":"), reverse=True):
            if cmds.namespace(exists=ns):
                try:
                    cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
                    removed += 1
                except Exception:
                    pass
        self.log(tab_key, "INFO", "Namespaces", f"Namespaces supprimés: {removed}")
        self.scan_namespaces(tab_key)

    def check_placeholder(self, tab_key: str) -> None:
        roots = self.tab_detected_roots[tab_key]
        placeholder_key = next((k for k in roots if "placeholder" in k), None)
        if not placeholder_key:
            self.log(tab_key, "FAIL", "Placeholder", "Aucun root placeholder dans cet onglet.")
            self._check_done(tab_key, "placeholder", False)
            return
        ph = self.get_selected_root(tab_key, placeholder_key)
        primaries = [self.get_selected_root(tab_key, k) for k in roots if k != placeholder_key]
        primaries = [p for p in primaries if p]
        if not ph or not primaries:
            self.log(tab_key, "FAIL", "Placeholder", "Roots insuffisants pour Placeholder Match.")
            self._check_done(tab_key, "placeholder", False)
            return
        tol = cmds.floatField(self.tab_ui[tab_key].get("placeholder_tol"), q=True, value=True) if self.tab_ui[tab_key].get("placeholder_tol") else 7.0
        c0 = self._bbox_center(ph)
        ok = True
        for root in primaries:
            dist = self._dist(c0, self._bbox_center(root))
            if dist > tol:
                ok = False
                self.log(tab_key, "WARNING", "Placeholder", f"Décalage > tolérance ({dist:.3f}) entre placeholder et {self._short(root)}", [ph, root])
        if ok:
            self.log(tab_key, "INFO", "Placeholder", "Placeholder Match OK.")
        self._check_done(tab_key, "placeholder", ok)

    def check_topology(self, tab_key: str) -> None:
        meshes = sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr})
        if not meshes:
            self.log(tab_key, "FAIL", "Topology", "Aucun mesh dans le scope implicite.")
            self._check_done(tab_key, "topology", False)
            return
        problems = 0
        for mesh in meshes:
            try:
                ngons = cmds.polyInfo(mesh, faceToVertex=True) or []
                if any(len([t for t in line.split() if t.isdigit()]) - 1 > 4 for line in ngons[:200]):
                    problems += 1
            except Exception:
                continue
        if problems:
            self.log(tab_key, "WARNING", "Topology", f"Meshes avec faces potentiellement non-quad: {problems}")
            self._check_done(tab_key, "topology", False)
        else:
            self.log(tab_key, "INFO", "Topology", "Topology check OK.")
            self._check_done(tab_key, "topology", True)

    def _check_uv_set(self, tab_key: str, minimum_sets: int, check_key: str, label: str) -> None:
        meshes = sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr})
        bad = []
        for mesh in meshes:
            shape = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
            if not shape:
                continue
            uv_sets = cmds.polyUVSet(shape[0], q=True, allUVSets=True) or []
            if len(uv_sets) < minimum_sets:
                bad.append(mesh)
        if bad:
            self.log(tab_key, "FAIL", label, f"{len(bad)} mesh(es) sans setup UV requis.", bad[:20])
            self._check_done(tab_key, check_key, False)
        else:
            self.log(tab_key, "INFO", label, "Setup UV conforme.")
            self._check_done(tab_key, check_key, True)

    def check_uv01(self, tab_key: str) -> None:
        self._check_uv_set(tab_key, 1, "uv01", "UV01")

    def check_uv02(self, tab_key: str) -> None:
        self._check_uv_set(tab_key, 2, "uv02", "UV02")

    def _collect_texture_sets(self, tab_key: str, mode: str) -> Dict[str, Dict[str, Any]]:
        sets: Dict[str, Dict[str, Any]] = {}
        for scope, meshes in self._active_mesh_sets(tab_key).items():
            for mesh in meshes:
                if mode == "materials":
                    shapes = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
                    if not shapes:
                        continue
                    engines = cmds.listConnections(shapes[0], type="shadingEngine") or []
                    names = [self._strip_ns(e) for e in engines] or ["NoMaterial"]
                else:
                    names = [self._strip_ns(self._short(mesh).split("_")[0])]
                for n in names:
                    key = f"{scope}::{n}"
                    if key not in sets:
                        sets[key] = {"name": n, "scope": scope, "objects": []}
                    sets[key]["objects"].append(mesh)
        return sets

    def _apply_texture_list(self, tab_key: str, sets: Dict[str, Dict[str, Any]]) -> None:
        self.tab_texture_sets[tab_key] = sets
        self.tab_texture_map[tab_key] = {}
        list_ui = self.tab_ui[tab_key]["texture_list"]
        cmds.textScrollList(list_ui, e=True, removeAll=True)
        for key in sorted(sets):
            data = sets[key]
            label = f"{data['scope']} | {data['name']} | {len(data['objects'])} obj(s)"
            self.tab_texture_map[tab_key][label] = key
            cmds.textScrollList(list_ui, e=True, append=label)

    def check_texture_sets_materials(self, tab_key: str) -> None:
        sets = self._collect_texture_sets(tab_key, "materials")
        self._apply_texture_list(tab_key, sets)
        self.log(tab_key, "INFO", "TextureSets", f"Texture sets (Materials) détectés: {len(sets)}")
        self._check_done(tab_key, "tex_mats", len(sets) > 0)

    def check_texture_sets_groups(self, tab_key: str) -> None:
        sets = self._collect_texture_sets(tab_key, "groups")
        self._apply_texture_list(tab_key, sets)
        self.log(tab_key, "INFO", "TextureSets", f"Texture sets (Groups) détectés: {len(sets)}")
        self._check_done(tab_key, "tex_groups", len(sets) > 0)

    def _selected_texture_keys(self, tab_key: str) -> List[str]:
        selected = cmds.textScrollList(self.tab_ui[tab_key]["texture_list"], q=True, selectItem=True) or []
        return [self.tab_texture_map[tab_key][s] for s in selected if s in self.tab_texture_map[tab_key]]

    def set_texture_visibility(self, tab_key: str, visible: bool, selected_only: bool) -> None:
        keys = self._selected_texture_keys(tab_key) if selected_only else list(self.tab_texture_sets[tab_key].keys())
        for key in keys:
            for obj in self.tab_texture_sets[tab_key][key]["objects"]:
                if cmds.objExists(obj):
                    cmds.setAttr(obj + ".visibility", 1 if visible else 0)

    def toggle_selected_texture(self, tab_key: str) -> None:
        for key in self._selected_texture_keys(tab_key):
            for obj in self.tab_texture_sets[tab_key][key]["objects"]:
                if cmds.objExists(obj):
                    state = cmds.getAttr(obj + ".visibility")
                    cmds.setAttr(obj + ".visibility", 0 if state else 1)

    def isolate_selected_texture(self, tab_key: str) -> None:
        selected_objs: Set[str] = set()
        for key in self._selected_texture_keys(tab_key):
            selected_objs.update(self.tab_texture_sets[tab_key][key]["objects"])
        all_objs = {o for data in self.tab_texture_sets[tab_key].values() for o in data["objects"]}
        for obj in all_objs:
            if cmds.objExists(obj):
                cmds.setAttr(obj + ".visibility", 1 if obj in selected_objs else 0)

    def show_all_texture(self, tab_key: str) -> None:
        self.set_texture_visibility(tab_key, True, selected_only=False)

    def check_vertex_colors(self, tab_key: str) -> None:
        meshes = sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr})
        bad = []
        for mesh in meshes:
            shapes = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
            if not shapes:
                continue
            sets = cmds.polyColorSet(shapes[0], q=True, allColorSets=True) or []
            if not sets:
                bad.append(mesh)
        if bad:
            self.log(tab_key, "WARNING", "VertexColor", f"Meshes sans color set: {len(bad)}", bad[:20])
            self._check_done(tab_key, "vcolor", False)
        else:
            self.log(tab_key, "INFO", "VertexColor", "Vertex colors OK.")
            self._check_done(tab_key, "vcolor", True)

    def display_vertex_colors(self, tab_key: str) -> None:
        for mesh in sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr}):
            shapes = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
            for s in shapes:
                try:
                    cmds.setAttr(s + ".displayColors", 1)
                except Exception:
                    pass

    def hide_vertex_colors(self, tab_key: str) -> None:
        for mesh in sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr}):
            shapes = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
            for s in shapes:
                try:
                    cmds.setAttr(s + ".displayColors", 0)
                except Exception:
                    pass

    def isolate_meshes_without_vcolor(self, tab_key: str) -> None:
        missing = []
        for mesh in sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr}):
            shapes = cmds.listRelatives(mesh, s=True, ni=True, f=True, type="mesh") or []
            if not shapes:
                continue
            if not (cmds.polyColorSet(shapes[0], q=True, allColorSets=True) or []):
                missing.append(mesh)
        if not missing:
            self.log(tab_key, "INFO", "VertexColor", "Aucun mesh sans VColor.")
            return
        all_meshes = sorted({m for arr in self._active_mesh_sets(tab_key).values() for m in arr})
        for mesh in all_meshes:
            if cmds.objExists(mesh):
                cmds.setAttr(mesh + ".visibility", 1 if mesh in missing else 0)
        cmds.select(missing, r=True)
        self.log(tab_key, "WARNING", "VertexColor", f"Isolation de {len(missing)} mesh(es) sans VColor.", missing[:20])

    def check_design_manual(self, tab_key: str) -> None:
        state = cmds.checkBox(self.tab_ui[tab_key]["check_boxes"]["design"], q=True, value=True)
        self._check_done(tab_key, "design", state)
        if state:
            self.log(tab_key, "INFO", "DesignKit", "Design kit validé manuellement.")

    def mark_design_reviewed(self, tab_key: str) -> None:
        cmds.checkBox(self.tab_ui[tab_key]["check_boxes"]["design"], e=True, value=True)
        self.check_design_manual(tab_key)

    def check_bake_presence(self, tab_key: str) -> None:
        high = self.get_selected_root(tab_key, "bake_high_root")
        low = self.get_selected_root(tab_key, "bake_low_root")
        ok = bool(high and low)
        if ok:
            self.log(tab_key, "INFO", "BakeScene", "High et Low présents dans la Bake Scene.", [high, low])
        else:
            self.log(tab_key, "FAIL", "BakeScene", "High ou Low absent dans la Bake Scene.")
        self._check_done(tab_key, "presence", ok)

    def check_bake_alignment(self, tab_key: str) -> None:
        high = self.get_selected_root(tab_key, "bake_high_root")
        low = self.get_selected_root(tab_key, "bake_low_root")
        if not high or not low:
            self.log(tab_key, "FAIL", "BakeAlign", "Roots bake high/low manquants.")
            self._check_done(tab_key, "align", False)
            return
        d = self._dist(self._bbox_center(high), self._bbox_center(low))
        ok = d < 0.01
        self.log(tab_key, "INFO" if ok else "WARNING", "BakeAlign", f"Distance centre high/low: {d:.5f}", [high, low])
        self._check_done(tab_key, "align", ok)

    def check_naming_bake(self, tab_key: str) -> None:
        bad = []
        for key in ["bake_high_root", "bake_low_root"]:
            root = self.get_selected_root(tab_key, key)
            if not root:
                continue
            suffix = "_high" if "high" in key else "_low"
            for m in self._collect_mesh_transforms(root):
                if not self._strip_ns(self._short(m)).lower().endswith(suffix):
                    bad.append(m)
        ok = len(bad) == 0
        self.log(tab_key, "INFO" if ok else "FAIL", "Naming", "Naming bake conforme." if ok else f"Meshes mal nommés: {len(bad)}", bad[:20])
        self._check_done(tab_key, "naming", ok)

    def check_naming_final(self, tab_key: str) -> None:
        root = self.get_selected_root(tab_key, "final_root")
        if not root:
            self.log(tab_key, "FAIL", "Naming", "Final root non détecté.")
            self._check_done(tab_key, "naming", False)
            return
        bad = [m for m in self._collect_mesh_transforms(root) if self._strip_ns(self._short(m)).lower().endswith("_low")]
        ok = len(bad) == 0
        self.log(tab_key, "INFO" if ok else "FAIL", "Naming", "Naming final sans _low OK." if ok else f"Meshes avec suffix _low: {len(bad)}", bad[:20])
        self._check_done(tab_key, "naming", ok)

    def run_all_checks(self, tab_key: str) -> None:
        for check_key, _, handler in self.tab_configs[tab_key].checks:
            if check_key == "design":
                continue
            self._run_handler(tab_key, handler)
        self.log(tab_key, "INFO", "RunAll", "Exécution de tous les checks terminée.")

    def save_report(self, tab_key: str) -> None:
        root = self.tab_paths[tab_key].get("root") or cmds.workspace(q=True, rootDirectory=True)
        out = os.path.join(root, f"outsource_review_{tab_key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        payload = {
            "tab": tab_key,
            "time": datetime.now().isoformat(),
            "checks": self.tab_check_states[tab_key],
            "notes": cmds.scrollField(self.tab_ui[tab_key]["notes"], q=True, text=True),
            "issues": [issue.__dict__ for issue in self.tab_issues[tab_key]],
            "paths": self.tab_paths[tab_key],
        }
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        self.log(tab_key, "INFO", "Report", f"Report sauvegardé: {out}")


_TOOL: Optional[OutsourceReviewTool] = None


def show_outsource_review_tool() -> OutsourceReviewTool:
    global _TOOL
    _TOOL = OutsourceReviewTool()
    _TOOL.build()
    return _TOOL
