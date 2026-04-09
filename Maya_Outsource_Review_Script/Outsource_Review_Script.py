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
from typing import Dict, List, Optional, Tuple

import maya.cmds as cmds


WINDOW_NAME = "highPolyReviewAssistantWin"
WINDOW_TITLE = "Outsource Review Script"
ROOT_SUFFIXES = {
    "high": "_high",
    "placeholder": "_placeholder",
}


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
        }

        self.detected_files: Dict[str, List[str]] = {
            "ma": [],
            "fbx": [],
        }

        self.detected_roots: Dict[str, List[str]] = {
            "high": [],
            "placeholder": [],
        }

        self.context = {
            "fbx_namespace": "fbxReview",
            "fbx_nodes": [],
            "fbx_meshes": [],
        }

        self.check_states = {
            "ma_fbx_compared": {"status": "PENDING", "mode": "AUTO"},
            "no_namespaces": {"status": "PENDING", "mode": "AUTO"},
            "placeholder_checked": {"status": "PENDING", "mode": "AUTO"},
            "design_kit_checked": {"status": "PENDING", "mode": "MANUAL"},
            "topology_checked": {"status": "PENDING", "mode": "AUTO"},
            "texture_sets_analyzed": {"status": "PENDING", "mode": "AUTO"},
            "texture_sets_groups_analyzed": {"status": "PENDING", "mode": "AUTO"},
            "vertex_colors_checked": {"status": "PENDING", "mode": "AUTO"},
        }

        self.check_ui_map = {
            "ma_fbx_compared": "check_ma_fbx",
            "no_namespaces": "check_ns",
            "placeholder_checked": "check_placeholder",
            "design_kit_checked": "check_design",
            "topology_checked": "check_topology",
            "texture_sets_analyzed": "check_texturesets",
            "texture_sets_groups_analyzed": "check_texturesets_groups",
            "vertex_colors_checked": "check_vtx",
        }

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
        self._build_checklist_section()
        self._build_global_action_section()
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
        cmds.frameLayout(label="1) Importation / Fichiers", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        self.ui["root_field"] = cmds.textFieldButtonGrp(
            label="Root Folder",
            buttonLabel="Browse",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.pick_root_folder(),
        )
        cmds.button(label="Scan Delivery Folder", height=30, command=lambda *_: self.scan_delivery_folder())

        cmds.separator(style="in")

        cmds.text(label="MA Found", align="left")
        self.ui["ma_status"] = cmds.text(label="Aucun .ma détecté", align="left")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6)])
        self.ui["ma_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("ma"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["ma_menu"])
        cmds.button(label="Load MA (Open Scene)", height=28, command=lambda *_: self.load_ma_scene())
        cmds.setParent("..")

        cmds.text(label="FBX Found", align="left")
        self.ui["fbx_status"] = cmds.text(label="Aucun .fbx détecté", align="left")
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=1, columnAttach=[(1, "both", 0), (2, "both", 6), (3, "both", 6)])
        self.ui["fbx_menu"] = cmds.optionMenu(changeCommand=lambda *_: self.on_detected_file_selected("fbx"))
        cmds.menuItem(label="-- Aucun --", parent=self.ui["fbx_menu"])
        cmds.button(label="Import FBX", height=28, command=lambda *_: self.load_fbx_into_scene(as_reference=False))
        cmds.button(label="Reference FBX", height=28, command=lambda *_: self.load_fbx_into_scene(as_reference=True))
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

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_checklist_section(self) -> None:
        cmds.frameLayout(label="2) Checks", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        self._build_check_row("check_ma_fbx", "MA vs FBX", self.compare_ma_vs_fbx)

        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_ns"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Pas de namespaces", align="left")
        cmds.button(label="Scan Namespaces", height=26, command=lambda *_: self.scan_namespaces())
        cmds.button(label="Remove Namespaces", height=26, command=lambda *_: self.remove_namespaces())
        cmds.setParent("..")

        self._build_check_row("check_placeholder", "Placeholder match", self.check_placeholder_match)
        self._build_check_row("check_topology", "Topologie", self.run_topology_checks)

        cmds.rowLayout(numberOfColumns=4, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8), (4, "both", 8)])
        self.ui["check_texturesets"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Texture sets", align="left")
        cmds.button(label="Run Texture Sets", height=26, command=lambda *_: self.analyze_texture_sets())
        cmds.button(label="Run Texture Sets (Based on Groups)", height=26, command=lambda *_: self.analyze_texture_sets_by_groups())
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui["check_texturesets_groups"] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label="Texture sets (based on groups)", align="left")
        cmds.button(label="Run Group Mode", height=26, command=lambda *_: self.analyze_texture_sets_by_groups())
        cmds.setParent("..")

        self._build_check_row("check_vtx", "Vertex Colors", self.check_vertex_colors)

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

    def _build_check_row(self, check_key_ui: str, label: str, command) -> None:
        cmds.rowLayout(numberOfColumns=3, adjustableColumn=2, columnAttach=[(1, "both", 0), (2, "both", 8), (3, "both", 8)])
        self.ui[check_key_ui] = cmds.checkBox(label="", value=False, enable=False)
        cmds.text(label=label, align="left")
        cmds.button(label=f"Run {label}", height=26, command=lambda *_: command())
        cmds.setParent("..")

    def _build_global_action_section(self) -> None:
        cmds.frameLayout(label="3) Actions globales", collapsable=True, collapse=False, marginWidth=8)
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
        ma_count = len(self.detected_files["ma"])
        fbx_count = len(self.detected_files["fbx"])

        ma_text = "Aucun .ma détecté"
        if ma_count == 1:
            ma_text = f"1 fichier détecté: {os.path.basename(self.detected_files['ma'][0])}"
        elif ma_count > 1:
            ma_text = f"{ma_count} fichiers .ma détectés. Sélectionnez le bon fichier."

        fbx_text = "Aucun .fbx détecté"
        if fbx_count == 1:
            fbx_text = f"1 fichier détecté: {os.path.basename(self.detected_files['fbx'][0])}"
        elif fbx_count > 1:
            fbx_text = f"{fbx_count} fichiers .fbx détectés. Sélectionnez le bon fichier."

        cmds.text(self.ui["ma_status"], e=True, label=ma_text)
        cmds.text(self.ui["fbx_status"], e=True, label=fbx_text)

    def on_detected_file_selected(self, file_key: str) -> None:
        files = self.detected_files[file_key]
        if not files:
            self.paths[file_key] = ""
            return

        index = cmds.optionMenu(self.ui[f"{file_key}_menu"], q=True, select=True) - 1
        index = max(0, min(index, len(files) - 1))
        self.paths[file_key] = files[index]
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
        found_ma: List[str] = []
        found_fbx: List[str] = []

        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                name_lower = filename.lower()
                full_path = os.path.join(dirpath, filename)
                if name_lower.endswith("_high.ma"):
                    found_ma.append(full_path)
                elif name_lower.endswith("_high.fbx"):
                    found_fbx.append(full_path)

        found_ma.sort()
        found_fbx.sort()

        self.detected_files["ma"] = found_ma
        self.detected_files["fbx"] = found_fbx

        self._populate_file_option_menu("ma")
        self._populate_file_option_menu("fbx")
        self.refresh_detected_file_labels()

        if not found_ma:
            self.log("WARNING", "Scan", "Aucun fichier *_HIGH.ma ou *_high.ma trouvé.")
        else:
            self.log("INFO", "Scan", f"{len(found_ma)} fichier(s) .ma High détecté(s).")

        if not found_fbx:
            self.log("WARNING", "Scan", "Aucun fichier *_HIGH.fbx ou *_high.fbx trouvé.")
        else:
            self.log("INFO", "Scan", f"{len(found_fbx)} fichier(s) .fbx High détecté(s).")

    def _populate_root_option_menu(self, root_key: str) -> None:
        menu = self.ui[f"{root_key}_root_menu"]
        items = self.detected_roots[root_key]
        self._clear_option_menu(menu)

        if not items:
            label = "High root non détecté" if root_key == "high" else "Placeholder root non détecté"
            cmds.menuItem(label=label, parent=menu)
            return

        for node in items:
            cmds.menuItem(label=node, parent=menu)

        cmds.optionMenu(menu, edit=True, select=1)

    def refresh_root_ui(self) -> None:
        self._populate_root_option_menu("high")
        self._populate_root_option_menu("placeholder")

    def on_root_selection_changed(self, root_key: str) -> None:
        root = self.get_detected_root(root_key)
        if root:
            self.log("INFO", "RootDetect", f"{root_key.capitalize()} root sélectionné: {root}")

    def get_detected_root(self, root_key: str) -> Optional[str]:
        candidates = self.detected_roots[root_key]
        if not candidates:
            return None

        index = cmds.optionMenu(self.ui[f"{root_key}_root_menu"], q=True, select=True) - 1
        index = max(0, min(index, len(candidates) - 1))
        root = candidates[index]
        return root if cmds.objExists(root) else None

    def set_root_from_selection(self, root_key: str) -> None:
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            self.log("WARNING", "Selection", "Aucun objet sélectionné.")
            return

        current = self.detected_roots[root_key][:]
        if sel[0] not in current:
            current.insert(0, sel[0])
        self.detected_roots[root_key] = current
        self.refresh_root_ui()
        self.log("INFO", "RootDetect", f"{root_key.capitalize()} root défini depuis la sélection: {sel[0]}")

    def _candidate_root_score(self, node: str) -> Tuple[int, int, int]:
        descendants = cmds.listRelatives(node, allDescendents=True, fullPath=True) or []
        mesh_shapes = cmds.listRelatives(node, allDescendents=True, fullPath=True, type="mesh") or []
        mesh_shapes = [m for m in mesh_shapes if not cmds.getAttr(m + ".intermediateObject")]

        depth = node.count("|")
        has_shape = 1 if (cmds.listRelatives(node, shapes=True, noIntermediate=True, fullPath=True) or []) else 0
        return (len(mesh_shapes), len(descendants) + has_shape, -depth)

    def _find_root_candidates(self, suffix_key: str) -> List[str]:
        suffix = ROOT_SUFFIXES[suffix_key]
        transforms = cmds.ls(type="transform", long=True) or []
        valid = []
        for node in transforms:
            short_name = node.split("|")[-1]
            if short_name.lower().endswith(suffix):
                valid.append(node)

        valid = sorted(valid, key=lambda x: self._candidate_root_score(x), reverse=True)
        return valid

    def auto_detect_scene_roots(self) -> None:
        high_candidates = self._find_root_candidates("high")
        placeholder_candidates = self._find_root_candidates("placeholder")

        self.detected_roots["high"] = high_candidates
        self.detected_roots["placeholder"] = placeholder_candidates
        self.refresh_root_ui()

        if high_candidates:
            self.log("INFO", "RootDetect", f"High root détecté: {high_candidates[0]}")
            if len(high_candidates) > 1:
                self.log("WARNING", "RootDetect", f"Plusieurs High roots détectés ({len(high_candidates)}). Sélection manuelle possible.")
        else:
            self.log("WARNING", "RootDetect", "High root non détecté.")

        if placeholder_candidates:
            self.log("INFO", "RootDetect", f"Placeholder root détecté: {placeholder_candidates[0]}")
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

    def _namespace_from_node(self, node: str) -> str:
        short = node.split("|")[-1]
        if ":" not in short:
            return ""
        return short.rsplit(":", 1)[0]

    def _node_is_in_namespace(self, node: str, namespace: str) -> bool:
        ns = self._namespace_from_node(node)
        return ns == namespace or ns.startswith(namespace + ":")

    def _collect_mesh_transforms_in_namespace(self, namespace: str) -> List[str]:
        if not namespace:
            return []
        shapes = cmds.ls(namespace + ":*", type="mesh", long=True) or []
        transforms = []
        for shape in shapes:
            if cmds.getAttr(shape + ".intermediateObject"):
                continue
            parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parent:
                transforms.append(parent[0])
        return sorted(set(transforms))

    def _get_scan_namespaces(self) -> List[str]:
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        blocked = {":", "UI", "shared", self.context["fbx_namespace"]}
        return sorted([n for n in namespaces if n not in blocked])

    # ----------------------------- Actions -----------------------------
    def load_ma_scene(self) -> None:
        path = self.paths.get("ma", "")
        if not path:
            self.log("FAIL", "File", "Aucun fichier .ma sélectionné (scan requis).")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier .ma introuvable: {path}")
            return

        should_open = cmds.confirmDialog(
            title="Open MA",
            message="Ouvrir ce .ma et remplacer la scène courante ?",
            button=["Open", "Cancel"],
            defaultButton="Open",
            cancelButton="Cancel",
            dismissString="Cancel",
        )
        if should_open != "Open":
            self.log("INFO", "File", "Ouverture .ma annulée.")
            return

        cmds.file(path, open=True, force=True)
        self.paths["ma"] = path
        self.log("INFO", "File", f"Scène .ma ouverte: {path}")

        # Auto-detect roots right after scene open.
        self.auto_detect_scene_roots()

    def load_fbx_into_scene(self, as_reference: bool = False) -> None:
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
        if as_reference:
            cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
            mode_label = "referenced"
        else:
            cmds.file(path, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
            mode_label = "imported"

        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["fbx_nodes"] = new_nodes
        self.context["fbx_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]

        self.paths["fbx"] = path
        self.log("INFO", "FBX", f"FBX {mode_label} ({len(self.context['fbx_meshes'])} meshes détectés).")

    def compare_ma_vs_fbx(self) -> None:
        high_root = self.get_high_root()
        review_ns = self.context["fbx_namespace"]

        ma_source_meshes = self._collect_mesh_transforms(root=high_root)
        if not ma_source_meshes:
            self.log("FAIL", "Compare", "Aucun mesh High détecté pour la comparaison.")
            self.set_check_status("ma_fbx_compared", "FAIL")
            return

        ma_meshes = [m for m in ma_source_meshes if not self._node_is_in_namespace(m, review_ns)]
        fbx_meshes = self._collect_mesh_transforms_in_namespace(review_ns)

        if not fbx_meshes:
            self.log(
                "WARNING",
                "Compare",
                f"Aucun mesh FBX détecté dans le namespace '{review_ns}'. Vérifiez l'action Reference FBX/Import FBX.",
            )
            self.set_check_status("ma_fbx_compared", "PENDING")
            return

        ma_sigs = sorted([self._mesh_signature(m) for m in ma_meshes])
        fbx_sigs = sorted([self._mesh_signature(m) for m in fbx_meshes])

        self.log("INFO", "Compare", f"MA meshes: {len(ma_meshes)} | FBX meshes: {len(fbx_meshes)}")

        if ma_sigs == fbx_sigs and fbx_sigs:
            self.log("INFO", "Compare", "Signatures topo globales cohérentes entre MA et FBX.")
            self.set_check_status("ma_fbx_compared", "OK")
        else:
            self.log("WARNING", "Compare", "Différences détectées entre MA et FBX (counts/signatures). Vérification visuelle requise.")
            self.set_check_status("ma_fbx_compared", "PENDING")

    def scan_namespaces(self) -> None:
        user_ns = self._get_scan_namespaces()

        if not user_ns:
            self.log("INFO", "Namespace", "Aucun namespace indésirable détecté (fbxReview ignoré volontairement).")
            self.set_check_status("no_namespaces", "OK")
            return

        total_objs = []
        for ns in user_ns:
            objs = cmds.ls(ns + ":*", long=True) or []
            total_objs.extend(objs)
            self.log("WARNING", "Namespace", f"Namespace détecté: {ns} ({len(objs)} objets)", objs[:50])

        self.log("FAIL", "Namespace", f"{len(user_ns)} namespace(s) utilisateur détecté(s).", total_objs[:200])
        self.set_check_status("no_namespaces", "FAIL")

    def remove_namespaces(self) -> None:
        removable = self._get_scan_namespaces()
        if not removable:
            self.log("INFO", "Namespace", "Aucun namespace à supprimer (fbxReview préservé).")
            self.set_check_status("no_namespaces", "OK")
            return

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
            self.log("INFO", "Namespace", f"Namespaces supprimés (merge vers root): {len(removed)}", removed)

        if failed:
            for ns, err in failed:
                self.log("WARNING", "Namespace", f"Suppression impossible pour {ns}: {err}")
            self.set_check_status("no_namespaces", "FAIL")
        else:
            self.log("INFO", "Namespace", "Suppression des namespaces indésirables terminée (fbxReview conservé).")
            self.set_check_status("no_namespaces", "OK")

    def check_placeholder_match(self) -> None:
        placeholder = self.get_placeholder_root()
        high = self.get_high_root()

        if not placeholder or not cmds.objExists(placeholder):
            self.log("FAIL", "Placeholder", "Placeholder root invalide/non détecté.")
            self.set_check_status("placeholder_checked", "FAIL")
            return
        if not high or not cmds.objExists(high):
            self.log("FAIL", "Placeholder", "High root invalide/non détecté.")
            self.set_check_status("placeholder_checked", "FAIL")
            return

        p_bb = cmds.exactWorldBoundingBox(placeholder)
        h_bb = cmds.exactWorldBoundingBox(high)
        p_dim = (p_bb[3] - p_bb[0], p_bb[4] - p_bb[1], p_bb[5] - p_bb[2])
        h_dim = (h_bb[3] - h_bb[0], h_bb[4] - h_bb[1], h_bb[5] - h_bb[2])

        p_piv = cmds.xform(placeholder, q=True, ws=True, rotatePivot=True)
        h_piv = cmds.xform(high, q=True, ws=True, rotatePivot=True)

        ratio = tuple((h_dim[i] / p_dim[i]) if p_dim[i] else 0.0 for i in range(3))

        self.log("INFO", "Placeholder", f"Placeholder dims: {tuple(round(v, 4) for v in p_dim)}")
        self.log("INFO", "Placeholder", f"High dims: {tuple(round(v, 4) for v in h_dim)}")
        self.log("INFO", "Placeholder", f"Scale ratio High/Placeholder: {tuple(round(v, 4) for v in ratio)}")
        self.log("INFO", "Placeholder", f"Pivot delta: {tuple(round(h_piv[i] - p_piv[i], 4) for i in range(3))}")

        tolerance = 0.05
        if all(abs(r - 1.0) <= tolerance for r in ratio if r != 0.0):
            self.log("INFO", "Placeholder", "Dimensions globales proches du placeholder (tolérance 5%).")
            self.set_check_status("placeholder_checked", "OK")
        else:
            self.log("WARNING", "Placeholder", "Écart de proportions détecté (au-delà de 5%). Vérifier visuellement.", [placeholder, high])
            self.set_check_status("placeholder_checked", "PENDING")

    def run_topology_checks(self) -> None:
        high_root = self.get_high_root()
        meshes = self._collect_mesh_transforms(root=high_root)
        if not meshes:
            self.log("FAIL", "Topology", "Aucun mesh trouvé pour les checks topologie.")
            self.set_check_status("topology_checked", "FAIL")
            return

        self.log("INFO", "Topology", f"Meshes analysés: {len(meshes)}")

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

        duplicate_short_names = [n for n in (cmds.ls(type="transform", long=True) or []) if "|" in n.split(":")[-1]]

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
        if duplicate_short_names:
            self.log(
                "WARNING",
                "Topology",
                f"Noms dupliqués potentiels (paths DAG ambigus): {len(duplicate_short_names)} — plusieurs objets partagent le même nom court.",
                duplicate_short_names[:100],
            )
            warn_count += 1

        if high_root:
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

    def analyze_texture_sets(self) -> None:
        high_root = self.get_high_root()
        meshes = self._collect_mesh_transforms(root=high_root)
        if not meshes:
            self.log("FAIL", "TextureSets", "Aucun mesh trouvé pour l'analyse texture sets.")
            self.set_check_status("texture_sets_analyzed", "FAIL")
            return

        mat_to_meshes: Dict[str, List[str]] = {}
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

        materials = sorted(mat_to_meshes.keys())
        self.log("INFO", "TextureSets", f"Texture sets potentiels (matériaux distincts): {len(materials)}")
        for mat in materials:
            self.log("INFO", "TextureSets", f"{mat}: {len(mat_to_meshes[mat])} mesh(es)", mat_to_meshes[mat][:150])

        if "<NO_MATERIAL>" in mat_to_meshes or "<UNBOUND_SURFACESHADER>" in mat_to_meshes:
            self.log("WARNING", "TextureSets", "Des meshes sans matériau valide ont été détectés.")
            self.set_check_status("texture_sets_analyzed", "PENDING")
        else:
            self.set_check_status("texture_sets_analyzed", "OK")
        self.set_check_status("texture_sets_groups_analyzed", "PENDING")

    def analyze_texture_sets_by_groups(self) -> None:
        high_root = self.get_high_root()
        if not high_root or not cmds.objExists(high_root):
            self.log("FAIL", "TextureSetsGroups", "High root invalide/non détecté.")
            self.set_check_status("texture_sets_groups_analyzed", "FAIL")
            return

        direct_children = cmds.listRelatives(high_root, children=True, fullPath=True, type="transform") or []
        candidate_groups = []
        for child in direct_children:
            child_meshes = cmds.listRelatives(child, allDescendents=True, fullPath=True, type="mesh") or []
            if child_meshes:
                candidate_groups.append(child)

        self.log("INFO", "TextureSetsGroups", f"High root analysé : {high_root}")
        if candidate_groups:
            self.log("INFO", "TextureSetsGroups", "Sous-groupes directs détectés :", candidate_groups)
            self.log("INFO", "TextureSetsGroups", f"Nombre de texture sets détectés (based on groups) : {len(candidate_groups)}")
            self.set_check_status("texture_sets_groups_analyzed", "OK")
        else:
            self.log("WARNING", "TextureSetsGroups", "Aucun sous-groupe direct avec mesh détecté sous le High root.")
            self.set_check_status("texture_sets_groups_analyzed", "PENDING")

    def check_vertex_colors(self) -> None:
        high_root = self.get_high_root()
        meshes = self._collect_mesh_transforms(root=high_root)
        if not meshes:
            self.log("FAIL", "VertexColor", "Aucun mesh trouvé pour le check vertex colors.")
            self.set_check_status("vertex_colors_checked", "FAIL")
            return

        with_vc = []
        without_vc = []

        for m in meshes:
            shapes = cmds.listRelatives(m, shapes=True, noIntermediate=True, fullPath=True) or []
            if not shapes:
                continue
            shape = shapes[0]
            color_sets = cmds.polyColorSet(shape, query=True, allColorSets=True) or []
            if color_sets:
                with_vc.append(m)
            else:
                without_vc.append(m)

        self.log("INFO", "VertexColor", f"Meshes avec vertex colors: {len(with_vc)}", with_vc[:150])
        self.log("INFO", "VertexColor", f"Meshes sans vertex colors: {len(without_vc)}", without_vc[:150])

        if without_vc:
            self.log("WARNING", "VertexColor", "Certains meshes n'ont pas de vertex color set.", without_vc)
            self.set_check_status("vertex_colors_checked", "PENDING")
        else:
            self.log("INFO", "VertexColor", "Tous les meshes analysés possèdent au moins un color set.")
            self.set_check_status("vertex_colors_checked", "OK")

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
        self.analyze_texture_sets()
        self.analyze_texture_sets_by_groups()
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
