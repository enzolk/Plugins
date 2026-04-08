# -*- coding: utf-8 -*-
"""
High Poly Review Assistant (Maya)
---------------------------------
Production-oriented review helper for outsourcing High Poly deliveries.

Usage in Maya Script Editor (Python tab):
    import maya_highpoly_review.Outsource_Review_Script as ors
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
WINDOW_TITLE = "Outsource Review Script - High Poly v1"


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
            "ma": "",
            "fbx": "",
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
            "vertex_colors_checked": {"status": "PENDING", "mode": "AUTO"},
        }

    # --------------------------- UI BUILD ---------------------------
    def build(self) -> None:
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        self.ui["window"] = cmds.window(
            WINDOW_NAME,
            title=WINDOW_TITLE,
            sizeable=True,
            widthHeight=(760, 780),
        )
        cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

        self._build_file_section()
        self._build_checklist_section()
        self._build_action_section()
        self._build_results_section()
        self._build_notes_section()
        self._build_summary_section()

        cmds.showWindow(self.ui["window"])
        self.refresh_summary()
        self.refresh_checklist_ui()

    def _build_file_section(self) -> None:
        cmds.frameLayout(label="1) Fichiers & contexte", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        self.ui["ma_field"] = cmds.textFieldButtonGrp(
            label="High .ma",
            buttonLabel="Browse",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.pick_file("ma", "Maya ASCII (*.ma)")
        )
        cmds.button(label="Load MA (Open Scene)", height=28, command=lambda *_: self.load_ma_scene())

        self.ui["fbx_field"] = cmds.textFieldButtonGrp(
            label="High .fbx",
            buttonLabel="Browse",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.pick_file("fbx", "FBX (*.fbx)")
        )

        self.ui["fbx_mode"] = cmds.radioButtonGrp(
            label="FBX mode",
            labelArray2=["Import", "Reference"],
            numberOfRadioButtons=2,
            select=1,
        )
        cmds.button(label="Import / Reference FBX", height=28, command=lambda *_: self.load_fbx_into_scene())

        self.ui["placeholder_field"] = cmds.textFieldButtonGrp(
            label="Placeholder root",
            buttonLabel="From Selection",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.set_field_from_selection("placeholder_field")
        )
        self.ui["high_field"] = cmds.textFieldButtonGrp(
            label="High root",
            buttonLabel="From Selection",
            adjustableColumn=2,
            buttonCommand=lambda *_: self.set_field_from_selection("high_field")
        )

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_checklist_section(self) -> None:
        cmds.frameLayout(label="2) Checklist High Poly", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=2)

        self.ui["check_ma_fbx"] = cmds.checkBox(label="[AUTO] MA vs FBX comparés", value=False, enable=False)
        self.ui["check_ns"] = cmds.checkBox(label="[AUTO] Pas de namespaces", value=False, enable=False)
        self.ui["check_placeholder"] = cmds.checkBox(label="[AUTO] Placeholder vérifié", value=False, enable=False)
        self.ui["check_design"] = cmds.checkBox(
            label="[MANUAL] Design kit vérifié manuellement",
            value=False,
            changeCommand=lambda *_: self.on_manual_design_toggle(),
        )
        self.ui["check_topology"] = cmds.checkBox(label="[AUTO] Topologie vérifiée", value=False, enable=False)
        self.ui["check_texturesets"] = cmds.checkBox(label="[AUTO] Texture sets analysés", value=False, enable=False)
        self.ui["check_vtx"] = cmds.checkBox(label="[AUTO] Vertex colors vérifiées", value=False, enable=False)

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_action_section(self) -> None:
        cmds.frameLayout(label="3) Actions", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

        cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
        cmds.button(label="Compare MA vs FBX", height=28, command=lambda *_: self.compare_ma_vs_fbx())
        cmds.button(label="Scan Namespaces", height=28, command=lambda *_: self.scan_namespaces())
        cmds.button(label="Check Placeholder Match", height=28, command=lambda *_: self.check_placeholder_match())
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=3, adjustableColumn=3)
        cmds.button(label="Run Topology Checks", height=28, command=lambda *_: self.run_topology_checks())
        cmds.button(label="Analyze Texture Sets", height=28, command=lambda *_: self.analyze_texture_sets())
        cmds.button(label="Check Vertex Colors", height=28, command=lambda *_: self.check_vertex_colors())
        cmds.setParent("..")

        cmds.rowLayout(numberOfColumns=4, adjustableColumn=4)
        cmds.button(label="Run All High Checks", height=28, command=lambda *_: self.run_all_checks())
        cmds.button(label="Isolate meshes without VColor", height=28, command=lambda *_: self.isolate_meshes_without_vertex_color())
        cmds.button(label="Clear Results", height=28, command=lambda *_: self.clear_results())
        cmds.button(label="Save Review Report", height=28, command=lambda *_: self.save_report())
        cmds.setParent("..")

        cmds.setParent("..")
        cmds.setParent("..")

    def _build_results_section(self) -> None:
        cmds.frameLayout(label="4) Résultats", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["results_list"] = cmds.textScrollList(
            allowMultiSelection=False,
            height=230,
            selectCommand=lambda *_: self.on_result_selected(),
        )
        cmds.text(label="Tip: clique une ligne liée à des objets pour sélectionner en scène.")
        cmds.setParent("..")
        cmds.setParent("..")

    def _build_notes_section(self) -> None:
        cmds.frameLayout(label="5) Notes de review", collapsable=True, collapse=False, marginWidth=8)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        self.ui["notes_field"] = cmds.scrollField(wordWrap=True, height=120, text="")
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
        mapping = {
            "ma_fbx_compared": "check_ma_fbx",
            "no_namespaces": "check_ns",
            "placeholder_checked": "check_placeholder",
            "design_kit_checked": "check_design",
            "topology_checked": "check_topology",
            "texture_sets_analyzed": "check_texturesets",
            "vertex_colors_checked": "check_vtx",
        }
        for key, ctrl in mapping.items():
            is_checked = self.check_states[key]["status"] == "OK"
            cmds.checkBox(self.ui[ctrl], e=True, value=is_checked)

        self.refresh_summary()

    def set_check_status(self, check_key: str, status: str) -> None:
        self.check_states[check_key]["status"] = status
        self.refresh_checklist_ui()

    def set_field_from_selection(self, field_name: str) -> None:
        sel = cmds.ls(selection=True, long=True) or []
        if not sel:
            self.log("WARNING", "Selection", "Aucun objet sélectionné.")
            return
        cmds.textFieldButtonGrp(self.ui[field_name], e=True, text=sel[0])

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

    def pick_file(self, file_key: str, file_filter: str) -> None:
        picked = cmds.fileDialog2(fileFilter=file_filter, dialogStyle=2, fileMode=1)
        if not picked:
            return
        self.paths[file_key] = picked[0]
        cmds.textFieldButtonGrp(self.ui[f"{file_key}_field"], e=True, text=picked[0])

    def get_high_root(self) -> Optional[str]:
        root = cmds.textFieldButtonGrp(self.ui["high_field"], q=True, text=True).strip()
        if root and cmds.objExists(root):
            return root
        return None

    def _collect_mesh_transforms(self, root: Optional[str] = None) -> List[str]:
        if root and cmds.objExists(root):
            shapes = cmds.listRelatives(root, allDescendents=True, fullPath=True, type="mesh") or []
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

    # ----------------------------- Actions -----------------------------
    def load_ma_scene(self) -> None:
        path = cmds.textFieldButtonGrp(self.ui["ma_field"], q=True, text=True).strip()
        if not path:
            self.log("FAIL", "File", "Aucun chemin .ma renseigné.")
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

    def load_fbx_into_scene(self) -> None:
        path = cmds.textFieldButtonGrp(self.ui["fbx_field"], q=True, text=True).strip()
        if not path:
            self.log("FAIL", "File", "Aucun chemin .fbx renseigné.")
            return
        if not os.path.isfile(path):
            self.log("FAIL", "File", f"Fichier .fbx introuvable: {path}")
            return

        mode = cmds.radioButtonGrp(self.ui["fbx_mode"], q=True, select=True)
        namespace = self.context["fbx_namespace"]

        if cmds.namespace(exists=namespace):
            try:
                cmds.namespace(removeNamespace=namespace, mergeNamespaceWithRoot=True)
            except RuntimeError:
                self.log("WARNING", "FBX", f"Namespace {namespace} déjà présent, merge impossible automatiquement.")

        before = set(cmds.ls(long=True) or [])
        if mode == 1:
            cmds.file(path, i=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
            mode_label = "imported"
        else:
            cmds.file(path, reference=True, type="FBX", ignoreVersion=True, mergeNamespacesOnClash=False, namespace=namespace)
            mode_label = "referenced"

        after = set(cmds.ls(long=True) or [])
        new_nodes = sorted(list(after - before))
        self.context["fbx_nodes"] = new_nodes
        self.context["fbx_meshes"] = [n for n in new_nodes if cmds.nodeType(n) == "mesh"]

        self.paths["fbx"] = path
        self.log("INFO", "FBX", f"FBX {mode_label} ({len(self.context['fbx_meshes'])} meshes détectés).")

    def compare_ma_vs_fbx(self) -> None:
        high_root = self.get_high_root()

        all_meshes = self._collect_mesh_transforms(root=high_root)
        if not all_meshes:
            self.log("FAIL", "Compare", "Aucun mesh High détecté pour la comparaison.")
            self.set_check_status("ma_fbx_compared", "FAIL")
            return

        ma_meshes = [m for m in all_meshes if (":" not in m or self.context["fbx_namespace"] not in m)]
        fbx_meshes = [m for m in all_meshes if self.context["fbx_namespace"] + ":" in m]

        if not fbx_meshes:
            self.log("WARNING", "Compare", "Aucun mesh FBX en namespace de review détecté. Import/reference FBX conseillé.")

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
        namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []
        blocked = {"UI", "shared"}
        user_ns = [n for n in namespaces if n not in blocked]

        if not user_ns:
            self.log("INFO", "Namespace", "Aucun namespace utilisateur détecté.")
            self.set_check_status("no_namespaces", "OK")
            return

        total_objs = []
        for ns in user_ns:
            objs = cmds.ls(ns + ":*", long=True) or []
            total_objs.extend(objs)
            self.log("WARNING", "Namespace", f"Namespace détecté: {ns} ({len(objs)} objets)", objs[:50])

        self.log("FAIL", "Namespace", f"{len(user_ns)} namespace(s) utilisateur détecté(s).", total_objs[:200])
        self.set_check_status("no_namespaces", "FAIL")

    def check_placeholder_match(self) -> None:
        placeholder = cmds.textFieldButtonGrp(self.ui["placeholder_field"], q=True, text=True).strip()
        high = cmds.textFieldButtonGrp(self.ui["high_field"], q=True, text=True).strip()

        if not placeholder or not cmds.objExists(placeholder):
            self.log("FAIL", "Placeholder", "Placeholder root invalide/non défini.")
            self.set_check_status("placeholder_checked", "FAIL")
            return
        if not high or not cmds.objExists(high):
            self.log("FAIL", "Placeholder", "High root invalide/non défini.")
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
        self.log("INFO", "Placeholder", f"Pivot delta: {tuple(round(h_piv[i]-p_piv[i], 4) for i in range(3))}")

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

        if non_manifold_items:
            self.log("FAIL", "Topology", f"Non-manifold détecté sur {len(non_manifold_items)} mesh(es).", non_manifold_items)
            fail_count += 1
        if lamina_items:
            self.log("FAIL", "Topology", f"Lamina faces détectées sur {len(lamina_items)} mesh(es).", lamina_items)
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
            self.log("WARNING", "Topology", f"Noms dupliqués potentiels (paths DAG ambigus): {len(duplicate_short_names)}", duplicate_short_names[:100])
            warn_count += 1

        # Non-mesh nodes under high root
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
