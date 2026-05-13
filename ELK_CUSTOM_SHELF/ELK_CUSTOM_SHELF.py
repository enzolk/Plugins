# -*- coding: utf-8 -*-
"""ELK UI Minimal Adaptive Shelf - Maya Dockable / Auto Launch.

Automatically switches to a horizontal shelf layout only when the panel is
wider than tall and its height is 250 px or less. Otherwise it uses the
vertical grid/list layout.
"""
import traceback
import os
import re
import json
from pathlib import Path
import maya.cmds as cmds
import maya.mel as mel
from maya import OpenMayaUI as omui
try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2 import QtSvg
    from shiboken2 import wrapInstance
except Exception:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6 import QtSvg
    from shiboken6 import wrapInstance

WINDOW_NAME = "ELK_UI_Minimal_Adaptive"
WORKSPACE_NAME = WINDOW_NAME + "WorkspaceControl"
SECOND_INSTANCE_WORKSPACE_PREFIX = WINDOW_NAME + "WorkspaceControlSecond"
OPTIONVAR_MAX_HEIGHT = "ELK_UI_MaxHeightPx"
OPTIONVAR_UI_SCALE_BTN_TEXT_H = "ELK_UI_ScaleBtnTextH"
OPTIONVAR_UI_SCALE_BTN_TEXT_V = "ELK_UI_ScaleBtnTextV"
OPTIONVAR_UI_SCALE_BTN_ICON_H = "ELK_UI_ScaleBtnIconH"
OPTIONVAR_UI_SCALE_BTN_ICON_V = "ELK_UI_ScaleBtnIconV"
OPTIONVAR_UI_SCALE_BTN_SHORT_H = "ELK_UI_ScaleBtnShortH"
OPTIONVAR_UI_SCALE_BTN_SHORT_V = "ELK_UI_ScaleBtnShortV"
OPTIONVAR_UI_SCALE_CAT_TEXT_H = "ELK_UI_ScaleCatTextH"
OPTIONVAR_UI_SCALE_CAT_TEXT_V = "ELK_UI_ScaleCatTextV"
OPTIONVAR_UI_SCALE_CAT_ICON_H = "ELK_UI_ScaleCatIconH"
OPTIONVAR_UI_SCALE_CAT_ICON_V = "ELK_UI_ScaleCatIconV"
OPTIONVAR_LAYOUT_DEBUG_LOGS = "ELK_UI_EnableLayoutDebugLogs"
OPTIONVAR_HCAT_WIDTHS = "ELK_UI_HorizontalCategoryWidths"
LEGACY_SHELF_ITEMS = [{'category': 'Tools', 'label': 'ShortCuts', 'tooltip': 'For each unique shortcut press, it:\n\n    Detects the shortcut.\n    Resolves possible actions.\n    Observes Maya command output right after the shortcut.\n    Infers the executed action by matching executed commands to possible actions.\n    Stores executed action ? shortcut links in a persistent table.', 'source': 'python', 'command': 'import maya_shortcut_logger\nmaya_shortcut_logger.open_shortcut_logger_ui()'}, {'category': 'Tools', 'label': 'Edge Loop', 'tooltip': 'Insert Edge Loop', 'source': 'mel', 'command': '//insert edgeloop relative distance \nSplitEdgeRingTool; \npolySelectEditCtx -e -splitType 1 -insertWithEdgeFlow 0 \npolySelectEditContext; '}, {'category': 'Tools', 'label': 'EdgF', 'tooltip': 'Insert Edge Loop', 'source': 'mel', 'command': '//insert edgeloop relative distance \nSplitEdgeRingTool; \npolySelectEditCtx -e -splitType 1 -insertWithEdgeFlow 1 \npolySelectEditContext; '}, {'category': 'Tools', 'label': 'Draw', 'tooltip': 'Quad Draw', 'source': 'mel', 'command': 'QuadDrawTool'}, {'category': 'Tools', 'label': 'SphereCube', 'tooltip': 'Create a sphere from a cube', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef create_quad_sphere_ui():\n    """\n    Creates a UI for the Quad Sphere Generator.\n    """\n    window_name = "quadSphereWindow"\n    \n    if cmds.window(window_name, exists=True):\n        cmds.deleteUI(window_name)\n    \n    cmds.window(window_name, title="Quad Sphere Generator", widthHeight=(300, 200))\n    cmds.columnLayout(adjustableColumn=True)\n    \n    # Sphere Radius Slider\n    cmds.floatSliderGrp(\'sphereRadiusSlider\', label="Sphere Radius", field=True, minValue=0.1, maxValue=100, value=30, step=0.1)\n    \n    # Smooth Divisions Slider\n    cmds.intSliderGrp(\'smoothDivisionsSlider\', label="Smooth Divisions", field=True, minValue=0, maxValue=6, value=3)\n    \n    # UV Mapping Checkbox\n    cmds.checkBox(\'uvMappingCheckbox\', label="Generate UVs", value=True)\n    \n    # Generate Button\n    cmds.button(label="Generate Quad Sphere", command=generate_quad_sphere)\n    \n    cmds.showWindow(window_name)\n\ndef generate_quad_sphere(*args):\n    """\n    Generates a quad sphere based on user input from the UI.\n    """\n    # Retrieve values from UI\n    sphere_radius = cmds.floatSliderGrp(\'sphereRadiusSlider\', query=True, value=True)\n    smooth_divisions = cmds.intSliderGrp(\'smoothDivisionsSlider\', query=True, value=True)\n    generate_uvs = cmds.checkBox(\'uvMappingCheckbox\', query=True, value=True)\n    \n    # Calculate cube size\n    coefficient_value = 2.3  # Recommended coefficient\n    cube_size = sphere_radius * coefficient_value\n    \n    # Create a poly cube\n    cube = cmds.polyCube(width=cube_size, height=cube_size, depth=cube_size, name="quadSphereCube")[0]\n    \n    # Apply smooth divisions\n    for _ in range(smooth_divisions):\n        cmds.polySmooth(cube, method=0, divisions=1, smoothUVs=1)\n    \n    # Create a poly sphere for reference\n    sphere = cmds.polySphere(radius=sphere_radius, subdivisionsX=20, subdivisionsY=20, name="quadSphereReference")[0]\n    \n    # Transfer vertex positions from the sphere to the cube\n    cmds.select([sphere, cube])\n    cmds.transferAttributes(pos=1)\n    \n    # Delete history and the reference sphere\n    cmds.delete(cube, constructionHistory=True)\n    cmds.delete(sphere)\n    \n    # Rename the cube to the final quad sphere\n    quad_sphere = cmds.rename(cube, "quadSphere")\n    \n    # Generate UVs if selected\n    if generate_uvs:\n        cmds.select(quad_sphere)\n        cmds.unfold()\n        cmds.layoutUV(quad_sphere, layoutMethod=2)\n    \n    # Inform the user\n    cmds.inViewMessage(amg=\'Quad Sphere <hl>created successfully</hl>.\', pos=\'midCenter\', fade=True)\n\n# Run the UI\ncreate_quad_sphere_ui()\n'}, {'category': 'Tools', 'label': 'BoundingBox', 'tooltip': 'import maya.cmds as cmds\n\n# Define a function to fill the selection in Maya\ndef fillSelection():\n    # Get the current selection\n    sel = cmds.ls(selection=True)\n    \n    # If there is nothing selected, do nothing\n    if not sel:\n        return\n    \n    # Get the bounding box of the current selection\n    boundingBox = cmds.exactWorldBoundingBox(sel)\n    \n    # Create a cube with the same dimensions as the bounding box\n    cube = cmds.polyCube(w=boundingBox[3]-boundingBox[0], h=boundingBox[4]-bo', 'source': 'python', 'command': 'import maya.cmds as cmds\n\n# Define a function to fill the selection in Maya\ndef fillSelection():\n    # Get the current selection\n    sel = cmds.ls(selection=True)\n    \n    # If there is nothing selected, do nothing\n    if not sel:\n        return\n    \n    # Get the bounding box of the current selection\n    boundingBox = cmds.exactWorldBoundingBox(sel)\n    \n    # Create a cube with the same dimensions as the bounding box\n    cube = cmds.polyCube(w=boundingBox[3]-boundingBox[0], h=boundingBox[4]-boundingBox[1], d=boundingBox[5]-boundingBox[2])\n    \n    # Position the cube at the center of the bounding box\n    cmds.move(boundingBox[0]+(boundingBox[3]-boundingBox[0])/2, boundingBox[1]+(boundingBox[4]-boundingBox[1])/2, boundingBox[2]+(boundingBox[5]-boundingBox[2])/2)\n\n# Call the function to fill the selection\nfillSelection()\n'}, {'category': 'Tools', 'label': 'CreaCurve', 'tooltip': 'Create A curve Between Two selected vertices', 'source': 'python', 'command': 'import maya.api.OpenMaya as om\nimport maya.cmds as cmds\n\ndef get_selected_vertices():\n    sel = om.MGlobal.getActiveSelectionList()\n    positions = []\n\n    for i in range(sel.length()):\n        dagPath, component = sel.getComponent(i)\n        if component.apiType() == om.MFn.kMeshVertComponent:\n            mfnMesh = om.MFnMesh(dagPath)\n            indices = om.MFnSingleIndexedComponent(component).getElements()\n            for index in indices:\n                pos = mfnMesh.getPoint(index, om.MSpace.kWorld)\n                positions.append(om.MVector(pos))\n\n    return positions\n\ndef create_bezier_curve(p0, p1):\n    direction = p1 - p0\n    length = direction.length()\n\n    p0_tangent = p0 + direction.normal() * (length * 0.25)\n    p1_tangent = p1 - direction.normal() * (length * 0.25)\n\n    bezier_points = [\n        (p0.x, p0.y, p0.z),\n        (p0_tangent.x, p0_tangent.y, p0_tangent.z),\n        (p1_tangent.x, p1_tangent.y, p1_tangent.z),\n        (p1.x, p1.y, p1.z)\n    ]\n\n    cmds.curve(p=bezier_points, degree=3)\n\ndef bezier_between_selected_vertices():\n    verts = get_selected_vertices()\n    if len(verts) != 2:\n        om.MGlobal.displayWarning("Veuillez slectionner exactement 2 vertex.")\n        return\n\n    create_bezier_curve(verts[0], verts[1])\n\n# Lancer la fonction principale\nbezier_between_selected_vertices()\n'}, {'category': 'Tools', 'label': 'AddPoint', 'tooltip': 'Add Curve Point Quickly', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport re\n\ndef insert_knot_rebuild():\n    sel = cmds.ls(sl=True, fl=True)\n    if not sel or len(sel) != 1 or ".cv[" not in sel[0]:\n        cmds.warning("Veuillez slectionner un seul CV sur une courbe.")\n        return\n\n    # Extraire le nom de la courbe et l\'index du CV\n    match = re.match(r"(.+)\\.cv\\[(\\d+)\\]", sel[0])\n    if not match:\n        cmds.warning("Nom de CV invalide.")\n        return\n\n    curve = match.group(1)\n    index = int(match.group(2))\n\n    # Obtenir la liste des CV actuels\n    cvs = cmds.ls(f"{curve}.cv[*]", fl=True)\n    positions = [cmds.pointPosition(cv, world=True) for cv in cvs]\n    num_cvs = len(positions)\n\n    # Dterminer les deux points entre lesquels insrer\n    if index < num_cvs - 1:\n        i1, i2 = index, index + 1\n    elif index > 0:\n        i1, i2 = index - 1, index\n    else:\n        cmds.warning("Impossible d\'insrer un point ici.")\n        return\n\n    # Calculer le point milieu\n    mid = [(a + b) / 2.0 for a, b in zip(positions[i1], positions[i2])]\n\n    # Crer nouvelle liste de points avec le point insr\n    new_positions = positions[:i2] + [mid] + positions[i2:]\n\n    # Obtenir degr et nom de forme\n    degree = cmds.getAttr(curve + ".degree")\n    shape = cmds.listRelatives(curve, shapes=True)[0]\n\n    # Supprimer lancienne courbe\n    cmds.delete(curve)\n\n    # Crer nouvelle courbe avec mme nom\n    new_curve = cmds.curve(p=new_positions, degree=degree, name=curve)\n    print(f"Nouvelle courbe cre avec point insr entre CV[{i1}] et CV[{i2}]")\n\n# Excuter\ninsert_knot_rebuild()\n'}, {'category': 'Object', 'label': 'World_A', 'tooltip': "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == '...", 'source': 'python', 'command': "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == 'moveSuperContext':\n   \n    tool = 'Move'\n    mode = cmds.manipMoveContext(tool, q=1, m=1)\n    if mode == 0:\n        cmds.manipMoveContext(tool, e=1, m=2)\n    elif mode == 2:\n        cmds.manipMoveContext(tool, e=1, m=2)\n    else:\n        cmds.manipMoveContext(tool, e=1, m=2)\n \nif ctx == 'RotateSuperContext':\n   \n    tool = 'Rotate'\n    mode = cmds.manipRotateContext(tool, q=1, m=1)\n   \n    if mode == 0:\n        cmds.manipRotateContext(tool, e=1, m=1)\n    elif mode == 1:\n        cmds.manipRotateContext(tool, e=1, m=1)\n    else:\n        cmds.manipRotateContext(tool, e=1, m=1)\n \nif ctx == 'scaleSuperContext':\n   \n    tool = 'Scale'\n    mode = cmds.manipScaleContext(tool, q=1, m=1)\n   \n    if mode == 0:\n        cmds.manipScaleContext(tool, e=1, m=2)\n    elif mode == 2:\n        cmds.manipScaleContext(tool, e=1, m=2)\n    else:\n        cmds.manipScaleContext(tool, e=1, m=2)"}, {'category': 'Object', 'label': 'Obj_A', 'tooltip': "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == '...", 'source': 'python', 'command': "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == 'moveSuperContext':\n   \n    tool = 'Move'\n    mode = cmds.manipMoveContext(tool, q=1, m=1)\n    if mode == 0:\n        cmds.manipMoveContext(tool, e=1, m=0)\n    elif mode == 2:\n        cmds.manipMoveContext(tool, e=1, m=0)\n    else:\n        cmds.manipMoveContext(tool, e=1, m=0)\n \nif ctx == 'RotateSuperContext':\n   \n    tool = 'Rotate'\n    mode = cmds.manipRotateContext(tool, q=1, m=1)\n   \n    if mode == 0:\n        cmds.manipRotateContext(tool, e=1, m=0) \n    elif mode == 1:\n        cmds.manipRotateContext(tool, e=1, m=0) \n    else:\n        cmds.manipRotateContext(tool, e=1, m=0) \n \nif ctx == 'scaleSuperContext':\n   \n    tool = 'Scale'\n    mode = cmds.manipScaleContext(tool, q=1, m=1)\n   \n    if mode == 0:\n        cmds.manipScaleContext(tool, e=1, m=0)\n    elif mode == 2:\n        cmds.manipScaleContext(tool, e=1, m=0)\n    else:\n        cmds.manipScaleContext(tool, e=1, m=0)"}, {'category': 'Object', 'label': 'Comp_A', 'tooltip': "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == '...", 'source': 'python', 'command': "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == 'moveSuperContext':\n   \n    tool = 'Move'\n    mode = cmds.manipMoveContext(tool, q=1, m=1)\n    if mode == 0:\n        cmds.manipMoveContext(tool, e=1, m=9)\n    elif mode == 2:\n        cmds.manipMoveContext(tool, e=1, m=9)\n    else:\n        cmds.manipMoveContext(tool, e=1, m=9)\n \nif ctx == 'RotateSuperContext':\n   \n    tool = 'Rotate'\n    mode = cmds.manipRotateContext(tool, q=1, m=1)\n   \n    if mode == 0:\n        cmds.manipRotateContext(tool, e=1, m=9)\n    elif mode == 1:\n        cmds.manipRotateContext(tool, e=1, m=9)\n    else:\n        cmds.manipRotateContext(tool, e=1, m=9)\n \nif ctx == 'scaleSuperContext':\n   \n    tool = 'Scale'\n    mode = cmds.manipScaleContext(tool, q=1, m=1)\n   \n    if mode == 0:\n        cmds.manipScaleContext(tool, e=1, m=9)\n    elif mode == 2:\n        cmds.manipScaleContext(tool, e=1, m=9)\n    else:\n        cmds.manipScaleContext(tool, e=1, m=9)"}, {'category': 'Sculpting', 'label': 'Freeze', 'tooltip': 'Freeze selected components', 'source': 'python', 'command': "import maya.cmds as mc\n\ndef freeze_selected_components():\n    getSel = getFrozenSelection()\n    if getSel:\n        for i in getSel[0]:\n            mc.setAttr('{}.freeze[{}]'.format(getSel[1], i), True)\n        freezeVpRefresh()\n\ndef getFrozenSelection():\n    getSel = mc.polyListComponentConversion(ff=True, fe=True, fv=True, tv=True)\n    if getSel:\n        getSel = mc.ls(getSel, fl=True)\n        getIndices = [int(x.split('[')[1].split(']')[0]) for x in getSel]\n        getTransform = getSel[0].split('.')[0]\n        return getIndices, getTransform\n    return None\n\ndef freezeVpRefresh():\n    if mc.contextInfo('sculptMeshCacheContext', ex=True):\n        if mc.currentCtx() == 'sculptMeshCacheContext':\n            mc.setToolTo('selectSuperContext')\n            mc.setToolTo('sculptMeshCacheContext')\n        else:\n            mc.setToolTo('sculptMeshCacheContext')\n\n# Run the script to freeze the selected components\nfreeze_selected_components()\n"}, {'category': 'Sculpting', 'label': 'Unfreeze', 'tooltip': 'Unfreeze Selected components', 'source': 'python', 'command': "import maya.cmds as mc\n\ndef unfreeze_selected_components():\n    getSel = getFrozenSelection()\n    if getSel:\n        for i in getSel[0]:\n            mc.setAttr('{}.freeze[{}]'.format(getSel[1], i), False)\n        freezeVpRefresh()\n\ndef getFrozenSelection():\n    getSel = mc.polyListComponentConversion(ff=True, fe=True, fv=True, tv=True)\n    if getSel:\n        getSel = mc.ls(getSel, fl=True)\n        getIndices = [int(x.split('[')[1].split(']')[0]) for x in getSel]\n        getTransform = getSel[0].split('.')[0]\n        return getIndices, getTransform\n    return None\n\ndef freezeVpRefresh():\n    if mc.contextInfo('sculptMeshCacheContext', ex=True):\n        if mc.currentCtx() == 'sculptMeshCacheContext':\n            mc.setToolTo('selectSuperContext')\n            mc.setToolTo('sculptMeshCacheContext')\n        else:\n            mc.setToolTo('sculptMeshCacheContext')\n\n# Run the script to unfreeze the selected components\nunfreeze_selected_components()"}, {'category': 'Sculpting', 'label': 'Curve Sculpt', 'tooltip': 'Store selected vertices, then select a NURBS curve and move vertices to the closest points along the curve.', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.api.OpenMaya as om\n\n# ---------------------------------------------------------------------------\n# Globals\n# ---------------------------------------------------------------------------\n\n# Liste de sets :\n# chaque entre = {"curve": curveTransformName, "verts": [vtx components]}\nstored_sets = []\n\n\n# ---------------------------------------------------------------------------\n# Utils\n# ---------------------------------------------------------------------------\n\ndef get_dag_path(obj):\n    """\n    Returns an MDagPath pointing to the nurbsCurve shape of the given object.\n    """\n    sel = om.MSelectionList()\n    sel.add(obj)\n    dag_path = sel.getDagPath(0)\n\n    if dag_path.node().hasFn(om.MFn.kTransform):\n        try:\n            dag_path.extendToShape()\n        except RuntimeError:\n            pass\n\n    return dag_path\n\n\ndef ensure_transform(node):\n    """\n    S\'assure qu\'on a un transform (pas juste le shape).\n    """\n    if not cmds.objExists(node):\n        return None\n    if cmds.nodeType(node) == "transform":\n        return node\n    parent = cmds.listRelatives(node, parent=True, fullPath=True)\n    return parent[0] if parent else node\n\n\ndef find_closest_point_on_curve(curve, point, sample_rate=100):\n    """\n    Trouve le point le plus proche sur une curve par sampling.\n    """\n    dag_path = get_dag_path(curve)\n    curve_fn = om.MFnNurbsCurve(dag_path)\n\n    closest_point = None\n    min_distance = float(\'inf\')\n    start_param, end_param = curve_fn.knotDomain\n\n    for i in range(sample_rate + 1):\n        t = start_param + (end_param - start_param) * (float(i) / float(sample_rate))\n        curve_point = curve_fn.getPointAtParam(t, om.MSpace.kWorld)\n        distance = om.MPoint(point).distanceTo(curve_point)\n\n        if distance < min_distance:\n            min_distance = distance\n            closest_point = curve_point\n\n    return closest_point\n\n\ndef move_vertices_to_curve(curve, vertices, sample_rate=100):\n    """\n    Dplace chaque vertex de \'vertices\' vers le point le plus proche sur \'curve\'.\n    """\n    for vert in vertices:\n        try:\n            vert_pos = cmds.pointPosition(vert, world=True)\n        except RuntimeError:\n            cmds.warning("Impossible de rcuprer la position de : {}".format(vert))\n            continue\n\n        closest_point = find_closest_point_on_curve(curve, vert_pos, sample_rate)\n        if closest_point and isinstance(closest_point, om.MPoint):\n            try:\n                cmds.move(closest_point.x, closest_point.y, closest_point.z,\n                          vert, worldSpace=True, absolute=True)\n            except Exception as e:\n                cmds.warning("chec du dplacement du vertex {} : {}".format(vert, e))\n        else:\n            cmds.warning("Impossible de dterminer un point proche sur la courbe pour : {}".format(vert))\n\n\n# ---------------------------------------------------------------------------\n# Grouping des edges en sets connects\n# ---------------------------------------------------------------------------\n\ndef parse_index_from_component(comp):\n    """\n    Ex: \'pCube1.vtx[12]\' -> 12\n    """\n    if \'[\' not in comp or \']\' not in comp:\n        return None\n    inside = comp[comp.find(\'[\') + 1:comp.find(\']\')]\n    try:\n        return int(inside.split(\':\')[0])\n    except ValueError:\n        return None\n\n\ndef group_edges_into_sets(edges):\n    """\n    edges : liste de composants edge (pCube1.e[10], etc.)\n    Retourne une liste de listes : chaque sous-liste = un set d\'edges connects.\n    On gre les meshes sparment (pas de sets mlangeant plusieurs meshes).\n    """\n    edge_sets = []\n\n    # 1) Regrouper par mesh\n    mesh_to_edges = {}\n    for e in edges:\n        long_e = cmds.ls(e, long=True)[0]\n        mesh = long_e.split(\'.\')[0]\n        mesh_to_edges.setdefault(mesh, []).append(long_e)\n\n    # 2) Pour chaque mesh, on dcoupe en composants connects\n    for mesh, mesh_edges in mesh_to_edges.items():\n        # Maps temporaires\n        edge_to_verts = {}\n        vertex_to_edges = {}\n\n        # Pr-calcul : quels vertices pour chaque edge\n        for edge in mesh_edges:\n            verts = cmds.polyListComponentConversion(edge, toVertex=True)\n            verts = cmds.ls(verts, flatten=True) or []\n            v_indices = []\n\n            for v in verts:\n                idx = parse_index_from_component(v)\n                if idx is None:\n                    continue\n                v_indices.append(idx)\n                vertex_to_edges.setdefault(idx, []).append(edge)\n\n            edge_to_verts[edge] = v_indices\n\n        unvisited = set(mesh_edges)\n\n        # BFS / DFS pour trouver les composants connects\n        while unvisited:\n            start = next(iter(unvisited))\n            unvisited.remove(start)\n            component = [start]\n            queue = [start]\n\n            while queue:\n                current = queue.pop(0)\n                for v_idx in edge_to_verts.get(current, []):\n                    for neighbor in vertex_to_edges.get(v_idx, []):\n                        if neighbor in unvisited:\n                            unvisited.remove(neighbor)\n                            queue.append(neighbor)\n                            component.append(neighbor)\n\n            edge_sets.append(component)\n\n    return edge_sets\n\n\n# ---------------------------------------------------------------------------\n# STEP 1  Crer les curves, rebuild, stocker les sets de verts\n# ---------------------------------------------------------------------------\n\ndef create_curves_and_store_vertices(spans=6, degree=3):\n    """\n    -  partir d\'une slection d\'edges (possiblement plusieurs lots)\n    - Regroupe en sets d\'edges connects\n    - Pour chaque set :\n        * cre une curve (polyToCurve)\n        * rebuildCurve (spans, degree)\n        * delete history + freeze\n        * convertit ce set d\'edges en vertices\n        * stocke {curve, verts} dans stored_sets\n    - Slectionne toutes les curves cres pour dition\n    """\n    global stored_sets\n    stored_sets = []  # reset\n\n    # Rcuprer la slection d\'edges\n    edge_sel = cmds.ls(selection=True, flatten=True)\n    if not edge_sel:\n        cmds.warning("Veuillez d\'abord slectionner au moins un edge.")\n        return\n\n    edge_sel = cmds.filterExpand(edge_sel, sm=32) or []\n    if not edge_sel:\n        cmds.warning("La slection doit contenir des edges de polygone.")\n        return\n\n    # Regrouper en sets d\'edges connects\n    edge_sets = group_edges_into_sets(edge_sel)\n    if not edge_sets:\n        cmds.warning("Aucun set d\'edges valide trouv.")\n        return\n\n    all_curves = []\n\n    for edge_set in edge_sets:\n        # 1) Convertir ce set d\'edges en vertices (et stocker)\n        verts = cmds.polyListComponentConversion(edge_set, toVertex=True)\n        verts = cmds.ls(verts, flatten=True) or []\n        if not verts:\n            cmds.warning("Impossible de convertir un set d\'edges en vertices.")\n            continue\n\n        # 2) Crer la curve pour ce set\n        cmds.select(edge_set, r=True)\n        try:\n            curve_list = cmds.polyToCurve(form=2, degree=1, conformToSmoothMeshPreview=0)\n        except RuntimeError as e:\n            cmds.warning("chec de polyToCurve sur un set d\'edges : {}".format(e))\n            continue\n\n        if not curve_list:\n            cmds.warning("polyToCurve n\'a pas cr de courbe pour un set d\'edges.")\n            continue\n\n        curve = ensure_transform(curve_list[0])\n\n        # 3) Rebuild la curve\n        try:\n            rebuild_result = cmds.rebuildCurve(curve,\n                                               ch=1, rpo=1, rt=0, end=1,\n                                               kr=0, kcp=0, kep=1, kt=0,\n                                               s=spans, d=degree, tol=0.01)\n        except RuntimeError as e:\n            cmds.warning("chec de rebuildCurve : {}".format(e))\n            continue\n\n        if isinstance(rebuild_result, (list, tuple)):\n            curve = ensure_transform(rebuild_result[0])\n        else:\n            curve = ensure_transform(rebuild_result)\n\n        if not curve:\n            cmds.warning("Impossible de rcuprer le transform de la courbe rebuild.")\n            continue\n\n        # 4) Delete history + freeze\n        try:\n            cmds.delete(curve, ch=True)\n            cmds.makeIdentity(curve, apply=True, t=1, r=1, s=1, n=0, pn=1)\n        except RuntimeError as e:\n            cmds.warning("Problme delete history / freeze : {}".format(e))\n\n        # 5) Stocker ce set\n        stored_sets.append({\n            "curve": curve,\n            "verts": verts\n        })\n        all_curves.append(curve)\n\n    if not stored_sets:\n        cmds.warning("Aucun set de courbe/vertices n\'a pu tre cr.")\n        return\n\n    # Slectionner toutes les curves pour les modifier si besoin\n    cmds.select(all_curves)\n\n    cmds.inViewMessage(\n        assistMessage=\'Curves created for each edge set. Edit them if needed, then use Step 2 to project & auto-delete.\',\n        position=\'midCenter\',\n        fade=True\n    )\n\n\n# ---------------------------------------------------------------------------\n# STEP 2  Projeter tous les sets + supprimer leurs curves\n# ---------------------------------------------------------------------------\n\ndef project_all_stored_sets(sample_rate=100):\n    """\n    Pour chaque set stock :\n      - projette ses vertices sur sa curve\n      - supprime la curve\n    """\n    global stored_sets\n\n    if not stored_sets:\n        cmds.warning("Aucun set stock. Lance d\'abord Step 1.")\n        return\n\n    for data in stored_sets:\n        curve = data.get("curve")\n        verts = data.get("verts") or []\n\n        if not curve or not cmds.objExists(curve):\n            cmds.warning("Courbe introuvable pour un set, ignor.")\n            continue\n\n        if not verts:\n            cmds.warning("Vertices manquants pour un set, ignor.")\n            continue\n\n        move_vertices_to_curve(curve, verts, sample_rate=sample_rate)\n\n        # Supprimer la curve aprs projection\n        try:\n            cmds.delete(curve)\n        except:\n            pass\n\n    stored_sets = []\n\n    cmds.select(clear=True)\n    cmds.inViewMessage(\n        assistMessage=\'All stored vertex sets projected to their curves. Curves auto-deleted.\',\n        position=\'midCenter\',\n        fade=True\n    )\n\n\n# ---------------------------------------------------------------------------\n# One-click  Step1 + Step2\n# ---------------------------------------------------------------------------\n\ndef one_click_project(spans=6, degree=3, sample_rate=100):\n    """\n    Workflow full auto :\n    - Cre les curves et stocke les sets (pour chaque groupe dedges connects)\n    - Projette chaque set sur sa curve\n    - Supprime les curves\n    """\n    create_curves_and_store_vertices(spans=spans, degree=degree)\n    if stored_sets:\n        project_all_stored_sets(sample_rate=sample_rate)\n\n\n# ---------------------------------------------------------------------------\n# UI\n# ---------------------------------------------------------------------------\n\ndef ui_step1(*_):\n    spans = cmds.intSliderGrp("projSpansField", q=True, value=True)\n    create_curves_and_store_vertices(spans=spans, degree=3)\n\n\ndef ui_step2(*_):\n    sample_rate = cmds.intSliderGrp("projSampleField", q=True, value=True)\n    project_all_stored_sets(sample_rate=sample_rate)\n\n\ndef ui_one_click(*_):\n    spans = cmds.intSliderGrp("projSpansField", q=True, value=True)\n    sample_rate = cmds.intSliderGrp("projSampleField", q=True, value=True)\n    one_click_project(spans=spans, degree=3, sample_rate=sample_rate)\n\n\ndef show_project_ui():\n    if cmds.window("projCurveWin", exists=True):\n        cmds.deleteUI("projCurveWin")\n\n    win = cmds.window("projCurveWin",\n                      title="Project Vertices to Curves (multi edge sets)",\n                      sizeable=False)\n\n    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")\n\n    cmds.intSliderGrp("projSpansField",\n                      label="Rebuild spans",\n                      field=True,\n                      minValue=1,\n                      maxValue=50,\n                      value=6)\n\n    cmds.intSliderGrp("projSampleField",\n                      label="Sample rate",\n                      field=True,\n                      minValue=10,\n                      maxValue=500,\n                      value=100)\n\n    cmds.separator(h=10, style="in")\n\n    cmds.button(label="Step 1  Create curves & store vertex sets",\n                height=30,\n                command=ui_step1)\n\n    cmds.button(label="Step 2  Project all sets + auto-delete curves",\n                height=30,\n                command=ui_step2)\n\n    cmds.separator(h=10, style="in")\n\n    cmds.button(label="One-click  Create, project & auto-delete (all sets)",\n                height=30,\n                command=ui_one_click)\n\n    cmds.setParent("..")\n    cmds.showWindow(win)\n\n\nshow_project_ui()\n'}, {'category': 'Sculpting', 'label': 'ProSeparate', 'tooltip': 'Separate', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef separate_and_rename_simple():\n    # Variable to store the initial face selection\n    saved_faces = []\n    original_object = None\n\n    # Check if the selection is a face selection\n    selected_faces = cmds.ls(selection=True, fl=True)\n    if selected_faces and ".f[" in selected_faces[0]:\n        # Save the face selection\n        saved_faces = selected_faces\n\n        # Extract the object name from the selected face\n        original_object = selected_faces[0].split(".f[")[0]\n        \n        # Perform polyChipOff to separate the faces\n        cmds.polyChipOff(selected_faces, keepFacesTogether=True)\n        \n        # Switch to object selection mode and select the object\n        cmds.selectMode(object=True)\n        cmds.select(original_object)\n    else:\n        # Get the selected objects (if no faces were selected)\n        selected_objects = cmds.ls(selection=True, type=\'transform\')\n        if not selected_objects:\n            cmds.error("No objects selected.")\n            return\n        original_object = selected_objects[0]\n\n    # Proceed with separation and renaming\n    separated_parts = cmds.polySeparate(original_object)\n\n    # Filter out non-transform nodes that might have been included\n    separated_parts = [part for part in separated_parts if cmds.nodeType(part) == \'transform\']\n    \n    # Store the name of the newly renamed object for face deletion later\n    renamed_object_name = None\n\n    # Delete history and freeze transformations on each part\n    for i, part in enumerate(separated_parts):\n        # Rename the part\n        new_name = f"{original_object}_Part{i+1}"\n        renamed_part = cmds.rename(part, new_name)\n\n        # Save the renamed object name if it corresponds to the original object\n        if i == 0:\n            renamed_object_name = renamed_part\n\n        # Clean up the part\n        cmds.delete(renamed_part, ch=True)\n        cmds.makeIdentity(renamed_part, apply=True, t=1, r=1, s=1, n=0)\n\n    # Remove the saved faces using the renamed object\n    if saved_faces and renamed_object_name:\n        # Update the face selection with the new object name\n        updated_faces = [face.replace(original_object, renamed_object_name) for face in saved_faces]\n        cmds.select(updated_faces)\n        cmds.delete()\n\n    print("Separation, cleanup, renaming, and face removal completed successfully.")\n\n# Execute the function\nseparate_and_rename_simple()'}, {'category': 'Sculpting', 'label': 'AutoConnect', 'tooltip': 'import maya.cmds as cmds\n\nclass AutoConnectTool:\n    def __init__(self):\n        self.window_name = "AutoConnectWindow"\n        self.is_active = False  # Tracks if the toggle is ON\n        self.script_job = None  # Stores script job ID\n\n    def create_ui(self):\n        # Close existing window if already open\n        if cmds.window(self.window_name, exists=True):\n            cmds.deleteUI(self.window_name)\n\n        # Create new window\n        self.window = cmds.window(self.window_name, title="Aut', 'source': 'python', 'command': 'import maya.cmds as cmds\n\nclass AutoConnectTool:\n    def __init__(self):\n        self.window_name = "AutoConnectWindow"\n        self.is_active = False  # Indique si le mode Auto Connect est activ\n        self.script_job = None  # Stocke l\'ID du scriptJob\n        self.edge_flow_enabled = False  # tat initial de l\'option Edge Flow\n\n    def create_ui(self):\n        # Fermer la fentre existante si elle est dj ouverte\n        if cmds.window(self.window_name, exists=True):\n            cmds.deleteUI(self.window_name)\n\n        # Crer une nouvelle fentre\n        self.window = cmds.window(self.window_name, title="Outil Auto Connect", widthHeight=(200, 120))\n        cmds.columnLayout(adjustableColumn=True)\n\n        # Bouton de bascule pour Auto Connect\n        self.toggle_btn = cmds.button(label="Auto Connect (OFF)", command=self.toggle_auto_connect, bgc=[0.4, 0.4, 0.4])\n\n        # Case  cocher pour activer/dsactiver l\'Edge Flow\n        self.edge_flow_checkbox = cmds.checkBox(label="Activer Edge Flow", value=self.edge_flow_enabled, changeCommand=self.toggle_edge_flow)\n\n        cmds.showWindow(self.window)\n\n    def toggle_auto_connect(self, *args):\n        """Active ou dsactive le mode Auto Connect."""\n        self.is_active = not self.is_active\n\n        if self.is_active:\n            cmds.button(self.toggle_btn, edit=True, label="Auto Connect (ON)", bgc=[0.2, 0.8, 0.2])\n            cmds.warning("Auto Connect est activ. Slectionnez deux sommets ou deux artes.")\n            self.start_script_job()\n        else:\n            cmds.button(self.toggle_btn, edit=True, label="Auto Connect (OFF)", bgc=[0.4, 0.4, 0.4])\n            cmds.warning("Auto Connect est dsactiv.")\n            self.kill_script_job()\n\n    def toggle_edge_flow(self, state):\n        """Active ou dsactive l\'option Edge Flow."""\n        self.edge_flow_enabled = state\n        if self.edge_flow_enabled:\n            cmds.warning("Edge Flow activ.")\n        else:\n            cmds.warning("Edge Flow dsactiv.")\n\n    def start_script_job(self):\n        """Dmarre un scriptJob pour surveiller les changements de slection."""\n        if self.script_job:\n            cmds.scriptJob(kill=self.script_job, force=True)  # Supprime le scriptJob prcdent s\'il existe\n        self.script_job = cmds.scriptJob(event=["SelectionChanged", self.on_selection_change], protected=True)\n\n    def on_selection_change(self):\n        """Vrifie si l\'utilisateur a slectionn exactement deux sommets ou deux artes et excute la commande approprie."""\n        if not self.is_active:\n            return  # Ignorer si le mode Auto Connect est dsactiv\n\n        selected = cmds.ls(selection=True, fl=True)  # Obtenir la slection\n        valid_vertices = []\n        valid_edges = []\n\n        # Filtrer la slection pour s\'assurer qu\'il s\'agit de sommets ou d\'artes\n        for sel in selected:\n            if ".vtx[" in sel:  # C\'est un sommet\n                parent_mesh = cmds.listRelatives(sel, parent=True, fullPath=True)  # Obtenir le maillage parent\n                if parent_mesh and cmds.nodeType(parent_mesh[0]) == "mesh":\n                    valid_vertices.append(sel)\n            elif ".e[" in sel:  # C\'est une arte\n                parent_mesh = cmds.listRelatives(sel, parent=True, fullPath=True)  # Obtenir le maillage parent\n                if parent_mesh and cmds.nodeType(parent_mesh[0]) == "mesh":\n                    valid_edges.append(sel)\n\n        if len(valid_vertices) == 2 or len(valid_edges) == 2:\n            # Excuter la commande pour connecter les composants slectionns\n            cmds.polyConnectComponents(ch=1, insertWithEdgeFlow=self.edge_flow_enabled, adjustEdgeFlow=1)\n            cmds.warning("Composants connects. Slectionnez les deux prochains sommets ou artes.")\n            # Rinitialiser la slection pour permettre  l\'utilisateur de choisir de nouveaux composants\n            cmds.select(clear=True)\n\n    def kill_script_job(self):\n        """Arrte le scriptJob actif en toute scurit."""\n        if self.script_job:\n            cmds.scriptJob(kill=self.script_job, force=True)\n            self.script_job = None\n\n# Excuter le script\ntool = AutoConnectTool()\ntool.create_ui()\n'}, {'category': 'Sculpting', 'label': 'ProCombine', 'tooltip': 'This script combines selected polygonal objects in Maya while preserving their \nhierarchy and applying clean-up operations like deleting history and freezing transformations.', 'source': 'python', 'command': '# combine_and_preserve_hierarchy.py\nimport maya.cmds as cmds\nimport re\n\ndef _get_mesh_transforms_in_selection():\n    """Return ordered list of transform nodes that actually carry mesh shapes.\n    Expands groups; if a selected transform has no mesh descendants but itself is a mesh, keep it."""\n    sel = cmds.ls(selection=True, type=\'transform\') or []\n    if not sel:\n        cmds.error("Aucun objet slectionn.")\n        return []\n    out = []\n    seen = set()\n    for obj in sel:\n        # All descendant transforms\n        descendants = cmds.listRelatives(obj, allDescendents=True, type=\'transform\') or []\n        # Check meshes on each descendant\n        for t in descendants + [obj]:\n            if t in seen:\n                continue\n            shapes = cmds.listRelatives(t, shapes=True, noIntermediate=True, type=\'mesh\') or []\n            if shapes:\n                out.append(t)\n                seen.add(t)\n    # keep order as discovered\n    return out\n\ndef combine_and_preserve_hierarchy():\n    cmds.undoInfo(openChunk=True)\n    try:\n        selected_objects = _get_mesh_transforms_in_selection()\n        if not selected_objects:\n            cmds.error("Aucun mesh valide trouv dans la slection.")\n            return\n\n        # Map temp -> original short name (for final rename)\n        original_names = {}\n        temp_names = []\n\n        # Temporarily rename to avoid conflicts (simple, unique)\n        for i, obj in enumerate(selected_objects):\n            temp_name = "temp_object_{:04d}".format(i)\n            original_names[temp_name] = obj  # store original path/name\n            new_name = cmds.rename(obj, temp_name)\n            temp_names.append(new_name)\n\n        # Find target (highest polycount) and remember its original parent before we rearrange\n        target_name = None\n        target_parent = None\n        highest_poly = -1\n        for t in temp_names:\n            if cmds.listRelatives(t, shapes=True, noIntermediate=True, type=\'mesh\'):\n                faces = cmds.polyEvaluate(t, face=True)\n                if faces > highest_poly:\n                    highest_poly = faces\n                    target_name = t\n        if target_name:\n            # parent of target BEFORE temporary grouping\n            target_parent = cmds.listRelatives(target_name, parent=True)\n\n        combined_mesh = None\n        temp_group = None\n\n        if len(temp_names) == 1:\n            # Rien  combiner : on travaille directement sur l\'objet\n            combined_mesh = temp_names[0]\n        else:\n            # Cre un groupe temporaire au monde & y parent les objets\n            temp_group = cmds.group(empty=True, name="temp_group", world=True)\n            try:\n                cmds.parent(temp_names, temp_group)\n            except Exception as e:\n                cmds.warning("chec du parentage dans le groupe temporaire : {}".format(e))\n\n            # Combine\n            try:\n                combined_mesh = cmds.polyUnite(temp_names, ch=False, mergeUVSets=True, name="combinedMesh#")[0]\n            except Exception as e:\n                cmds.error("chec du combine (polyUnite) : {}".format(e))\n                return\n\n        # Nettoyage : delete history + freeze\n        try:\n            cmds.delete(combined_mesh, ch=True)\n            cmds.makeIdentity(combined_mesh, apply=True, t=1, r=1, s=1, n=0)\n        except Exception as e:\n            cmds.warning("Nettoyage partiel (delete history / freeze) : {}".format(e))\n\n        # Re-parent vers la hirarchie d\'origine du target si connue\n        if target_parent:\n            try:\n                cmds.parent(combined_mesh, target_parent[0])\n            except Exception as e:\n                cmds.warning("chec du re-parent vers le parent d\'origine : {}".format(e))\n        else:\n            # Au monde sinon\n            try:\n                cmds.parent(combined_mesh, world=True)\n            except Exception as e:\n                cmds.warning("chec du parentage au monde : {}".format(e))\n\n        # Supprime le groupe temporaire s\'il existe encore\n        if temp_group and cmds.objExists(temp_group):\n            try:\n                cmds.delete(temp_group)\n            except Exception as e:\n                cmds.warning("chec de suppression du groupe temporaire : {}".format(e))\n\n        # Si le parent n\'a plus qu\'un enfant (le mesh combin), on "aplati" un niveau\n        parent_group = cmds.listRelatives(combined_mesh, parent=True)\n        if parent_group:\n            children = cmds.listRelatives(parent_group[0], children=True) or []\n            if len(children) == 1 and children[0] == combined_mesh:\n                grandparent = cmds.listRelatives(parent_group[0], parent=True)\n                if grandparent:\n                    cmds.parent(combined_mesh, grandparent[0])\n                else:\n                    cmds.parent(combined_mesh, world=True)\n                try:\n                    cmds.delete(parent_group[0])\n                except Exception as e:\n                    cmds.warning("chec de suppression du parent vide : {}".format(e))\n\n        # Dterminer le nom final d\'aprs l\'objet cible (celui au polycount max)\n        # On veut le shortName original, sans suffixe _PartX\n        final_name = None\n        if target_name:\n            original_target = original_names.get(target_name, target_name)\n            # Rcuprer uniquement le shortName (sans chemin hirarchique)\n            short = original_target.split(\'|\')[-1]\n            short = re.sub(r\'_Part\\d+$\', \'\', short)\n            final_name = short\n\n        if final_name:\n            try:\n                combined_mesh = cmds.rename(combined_mesh, final_name)\n            except Exception as e:\n                cmds.warning("chec du renommage final \'{}\': {}".format(final_name, e))\n\n        # Merge vertices lgers (tolrance 0.01)\n        try:\n            # Assure qu\'on vise bien les sommets du shape du transform renomm\n            cmds.select("{}.vtx[*]".format(combined_mesh), r=True)\n            cmds.polyMergeVertex(d=0.01, am=1, ch=1)\n        except Exception as e:\n            cmds.warning("chec du merge vertices : {}".format(e))\n\n        # Slection propre\n        cmds.select(clear=True)\n        cmds.selectMode(object=True)\n\n        print("Mesh final \'{}\' cr/merg et replac correctement.".format(combined_mesh))\n\n    finally:\n        cmds.undoInfo(closeChunk=True)\n\n# Excuter\nif __name__ == "__main__":\n    combine_and_preserve_hierarchy()\n'}, {'category': 'Sculpting', 'label': 'EqualSpace', 'tooltip': "Ce script cre une interface permettant d'espacer uniformment les objets slectionns. L'utilisateur peut spcifier la distance d'espacement, choisir l'axe (X, Y ou Z) et dterminer si l'espacement doit tre appliqu selon l'axe du monde ou l'axe local de l'objet. Cette flexibilit facilite l'organisation prcise des objets dans la scne 3D.", 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef espacer_objets():\n    # Vrifier le nombre d\'objets slectionns\n    objets_selectionnes = cmds.ls(selection=True)\n    nombre_objets = len(objets_selectionnes)\n\n    if nombre_objets < 2:\n        cmds.warning("Veuillez slectionner au moins deux objets.")\n        return\n\n    # Fonction pour appliquer l\'espacement\n    def appliquer_espacement(*args):\n        try:\n            espacement = float(cmds.textField(espacement_champ, query=True, text=True))\n        except ValueError:\n            cmds.warning("Veuillez entrer une valeur numrique valide pour l\'espacement.")\n            return\n\n        axe = cmds.radioButtonGrp(axe_boutons, query=True, select=True)\n        axes = {1: \'x\', 2: \'y\', 3: \'z\'}\n        axe_selectionne = axes.get(axe, \'x\')\n\n        espace = cmds.radioButtonGrp(espace_boutons, query=True, select=True)\n        espaces = {1: \'world\', 2: \'object\'}\n        espace_selectionne = espaces.get(espace, \'world\')\n\n        # Index de l\'axe : 0 pour x, 1 pour y, 2 pour z\n        index_axe = {\'x\': 0, \'y\': 1, \'z\': 2}[axe_selectionne]\n\n        # Obtenir la position du premier objet\n        if espace_selectionne == \'world\':\n            position_depart = cmds.xform(objets_selectionnes[0], query=True, worldSpace=True, translation=True)\n        else:\n            position_depart = cmds.xform(objets_selectionnes[0], query=True, objectSpace=True, translation=True)\n\n        # Espacer les objets\n        for i in range(1, nombre_objets):\n            nouvelle_position = position_depart[:]\n            nouvelle_position[index_axe] += i * espacement\n            if espace_selectionne == \'world\':\n                cmds.xform(objets_selectionnes[i], worldSpace=True, translation=nouvelle_position)\n            else:\n                cmds.xform(objets_selectionnes[i], objectSpace=True, translation=nouvelle_position)\n\n    # Crer la fentre\n    if cmds.window("espacementFenetre", exists=True):\n        cmds.deleteUI("espacementFenetre", window=True)\n\n    cmds.window("espacementFenetre", title="Espacement des Objets", widthHeight=(300, 200))\n    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")\n\n    # Champ de texte pour la distance d\'espacement\n    cmds.text(label="Distance d\'espacement :")\n    espacement_champ = cmds.textField()\n\n    # Boutons radio pour slectionner l\'axe\n    cmds.text(label="Slectionnez l\'axe :")\n    axe_boutons = cmds.radioButtonGrp(labelArray3=[\'X\', \'Y\', \'Z\'], numberOfRadioButtons=3, select=1)\n\n    # Boutons radio pour slectionner l\'espace\n    cmds.text(label="Slectionnez l\'espace :")\n    espace_boutons = cmds.radioButtonGrp(labelArray2=[\'Monde\', \'Objet\'], numberOfRadioButtons=2, select=1)\n\n    # Bouton pour appliquer l\'espacement\n    cmds.button(label="Appliquer l\'espacement", command=appliquer_espacement)\n\n    cmds.showWindow("espacementFenetre")\n\nespacer_objets()\n'}, {'category': 'Sculpting', 'label': 'Transform', 'tooltip': 'Transform', 'source': 'mel', 'command': 'performPolyMove "" 0'}, {'category': 'Sculpting', 'label': 'VertexEdgeWeld', 'tooltip': 'A Maya tool that identifies the closest edge to a selected vertex, inserts a vertex in the middle of this edge, and then seamlessly welds the new vertex to the selected vertex for precise geometry adjustments.', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.api.OpenMaya as om\n\ndef get_vertices_within_distance(target_vertex, distance_threshold):\n    """Finds vertices within a specified distance from the target vertex."""\n    target_position = om.MPoint(cmds.pointPosition(target_vertex, world=True))\n    mesh = target_vertex.split(\'.\')[0]\n    vertices = cmds.ls(f"{mesh}.vtx[*]", fl=True)\n    nearby_vertices = []\n\n    for vertex in vertices:\n        if vertex != target_vertex:\n            position = om.MPoint(cmds.pointPosition(vertex, world=True))\n            if (position - target_position).length() < distance_threshold:\n                nearby_vertices.append(vertex)\n    \n    return nearby_vertices\n\ndef get_closest_edge_to_vertex(vertex, max_edge_distance):\n    # Get the selected vertex\'s position\n    vertex_position = cmds.pointPosition(vertex, world=True)\n    vertex_position = om.MPoint(vertex_position)\n\n    # Get the mesh name from the vertex\n    mesh = vertex.split(\'.\')[0]\n\n    # Get all the edges in the mesh\n    edges = cmds.ls(f"{mesh}.e[*]", fl=True)\n    connected_edges = cmds.polyListComponentConversion(vertex, fromVertex=True, toEdge=True)\n    connected_edges = cmds.ls(connected_edges, fl=True)\n\n    # Find the closest edge that isn\'t connected to the vertex\n    min_distance = float(\'inf\')\n    closest_edge = None\n\n    for edge in edges:\n        if edge not in connected_edges:\n            # Get the vertices of the edge\n            edge_vertices = cmds.polyInfo(edge, edgeToVertex=True)[0].split()[2:4]\n            v1 = f"{mesh}.vtx[{edge_vertices[0]}]"\n            v2 = f"{mesh}.vtx[{edge_vertices[1]}]"\n            \n            # Get positions of the vertices\n            v1_position = cmds.pointPosition(v1, world=True)\n            v2_position = cmds.pointPosition(v2, world=True)\n            \n            # Convert positions to MPoint\n            v1_position = om.MPoint(v1_position)\n            v2_position = om.MPoint(v2_position)\n\n            # Calculate edge vector and check for zero-length edge\n            edge_vector = v2_position - v1_position\n            if edge_vector.length() == 0:\n                continue\n\n            # Find the closest point on the edge to the vertex\n            vertex_vector = vertex_position - v1_position\n            projection = (vertex_vector * edge_vector) / (edge_vector * edge_vector)\n            projection = max(0, min(1, projection))\n            closest_point = v1_position + projection * edge_vector\n\n            # Calculate distance\n            distance = (closest_point - vertex_position).length()\n            if distance < min_distance and distance <= max_edge_distance:\n                min_distance = distance\n                closest_edge = edge\n\n    return closest_edge, min_distance\n\ndef insert_vertex_at_middle_of_edge(edge):\n    # Insert a vertex in the middle of the specified edge\n    cmds.polySubdivideEdge(edge, divisions=1)\n    # Get the newly created vertex\n    new_vertex = cmds.polyListComponentConversion(edge, fromEdge=True, toVertex=True)\n    new_vertex = cmds.ls(new_vertex, flatten=True)[-1]  # Get the last vertex in the list\n    return new_vertex\n\ndef target_weld_vertices(source_vertex, target_vertex):\n    # Get the position of the target vertex\n    target_position = cmds.pointPosition(target_vertex, world=True)\n    \n    # Move the source vertex to the target vertex position\n    cmds.move(target_position[0], target_position[1], target_position[2], source_vertex, absolute=True, worldSpace=True)\n    \n    # Merge the vertices\n    cmds.polyMergeVertex([source_vertex, target_vertex], distance=0.000001)\n\ndef is_vertex_on_border(vertex):\n    """Checks if the given vertex is on a border (open edge)."""\n    edges = cmds.polyListComponentConversion(vertex, fromVertex=True, toEdge=True)\n    edges = cmds.ls(edges, fl=True)\n    for edge in edges:\n        # Get the number of faces connected to the edge\n        faces = cmds.polyListComponentConversion(edge, fromEdge=True, toFace=True)\n        faces = cmds.ls(faces, fl=True)\n        if len(faces) == 1:  # An edge with only one connected face is a border edge\n            return True\n    return False\n\n# Example usage\nselected_vertices = cmds.ls(selection=True, flatten=True)\ndistance_threshold = 0.002  # For nearby vertex detection\nmax_edge_distance = 0.05     # Maximum distance for edge detection\n\nif selected_vertices:\n    for target_vertex in selected_vertices:\n        # Check if the vertex is on a border\n        if is_vertex_on_border(target_vertex):\n            # Check for nearby vertices to merge\n            nearby_vertices = get_vertices_within_distance(target_vertex, distance_threshold)\n            if nearby_vertices:\n                for nearby_vertex in nearby_vertices:\n                    print(f"Merging {target_vertex} with nearby vertex {nearby_vertex}")\n                    target_weld_vertices(nearby_vertex, target_vertex)\n            else:\n                # No nearby vertices, proceed with finding the closest edge within max_edge_distance\n                closest_edge, distance = get_closest_edge_to_vertex(target_vertex, max_edge_distance)\n                if closest_edge:\n                    print(f"The closest edge to {target_vertex} is {closest_edge} with a distance of {distance}")\n                    new_vertex = insert_vertex_at_middle_of_edge(closest_edge)\n                    target_weld_vertices(new_vertex, target_vertex)\n                    print(f"Target welded vertex {new_vertex} to {target_vertex}")\n                else:\n                    print(f"No edge found within {max_edge_distance} units from {target_vertex}")\n        else:\n            print(f"Vertex {target_vertex} is not on a border and will be skipped.")\nelse:\n    print("Please select at least one vertex.")\n'}, {'category': 'Sculpting', 'label': 'Center Edge', 'tooltip': 'Select the center edge of the selected obect', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.OpenMaya as om\n\ndef on_button_click(axis):\n    select_center_edge_loop(axis)\n    cmds.deleteUI("centerAxisWin")\n\ndef create_ui():\n    if cmds.window("centerAxisWin", exists=True):\n        cmds.deleteUI("centerAxisWin")\n\n    cmds.window("centerAxisWin", title="Select Center Axis")\n    cmds.columnLayout(adjustableColumn=True)\n    \n    cmds.text(label="Choose the center axis:")\n    \n    cmds.button(label="X Axis", command=lambda x: on_button_click(\'x\'))\n    cmds.button(label="Y Axis", command=lambda x: on_button_click(\'y\'))\n    cmds.button(label="Z Axis", command=lambda x: on_button_click(\'z\'))\n    \n    cmds.showWindow("centerAxisWin")\n\ndef select_center_edge_loop(center_axis):\n    # Get the selected object\n    selected_objects = cmds.ls(selection=True)\n    if not selected_objects:\n        om.MGlobal.displayError("Please select an object.")\n        return\n    \n    selected_object = selected_objects[0]\n    \n    # Get the bounding box of the object\n    bbox = cmds.exactWorldBoundingBox(selected_object)\n    \n    # Determine the center plane position\n    center_pos = {\n        \'x\': (bbox[0] + bbox[3]) / 2,\n        \'y\': (bbox[1] + bbox[4]) / 2,\n        \'z\': (bbox[2] + bbox[5]) / 2\n    }\n    \n    # Create a very thin box along the selected axis\n    tolerance = 0.1\n    min_bounds = list(bbox[:3])\n    max_bounds = list(bbox[3:])\n    \n    if center_axis == \'x\':\n        min_bounds[0] = center_pos[\'x\'] - tolerance\n        max_bounds[0] = center_pos[\'x\'] + tolerance\n    elif center_axis == \'y\':\n        min_bounds[1] = center_pos[\'y\'] - tolerance\n        max_bounds[1] = center_pos[\'y\'] + tolerance\n    elif center_axis == \'z\':\n        min_bounds[2] = center_pos[\'z\'] - tolerance\n        max_bounds[2] = center_pos[\'z\'] + tolerance\n    \n    # Convert to tuples\n    min_bounds = tuple(min_bounds)\n    max_bounds = tuple(max_bounds)\n    \n    # Find edges within the box\n    edge_ids = cmds.polyListComponentConversion(selected_object, toEdge=True)\n    edge_ids = cmds.filterExpand(edge_ids, selectionMask=32, expand=True)\n    \n    selected_edges = []\n    for edge in edge_ids:\n        vertices = cmds.polyInfo(edge, edgeToVertex=True)[0].split()[2:4]\n        vertices = [int(v) for v in vertices]\n        positions = [cmds.pointPosition(f"{selected_object}.vtx[{v}]") for v in vertices]\n        \n        in_box = all(\n            min_bounds[i] <= positions[0][i] <= max_bounds[i] and\n            min_bounds[i] <= positions[1][i] <= max_bounds[i]\n            for i in range(3)\n        )\n        \n        if in_box:\n            selected_edges.append(edge)\n    \n    # Select the edges\n    if selected_edges:\n        cmds.select(selected_edges)\n    else:\n        om.MGlobal.displayWarning("No edges found in the specified plane.")\n\n# Run the UI\ncreate_ui()\n'}, {'category': 'Sculpting', 'label': 'In_Sel', 'tooltip': 'Select Inner faces', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.mel as mel\n\ndef save_face_selection_on_original_mesh(original_mesh_name):\n    # Get the face selection on the duplicate mesh "In_Sel_Temp_Mesh_B"\n    face_selection_on_b = cmds.ls(selection=True, fl=True)\n\n    if not face_selection_on_b:\n        cmds.warning("No faces selected on In_Sel_Temp_Mesh_B.")\n        return\n\n    # Convert the selection to the original mesh\n    face_selection_on_original = [face.replace("In_Sel_Temp_Mesh_B", original_mesh_name) for face in face_selection_on_b]\n\n    # Delete the duplicate mesh "In_Sel_Temp_Mesh_B"\n    cmds.delete("In_Sel_Temp_Mesh_B")\n\n    # Unhide the original mesh\n    cmds.showHidden(original_mesh_name)\n\n    # Select the original mesh in object mode\n    cmds.select(original_mesh_name)\n    cmds.selectMode(object=True)\n\n    # Switch to face selection mode and clear the selection\n    cmds.selectMode(component=True)\n    cmds.selectType(facet=True)\n    cmds.select(clear=True)\n\n    # Select the corresponding faces on the original mesh\n    cmds.select(face_selection_on_original)\n\n    print(f"In_Sel_Temp_Mesh_B has been deleted. Original mesh \'{original_mesh_name}\' is unhidden. Face selection recovered on original mesh: {face_selection_on_original}")\n\n    # Clean up the script job after it\'s done\n    job_id = cmds.scriptJob(listJobs=True)[-1].split(":")[0]\n    cmds.scriptJob(kill=int(job_id), force=True)\n\ndef save_clear_duplicate_uv_cut_and_wait_for_uv_shell_selection():\n    # Get the current selection (edge or face)\n    selection = cmds.ls(selection=True, fl=True)\n\n    if not selection:\n        cmds.warning("No selection detected.")\n        return\n\n    # Determine if the selection is edge or face\n    if ".e[" in selection[0]:\n        selection_type = "edge"\n    elif ".f[" in selection[0]:\n        selection_type = "face"\n        # Convert face selection to edge perimeter\n        mel.eval(\'ConvertSelectionToEdgePerimeter;\')\n        selection = cmds.ls(selection=True, fl=True)\n        selection_type = "edge"\n    else:\n        cmds.warning("Unsupported selection type. Please select edges or faces.")\n        return\n\n    # Extract the object from the selection\n    objects = list(set([sel.split(\'.\')[0] for sel in selection]))\n\n    if len(objects) > 1:\n        cmds.warning("Multiple objects are selected. This script only works with one object at a time.")\n        return\n\n    original_mesh_name = objects[0]\n\n    # Clear the selection\n    cmds.select(clear=True)\n\n    # Switch to object mode and select the original mesh\n    cmds.select(original_mesh_name)\n    cmds.selectMode(object=True)\n\n    # Duplicate the original mesh and name it "In_Sel_Temp_Mesh_B"\n    duplicate_mesh_name = cmds.duplicate(original_mesh_name, name="In_Sel_Temp_Mesh_B")[0]\n\n    # Hide the original mesh\n    cmds.hide(original_mesh_name)\n\n    # Select "In_Sel_Temp_Mesh_B" and apply UV Camera Based Projection\n    cmds.select(duplicate_mesh_name)\n    cmds.UVCameraBasedProjection()\n\n    # Recover the saved edge selection on "In_Sel_Temp_Mesh_B"\n    edge_selection_on_mesh_b = [sel.replace(original_mesh_name, duplicate_mesh_name) for sel in selection]\n    cmds.select(edge_selection_on_mesh_b)\n\n    # Perform UV cut using the recovered edge selection on "In_Sel_Temp_Mesh_B"\n    cmds.polyMapCut()\n\n    # Switch to UV Shell selection mode on "In_Sel_Temp_Mesh_B" using the provided MEL command\n    mel.eval(\'\'\'\n        changeSelectMode -component;\n        setComponentPickMask "Facet" true;\n        selectType -ocm -alc false;\n        selectType -msh true;\n        selectType -sf false -se false -suv false -cv false;\n    \'\'\')\n\n    print(f"Selection saved on original mesh \'{original_mesh_name}\'.")\n    print(f"Duplicate mesh created and selected: \'In_Sel_Temp_Mesh_B\'. Original mesh \'{original_mesh_name}\' is hidden.")\n    print("UV Camera Based Projection applied to \'In_Sel_Temp_Mesh_B\'.")\n    print("UV cut performed on \'In_Sel_Temp_Mesh_B\' using the recovered selection.")\n    print("Switched to UV Shell selection mode on \'In_Sel_Temp_Mesh_B\'. Please select a UV shell.")\n\n    # Set up a script job to wait for user selection on "In_Sel_Temp_Mesh_B"\n    script_job_id = cmds.scriptJob(event=["SelectionChanged", lambda: save_face_selection_on_original_mesh(original_mesh_name)], runOnce=True)\n\n# Execute the function\nsave_clear_duplicate_uv_cut_and_wait_for_uv_shell_selection()'}, {'category': 'Sculpting', 'label': 'Sel Hard Edges', 'tooltip': 'Select Hard Edges', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef select_edges_by_angle(min_angle, max_angle):\n    """\n    Selects edges within the specified angle range without deselecting the initial object.\n    """\n    # Get the currently selected objects\n    selected_objects = cmds.ls(selection=True, long=True)\n    \n    if not selected_objects:\n        cmds.warning("No objects selected.")\n        return\n    \n    # Iterate over each selected object\n    for obj in selected_objects:\n        # Select all edges of the object\n        cmds.select(obj + ".e[*]", replace=True)\n        \n        # Apply the angle constraint\n        cmds.polySelectConstraint(mode=3, type=0x8000, angle=True, anglebound=(min_angle, max_angle))\n        \n        # Disable the selection constraint\n        cmds.polySelectConstraint(disable=True)\n        \n        # Add the selected edges to the current selection without deselecting the object\n        selected_edges = cmds.ls(selection=True, long=True)\n        cmds.select(obj, add=True)\n        cmds.select(selected_edges, add=True)\n    \n    print(f"Edges between {min_angle} and {max_angle} selected.")\n\ndef select_hardened_edges():\n    """\n    Selects all hardened (hard) edges on the currently selected objects.\n    """\n    # Get the currently selected objects\n    selected_objects = cmds.ls(selection=True, long=True)\n    \n    if not selected_objects:\n        cmds.warning("No objects selected.")\n        return\n    \n    # Iterate over each selected object\n    for obj in selected_objects:\n        # Select all edges of the object\n        cmds.select(obj + ".e[*]", replace=True)\n        \n        # Apply the constraint to select hard edges\n        cmds.polySelectConstraint(mode=3, type=0x8000, smoothness=1)\n        \n        # Disable the selection constraint\n        cmds.polySelectConstraint(disable=True)\n        \n        # Add the selected hard edges to the current selection without deselecting the object\n        hard_edges = cmds.ls(selection=True, long=True)\n        cmds.select(obj, add=True)\n        cmds.select(hard_edges, add=True)\n    \n    print("Hardened edges selected.")\n\ndef create_ui():\n    """\n    Creates a user interface to select predefined angle ranges and hardened edges.\n    """\n    window_name = "edgeSelectorUI"\n    \n    if cmds.window(window_name, exists=True):\n        cmds.deleteUI(window_name)\n    \n    cmds.window(window_name, title="Edge Selector by Angle", widthHeight=(300, 250))\n    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")\n    \n    cmds.text(label="Select a range of angles:")\n    \n    # Define presets as (min_angle, max_angle, label)\n    presets = [\n        (89, 91, "89 - 91"),\n        (85, 95, "85 - 95"),\n        (80, 100, "80 - 100"),\n        (70, 110, "70 - 110"),\n        (60, 120, "60 - 120"),\n        (50, 130, "50 - 130"),\n        (40, 140, "40 - 140"),\n        (30, 150, "30 - 150"),\n        (20, 160, "20 - 160"),\n        (10, 170, "10 - 170"),\n        (5, 175, "5 - 175")\n    ]\n    \n    for min_angle, max_angle, label in presets:\n        cmds.button(\n            label=label,\n            command=lambda _, min_angle=min_angle, max_angle=max_angle: select_edges_by_angle(min_angle, max_angle),\n            width=250\n        )\n    \n    cmds.separator(height=10, style=\'in\')\n    \n    cmds.button(\n        label="Select Hardened Edges",\n        command=lambda _: select_hardened_edges(),\n        width=250,\n        backgroundColor=(0.8, 0.2, 0.2)\n    )\n    \n    cmds.showWindow(window_name)\n\n# Execute the user interface\ncreate_ui()\n'}, {'category': 'Sculpting', 'label': 'Sel Crease', 'tooltip': 'Select Creased Edges', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef select_creased_edges():\n    # Get the currently selected mesh\n    selected_meshes = cmds.ls(selection=True, dag=True, type=\'mesh\')\n    \n    if not selected_meshes:\n        cmds.warning("Please select a mesh.")\n        return\n\n    # Switch to edge selection mode and clear the selection\n    cmds.selectMode(component=True)\n    cmds.selectType(edge=True)\n    cmds.select(clear=True)\n\n    # Initialize an empty list to hold the creased edges\n    creased_edges = []\n\n    for mesh in selected_meshes:\n        # Get all the edges of the mesh\n        edges = cmds.polyListComponentConversion(mesh, toEdge=True)\n        edges = cmds.filterExpand(edges, selectionMask=32)\n        \n        if edges:\n            for edge in edges:\n                # Check if the edge is creased\n                crease_value = cmds.polyCrease(edge, query=True, value=True)\n                if crease_value[0] > 0.0:\n                    creased_edges.append(edge)\n\n    if creased_edges:\n        # Select the creased edges\n        cmds.select(creased_edges)\n        print("Creased edges selected.")\n    else:\n        cmds.warning("No creased edges found.")\n\n# Run the function\nselect_creased_edges()\n'}, {'category': 'Sculpting', 'label': 'Creased Edges', 'tooltip': 'Apply Crease to selected edges', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef apply_crease_to_selected_edges(strength=10):\n    # Get the currently selected edges\n    selected_edges = cmds.ls(selection=True, flatten=True)\n    \n    if not selected_edges:\n        cmds.warning("Please select some edges.")\n        return\n\n    # Apply the crease value to the selected edges\n    cmds.polyCrease(selected_edges, value=strength)\n    print("Crease applied with strength:", strength)\n\n# Automatically apply a crease with strength 10 to the selected edges\napply_crease_to_selected_edges()\n'}, {'category': 'Sculpting', 'label': 'Smooth_Crease', 'tooltip': 'Set mesh options to receive creasing correctly', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef set_subdiv_display_on_selection():\n    """\n    For ALL selected objects (even if components are selected),\n    set these mesh shape attrs:\n      - useGlobalSmoothDrawType = 0\n      - propagateEdgeHardness   = 1\n      - smoothDrawType          = 0  (Maya Catmull-Clark)\n    """\n    sel = cmds.ls(sl=True, fl=True, long=True) or []\n    if not sel:\n        cmds.warning("Please select one or more mesh objects (or components).")\n        return\n\n    # Convert any component selection to transforms (object selection)\n    objs = cmds.ls(sl=True, o=True, long=True) or []\n    if not objs:\n        # Fallback: force object mode and re-query\n        try:\n            cmds.select(sel, r=True)\n            cmds.selectMode(object=True)\n        except Exception:\n            pass\n        objs = cmds.ls(sl=True, type="transform", long=True) or []\n\n    if not objs:\n        cmds.warning("No transform objects found in selection.")\n        return\n\n    updated_shapes = 0\n\n    for obj in objs:\n        # Get non-intermediate mesh shapes under transform\n        shapes = cmds.listRelatives(obj, shapes=True, noIntermediate=True, fullPath=True) or []\n        for sh in shapes:\n            if cmds.nodeType(sh) != "mesh":\n                continue\n\n            # Safe-set each attribute only if it exists on this node\n            if cmds.attributeQuery("useGlobalSmoothDrawType", node=sh, exists=True):\n                cmds.setAttr(sh + ".useGlobalSmoothDrawType", 0)\n\n            if cmds.attributeQuery("propagateEdgeHardness", node=sh, exists=True):\n                cmds.setAttr(sh + ".propagateEdgeHardness", 1)\n\n            if cmds.attributeQuery("smoothDrawType", node=sh, exists=True):\n                cmds.setAttr(sh + ".smoothDrawType", 0)\n\n            updated_shapes += 1\n\n    # Restore selection (transforms)\n    try:\n        cmds.select(objs, r=True)\n    except Exception:\n        pass\n\n    print("[SubdivDisplay] Updated {} mesh shape(s) on {} object(s).".format(updated_shapes, len(objs)))\n\n# Run\nset_subdiv_display_on_selection()\n'}, {'category': 'Sculpting', 'label': 'Preview_Smooth', 'tooltip': 'Create Poly From Preview', 'source': 'mel', 'command': 'CreatePolyFromPreview;\n'}, {'category': 'Action', 'label': 'Shift+P', 'tooltip': 'Unparent', 'source': 'mel', 'command': 'parent -w'}, {'category': 'Action', 'label': 'Ungr', 'tooltip': 'Ungroup', 'source': 'mel', 'command': 'ungroup'}, {'category': 'Action', 'label': 'Inst', 'tooltip': 'searchReplaceNames "$" "_Mast" "selected";\ninstance; move -r 50 0 0;\nsearchReplaceNames "_Mast1" "_Inst" "selected";', 'source': 'mel', 'command': 'global proc createAndRenameInstance() {\n    // tape 1 : Vrifier la slection\n    string $selection[] = `ls -sl`;\n    if (size($selection) == 0) {\n        error "Veuillez slectionner un objet avant d\'excuter ce script.";\n        return;\n    }\n\n    // Obtenir le nom de l\'objet d\'origine\n    string $originalName = $selection[0];\n    string $suffix = "_Inst";\n\n    // Vrifier si l\'objet d\'origine a dj le suffixe _Inst\n    int $hasSuffix = `gmatch $originalName ("*" + $suffix)`;\n\n    // tape 2 : Crer une instance de l\'objet slectionn\n    string $instance[] = `instance`;\n\n    // Vrifier qu\'une instance a bien t cre\n    if (size($instance) == 0) {\n        error "Impossible de crer une instance.";\n        return;\n    }\n\n    // tape 3 : Retirer l\'instance de tous les groupes/hirarchies\n    string $instanceName = $instance[0];\n    parent -w $instanceName; // Dplace l\'instance  la racine de la scne\n\n    // tape 4 : Renommer l\'instance avec le suffixe _Inst uniquement si ncessaire\n    string $newName;\n    if ($hasSuffix) {\n        $newName = $originalName; // Garder le nom tel quel\n    } else {\n        $newName = $originalName + $suffix; // Ajouter le suffixe _Inst\n    }\n    rename $instanceName $newName;\n\n    // tape 5 : Dplacer l\'instance\n    move -r 5 0 0;\n\n    print ("Instance cre, retire de tous les groupes, et renomme en : " + $newName + "\\n");\n}\n\n// Excuter la procdure\ncreateAndRenameInstance();\n'}, {'category': 'Action', 'label': 'ProInst', 'tooltip': 'import maya.cmds as cmds\n\ndef rename_freeze_instance():\n    """Renomme l\'objet slectionn, applique Freeze Transform et Bake Pivot,\n    cre une instance avec un nom unique et replace l\'objet original au centre du monde."""\n    \n    selected_objects = cmds.ls(selection=True)\n    \n    if not selected_objects:\n        cmds.warning("Aucun objet slectionn ! Veuillez slectionner un objet  renommer.")\n        return\n    \n    def get_unique_name(base_name):\n        """Gnre un nom unique en ajoutant un su', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef rename_freeze_instance():\n    """Renomme l\'objet slectionn, applique Freeze Transform et Bake Pivot,\n    cre une instance avec un nom unique et replace l\'objet original au centre du monde."""\n    \n    selected_objects = cmds.ls(selection=True)\n    \n    if not selected_objects:\n        cmds.warning("Aucun objet slectionn ! Veuillez slectionner un objet  renommer.")\n        return\n    \n    def get_unique_name(base_name):\n        """Gnre un nom unique en ajoutant un suffixe numrique si ncessaire."""\n        count = 1\n        unique_name = base_name\n        while cmds.objExists(unique_name):\n            unique_name = f"{base_name}_{count}"\n            count += 1\n        return unique_name\n    \n    def apply_changes(*args):\n        new_name = cmds.textField(rename_field, query=True, text=True)\n        if new_name:\n            # Renommer l\'objet slectionn\n            renamed_object = cmds.rename(selected_objects[0], new_name)\n            \n            # Appliquer Freeze Transformations\n            cmds.makeIdentity(renamed_object, apply=True, translate=True, rotate=True, scale=True, normal=False)\n            \n            # Appliquer Bake Pivot\n            cmds.BakeCustomPivot()\n            \n            # Obtenir la position actuelle de l\'objet\n            position = cmds.xform(renamed_object, query=True, worldSpace=True, translation=True)\n            \n            # Gnrer un nom unique pour l\'instance\n            instance_name = get_unique_name(f"{new_name}_Instance")\n            \n            # Crer une instance avec un nom unique\n            instance_object = cmds.instance(renamed_object, name=instance_name)[0]\n            \n            # Remettre l\'instance  la mme position\n            cmds.xform(instance_object, worldSpace=True, translation=position)\n            \n            # Placer l\'objet original au centre du monde\n            cmds.xform(renamed_object, worldSpace=True, translation=[0, 0, 0])\n            \n            # Fermer la fentre aprs application\n            cmds.deleteUI(window, window=True)\n        else:\n            cmds.warning("Veuillez entrer un nom valide.")\n    \n    # Cration de la fentre\n    window = "renameWindow"\n    if cmds.window(window, exists=True):\n        cmds.deleteUI(window)\n    \n    window = cmds.window(window, title="Renommer et grer l\'instance", widthHeight=(350, 150))\n    cmds.columnLayout(adjustableColumn=True)\n    \n    cmds.text(label=f"Renommer : {selected_objects[0]}", align="center")\n    rename_field = cmds.textField(text=selected_objects[0])\n    cmds.button(label="Appliquer", command=apply_changes)\n    \n    cmds.showWindow(window)\n\n# Excuter la fonction\nrename_freeze_instance()\n'}, {'category': 'Action', 'label': 'PSelect', 'tooltip': 'This MEL script selects parent groups associated with selected objects, or the objects themselves if no parent group is found.', 'source': 'mel', 'command': 'string $selectedObjs[] = `ls -sl`;\nif (size($selectedObjs) == 0) {\n    warning "Please select one or more objects.";\n} else {\n    string $parentGroups[]; // Array to store parent groups\n\n    // Iterate through each selected object\n    for ($obj in $selectedObjs) {\n        string $parentGroup[] = `listRelatives -p -f $obj`;\n        if (size($parentGroup) != 0) {\n            // Add parent group to the array if found\n            $parentGroups[size($parentGroups)] = $parentGroup[0];\n        } else {\n            // If no parent group found, select the object itself\n            $parentGroups[size($parentGroups)] = $obj;\n        }\n    }\n\n    // Check if any parent groups were found\n    if (size($parentGroups) == 0) {\n        warning ("Selected object(s) have no parent groups.");\n    } else {\n        // Select all parent groups or objects\n        select -r $parentGroups;\n    }\n}\n'}, {'category': 'Action', 'label': 'edgeSel', 'tooltip': 'This script selects edges in a Maya mesh based on the area of their adjacent faces and their length. Users can define min/max thresholds for both criteria via a UI.', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.api.OpenMaya as om\n\ndef selectEdgesBasedOnFaceArea(minArea, maxArea, minEdge, maxEdge):\n    """\n    Slectionne toutes les artes dont :\n      - Toutes les faces adjacentes ont une aire comprise entre minArea et maxArea.\n      - La longueur de l\'arte est comprise entre minEdge et maxEdge.\n    """\n    # Vrifier qu\'un objet est slectionn\n    sel = cmds.ls(selection=True, long=True)\n    if not sel:\n        cmds.error("Veuillez slectionner un objet maillage.")\n    \n    meshName = sel[0]\n    \n    # Prparer l\'API OpenMaya pour itrer sur le maillage\n    selList = om.MSelectionList()\n    selList.add(meshName)\n    dagPath = selList.getDagPath(0)\n    \n    # Calculer l\'aire de chaque face et stocker dans un dictionnaire\n    faceArea = {}\n    polyIter = om.MItMeshPolygon(dagPath)\n    while not polyIter.isDone():\n        faceIndex = polyIter.index()\n        area = polyIter.getArea()\n        faceArea[faceIndex] = area\n        polyIter.next()\n    \n    # Itrer sur les artes et vrifier les conditions sur les faces et la longueur de l\'arte\n    selectedEdges = []\n    edgeIter = om.MItMeshEdge(dagPath)\n    while not edgeIter.isDone():\n        connectedFaces = edgeIter.getConnectedFaces()\n        allFacesInRange = True\n        for faceIdx in connectedFaces:\n            area = faceArea.get(faceIdx, 0)\n            if area < minArea or area > maxArea:\n                allFacesInRange = False\n                break\n        \n        if allFacesInRange and connectedFaces:\n            # Rcuprer les positions des deux extrmits de l\'arte\n            p0 = edgeIter.point(0, om.MSpace.kWorld)\n            p1 = edgeIter.point(1, om.MSpace.kWorld)\n            edgeLength = p0.distanceTo(p1)\n            \n            # Vrifier que la longueur est dans le range spcifi\n            if minEdge <= edgeLength <= maxEdge:\n                edgeIndex = edgeIter.index()\n                edgeComponent = "{}.e[{}]".format(meshName, edgeIndex)\n                selectedEdges.append(edgeComponent)\n        edgeIter.next()\n    \n    # Slectionner les artes ou vider la slection si aucune ne correspond\n    if selectedEdges:\n        cmds.select(selectedEdges, replace=True)\n        print("Artes slectionnes :", selectedEdges)\n    else:\n        cmds.select(clear=True)\n        print("Aucune arte ne rpond aux critres.")\n\ndef createUI():\n    """\n    Cre une interface utilisateur pour dfinir l\'intervalle d\'aire et de taille des artes.\n    """\n    # Si la fentre existe dj, on la supprime\n    if cmds.window("edgeSelectorWindow", exists=True):\n        cmds.deleteUI("edgeSelectorWindow")\n    \n    window = cmds.window("edgeSelectorWindow", title="Slection d\'artes par aire des faces et taille", widthHeight=(300, 200))\n    cmds.columnLayout(adjustableColumn=True, columnAlign="center")\n    \n    cmds.text(label="Dfinir l\'intervalle d\'aire des faces", align="center", height=20)\n    cmds.floatFieldGrp("areaRangeField", numberOfFields=2, label="Aire (Min, Max):", value1=0.5, value2=2.0)\n    \n    cmds.separator(height=10, style="in")\n    \n    cmds.text(label="Dfinir l\'intervalle de taille des artes", align="center", height=20)\n    cmds.floatFieldGrp("edgeRangeField", numberOfFields=2, label="Taille (Min, Max):", value1=0.1, value2=5.0)\n    \n    cmds.separator(height=10, style="in")\n    \n    cmds.button(label="Slectionner les artes", command=lambda *args: onSelectEdges())\n    \n    cmds.separator(height=10, style="in")\n    \n    cmds.button(label="Fermer", command=lambda *args: cmds.deleteUI(window, window=True))\n    \n    cmds.showWindow(window)\n\ndef onSelectEdges():\n    """\n    Rcupre les valeurs saisies et appelle la fonction de slection.\n    """\n    areaValues = cmds.floatFieldGrp("areaRangeField", query=True, value=True)\n    edgeValues = cmds.floatFieldGrp("edgeRangeField", query=True, value=True)\n    if areaValues and len(areaValues) >= 2 and edgeValues and len(edgeValues) >= 2:\n        minArea = areaValues[0]\n        maxArea = areaValues[1]\n        minEdge = edgeValues[0]\n        maxEdge = edgeValues[1]\n        selectEdgesBasedOnFaceArea(minArea, maxArea, minEdge, maxEdge)\n    else:\n        cmds.error("Veuillez entrer des valeurs valides pour l\'aire et la taille des artes.")\n\n# Excuter l\'interface utilisateur\ncreateUI()\n'}, {'category': 'Action', 'label': 'Sel_Loop', 'tooltip': 'polySelectEdgesEveryN "edgeRing" 1;', 'source': 'mel', 'command': 'polySelectEdgesEveryN "edgeRing" 0;'}, {'category': 'Action', 'label': 'PtoVert', 'tooltip': 'Snap the pivot to the nearest Vertex', 'source': 'python', 'command': 'import maya.api.OpenMaya as om\nimport maya.cmds as cmds\n\ndef move_pivot_to_nearest_vertex():\n    # Get the selected object\n    selection = cmds.ls(selection=True, long=True)\n    if not selection:\n        cmds.warning("Please select an object.")\n        return\n\n    obj = selection[0]\n\n    # Get the current pivot position in world space\n    pivot_pos = cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True)\n    pivot_point = om.MPoint(pivot_pos)\n\n    # Get the DAG path of the object\n    sel_list = om.MSelectionList()\n    sel_list.add(obj)\n    dag_path = sel_list.getDagPath(0)\n\n    # Ensure the object has a mesh\n    try:\n        mesh = om.MFnMesh(dag_path)\n    except:\n        cmds.warning("Selected object does not have a mesh.")\n        return\n\n    # Initialize variables to find the nearest vertex\n    closest_vertex_index = None\n    min_distance = float(\'inf\')\n\n    # Iterate through each vertex to find the closest one\n    for i in range(mesh.numVertices):\n        vertex_point = mesh.getPoint(i, om.MSpace.kWorld)\n        distance = (vertex_point - pivot_point).length()\n        if distance < min_distance:\n            min_distance = distance\n            closest_vertex_index = i\n\n    # If a closest vertex is found, move the pivot to its position\n    if closest_vertex_index is not None:\n        closest_vertex_pos = mesh.getPoint(closest_vertex_index, om.MSpace.kWorld)\n        cmds.xform(obj, worldSpace=True, pivots=(closest_vertex_pos.x, closest_vertex_pos.y, closest_vertex_pos.z))\n        print(f"Pivot moved to vertex {closest_vertex_index} at position {closest_vertex_pos}.")\n    else:\n        cmds.warning("No vertices found on the mesh.")\n\n# Execute the function\nmove_pivot_to_nearest_vertex()\n'}, {'category': 'Action', 'label': 'BB Scale', 'tooltip': 'bt_boundingBoxScaleWindow;', 'source': 'mel', 'command': 'bt_boundingBoxScaleWindow;\n'}, {'category': 'Action', 'label': 'Distance', 'tooltip': 'Set a distance between 2 selected objects', 'source': 'mel', 'command': 'global proc alignLastSelectedByDistance() {\n    // Obtenir la slection\n    string $selection[] = `ls -sl -flatten`;\n\n    // Vrifier que deux lments sont slectionns\n    if (size($selection) != 2) {\n        error "Veuillez slectionner exactement deux objets ou composants.";\n        return;\n    }\n\n    // Ouvrir une fentre pour demander la distance\n    if (`window -exists alignLastSelectedWindow`) {\n        deleteUI alignLastSelectedWindow;\n    }\n    \n    window -title "Aligner par Distance" -widthHeight 300 100 alignLastSelectedWindow;\n    \n    columnLayout -adjustableColumn true;\n    text -label "Entrez la distance pour aligner le dernier lment slectionn :";\n    floatFieldGrp -label "Distance" -value1 0.0 distanceField;\n    button -label "Aligner" -command ("alignLastObjectOrComponent \\"" + $selection[0] + "\\" \\"" + $selection[1] + "\\"");\n    showWindow alignLastSelectedWindow;\n}\n\nglobal proc alignLastObjectOrComponent(string $first, string $last) {\n    // Obtenir la distance souhaite\n    float $distance = `floatFieldGrp -q -value1 distanceField`;\n\n    // Obtenir les positions des lments\n    vector $posFirst = getWorldPosition($first);\n    vector $posLast = getWorldPosition($last);\n\n    // Calculer le vecteur directionnel\n    vector $direction = unit($posLast - $posFirst);\n\n    // Calculer la nouvelle position du dernier lment\n    vector $newPosLast = $posFirst + ($direction * $distance);\n\n    // Dplacer le dernier lment vers la nouvelle position\n    setWorldPosition($last, $newPosLast);\n\n    // Fermer la fentre\n    if (`window -exists alignLastSelectedWindow`) {\n        deleteUI alignLastSelectedWindow;\n    }\n\n    print ("Dernier lment align  une distance de : " + $distance + "\\n");\n}\n\nglobal proc vector getWorldPosition(string $selection) {\n    // Obtenir la position en espace monde d\'un objet ou d\'un composant\n    if (`objExists $selection`) {\n        // C\'est un objet\n        float $pos[] = `xform -q -ws -t $selection`;\n        return <<$pos[0], $pos[1], $pos[2]>>;\n    } else {\n        // C\'est un composant (e.g., sommet, CV)\n        float $pos[] = `pointPosition -w $selection`;\n        return <<$pos[0], $pos[1], $pos[2]>>;\n    }\n}\n\nglobal proc setWorldPosition(string $selection, vector $position) {\n    // Dfinir la position en espace monde d\'un objet ou d\'un composant\n    if (`objExists $selection`) {\n        // C\'est un objet\n        xform -ws -t ($position.x) ($position.y) ($position.z) $selection;\n    } else {\n        // C\'est un composant (e.g., sommet, CV)\n        move -ws ($position.x) ($position.y) ($position.z) $selection;\n    }\n}\n\n// Excuter le script\nalignLastSelectedByDistance();\n'}, {'category': 'Action', 'label': 'Teleport', 'tooltip': 'Snap Together Tool', 'source': 'mel', 'command': 'SetSnapTogetherTool'}, {'category': 'Action', 'label': 'Quick Set', 'tooltip': 'Quick Select Set...', 'source': 'mel', 'command': 'CreateQuickSelectSet'}, {'category': 'Action', 'label': 'Image', 'tooltip': 'Free Image Plane', 'source': 'mel', 'command': 'CreateImagePlane'}, {'category': 'Nurbs', 'label': 'Extrude', 'tooltip': 'Extrude', 'source': 'mel', 'command': 'performSweepPreset(1,0,0,2,1,1,1,1,0,0,1,0,1,3)'}, {'category': 'Nurbs', 'label': 'Revolve', 'tooltip': 'Revolve', 'source': 'mel', 'command': 'revolvePreset 1 0 0 0 360 0 0.01 3 8 1 0 1 0 0 0 0'}, {'category': 'Nurbs', 'label': 'Planar', 'tooltip': 'Planar', 'source': 'mel', 'command': 'performPlanarTrimPreset 1 3 0 0.01 0 0'}, {'category': 'Nurbs', 'label': 'Convert', 'tooltip': 'NURBS to Polygons', 'source': 'mel', 'command': 'nurbsToPoly -mnd 1  -ch 1 -f 2 -pt 1 -pc 289 -chr 0.1 -ft 0.01 -mel 0.001 -d 0.1 -ut 1 -un 21 -vt 1 -vn 21 -uch 0 -ucr 0 -cht 0.2 -es 0 -ntr 0 -mrt 0 -uss 1\n'}, {'category': 'Nurbs', 'label': 'Sweep', 'tooltip': 'Create sweep mesh based on selected curve(s)', 'source': 'mel', 'command': 'performSweepMesh 0;'}, {'category': 'Deliver', 'label': 'Select UV Borders', 'tooltip': 'Select UV Borders', 'source': 'python', 'command': '# -*- coding: utf-8 -*-\n"""\nselect_uv_shell_perimeters.py\nSafely select the perimeter edges of *every* UV shell on the\ncurrently-selected polygon mesh object(s), whatever flavour of\npolyEvaluate your Maya returns.\n\nUsage\n-----\n1.  Select one or more poly meshes.\n2.  Run:\n        select_perimeter_edges_all_uv_shells()\n"""\n\nimport maya.cmds as cmds\nimport maya.mel as mel\n\n\ndef _uv_components_for_shell(obj, shell_index):\n    """\n    Return a list of UV component strings for one UV shell on `obj`,\n    handling both \'int\' and already-formatted strings.\n    """\n    raw = cmds.polyEvaluate(obj, uvsInShell=shell_index) or []\n\n    # Maya 20182022 usually ? list[int]; some builds ? list[str]\n    comps = []\n    for item in raw:\n        if isinstance(item, int):                       # classic behaviour\n            comps.append(f"{obj}.map[{item}]")\n        else:                                          # already looks like "something.map[...]"\n            comps.append(item)\n    return comps\n\n\ndef select_perimeter_edges_all_uv_shells():\n    """\n    Walk selected transforms, gather every UV-shell perimeter edge,\n    then finish with a single unified edge selection.\n    """\n    xforms = cmds.ls(selection=True, dag=True, type="transform", long=True)\n    if not xforms:\n        cmds.error("Nothing selected. Please select one or more polygon meshes.")\n        return\n\n    perimeter_edges = set()\n\n    for xform in xforms:\n        # Only deal with meshes\n        if not cmds.listRelatives(xform, s=True, ni=True, type="mesh"):\n            cmds.warning(f\'"{xform}" is not a polygon mesh - skipped.\')\n            continue\n\n        shell_count = cmds.polyEvaluate(xform, uvShell=True)\n        for shell_id in range(shell_count):\n            uv_comps = _uv_components_for_shell(xform, shell_id)\n            if not uv_comps:\n                continue\n\n            # 1  Select this shells UVs\n            cmds.select(uv_comps, r=True)\n\n            # 2  Convert UV selection ? perimeter edges\n            mel.eval("ConvertSelectionToEdgePerimeter;")\n\n            # 3  Cache whats now selected\n            perimeter_edges.update(cmds.ls(selection=True, flatten=True) or [])\n\n    # 4  Reselect everything we found\n    if perimeter_edges:\n        cmds.select(list(perimeter_edges), r=True)\n        print(f"Selected {len(perimeter_edges)} unique perimeter edges.")\n    else:\n        cmds.warning("No perimeter edges found on the chosen object(s).")\n\n\n# Auto-run when executed directly (e.g. from Script Editor Execute button)\nif __name__ == "__main__":\n    select_perimeter_edges_all_uv_shells()\n'}, {'category': 'Deliver', 'label': 'UV Orient', 'tooltip': 'Orient UV shells In the same direction', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.mel as mel\nimport maya.api.OpenMaya as om\nimport math\nimport re\n\n# ------------------------------\n# Fonction de log\n# ------------------------------\n\ndef logMessage(msg):\n    """Affiche un message si la case  cocher \'Activer le log\' est active."""\n    if cmds.checkBox("activeLogCB", query=True, value=True):\n        print(msg)\n\n# ------------------------------\n# Fonctions utilitaires\n# ------------------------------\n\ndef getFaceIndices(faceList):\n    """\n    Extrait les indices de face depuis une liste de composants (ex : "pCube.f[23]").\n    """\n    indices = []\n    for comp in faceList:\n        m = re.search(r\'\\[(\\d+)\\]\', comp)\n        if m:\n            indices.append(int(m.group(1)))\n    return indices\n\ndef getUVShells():\n    """\n    Retourne une liste de shells UV, chaque shell tant une liste de composants UV.\n    """\n    sel = cmds.ls(selection=True, flatten=True)\n    if not sel:\n        cmds.error("Veuillez slectionner des UVs dans un UV shell.")\n    uvSel = cmds.polyListComponentConversion(sel, toUV=True)\n    uvSel = cmds.ls(uvSel, flatten=True)\n    \n    shells = []\n    processed = set()\n    for uv in uvSel:\n        if uv in processed:\n            continue\n        cmds.select(uv)\n        cmds.polySelectConstraint(mode=2, type=0x0010, shell=1)\n        shellGroup = cmds.ls(selection=True, flatten=True)\n        cmds.polySelectConstraint(disable=True)\n        if shellGroup:\n            shells.append(shellGroup)\n            processed.update(shellGroup)\n    logMessage("UV Shells trouvs: %s" % shells)\n    return shells\n\ndef getFacesFromUVShell(uvShell):\n    """\n    Convertit un UV shell en faces correspondantes.\n    """\n    cmds.select(uvShell)\n    faceSel = cmds.polyListComponentConversion(toFace=True)\n    faceSel = cmds.ls(faceSel, flatten=True)\n    logMessage("Faces du shell: %s" % faceSel)\n    return faceSel\n\ndef getBoundingBox3D(components):\n    """\n    Retourne la bounding box 3D [xmin, ymin, zmin, xmax, ymax, zmax] des composants donns.\n    """\n    bb = cmds.exactWorldBoundingBox(components)\n    logMessage("Bounding box 3D: %s" % bb)\n    return bb\n\ndef getBoundingBoxUV(uvShell):\n    """\n    Calcule la bounding box UV ([uMin, vMin, uMax, vMax]) du shell UV.\n    """\n    u_vals = []\n    v_vals = []\n    for uv in uvShell:\n        coord = cmds.polyEditUV(uv, query=True)\n        if coord:\n            u_vals.append(coord[0])\n            v_vals.append(coord[1])\n    if not u_vals or not v_vals:\n        return None\n    bbuv = [min(u_vals), min(v_vals), max(u_vals), max(v_vals)]\n    logMessage("Bounding box UV: %s" % bbuv)\n    return bbuv\n\ndef getShellVertices(faceSel):\n    """\n    Retourne les vertices (en 3D) correspondant  la slection de faces.\n    """\n    cmds.select(faceSel)\n    vertSel = cmds.polyListComponentConversion(toVertex=True)\n    vertSel = cmds.ls(vertSel, flatten=True)\n    logMessage("Vertices du shell: %s" % vertSel)\n    return vertSel\n\ndef getVertexPosition(vertex):\n    """\n    Retourne la position 3D du vertex sous forme de tuple (x, y, z).\n    """\n    pos = cmds.pointPosition(vertex, world=True)\n    return pos\n\ndef getVertexUV(vertex, uvShell):\n    """\n    Retourne la coordonne UV associe au vertex, filtre par le shell UV.\n    """\n    uvList = cmds.polyListComponentConversion(vertex, fromVertex=True, toUV=True)\n    uvList = cmds.ls(uvList, flatten=True)\n    for uv in uvList:\n        if uv in uvShell:\n            coord = cmds.polyEditUV(uv, query=True)\n            return coord\n    return None\n\ndef computeWeightedAverageNormal(faceList, dagPath):\n    """\n    Calcule la normale moyenne pondre par l\'aire pour les faces dont les indices\n    sont dans faceList. Renvoie un om.MVector.\n    """\n    totalArea = 0.0\n    sumNormal = om.MVector(0, 0, 0)\n    itPoly = om.MItMeshPolygon(dagPath)\n    faceIndices = set(faceList)\n    while not itPoly.isDone():\n        idx = itPoly.index()\n        if idx in faceIndices:\n            normal = itPoly.getNormal(0, om.MSpace.kWorld)\n            area = itPoly.getArea()\n            totalArea += area\n            sumNormal += normal * area\n        itPoly.next()\n    if totalArea > 0:\n        avg = sumNormal / totalArea\n        logMessage("Normale moyenne pondre: %s" % avg)\n        return avg\n    else:\n        return om.MVector(0, 0, 0)\n\n# ------------------------------\n# Traitement d\'un UV shell\n# ------------------------------\n\ndef processUVShell(uvShell, uvTolerance):\n    """\n    Pour un UV shell, effectue les tapes suivantes :\n      - Calcule la bounding box 3D des faces associes et extrait le Y minimum.\n      - Calcule la normale moyenne pondre par l\'aire des faces.\n      - Selon la direction de la normale (horizontale ou verticale), dfinit les coins cibles :\n          * Si horizontal (normal principalement en X/Z) : 4 coins.\n          * Sinon (normal principalement en Y) : 2 coins, ici (xmin, ymin, zmax) et (xmax, ymin, zmax).\n      - Pour chaque coin, recherche le vertex dont la position 3D est la plus proche.\n      - **VRIFICATION UV MODIFIE :**\n            1. Calcule la bounding box 2D des UVs associs aux vertex identifis.\n            2. Si cette bounding box est plus longue verticalement (V) que horizontalement (U),\n               applique polyRotateUVs 90 1 et recalcule, jusqu\' 4 tentatives maximum.\n            3. Ensuite, compte le pourcentage d\'UV du shell qui sont au-dessus de la V minimale\n               des UV des vertex identifis. Si ce pourcentage est infrieur au seuil dfini (via l\'interface),\n               applique polyRotateUVs 180 1.\n      - Retourne la liste des vertex identifis.\n    """\n    logMessage("Traitement du shell UV: %s" % uvShell)\n    faceSel = getFacesFromUVShell(uvShell)\n    if not faceSel:\n        cmds.warning("Aucune face trouve pour ce shell.")\n        return []\n    bb3d = getBoundingBox3D(faceSel)  # [xmin, ymin, zmin, xmax, ymax, zmax]\n    xmin, ymin, zmin, xmax, ymax, zmax = bb3d\n    verts = getShellVertices(faceSel)\n    if not verts:\n        cmds.warning("Aucun vertex trouv pour ce shell.")\n        return []\n    \n    # Calcul de la normale moyenne pondre par l\'aire\n    faceIndices = getFaceIndices(faceSel)\n    selList = om.MSelectionList()\n    selList.add(faceSel[0])\n    dagPath = selList.getDagPath(0)\n    avgNormal = computeWeightedAverageNormal(faceIndices, dagPath)\n    \n    # Dfinir les coins cibles selon l\'orientation de la normale\n    if abs(avgNormal.y) < max(abs(avgNormal.x), abs(avgNormal.z)):\n        corners = [\n            (xmin, ymin, zmin),\n            (xmin, ymin, zmax),\n            (xmax, ymin, zmax),\n            (xmax, ymin, zmin)\n        ]\n    else:\n        # Pour une normale principalement oriente en Y, on cible les coins en Z+\n        corners = [\n            (xmin, ymin, zmax),\n            (xmax, ymin, zmax)\n        ]\n    logMessage("Coins cibles en 3D: %s" % corners)\n    \n    # Pour chaque coin, trouver le vertex le plus proche\n    selectedVerts = []\n    for corner in corners:\n        bestVert = None\n        bestDist = float(\'inf\')\n        for v in verts:\n            pos = getVertexPosition(v)\n            dist = math.sqrt((pos[0]-corner[0])**2 + (pos[1]-corner[1])**2 + (pos[2]-corner[2])**2)\n            if dist < bestDist:\n                bestDist = dist\n                bestVert = v\n        if bestVert:\n            logMessage("Vertex choisi pour le coin %s: %s (distance = %s)" % (corner, bestVert, bestDist))\n            selectedVerts.append(bestVert)\n    \n    # Calculer la bounding box UV du shell et la valeur minimale de V\n    bbuv = getBoundingBoxUV(uvShell)\n    if bbuv is None:\n        cmds.warning("Impossible de calculer la bounding box UV pour ce shell.")\n        return selectedVerts\n    allUVs = []\n    for v in verts:\n        uv = getVertexUV(v, uvShell)\n        if uv:\n            allUVs.append(uv)\n    if not allUVs:\n        cmds.warning("Impossible de rcuprer les UVs du shell.")\n        return selectedVerts\n    minV = min(uv[1] for uv in allUVs)\n    logMessage("Valeur minV du shell: %s" % minV)\n    \n    # VRIFICATION UV MODIFIE\n    # 5a. Calculer la bounding box 2D des UVs associs aux vertex identifis\n    identifiedUVs = [getVertexUV(v, uvShell) for v in selectedVerts if getVertexUV(v, uvShell) is not None]\n    if identifiedUVs:\n        minU_id = min(uv[0] for uv in identifiedUVs)\n        maxU_id = max(uv[0] for uv in identifiedUVs)\n        minV_id = min(uv[1] for uv in identifiedUVs)\n        maxV_id = max(uv[1] for uv in identifiedUVs)\n        boxWidth = maxU_id - minU_id\n        boxHeight = maxV_id - minV_id\n        logMessage("Bounding box 2D des vertex identifis: width = %s, height = %s" % (boxWidth, boxHeight))\n        \n        # 5b. Si la bounding box est plus longue verticalement (V > U), appliquer des rotations de 90 (max 4 tentatives)\n        attempts = 0\n        while boxHeight > boxWidth and attempts < 4:\n            logMessage("Bounding box verticale dominante. Rotation de 90, tentative #%s" % (attempts+1))\n            mel.eval(\'polyRotateUVs 90 1\')\n            identifiedUVs = [getVertexUV(v, uvShell) for v in selectedVerts if getVertexUV(v, uvShell) is not None]\n            if not identifiedUVs:\n                break\n            minU_id = min(uv[0] for uv in identifiedUVs)\n            maxU_id = max(uv[0] for uv in identifiedUVs)\n            minV_id = min(uv[1] for uv in identifiedUVs)\n            maxV_id = max(uv[1] for uv in identifiedUVs)\n            boxWidth = maxU_id - minU_id\n            boxHeight = maxV_id - minV_id\n            logMessage("Aprs rotation, bounding box 2D: width = %s, height = %s" % (boxWidth, boxHeight))\n            attempts += 1\n        \n        # 5c. Vrifier le pourcentage d\'UV du shell qui sont au-dessus de la V minimale des UV des vertex identifis\n        identified_minV = min(uv[1] for uv in identifiedUVs)\n        allUVsShell = []\n        for uv in uvShell:\n            coord = cmds.polyEditUV(uv, query=True)\n            if coord:\n                allUVsShell.append(coord)\n        if allUVsShell:\n            countAbove = sum(1 for uv in allUVsShell if uv[1] > identified_minV)\n            fraction = countAbove / float(len(allUVsShell))\n            logMessage("Fraction d\'UV au-dessus de la V minimale identifie: %s" % fraction)\n            threshold = cmds.floatFieldGrp("uvPercentageField", query=True, value=True)[0] / 100.0\n            if fraction < threshold:\n                logMessage("Fraction insuffisante (< %s%%). Rotation de 180." % (threshold*100))\n                mel.eval(\'polyRotateUVs 180 1\')\n    \n    return selectedVerts\n\n# ------------------------------\n# Traitement des UV shells slectionns\n# ------------------------------\n\ndef processSelectedUVShells(uvTolerance, selectIdentified):\n    """\n    Pour chaque UV shell slectionn, excute le traitement dcrit et, si selectIdentified est True,\n    slectionne tous les vertex identifis  la fin.\n    """\n    shells = getUVShells()\n    if not shells:\n        cmds.error("Aucun UV shell trouv dans la slection.")\n    allIdentifiedVerts = []\n    for shell in shells:\n        cmds.select(shell)\n        vertsIdentified = processUVShell(shell, uvTolerance)\n        if vertsIdentified:\n            allIdentifiedVerts.extend(vertsIdentified)\n    cmds.select(clear=True)\n    if selectIdentified and allIdentifiedVerts:\n        cmds.select(allIdentifiedVerts, replace=True)\n        logMessage("Vertex identifis slectionns: %s" % allIdentifiedVerts)\n        cmds.confirmDialog(title=\'Traitement termin\', message=\'Les UV shells ont t traits et les vertex identifis sont slectionns.\')\n    else:\n        cmds.confirmDialog(title=\'Traitement termin\', message=\'Les UV shells ont t traits.\')\n\n# ------------------------------\n# Interface utilisateur\n# ------------------------------\n\ndef createUI():\n    """\n    Cre une interface utilisateur pour dfinir :\n      - La tolrance UV pour la vrification des UV (en units UV).\n      - Le pourcentage minimum d\'UV du shell devant tre au-dessus des UV des vertex identifis.\n      - Si les vertex identifis doivent tre slectionns  la fin.\n      - Si le log doit tre activ.\n    """\n    windowName = "uvShellCorrectionWindow"\n    if cmds.window(windowName, exists=True):\n        cmds.deleteUI(windowName)\n    window = cmds.window(windowName, title="Correction UV Shells", widthHeight=(320, 240))\n    cmds.columnLayout(adjustableColumn=True, columnAlign="center")\n    cmds.text(label="Tolrance pour la vrification V- (units UV):", align="center", height=20)\n    cmds.floatFieldGrp("uvToleranceField", numberOfFields=1, label="Tolrance:", value1=0.01, precision=4)\n    cmds.separator(height=10, style="in")\n    cmds.checkBox("selectIdentifiedVertsCB", label="Slectionner les vertex identifis", value=True)\n    cmds.separator(height=10, style="in")\n    cmds.text(label="Pourcentage minimum d\'UV au-dessus (en %):", align="center", height=20)\n    cmds.floatFieldGrp("uvPercentageField", numberOfFields=1, label="Pourcentage:", value1=90.0, precision=2)\n    cmds.separator(height=10, style="in")\n    cmds.checkBox("activeLogCB", label="Activer le log", value=False)\n    cmds.separator(height=10, style="in")\n    cmds.button(label="Traiter les UV shells", command=lambda *args: onProcessUI())\n    cmds.separator(height=10, style="in")\n    cmds.button(label="Fermer", command=lambda *args: cmds.deleteUI(window, window=True))\n    cmds.showWindow(window)\n\ndef onProcessUI():\n    uvTol = cmds.floatFieldGrp("uvToleranceField", query=True, value=True)[0]\n    selectIdentified = cmds.checkBox("selectIdentifiedVertsCB", query=True, value=True)\n    processSelectedUVShells(uvTol, selectIdentified)\n\n# Excuter l\'interface\ncreateUI()\n'}, {'category': 'Deliver', 'label': 'TrimAuto', 'tooltip': 'Using A trimmed plane as a reference, it automaticly place the UV Shells inside Trimmed Area', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport random\n\n# Global storage for selections\nglobal_trimmed_plane = None      # Will store the trimmed plane object name\nglobal_uv_shells = []            # Will store a list of UV shell groups (each is a list of UV component names)\n\n# -----------------------------\n# Helper functions\n# -----------------------------\n\ndef get_uv_shells_from_selection(selection):\n    """\n    Given a list of UV components (from selection), group them by UV shell.\n    Returns a list of shells; each shell is a list of UV component names.\n    """\n    shells = []\n    processed = set()\n    # Convert selection to UV components\n    all_uvs = cmds.polyListComponentConversion(selection, toUV=True)\n    if not all_uvs:\n        return shells\n    all_uvs = cmds.ls(all_uvs, flatten=True)\n    \n    for uv in all_uvs:\n        if uv in processed:\n            continue\n        # Select one UV and expand to the entire shell:\n        cmds.select(uv, replace=True)\n        cmds.polySelectConstraint(mode=2, type=0x0010, shell=1)\n        shell_group = cmds.ls(selection=True, flatten=True)\n        cmds.polySelectConstraint(disable=True)\n        if shell_group:\n            shells.append(shell_group)\n            processed.update(shell_group)\n    return shells\n\ndef get_uv_shell_bbox(uv_shell):\n    """\n    Given a list of UV component names, compute the bounding box in UV space.\n    Returns a dictionary with minU, maxU, minV, maxV, center_U, center_V, and height.\n    """\n    minU = minV = 1e9\n    maxU = maxV = -1e9\n    for uv in uv_shell:\n        # Query the UV coordinate; polyEditUV returns [u, v]\n        coord = cmds.polyEditUV(uv, query=True)\n        if not coord:\n            continue\n        u, v = coord[0], coord[1]\n        minU = min(minU, u)\n        maxU = max(maxU, u)\n        minV = min(minV, v)\n        maxV = max(maxV, v)\n    center_U = (minU + maxU) / 2.0\n    center_V = (minV + maxV) / 2.0\n    height = maxV - minV\n    return {\n        \'minU\': minU,\n        \'maxU\': maxU,\n        \'minV\': minV,\n        \'maxV\': maxV,\n        \'center_U\': center_U,\n        \'center_V\': center_V,\n        \'height\': height\n    }\n\ndef translate_uv_shell(uv_shell, du, dv):\n    """\n    Translates every UV in the shell by du, dv.\n    """\n    for uv in uv_shell:\n        cmds.polyEditUV(uv, u=du, v=dv, relative=True)\n\ndef scale_uv_shell_V(uv_shell, scale_factor, pivotV):\n    """\n    Scales the UV shell in the V axis by scale_factor relative to the pivotV.\n    Each UV\'s V coordinate is adjusted by a relative offset computed as:\n        delta_v = (currentV - pivotV) * (scale_factor - 1)\n    so that the scaling occurs about pivotV.\n    """\n    for uv in uv_shell:\n        coord = cmds.polyEditUV(uv, query=True)\n        if not coord:\n            continue\n        v = coord[1]\n        delta_v = (v - pivotV) * (scale_factor - 1)\n        cmds.polyEditUV(uv, v=delta_v, relative=True)\n\n# -----------------------------\n# UI Functions\n# -----------------------------\n\ndef save_trimmed_plane(*args):\n    """\n    Save the selected trimmed plane.\n    """\n    global global_trimmed_plane\n    sel = cmds.ls(selection=True)\n    if not sel:\n        cmds.confirmDialog(title=\'Error\', message=\'No object selected for trimmed plane.\')\n        return\n    global_trimmed_plane = sel[0]\n    cmds.confirmDialog(title=\'Saved\', message=\'Trimmed plane saved: \' + global_trimmed_plane)\n\ndef save_uv_shells(*args):\n    """\n    Save the selected UV shells.\n    """\n    global global_uv_shells\n    sel = cmds.ls(selection=True)\n    if not sel:\n        cmds.confirmDialog(title=\'Error\', message=\'No UV components selected.\')\n        return\n    shells = get_uv_shells_from_selection(sel)\n    if not shells:\n        cmds.confirmDialog(title=\'Error\', message=\'Could not determine UV shells from selection.\')\n        return\n    global_uv_shells = shells\n    cmds.confirmDialog(title=\'Saved\', message=f\'{len(shells)} UV shell(s) saved.\')\n\ndef execute_processing(*args):\n    """\n    For each saved UV shell, find the trimmed plane UV shell with the closest height\n    within a tolerance range (as defined in the UI), center it, scale the shell in the V axis\n    so that its height matches the target, and then apply a random horizontal (U axis)\n    translation. If any UV falls outside the [0,1] U/V area after the random translation,\n    the shell is shifted back so that it fully lies within [0,1].\n    """\n    global global_trimmed_plane, global_uv_shells\n    if not global_trimmed_plane:\n        cmds.confirmDialog(title=\'Error\', message=\'No trimmed plane saved.\')\n        return\n    if not global_uv_shells:\n        cmds.confirmDialog(title=\'Error\', message=\'No UV shells saved.\')\n        return\n    \n    # Get tolerance percentage from UI\n    tolerance_percent = cmds.floatField(\'toleranceField\', query=True, value=True)\n\n    # Get all UV shells from the trimmed plane.\n    trimmed_plane_shells = get_uv_shells_from_selection([global_trimmed_plane])\n    if not trimmed_plane_shells:\n        cmds.confirmDialog(title=\'Error\', message=\'No UV shells found on the trimmed plane.\')\n        return\n\n    # Process each saved UV shell.\n    for sel_shell in global_uv_shells:\n        # Compute bounding box for the selected UV shell.\n        bbox_sel = get_uv_shell_bbox(sel_shell)\n        height_sel = bbox_sel[\'height\']\n        center_sel = (bbox_sel[\'center_U\'], bbox_sel[\'center_V\'])\n        \n        # Find candidate trimmed plane UV shells within the tolerance range.\n        candidate_shells = []\n        for t_shell in trimmed_plane_shells:\n            bbox_t = get_uv_shell_bbox(t_shell)\n            if abs(bbox_t[\'height\'] - height_sel) <= tolerance_percent * height_sel:\n                candidate_shells.append((t_shell, bbox_t))\n        \n        # Choose a target shell.\n        if candidate_shells:\n            target_shell = random.choice(candidate_shells)\n        else:\n            # Fallback: choose the shell with the minimum absolute difference.\n            min_diff = 1e9\n            target_shell = None\n            for t_shell in trimmed_plane_shells:\n                bbox_t = get_uv_shell_bbox(t_shell)\n                diff = abs(bbox_t[\'height\'] - height_sel)\n                if diff < min_diff:\n                    min_diff = diff\n                    target_shell = (t_shell, bbox_t)\n        if not target_shell:\n            continue  # Skip if no matching shell is found\n\n        t_shell, bbox_target = target_shell\n        center_target = (bbox_target[\'center_U\'], bbox_target[\'center_V\'])\n        target_height = bbox_target[\'height\']\n\n        # Translate the selected shell to center with the target trimmed plane UV shell.\n        du = center_target[0] - center_sel[0]\n        dv = center_target[1] - center_sel[1]\n        translate_uv_shell(sel_shell, du, dv)\n\n        # Recompute the bounding box after translation.\n        bbox_sel = get_uv_shell_bbox(sel_shell)\n        height_sel = bbox_sel[\'height\']\n        pivotV = bbox_sel[\'center_V\']\n\n        # Scale the selected shell in the V axis so its height matches the target height.\n        if height_sel > 0:\n            scale_factor = target_height / height_sel\n            scale_uv_shell_V(sel_shell, scale_factor, pivotV)\n        \n        # --- Random Horizontal Translation and Clamping ---\n        # Generate a random U offset between -1 and 1.\n        rand_u_offset = random.uniform(-1, 1)\n        translate_uv_shell(sel_shell, rand_u_offset, 0)\n        \n        # Check the bounding box after random translation.\n        bbox_after = get_uv_shell_bbox(sel_shell)\n        du_correction = 0\n        dv_correction = 0\n        \n        # Correct U if out of bounds.\n        if bbox_after[\'minU\'] < 0:\n            du_correction = -bbox_after[\'minU\']\n        elif bbox_after[\'maxU\'] > 1:\n            du_correction = 1 - bbox_after[\'maxU\']\n        \n        # Optionally, check V as well in case it goes out of bounds.\n        if bbox_after[\'minV\'] < 0:\n            dv_correction = -bbox_after[\'minV\']\n        elif bbox_after[\'maxV\'] > 1:\n            dv_correction = 1 - bbox_after[\'maxV\']\n        \n        if du_correction != 0 or dv_correction != 0:\n            translate_uv_shell(sel_shell, du_correction, dv_correction)\n        \n    cmds.confirmDialog(title=\'Processing Complete\', message=\'All selected UV shells have been centered, scaled, and randomly translated.\')\n\ndef create_ui():\n    """\n    Create the interface.\n    """\n    if cmds.window(\'uvShellProcessWindow\', exists=True):\n        cmds.deleteUI(\'uvShellProcessWindow\')\n    \n    window = cmds.window(\'uvShellProcessWindow\', title=\'UV Shell Processor\', widthHeight=(300, 320))\n    cmds.columnLayout(adjustableColumn=True, rowSpacing=10)\n    \n    cmds.text(label=\'Step 1: Save Trimmed Plane\')\n    cmds.button(label=\'Save Selected Trimmed Plane\', command=save_trimmed_plane)\n    \n    cmds.separator(height=10, style=\'in\')\n    \n    cmds.text(label=\'Step 2: Save UV Shells to Process\')\n    cmds.button(label=\'Save Selected UV Shells\', command=save_uv_shells)\n    \n    cmds.separator(height=10, style=\'in\')\n    \n    cmds.text(label=\'Step 3: Adjust Tolerance, Process, and Random U Translation\')\n    cmds.text(label=\'Tolerance Percentage (e.g., 0.10 for 10%):\')\n    cmds.floatField(\'toleranceField\', value=0.10, minValue=0.0, maxValue=1.0)\n    \n    cmds.separator(height=10, style=\'in\')\n    \n    cmds.button(label=\'Execute\', command=execute_processing)\n    \n    cmds.showWindow(window)\n\n# Run the UI\ncreate_ui()\n'}, {'category': 'Deliver', 'label': 'Share Face Select', 'tooltip': 'Select faces that share the same space', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport math\n\n# ---------- Utilitaires gomtrie ----------\ndef _round_with_tol(p, eps):\n    return (round(p[0] / eps) * eps,\n            round(p[1] / eps) * eps,\n            round(p[2] / eps) * eps)\n\ndef _get_mesh_shape_from_selection():\n    sel = cmds.ls(selection=True, dag=True, shapes=True, type=\'mesh\')\n    if not sel:\n        sel_tr = cmds.ls(selection=True, type=\'transform\')\n        if len(sel_tr) != 1:\n            cmds.warning("Slectionne exactement un mesh (transform ou shape).")\n            return None\n        shapes = cmds.listRelatives(sel_tr[0], s=True, fullPath=True, type=\'mesh\') or []\n        if not shapes:\n            cmds.warning("Objet slectionn invalide (pas de mesh).")\n            return None\n        return shapes[0]\n    if len(sel) > 1:\n        cmds.warning("Plusieurs meshes slectionns  je prends le premier.")\n    return sel[0]\n\ndef _cache_vertex_positions(mesh_shape):\n    vtx_count = cmds.polyEvaluate(mesh_shape, vertex=True)\n    if not vtx_count:\n        return {}\n    vtx_comps = [f"{mesh_shape}.vtx[{i}]" for i in range(vtx_count)]\n    flat = cmds.xform(vtx_comps, q=True, ws=True, t=True)\n    return {i: (flat[3*i], flat[3*i+1], flat[3*i+2]) for i in range(vtx_count)}\n\ndef _face_vertices_indices(mesh_shape, face_index):\n    info = cmds.polyInfo(f"{mesh_shape}.f[{face_index}]", faceToVertex=True)\n    if not info:\n        return []\n    tokens = info[0].replace(\',\', \' \').split()\n    vtx_ids = []\n    for tok in tokens:\n        try:\n            vtx_ids.append(int(tok))\n        except:\n            pass\n    return vtx_ids\n\ndef _dedupe_positions_with_tol(positions, eps):\n    seen = set()\n    out = []\n    for p in positions:\n        q = _round_with_tol(p, eps)\n        if q not in seen:\n            seen.add(q)\n            out.append(q)\n    return out\n\ndef get_face_signature(mesh_shape, face_index, vtx_pos_cache, eps):\n    vtx_ids = _face_vertices_indices(mesh_shape, face_index)\n    if not vtx_ids:\n        return None\n    positions = [vtx_pos_cache[i] for i in vtx_ids]\n    q_positions = _dedupe_positions_with_tol(positions, eps)\n    q_positions.sort()  # insensible  l\'ordre\n    return tuple(q_positions)\n\n# ---------- Logique de slection ----------\ndef find_identical_faces(mesh_shape, tolerance):\n    face_count = cmds.polyEvaluate(mesh_shape, face=True)\n    if not face_count or face_count < 2:\n        cmds.warning("Mesh trop petit ou invalide.")\n        return []\n\n    vtx_pos_cache = _cache_vertex_positions(mesh_shape)\n    groups = {}\n    for f in range(face_count):\n        sig = get_face_signature(mesh_shape, f, vtx_pos_cache, eps=tolerance)\n        if sig is None:\n            continue\n        groups.setdefault(sig, []).append(f)\n\n    # Ne garder que les groupes avec au moins 2 faces identiques\n    dup_groups = [inds for inds in groups.values() if len(inds) > 1]\n    return dup_groups\n\ndef select_identical_faces(tolerance=0.01, select_all=False):\n    mesh_shape = _get_mesh_shape_from_selection()\n    if not mesh_shape:\n        return\n\n    dup_groups = find_identical_faces(mesh_shape, tolerance)\n    if not dup_groups:\n        cmds.warning("Aucune face identique trouve (tolrance = {}).".format(tolerance))\n        return\n\n    if select_all:\n        chosen = [f"{mesh_shape}.f[{i}]" for group in dup_groups for i in group]\n    else:\n        chosen = [f"{mesh_shape}.f[{group[0]}]" for group in dup_groups]\n\n    cmds.select(chosen, r=True)\n    mode = "toutes les faces des groupes" if select_all else "1 face par groupe"\n    print("Tolrance utilise:", tolerance)\n    print("Mode:", mode)\n    print("Slection:", chosen)\n\n# ---------- Interface utilisateur ----------\ndef show_identical_faces_ui():\n    if cmds.window("identicalFacesWin", exists=True):\n        cmds.deleteUI("identicalFacesWin")\n\n    win = cmds.window("identicalFacesWin", title="Faces identiques - Tolrance", sizeable=False)\n    col = cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAlign="center")\n\n    cmds.text(label="Tolrance (monde) :", align="center")\n    # floatSliderGrp avec champ de saisie (field=True) pour valeurs prcises comme 0.0025\n    tol_grp = cmds.floatSliderGrp(\n        "tolSliderGrp",\n        field=True,\n        minValue=0.0001,\n        maxValue=1.0,\n        value=0.01,\n        fieldMinValue=0.000001,  # autorise la saisie en dessous si besoin\n        fieldMaxValue=100.0,     # autorise la saisie plus large si besoin\n        precision=6,             # affichage lisible 0.002500\n        step=0.0001              # pas du slider; la saisie texte permet du plus fin\n    )\n\n    # Boutons de presets pratiques\n    row = cmds.rowLayout(numberOfColumns=5, adjustableColumn=5, columnAlign=(1, "center"))\n    for preset in (0.1, 0.01, 0.005, 0.0025):\n        cmds.button(label=str(preset),\n                    c=lambda *_ , v=preset: cmds.floatSliderGrp(tol_grp, e=True, value=v))\n    cmds.setParent(\'..\')\n\n    # Option slectionner tout le groupe\n    sel_all_chk = cmds.checkBox("selAllChk", label="Slectionner TOUTES les faces de chaque groupe", value=False)\n\n    # Bouton d\'action\n    def _run(*args):\n        tol = cmds.floatSliderGrp(tol_grp, q=True, value=True)\n        select_all = cmds.checkBox(sel_all_chk, q=True, value=True)\n        # clamp minimal de scurit\n        tol = max(1e-8, float(tol))\n        select_identical_faces(tolerance=tol, select_all=select_all)\n\n    cmds.button(label="Dtecter & Slectionner", command=_run, bgc=(0.3, 0.6, 0.3), height=30)\n    cmds.separator(h=8, style=\'in\')\n    cmds.text(label="Astuce : utilise le champ texte pour entrer des valeurs fines (ex : 0.0025).", align="center")\n    cmds.showWindow(win)\n\n# Lancer l\'UI\nshow_identical_faces_ui()\n'}, {'category': 'Deliver', 'label': 'Select Face Mat', 'tooltip': 'Select all faces assigned to a material', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.api.OpenMaya as om2\n\n# Qt import compatible Maya 2018 -> 2025\ntry:\n    from PySide6 import QtCore, QtGui, QtWidgets\n    from shiboken6 import wrapInstance\nexcept ImportError:\n    from PySide2 import QtCore, QtGui, QtWidgets\n    from shiboken2 import wrapInstance\n\nimport maya.OpenMayaUI as omui\n\n\ndef get_maya_main_window():\n    ptr = omui.MQtUtil.mainWindow()\n    return wrapInstance(int(ptr), QtWidgets.QWidget)\n\n\ndef _warn(msg):\n    cmds.warning("[MaterialSelector] " + str(msg))\n\n\nclass MaterialRowWidget(QtWidgets.QWidget):\n    ACTIONS = ["Do Nothing", "To Delete", "To Mirror"]\n\n    def __init__(self, material_name, swatch_icon=None, parent=None):\n        super(MaterialRowWidget, self).__init__(parent)\n        self.material_name = material_name\n\n        lay = QtWidgets.QHBoxLayout(self)\n        lay.setContentsMargins(6, 2, 6, 2)\n        lay.setSpacing(8)\n\n        self.icon_lbl = QtWidgets.QLabel()\n        self.icon_lbl.setFixedSize(18, 18)\n        if swatch_icon:\n            pix = swatch_icon.pixmap(14, 14)\n            self.icon_lbl.setPixmap(pix)\n        lay.addWidget(self.icon_lbl)\n\n        self.name_lbl = QtWidgets.QLabel(material_name)\n        self.name_lbl.setMinimumWidth(240)\n        self.name_lbl.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)\n        lay.addWidget(self.name_lbl, 1)\n\n        self.action_combo = QtWidgets.QComboBox()\n        self.action_combo.addItems(self.ACTIONS)\n        self.action_combo.setFixedWidth(120)\n        lay.addWidget(self.action_combo)\n\n        self.pair_edit = QtWidgets.QLineEdit()\n        self.pair_edit.setPlaceholderText("Pair (A)")\n        self.pair_edit.setFixedWidth(70)\n        self.pair_edit.setMaxLength(2)\n        lay.addWidget(self.pair_edit)\n\n    def get_action(self):\n        return self.action_combo.currentText()\n\n    def set_action(self, action_text):\n        idx = self.action_combo.findText(action_text)\n        if idx >= 0:\n            self.action_combo.setCurrentIndex(idx)\n\n    def get_pair(self):\n        t = (self.pair_edit.text() or "").strip()\n        if not t:\n            return ""\n        return t[0].upper()\n\n    def set_pair(self, pair_text):\n        t = (pair_text or "").strip()\n        self.pair_edit.setText(t[:1].upper() if t else "")\n\n\nclass MaterialSelectorUI(QtWidgets.QDialog):\n    def __init__(self, parent=get_maya_main_window()):\n        super(MaterialSelectorUI, self).__init__(parent)\n\n        self.setWindowTitle("Material Selector")\n        self.setMinimumWidth(720)\n        self.setMinimumHeight(950)\n\n        self._script_job = None\n        self._swatch_cache = {}\n        self._action_cache = {}\n\n        self.build_ui()\n        self.create_connections()\n        self.install_script_job()\n        self.refresh_materials()\n\n    # -------------------------\n    # UI\n    # -------------------------\n    def build_ui(self):\n        main_layout = QtWidgets.QVBoxLayout(self)\n        main_layout.setContentsMargins(10, 10, 10, 10)\n        main_layout.setSpacing(10)\n\n        # Sorting\n        sort_group = QtWidgets.QGroupBox("Sorting")\n        sort_layout = QtWidgets.QVBoxLayout(sort_group)\n        sort_layout.setContentsMargins(10, 10, 10, 10)\n        sort_layout.setSpacing(8)\n\n        sort_layout.addWidget(QtWidgets.QLabel("Sort materials list by:"))\n        self.sort_combo = QtWidgets.QComboBox()\n        self.sort_combo.addItems([\n            "Name (A ? Z)",\n            "Name (Z ? A)",\n            "Polygons (Low ? High)",\n            "Polygons (High ? Low)",\n        ])\n        sort_layout.addWidget(self.sort_combo)\n\n        # Symmetry tools (kept)\n        sym_group = QtWidgets.QGroupBox("Side selection / Symmetry check (Object space)")\n        sym_layout = QtWidgets.QGridLayout(sym_group)\n        sym_layout.setContentsMargins(10, 10, 10, 10)\n        sym_layout.setHorizontalSpacing(10)\n        sym_layout.setVerticalSpacing(8)\n\n        self.axis_combo = QtWidgets.QComboBox()\n        self.axis_combo.addItems(["X", "Y", "Z"])\n\n        self.side_combo = QtWidgets.QComboBox()\n        self.side_combo.addItems(["+", "-"])\n\n        self.side_tol_spin = QtWidgets.QDoubleSpinBox()\n        self.side_tol_spin.setDecimals(6)\n        self.side_tol_spin.setRange(0.0, 100000.0)\n        self.side_tol_spin.setSingleStep(0.001)\n        self.side_tol_spin.setValue(0.0001)\n\n        self.match_tol_spin = QtWidgets.QDoubleSpinBox()\n        self.match_tol_spin.setDecimals(6)\n        self.match_tol_spin.setRange(0.0, 100000.0)\n        self.match_tol_spin.setSingleStep(0.001)\n        self.match_tol_spin.setValue(0.001)\n\n        sym_layout.addWidget(QtWidgets.QLabel("Axis:"), 0, 0)\n        sym_layout.addWidget(self.axis_combo, 0, 1)\n        sym_layout.addWidget(QtWidgets.QLabel("Side (for select):"), 0, 2)\n        sym_layout.addWidget(self.side_combo, 0, 3)\n\n        sym_layout.addWidget(QtWidgets.QLabel("Side tolerance:"), 1, 0)\n        sym_layout.addWidget(self.side_tol_spin, 1, 1, 1, 3)\n\n        sym_layout.addWidget(QtWidgets.QLabel("Match tolerance (mirror):"), 2, 0)\n        sym_layout.addWidget(self.match_tol_spin, 2, 1, 1, 3)\n\n        self.select_side_btn = QtWidgets.QPushButton("Select Faces (Side)")\n        self.find_sym_mismatch_btn = QtWidgets.QPushButton("Find Symmetry Mismatch")\n\n        sym_layout.addWidget(self.select_side_btn, 3, 0, 1, 4)\n        sym_layout.addWidget(self.find_sym_mismatch_btn, 4, 0, 1, 4)\n\n        # Batch actions\n        batch_group = QtWidgets.QGroupBox("Batch Actions (Delete / Mirror by Pair)")\n        batch_layout = QtWidgets.QVBoxLayout(batch_group)\n        batch_layout.setContentsMargins(10, 10, 10, 10)\n        batch_layout.setSpacing(10)\n\n        # --- polyMirrorFace settings\n        pm_group = QtWidgets.QGroupBox("polyMirrorFace settings")\n        pm_layout = QtWidgets.QGridLayout(pm_group)\n        pm_layout.setContentsMargins(10, 10, 10, 10)\n        pm_layout.setHorizontalSpacing(10)\n        pm_layout.setVerticalSpacing(8)\n\n        self.pm_cutMesh = QtWidgets.QComboBox()\n        self.pm_cutMesh.addItems(["0", "1"])\n        self.pm_cutMesh.setCurrentText("1")\n\n        self.pm_axis = QtWidgets.QComboBox()\n        self.pm_axis.addItems(["0 (X)", "1 (Y)", "2 (Z)"])\n        self.pm_axis.setCurrentIndex(0)\n\n        self.pm_axisDir = QtWidgets.QComboBox()\n        self.pm_axisDir.addItems(["0", "1"])\n        self.pm_axisDir.setCurrentText("0")\n\n        self.pm_mergeMode = QtWidgets.QComboBox()\n        self.pm_mergeMode.addItems(["0", "1", "2", "3"])\n        self.pm_mergeMode.setCurrentText("3")\n\n        self.pm_mergeThresholdType = QtWidgets.QComboBox()\n        self.pm_mergeThresholdType.addItems(["0", "1"])\n        self.pm_mergeThresholdType.setCurrentText("0")\n\n        self.pm_mergeThreshold = QtWidgets.QDoubleSpinBox()\n        self.pm_mergeThreshold.setDecimals(6)\n        self.pm_mergeThreshold.setRange(0.0, 100000.0)\n        self.pm_mergeThreshold.setSingleStep(0.001)\n        self.pm_mergeThreshold.setValue(0.001)\n\n        self.pm_mirrorAxis = QtWidgets.QComboBox()\n        self.pm_mirrorAxis.addItems(["0", "1", "2"])\n        self.pm_mirrorAxis.setCurrentText("1")\n\n        self.pm_mirrorPosition = QtWidgets.QDoubleSpinBox()\n        self.pm_mirrorPosition.setDecimals(6)\n        self.pm_mirrorPosition.setRange(-100000.0, 100000.0)\n        self.pm_mirrorPosition.setSingleStep(0.1)\n        self.pm_mirrorPosition.setValue(0.0)\n\n        self.pm_smoothingAngle = QtWidgets.QDoubleSpinBox()\n        self.pm_smoothingAngle.setDecimals(3)\n        self.pm_smoothingAngle.setRange(0.0, 180.0)\n        self.pm_smoothingAngle.setSingleStep(1.0)\n        self.pm_smoothingAngle.setValue(30.0)\n\n        self.pm_flipUVs = QtWidgets.QComboBox()\n        self.pm_flipUVs.addItems(["0", "1"])\n        self.pm_flipUVs.setCurrentText("0")\n\n        self.pm_ch = QtWidgets.QComboBox()\n        self.pm_ch.addItems(["0", "1"])\n        self.pm_ch.setCurrentText("1")\n\n        pm_layout.addWidget(QtWidgets.QLabel("cutMesh:"), 0, 0)\n        pm_layout.addWidget(self.pm_cutMesh, 0, 1)\n        pm_layout.addWidget(QtWidgets.QLabel("axis:"), 0, 2)\n        pm_layout.addWidget(self.pm_axis, 0, 3)\n\n        pm_layout.addWidget(QtWidgets.QLabel("axisDirection:"), 1, 0)\n        pm_layout.addWidget(self.pm_axisDir, 1, 1)\n        pm_layout.addWidget(QtWidgets.QLabel("mergeMode:"), 1, 2)\n        pm_layout.addWidget(self.pm_mergeMode, 1, 3)\n\n        pm_layout.addWidget(QtWidgets.QLabel("mergeThresholdType:"), 2, 0)\n        pm_layout.addWidget(self.pm_mergeThresholdType, 2, 1)\n        pm_layout.addWidget(QtWidgets.QLabel("mergeThreshold:"), 2, 2)\n        pm_layout.addWidget(self.pm_mergeThreshold, 2, 3)\n\n        pm_layout.addWidget(QtWidgets.QLabel("mirrorAxis:"), 3, 0)\n        pm_layout.addWidget(self.pm_mirrorAxis, 3, 1)\n        pm_layout.addWidget(QtWidgets.QLabel("mirrorPosition:"), 3, 2)\n        pm_layout.addWidget(self.pm_mirrorPosition, 3, 3)\n\n        pm_layout.addWidget(QtWidgets.QLabel("smoothingAngle:"), 4, 0)\n        pm_layout.addWidget(self.pm_smoothingAngle, 4, 1)\n        pm_layout.addWidget(QtWidgets.QLabel("flipUVs:"), 4, 2)\n        pm_layout.addWidget(self.pm_flipUVs, 4, 3)\n\n        pm_layout.addWidget(QtWidgets.QLabel("ch:"), 5, 0)\n        pm_layout.addWidget(self.pm_ch, 5, 1)\n\n        batch_layout.addWidget(pm_group)\n\n        merge_group = QtWidgets.QGroupBox("Final border merge")\n        merge_layout = QtWidgets.QGridLayout(merge_group)\n        merge_layout.setContentsMargins(10, 10, 10, 10)\n        merge_layout.setHorizontalSpacing(10)\n        merge_layout.setVerticalSpacing(8)\n\n        self.final_merge_thresh = QtWidgets.QDoubleSpinBox()\n        self.final_merge_thresh.setDecimals(6)\n        self.final_merge_thresh.setRange(0.0, 100000.0)\n        self.final_merge_thresh.setSingleStep(0.001)\n        self.final_merge_thresh.setValue(0.001)\n\n        merge_layout.addWidget(QtWidgets.QLabel("polyMergeVertex threshold:"), 0, 0)\n        merge_layout.addWidget(self.final_merge_thresh, 0, 1)\n\n        batch_layout.addWidget(merge_group)\n\n        self.apply_actions_btn = QtWidgets.QPushButton("Apply Actions (Delete / Mirror + Merge Borders)")\n        self.apply_actions_btn.setMinimumHeight(44)\n        batch_layout.addWidget(self.apply_actions_btn)\n\n        # Material list\n        self.list_widget = QtWidgets.QListWidget()\n        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)\n        self.list_widget.setUniformItemSizes(False)\n        self.list_widget.setSpacing(2)\n\n        # Buttons bottom\n        btn_layout = QtWidgets.QVBoxLayout()\n        btn_layout.setSpacing(8)\n\n        self.refresh_btn = QtWidgets.QPushButton("Refresh Materials")\n        self.select_faces_btn = QtWidgets.QPushButton("Select Faces")\n        self.select_faces_edges_btn = QtWidgets.QPushButton("Select Faces and Convert to Edges")\n\n        btn_layout.addWidget(self.refresh_btn)\n        btn_layout.addWidget(self.select_faces_btn)\n        btn_layout.addWidget(self.select_faces_edges_btn)\n\n        main_layout.addWidget(sort_group)\n        main_layout.addWidget(sym_group)\n        main_layout.addWidget(batch_group)\n        main_layout.addWidget(self.list_widget, 1)\n        main_layout.addLayout(btn_layout)\n\n    def create_connections(self):\n        self.refresh_btn.clicked.connect(self.refresh_materials)\n        self.select_faces_btn.clicked.connect(self.on_select_faces_clicked)\n        self.select_faces_edges_btn.clicked.connect(self.on_select_faces_and_convert_edges_clicked)\n\n        self.select_side_btn.clicked.connect(self.on_select_faces_side_clicked)\n        self.find_sym_mismatch_btn.clicked.connect(self.on_find_symmetry_mismatch_clicked)\n\n        self.apply_actions_btn.clicked.connect(self.on_apply_actions_clicked)\n        self.sort_combo.currentIndexChanged.connect(self.refresh_materials)\n\n    # -------------------------\n    # scriptJob\n    # -------------------------\n    def install_script_job(self):\n        if self._script_job and cmds.scriptJob(exists=self._script_job):\n            try:\n                cmds.scriptJob(kill=self._script_job, force=True)\n            except Exception:\n                pass\n        self._script_job = cmds.scriptJob(event=("SelectionChanged", self.refresh_materials), protected=True)\n\n    def closeEvent(self, event):\n        try:\n            if self._script_job and cmds.scriptJob(exists=self._script_job):\n                cmds.scriptJob(kill=self._script_job, force=True)\n        except Exception:\n            pass\n        super(MaterialSelectorUI, self).closeEvent(event)\n\n    # -------------------------\n    # Sorting\n    # -------------------------\n    def sort_items(self, items):\n        mode = self.sort_combo.currentText()\n        if mode == "Name (A ? Z)":\n            return sorted(items, key=lambda x: x["name"].lower())\n        if mode == "Name (Z ? A)":\n            return sorted(items, key=lambda x: x["name"].lower(), reverse=True)\n        if mode == "Polygons (Low ? High)":\n            return sorted(items, key=lambda x: (x["count"], x["name"].lower()))\n        if mode == "Polygons (High ? Low)":\n            return sorted(items, key=lambda x: (-x["count"], x["name"].lower()))\n        return sorted(items, key=lambda x: x["name"].lower())\n\n    # -------------------------\n    # Swatch\n    # -------------------------\n    def get_material_base_color(self, material):\n        candidates = ["baseColor", "base_color", "base_color_color", "color"]\n        for attr in candidates:\n            if cmds.attributeQuery(attr, node=material, exists=True):\n                try:\n                    val = cmds.getAttr("{}.{}".format(material, attr))\n                    if isinstance(val, (list, tuple)) and len(val) > 0:\n                        rgb = val[0]\n                        if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:\n                            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])\n                            return (max(0.0, min(1.0, r)),\n                                    max(0.0, min(1.0, g)),\n                                    max(0.0, min(1.0, b)))\n                except Exception:\n                    pass\n        return (0.5, 0.5, 0.5)\n\n    def make_swatch_icon(self, rgb, size=14):\n        key = (round(rgb[0], 3), round(rgb[1], 3), round(rgb[2], 3), size)\n        if key in self._swatch_cache:\n            return self._swatch_cache[key]\n\n        pix = QtGui.QPixmap(size, size)\n        pix.fill(QtCore.Qt.transparent)\n\n        painter = QtGui.QPainter(pix)\n        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)\n\n        color = QtGui.QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))\n        painter.setBrush(QtGui.QBrush(color))\n        painter.setPen(QtGui.QPen(QtGui.QColor(40, 40, 40)))\n        painter.drawRect(0, 0, size - 1, size - 1)\n        painter.end()\n\n        icon = QtGui.QIcon(pix)\n        self._swatch_cache[key] = icon\n        return icon\n\n    # -------------------------\n    # Refresh list (kept)\n    # -------------------------\n    def refresh_materials(self, *args):\n        self.list_widget.clear()\n\n        materials = cmds.ls(materials=True) or []\n        selected_objects = cmds.ls(selection=True, type="transform") or []\n\n        if not selected_objects:\n            items = [{"name": m, "count": 0, "display": m, "color": self.get_material_base_color(m)}\n                     for m in materials]\n            items = self.sort_items(items)\n            for it in items:\n                self._add_material_row(it["name"], it["display"], it["color"])\n            return\n\n        material_face_counts = {m: 0 for m in materials}\n\n        for obj in selected_objects:\n            shapes = cmds.listRelatives(obj, shapes=True, type=\'mesh\', fullPath=True) or []\n            if not shapes:\n                continue\n\n            for material in materials:\n                shading_groups = cmds.listConnections(material, type=\'shadingEngine\') or []\n                for sg in shading_groups:\n                    faces = cmds.sets(sg, query=True) or []\n                    for face in faces:\n                        if face.startswith(obj):\n                            material_face_counts[material] += self._count_faces_from_component(face)\n\n        items = []\n        for m, count in material_face_counts.items():\n            rgb = self.get_material_base_color(m)\n            items.append({"name": m, "count": int(count),\n                          "display": "{} ({} polygons)".format(m, int(count)),\n                          "color": rgb})\n        items = self.sort_items(items)\n        for it in items:\n            self._add_material_row(it["name"], it["display"], it["color"])\n\n    def _count_faces_from_component(self, face_component):\n        # face_component can be "obj.f[12]" or "obj.f[3:10]"\n        try:\n            face_part = face_component.split("[")[1].split("]")[0]\n        except Exception:\n            return 0\n        if ":" in face_part:\n            a, b = face_part.split(":")\n            return int(b) - int(a) + 1\n        return 1\n\n    def _add_material_row(self, material_name, display_text, color_rgb):\n        cached = self._action_cache.get(material_name, {"action": "Do Nothing", "pair": ""})\n        icon = self.make_swatch_icon(color_rgb)\n\n        item = QtWidgets.QListWidgetItem()\n        item.setSizeHint(QtCore.QSize(10, 28))\n        item.setData(QtCore.Qt.UserRole, material_name)\n        self.list_widget.addItem(item)\n\n        row = MaterialRowWidget(material_name, swatch_icon=icon)\n        row.name_lbl.setText(display_text)\n        row.set_action(cached.get("action", "Do Nothing"))\n        row.set_pair(cached.get("pair", ""))\n\n        def _on_action_changed(_idx):\n            self._action_cache.setdefault(material_name, {})\n            self._action_cache[material_name]["action"] = row.get_action()\n\n        def _on_pair_changed(_text):\n            self._action_cache.setdefault(material_name, {})\n            self._action_cache[material_name]["pair"] = row.get_pair()\n\n        row.action_combo.currentIndexChanged.connect(_on_action_changed)\n        row.pair_edit.textChanged.connect(_on_pair_changed)\n\n        self.list_widget.setItemWidget(item, row)\n\n        self._action_cache.setdefault(material_name, {})\n        self._action_cache[material_name]["action"] = row.get_action()\n        self._action_cache[material_name]["pair"] = row.get_pair()\n\n    # -------------------------\n    # State helpers\n    # -------------------------\n    def get_selected_material_names(self):\n        mats = []\n        for item in self.list_widget.selectedItems():\n            mat_name = item.data(QtCore.Qt.UserRole)\n            if mat_name:\n                mats.append(mat_name)\n        return mats\n\n    def get_selected_transforms(self):\n        return cmds.ls(selection=True, type="transform") or []\n\n    def get_all_material_rows_state(self):\n        state = dict(self._action_cache)\n        for i in range(self.list_widget.count()):\n            it = self.list_widget.item(i)\n            mat = it.data(QtCore.Qt.UserRole)\n            w = self.list_widget.itemWidget(it)\n            if mat and w:\n                state.setdefault(mat, {})\n                state[mat]["action"] = w.get_action()\n                state[mat]["pair"] = w.get_pair()\n        return state\n\n    # -------------------------\n    # OpenMaya mesh/shader helpers\n    # -------------------------\n    def _get_mesh_dagpath(self, transform):\n        sel = om2.MSelectionList()\n        try:\n            sel.add(transform)\n        except Exception:\n            return None\n\n        dag = sel.getDagPath(0)\n        if not dag.isValid():\n            return None\n\n        fnDag = om2.MFnDagNode(dag)\n        for i in range(fnDag.childCount()):\n            child = fnDag.child(i)\n            if child.hasFn(om2.MFn.kMesh):\n                return om2.MDagPath.getAPathTo(child)\n        return None\n\n    def _get_shader_assignment_cache(self, mesh_fn, material):\n        material_sgs = set(cmds.listConnections(material, type="shadingEngine") or [])\n        sgs, face_shader_ids = mesh_fn.getConnectedShaders(0)\n\n        sg_names = []\n        for sg_obj in sgs:\n            try:\n                sg_names.append(om2.MFnDependencyNode(sg_obj).name())\n            except Exception:\n                sg_names.append("")\n\n        material_sg_indices = {i for i, name in enumerate(sg_names) if name in material_sgs}\n        return face_shader_ids, material_sg_indices\n\n    def _face_has_material(self, face_id, face_shader_ids, material_sg_indices):\n        if face_id < 0 or face_id >= len(face_shader_ids):\n            return False\n        return face_shader_ids[face_id] in material_sg_indices\n\n    def _collect_faces_for_material_on_obj(self, obj, material):\n        mesh_path = self._get_mesh_dagpath(obj)\n        if not mesh_path:\n            return []\n\n        mesh_fn = om2.MFnMesh(mesh_path)\n        face_shader_ids, material_sg_indices = self._get_shader_assignment_cache(mesh_fn, material)\n\n        out = []\n        for fid in range(mesh_fn.numPolygons):\n            if self._face_has_material(fid, face_shader_ids, material_sg_indices):\n                out.append("{}.f[{}]".format(obj, fid))\n        return out\n\n    def _get_sg_for_material(self, material):\n        sgs = cmds.listConnections(material, type="shadingEngine") or []\n        # pick first non-initial if possible\n        for sg in sgs:\n            if sg != "initialShadingGroup":\n                return sg\n        return sgs[0] if sgs else None\n\n    # -------------------------\n    # Select Faces (FIX)\n    # -------------------------\n    def on_select_faces_clicked(self, *args):\n        selected_materials = self.get_selected_material_names()\n        selected_objects = self.get_selected_transforms()\n\n        if not selected_objects:\n            cmds.warning("Please select at least one object.")\n            return\n        if not selected_materials:\n            cmds.warning("Please select at least one material in the list.")\n            return\n\n        all_faces = []\n        for obj in selected_objects:\n            if not self._get_mesh_dagpath(obj):\n                continue\n            for material in selected_materials:\n                all_faces.extend(self._collect_faces_for_material_on_obj(obj, material))\n\n        all_faces = cmds.ls(all_faces, fl=True) or []\n        if not all_faces:\n            cmds.warning("No faces with the selected materials found on the selected objects.")\n            return\n\n        cmds.selectMode(component=True)\n        cmds.selectType(facet=True)\n        cmds.select(all_faces, replace=True)\n\n    def on_select_faces_and_convert_edges_clicked(self, *args):\n        self.on_select_faces_clicked(*args)\n        cmds.ConvertSelectionToEdgePerimeter()\n\n    # -------------------------\n    # Side selection (kept)\n    # -------------------------\n    def _axis_index(self, axis):\n        axis = axis.upper()\n        return {"X": 0, "Y": 1, "Z": 2}.get(axis, 0)\n\n    def _classify_side(self, v, tol):\n        if v > tol:\n            return "+"\n        if v < -tol:\n            return "-"\n        return "0"\n\n    def _compute_face_center_object_space(self, mesh_fn, face_id, points_obj):\n        vtx_ids = mesh_fn.getPolygonVertices(face_id)\n        if not vtx_ids:\n            return om2.MPoint(0.0, 0.0, 0.0)\n        cx = cy = cz = 0.0\n        count = float(len(vtx_ids))\n        for vid in vtx_ids:\n            p = points_obj[vid]\n            cx += p.x\n            cy += p.y\n            cz += p.z\n        return om2.MPoint(cx / count, cy / count, cz / count)\n\n    def on_select_faces_side_clicked(self, *args):\n        selected_materials = self.get_selected_material_names()\n        selected_objects = self.get_selected_transforms()\n\n        if not selected_objects:\n            cmds.warning("Please select at least one object.")\n            return\n        if not selected_materials:\n            cmds.warning("Please select at least one material in the list.")\n            return\n\n        axis = self.axis_combo.currentText()\n        side = self.side_combo.currentText()\n        tol = float(self.side_tol_spin.value())\n        axis_idx = self._axis_index(axis)\n\n        faces_to_select = []\n        for obj in selected_objects:\n            mesh_path = self._get_mesh_dagpath(obj)\n            if not mesh_path:\n                continue\n            mesh_fn = om2.MFnMesh(mesh_path)\n            points_obj = mesh_fn.getPoints(om2.MSpace.kObject)\n\n            for material in selected_materials:\n                face_shader_ids, material_sg_indices = self._get_shader_assignment_cache(mesh_fn, material)\n                for fid in range(mesh_fn.numPolygons):\n                    if not self._face_has_material(fid, face_shader_ids, material_sg_indices):\n                        continue\n                    c = self._compute_face_center_object_space(mesh_fn, fid, points_obj)\n                    v = (c.x, c.y, c.z)[axis_idx]\n                    if self._classify_side(v, tol) == side:\n                        faces_to_select.append("{}.f[{}]".format(obj, fid))\n\n        faces_to_select = cmds.ls(faces_to_select, fl=True) or []\n        if not faces_to_select:\n            cmds.warning("No faces found for the chosen material(s) on that side.")\n            return\n\n        cmds.selectMode(component=True)\n        cmds.selectType(facet=True)\n        cmds.select(faces_to_select, replace=True)\n\n    # -------------------------\n    # Symmetry mismatch (pas inclus ici, garde ta version si tu l\'avais)\n    # -------------------------\n    def on_find_sym_mismatch_clicked_stub(self, *args):\n        cmds.warning("Not implemented in this paste. (Keep your existing mismatch function if you had one.)")\n\n    def on_find_sym_mismatch_clicked(self, *args):\n        # keep button working if you didn\'t paste mismatch implementation\n        self.on_find_sym_mismatch_clicked_stub(*args)\n\n    # -------------------------\n    # polyMirrorFace exact settings\n    # -------------------------\n    def _get_polyMirrorFace_settings(self):\n        axis = int(self.pm_axis.currentText().split()[0])  # "0 (X)" -> 0\n        return {\n            "cutMesh": int(self.pm_cutMesh.currentText()),\n            "axis": axis,\n            "axisDirection": int(self.pm_axisDir.currentText()),\n            "mergeMode": int(self.pm_mergeMode.currentText()),\n            "mergeThresholdType": int(self.pm_mergeThresholdType.currentText()),\n            "mergeThreshold": float(self.pm_mergeThreshold.value()),\n            "mirrorAxis": int(self.pm_mirrorAxis.currentText()),\n            "mirrorPosition": float(self.pm_mirrorPosition.value()),\n            "smoothingAngle": float(self.pm_smoothingAngle.value()),\n            "flipUVs": int(self.pm_flipUVs.currentText()),\n            "ch": int(self.pm_ch.currentText()),\n        }\n\n    def _poly_mirror_faces_exact(self, faces, pm):\n        """\n        Runs polyMirrorFace with exact flags from UI.\n        Returns created faces (best-effort).\n        """\n        if not faces:\n            return []\n\n        obj = faces[0].split(".f[")[0]\n        shapes = cmds.listRelatives(obj, shapes=True, type="mesh", fullPath=True) or []\n        shape = shapes[0] if shapes else None\n\n        before_count = None\n        if shape:\n            try:\n                before_count = cmds.polyEvaluate(shape, face=True)\n            except Exception:\n                before_count = None\n\n        cmds.select(faces, r=True)\n\n        try:\n            cmds.polyMirrorFace(\n                cutMesh=pm["cutMesh"],\n                axis=pm["axis"],\n                axisDirection=pm["axisDirection"],\n                mergeMode=pm["mergeMode"],\n                mergeThresholdType=pm["mergeThresholdType"],\n                mergeThreshold=pm["mergeThreshold"],\n                mirrorAxis=pm["mirrorAxis"],\n                mirrorPosition=pm["mirrorPosition"],\n                smoothingAngle=pm["smoothingAngle"],\n                flipUVs=pm["flipUVs"],\n                ch=pm["ch"],\n            )\n        except Exception as e:\n            _warn("polyMirrorFace failed: {}".format(e))\n            return []\n\n        created = []\n        if shape and before_count is not None:\n            try:\n                after_count = cmds.polyEvaluate(shape, face=True)\n                if after_count and after_count > before_count:\n                    created = ["{}.f[{}]".format(obj, i) for i in range(before_count, after_count)]\n            except Exception:\n                created = []\n\n        # Fallback: grab current selection (sometimes it leaves created faces selected)\n        if not created:\n            sel = cmds.ls(sl=True, fl=True) or []\n            created = [s for s in sel if s.startswith(obj + ".f[")]\n\n        return created\n\n    def _merge_open_border_verts(self, obj, threshold=0.001):\n        border_edges = cmds.polyListComponentConversion(obj, toEdge=True, border=True) or []\n        border_edges = cmds.ls(border_edges, fl=True) or []\n        if not border_edges:\n            return\n\n        verts = cmds.polyListComponentConversion(border_edges, toVertex=True) or []\n        verts = cmds.ls(verts, fl=True) or []\n        if not verts:\n            return\n\n        try:\n            cmds.polyMergeVertex(verts, d=threshold, am=True, ch=False)\n        except Exception as e:\n            _warn("polyMergeVertex failed on {}: {}".format(obj, e))\n\n    # -------------------------\n    # APPLY ACTIONS (REAL IMPLEMENTATION)\n    # -------------------------\n    def on_apply_actions_clicked(self, *args):\n        selected_objects = self.get_selected_transforms()\n        if not selected_objects:\n            cmds.warning("Please select at least one object.")\n            return\n\n        state = self.get_all_material_rows_state()\n\n        delete_mats = set()\n        mirror_by_pair = {}\n        delete_by_pair = {}\n\n        for mat, info in state.items():\n            action = (info.get("action") or "Do Nothing").strip()\n            pair = (info.get("pair") or "").strip().upper()\n\n            if action == "To Delete":\n                delete_mats.add(mat)\n                if pair:\n                    delete_by_pair.setdefault(pair, []).append(mat)\n\n            elif action == "To Mirror":\n                if pair:\n                    mirror_by_pair.setdefault(pair, []).append(mat)\n\n        if not delete_mats and not mirror_by_pair:\n            cmds.warning("Nothing to do: no materials set to To Delete or To Mirror.")\n            return\n\n        pm = self._get_polyMirrorFace_settings()\n        final_merge = float(self.final_merge_thresh.value())\n\n        # Process each selected object independently\n        for obj in selected_objects:\n            if not self._get_mesh_dagpath(obj):\n                continue\n\n            # 1) Delete faces assigned to materials marked "To Delete"\n            faces_to_delete = []\n            for mat in delete_mats:\n                faces_to_delete.extend(self._collect_faces_for_material_on_obj(obj, mat))\n\n            faces_to_delete = cmds.ls(faces_to_delete, fl=True) or []\n            if faces_to_delete:\n                try:\n                    cmds.delete(faces_to_delete)\n                except Exception as e:\n                    _warn("Delete failed on {}: {}".format(obj, e))\n\n            # 2) For each pair: mirror sources -> assign to first delete material in same pair\n            all_pairs = sorted(set(list(mirror_by_pair.keys()) + list(delete_by_pair.keys())))\n            for pair in all_pairs:\n                mirrors = mirror_by_pair.get(pair, [])\n                deletes = delete_by_pair.get(pair, [])\n\n                if not mirrors:\n                    continue\n                if not deletes:\n                    _warn("Pair \'{}\' has To Mirror but no To Delete receiver material.".format(pair))\n                    continue\n\n                src_mat = mirrors[0]\n                dst_mat = deletes[0]\n\n                dst_sg = self._get_sg_for_material(dst_mat)\n                if not dst_sg:\n                    _warn("Cannot find shadingEngine for \'{}\'. Pair \'{}\' skipped.".format(dst_mat, pair))\n                    continue\n\n                src_faces = self._collect_faces_for_material_on_obj(obj, src_mat)\n                src_faces = cmds.ls(src_faces, fl=True) or []\n                if not src_faces:\n                    continue\n\n                created_faces = self._poly_mirror_faces_exact(src_faces, pm)\n                created_faces = cmds.ls(created_faces, fl=True) or []\n                created_faces = [f for f in created_faces if f.startswith(obj + ".f[")]\n\n                if not created_faces:\n                    _warn("Pair \'{}\': mirror produced no detectable faces on {}.".format(pair, obj))\n                    continue\n\n                try:\n                    cmds.sets(created_faces, e=True, forceElement=dst_sg)\n                except Exception as e:\n                    _warn("Assign failed (pair {} / {}): {}".format(pair, obj, e))\n\n            # 3) Merge open border verts\n            self._merge_open_border_verts(obj, threshold=final_merge)\n\n        cmds.inViewMessage(\n            amg="<hl>Batch Actions</hl> done (Delete / Mirror + Merge Borders).",\n            pos=\'midCenterTop\',\n            fade=True\n        )\n        \n        \n    # -------------------------\n    # Symmetry mismatch detection (stub / safe)\n    # -------------------------\n    def on_find_symmetry_mismatch_clicked(self, *args):\n        """\n        Safe placeholder so the UI doesn\'t crash if you haven\'t pasted\n        the full symmetry mismatch implementation.\n        """\n        _warn("Symmetry mismatch tool is not implemented in this version of the script.")\n\n\n# Run / show\ndef show_material_selector_ui():\n    for w in QtWidgets.QApplication.allWidgets():\n        if isinstance(w, QtWidgets.QDialog) and w.windowTitle() == "Material Selector":\n            try:\n                w.close()\n            except Exception:\n                pass\n\n    dlg = MaterialSelectorUI()\n    dlg.show()\n    return dlg\n\n\nshow_material_selector_ui()\n'}, {'category': 'Deliver', 'label': 'Sym Face', 'tooltip': 'Search for not symmetrical faces', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.api.OpenMaya as om\n\ndef get_selected_faces():\n    """Returns a list of selected faces."""\n    return cmds.filterExpand(selectionMask=34)  # 34 is the selection mask for polygon faces\n\ndef get_vertex_positions(face, mesh):\n    """Returns the local space positions of the vertices of a given face."""\n    vertices = cmds.polyInfo(face, faceToVertex=True)[0].split()[2:]\n    positions = [cmds.pointPosition(f"{mesh}.vtx[{v}]", local=True) for v in vertices]\n    return positions\n\ndef calculate_face_center(vertices):\n    """Calculates the center of a face given its vertices\' positions."""\n    avg_position = [sum(axis) / len(axis) for axis in zip(*vertices)]\n    return avg_position\n\ndef find_mirrored_faces(mesh, tolerance=0.001):\n    """Finds all faces with their mirrored counterparts."""\n    mirrored_faces = set()\n    face_centers = {}\n    \n    for face in cmds.ls(f"{mesh}.f[*]", flatten=True):\n        vertices = get_vertex_positions(face, mesh)\n        center = calculate_face_center(vertices)\n        mirrored_center = (-center[0], center[1], center[2])  # Mirroring across the X-axis\n\n        # Round centers to avoid floating-point issues and use as dictionary keys\n        rounded_center = tuple(round(c, 4) for c in center)\n        rounded_mirrored_center = tuple(round(c, 4) for c in mirrored_center)\n\n        # Store the face\'s center\n        face_centers[rounded_center] = face\n\n        # Check if the mirrored position exists in the recorded centers\n        if rounded_mirrored_center in face_centers:\n            mirrored_faces.add(face)\n            mirrored_faces.add(face_centers[rounded_mirrored_center])\n\n    return mirrored_faces\n\ndef select_faces_without_mirrors():\n    selected_faces = get_selected_faces()\n    if not selected_faces:\n        cmds.warning("Please select some faces.")\n        return\n\n    mesh = selected_faces[0].split(\'.\')[0]\n    mirrored_faces = find_mirrored_faces(mesh)\n    faces_without_mirrors = [face for face in selected_faces if face not in mirrored_faces]\n\n    if faces_without_mirrors:\n        cmds.select(faces_without_mirrors)\n        print(f"Faces without mirrored counterparts: {faces_without_mirrors}")\n    else:\n        cmds.warning("All selected faces have mirrored counterparts.")\n\n# Run the function to select faces without mirrored counterparts\nselect_faces_without_mirrors()\n'}, {'category': 'Deliver', 'label': 'Open Borders', 'tooltip': 'Find the open borders', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef get_open_border_vertices():\n    """Select vertices around every open border of all selected meshes."""\n    selected_objects = cmds.ls(selection=True, type="transform")\n\n    if not selected_objects:\n        cmds.warning("Please select at least one mesh object.")\n        return\n\n    all_border_vertices = []\n\n    for selected_object in selected_objects:\n        shapes = cmds.listRelatives(selected_object, shapes=True, type=\'mesh\', fullPath=True)\n        if not shapes:\n            cmds.warning(f"Selected object \'{selected_object}\' has no mesh shapes.")\n            continue\n\n        mesh = shapes[0]\n\n        # Get all edges of the mesh\n        all_edges = cmds.ls(cmds.polyListComponentConversion(mesh, toEdge=True), fl=True)\n\n        # Find all border edges (edges connected to only one face)\n        border_edges = []\n        for edge in all_edges:\n            connected_faces_info = cmds.polyInfo(edge, edgeToFace=True)\n            if connected_faces_info:\n                connected_faces = connected_faces_info[0].split()[2:]  # Remove "FACE" and other labels\n                if len(connected_faces) == 1:  # Border edge has only one connected face\n                    border_edges.append(edge)\n\n        if not border_edges:\n            cmds.warning(f"No open borders found for \'{selected_object}\'.")\n            continue\n\n        # Convert border edges to vertices\n        border_vertices = cmds.ls(cmds.polyListComponentConversion(border_edges, fromEdge=True, toVertex=True), fl=True)\n\n        all_border_vertices.extend(border_vertices)\n\n    if not all_border_vertices:\n        cmds.warning("No open border vertices found for any selected objects.")\n        return\n\n    # Select the vertices around the open borders\n    cmds.select(all_border_vertices, replace=True)\n    print(f"Selected open border vertices: {all_border_vertices}")\n\n# Run the function to select open border vertices\nget_open_border_vertices()\n'}, {'category': 'Deliver', 'label': 'AutoUV', 'tooltip': 'Unfold 3D - Preserve Edges - Layout 45', 'source': 'mel', 'command': 'polyMapCut;\ngetFaces;\nif(!`exists MTselAll`) source MTprocs.mel; select -cl; MTselAll;\nu3dUnfold -ite 1 -p 0 -bi 1 -tf 1 -ms 1024 -rs 0;\nu3dOptimize -ite 500 -pow 1 -sa 1 -bi 0 -tf 1 -ms 1024 -rs 0;\nevalEcho("texOrientShells");\nu3dLayout -res 256 -rot 2 -scl 1 -spc 0.00244140625 -mar 0.00244140625 -box 0 1 0 1 pSphere1.e[0:459];\n{\n//Lists the transform nodes of all selected objects\nstring $nodes[] = `ls -selection`;\n\nfor ($node in $nodes)\n{\n//Loop through each object and obtain its shape node\nstring $shapes[] = `listRelatives -shapes $node`;\n\n//Set the visibility attribute of each shape node to 0\n//The shape node is saved to the 1st (or 0th) element of the $shape array\nsetAttr ($shapes[0] + ".osdFvarBoundary") (1);\n}\n}'}, {'category': 'Deliver', 'label': 'smooth1', 'tooltip': '{\n//Lists the transform nodes of all selected objects\nstring $no...', 'source': 'mel', 'command': '{\n//Lists the transform nodes of all selected objects\nstring $nodes[] = `ls -selection`;\n\nfor ($node in $nodes)\n{\n//Loop through each object and obtain its shape node\nstring $shapes[] = `listRelatives -shapes $node`;\n\n//Set the visibility attribute of each shape node to 0\n//The shape node is saved to the 1st (or 0th) element of the $shape array\nsetAttr ($shapes[0] + ".smoothLevel") (1);\n}\n}'}, {'category': 'Deliver', 'label': 'Cam_Based', 'tooltip': 'Create UV texture coordinates for the selected object, using the current camera view as the plane of projection', 'source': 'mel', 'command': 'UVCameraBasedProjection;'}, {'category': 'Deliver', 'label': 'Renamer', 'tooltip': 'A renamer tool', 'source': 'python', 'command': '#\n# Copyright (C) by Adrian Sochacki, since 2019. All rights reserved.\n#\n# Description: Gives you the function to easily rename everything\n#\n# How to use: Run the script, change the textfields depending on the rename method and hit the corresponding button.\n#\n# Version: 1.2.1\n#\n\nimport maya.cmds as cmds\nimport sys\nfrom functools import partial\n\n\ndef onMayaDroppedPythonFile(*args):\n\tRenameWindow()\n\n\ndef RenameWindow(*args):\n\twinID = \'schocki_renameWindowUI\'\n\tif cmds.window(winID, exists = True):\n\t\tcmds.deleteUI(winID)\n\n\tif cmds.windowPref(winID, exists = True):\n\t\ttopLeftCorner = cmds.windowPref(winID, query = True, topLeftCorner = True)\n\t\tcmds.windowPref(winID, remove = True)\n\telse:\n\t\ttopLeftCorner = (197, 442)\n\n\titemWidth = 278\n\n\tcmds.window(winID, title = \'Renamer\',width = 294, sizeable = False, topLeftCorner = topLeftCorner, minimizeCommand = SaveOptionVariables, closeCommand = SaveOptionVariables)\n\tcmds.columnLayout(\'masterRowLayout\')\n\tcmds.separator(style = \'none\', height = 5)\n\n\t#Add string at position\n\taddStringAtPositionAnnotation = \'Add a string at a specific position:\\nChange "Cube1" to "masterCube1"\\nChange "Cube1" to "Cube1_master"\\nChange "Cube1" to "Cu_master_be1"\'\n\n\tcmds.rowColumnLayout(\'addStringAtPositionRowColumnLayout\', numberOfColumns = 3, annotation = addStringAtPositionAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Add string at position :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout1\', annotation = addStringAtPositionAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = addStringAtPositionAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'String to add :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.textField(\'stringToAddTextField\', width = 199)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout2\', annotation = addStringAtPositionAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = addStringAtPositionAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'At position :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.intField(\'stringToAddAtPositionIntField\', width = 210, minValue = 0)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout3\', annotation = addStringAtPositionAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#Button\n\tcmds.rowColumnLayout(numberOfColumns = 2, annotation = addStringAtPositionAnnotation)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.button(\'addStringAtPositionButton\', label = \'Add string at position\', width = itemWidth+1, command = partial(PreRename, \'addStringAtPosition\'))\n\tcmds.setParent(\'..\')\n\n\t#Separator\n\tcmds.rowColumnLayout(\'separatorRowColumnLayout1\', numberOfColumns = 3)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.separator(height = 10, width = itemWidth)\n\tcmds.separator(style = \'none\', width = 3)\n\tcmds.setParent(\'..\')\n\n\t#Replace string\n\treplaceStringAnnotation = \'Replace a string with another one:\\nChange "pCube1" to "pSphere1"\\nChange "testCurve" to "masterCurve"\'\n\n\tcmds.rowColumnLayout(\'replaceStringRowColumnLayout\', numberOfColumns = 3, annotation = replaceStringAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Replace string with string :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout5\', annotation = replaceStringAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#TextField\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = replaceStringAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'Replace string :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.textField(\'toReplaceTextField\', width = 194)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout6\', annotation = replaceStringAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#TextField\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = replaceStringAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'With string :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.textField(\'replaceWithTextField\', width = 209)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout7\', annotation = replaceStringAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#Button\n\tcmds.rowColumnLayout(numberOfColumns = 2, annotation = replaceStringAnnotation)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.button(\'replaceStringButton\', label = \'Replace string with string\', width = itemWidth+1, command = partial(PreRename, \'replaceWith\'))\n\tcmds.setParent(\'..\')\n\n\t#Separator\n\tcmds.rowColumnLayout(\'separatorRowColumnLayout3\', numberOfColumns = 3)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.separator(height = 10, width = itemWidth)\n\tcmds.separator(style = \'none\', width = 3)\n\tcmds.setParent(\'..\')\n\n\t#Add padding\n\taddPaddingAnnotation = \'Adds a padding that goes up for every object you have selected:\\nChanges your first selected object from "pCube" to "pCube0100"\\nChanges your second selected object from "pSphere" to "pSphere0101"\\nChanges your third selected object from "pCone" to "pCone0102"\'\n\n\tcmds.rowColumnLayout(\'addPaddingRowColumnLayout\', numberOfColumns = 3, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Add padding :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout10\', annotation = addPaddingAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#IntField\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'How much padding :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.intField(\'paddingCountIntField\', width = 165, minValue = 0)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout11\', annotation = addPaddingAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#IntField\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'Start at(integer) :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.intField(\'startAtIntField\', width = 187, minValue = 0)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout12\', annotation = addPaddingAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#IntField\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'Add at following position :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.intField(\'addAtFollowingIntField\', width = 134, minValue = 0)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout13\', annotation = addPaddingAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#Button\n\tcmds.rowColumnLayout(numberOfColumns = 2, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.button(\'addPaddingButton\', label = \'Add padding\', width = itemWidth+1, command = partial(PreRename, \'addPadding\'))\n\tcmds.setParent(\'..\')\n\n\t#Separator\n\tcmds.rowColumnLayout(\'separatorRowColumnLayout4\', numberOfColumns = 3)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.separator(height = 10, width = itemWidth)\n\tcmds.separator(style = \'none\', width = 3)\n\tcmds.setParent(\'..\')\n\n\t#Rename and add padding\n\trenameAndAddPaddingAnnotation = \'Renames and adds a padding that goes up for every object you have selected\\nChanges first selected object, "pCube1" to "pCube_001"\\nChanges second selected object, "pSphere" to "pCube_002"\\nChanges first selected object, "pTorus" to "pCube_003"\\nFormula: renameTo + specialCharacter + paddingAmount\'\n\n\tcmds.rowColumnLayout(\'renameAndAddPaddingRowColumnLayout\', numberOfColumns = 3, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Rename and add padding :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'How much padding :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.intField(\'renameAndAddPaddingCountIntField\', width = 165, minValue = 0)\n\tcmds.setParent(\'..\')\n\n\t#IntField\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'Start at(integer) :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.intField(\'renameAndAddPaddingStartAtIntField\', width = 187, minValue = 0)\n\tcmds.setParent(\'..\')\n\n\t#Text Field\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'Special character separator :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.textField(\'renameAndAddPaddingSpecialCharacterSeparatorTextField\', width = 129)\n\tcmds.setParent(\'..\')\n\n\t#Text Field\n\tcmds.rowColumnLayout(numberOfColumns = 4, annotation = renameAndAddPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(label = \'Rename to :\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.textField(\'renameAndAddPaddingRenameToTextField\', width = 212)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout19\', annotation = addPaddingAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\t#Button\n\tcmds.rowColumnLayout(numberOfColumns = 2, annotation = addPaddingAnnotation)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.button(\'renameAndAddPaddingButton\', label = \'Rename and add padding\', width = itemWidth+1, command = partial(PreRename, \'renameAndAddPadding\'))\n\tcmds.setParent(\'..\')\n\n\t#Separator\n\tcmds.rowColumnLayout(\'separatorRowColumnLayout10\', numberOfColumns = 3)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.separator(height = 10, width = itemWidth)\n\tcmds.separator(style = \'none\', width = 3)\n\tcmds.setParent(\'..\')\n\n\t#Quick prefix/suffix\n\tquickPrefixSuffixAnnotation = \'Quickly adds text as a prefix or suffix to your selection:\\nChanges "pCube" to "pCubeGEO\\nChanges "NurbsCurve" to "crvNurbsCurve"\'\n\n\tcmds.rowColumnLayout(\'quickPrefixSuffixRowColumnLayout\', numberOfColumns = 3, annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Add prefix/suffix :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout14\', annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowLayout(numberOfColumns = 4, annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(style = \'none\', width = 6)\n\tcmds.radioCollection()\n\tcmds.radioButton(\'prefixRadioButton\', label = \'Prefix\')\n\tcmds.separator(style = \'none\', width = 41)\n\tcmds.radioButton(\'suffixRadioButton\', label = \'Suffix\')\n\tcmds.setParent(\'..\')\n\tcmds.rowLayout(numberOfColumns = 4)\n\tcmds.separator(style = \'none\', width = 6)\n\tcmds.radioCollection()\n\tcmds.radioButton(\'lowercaseRadioButton\', label = \'Lowercase\', onCommand = partial(ChangeButtonLabel, \'lowercase\'))\n\tcmds.separator(style = \'none\', width = 15)\n\tcmds.radioButton(\'uppercaseRadioButton\', label = \'Uppercase\', onCommand = partial(ChangeButtonLabel, \'uppercase\'))\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout15\', annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(height = 3)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowLayout(\'buttonRowLayout1\', numberOfColumns = 7, annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(style = \'none\', width = 6)\n\tcmds.button(\'geoButton\', label = \'geo\', command = partial(PreRename, \'quickPrefixSuffix\', \'geo\'), width = 44)\n\tcmds.button(\'grpButton\', label = \'grp\', command = partial(PreRename, \'quickPrefixSuffix\', \'grp\'), width = 44)\n\tcmds.button(\'animButton\', label = \'anim\', command = partial(PreRename, \'quickPrefixSuffix\', \'anim\'), width = 44)\n\tcmds.button(\'locButton\', label = \'loc\', command = partial(PreRename, \'quickPrefixSuffix\', \'loc\'), width = 44)\n\tcmds.button(\'camButton\', label = \'cam\', command = partial(PreRename, \'quickPrefixSuffix\', \'cam\'), width = 44)\n\tcmds.button(\'jntButton\', label = \'jnt\', command = partial(PreRename, \'quickPrefixSuffix\', \'jnt\'), width = 44)\n\tcmds.setParent(\'..\')\n\tcmds.rowLayout(\'buttonRowLayout2\', numberOfColumns = 7, annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(style = \'none\', width = 6)\n\tcmds.button(\'proxyButton\', label = \'proxy\', command = partial(PreRename, \'quickPrefixSuffix\', \'proxy\'), width = 44)\n\tcmds.button(\'lgtButton\', label = \'lgt\', command = partial(PreRename, \'quickPrefixSuffix\', \'lgt\'), width = 44)\n\tcmds.button(\'crvButton\', label = \'crv\', command = partial(PreRename, \'quickPrefixSuffix\', \'crv\'), width = 44)\n\tcmds.button(\'ikButton\', label = \'ik\', command = partial(PreRename, \'quickPrefixSuffix\', \'ik\'), width = 44)\n\tcmds.button(\'fkButton\', label = \'fk\', command = partial(PreRename, \'quickPrefixSuffix\', \'fk\'), width = 44)\n\tcmds.button(\'setButton\', label = \'set\', command = partial(PreRename, \'quickPrefixSuffix\', \'set\'), width = 44)\n\tcmds.setParent(\'..\')\n\tcmds.rowLayout(\'buttonRowLayout3\', numberOfColumns = 7, annotation = quickPrefixSuffixAnnotation)\n\tcmds.separator(style = \'none\', width = 6)\n\tcmds.button(\'nrbButton\', label = \'nrb\', command = partial(PreRename, \'quickPrefixSuffix\', \'nrb\'), width = 44)\n\tcmds.button(\'dummyButton\', label = \'dummy\', command = partial(PreRename, \'quickPrefixSuffix\', \'dummy\'), width = 44)\n\tcmds.button(\'clustButton\', label = \'clust\', command = partial(PreRename, \'quickPrefixSuffix\', \'clust\'), width = 44)\n\tcmds.button(\'infButton\', label = \'inf\', command = partial(PreRename, \'quickPrefixSuffix\', \'inf\'), width = 44)\n\tcmds.button(\'constButton\', label = \'const\', command = partial(PreRename, \'quickPrefixSuffix\', \'const\'), width = 44)\n\tcmds.button(\'fxButton\', label = \'fx\', command = partial(PreRename, \'quickPrefixSuffix\', \'fx\'), width = 44)\n\tcmds.setParent(\'..\')\n\n\t#Separator\n\tcmds.rowColumnLayout(\'separatorRowColumnLayout5\', numberOfColumns = 3)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.separator(height = 10, width = itemWidth)\n\tcmds.separator(style = \'none\', width = 3)\n\tcmds.setParent(\'..\')\n\n\t#Remove character\n\tremoveCharacterAnnotation = \'Removes first or last character:\\nChanges "pCube1" to "Cube1"\\nChanges "pSphere1" to "pSphere"\'\n\n\tcmds.rowColumnLayout(\'removeRowColumnLayout\', numberOfColumns = 3, annotation = removeCharacterAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Remove character :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout16\', annotation = removeCharacterAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowLayout(numberOfColumns = 3, annotation = removeCharacterAnnotation)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.button(\'removeFirstButton\', label = \'Remove first character\', width = 137, command = partial(PreRename, \'removeCharacter\', \'first\'))\n\tcmds.button(\'removeLastButton\', label = \'Remove last character\', width = 137, command = partial(PreRename, \'removeCharacter\', \'last\'))\n\tcmds.setParent(\'..\')\n\n\t#Separator\n\tcmds.rowColumnLayout(\'separatorRowColumnLayout7\', numberOfColumns = 3)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.separator(height = 10, width = itemWidth)\n\tcmds.separator(style = \'none\', width = 3)\n\tcmds.setParent(\'..\')\n\n\t#Rename shape\n\trenameShapeAnnotation = "Renames the shape corresponding to it\'s transform name. Fixes some errors that depend on correct shape names"\n\n\tcmds.rowColumnLayout(\'renameShapeRowColumnLayout\', numberOfColumns = 3, annotation = renameShapeAnnotation)\n\tcmds.separator(style = \'none\', width = 7)\n\tcmds.text(\'Rename shape :\', font = \'boldLabelFont\')\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout17\', annotation = renameShapeAnnotation)\n\tcmds.separator(height = 1)\n\tcmds.setParent(\'..\')\n\n\tcmds.rowLayout(numberOfColumns = 2, annotation = renameShapeAnnotation)\n\tcmds.separator(style = \'none\', width = 5)\n\tcmds.button(\'renameShapeButton\', label = \'Rename shapes\', width = itemWidth-2, command = partial(PreRename, \'renameShape\'))\n\tcmds.setParent(\'..\')\n\n\t#Space\n\tcmds.rowLayout(\'spaceRowLayout18\', annotation = renameShapeAnnotation)\n\tcmds.separator(height = 4)\n\tcmds.setParent(\'..\')\n\n\tcmds.setParent(\'..\')\n\n\tif not cmds.radioButton(\'prefixRadioButton\', query = True, select = True) and not cmds.radioButton(\'suffixRadioButton\', query = True, select = True):\n\t\tcmds.radioButton(\'prefixRadioButton\', edit = True, select = True)\n\t\tcmds.radioButton(\'suffixRadioButton\', edit = True, select = False)\n\n\tif not cmds.radioButton(\'lowercaseRadioButton\', query = True, select = True) and not cmds.radioButton(\'uppercaseRadioButton\', query = True, select = True):\n\t\tcmds.radioButton(\'lowercaseRadioButton\', edit = True, select = True)\n\t\tcmds.radioButton(\'uppercaseRadioButton\', edit = True, select = False)\n\n\tCheckOptionVariables()\n\n\tcmds.showWindow()\n\n\ndef PreRename(command, extra, *args):\n\tsel = cmds.ls(sl = True)\n\tif len(sel) == 0:\n\t\tsys.exit(\'You have nothing selected. Please select at least one object.\\n\')\n\telse:\n\t\tcmds.undoInfo(chunkName = \'batchRenamer_rename\', openChunk = True)\n\t\tif command == \'addStringAtPosition\':\n\t\t\tAddStringAtPosition(sel)\n\n\t\telif command == \'replaceWith\':\n\t\t\tReplaceWith(sel)\n\n\t\telif command == \'addPadding\':\n\t\t\tAddPadding(sel)\n\n\t\telif command == \'quickPrefixSuffix\':\n\t\t\tQuickPrefixSuffix(sel, extra)\n\n\t\telif command == \'removeCharacter\':\n\t\t\tif extra == \'first\':\n\t\t\t\tRemoveCharacter(sel, extra)\n\t\t\telif extra == \'last\':\n\t\t\t\tRemoveCharacter(sel, extra)\n\n\t\telif command == \'renameShape\':\n\t\t\tRenameShape(sel)\n\n\t\telif command == \'renameAndAddPadding\':\n\t\t\tRenameAndAddPadding(sel)\n\t\telse:\n\t\t\tsys.exit(\'Unexpected Error, Please contact me.\')\n\t\t\tcmds.undoInfo(chunkName = \'batchRenamer_rename\', closeChunk = True)\n\t\tcmds.undoInfo(chunkName = \'batchRenamer_rename\', closeChunk = True)\n\n\tSaveOptionVariables()\n\n\ndef AddStringAtPosition(sel, *args):\n\tstringToAdd = cmds.textField(\'stringToAddTextField\', query = True, text = True)\n\n\tif stringToAdd == \'\':\n\t\tsys.exit(\'The "String to add" text field is empty, please type something in.\\n\')\n\taddAtPos = cmds.intField(\'stringToAddAtPositionIntField\', query = True, value = True)\n\n\tif addAtPos == 0 or addAtPos == 1:\n\t\taddAtPos = 0\n\telse:\n\t\taddAtPos -= 1\n\n\tfor x in sel:\n\t\tcmds.rename(x, x[:addAtPos] + stringToAdd + x[addAtPos:])\n\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + x[:addAtPos] + stringToAdd + x[addAtPos:] + \'".\\n\')\n\n\ndef ReplaceWith(sel, *args):\n\ttoReplace = cmds.textField(\'toReplaceTextField\', query = True, text = True)\n\treplaceWith = cmds.textField(\'replaceWithTextField\', query = True, text = True)\n\tif toReplace == \'\' and replaceWith == \'\':\n\t\tsys.exit(\'The "Replace string" text field is empty, please type something in.\\n\')\n\telif toReplace == \'\':\n\t\tsys.exit(\'The "Replace string" and "With string" textfields are empty, please type something in.\\n\')\n\n\tfor x in sel:\n\t\tcmds.rename(x, x.replace(str(toReplace), str(replaceWith)))\n\t\tsys.stdout.write(\'Replaced "\' + toReplace + \'" with "\' + replaceWith + \'".\\n\')\n\n\ndef AddPadding(sel, *args):\n\tpaddingNumber = cmds.intField(\'paddingCountIntField\', query = True, value = True)\n\tstartAt = cmds.intField(\'startAtIntField\', query = True, value = True)\n\taddAtPos = cmds.intField(\'addAtFollowingIntField\', query = True, value = True)\n\n\tif paddingNumber == \'\':\n\t\tsys.exit(\'The "How much padding" text field is empty, please type something in.\\n\')\n\telif startAt == \'\':\n\t\tsys.exit(\'The "Start at" text field is empty, please type something in.\\n\')\n\telif addAtPos == \'\':\n\t\tsys.exit(\'The "Add at following position" text field is empty, please type something in.\\n\')\n\n\tif addAtPos == 0 or addAtPos == 1:\n\t\taddAtPos = 0\n\telse:\n\t\taddAtPos -= 1\n\n\tfor x in range(len(sel)):\n\t\tif addAtPos > len(sel[x]):\n\t\t\tcmds.rename(sel[x], sel[x] + str(startAt).zfill(paddingNumber))\n\t\telif addAtPos > 0:\n\t\t\tcmds.rename(sel[x], sel[x][:addAtPos] + str(startAt).zfill(paddingNumber) + sel[x][addAtPos:])\n\t\telif addAtPos == 0:\n\t\t\tcmds.rename(sel[x], str(startAt).zfill(paddingNumber) + sel[x])\n\t\telse:\n\t\t\tcmds.rename(sel[x], sel[x] + str(x + 1).zfill(paddingNumber - len(str(x))))\n\t\tsys.stdout.write(\'Added padding to \' + sel[x] + \'.\\n\')\n\t\tstartAt += 1\n\n\ndef RenameAndAddPadding(sel, *args):\n\tpaddingNumber = cmds.intField(\'renameAndAddPaddingCountIntField\', query = True, value = True)\n\tstartAt = cmds.intField(\'renameAndAddPaddingStartAtIntField\', query = True, value = True)\n\tspecialCharacter = cmds.textField(\'renameAndAddPaddingSpecialCharacterSeparatorTextField\', query = True, text = True)\n\trenameTo = cmds.textField(\'renameAndAddPaddingRenameToTextField\', query = True, text = True)\n\n\tif paddingNumber == \'\':\n\t\tsys.exit(\'The "How much padding" text field is empty, please type something in.\\n\')\n\tif startAt == \'\':\n\t\tsys.exit(\'The "Start at" text field is empty, please type something in.\\n\')\n\tif renameTo == \'\':\n\t\tsys.exit(\'The "Rename to" text field is empty, please type something in.asd\\n\')\n\n\tfor x in range(len(sel)):\n\t\tnewName = renameTo + specialCharacter + str(startAt + x).zfill(paddingNumber)\n\t\tcmds.rename(sel[x], newName)\n\t\tsys.stdout.write(\'Renamed \' + sel[x] + \' to \' + newName + \'.\\n\')\n\n\ndef QuickPrefixSuffix(sel, toAddFix, *args):\n\tlowercase = cmds.radioButton(\'lowercaseRadioButton\', query = True, select = True)\n\tuppercase = cmds.radioButton(\'uppercaseRadioButton\', query = True, select = True)\n\n\tprefix = cmds.radioButton(\'prefixRadioButton\', query = True, select = True)\n\tsuffix = cmds.radioButton(\'suffixRadioButton\', query = True, select = True)\n\tfor x in sel:\n\t\tif prefix and not suffix:\n\t\t\tif lowercase and not uppercase:\n\t\t\t\tcmds.rename(toAddFix.lower() + x)\n\t\t\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + toAddFix.lower() + x + \'".\\n\')\n\t\t\telif not lowercase and uppercase:\n\t\t\t\tcmds.rename(toAddFix.upper() + x)\n\t\t\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + toAddFix.upper() + x + \'".\\n\')\n\n\t\telif not prefix and suffix:\n\t\t\tif lowercase and not uppercase:\n\t\t\t\tcmds.rename(x + toAddFix.lower())\n\t\t\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + x + toAddFix.lower() + \'".\\n\')\n\t\t\telif not lowercase and uppercase:\n\t\t\t\tcmds.rename(x + toAddFix.upper())\n\t\t\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + x + toAddFix.upper() + \'".\\n\')\n\t\telse:\n\t\t\tsys.exit(\'Unexpected Error, please contact me.\\n\')\n\n\ndef ChangeButtonLabel(case, *args):\n\tif case == \'lowercase\':\n\t\tcmds.button(\'geoButton\', edit = True, label = \'geo\')\n\t\tcmds.button(\'grpButton\', edit = True, label = \'grp\')\n\t\tcmds.button(\'animButton\', edit = True, label = \'anim\')\n\t\tcmds.button(\'locButton\', edit = True, label = \'loc\')\n\t\tcmds.button(\'camButton\', edit = True, label = \'cam\')\n\t\tcmds.button(\'jntButton\', edit = True, label = \'jnt\')\n\t\tcmds.button(\'proxyButton\', edit = True, label = \'proxy\')\n\t\tcmds.button(\'lgtButton\', edit = True, label = \'lgt\')\n\t\tcmds.button(\'crvButton\', edit = True, label = \'crv\')\n\t\tcmds.button(\'ikButton\', edit = True, label = \'ik\')\n\t\tcmds.button(\'fkButton\', edit = True, label = \'fk\')\n\t\tcmds.button(\'setButton\', edit = True, label = \'set\')\n\t\tcmds.button(\'nrbButton\', edit = True, label = \'nrb\')\n\t\tcmds.button(\'dummyButton\', edit = True, label = \'dummy\')\n\t\tcmds.button(\'clustButton\', edit = True, label = \'clust\')\n\t\tcmds.button(\'infButton\', edit = True, label = \'inf\')\n\t\tcmds.button(\'constButton\', edit = True, label = \'const\')\n\t\tcmds.button(\'fxButton\', edit = True, label = \'fx\')\n\telif case == \'uppercase\':\n\t\tcmds.button(\'geoButton\', edit = True, label = \'geo\'.upper())\n\t\tcmds.button(\'grpButton\', edit = True, label = \'grp\'.upper())\n\t\tcmds.button(\'animButton\', edit = True, label = \'anim\'.upper())\n\t\tcmds.button(\'locButton\', edit = True, label = \'loc\'.upper())\n\t\tcmds.button(\'camButton\', edit = True, label = \'cam\'.upper())\n\t\tcmds.button(\'jntButton\', edit = True, label = \'jnt\'.upper())\n\t\tcmds.button(\'proxyButton\', edit = True, label = \'proxy\'.upper())\n\t\tcmds.button(\'lgtButton\', edit = True, label = \'lgt\'.upper())\n\t\tcmds.button(\'crvButton\', edit = True, label = \'crv\'.upper())\n\t\tcmds.button(\'ikButton\', edit = True, label = \'ik\'.upper())\n\t\tcmds.button(\'fkButton\', edit = True, label = \'fk\'.upper())\n\t\tcmds.button(\'setButton\', edit = True, label = \'set\'.upper())\n\t\tcmds.button(\'nrbButton\', edit = True, label = \'nrb\'.upper())\n\t\tcmds.button(\'dummyButton\', edit = True, label = \'dummy\'.upper())\n\t\tcmds.button(\'clustButton\', edit = True, label = \'clust\'.upper())\n\t\tcmds.button(\'infButton\', edit = True, label = \'inf\'.upper())\n\t\tcmds.button(\'constButton\', edit = True, label = \'const\'.upper())\n\t\tcmds.button(\'fxButton\', edit = True, label = \'fx\'.upper())\n\telse:\n\t\tsys.exit(\'Unexpected Error, Please contact me.\')\n\n\tSaveOptionVariables()\n\n\ndef RemoveCharacter(sel, position, *args):\n\tfor x in sel:\n\t\tif position == \'first\':\n\t\t\tcmds.rename(x, x[1:])\n\t\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + x[1:] + \'"\' + \'\\n\')\n\t\telif position == \'last\':\n\t\t\tcmds.rename(x, x[0:-1])\n\t\t\tsys.stdout.write(\'Renamed "\' + x + \'" to "\' + x[0:-1] + \'"\' + \'.\\n\')\n\t\telse:\n\t\t\tsys.exit(\'Unexpected Error, Please contact me.\')\n\n\ndef RenameShape(selS, *args):\n\tselL = cmds.ls(sl = True, long = True)\n\n\tfor x in range(len(selL)):\n\t\tshapeL = cmds.listRelatives(selL[x], shapes = True, fullPath = True)\n\t\tshapeS = cmds.listRelatives(selL[x], shapes = True)\n\n\t\tif selL[x] + \'|\' + selS[x] + \'Shape\' == shapeL[0]:\n\t\t\tsys.stdout.write(\'"\' + shapeS[0] + \'"\' + " and it\'s transform have already the same name.\\n")\n\n\t\telif selL[x][0: len(selL[x]) - 1]+ \'|\' + selS[x] + \'Shape\' != shapeL[0]:\n\t\t\tif \'|\' in selS[x]:\n\t\t\t\tcmds.rename(shapeL[0], selS[x].split(\'|\')[-1] + \'Shape\')\n\t\t\telse:\n\t\t\t\tcmds.rename(shapeL[0], selS[x] + \'Shape\')\n\t\t\tsys.stdout.write(\'"\' + selS[x] + \'"\' +  " and it\'s shape were synchronized.\\n")\n\t\telse:\n\t\t\tsys.exit(\'Unexpected Error, Please contact me.\')\n\n\ndef SaveOptionVariables(*args):\n\tcmds.optionVar(stringValue = [\'batchRenamer_stringToAddTextField\', cmds.textField(\'stringToAddTextField\', query = True, text = True)])\n\tcmds.optionVar(intValue = [\'batchRenamer_stringToAddAtPositionIntField\', cmds.intField(\'stringToAddAtPositionIntField\', query = True, value = True)])\n\tcmds.optionVar(stringValue = [\'batchRenamer_toReplaceTextField\', cmds.textField(\'toReplaceTextField\', query = True, text = True)])\n\tcmds.optionVar(stringValue = [\'batchRenamer_replaceWithTextField\', cmds.textField(\'replaceWithTextField\', query = True, text = True)])\n\tcmds.optionVar(intValue = [\'batchRenamer_paddingCountIntField\', cmds.intField(\'paddingCountIntField\', query = True, value = True)])\n\tcmds.optionVar(intValue = [\'batchRenamer_startAtIntField\', cmds.intField(\'startAtIntField\', query = True, value = True)])\n\tcmds.optionVar(intValue = [\'batchRenamer_addAtFollowingIntField\', cmds.intField(\'addAtFollowingIntField\', query = True, value = True)])\n\n\tcmds.optionVar(intValue = [\'batchRenamer_renameAndAddPaddingPaddingNumberIntField\', cmds.intField(\'renameAndAddPaddingCountIntField\', query = True, value = True)])\n\tcmds.optionVar(intValue = [\'batchRenamer_renameAndAddPaddingStartAtIntField\', cmds.intField(\'renameAndAddPaddingStartAtIntField\', query = True, value = True)])\n\tcmds.optionVar(stringValue = [\'batchRenamer_renameAndAddPaddingSpecialCharacterTextField\', cmds.textField(\'renameAndAddPaddingSpecialCharacterSeparatorTextField\', query = True, text = True)])\n\tcmds.optionVar(stringValue = [\'batchRenamer_renameAndAddPaddingRenameToTextField\', cmds.textField(\'renameAndAddPaddingRenameToTextField\', query = True, text = True)])\n\n\tif cmds.radioButton(\'prefixRadioButton\', query = True, select = True):\n\t\tprefixRadioButtonValue = True\n\telse:\n\t\tprefixRadioButtonValue = False\n\n\tif cmds.radioButton(\'suffixRadioButton\', query = True, select = True):\n\t\tsuffixRadioButtonValue = True\n\telse:\n\t\tsuffixRadioButtonValue = False\n\n\tif cmds.radioButton(\'lowercaseRadioButton\', query = True, select = True):\n\t\tlowercaseRadioButtonValue = True\n\telse:\n\t\tlowercaseRadioButtonValue = False\n\n\tif cmds.radioButton(\'uppercaseRadioButton\', query = True, select = True):\n\t\tuppercaseRadioButtonValue = True\n\telse:\n\t\tuppercaseRadioButtonValue = False\n\n\tcmds.optionVar(intValue = [\'batchRenamer_prefixRadioButton\', prefixRadioButtonValue])\n\tcmds.optionVar(intValue = [\'batchRenamer_suffixRadioButton\', suffixRadioButtonValue])\n\tcmds.optionVar(intValue = [\'batchRenamer_lowercaseRadioButton\', lowercaseRadioButtonValue])\n\tcmds.optionVar(intValue = [\'batchRenamer_uppercaseRadioButton\', uppercaseRadioButtonValue])\n\n\ndef CheckOptionVariables(*args):\n\tstringToAddTextFieldValue = cmds.optionVar(query = \'batchRenamer_stringToAddTextField\')\n\tif stringToAddTextFieldValue != 0 or stringToAddTextFieldValue != \'\' or stringToAddTextFieldValue != \' \' or stringToAddTextFieldValue != None:\n\t\tif stringToAddTextFieldValue == 0:\n\t\t\tcmds.textField(\'stringToAddTextField\', edit = True, text = \'\')\n\t\telse:\n\t\t\tcmds.textField(\'stringToAddTextField\', edit = True, text = stringToAddTextFieldValue)\n\telse:\n\t\tcmds.textField(\'stringToAddTextField\', edit = True, text = \'\')\n\n\tstringToAddAtPositionIntFieldValue = cmds.optionVar(query = \'batchRenamer_stringToAddAtPositionIntField\')\n\tif stringToAddAtPositionIntFieldValue != 0 or stringToAddAtPositionIntFieldValue != \'\' or stringToAddAtPositionIntFieldValue != \' \' or stringToAddAtPositionIntFieldValue != None:\n\t\tcmds.intField(\'stringToAddAtPositionIntField\', edit = True, value = stringToAddAtPositionIntFieldValue)\n\telse:\n\t\tcmds.intField(\'stringToAddAtPositionIntField\', edit = True, value = 0)\n\n\ttoReplaceTextFieldValue = cmds.optionVar(query = \'batchRenamer_toReplaceTextField\')\n\tif toReplaceTextFieldValue != 0 or toReplaceTextFieldValue != \'\' or toReplaceTextFieldValue != \' \' or toReplaceTextFieldValue != None:\n\t\tif toReplaceTextFieldValue == 0:\n\t\t\tcmds.textField(\'toReplaceTextField\', edit = True, text = \'\')\n\t\telse:\n\t\t\tcmds.textField(\'toReplaceTextField\', edit = True, text = toReplaceTextFieldValue)\n\telse:\n\t\tcmds.textField(\'toReplaceTextField\', edit = True, text = \'\')\n\n\treplaceWithTextFieldValue = cmds.optionVar(query = \'batchRenamer_replaceWithTextField\')\n\tif replaceWithTextFieldValue != 0 or replaceWithTextFieldValue != \'\' or replaceWithTextFieldValue != \' \' or replaceWithTextFieldValue != None:\n\t\tif replaceWithTextFieldValue == 0:\n\t\t\tcmds.textField(\'replaceWithTextField\', edit = True, text = \'\')\n\t\telse:\n\t\t\tcmds.textField(\'replaceWithTextField\', edit = True, text = replaceWithTextFieldValue)\n\telse:\n\t\tcmds.textField(\'replaceWithTextField\', edit = True, text = \'\')\n\n\tpaddingCountIntFieldValue = cmds.optionVar(query = \'batchRenamer_paddingCountIntField\')\n\tif paddingCountIntFieldValue != 0 or paddingCountIntFieldValue != \'\' or paddingCountIntFieldValue != \' \' or paddingCountIntFieldValue != None:\n\t\tcmds.intField(\'paddingCountIntField\', edit = True, value = paddingCountIntFieldValue)\n\telse:\n\t\tcmds.intField(\'paddingCountIntField\', edit = True, value = 0)\n\n\tstartAtIntFieldValue = cmds.optionVar(query = \'batchRenamer_startAtIntField\')\n\tif startAtIntFieldValue != 0 or startAtIntFieldValue != \'\' or startAtIntFieldValue != \' \' or startAtIntFieldValue != None:\n\t\tcmds.intField(\'startAtIntField\', edit = True, value = startAtIntFieldValue)\n\telse:\n\t\tcmds.intField(\'startAtIntField\', edit = True, value = 0)\n\n\taddAtFollowingIntFieldValue = cmds.optionVar(query = \'batchRenamer_addAtFollowingIntField\')\n\tif addAtFollowingIntFieldValue != 0 or addAtFollowingIntFieldValue != \'\' or addAtFollowingIntFieldValue != \' \' or addAtFollowingIntFieldValue != None:\n\t\tcmds.intField(\'addAtFollowingIntField\', edit = True, value = addAtFollowingIntFieldValue)\n\telse:\n\t\tcmds.intField(\'addAtFollowingIntField\', edit = True, value = 0)\n\n\trenameAndAddPaddingPaddingNumberIntFieldValue = cmds.optionVar(query = \'batchRenamer_renameAndAddPaddingPaddingNumberIntField\')\n\tif renameAndAddPaddingPaddingNumberIntFieldValue != 0 or renameAndAddPaddingPaddingNumberIntFieldValue != \'\' or renameAndAddPaddingPaddingNumberIntFieldValue != \' \' or renameAndAddPaddingPaddingNumberIntFieldValue != None:\n\t\tcmds.intField(\'renameAndAddPaddingCountIntField\', edit = True, value = renameAndAddPaddingPaddingNumberIntFieldValue)\n\telse:\n\t\tcmds.intField(\'renameAndAddPaddingCountIntField\', edit = True, value = 0)\n\n\n\trenameAndAddPaddingStartAtIntFieldValue = cmds.optionVar(query = \'batchRenamer_renameAndAddPaddingStartAtIntField\')\n\tif renameAndAddPaddingStartAtIntFieldValue != 0 or renameAndAddPaddingStartAtIntFieldValue != \'\' or renameAndAddPaddingStartAtIntFieldValue != \' \' or renameAndAddPaddingStartAtIntFieldValue != None:\n\t\tcmds.intField(\'renameAndAddPaddingStartAtIntField\', edit = True, value = renameAndAddPaddingStartAtIntFieldValue)\n\telse:\n\t\tcmds.intField(\'renameAndAddPaddingStartAtIntField\', edit = True, value = 0)\n\n\n\trenameAndAddPaddingSpecialCharacterTextFieldValue = cmds.optionVar(query = \'batchRenamer_renameAndAddPaddingSpecialCharacterTextField\')\n\tif renameAndAddPaddingSpecialCharacterTextFieldValue:\n\t\tcmds.textField(\'renameAndAddPaddingSpecialCharacterSeparatorTextField\', edit = True, text = renameAndAddPaddingSpecialCharacterTextFieldValue)\n\n\n\trenameAndAddPaddingRenameToTextFieldValue = cmds.optionVar(query = \'batchRenamer_renameAndAddPaddingRenameToTextField\')\n\tif renameAndAddPaddingRenameToTextFieldValue:\n\t\tcmds.textField(\'renameAndAddPaddingRenameToTextField\', edit = True, text = renameAndAddPaddingRenameToTextFieldValue)\n\n\n\tprefixRadioButtonValue = cmds.optionVar(query = \'batchRenamer_prefixRadioButton\')\n\tsuffixRadioButtonValue = cmds.optionVar(query = \'batchRenamer_suffixRadioButton\')\n\tif prefixRadioButtonValue == 1 and suffixRadioButtonValue == 0:\n\t\tcmds.radioButton(\'prefixRadioButton\', edit = True, select = True)\n\t\tcmds.radioButton(\'suffixRadioButton\', edit = True, select = False)\n\telif prefixRadioButtonValue == 0 and suffixRadioButtonValue == 1:\n\t\tcmds.radioButton(\'prefixRadioButton\', edit = True, select = False)\n\t\tcmds.radioButton(\'suffixRadioButton\', edit = True, select = True)\n\telse:\n\t\tcmds.radioButton(\'prefixRadioButton\', edit = True, select = True)\n\t\tcmds.radioButton(\'suffixRadioButton\', edit = True, select = False)\n\n\tlowercaseRadioButtonValue = cmds.optionVar(query = \'batchRenamer_lowercaseRadioButton\')\n\tuppercaseRadioButtonValue = cmds.optionVar(query = \'batchRenamer_uppercaseRadioButton\')\n\tif lowercaseRadioButtonValue == 1 and uppercaseRadioButtonValue == 0:\n\t\tcmds.radioButton(\'lowercaseRadioButton\', edit = True, select = True)\n\t\tcmds.radioButton(\'uppercaseRadioButton\', edit = True, select = False)\n\t\tChangeButtonLabel(\'lowercase\')\n\telif lowercaseRadioButtonValue == 0 and uppercaseRadioButtonValue == 1:\n\t\tcmds.radioButton(\'lowercaseRadioButton\', edit = True, select = False)\n\t\tcmds.radioButton(\'uppercaseRadioButton\', edit = True, select = True)\n\t\tChangeButtonLabel(\'uppercase\')\n\telse:\n\t\tcmds.radioButton(\'lowercaseRadioButton\', edit = True, select = True)\n\t\tcmds.radioButton(\'uppercaseRadioButton\', edit = True, select = False)\n\t\tChangeButtonLabel(\'lowercase\')\n\n\nif __name__ == \'__main__\':\n\tif not cmds.about(batch = True):\n\t\tRenameWindow()'}, {'category': 'Deliver', 'label': 'SmartExporter', 'tooltip': 'Smrt Exporter Tool', 'source': 'python', 'command': 'from pathlib import Path\nimport maya.cmds as cmds\nimport maya.mel as mel\n\n# ---------- Gestion des labels avec emojis ----------\n\nUSE_EMOJI = True  # Mets False si tu veux repasser en ASCII uniquement\n\ndef U(hex_code, fallback=""):\n    """Retourne un caractre Unicode depuis son code hex, ou fallback."""\n    try:\n        return chr(int(hex_code, 16)) if USE_EMOJI else fallback\n    except:\n        return fallback\n\ndef L(emoji_hex, text):\n    """Construit un label avec emoji + texte (si activ)."""\n    emoji = U(emoji_hex, "")\n    return f"{emoji} {text}" if emoji else text\n\n# ---------- UI ----------\n\ndef show_export_ui():\n    if cmds.window("customExportWin", exists=True):\n        cmds.deleteUI("customExportWin")\n\n    cmds.window("customExportWin", title="Custom Exporter", sizeable=False)\n    cmds.columnLayout(adjustableColumn=True, rowSpacing=10,\n                      columnAlign="center", columnAttach=("both", 10))\n\n    cmds.optionMenu("exportFormat", label=L("1F4DD", "Format :"))  # ??\n    cmds.menuItem(label="fbx")\n    cmds.menuItem(label="obj")\n\n    cmds.checkBox("triangulateCheck", label=L("1F9CA", "Triangulation"), value=False)  # ??\n    cmds.checkBox("moveToOriginCheck", label=L("1F3AF", "Move to Origin (utilise le pivot)"), value=True)  # ??\n\n    cmds.optionMenu("upAxisMenu", label=L("1F9ED", "UP Axis :"))  # ??\n    cmds.menuItem(label="Y")\n    cmds.menuItem(label="Z")\n\n    cmds.textFieldButtonGrp("pathField", label=L("1F4C1", "Dossier export :"),  # ??\n                            buttonLabel="Parcourir", text="", buttonCommand=browse_folder)\n    cmds.textFieldGrp("groupStringField", label=L("1F50E", "Groupe  exporter si contient :"), text="SM_")  # ??\n\n    cmds.checkBox("autoSubdirsCheck", label=L("1F4C2", "Crer Sous-Dossiers (chane des GRP_ uniquement)"), value=True)  # ??\n\n    cmds.button(label=L("1F680", "Exporter la slection"), command=perform_export)  # ??\n    cmds.setParent("..")\n    cmds.showWindow("customExportWin")\n\ndef browse_folder(*args):\n    folder = cmds.fileDialog2(dialogStyle=2, fileMode=3)\n    if folder:\n        cmds.textFieldButtonGrp("pathField", edit=True, text=folder[0])\n\ndef perform_export(*args):\n    fmt = cmds.optionMenu("exportFormat", query=True, value=True)\n    triangulate = cmds.checkBox("triangulateCheck", query=True, value=True)\n    move_to_origin = cmds.checkBox("moveToOriginCheck", query=True, value=True)\n    up_axis = cmds.optionMenu("upAxisMenu", query=True, value=True)\n    path = cmds.textFieldButtonGrp("pathField", query=True, text=True)\n    group_identifier = cmds.textFieldGrp("groupStringField", query=True, text=True)\n    auto_subdirs = cmds.checkBox("autoSubdirsCheck", query=True, value=True)\n\n    print(f"\\n?? Format : {fmt}\\n?? Triangulation : {triangulate}\\n?? Move to Origin : {move_to_origin}\\n?? UP Axis : {up_axis}\\n?? Dossier export : {path}\\n?? Sous-dossiers auto : {auto_subdirs}\\n")\n\n    if not path or not Path(path).exists():\n        cmds.confirmDialog(title="Erreur", message="Le chemin dexport est invalide.", button=["OK"])\n        return\n\n    sel = cmds.ls(selection=True, long=True)\n    if not sel:\n        cmds.confirmDialog(title="Erreur", message="Veuillez slectionner au moins un objet.", button=["OK"])\n        return\n\n    for obj in sel:\n        print(f"?? Analyse de : {obj}")\n        export_node(obj, fmt, triangulate, move_to_origin, up_axis, path, group_identifier, auto_subdirs)\n\n    print("\\n? Export termin pour tous les objets slectionns.")\n\n# ---------- Helpers noms/chemins ----------\n\ndef _basename_from_longname(longname):\n    short = longname.split("|")[-1]\n    return short.split(":")[-1]\n\ndef _ancestors_from_longname(longname):\n    parts = [p for p in longname.split("|") if p]\n    if len(parts) <= 1:\n        return []\n    ancestors = parts[:-1]\n    return [a.split(":")[-1] for a in ancestors]\n\ndef _group_folder_chain(longname):\n    ancestors = _ancestors_from_longname(longname)\n    return [a for a in ancestors if a.startswith("GRP_")]\n\n# ---------- Export logique ----------\n\ndef export_node(node, fmt, triangulate, move_to_origin, up_axis, export_path, identifier, auto_subdirs):\n    name = _basename_from_longname(node)\n    if identifier in name:\n        _export_single_node(node, name, fmt, triangulate, move_to_origin, up_axis, export_path, auto_subdirs)\n    else:\n        children = cmds.listRelatives(node, children=True, type="transform", fullPath=True) or []\n        if not children:\n            shapes = cmds.listRelatives(node, shapes=True, fullPath=True)\n            if shapes:\n                _export_single_node(node, name, fmt, triangulate, move_to_origin, up_axis, export_path, auto_subdirs)\n        else:\n            for child in children:\n                export_node(child, fmt, triangulate, move_to_origin, up_axis, export_path, identifier, auto_subdirs)\n\ndef _get_scene_up_axis():\n    return cmds.upAxis(query=True, axis=True).upper()\n\ndef _apply_up_axis_correction(temp_node, desired_up, fmt):\n    desired = desired_up.upper()\n    scene_up = _get_scene_up_axis()\n    if scene_up == desired:\n        return\n    if fmt.lower() == "fbx":\n        sign = -1 if (scene_up == "Y" and desired == "Z") else +1\n    else:\n        sign = +1 if (scene_up == "Y" and desired == "Z") else -1\n    cmds.rotate(90 * sign, 0, 0, temp_node, relative=True, os=True)\n\ndef _export_single_node(original_node, name, fmt, triangulate, move_to_origin, up_axis, export_path, auto_subdirs):\n    dest_dir = Path(export_path).joinpath(*_group_folder_chain(original_node)) if auto_subdirs else Path(export_path)\n    dest_dir.mkdir(parents=True, exist_ok=True)\n    export_file = dest_dir / f"{name}.{fmt}"\n\n    temp = cmds.duplicate(original_node, name=f"{name}_tempExport")[0]\n    try: cmds.parent(temp, world=True)\n    except: pass\n\n    _apply_up_axis_correction(temp, up_axis, fmt)\n\n    if fmt == "obj" and triangulate:\n        meshes = cmds.listRelatives(temp, allDescendents=True, type="mesh", fullPath=True) or []\n        if meshes:\n            parents = list({cmds.listRelatives(m, parent=True, fullPath=True)[0] for m in meshes})\n            cmds.select(parents, r=True)\n            cmds.polyTriangulate()\n\n    if move_to_origin:\n        rp = cmds.xform(temp, q=True, ws=True, rp=True)\n        cmds.move(-rp[0], -rp[1], -rp[2], temp, r=True, ws=True)\n\n    cmds.makeIdentity(temp, apply=True, translate=True, rotate=True, scale=True)\n\n    cmds.select(temp, replace=True)\n\n    try:\n        if fmt == "fbx":\n            mel.eval(\'FBXResetExport;\')\n            mel.eval(f\'FBXExportUpAxis "{up_axis.upper()}";\')\n            mel.eval(\'FBXExportSmoothingGroups -v true;\')\n            mel.eval(\'FBXExportTangents -v true;\')\n            mel.eval(\'FBXExportSmoothMesh -v true;\')\n            mel.eval(\'FBXExportHardEdges -v false;\')\n            mel.eval(\'FBXExportBakeComplexAnimation -v false;\')\n            mel.eval(\'FBXExportInputConnections -v true;\')\n            mel.eval(\'FBXExportInAscii -v false;\')\n            mel.eval(f\'FBXExportTriangulate -v {"true" if triangulate else "false"};\')\n            mel.eval(f\'FBXExport -f "{export_file.as_posix()}" -s;\')\n        elif fmt == "obj":\n            cmds.file(\n                export_file.as_posix(),\n                force=True,\n                options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1",\n                typ="OBJexport",\n                pr=True,\n                es=True\n            )\n    except Exception as e:\n        print(f"? ERREUR export {name} : {e}")\n\n    cmds.delete(temp)\n\n# ---------- Lancer UI ----------\nshow_export_ui()\n'}, {'category': 'Deliver', 'label': 'Import FBX Mat', 'tooltip': 'Import an FBX, but check if already same materials exists in the scene', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport maya.mel as mel\nimport os\n\ndef reassign_materials(original_materials):\n    # Get a list of all materials in the scene after import\n    imported_materials = cmds.ls(mat=True)\n\n    # Iterate through the imported materials and compare with original materials\n    for material in imported_materials:\n        if material not in original_materials:\n            # Extract the base name of the material (without any suffix)\n            base_name = material.rstrip("0123456789")\n\n            if base_name in original_materials:\n                # If a material with the same base name exists, reassign it\n                print(f"Material \'{material}\' found as existing material \'{base_name}\'. Reassigning...")\n                assigned_objects = cmds.listConnections(material + \'.outColor\', type=\'shadingEngine\')\n                if assigned_objects:\n                    for shading_group in assigned_objects:\n                        connected_objects = cmds.sets(shading_group, q=True)\n                        if connected_objects:\n                            cmds.select(connected_objects, r=True)\n                            cmds.hyperShade(assign=base_name)\n                # Delete the newly imported duplicate material\n                cmds.delete(material)\n            else:\n                print(f"Material \'{material}\' is unique, keeping it.")\n        else:\n            print(f"Material \'{material}\' is an original material, keeping it.")\n\ndef import_fbx_without_creating_materials():\n    # Open a file dialog to select the FBX file\n    fbx_path = cmds.fileDialog2(fileFilter="*.fbx", dialogStyle=2, fileMode=1, caption="Import FBX File")\n\n    # Check if the user selected a file\n    if fbx_path:\n        fbx_path = fbx_path[0]\n        if not os.path.exists(fbx_path):\n            cmds.error("File not found.")\n            return\n\n        # Store the original materials before import\n        original_materials = cmds.ls(materials=True)\n\n        # Import the FBX file\n        cmds.file(fbx_path, i=True, type="FBX", ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace=":", options="fbx")\n\n        # Call the function to reassign materials after import\n        reassign_materials(original_materials)\n    else:\n        cmds.error("No file selected.")\n\n# Execute the function to display the file dialog and import the FBX\nimport_fbx_without_creating_materials()\n'}, {'category': 'Deliver', 'label': 'UV Transfer', 'tooltip': 'Transfer the UV between two objects', 'source': 'python', 'command': 'import maya.cmds as cmds\n\ndef transfer_uvs_to_target(source_obj):\n    # Get the currently selected object as the target object\n    target_obj = cmds.ls(selection=True, long=True)\n    \n    if not target_obj:\n        cmds.warning("No target object selected.")\n        return\n    \n    target_obj = target_obj[0]\n\n    # Verify that both source and target have the same topology\n    if cmds.polyEvaluate(source_obj, face=True) != cmds.polyEvaluate(target_obj, face=True):\n        cmds.warning("Source and target objects do not have the same topology.")\n        return\n\n    # Transfer UVs from source to target using polyTransfer\n    try:\n        cmds.polyTransfer(target_obj, uv=1, alternateObject=source_obj)\n        cmds.warning(f"UVs transferred from {source_obj} to {target_obj} successfully.")\n    except Exception as e:\n        cmds.warning(f"Failed to transfer UVs: {e}")\n\n    # Clear selection\n    cmds.select(clear=True)\n\n    # Schedule the cleanup of the scriptJob\n    cmds.evalDeferred(kill_script_job)\n\ndef kill_script_job():\n    global my_script_job\n    if cmds.scriptJob(exists=my_script_job):\n        cmds.scriptJob(kill=my_script_job, force=True)\n\ndef on_target_selected():\n    # Get the source object stored in a global variable\n    source_obj = cmds.optionVar(q="sourceObj")\n    if source_obj:\n        transfer_uvs_to_target(source_obj)\n    else:\n        cmds.warning("No source object found.")\n\ndef transfer_uvs():\n    # Get the selected objects\n    selected_objects = cmds.ls(selection=True, long=True)\n    \n    if len(selected_objects) != 1:\n        cmds.warning("Please select the source object only.")\n        return\n    \n    source_obj = selected_objects[0]\n    cmds.optionVar(sv=("sourceObj", source_obj))\n    \n    # Notify the user to select the target object\n    cmds.warning("Please select the target object to transfer UVs to.")\n    \n    # Set up a scriptJob to wait for the next selection\n    global my_script_job\n    my_script_job = cmds.scriptJob(event=["SelectionChanged", on_target_selected], runOnce=True)\n\n# Run the function\ntransfer_uvs()\n'}, {'category': 'Deliver', 'label': 'RizomUV', 'tooltip': 'Send UV to RizomUV', 'source': 'python', 'command': 'import maya.cmds as cmds\nimport subprocess, tempfile, os, platform\nimport maya.mel as mel\n\n###########################################################################\n#  Change the RizomUV path to your location                               #\n###########################################################################\nrizomPath = r\'C:\\Program Files\\Rizom Lab\\RizomUV 2023.0\\rizomuv.exe\'\n#osx path is usually "/Applications/RizomUV.2018.0.app"\n################## DONT TOUCH ANYTHING BELOW THIS LINE ####################\n\ndef sendToRizom(*args):\n  obj = cmds.ls( selection=True, geometry=True, ap=True, dag=True)\n\n  exportFile = tempfile.gettempdir() + os.sep + "ODRizomExport.obj"\n  cmds.file(exportFile, f=1, pr=1, typ="OBJexport", es=1, op="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")\n  if cmds.checkBox(\'uvcheck\', query=True, value=True):\n    cmd = \'"\' + rizomPath + \'" "\' + exportFile + \'"\'\n  else:\n    cmd = \'"\' + rizomPath + \'" /nu "\' + exportFile + \'"\'\n  if platform.system() == "Windows":\n    subprocess.Popen(cmd)\n  else:\n    subprocess.Popen(["open", "-a", rizomPath, "--args", exportFile])\n\ndef getFromRizom(*args):\n  originalOBJs = cmds.ls( selection=True, geometry=True, ap=True, dag=True)\n  exportFile = tempfile.gettempdir() + os.sep + "ODRizomExport.obj"\n\n  if cmds.checkBox(\'linecheck\', query=True, value=True):\n    f = open(exportFile, "r")\n    lines = f.readlines()\n    f.close()\n\n    f = open(exportFile, "w")\n    for line in lines:\n      if not line.startswith("#ZOMPROPERTIES"):\n        f.write(line)\n    f.close()\n\n  cmds.file(exportFile, i=1, typ="OBJ", pr=1, op="mo=1", ns="ODRIZUV")\n  \n  cmds.select("ODRIZUV*:*")\n  importedOBJs = cmds.ls(selection=True, geometry=True, o=True, s=False)\n  cmds.select(clear=True)\n\n  actualReplacedUVOJBs = []\n  for obj in originalOBJs:\n    for imp in importedOBJs:\n      if obj.replace("Shape", "") in imp:\n        cmds.polyTransfer(obj.replace("Shape", ""), vc=0, uv=1, v=0, ao=imp[:-5])\n        actualReplacedUVOJBs.append(obj.replace("Shape", ""))\n        break\n\n  for obj in importedOBJs:\n    cmds.select(obj[:-5], r=True)\n    cmds.delete()\n\n  for obj in actualReplacedUVOJBs:\n    cmds.select(obj, add=True)\n\ndef rizomAutoRoundtrip(*args):\n\n  originalOBJs = cmds.ls( selection=True, geometry=True, ap=True, dag=True)\n  exportFile = tempfile.gettempdir() + os.sep + "ODRizomExport.obj"\n  cmds.file(exportFile, f=1, pr=1, typ="OBJexport", es=1, op="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")\n\n  luascript = """ZomLoad({File={Path="odfilepath", ImportGroups=true, XYZ=true}, NormalizeUVW=true})\n--U3dSymmetrySet({Point={0, 0, 0}, Normal={1, 0, 0}, Threshold=0.01, Enabled=true, UPos=0.5, LocalMode=false})\nZomSelect({PrimType="Edge", Select=true, ResetBefore=true, ProtectMapName="Protect", FilterIslandVisible=true, Auto={Skeleton={}, Open=true, PipesCutter=true, HandleCutter=true}})\nZomCut({PrimType="Edge"})\nZomUnfold({PrimType="Edge", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, PinMapName="Pin", ProcessNonFlats=true, ProcessSelection=true, ProcessAllIfNoneSelected=true, ProcessJustCut=true, BorderIntersections=true, TriangleFlips=true})\nZomIslandGroups({Mode="DistributeInTilesEvenly", MergingPolicy=8322, GroupPath="RootGroup"})\nZomPack({ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={Mode=2}, Rotate={}, Translate=true, LayoutScalingMode=2})\nZomSave({File={Path="odfilepath", UVWProps=true}, __UpdateUIObjFileName=true})\nZomQuit()\n"""\n\n  f = open(tempfile.gettempdir() + os.sep + "riz.lua", "w")\n  f.write(luascript.replace("odfilepath", exportFile.replace("\\\\", "/")))\n  f.close()\n\n  cmd = \'"\' + rizomPath + \'" -cfi "\' + tempfile.gettempdir() + os.sep + "riz.lua" + \'"\'\n  if platform.system() == "Windows":\n    subprocess.call(cmd, shell=False)\n  else:\n    os.system(\'open -W "\' + rizomPath + \'" --args -cfi "\'+tempfile.gettempdir() + os.sep + \'riz.lua"\')\n    #subprocess.Popen(["open", "-a", rizomPath, "--args", " -cfi ", tempfile.gettempdir() + os.sep + "riz.lua"])\n\n  if cmds.checkBox(\'linecheck\', query=True, value=True):\n    f = open(exportFile, "r")\n    lines = f.readlines()\n    f.close()\n\n    f = open(exportFile, "w")\n    for line in lines:\n      if not line.startswith("#ZOMPROPERTIES"):\n        f.write(line)\n    f.close()\n\n  cmds.file(exportFile, i=1, typ="OBJ", pr=1, op="mo=1", ns="ODRIZUV")\n  \n  cmds.select("ODRIZUV*:*")\n  importedOBJs = cmds.ls(selection=True, geometry=True, o=True, s=False)\n  cmds.select(clear=True)\n\n  actualReplacedUVOJBs = []\n  for obj in originalOBJs:\n    for imp in importedOBJs:\n      if obj.replace("Shape", "") in imp:\n        cmds.polyTransfer(obj.replace("Shape", ""), vc=0, uv=1, v=0, ao=imp[:-5])\n        actualReplacedUVOJBs.append(obj.replace("Shape", ""))\n        break\n\n  for obj in importedOBJs:\n    cmds.select(obj[:-5], r=True)\n    cmds.delete()\n\n  for obj in actualReplacedUVOJBs:\n    cmds.select(obj, add=True)\n\n# UI\ncmds.window(title="OD Maya <-> RizomUV Bridge" )\ncmds.columnLayout()\ncmds.button( label=\'Send To RizomUV\', width=300, command=sendToRizom)\ncmds.checkBox(\'uvcheck\', label=\'Transfer Existing UVs to Rizom\', align=\'center\')\ncmds.button( label=\'Get From RizomUV\', width=300, command=getFromRizom)\ncmds.checkBox(\'linecheck\', label=\'Long Line Check (intermediate Rizom fix for long lines)\', align=\'center\')\ncmds.button( label=\'RizomUV Automatic Roundtrip\', width=300, command=rizomAutoRoundtrip)\ncmds.showWindow()'}]


def _elk_data_dir_candidates():
    candidates = []
    try:
        versioned_scripts_dir = Path(cmds.internalVar(userScriptDir=True)).resolve()
    except Exception:
        versioned_scripts_dir = None

    if versioned_scripts_dir is not None:
        candidates.append((versioned_scripts_dir / "ELK_CUSTOM_SHELF").resolve())
        maya_root = versioned_scripts_dir.parent.parent if len(versioned_scripts_dir.parents) >= 2 else None
        if maya_root is not None:
            candidates.append((maya_root / "scripts" / "ELK_CUSTOM_SHELF").resolve())

    try:
        this_file = Path(__file__).resolve()
        candidates.append(this_file.parent)
    except Exception:
        pass

    ordered = []
    seen = set()
    for cand in candidates:
        key = str(cand).lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cand)
    return ordered


def _resolve_elk_data_dir():
    candidates = _elk_data_dir_candidates()
    if not candidates:
        return Path.cwd()

    for folder in candidates:
        if folder.exists():
            return folder

    preferred = candidates[0]
    try:
        preferred.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return preferred


def _first_existing_meta_file(file_name):
    for folder in _elk_data_dir_candidates():
        meta_file = folder / file_name
        if meta_file.exists():
            return meta_file
    return BASE_DIR / file_name


BASE_DIR = _resolve_elk_data_dir()
SCRIPTS_ROOT = BASE_DIR / "scripts"
CATEGORY_META_FILE = _first_existing_meta_file("categories.json")
ITEMS_META_FILE = _first_existing_meta_file("items_order.json")
ICONS_DIR = BASE_DIR / "Icons"

ANIMATION_DURATION = 160
REORDER_COOLDOWN_MS = 30
REORDER_CONFIRM_FRAMES = 10
HYSTERESIS_RATIO = 1

MIN_SUPPORTED_MAYA_VERSION = 2022
AUTO_HIDE_MAYA_SHELF = True
AUTO_RESPONSIVE_DOCK_HEIGHT = True
DOCK_HEIGHT_FALLBACK = 120
DOCK_HEIGHT_MIN = 84
DOCK_HEIGHT_MAX_RATIO = 0.26


def _maya_version_int():
    """Return Maya major version as int when available (e.g. 2022, 2027)."""
    try:
        return int(cmds.about(version=True))
    except Exception:
        return None


def _is_maya_2022_compat_mode():
    return _maya_version_int() == 2022


def _warn_if_unsupported_maya():
    version = _maya_version_int()
    if version is not None and version < MIN_SUPPORTED_MAYA_VERSION:
        cmds.warning("[ELK UI] Unsupported Maya version {}. Minimum supported version is {}.".format(version, MIN_SUPPORTED_MAYA_VERSION))


def _maya2022_log(step, error=None):
    """Logs détaillés pour diagnostiquer les points de casse sur Maya 2022."""
    if not _is_maya_2022_compat_mode():
        return
    if error is None:
        print("[ELK UI][Maya2022][OK] {}".format(step))
        return
    cmds.warning("[ELK UI][Maya2022][ERROR] {} -> {}: {}".format(step, error.__class__.__name__, error))
    traceback.print_exc()


def event_global_pos(event):
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()




class ELKCategoryScrollArea(QtWidgets.QScrollArea):
    """Map vertical wheel motion to internal horizontal category scrolling."""

    def __init__(self, parent_category=None, *args, **kwargs):
        super(ELKCategoryScrollArea, self).__init__(*args, **kwargs)
        self._parent_category = parent_category

    def wheelEvent(self, event):
        parent_category = self._parent_category
        parent_ui = getattr(parent_category, "parent_ui", None)
        if parent_ui is not None and getattr(parent_ui, "is_horizontal_mode", None) and parent_ui.is_horizontal_mode():
            delta = event.angleDelta()
            dx = delta.x()
            dy = delta.y()
            step = dx if abs(dx) > abs(dy) and dx != 0 else dy
            if step != 0:
                bar = self.horizontalScrollBar()
                if bar is not None and bar.maximum() > bar.minimum():
                    lines = step / 120.0
                    single_step = bar.singleStep() or 20
                    bar.setValue(bar.value() - int(round(lines * single_step)))
                    event.accept()
                    return
        super(ELKCategoryScrollArea, self).wheelEvent(event)

def _unique_fs_path(base_path):
    p = Path(base_path)
    if not p.exists():
        return p
    i = 2
    while True:
        cand = p.parent / f"{p.name}_{i}"
        if not cand.exists():
            return cand
        i += 1

def _iter_live_ui_instances():
    instances = globals().setdefault("ELK_UI_INSTANCES", [])
    alive = []
    for ui in list(instances):
        try:
            if ui is not None and hasattr(ui, "isVisible") and ui.parent() is not None:
                alive.append(ui)
        except Exception:
            continue
    globals()["ELK_UI_INSTANCES"] = alive
    return alive

def _broadcast_refresh(source_ui=None):
    for ui in _iter_live_ui_instances():
        if ui is source_ui:
            continue
        try:
            ui._refresh_ui_data()
        except Exception:
            continue

def _load_category_meta():
    data = {"order": [], "names": {}, "icons": {}, "icon_colors": {}}
    if not CATEGORY_META_FILE.exists():
        _save_category_meta(data)
        return data
    if CATEGORY_META_FILE.exists():
        try:
            parsed = json.loads(CATEGORY_META_FILE.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data["order"] = [str(x) for x in parsed.get("order", []) if str(x).strip()]
                names = parsed.get("names", {})
                if isinstance(names, dict):
                    data["names"] = {str(k): str(v) for k, v in names.items() if str(k).strip()}
                icons = parsed.get("icons", {})
                if isinstance(icons, dict):
                    data["icons"] = {str(k): str(v) for k, v in icons.items() if str(k).strip() and str(v).strip()}
                icon_colors = parsed.get("icon_colors", {})
                if isinstance(icon_colors, dict):
                    data["icon_colors"] = {str(k): str(v) for k, v in icon_colors.items() if str(k).strip() and str(v).strip()}
        except Exception:
            pass
    return data

def _save_category_meta(meta):
    CATEGORY_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    CATEGORY_META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

def _sync_category_meta_from_fs():
    meta = _load_category_meta()
    slugs = [d.name for d in SCRIPTS_ROOT.iterdir() if d.is_dir()] if SCRIPTS_ROOT.exists() else []
    names = dict(meta.get("names") or {})
    order = [x for x in (meta.get("order") or []) if x in slugs]
    for slug in slugs:
        names.setdefault(slug, slug.replace('_', ' ').title())
        if slug not in order:
            order.append(slug)
    meta = {"order": order, "names": names, "icons": dict(meta.get("icons") or {}), "icon_colors": dict(meta.get("icon_colors") or {})}
    _save_category_meta(meta)
    return meta

def _display_to_slug(category_name):
    name = (category_name or "").strip()
    if not name:
        return "tools"
    meta = _sync_category_meta_from_fs()
    target = name.casefold()
    for slug, disp in (meta.get("names") or {}).items():
        if (disp or "").strip().casefold() == target:
            return slug
    return _slugify(name)

def _slugify(text):
    t = re.sub(r"[^a-zA-Z0-9_]+", "_", (text or "item").strip().lower()).strip("_")
    return t or "item"


def _is_valid_script_name(name):
    value = (name or "").strip()
    if not value:
        return False
    if value in {'.', '..'}:
        return False
    return re.match(r'^[^\\/:*?"<>|]+$', value, re.UNICODE) is not None

def _script_payload(item):
    meta = {
        "label": item.get("label", ""),
        "short_name": item.get("short_name", ""),
        "tooltip": item.get("tooltip", ""),
        "source": item.get("source", "python"),
        "icon_svg": item.get("icon_svg", ""),
        "icon_color": item.get("icon_color", ""),
    }
    return "# ELK_META " + json.dumps(meta, ensure_ascii=False) + "\n" + (item.get("command", "") or "")

def _read_script_file(path, category):
    path = Path(path)
    txt = path.read_text(encoding="utf-8")
    lines = txt.splitlines()
    meta = {}
    command = txt
    if lines and (lines[0].startswith("# ELK_META ") or lines[0].startswith("// ELK_META ")):
        try:
            meta = json.loads(lines[0].split("ELK_META ", 1)[1].strip())
        except Exception:
            meta = {}
        command = "\n".join(lines[1:])
    source = meta.get("source") or ('mel' if path.suffix.lower() == '.mel' else 'python')
    return {"category": category, "label": meta.get("label") or path.stem, "short_name": meta.get("short_name", ""), "tooltip": meta.get("tooltip", ""), "source": source, "command": command, "icon_svg": normalize_icon_name(meta.get("icon_svg", "")), "icon_color": meta.get("icon_color", ""), "file_path": str(path)}

def bootstrap_scripts_from_legacy():
    if SCRIPTS_ROOT.exists() and any(SCRIPTS_ROOT.rglob('*.*')):
        return
    for item in LEGACY_SHELF_ITEMS:
        cat_dir = SCRIPTS_ROOT / _display_to_slug(item.get('category','tools'))
        cat_dir.mkdir(parents=True, exist_ok=True)
        stem = _slugify(item.get('label','script'))
        ext = '.mel' if (item.get('source','python') or '').lower() == 'mel' else '.py'
        out = cat_dir / f"{stem}{ext}"
        i=1
        while out.exists():
            i += 1
            out = cat_dir / f"{stem}_{i}{ext}"
        out.write_text(_script_payload(item), encoding='utf-8')



def migrate_script_extensions():
    if not SCRIPTS_ROOT.exists():
        return
    for py_file in SCRIPTS_ROOT.rglob('*.py'):
        try:
            lines = py_file.read_text(encoding='utf-8').splitlines()
            if lines and lines[0].startswith('# ELK_META '):
                meta = json.loads(lines[0][11:].strip())
                if (meta.get('source') or '').lower() == 'mel':
                    mel_path = py_file.with_suffix('.mel')
                    mel_path.write_text('\n'.join(lines[1:]), encoding='utf-8')
                    py_file.unlink()
        except Exception:
            continue
def _load_items_meta():
    data = {"order": [], "category_by_file": {}}
    if not ITEMS_META_FILE.exists():
        _save_items_meta(data)
        return data
    if ITEMS_META_FILE.exists():
        try:
            parsed = json.loads(ITEMS_META_FILE.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                data["order"] = [str(x) for x in parsed.get("order", []) if str(x).strip()]
                cbf = parsed.get("category_by_file", {})
                if isinstance(cbf, dict):
                    data["category_by_file"] = {str(k): str(v) for k, v in cbf.items()}
        except Exception:
            pass
    return data


def _save_items_meta(meta):
    ITEMS_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    ITEMS_META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def load_shelf_items():
    migrate_script_extensions()
    cat_meta = _sync_category_meta_from_fs()
    item_meta = _load_items_meta()
    items=[]
    dirs = [d for d in SCRIPTS_ROOT.iterdir() if d.is_dir()] if SCRIPTS_ROOT.exists() else []
    rank = {slug: i for i, slug in enumerate(cat_meta.get('order') or [])}
    for cat_dir in sorted(dirs, key=lambda p: (rank.get(p.name, 9999), p.name)):
        cat = (cat_meta.get('names') or {}).get(cat_dir.name, cat_dir.name.replace('_', ' ').title())
        for sp in [x for x in cat_dir.iterdir() if x.suffix.lower() in ('.py', '.mel')]:
            try:
                rel = str(sp.relative_to(BASE_DIR)).replace('\\', '/')
                cat = item_meta.get("category_by_file", {}).get(rel, cat)
                item = _read_script_file(sp, cat)
                item["file_key"] = rel
                items.append(item)
            except Exception:
                continue
    order_rank = {k: i for i, k in enumerate(item_meta.get("order") or [])}
    items.sort(key=lambda it: (rank.get(_display_to_slug(it.get('category', 'Tools')), 9999), order_rank.get(it.get('file_key',''), 99999), it.get('label','').lower()))
    return items

def save_item_to_disk(item):
    cat_dir = SCRIPTS_ROOT / _display_to_slug(item.get('category','tools'))
    cat_dir.mkdir(parents=True, exist_ok=True)
    source = (item.get('source') or 'python').lower()
    ext = '.mel' if source == 'mel' else '.py'
    existing = item.get('file_path')
    if existing:
        out = Path(existing)
        if out.suffix.lower() != ext:
            out = out.with_suffix(ext)
    else:
        out = cat_dir / f"{_slugify(item.get('label','script'))}{ext}"
    payload = item.get('command','') or ''
    if source == 'python':
        payload = _script_payload(item)
    else:
        meta = {
            "label": item.get("label", ""),
            "short_name": item.get("short_name", ""),
            "tooltip": item.get("tooltip", ""),
            "source": "mel",
            "icon_svg": item.get("icon_svg", ""),
            "icon_color": item.get("icon_color", ""),
        }
        payload = "// ELK_META " + json.dumps(meta, ensure_ascii=False) + "\n" + payload
    out.write_text(payload, encoding='utf-8')
    return str(out)
BG="#2a2a2a"; PANEL="#373737"; BUTTON_BG="#444444"; BUTTON_HOVER="#505050"; BORDER="#565656"; TEXT="#f0f0f0"; MUTED="#b7b7b7"

def run_item(item):
    cmd=item.get("command","") or ""
    if not cmd.strip():
        cmds.warning("[ELK UI] Empty command: {}".format(item.get("label","Tool"))); return
    try:
        if (item.get("source") or "mel").lower()=="python":
            glb={"cmds":cmds,"mel":mel,"maya":__import__("maya")}; exec(cmd, glb, glb)
        else:
            mel.eval(cmd)
    except Exception as e:
        cmds.warning("[ELK UI] Error in {}: {}".format(item.get("label","Tool"), e)); traceback.print_exc()

ICON_COLORS = [
    "#36d6ff", "#67e86a", "#ffad3b", "#a56bff", "#ffd43b", "#ff5d3b",
    "#4cc9f0", "#f72585", "#90f1ef", "#caff70", "#ff8fab", "#b8f2e6",
]

def stable_hash(text):
    text = text or ""
    h = 0
    for ch in text:
        h = (h * 33 + ord(ch)) & 0xffffffff
    return h

def item_color(item):
    return (item or {}).get("icon_color") or "#36d6ff"


def icon_catalog():
    if not ICONS_DIR.exists() or not ICONS_DIR.is_dir():
        return []
    try:
        return sorted([p for p in ICONS_DIR.iterdir() if p.suffix.lower() == ".svg"], key=lambda p: p.name.lower())
    except Exception:
        return []


def normalize_icon_name(icon_name):
    n = (icon_name or "").strip()
    if not n:
        return ""
    return n if n.lower().endswith(".svg") else (n + ".svg")


def resolve_icon_path(icon_name):
    name = normalize_icon_name(icon_name)
    if not name:
        return None
    p = ICONS_DIR / name
    return p if p.exists() else None


def tokenized(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _clean_tooltip(text, limit=240):
    text = (text or '').strip()
    # Avoid giant black tooltip blocks containing full scripts.
    text = ' '.join(text.split())
    if not text:
        return ''
    if len(text) > limit:
        text = text[:limit].rstrip() + '…'
    return text

class VectorIcon(QtWidgets.QWidget):
    def __init__(self, kind="tool", color="#36d6ff", size=18, parent=None):
        super(VectorIcon,self).__init__(parent)
        self.kind=(kind or "tool").lower()
        self.color=QtGui.QColor(color)
        self.setFixedSize(size,size)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

    def paintEvent(self,event):
        p=QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        w=self.width(); h=self.height(); c=self.color
        pen=QtGui.QPen(c, max(1.35, w*.08))
        pen.setCapStyle(QtCore.Qt.RoundCap); pen.setJoinStyle(QtCore.Qt.RoundJoin)
        p.setPen(pen); p.setBrush(QtCore.Qt.NoBrush)
        k=self.kind
        r=QtCore.QRectF(w*.2,h*.2,w*.6,h*.6)

        # Category icons
        if "tool" in k:
            p.drawLine(w*.25,h*.75,w*.75,h*.25)
            p.drawEllipse(QtCore.QRectF(w*.58,h*.08,w*.28,h*.28))
            p.drawEllipse(QtCore.QRectF(w*.14,h*.64,w*.22,h*.22))
        elif "object" in k:
            pts=[QtCore.QPointF(w*.5,h*.12),QtCore.QPointF(w*.82,h*.3),QtCore.QPointF(w*.82,h*.68),QtCore.QPointF(w*.5,h*.88),QtCore.QPointF(w*.18,h*.68),QtCore.QPointF(w*.18,h*.3),QtCore.QPointF(w*.5,h*.12)]
            for a,b in zip(pts,pts[1:]): p.drawLine(a,b)
            p.drawLine(w*.18,h*.3,w*.5,h*.48); p.drawLine(w*.82,h*.3,w*.5,h*.48); p.drawLine(w*.5,h*.48,w*.5,h*.88)
        elif "sculpt" in k:
            p.drawEllipse(QtCore.QRectF(w*.18,h*.18,w*.52,h*.52)); p.drawLine(w*.62,h*.62,w*.86,h*.86)
        elif "action" in k:
            p.drawLine(w*.18,h*.52,w*.82,h*.52); p.drawLine(w*.62,h*.32,w*.82,h*.52); p.drawLine(w*.62,h*.72,w*.82,h*.52)
        elif "nurbs" in k:
            path=QtGui.QPainterPath(); path.moveTo(w*.12,h*.7); path.cubicTo(w*.35,h*.1,w*.65,h*.9,w*.88,h*.3); p.drawPath(path)
        elif "deliver" in k or "export" in k or "import" in k:
            p.drawRect(QtCore.QRectF(w*.25,h*.45,w*.5,h*.35)); p.drawLine(w*.5,h*.12,w*.5,h*.62); p.drawLine(w*.32,h*.3,w*.5,h*.12); p.drawLine(w*.68,h*.3,w*.5,h*.12)
        else:
            # Per-button icons: deterministic, no external library.
            shape = stable_hash(k) % 12
            if shape == 0:
                p.drawRoundedRect(r, 4, 4); p.drawLine(w*.34,h*.5,w*.66,h*.5); p.drawLine(w*.5,h*.34,w*.5,h*.66)
            elif shape == 1:
                p.drawEllipse(r); p.drawLine(w*.50,h*.18,w*.50,h*.82); p.drawLine(w*.18,h*.50,w*.82,h*.50)
            elif shape == 2:
                p.drawRect(QtCore.QRectF(w*.22,h*.22,w*.46,h*.46)); p.drawRect(QtCore.QRectF(w*.36,h*.36,w*.46,h*.46))
            elif shape == 3:
                p.drawLine(w*.18,h*.28,w*.82,h*.28); p.drawLine(w*.18,h*.50,w*.82,h*.50); p.drawLine(w*.18,h*.72,w*.82,h*.72)
                p.drawEllipse(QtCore.QRectF(w*.25,h*.20,w*.16,h*.16)); p.drawEllipse(QtCore.QRectF(w*.58,h*.42,w*.16,h*.16))
            elif shape == 4:
                p.drawLine(w*.5,h*.12,w*.5,h*.88); p.drawLine(w*.28,h*.34,w*.5,h*.12); p.drawLine(w*.72,h*.34,w*.5,h*.12)
            elif shape == 5:
                pts=[QtCore.QPointF(w*.5,h*.12),QtCore.QPointF(w*.82,h*.5),QtCore.QPointF(w*.5,h*.88),QtCore.QPointF(w*.18,h*.5),QtCore.QPointF(w*.5,h*.12)]
                for a,b in zip(pts,pts[1:]): p.drawLine(a,b)
            elif shape == 6:
                p.drawArc(QtCore.QRectF(w*.18,h*.18,w*.64,h*.64), 30*16, 285*16); p.drawLine(w*.70,h*.20,w*.82,h*.42)
            elif shape == 7:
                p.drawLine(w*.20,h*.80,w*.80,h*.20); p.drawLine(w*.20,h*.20,w*.80,h*.80)
            elif shape == 8:
                p.drawEllipse(QtCore.QRectF(w*.18,h*.18,w*.24,h*.24)); p.drawEllipse(QtCore.QRectF(w*.58,h*.18,w*.24,h*.24)); p.drawEllipse(QtCore.QRectF(w*.38,h*.58,w*.24,h*.24)); p.drawLine(w*.42,h*.30,w*.58,h*.30); p.drawLine(w*.50,h*.42,w*.50,h*.58)
            elif shape == 9:
                path=QtGui.QPainterPath(); path.moveTo(w*.16,h*.70); path.cubicTo(w*.30,h*.18,w*.70,h*.18,w*.84,h*.70); p.drawPath(path)
            elif shape == 10:
                p.drawRoundedRect(QtCore.QRectF(w*.18,h*.25,w*.64,h*.5), 3, 3); p.drawLine(w*.32,h*.25,w*.32,h*.75); p.drawLine(w*.68,h*.25,w*.68,h*.75)
            else:
                p.drawLine(w*.18,h*.50,w*.82,h*.50); p.drawLine(w*.50,h*.18,w*.50,h*.82); p.drawEllipse(QtCore.QRectF(w*.38,h*.38,w*.24,h*.24))
        p.end()


class SvgIconWidget(QtWidgets.QWidget):
    def __init__(self, svg_name="", color="#36d6ff", size=18, parent=None):
        super(SvgIconWidget, self).__init__(parent)
        self.svg_name = normalize_icon_name(svg_name)
        self.color = QtGui.QColor(color or "#36d6ff")
        self.setFixedSize(size, size)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

    def set_svg(self, svg_name, color=None):
        self.svg_name = normalize_icon_name(svg_name)
        if color is not None:
            self.color = QtGui.QColor(color or "#36d6ff")
        self.update()

    def paintEvent(self, event):
        path = resolve_icon_path(self.svg_name)
        if not path:
            return
        renderer = QtSvg.QSvgRenderer(path.as_posix())
        if not renderer.isValid():
            return
        pm = QtGui.QPixmap(self.width(), self.height())
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        renderer.render(p, QtCore.QRectF(0, 0, self.width(), self.height()))
        p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        p.fillRect(pm.rect(), self.color)
        p.end()
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, pm)
        painter.end()

class ToolButton(QtWidgets.QFrame):
    clicked=QtCore.Signal(dict)
    dragStarted=QtCore.Signal(object, object)
    def __init__(self,item,color="#36d6ff",compact=False,tight=False,parent_ui=None,parent=None):
        super(ToolButton,self).__init__(parent)
        self.item=item
        self.parent_ui=parent_ui
        self.compact=compact
        self.tight=tight
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip(_clean_tooltip((item.get("label", "Tool") + "\n\n" + item.get("tooltip", "")).strip()))
        self.setObjectName("ToolButton")
        self._press_pos = None
        self._drag_started = False
        self._overlay_label = None
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        ui_scale = self.parent_ui.ui_scale_value if self.parent_ui else (lambda *_: 1.0)
        text_scale = ui_scale("btn_text")
        icon_scale = ui_scale("btn_icon")
        short_text_scale = ui_scale("btn_short")
        lay=QtWidgets.QHBoxLayout(self)
        if compact:
            lay.setContentsMargins(0,0,0,0)
            lay.setSpacing(0)
            icon_size = max(8, int(round((20 if tight else 24) * icon_scale)))
            icon = SvgIconWidget(item.get("icon_svg", ""), item_color(item), icon_size) if item.get("icon_svg") else VectorIcon(item.get("label","tool"), item_color(item), icon_size)
            lay.addStretch(1)
            lay.addWidget(icon,0,QtCore.Qt.AlignCenter)
            lay.addStretch(1)
            self.setFixedSize(48,42) if tight else self.setFixedSize(56,48)
            self.setStyleSheet("QFrame#ToolButton{background:#444444;border:1px solid #565656;border-radius:7px;} QFrame#ToolButton:hover{background:#505050;border-color:#6a6a6a;} QLabel{background:transparent;border:0px;}")
            short_name = (item.get("short_name") or "").strip()
            if short_name:
                short_px = max(8, int(round(9 * short_text_scale)))
                self._overlay_label = QtWidgets.QLabel(short_name, self)
                self._overlay_label.setObjectName("ToolShortNameOverlay")
                self._overlay_label.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom)
                self._overlay_label.setWordWrap(False)
                self._overlay_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
                self._overlay_label.setStyleSheet(
                    "QLabel#ToolShortNameOverlay{"
                    "color:#ffffff;"
                    "font-weight:700;"
                    "font-size:%dpx;"
                    "padding:0px 1px;"
                    "background-color:rgba(0, 0, 0, 90);"
                    "border-radius:4px;"
                    "}" % short_px
                )
                self._overlay_label.raise_()
        else:
            if self.tight:
                lay.setContentsMargins(7,5,7,5)
                lay.setSpacing(6)
                icon_size = max(8, int(round(16 * icon_scale)))
                min_height = 30
            else:
                lay.setContentsMargins(10,7,10,7)
                lay.setSpacing(8)
                icon_size = max(8, int(round(18 * icon_scale)))
                min_height = 34
            lay.addWidget(SvgIconWidget(item.get("icon_svg", ""), item_color(item), icon_size) if item.get("icon_svg") else VectorIcon(item.get("label","tool"), item_color(item), icon_size))
            lab=QtWidgets.QLabel(item.get("label","Tool"))
            lab.setObjectName("ToolLabel")
            lab.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
            text_px = max(7, int(round(12 * text_scale)))
            lab.setStyleSheet("QLabel#ToolLabel{background:transparent;color:%s;font-weight:600;font-size:%dpx;border:0px;}"%(TEXT, text_px))
            lab.setWordWrap(False)
            lay.addWidget(lab,1)
            self.setMinimumHeight(min_height)
            self.setStyleSheet("QFrame#ToolButton{background:#444444;border:1px solid #565656;border-radius:7px;} QFrame#ToolButton:hover{background:#505050;border-color:#6a6a6a;} QFrame#ToolButton QLabel{background:transparent;}")

    def resizeEvent(self, event):
        super(ToolButton, self).resizeEvent(event)
        if self._overlay_label is not None:
            inset = 3
            bottom_inset = 3
            label_h = max(10, self._overlay_label.sizeHint().height())
            self._overlay_label.setGeometry(
                inset,
                max(inset, self.height() - label_h - bottom_inset),
                max(0, self.width() - (inset * 2)),
                label_h
            )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._press_pos = event_global_pos(event)
            self._drag_started = False
        super(ToolButton, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press_pos and not self._drag_started:
            gp = event_global_pos(event)
            if (gp - self._press_pos).manhattanLength() > 6:
                self._drag_started = True
                self.dragStarted.emit(self, gp)
                return
        super(ToolButton, self).mouseMoveEvent(event)

    def clone_preview(self):
        clone = ToolButton(self.item, compact=self.compact, tight=self.tight, parent_ui=self.parent_ui)
        clone.setObjectName("dragPreview")
        clone.setStyleSheet("QFrame#dragPreview{background:#4f4f4f;border:1px solid #777777;border-radius:7px;}")
        clone.resize(self.size())
        clone.setFixedSize(self.size())
        return clone

    def mouseReleaseEvent(self,e):
        if e.button()==QtCore.Qt.LeftButton:
            self.clicked.emit(self.item)
        elif e.button()==QtCore.Qt.RightButton and getattr(self.parent_ui, "open_script_context_menu", None):
            self.parent_ui.open_script_context_menu(self.item, self.mapToGlobal(e.pos()))
            e.accept()
            return
        self._press_pos = None
        self._drag_started = False
        super(ToolButton,self).mouseReleaseEvent(e)


class Placeholder(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super(Placeholder, self).__init__(parent)
        self.setObjectName("placeholder")
        self.setMinimumHeight(30)

class VerticalTextLabel(QtWidgets.QLabel):
    """Auto-sized rotated text label used only for closed horizontal categories.

    The text is drawn vertically and its font size is reduced automatically so
    long category names such as SCULPTING never get cropped when the shelf height
    is small.
    """
    def __init__(self, text="", color=TEXT, scale=1.0, parent=None):
        super(VerticalTextLabel, self).__init__(text, parent)
        self._color = QtGui.QColor(color)
        self._scale = max(0.25, float(scale))
        self.setMinimumWidth(20)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

    def sizeHint(self):
        # Width is the real horizontal footprint of the collapsed tab.
        # Height is flexible and provided by the surrounding shelf row.
        return QtCore.QSize(22, 92)

    def _fitted_font(self):
        text = self.text() or ""
        font = self.font()
        font.setBold(True)

        # After rotation, the available text length is the widget height,
        # and the available text thickness is the widget width.
        max_text_length = max(10, self.height() - 10)
        max_text_thickness = max(8, self.width() - 3)

        # Pixel sizes are more predictable inside Maya than point sizes.
        for px in range(int(round(13 * self._scale)), int(round(6 * self._scale)), -1):
            font.setPixelSize(max(6, px))
            fm = QtGui.QFontMetrics(font)
            text_w = fm.horizontalAdvance(text) if hasattr(fm, "horizontalAdvance") else fm.width(text)
            text_h = fm.height()
            if text_w <= max_text_length and text_h <= max_text_thickness:
                return font

        font.setPixelSize(max(6, int(round(7 * self._scale))))
        return font

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.setPen(self._color)
        painter.setFont(self._fitted_font())

        painter.translate(0, self.height())
        painter.rotate(-90)
        rect = QtCore.QRect(0, 0, self.height(), self.width())
        painter.drawText(rect, QtCore.Qt.AlignCenter, self.text())
        painter.end()

def _elk_debug_rect(widget):
    if widget is None:
        return "None"
    try:
        g = widget.geometry()
        return "{}x{}@{},{}".format(g.width(), g.height(), g.x(), g.y())
    except Exception:
        return "<unavailable>"


def _elk_enum_debug_name(value):
    if value is None:
        return "None"
    try:
        return str(int(value))
    except Exception:
        pass
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        try:
            return str(int(enum_value))
        except Exception:
            return str(enum_value)
    return str(value)


def _elk_policy_name(policy):
    names = {
        QtWidgets.QSizePolicy.Fixed: "Fixed",
        QtWidgets.QSizePolicy.Minimum: "Minimum",
        QtWidgets.QSizePolicy.Maximum: "Maximum",
        QtWidgets.QSizePolicy.Preferred: "Preferred",
        QtWidgets.QSizePolicy.Expanding: "Expanding",
        QtWidgets.QSizePolicy.MinimumExpanding: "MinimumExpanding",
        QtWidgets.QSizePolicy.Ignored: "Ignored",
    }
    return names.get(policy, _elk_enum_debug_name(policy))


def _elk_scroll_policy_name(policy):
    names = {
        QtCore.Qt.ScrollBarAsNeeded: "AsNeeded",
        QtCore.Qt.ScrollBarAlwaysOff: "AlwaysOff",
        QtCore.Qt.ScrollBarAlwaysOn: "AlwaysOn",
    }
    return names.get(policy, _elk_enum_debug_name(policy))


class Category(QtWidgets.QFrame):
    def __init__(self,name,items,parent_ui,parent=None):
        super(Category,self).__init__(parent)
        self.name=name; self.items=items; self.parent_ui=parent_ui
        self.expanded = name not in getattr(parent_ui, "collapsed_categories", set())
        self.slug = _display_to_slug(name)
        cat_meta = _load_category_meta()
        self.icon_svg = normalize_icon_name((cat_meta.get("icons") or {}).get(self.slug, ""))
        self.icon_color = (cat_meta.get("icon_colors") or {}).get(self.slug, "")
        self.color = self.icon_color or "#36d6ff"
        self._vertical_min_valid_height = 20
        self._last_valid_vertical_body_height = None
        self._last_valid_vertical_category_height = None
        self.setObjectName("Category")
        self.setProperty("dragOver", False)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.build()

    def mousePressEvent(self, event):
        if (
            self.parent_ui.is_horizontal_mode()
            and self.expanded
            and event.button() == QtCore.Qt.LeftButton
            and event.pos().x() >= (self.width() - 8)
        ):
            self._resize_drag_active = True
            self._resize_drag_start_global_x = event_global_pos(event).x()
            self._resize_drag_start_width = self.width()
            event.accept()
            return
        super(Category, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self.parent_ui.is_horizontal_mode()
            and self.expanded
            and not getattr(self, "_resize_drag_active", False)
        ):
            edge_hover = event.pos().x() >= (self.width() - 8)
            self.setCursor(QtCore.Qt.SizeHorCursor if edge_hover else QtCore.Qt.ArrowCursor)
        if getattr(self, "_resize_drag_active", False):
            delta = event_global_pos(event).x() - getattr(self, "_resize_drag_start_global_x", 0)
            new_w = max(110, self._resize_drag_start_width + delta)
            self.parent_ui.set_user_horizontal_width(self.name, new_w)
            self.parent_ui.reflow()
            event.accept()
            return
        super(Category, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if getattr(self, "_resize_drag_active", False) and event.button() == QtCore.Qt.LeftButton:
            self._resize_drag_active = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            event.accept()
            return
        super(Category, self).mouseReleaseEvent(event)

    def build(self):
        self.outer=QtWidgets.QVBoxLayout(self); self.outer.setContentsMargins(0,0,0,0); self.outer.setSpacing(5)
        self.header=QtWidgets.QFrame(); self.header.setObjectName("CategoryHeader"); self.header.setCursor(QtCore.Qt.PointingHandCursor)
        h=QtWidgets.QHBoxLayout(self.header); h.setContentsMargins(10,8,10,8); h.setSpacing(8)
        self.header_icon = SvgIconWidget(self.icon_svg, self.icon_color or self.color, 16)
        h.addWidget(self.header_icon)
        self.title=QtWidgets.QLabel(self.name.upper()); h.addWidget(self.title,1)
        self.count_label=QtWidgets.QLabel(str(len(self.items))); h.addWidget(self.count_label)
        self.arrow=QtWidgets.QLabel("⌄"); self.arrow.setStyleSheet("background:transparent;color:%s;font-size:13px;border:0px;"%MUTED); h.addWidget(self.arrow)
        self.header.mouseReleaseEvent=self.toggle_event; self.outer.addWidget(self.header)

        # Compact vertical header used only when a category is collapsed in horizontal shelf mode.
        # It takes the full available height, but only a very small width.
        self.collapsed_header=QtWidgets.QFrame(); self.collapsed_header.setObjectName("CollapsedCategoryHeader"); self.collapsed_header.setCursor(QtCore.Qt.PointingHandCursor)
        ch=QtWidgets.QVBoxLayout(self.collapsed_header); ch.setContentsMargins(5,5,5,5); ch.setSpacing(3)
        self.collapsed_icon = SvgIconWidget(self.icon_svg, self.icon_color or self.color, 17)
        ch.addWidget(self.collapsed_icon,0,QtCore.Qt.AlignHCenter)
        self.collapsed_title=VerticalTextLabel(self.name.upper(), TEXT, scale=1.0)
        ch.addWidget(self.collapsed_title,1,QtCore.Qt.AlignHCenter)
        self.collapsed_arrow=QtWidgets.QLabel("⌄"); self.collapsed_arrow.setAlignment(QtCore.Qt.AlignCenter); self.collapsed_arrow.setStyleSheet("background:transparent;color:%s;font-size:12px;border:0px;"%MUTED)
        ch.addWidget(self.collapsed_arrow,0,QtCore.Qt.AlignHCenter)
        self.collapsed_header.mouseReleaseEvent=self.toggle_event; self.outer.addWidget(self.collapsed_header)

        self.body_scroll = ELKCategoryScrollArea(parent_category=self)
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.body_scroll.setStyleSheet("QScrollArea{background:transparent;border:0px;} QScrollBar:vertical{background:#2a2a2a;width:8px;margin:0;} QScrollBar::handle:vertical{background:#565656;border-radius:4px;min-height:22px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;} QScrollBar:horizontal{background:#2a2a2a;height:8px;margin:0;} QScrollBar::handle:horizontal{background:#565656;border-radius:4px;min-width:22px;} QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0px;}")
        self.body = QtWidgets.QWidget(); self.body.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.grid = QtWidgets.QGridLayout(self.body); self.grid.setContentsMargins(10,0,10,10); self.grid.setSpacing(7)
        self.body_scroll.setWidget(self.body)
        self.outer.addWidget(self.body_scroll, 1)
        self.setStyleSheet("QFrame#Category{background:#373737;border:1px solid #565656;border-radius:9px;} QFrame#Category[dragOver=\"true\"]{border:1px solid #ff9f2e;} QFrame#placeholder{background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.16);border-radius:6px;} QFrame#CategoryHeader{background:transparent;border:0px;} QFrame#CollapsedCategoryHeader{background:transparent;border:0px;} QLabel{background:transparent;}")
        self.reflow()

    def _apply_header_scale(self):
        icon_scale = self.parent_ui.ui_scale_value("cat_icon")
        text_scale = self.parent_ui.ui_scale_value("cat_text")
        self.header_icon.setFixedSize(max(8, int(round(16 * icon_scale))), max(8, int(round(16 * icon_scale))))
        self.collapsed_icon.setFixedSize(max(8, int(round(17 * icon_scale))), max(8, int(round(17 * icon_scale))))
        self.title.setStyleSheet("background:transparent;color:%s;font-weight:800;font-size:%dpx;border:0px;"%(TEXT, max(7, int(round(12 * text_scale)))))
        self.count_label.setStyleSheet("background:transparent;color:%s;font-size:%dpx;border:0px;"%(MUTED, max(7, int(round(11 * text_scale)))))
        self.collapsed_title._scale = max(0.25, float(text_scale))
        self.collapsed_title.update()

    def toggle_event(self,event):
        self.expanded=not self.expanded
        if self.expanded:
            self.parent_ui.collapsed_categories.discard(self.name)
        else:
            self.parent_ui.collapsed_categories.add(self.name)
        self.body_scroll.setVisible(self.expanded)
        self.arrow.setText("⌄" if self.expanded else "›")
        if hasattr(self, "collapsed_arrow"):
            self.collapsed_arrow.setText("⌄" if not self.expanded else "›")
        QtCore.QTimer.singleShot(0, self.parent_ui.reflow)

    def _update_vertical_body_height(self):
        if self.parent_ui.is_horizontal_mode() or not self.expanded:
            return
        self.grid.activate()
        body_layout = self.body.layout()
        if body_layout:
            body_layout.activate()
        self.body.adjustSize()

        calc_body_h = max(self.grid.sizeHint().height(), self.body.sizeHint().height())
        min_valid = self._vertical_min_valid_height
        cached_body_h = self._last_valid_vertical_body_height

        if calc_body_h > min_valid:
            body_h = calc_body_h
            self._last_valid_vertical_body_height = body_h
        elif cached_body_h is not None:
            body_h = cached_body_h
            if getattr(self.parent_ui, "layout_debug_logs_enabled", False):
                print("[ELK_LAYOUT_WARNING] ignored invalid vertical body height={}, using cached height={}".format(calc_body_h, cached_body_h))
        else:
            body_h = max(min_valid, calc_body_h)
            self._last_valid_vertical_body_height = body_h

        self.body_scroll.setMinimumHeight(body_h)
        self.body_scroll.setFixedHeight(body_h)

        header_h = self.header.sizeHint().height() if hasattr(self, "header") and self.header is not None else 0
        margins = self.outer.contentsMargins() if hasattr(self, "outer") and self.outer is not None else QtCore.QMargins(0, 0, 0, 0)
        spacing = self.outer.spacing() if hasattr(self, "outer") and self.outer is not None else 0
        calc_category_h = body_h + header_h + margins.top() + margins.bottom() + max(0, spacing)
        cached_cat_h = self._last_valid_vertical_category_height
        if calc_category_h > min_valid:
            cat_h = calc_category_h
            self._last_valid_vertical_category_height = cat_h
        elif cached_cat_h is not None:
            cat_h = cached_cat_h
        else:
            cat_h = max(min_valid, calc_category_h)
            self._last_valid_vertical_category_height = cat_h
        self.setMinimumHeight(cat_h)

    def reflow(self):
        self._apply_header_scale()
        while self.grid.count():
            it=self.grid.takeAt(0); w=it.widget(); w.deleteLater() if w else None

        horizontal = self.parent_ui.is_horizontal_mode()
        width=max(1,self.parent_ui.available_width())

        is_tight = width < 540

        if horizontal:
            # Shelf mode: opened categories receive the available room.
            # Collapsed categories become a very narrow vertical tab.
            if not self.expanded:
                cat_w = self.parent_ui.collapsed_category_width(self.name)
                self.body_scroll.setVisible(False)
                self.header.setVisible(False)
                self.collapsed_header.setVisible(True)
                self.setMinimumWidth(cat_w)
                self.setMaximumWidth(cat_w)
                self.setMinimumHeight(0)
                self.setMaximumHeight(16777215)
                self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
            else:
                cat_w = int(self.parent_ui.horizontal_category_width(self.name))
                self.body_scroll.setVisible(True)
                self.header.setVisible(True)
                self.collapsed_header.setVisible(False)
                self.setMinimumWidth(cat_w)
                self.setMaximumWidth(cat_w)
                self.setMaximumHeight(16777215)
                self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
            hpad = 6 if is_tight else 10
            bpad = 6 if is_tight else 10
            self.grid.setContentsMargins(hpad, 0, hpad, bpad)
            self.grid.setSpacing(4 if is_tight else 6)
            cols = max(1, len(self.items))
            self.grid.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
            self.body_scroll.setMinimumHeight(0)
            self.body_scroll.setMaximumHeight(16777215)
            self.body_scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.body_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.body_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        else:
            self.body_scroll.setVisible(self.expanded)
            self.header.setVisible(True)
            self.collapsed_header.setVisible(False)
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            if self._last_valid_vertical_category_height is not None:
                self.setMinimumHeight(self._last_valid_vertical_category_height)
            else:
                self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            hpad = 6 if width < 500 else 10
            bpad = 6 if width < 500 else 10
            self.grid.setContentsMargins(hpad, 0, hpad, bpad)
            self.grid.setSpacing(5 if width < 500 else 7)
            cols=1 if self.parent_ui.view_mode=="list" or width<430 else max(2,min(6,int(width/205)))
            self.grid.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
            self.body_scroll.setMinimumHeight(0)
            self.body_scroll.setMaximumHeight(16777215)
            self.body_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.body_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.body_scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.count_label.setVisible(not horizontal or self.expanded)
        self.title.setVisible(True)

        if horizontal and not self.expanded:
            return

        for i,item in enumerate(self.items):
            btn=ToolButton(item,self.color,compact=horizontal,tight=is_tight,parent_ui=self.parent_ui); btn.clicked.connect(run_item); btn.dragStarted.connect(self.parent_ui.start_drag); self.grid.addWidget(btn,i//cols,i%cols)

        if not horizontal and self.expanded:
            self._update_vertical_body_height()
            QtCore.QTimer.singleShot(0, self._update_vertical_body_height)
        elif horizontal:
            self.body_scroll.setMinimumHeight(0)
            self.body_scroll.setMaximumHeight(16777215)

    def layout_items(self):
        result=[]
        for i in range(self.grid.count()):
            w=self.grid.itemAt(i).widget()
            if w: result.append(w)
        return result

    def remove_widget_from_layout(self, widget):
        self.grid.removeWidget(widget)

    def insert_widget_at(self, index, widget):
        items=[w for w in self.layout_items() if w is not widget]
        index=max(0,min(index,len(items)))
        items.insert(index,widget)
        cols=max(1,len(items)) if self.parent_ui.is_horizontal_mode() else (1 if self.parent_ui.view_mode=="list" or self.parent_ui.available_width()<430 else max(2,min(6,int(self.parent_ui.available_width()/205))))
        for i,w in enumerate(items):
            self.grid.addWidget(w,i//cols,i%cols)

    def set_drag_over(self, state):
        self.setProperty("dragOver", bool(state))
        self.style().unpolish(self); self.style().polish(self); self.update()

class ELKMinimalUI(QtWidgets.QWidget):
    def __init__(self,parent=None, instance_name=None):
        super(ELKMinimalUI,self).__init__(parent)
        self.view_mode="grid"
        self.layout_mode=None
        self.collapsed_categories=set()
        self.category_widgets=[]
        self.search=""
        self.max_height_px = self._load_max_height_px()
        self.ui_scale_settings = self._load_ui_scale_settings()
        self.layout_debug_logs_enabled = self._load_layout_debug_logs_enabled()
        self.user_horizontal_widths = self._load_user_horizontal_widths()
        self.drag_state = None
        self.last_reorder_time = 0
        self.candidate_key = None
        self.candidate_frames = 0
        self.instance_name = instance_name or WINDOW_NAME
        self.setObjectName(self.instance_name)
        self._layout_debug_resize_timer = QtCore.QTimer(self)
        self._layout_debug_resize_timer.setSingleShot(True)
        self._layout_debug_resize_timer.timeout.connect(lambda: self.log_layout_state("resize_debounced"))
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.build()
        self._apply_max_height_limit()
        self.refresh()
        QtCore.QTimer.singleShot(0, lambda: self.log_layout_state("ui_open"))
        QtCore.QTimer.singleShot(60, lambda: self.log_layout_state("first_build_complete"))


    def categories(self):
        return list(getattr(self, "category_widgets", []))

    def find_category_for_widget(self, widget):
        for c in self.categories():
            if widget in c.layout_items():
                return c
        return None

    def category_under_global_pos(self, global_pos):
        for c in self.categories():
            rect = QtCore.QRect(c.mapToGlobal(QtCore.QPoint(0, 0)), c.size())
            if rect.contains(global_pos):
                return c
        return None

    def start_drag(self, source_button, global_pos):
        if self.drag_state or self.is_horizontal_mode():
            return
        source_category = self.find_category_for_widget(source_button)
        if not source_category:
            return
        source_index = source_category.layout_items().index(source_button)
        source_rect_global = QtCore.QRect(source_button.mapToGlobal(QtCore.QPoint(0,0)), source_button.size())
        placeholder = Placeholder(); placeholder.setFixedHeight(source_button.height())
        source_category.remove_widget_from_layout(source_button); source_button.hide(); source_button.setParent(None)
        source_category.insert_widget_at(source_index, placeholder); placeholder.show()
        preview = source_button.clone_preview(); preview.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint); preview.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True); preview.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        preview.move(source_rect_global.topLeft()); preview.show(); preview.raise_()
        self.drag_state={"source":source_button,"placeholder":placeholder,"preview":preview,"offset":global_pos-source_rect_global.topLeft()}
        self.grabMouse(); self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        if self.drag_state:
            self.update_drag(event_global_pos(event)); return
        super(ELKMinimalUI, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_state and event.button()==QtCore.Qt.LeftButton:
            self.end_drag(); return
        super(ELKMinimalUI, self).mouseReleaseEvent(event)

    def update_drag(self, global_pos):
        st=self.drag_state; st["preview"].move(global_pos-st["offset"])
        for c in self.categories(): c.set_drag_over(False)
        target=self.category_under_global_pos(global_pos)
        if not target: return
        target.set_drag_over(True)
        items=[w for w in target.layout_items() if isinstance(w, ToolButton)]
        idx=len(items)
        for i,w in enumerate(items):
            r=QtCore.QRect(w.mapToGlobal(QtCore.QPoint(0,0)), w.size())
            if global_pos.y()<r.center().y() or (abs(global_pos.y()-r.center().y())<r.height() and global_pos.x()<r.left()+r.width()*HYSTERESIS_RATIO):
                idx=i; break
        key=f"{self.categories().index(target)}:{idx}"
        if self.candidate_key!=key: self.candidate_key=key; self.candidate_frames=1; return
        self.candidate_frames += 1
        if self.candidate_frames < REORDER_CONFIRM_FRAMES: return
        now=QtCore.QDateTime.currentMSecsSinceEpoch()
        if now-self.last_reorder_time < REORDER_COOLDOWN_MS: return
        self.last_reorder_time=now
        self.move_placeholder(target, idx)

    def move_placeholder(self, target_category, target_index):
        ph=self.drag_state["placeholder"]; cur=self.find_category_for_widget(ph)
        if cur: cur.remove_widget_from_layout(ph)
        target_category.insert_widget_at(target_index, ph); ph.show()

    def end_drag(self):
        st=self.drag_state; source=st["source"]; preview=st["preview"]; placeholder=st["placeholder"]
        target=self.find_category_for_widget(placeholder)
        if not target:
            preview.close(); source.show(); self.drag_state=None; self.releaseMouse(); return
        idx=target.layout_items().index(placeholder)
        target.remove_widget_from_layout(placeholder); placeholder.deleteLater()
        target.insert_widget_at(idx, source); source.show(); source.raise_()
        source.item["category"]=target.name
        preview.close(); preview.deleteLater()
        for c in self.categories(): c.set_drag_over(False)
        self.drag_state=None
        try: self.releaseMouse()
        except Exception: pass
        self.save_current_order()

    def save_current_order(self):
        order=[]; category_by_file={}
        for c in self.categories():
            for w in c.layout_items():
                if isinstance(w, ToolButton):
                    key=w.item.get("file_key")
                    if key: order.append(key); category_by_file[key]=c.name
        _save_items_meta({"order":order, "category_by_file":category_by_file})
        self.shelf_items = load_shelf_items()
        _broadcast_refresh(self)

    def _load_max_height_px(self):
        if cmds.optionVar(exists=OPTIONVAR_MAX_HEIGHT):
            try:
                return max(0, int(cmds.optionVar(q=OPTIONVAR_MAX_HEIGHT)))
            except Exception:
                return 0
        return 0

    def _load_percent_option(self, key, default=100):
        if cmds.optionVar(exists=key):
            try:
                return max(10, min(300, int(cmds.optionVar(q=key))))
            except Exception:
                pass
        return default

    def _load_ui_scale_settings(self):
        return {
            "btn_text_h": self._load_percent_option(OPTIONVAR_UI_SCALE_BTN_TEXT_H),
            "btn_text_v": self._load_percent_option(OPTIONVAR_UI_SCALE_BTN_TEXT_V),
            "btn_icon_h": self._load_percent_option(OPTIONVAR_UI_SCALE_BTN_ICON_H),
            "btn_icon_v": self._load_percent_option(OPTIONVAR_UI_SCALE_BTN_ICON_V),
            "btn_short_h": self._load_percent_option(OPTIONVAR_UI_SCALE_BTN_SHORT_H, 150),
            "btn_short_v": self._load_percent_option(OPTIONVAR_UI_SCALE_BTN_SHORT_V, 100),
            "cat_text_h": self._load_percent_option(OPTIONVAR_UI_SCALE_CAT_TEXT_H),
            "cat_text_v": self._load_percent_option(OPTIONVAR_UI_SCALE_CAT_TEXT_V),
            "cat_icon_h": self._load_percent_option(OPTIONVAR_UI_SCALE_CAT_ICON_H),
            "cat_icon_v": self._load_percent_option(OPTIONVAR_UI_SCALE_CAT_ICON_V),
        }

    def _load_layout_debug_logs_enabled(self):
        if cmds.optionVar(exists=OPTIONVAR_LAYOUT_DEBUG_LOGS):
            try:
                return bool(int(cmds.optionVar(q=OPTIONVAR_LAYOUT_DEBUG_LOGS)))
            except Exception:
                return False
        return False

    def _load_user_horizontal_widths(self):
        if cmds.optionVar(exists=OPTIONVAR_HCAT_WIDTHS):
            try:
                raw = cmds.optionVar(q=OPTIONVAR_HCAT_WIDTHS)
                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        return {str(k): int(v) for k, v in parsed.items() if str(v).strip().lstrip("-").isdigit()}
            except Exception:
                pass
        return {}

    def _save_user_horizontal_widths(self):
        try:
            cmds.optionVar(sv=(OPTIONVAR_HCAT_WIDTHS, json.dumps(self.user_horizontal_widths)))
        except Exception:
            pass

    def set_user_horizontal_width(self, category_name, width):
        if not category_name:
            return
        w = max(110, min(1200, int(width)))
        self.user_horizontal_widths[str(category_name)] = w
        self._save_user_horizontal_widths()

    def ui_scale_value(self, section):
        suffix = "h" if self.is_horizontal_mode() else "v"
        key = f"{section}_{suffix}"
        return max(0.1, float(self.ui_scale_settings.get(key, 100)) / 100.0)

    def _apply_max_height_limit(self):
        max_h = self.max_height_px if self.max_height_px > 0 else 16777215
        self.setMinimumWidth(0)
        self.setMinimumHeight(0)
        self.setMaximumHeight(max_h)

        # Apply the cap only to the immediate ELK host widget.
        # Do NOT touch self.window() here because in Maya dock mode it can
        # resolve to a higher-level app window and unintentionally clamp Maya.
        host = self.parentWidget()
        if host is not None:
            host.setMinimumWidth(0)
            host.setMinimumHeight(0)
            host.setMaximumHeight(max_h)

        # When docked in a Maya workspaceControl, also clamp the control itself.
        # Without this, Maya can keep stretching the dock area vertically even if
        # the Qt widget has a lower max height.
        if cmds.workspaceControl(WORKSPACE_NAME, exists=True):
            try:
                cmds.workspaceControl(
                    WORKSPACE_NAME,
                    edit=True,
                    minimumWidth=0,
                    minimumHeight=0,
                    maximumHeight=max_h
                )
                if self.max_height_px > 0:
                    cmds.workspaceControl(
                        WORKSPACE_NAME,
                        edit=True,
                        heightProperty="preferred",
                        resizeHeight=max_h
                    )
            except Exception:
                pass

    def is_horizontal_mode(self):
        return self.layout_mode == "horizontal"

    def desired_layout_mode(self):
        w = max(1, self.width())
        h = max(1, self.height())
        return "horizontal" if (w > h and h <= 250) else "vertical"

    def available_width(self):
        if hasattr(self,'scroll'):
            return self.scroll.viewport().width()-28
        return self.width()

    def collapsed_category_width(self, category_name):
        return 54

    def horizontal_category_width(self, category_name):
        """Return a per-category width that fills the available shelf width.

        The width is computed from the number of visible categories and their number
        of tools. If everything can fit, remaining space is distributed so the UI
        always fills the docked shelf instead of stopping after a few hundred pixels.
        """
        widths = getattr(self, "_horizontal_widths", {})
        return widths.get(category_name, 180)

    def compute_horizontal_widths(self):
        """Compute horizontal category widths that always fit the viewport.

        - Small categories keep a compact natural width.
        - Large categories can grow more and scroll internally if capped.
        - The total (categories + spacing + right buttons area) always matches the
          available shelf width so nothing overflows to the right.
        """
        groups = self.grouped_items()
        n = max(1, len(groups))
        reserve = self.horizontal_options_space()
        viewport_w = self.scroll.viewport().width() if hasattr(self, "scroll") else self.width()
        available = max(220, int(max(1, viewport_w) - reserve))
        spacing_total = 8 * max(0, n - 1)

        collapsed_w = self.collapsed_category_width("")
        tight = self.available_width() < 540
        hpad = 6 if tight else 10
        spacing = 4 if tight else 6
        button_w = 48 if tight else 56

        open_groups = [(cat, items) for cat, items in groups if cat not in self.collapsed_categories]
        closed_groups = [(cat, items) for cat, items in groups if cat in self.collapsed_categories]

        widths = {}
        for cat, _ in closed_groups:
            widths[cat] = collapsed_w

        closed_total = len(closed_groups) * collapsed_w
        open_n = len(open_groups)
        open_target = max(0, available - spacing_total - closed_total)

        if open_n <= 0:
            self._horizontal_widths = widths
            return

        naturals = []
        weights = []
        min_open_w = 110
        max_open_w = max(170, int(max(1, viewport_w) * 0.42))

        for _, items in open_groups:
            count = max(1, len(items))
            natural_w = (hpad * 2) + (count * button_w) + (max(0, count - 1) * spacing)
            naturals.append(max(min_open_w, min(max_open_w, natural_w)))
            weights.append(max(1.0, float(count)))

        total_natural = sum(naturals)
        open_widths = list(naturals)

        if total_natural > open_target and open_target > 0:
            # Compress proportionally, but never below minimum.
            factor = float(open_target) / float(total_natural)
            open_widths = [max(min_open_w, int(round(w * factor))) for w in naturals]
        elif total_natural < open_target:
            # Fill remaining room mostly on categories that have many tools.
            extra = open_target - total_natural
            total_weight = sum(weights) or 1.0
            open_widths = [w + int(round(extra * (wt / total_weight))) for w, wt in zip(naturals, weights)]

        # Clamp and force exact fit to avoid right overflow.
        open_widths = [max(min_open_w, min(max_open_w, w)) for w in open_widths]
        delta = open_target - sum(open_widths)
        if open_widths and delta != 0:
            step = 1 if delta > 0 else -1
            i = 0
            guard = 0
            while delta != 0 and guard < 20000:
                idx = i % len(open_widths)
                cand = open_widths[idx] + step
                if min_open_w <= cand <= max_open_w:
                    open_widths[idx] = cand
                    delta -= step
                i += 1
                guard += 1

        for (cat, _), w in zip(open_groups, open_widths):
            widths[cat] = int(w)

        # Apply user-resized widths in horizontal mode and keep total fitting.
        open_names = [cat for cat, _ in open_groups]
        if open_names:
            min_open_w = 110
            max_open_w = max(170, int(max(1, viewport_w) * 0.70))
            locked = {}
            for cat in open_names:
                if cat in self.user_horizontal_widths:
                    locked[cat] = max(min_open_w, min(max_open_w, int(self.user_horizontal_widths[cat])))

            if locked:
                locked_total = sum(locked.values())
                unlocked = [cat for cat in open_names if cat not in locked]
                target_total = max(open_n * min_open_w, open_target)
                remaining = max(0, target_total - locked_total)
                if unlocked:
                    unlocked_default = [widths.get(cat, min_open_w) for cat in unlocked]
                    default_sum = max(1, sum(unlocked_default))
                    adjusted = [max(min_open_w, int(round(remaining * (w / float(default_sum))))) for w in unlocked_default]
                    delta = remaining - sum(adjusted)
                    i = 0
                    while delta != 0 and i < 20000 and adjusted:
                        idx = i % len(adjusted)
                        cand = adjusted[idx] + (1 if delta > 0 else -1)
                        if cand >= min_open_w:
                            adjusted[idx] = cand
                            delta += -1 if delta > 0 else 1
                        i += 1
                    for cat, w in zip(unlocked, adjusted):
                        widths[cat] = int(max(min_open_w, min(max_open_w, w)))
                for cat, w in locked.items():
                    widths[cat] = int(w)

        self._horizontal_widths = widths

    def horizontal_options_space(self):
        return 40 if hasattr(self, "h_options_stack") and self.h_options_stack is not None else 0

    def build(self):
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QWidget#%s{background:%s;font-family:Segoe UI,Arial;}
            QLabel{background:transparent;}
            QLineEdit{background:#373737;color:%s;border:1px solid %s;border-radius:7px;padding:7px 10px;}
            QPushButton{background:#444444;color:%s;border:1px solid #565656;border-radius:7px;padding:7px 10px;font-weight:700;}
            QPushButton:hover{background:#505050;}
            QToolTip{background-color:#444444;color:#eaf2f8;border:1px solid #6a6a6a;border-radius:6px;padding:7px 9px;font-size:11px;}
            QScrollArea{border:none;background:%s;}
            QScrollArea > QWidget > QWidget{background:%s;}
        """%(WINDOW_NAME,BG,TEXT,BORDER,TEXT,BG,BG))

        # Force a readable tooltip palette in Maya/PySide sessions where QToolTip ignores parts of the stylesheet.
        pal = QtGui.QPalette()
        pal.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor("#444444"))
        pal.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor("#eaf2f8"))
        QtWidgets.QToolTip.setPalette(pal)
        QtWidgets.QToolTip.setFont(QtGui.QFont("Segoe UI", 9))

        main=QtWidgets.QVBoxLayout(self); main.setContentsMargins(10,10,10,10); main.setSpacing(8)
        top=QtWidgets.QHBoxLayout(); top.setSpacing(8)
        self.title_label=QtWidgets.QLabel("ELK UI"); self.title_label.setStyleSheet("color:#ffad3b;font-size:15px;font-weight:900;"); top.addWidget(self.title_label)
        self.search_box=QtWidgets.QLineEdit(); self.search_box.setPlaceholderText("Search tools..."); self.search_box.textChanged.connect(self.on_search); top.addWidget(self.search_box,1)
        self.view_btn=QtWidgets.QPushButton("Grid"); self.view_btn.clicked.connect(self.toggle_view); top.addWidget(self.view_btn)
        self.add_btn=QtWidgets.QToolButton(); self.add_btn.setToolTip("Add script"); self.add_btn.clicked.connect(self.open_add_script_dialog); self.add_btn.setFixedSize(32,32); self.add_btn.setIcon(QtGui.QIcon(resolve_icon_path("new-section.svg").as_posix())); self.add_btn.setIconSize(QtCore.QSize(18, 18)); self.add_btn.setStyleSheet("QToolButton{background:#444444;color:#f0f0f0;border:1px solid #565656;border-radius:7px;} QToolButton:hover{background:#505050;}"); top.addWidget(self.add_btn)
        self.options_btn=QtWidgets.QToolButton(); self.options_btn.setToolTip("Options"); self.options_btn.clicked.connect(self.open_options_dialog); self.options_btn.setFixedSize(32,32); self.options_btn.setIcon(QtGui.QIcon(resolve_icon_path("settings.svg").as_posix())); self.options_btn.setIconSize(QtCore.QSize(18, 18)); self.options_btn.setStyleSheet("QToolButton{background:#444444;color:#f0f0f0;border:1px solid #565656;border-radius:7px;} QToolButton:hover{background:#505050;}")
        top.addWidget(self.options_btn)
        main.addLayout(top)

        self.scroll=QtWidgets.QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setMinimumHeight(0)
        self.scroll.setStyleSheet("QScrollArea{background:%s;border:none;} QScrollBar:vertical{background:#2a2a2a;width:10px;margin:0;} QScrollBar::handle:vertical{background:#565656;border-radius:5px;min-height:28px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;} QScrollBar:horizontal{background:#2a2a2a;height:10px;margin:0;} QScrollBar::handle:horizontal{background:#565656;border-radius:5px;min-width:28px;} QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0px;}"%BG)
        self.content=QtWidgets.QWidget(); self.content.setAttribute(QtCore.Qt.WA_StyledBackground, True); self.content.setStyleSheet("background:%s;"%BG)
        self.content_lay=QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.TopToBottom, self.content)
        self.content_lay.setContentsMargins(0,0,0,0); self.content_lay.setSpacing(8)
        self.scroll.setWidget(self.content); main.addWidget(self.scroll,1)
        self.h_options_stack = None
        self.h_options_btn = None
        self.h_search_btn = None
        self.h_add_btn = None
        self.h_search_popup = None
        self.h_search_line = None
        self._keep_search_focus = False
        self.shelf_items = load_shelf_items()

        try:
            ShortcutClass = getattr(QtWidgets, "QShortcut", None) or getattr(QtGui, "QShortcut", None)
            if ShortcutClass:
                sc=ShortcutClass(QtGui.QKeySequence("Ctrl+F"), self); sc.activated.connect(self.focus_search); self._shortcut=sc
        except Exception: pass

    def focus_search(self):
        if self.is_horizontal_mode():
            self.show_horizontal_search(True)
            if self.h_search_line is not None:
                self.h_search_line.setFocus()
                self.h_search_line.selectAll()
        else:
            self.search_box.setFocus()
            self.search_box.selectAll()

    def show_horizontal_search(self, visible):
        if self.h_search_popup is None:
            return
        self.h_search_popup.setVisible(bool(visible))
        if visible:
            self.update_horizontal_search_geometry()

    def toggle_horizontal_search(self):
        if self.h_search_popup is None:
            return
        visible = not self.h_search_popup.isVisible()
        self.show_horizontal_search(visible)
        if visible and self.h_search_line is not None:
            self.h_search_line.setFocus()
            self.h_search_line.selectAll()

    def update_horizontal_search_geometry(self):
        if self.h_search_popup is None:
            return
        scale = 1.15
        base_h = max(30, int(self.height() * 0.14 * scale))
        popup_h = min(44, base_h)
        popup_w = max(165, min(360, int(self.width() * 0.30 * scale)))

        # Keep the floating search anchored to the top-right of the panel,
        # independent from the shelf widgets that are rebuilt during filtering.
        right_margin = 46
        x = max(6, self.width() - popup_w - right_margin)
        y = 6

        # If the search icon exists, align vertically with it for visual continuity.
        if self.h_search_btn is not None:
            btn_pos = self.h_search_btn.mapTo(self, QtCore.QPoint(0, 0))
            y = max(4, btn_pos.y() + int((self.h_search_btn.height() - popup_h) * 0.5))

        global_pos = self.mapToGlobal(QtCore.QPoint(x, y))
        self.h_search_popup.setGeometry(global_pos.x(), global_pos.y(), popup_w, popup_h)

    def apply_layout_mode(self):
        new_mode = self.desired_layout_mode()
        if new_mode == self.layout_mode:
            return False
        self.layout_mode = new_mode
        self.log_layout_state("layout_mode_change:{}".format(new_mode))
        if new_mode == "horizontal":
            self.content_lay.setDirection(QtWidgets.QBoxLayout.LeftToRight)
            self.content_lay.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            # In shelf mode the content must stretch to the full viewport instead of
            # keeping a small fixed natural width. This avoids the broken/empty area
            # visible when the panel is docked horizontally.
            self.scroll.setWidgetResizable(True)
            self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.title_label.setVisible(False)
            self.search_box.setVisible(False)
            self.view_btn.setVisible(False)
            self.options_btn.setVisible(False)
            self.add_btn.setVisible(False)
        else:
            self.content_lay.setDirection(QtWidgets.QBoxLayout.TopToBottom)
            self.content_lay.setAlignment(QtCore.Qt.AlignTop)
            self.scroll.setWidgetResizable(True)
            self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.title_label.setVisible(True)
            self.search_box.setVisible(True)
            self.view_btn.setVisible(True)
            self.options_btn.setVisible(True)
            self.add_btn.setVisible(True)
        return True

    def _category_rows(self):
        meta = _sync_category_meta_from_fs()
        rows = []
        for slug in meta.get('order') or []:
            path = SCRIPTS_ROOT / slug
            if path.is_dir():
                rows.append((slug, (meta.get('names') or {}).get(slug, slug.replace('_', ' ').title()), path))
        return rows

    def _refresh_ui_data(self):
        self.shelf_items = load_shelf_items()
        self.refresh()

    def open_options_dialog(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("ELK Options")
        root = QtWidgets.QVBoxLayout(dlg)

        form = QtWidgets.QFormLayout()
        spin = QtWidgets.QSpinBox(); spin.setRange(0, 4000); spin.setSuffix(" px"); spin.setSpecialValueText("No limit"); spin.setValue(self.max_height_px)
        form.addRow("Max UI height:", spin)
        layout_debug_check = QtWidgets.QCheckBox("Enable Layout Debug Logs")
        layout_debug_check.setChecked(bool(self.layout_debug_logs_enabled))
        form.addRow("", layout_debug_check)
        scale_grp = QtWidgets.QGroupBox("UI scale (%)")
        scale_form = QtWidgets.QFormLayout(scale_grp)
        scale_spins = {}
        labels = [
            ("btn_text_h", "Textes des boutons (Horizontal)"),
            ("btn_text_v", "Textes des boutons (Vertical)"),
            ("btn_icon_h", "Icônes des boutons (Horizontal)"),
            ("btn_icon_v", "Icônes des boutons (Vertical)"),
            ("btn_short_h", "Short name boutons (Horizontal)"),
            ("btn_short_v", "Short name boutons (Vertical)"),
            ("cat_text_h", "Textes des catégories (Horizontal)"),
            ("cat_text_v", "Textes des catégories (Vertical)"),
            ("cat_icon_h", "Icônes des catégories (Horizontal)"),
            ("cat_icon_v", "Icônes des catégories (Vertical)"),
        ]
        for key, label in labels:
            s = QtWidgets.QSpinBox(); s.setRange(10, 300); s.setSuffix("%"); s.setValue(int(self.ui_scale_settings.get(key, 100)))
            scale_spins[key] = s
            scale_form.addRow(label + ":", s)
        root.addLayout(form)
        root.addWidget(scale_grp)

        grp = QtWidgets.QGroupBox("Category Manager")
        gl = QtWidgets.QVBoxLayout(grp)
        cat_list = QtWidgets.QListWidget(); cat_list.setMinimumHeight(180)
        gl.addWidget(cat_list)
        row = QtWidgets.QHBoxLayout()
        for label, fn in (("+ Add", "add"), ("Rename", "ren"), ("Delete", "del"), ("↑", "up"), ("↓", "down")):
            b = QtWidgets.QPushButton(label); b.setProperty("op", fn); row.addWidget(b)
            setattr(self, f"_cat_btn_{fn}", b)
        gl.addLayout(row)
        root.addWidget(grp)
        second_instance_btn = QtWidgets.QPushButton("Open Second Instance")
        second_instance_btn.clicked.connect(lambda: show_second_instance())
        root.addWidget(second_instance_btn)

        def reload_list(select_slug=None):
            cat_list.clear()
            for slug, disp, path in self._category_rows():
                it = QtWidgets.QListWidgetItem(f"{disp}    [{slug}]")
                it.setData(QtCore.Qt.UserRole, slug)
                it.setData(QtCore.Qt.UserRole+1, disp)
                it.setData(QtCore.Qt.UserRole+2, str(path))
                cat_list.addItem(it)
                if select_slug and slug == select_slug:
                    cat_list.setCurrentItem(it)

        def selected_row():
            it = cat_list.currentItem()
            return it.data(QtCore.Qt.UserRole) if it else None

        def _category_editor(initial_name="", initial_icon="", initial_color="#36d6ff"):
            cat_dlg = QtWidgets.QDialog(dlg)
            cat_dlg.setWindowTitle("Configurer la catégorie")
            cat_form = QtWidgets.QFormLayout(cat_dlg)
            name_edit = QtWidgets.QLineEdit(initial_name)
            icon_name = QtWidgets.QLineEdit(normalize_icon_name(initial_icon))
            icon_name.setReadOnly(True)
            icon_color = QtWidgets.QComboBox()
            icon_color.addItems(ICON_COLORS)
            icon_color.setCurrentText(initial_color if initial_color in ICON_COLORS else "#36d6ff")
            color_picker_row = self._build_color_picker_row(icon_color, initial_color)
            icon_preview = QtWidgets.QLabel("")
            icon_preview.setMinimumHeight(24)
            icon_preview.setStyleSheet("color:#b7b7b7;")
            icon_visual = SvgIconWidget(icon_name.text().strip(), icon_color.currentText(), 20)
            icon_btn = QtWidgets.QPushButton("Choisir icône SVG…")

            def _refresh_preview():
                self._set_icon_preview(icon_preview, icon_name.text().strip(), icon_color.currentText())
                icon_visual.setVisible(bool(icon_name.text().strip()))
                icon_visual.set_svg(icon_name.text().strip(), icon_color.currentText())

            def _pick():
                picked = self._pick_svg_icon(icon_name.text().strip(), icon_color.currentText())
                if picked:
                    icon_name.setText(picked[0])
                    icon_color.setCurrentText(picked[1])
                    _refresh_preview()

            icon_btn.clicked.connect(_pick)
            icon_color.currentTextChanged.connect(lambda _v: _refresh_preview())
            _refresh_preview()
            cat_form.addRow("Nom", name_edit)
            cat_form.addRow("Icône SVG", icon_btn)
            cat_form.addRow("Aperçu icône", icon_visual)
            cat_form.addRow("Sélection", icon_preview)
            cat_form.addRow("Couleur", color_picker_row)
            cat_btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            cat_form.addRow(cat_btns)
            cat_btns.accepted.connect(cat_dlg.accept); cat_btns.rejected.connect(cat_dlg.reject)
            if (cat_dlg.exec_() if hasattr(cat_dlg, "exec_") else cat_dlg.exec()):
                return {
                    "name": (name_edit.text() or "").strip(),
                    "icon_svg": normalize_icon_name(icon_name.text().strip()),
                    "icon_color": icon_color.currentText()
                }
            return None

        def add_category():
            edited = _category_editor()
            if not edited: return
            name = edited["name"]
            if len(name) < 2:
                cmds.warning("Invalid category name."); return
            slug = _slugify(name)
            meta = _sync_category_meta_from_fs()
            existing_names = {(v or '').strip().casefold() for v in (meta.get('names') or {}).values()}
            if name.casefold() in existing_names:
                cmds.warning("Category already exists."); return
            slug = slug if slug not in (meta.get('names') or {}) else _unique_fs_path(SCRIPTS_ROOT / slug).name
            (SCRIPTS_ROOT / slug).mkdir(parents=True, exist_ok=True)
            meta['names'][slug] = name
            if slug not in meta['order']: meta['order'].append(slug)
            meta.setdefault('icons', {})[slug] = edited["icon_svg"]
            meta.setdefault('icon_colors', {})[slug] = edited["icon_color"]
            _save_category_meta(meta)
            reload_list(select_slug=slug); self._refresh_ui_data(); _broadcast_refresh(self)

        def rename_category():
            slug = selected_row();
            if not slug: return
            meta = _sync_category_meta_from_fs(); old = meta['names'].get(slug, slug)
            edited = _category_editor(
                initial_name=old,
                initial_icon=(meta.get('icons') or {}).get(slug, ""),
                initial_color=(meta.get('icon_colors') or {}).get(slug, "#36d6ff")
            )
            if not edited: return
            name = edited["name"]
            if not name: return
            existing = {(v or '').strip().casefold(): k for k,v in meta['names'].items()}
            if name.casefold() in existing and existing[name.casefold()] != slug:
                cmds.warning("Category name conflict."); return
            new_slug = _slugify(name)
            if new_slug != slug:
                dst = SCRIPTS_ROOT / new_slug
                if dst.exists():
                    dst = _unique_fs_path(dst)
                (SCRIPTS_ROOT / slug).rename(dst)
                final_slug = dst.name
                meta['names'].pop(slug, None)
                meta['names'][final_slug] = name
                if slug in meta.get('icons', {}):
                    meta.setdefault('icons', {})[final_slug] = meta['icons'].pop(slug)
                if slug in meta.get('icon_colors', {}):
                    meta.setdefault('icon_colors', {})[final_slug] = meta['icon_colors'].pop(slug)
                meta['order'] = [final_slug if x == slug else x for x in meta['order']]
            else:
                final_slug = slug; meta['names'][slug] = name
            meta.setdefault('icons', {})[final_slug] = edited["icon_svg"]
            meta.setdefault('icon_colors', {})[final_slug] = edited["icon_color"]
            _save_category_meta(meta); reload_list(select_slug=final_slug); self._refresh_ui_data(); _broadcast_refresh(self)

        def delete_category():
            slug = selected_row();
            if not slug: return
            path = SCRIPTS_ROOT / slug
            files = [x for x in path.iterdir() if x.suffix.lower() in ('.py','.mel')] if path.exists() else []
            if files:
                items = [d for d in self._category_rows() if d[0] != slug]
                names = [d[1] for d in items]
                choice, ok = QtWidgets.QInputDialog.getItem(dlg, "Category not empty", "Move scripts to:", names, 0, False)
                if not ok: return
                target_slug = items[names.index(choice)][0]
                for f in files: f.rename((SCRIPTS_ROOT / target_slug / f.name))
            else:
                res = QtWidgets.QMessageBox.question(dlg, "Delete category", "Confirm delete this category?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if res != QtWidgets.QMessageBox.Yes: return
            if path.exists(): path.rmdir()
            meta = _sync_category_meta_from_fs(); meta['names'].pop(slug, None); meta.get('icons', {}).pop(slug, None); meta.get('icon_colors', {}).pop(slug, None); meta['order'] = [x for x in meta['order'] if x != slug]; _save_category_meta(meta)
            reload_list(); self._refresh_ui_data(); _broadcast_refresh(self)

        def move(offset):
            slug = selected_row();
            if not slug: return
            meta = _sync_category_meta_from_fs(); order = meta['order']; i = order.index(slug); j=i+offset
            if j<0 or j>=len(order): return
            order[i], order[j] = order[j], order[i]; meta['order']=order; _save_category_meta(meta); reload_list(select_slug=slug); self._refresh_ui_data(); _broadcast_refresh(self)

        reload_list()
        self._cat_btn_add.clicked.connect(add_category); self._cat_btn_ren.clicked.connect(rename_category); self._cat_btn_del.clicked.connect(delete_category)
        self._cat_btn_up.clicked.connect(lambda: move(-1)); self._cat_btn_down.clicked.connect(lambda: move(1))

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        root.addWidget(btns); btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        if dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec():
            self.max_height_px = int(spin.value()); cmds.optionVar(iv=(OPTIONVAR_MAX_HEIGHT, self.max_height_px))
            self.layout_debug_logs_enabled = bool(layout_debug_check.isChecked())
            cmds.optionVar(iv=(OPTIONVAR_LAYOUT_DEBUG_LOGS, 1 if self.layout_debug_logs_enabled else 0))
            optionvar_map = {
                "btn_text_h": OPTIONVAR_UI_SCALE_BTN_TEXT_H,
                "btn_text_v": OPTIONVAR_UI_SCALE_BTN_TEXT_V,
                "btn_icon_h": OPTIONVAR_UI_SCALE_BTN_ICON_H,
                "btn_icon_v": OPTIONVAR_UI_SCALE_BTN_ICON_V,
                "btn_short_h": OPTIONVAR_UI_SCALE_BTN_SHORT_H,
                "btn_short_v": OPTIONVAR_UI_SCALE_BTN_SHORT_V,
                "cat_text_h": OPTIONVAR_UI_SCALE_CAT_TEXT_H,
                "cat_text_v": OPTIONVAR_UI_SCALE_CAT_TEXT_V,
                "cat_icon_h": OPTIONVAR_UI_SCALE_CAT_ICON_H,
                "cat_icon_v": OPTIONVAR_UI_SCALE_CAT_ICON_V,
            }
            for key, opt_name in optionvar_map.items():
                val = int(scale_spins[key].value())
                self.ui_scale_settings[key] = val
                cmds.optionVar(iv=(opt_name, val))
            self._apply_max_height_limit(); self.reflow()

    def open_add_script_dialog(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Add ELK Script")
        lay = QtWidgets.QFormLayout(dlg)
        full_name = QtWidgets.QLineEdit()
        short_name = QtWidgets.QLineEdit()
        category = QtWidgets.QComboBox()
        category.setEditable(True)
        categories = [disp for _, disp, _ in self._category_rows()]
        categories = sorted({c for c in categories if c})
        if "Tools" not in categories:
            categories.insert(0, "Tools")
        category.addItems(categories)
        comp_model = QtCore.QStringListModel(categories, category)
        completer = QtWidgets.QCompleter(comp_model, category)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        category.setCompleter(completer)

        def _filter_category_options(text):
            txt = (text or "").strip().lower()
            filtered = [c for c in categories if txt in c.lower()] if txt else categories
            comp_model.setStringList(filtered if filtered else categories)
            if hasattr(category, "showPopup"):
                category.showPopup()

        category.lineEdit().textEdited.connect(_filter_category_options)

        desc = QtWidgets.QLineEdit()
        source = QtWidgets.QComboBox(); source.addItems(["python", "mel"])
        icon_name = QtWidgets.QLineEdit()
        icon_name.setReadOnly(True)
        icon_preview = QtWidgets.QLabel("Aucune")
        icon_preview.setMinimumHeight(22)
        icon_color = QtWidgets.QComboBox(); icon_color.addItems(ICON_COLORS)
        icon_color.setCurrentText("#36d6ff")
        icon_visual = SvgIconWidget("", icon_color.currentText(), 20)
        icon_visual.setVisible(False)
        color_picker_row = self._build_color_picker_row(icon_color, "#36d6ff")
        icon_btn = QtWidgets.QPushButton("Choisir icône…")

        def pick_icon():
            picked = self._pick_svg_icon(icon_name.text().strip(), icon_color.currentText())
            if not picked:
                return
            icon_name.setText(picked[0]); icon_color.setCurrentText(picked[1]); self._set_icon_preview(icon_preview, icon_name.text(), icon_color.currentText())
            icon_visual.setVisible(True); icon_visual.set_svg(icon_name.text(), icon_color.currentText())

        icon_btn.clicked.connect(pick_icon)
        icon_color.currentTextChanged.connect(lambda _v: (self._set_icon_preview(icon_preview, icon_name.text(), icon_color.currentText()), icon_visual.set_svg(icon_name.text(), icon_color.currentText())))
        code = QtWidgets.QPlainTextEdit()
        code.setMinimumHeight(220)
        lay.addRow("Nom complet", full_name)
        lay.addRow("Nom abrégé", short_name)
        lay.addRow("Catégorie", category)
        lay.addRow("Description", desc)
        lay.addRow("Source", source)
        lay.addRow("Icône SVG", icon_btn)
        lay.addRow("Aperçu icône", icon_visual)
        lay.addRow("Sélection", icon_preview)
        lay.addRow("Couleur", color_picker_row)
        lay.addRow("Script", code)
        btns=QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok|QtWidgets.QDialogButtonBox.Cancel)
        lay.addRow(btns)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        if (dlg.exec_() if hasattr(dlg,'exec_') else dlg.exec()):
            item={"label":full_name.text().strip() or "New Script","short_name":short_name.text().strip(),"category":category.currentText().strip() or "Tools","tooltip":desc.text().strip(),"source":source.currentText(),"icon_svg": normalize_icon_name(icon_name.text().strip()), "icon_color": icon_color.currentText(), "command":code.toPlainText()}
            item['file_path']=save_item_to_disk(item)
            self.shelf_items = load_shelf_items()
            self.refresh()
            _broadcast_refresh(self)

    def _set_icon_preview(self, label, icon_name, color_hex):
        icon_text = (icon_name or "").strip()
        if icon_text:
            label.setText("{} ({})".format(icon_text, color_hex))
        else:
            label.setText("Aucune icône sélectionnée")

    def _apply_color_combo_swatch(self, color_combo):
        for i in range(color_combo.count()):
            hex_color = color_combo.itemText(i)
            qcol = QtGui.QColor(hex_color)
            if not qcol.isValid():
                continue
            pm = QtGui.QPixmap(14, 14)
            pm.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pm)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtGui.QPen(QtGui.QColor("#2e2e2e"), 1))
            painter.setBrush(QtGui.QBrush(qcol))
            painter.drawEllipse(1, 1, 12, 12)
            painter.end()
            color_combo.setItemIcon(i, QtGui.QIcon(pm))

    def _build_color_picker_row(self, color_combo, initial_color="#36d6ff"):
        row = QtWidgets.QWidget()
        lay = QtWidgets.QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        swatch = QtWidgets.QLabel()
        swatch.setFixedSize(22, 22)
        swatch.setFrameShape(QtWidgets.QFrame.Box)
        swatch.setLineWidth(1)

        choose_btn = QtWidgets.QPushButton("Choose Color")

        def _valid_color_hex(text):
            c = QtGui.QColor(text or "")
            return c.name(QtGui.QColor.HexRgb) if c.isValid() else "#36d6ff"

        def _apply_color(color_hex):
            safe = _valid_color_hex(color_hex)
            swatch.setStyleSheet("background:{};border:1px solid #565656;border-radius:4px;".format(safe))
            idx = color_combo.findText(safe)
            if idx >= 0 and color_combo.currentIndex() != idx:
                color_combo.setCurrentIndex(idx)
            elif idx < 0 and color_combo.currentText() != safe:
                color_combo.setCurrentText(safe)

        def _choose_color():
            start = QtGui.QColor(color_combo.currentText() or initial_color)
            if not start.isValid():
                start = QtGui.QColor("#36d6ff")
            chosen = QtWidgets.QColorDialog.getColor(start, self, "Choose Color")
            if chosen.isValid():
                _apply_color(chosen.name(QtGui.QColor.HexRgb))

        choose_btn.clicked.connect(_choose_color)
        color_combo.currentTextChanged.connect(_apply_color)
        self._apply_color_combo_swatch(color_combo)
        _apply_color(color_combo.currentText() or initial_color)

        lay.addWidget(swatch)
        lay.addWidget(color_combo, 1)
        lay.addWidget(choose_btn)
        return row

    def _pick_svg_icon(self, current_name="", current_color="#36d6ff"):
        icons = icon_catalog()
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Choisir une icône SVG")
        lay = QtWidgets.QVBoxLayout(dlg)
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Tapez pour rechercher une icône…")
        lay.addWidget(search)
        lst = QtWidgets.QListWidget()
        lst.setUniformItemSizes(True)
        lay.addWidget(lst, 1)
        info = QtWidgets.QLabel("Tapez pour rechercher une icône.")
        info.setStyleSheet("color:#b7b7b7;")
        lay.addWidget(info)
        color = QtWidgets.QComboBox(); color.addItems(ICON_COLORS); color.setCurrentText(current_color if current_color in ICON_COLORS else ICON_COLORS[0])
        self._apply_color_combo_swatch(color)
        lay.addWidget(color)
        selection = {"name": normalize_icon_name(current_name)}
        token_query = tokenized(current_name)
        max_results = 50
        min_chars = 3
        icon_cache = {}
        icon_index = []
        for p in icons:
            icon_index.append((p, tokenized(p.stem), tokenized(p.name)))

        def _fuzzy_match(query, target):
            if not query:
                return True
            if query in target:
                return True
            qi = 0
            for ch in target:
                if qi < len(query) and query[qi] == ch:
                    qi += 1
                    if qi >= len(query):
                        return True
            return False

        def refill():
            lst.clear()
            q = tokenized(search.text())
            if len(q) < min_chars:
                info.setText("Tapez au moins {} caractères pour rechercher.".format(min_chars))
                return

            matches = []
            for p, stem_key, name_key in icon_index:
                if not (_fuzzy_match(q, stem_key) or _fuzzy_match(q, name_key)):
                    continue
                matches.append((p, stem_key, name_key))

            total = len(matches)
            for p, stem_key, name_key in matches[:max_results]:
                it = QtWidgets.QListWidgetItem(p.stem)
                it.setData(QtCore.Qt.UserRole, p.name)
                it.setToolTip(p.name)
                if p.name not in icon_cache:
                    icon_cache[p.name] = QtGui.QIcon(p.as_posix())
                it.setIcon(icon_cache[p.name])
                lst.addItem(it)
                if (selection["name"] and p.name == selection["name"]) or (not selection["name"] and token_query and (token_query in stem_key or token_query in name_key)):
                    lst.setCurrentItem(it)
            if total > max_results:
                info.setText("{} résultats affichés, affinez la recherche.".format(max_results))
            elif total == 0:
                info.setText("Aucun résultat.")
            else:
                info.setText("{} résultat(s).".format(total))

        debounce = QtCore.QTimer(dlg)
        debounce.setSingleShot(True)
        debounce.setInterval(200)
        debounce.timeout.connect(refill)
        search.textChanged.connect(lambda _txt: debounce.start())
        refill()
        lst.itemClicked.connect(lambda it: selection.update({"name": it.data(QtCore.Qt.UserRole)}))
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept); btns.rejected.connect(dlg.reject)
        if not icons:
            return None
        if (dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()):
            cur = lst.currentItem()
            if cur:
                selection["name"] = cur.data(QtCore.Qt.UserRole)
            return (normalize_icon_name(selection["name"]), color.currentText()) if selection["name"] else None
        return None

    def open_script_context_menu(self, item, global_pos):
        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("QMenu{background:#373737;color:#f0f0f0;border:1px solid #565656;} QMenu::item{padding:6px 16px;} QMenu::item:selected{background:#505050;}")
        edit_action = menu.addAction("Modifier")
        delete_action = menu.addAction("Supprimer")
        chosen = menu.exec_(global_pos) if hasattr(menu, "exec_") else menu.exec(global_pos)
        if chosen == edit_action:
            self.open_edit_script_dialog(item)
        elif chosen == delete_action:
            self.delete_script_item(item)

    def delete_script_item(self, item):
        label = (item or {}).get("label") or "Script"
        file_path = Path((item or {}).get("file_path", ""))
        if not str(file_path):
            QtWidgets.QMessageBox.warning(self, "Suppression impossible", "Le chemin du script est introuvable.")
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirmer la suppression",
            "Supprimer définitivement le script « {} » ?\n\nCette action est irréversible.".format(label),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        try:
            if file_path.exists():
                file_path.unlink()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Fichier manquant",
                    "Le bouton sera retiré de l'interface, mais le fichier n'existe déjà plus :\n{}".format(file_path.as_posix())
                )
            self._refresh_ui_data()
            _broadcast_refresh(self)
            cmds.inViewMessage(amg="Script <hl>{}</hl> supprimé.".format(label), pos='midCenter', fade=True)
        except PermissionError:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de permissions",
                "Permissions insuffisantes pour supprimer ce fichier :\n{}".format(file_path.as_posix())
            )
        except OSError as ex:
            QtWidgets.QMessageBox.critical(
                self,
                "Erreur de suppression",
                "Impossible de supprimer le script « {} ».\n\nDétail : {}".format(label, ex)
            )

    def open_edit_script_dialog(self, item):
        current_path = Path(item.get("file_path", ""))
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Modifier le script ELK")
        dlg.setMinimumSize(840, 620)
        dlg.resize(980, 700)
        dlg.setSizeGripEnabled(True)
        root = QtWidgets.QVBoxLayout(dlg)

        err = QtWidgets.QLabel("")
        err.setWordWrap(True)
        err.setStyleSheet("color:#ff8f8f;font-weight:600;")
        err.hide()

        form = QtWidgets.QFormLayout()
        full_name = QtWidgets.QLineEdit(item.get("label", ""))
        short_name = QtWidgets.QLineEdit(item.get("short_name", ""))
        desc = QtWidgets.QLineEdit(item.get("tooltip", ""))
        category = QtWidgets.QComboBox(); category.setEditable(True)
        categories = [disp for _, disp, _ in self._category_rows()]
        categories = sorted({c for c in categories if c})
        if "Tools" not in categories:
            categories.insert(0, "Tools")
        current_category = item.get("category") or "Tools"
        if current_category not in categories:
            categories.append(current_category)
        category.addItems(categories)
        category.setCurrentText(current_category)
        comp_model = QtCore.QStringListModel(categories, category)
        completer = QtWidgets.QCompleter(comp_model, category)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        category.setCompleter(completer)

        def _filter_category_options(text):
            txt = (text or "").strip().lower()
            filtered = [c for c in categories if txt in c.lower()] if txt else categories
            comp_model.setStringList(filtered if filtered else categories)
            if hasattr(category, "showPopup"):
                category.showPopup()

        category.lineEdit().textEdited.connect(_filter_category_options)
        source = QtWidgets.QComboBox(); source.addItems(["python", "mel"])
        source.setCurrentText((item.get("source") or "python").lower())
        icon_name = QtWidgets.QLineEdit(normalize_icon_name(item.get("icon_svg", ""))); icon_name.setReadOnly(True)
        icon_color = QtWidgets.QComboBox(); icon_color.addItems(ICON_COLORS); icon_color.setCurrentText(item.get("icon_color") or "#36d6ff")
        color_picker_row = self._build_color_picker_row(icon_color, item.get("icon_color") or "#36d6ff")
        icon_btn = QtWidgets.QPushButton("Choisir icône…")
        icon_preview = QtWidgets.QLabel("{} ({})".format(icon_name.text() or "Aucune", icon_color.currentText()))
        icon_visual = SvgIconWidget(icon_name.text().strip(), icon_color.currentText(), 20)
        icon_visual.setVisible(bool(icon_name.text().strip()))
        icon_btn.clicked.connect(lambda: (lambda picked: (icon_name.setText(picked[0]), icon_color.setCurrentText(picked[1]), self._set_icon_preview(icon_preview, picked[0], picked[1])) if picked else None)(self._pick_svg_icon(icon_name.text(), icon_color.currentText())))
        icon_color.currentTextChanged.connect(lambda _v: (self._set_icon_preview(icon_preview, icon_name.text(), icon_color.currentText()), icon_visual.set_svg(icon_name.text(), icon_color.currentText())))

        form.addRow("Nom du script", full_name)
        form.addRow("Nom abrégé", short_name)
        form.addRow("Description", desc)
        form.addRow("Catégorie", category)
        form.addRow("Type", source)
        form.addRow("Icône SVG", icon_btn)
        form.addRow("Aperçu icône", icon_visual)
        form.addRow("Sélection", icon_preview)
        form.addRow("Couleur", color_picker_row)
        root.addLayout(form)
        root.addWidget(err)

        code = QtWidgets.QPlainTextEdit(item.get("command", ""))
        code.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        code.setMinimumHeight(360)
        root.addWidget(code, 1)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        root.addWidget(btns)
        btns.rejected.connect(dlg.reject)

        def show_error(msg):
            err.setText(msg)
            err.setVisible(bool(msg))

        def do_save():
            name = full_name.text().strip()
            short = short_name.text().strip()
            cat = category.currentText().strip() or "Tools"
            tip = desc.text().strip()
            src = source.currentText().strip().lower()
            cmd = code.toPlainText()
            if not _is_valid_script_name(name):
                show_error("Nom de script invalide. Caractères interdits: \\ / : * ? \" < > |")
                return
            if not _is_valid_script_name(short) and short:
                show_error("Nom abrégé invalide. Caractères interdits: \\ / : * ? \" < > |")
                return
            if not cat:
                show_error("La catégorie est obligatoire.")
                return
            new_slug = _slugify(name)
            cat_slug = _display_to_slug(cat)
            ext = '.mel' if src == 'mel' else '.py'
            target_dir = SCRIPTS_ROOT / cat_slug
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / f"{new_slug}{ext}"
            if current_path and target_path.resolve() != current_path.resolve() and target_path.exists():
                show_error("Un script avec le même nom existe déjà dans cette catégorie.")
                return
            updated = {"label": name, "short_name": short, "tooltip": tip, "category": cat, "source": src, "icon_svg": normalize_icon_name(icon_name.text().strip()), "icon_color": icon_color.currentText(), "command": cmd, "file_path": str(target_path)}
            try:
                if current_path and current_path.exists() and current_path.resolve() != target_path.resolve():
                    current_path.unlink()
                updated["file_path"] = save_item_to_disk(updated)
            except Exception as ex:
                show_error("Erreur lors de la sauvegarde: {}".format(ex))
                return
            self._refresh_ui_data()
            _broadcast_refresh(self)
            dlg.accept()

        btns.accepted.connect(do_save)
        dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()

    def on_search(self,t):
        text = t or ''
        sender = self.sender()
        self._keep_search_focus = bool(sender is self.h_search_line and self.is_horizontal_mode())
        if sender is self.search_box and self.h_search_line is not None and self.h_search_line.text() != text:
            self.h_search_line.blockSignals(True); self.h_search_line.setText(text); self.h_search_line.blockSignals(False)
        elif sender is self.h_search_line and self.search_box.text() != text:
            self.search_box.blockSignals(True); self.search_box.setText(text); self.search_box.blockSignals(False)
        self.search=text.lower().strip(); self.refresh()

    def toggle_view(self):
        self.view_mode="list" if self.view_mode=="grid" else "grid"; self.view_btn.setText("List" if self.view_mode=="list" else "Grid"); self.refresh()

    def grouped_items(self):
        order=[]; d={}
        for item in self.shelf_items:
            hay=(item.get('label','')+' '+item.get('tooltip','')+' '+item.get('category','')).lower()
            if self.search and self.search not in hay: continue
            cat=item.get('category','Tools') or 'Tools'
            if cat not in d: d[cat]=[]; order.append(cat)
            d[cat].append(item)
        return [(c,d[c]) for c in order if d[c]]

    def clear(self):
        while self.content_lay.count():
            it=self.content_lay.takeAt(0); w=it.widget(); w.deleteLater() if w else None

    def refresh(self):
        self.apply_layout_mode()
        was_horizontal_search_visible = bool(self.h_search_popup and self.h_search_popup.isVisible())
        keep_horizontal_search_visible = was_horizontal_search_visible or bool(self.search)
        self.clear(); self.category_widgets=[]; groups=self.grouped_items()
        if not groups:
            lab=QtWidgets.QLabel("No tool found"); lab.setAlignment(QtCore.Qt.AlignCenter); lab.setStyleSheet("color:%s;padding:30px;"%MUTED); self.content_lay.addWidget(lab); self.content_lay.addStretch(); return
        self.h_options_btn = None
        self.h_options_stack = None
        self.h_search_btn = None
        self.h_add_btn = None
        if self.is_horizontal_mode():
            self.compute_horizontal_widths()
        for cat,items in groups:
            w=Category(cat,items,self); self.category_widgets.append(w); self.content_lay.addWidget(w)
        if self.is_horizontal_mode():
            self.content_lay.addStretch()
            self.h_options_stack = QtWidgets.QFrame()
            v = QtWidgets.QVBoxLayout(self.h_options_stack)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(6)
            self.h_options_btn = QtWidgets.QToolButton()
            self.h_options_btn.setToolTip("Options")
            self.h_options_btn.setFixedSize(32, 32)
            self.h_options_btn.clicked.connect(self.open_options_dialog)
            self.h_options_btn.setIcon(QtGui.QIcon(resolve_icon_path("settings.svg").as_posix()))
            self.h_options_btn.setIconSize(QtCore.QSize(18, 18))
            self.h_options_btn.setStyleSheet("QToolButton{background:#444444;color:#f0f0f0;border:1px solid #565656;border-radius:7px;} QToolButton:hover{background:#505050;}")
            v.addWidget(self.h_options_btn, 0, QtCore.Qt.AlignHCenter)
            self.h_search_btn = QtWidgets.QToolButton()
            self.h_search_btn.setToolTip("Search / Filter")
            self.h_search_btn.setFixedSize(32, 32)
            self.h_search_btn.clicked.connect(self.toggle_horizontal_search)
            self.h_search_btn.setIcon(QtGui.QIcon(resolve_icon_path("search.svg").as_posix()))
            self.h_search_btn.setIconSize(QtCore.QSize(18, 18))
            self.h_search_btn.setStyleSheet("QToolButton{background:#444444;color:#f0f0f0;border:1px solid #565656;border-radius:7px;} QToolButton:hover{background:#505050;}")
            v.addWidget(self.h_search_btn, 0, QtCore.Qt.AlignHCenter)
            self.h_add_btn = QtWidgets.QToolButton()
            self.h_add_btn.setToolTip("Add script")
            self.h_add_btn.setFixedSize(32, 32)
            self.h_add_btn.clicked.connect(self.open_add_script_dialog)
            self.h_add_btn.setIcon(QtGui.QIcon(resolve_icon_path("new-section.svg").as_posix()))
            self.h_add_btn.setIconSize(QtCore.QSize(18, 18))
            self.h_add_btn.setStyleSheet("QToolButton{background:#444444;color:#f0f0f0;border:1px solid #565656;border-radius:7px;} QToolButton:hover{background:#505050;}")
            v.addWidget(self.h_add_btn, 0, QtCore.Qt.AlignHCenter)
            v.addStretch()
            self.content_lay.addWidget(self.h_options_stack, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)

            if self.h_search_popup is None:
                self.h_search_popup = QtWidgets.QFrame(self, QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
                self.h_search_popup.setVisible(False)
                self.h_search_popup.setStyleSheet("QFrame{background:#373737;border:1px solid #565656;border-radius:7px;}")
                hlay = QtWidgets.QHBoxLayout(self.h_search_popup)
                hlay.setContentsMargins(7, 5, 7, 5)
                hlay.setSpacing(5)
                self.h_search_line = QtWidgets.QLineEdit(self.h_search_popup)
                self.h_search_line.setPlaceholderText("Search tools...")
                self.h_search_line.textChanged.connect(self.on_search)
                self.h_search_line.setMinimumHeight(30)
                self.h_search_line.setStyleSheet("QLineEdit{background:#2f2f2f;color:%s;border:1px solid #565656;border-radius:6px;padding:6px 8px;font-size:13px;}" % TEXT)
                hlay.addWidget(self.h_search_line, 1)
            if self.h_search_line is not None:
                self.h_search_line.setText(self.search_box.text())
            self.update_horizontal_search_geometry()
            self.show_horizontal_search(keep_horizontal_search_visible)
            if keep_horizontal_search_visible and self.h_search_popup is not None:
                self.h_search_popup.raise_()
                if self._keep_search_focus and self.h_search_line is not None:
                    self.h_search_line.setFocus()
                    self.h_search_line.setCursorPosition(len(self.h_search_line.text()))
        else:
            self.show_horizontal_search(False)
            self.content_lay.addStretch()
        self.reflow()
        self._keep_search_focus = False
        self.shelf_items = load_shelf_items()

    def log_layout_state(self, reason=""):
        if not getattr(self, "layout_debug_logs_enabled", False):
            return
        prefix = "[ELK_LAYOUT_DEBUG]"
        warn = "[ELK_LAYOUT_WARNING]"
        try:
            mode = "Horizontal" if self.is_horizontal_mode() else "Vertical"
            print("{} ===== layout snapshot: {} =====".format(prefix, reason or "n/a"))
            print("{} mode={} window={} main_viewport={} content_widget={}".format(
                prefix,
                mode,
                _elk_debug_rect(self),
                _elk_debug_rect(self.scroll.viewport() if hasattr(self, "scroll") else None),
                _elk_debug_rect(self.content if hasattr(self, "content") else None),
            ))

            gscroll = self.scroll.verticalScrollBar() if hasattr(self, "scroll") else None
            g_visible = bool(gscroll and gscroll.isVisible())
            print("{} global_scroll present={} visible={} min={} max={} value={}".format(
                prefix,
                bool(gscroll),
                g_visible,
                gscroll.minimum() if gscroll else "n/a",
                gscroll.maximum() if gscroll else "n/a",
                gscroll.value() if gscroll else "n/a",
            ))

            if self.scroll is not None and self.content is not None:
                vp_h = self.scroll.viewport().height()
                content_h = self.content.sizeHint().height()
                if content_h > vp_h and (not gscroll or gscroll.maximum() <= 0):
                    print("{} Vertical overflow in main content but global scroll is not active (content_h={} viewport_h={})".format(warn, content_h, vp_h))

            for cat in self.categories():
                body_scroll = getattr(cat, "body_scroll", None)
                body_viewport = body_scroll.viewport() if body_scroll else None
                body_bar = body_scroll.verticalScrollBar() if body_scroll else None
                body_content = body_scroll.widget() if body_scroll else None
                overflow = False
                if body_content is not None and body_viewport is not None:
                    overflow = body_content.sizeHint().height() > body_viewport.height()
                cat_policy = cat.sizePolicy()
                sh = cat.sizeHint()
                print("{} cat='{}' cat_rect={} body_rect={} body_viewport={} body_content={}".format(
                    prefix, cat.name, _elk_debug_rect(cat), _elk_debug_rect(body_scroll), _elk_debug_rect(body_viewport), _elk_debug_rect(body_content)
                ))
                print("{}   internal_scroll visible={} min={} max={} value={} vPolicy={} hPolicy={} sizePolicy=({}, {}) minH={} maxH={} sizeHint={} overflow={}".format(
                    prefix,
                    bool(body_bar and body_bar.isVisible()),
                    body_bar.minimum() if body_bar else "n/a",
                    body_bar.maximum() if body_bar else "n/a",
                    body_bar.value() if body_bar else "n/a",
                    _elk_scroll_policy_name(body_scroll.verticalScrollBarPolicy()) if body_scroll else "n/a",
                    _elk_scroll_policy_name(body_scroll.horizontalScrollBarPolicy()) if body_scroll else "n/a",
                    _elk_policy_name(cat_policy.horizontalPolicy()) if cat_policy else "n/a",
                    _elk_policy_name(cat_policy.verticalPolicy()) if cat_policy else "n/a",
                    cat.minimumHeight(),
                    cat.maximumHeight(),
                    "{}x{}".format(sh.width(), sh.height()) if sh else "n/a",
                    overflow,
                ))
                if mode == "Vertical" and body_bar and (body_bar.isVisible() or body_bar.maximum() > 0):
                    print("{} Vertical mode has active internal category scroll: '{}'".format(warn, cat.name))
                if mode == "Vertical" and overflow:
                    print("{} Category content exceeds viewport in Vertical mode: '{}'".format(warn, cat.name))
                if cat.maximumHeight() < cat.minimumHeight() or (cat.maximumHeight() not in (0, 16777215) and cat.maximumHeight() <= 1):
                    print("{} Suspicious category height constraints on '{}': minH={} maxH={}".format(warn, cat.name, cat.minimumHeight(), cat.maximumHeight()))
            print("{} ===== end snapshot =====".format(prefix))
        except Exception as ex:
            print("{} layout log failed: {}".format(warn, ex))

    def resizeEvent(self,e):
        super(ELKMinimalUI,self).resizeEvent(e)
        QtCore.QTimer.singleShot(0,self.reflow)
        if AUTO_RESPONSIVE_DOCK_HEIGHT:
            workspace_name = getattr(self, "_elk_workspace_name", None)
            if workspace_name and cmds.workspaceControl(workspace_name, exists=True):
                QtCore.QTimer.singleShot(0, lambda: _apply_workspace_height(workspace_name, _calc_responsive_dock_height(self)))
        self._layout_debug_resize_timer.start(250)

    def reflow(self):
        changed = self.apply_layout_mode()
        if changed:
            self.refresh()
            return
        if self.is_horizontal_mode():
            self.compute_horizontal_widths()
            tight = self.height() <= 180 or self.width() <= 760
            self.layout().setContentsMargins(4, 4, 4, 4) if tight else self.layout().setContentsMargins(10, 10, 10, 10)
            self.layout().setSpacing(4 if tight else 8)
            self.content_lay.setSpacing(5 if tight else 8)
        else:
            self.layout().setContentsMargins(10, 10, 10, 10)
            self.layout().setSpacing(8)
            self.content_lay.setSpacing(8)
        self.update_horizontal_search_geometry()
        for c in self.category_widgets: c.reflow()
        self.log_layout_state("reflow")


def close_existing():
    if cmds.workspaceControl(WORKSPACE_NAME, exists=True): cmds.deleteUI(WORKSPACE_NAME, control=True)
    if cmds.window(WINDOW_NAME, exists=True): cmds.deleteUI(WINDOW_NAME)


def _set_maya_shelf_visibility(visible):
    """Show/hide native Maya shelf tab layout when available."""
    try:
        top_shelf = mel.eval("global string $gShelfTopLevel; $tmp=$gShelfTopLevel;")
        if top_shelf and cmds.control(top_shelf, exists=True):
            cmds.control(top_shelf, edit=True, visible=visible)
            return True
    except Exception:
        pass
    return False


def _calc_responsive_dock_height(ui):
    """Compute a responsive dock height based on content and screen geometry."""
    app = QtWidgets.QApplication.instance()
    primary = app.primaryScreen() if app else None
    available_h = primary.availableGeometry().height() if primary else 1080
    hint_values = [DOCK_HEIGHT_FALLBACK]
    try:
        hint_values.append(ui.minimumSizeHint().height())
    except Exception:
        pass
    try:
        hint_values.append(ui.sizeHint().height())
    except Exception:
        pass
    content = getattr(ui, "content", None)
    if content is not None:
        try:
            hint_values.append(content.minimumSizeHint().height())
        except Exception:
            pass
        try:
            hint_values.append(content.sizeHint().height())
        except Exception:
            pass
    target = max(DOCK_HEIGHT_MIN, max(int(v) for v in hint_values if v))
    target = min(target, int(max(available_h * DOCK_HEIGHT_MAX_RATIO, DOCK_HEIGHT_FALLBACK)))
    return target


def _apply_workspace_height(workspace_name, height):
    try:
        cmds.workspaceControl(
            workspace_name,
            edit=True,
            minimumHeight=DOCK_HEIGHT_MIN,
            initialHeight=max(DOCK_HEIGHT_MIN, int(height)),
            resizeHeight=max(DOCK_HEIGHT_MIN, int(height)),
            heightProperty="preferred",
        )
    except Exception:
        pass


def create_docked_workspace_control(workspace_name, floating=False):
    print("[ELK UI][DOCK] Creating workspaceControl...")
    if cmds.workspaceControl(workspace_name, exists=True):
        cmds.deleteUI(workspace_name, control=True)
        print("[ELK UI][DOCK] Existing workspaceControl removed.")
    control = cmds.workspaceControl(
        workspace_name,
        label="ELK Custom Shelf",
        retain=False,
        floating=floating,
        initialHeight=DOCK_HEIGHT_FALLBACK,
        minimumWidth=0,
        minimumHeight=DOCK_HEIGHT_MIN,
        widthProperty="free",
        heightProperty="preferred"
    )
    cmds.workspaceControl(workspace_name, edit=True, dockToMainWindow=("top", 1))
    print("[ELK UI][DOCK] Docked near Maya shelf area.")
    return control

def _build_unique_workspace_name(prefix):
    if not cmds.workspaceControl(prefix, exists=True):
        return prefix
    i = 2
    while True:
        candidate = "{}{}".format(prefix, i)
        if not cmds.workspaceControl(candidate, exists=True):
            return candidate
        i += 1

def show(close_existing_first=True, workspace_name=WORKSPACE_NAME, floating=False):
    """Launch ELK UI. Tries dockable workspaceControl first, then falls back to a normal Qt window."""
    _warn_if_unsupported_maya()
    if _is_maya_2022_compat_mode():
        print("[ELK UI] Maya 2022 compatibility mode enabled.")
    if close_existing_first:
        close_existing()

    ui = None
    try:
        _maya2022_log("Tentative d'ouverture en mode dock workspaceControl")
        control = create_docked_workspace_control(workspace_name, floating=floating)

        ptr = omui.MQtUtil.findControl(control)
        if not ptr:
            raise RuntimeError("MQtUtil.findControl returned None for workspaceControl")

        control_widget = wrapInstance(int(ptr), QtWidgets.QWidget)
        control_widget.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        control_widget.setStyleSheet("background:%s;" % BG)
        control_widget.setMinimumSize(0, 0)
        control_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        old_layout = control_widget.layout()
        if old_layout is not None:
            while old_layout.count():
                item = old_layout.takeAt(0)
                child = item.widget()
                if child:
                    child.setParent(None)
            layout = old_layout
        else:
            layout = QtWidgets.QVBoxLayout(control_widget)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        ui = ELKMinimalUI(control_widget, instance_name=workspace_name + "_UI")
        layout.addWidget(ui)
        ui._elk_workspace_name = workspace_name

        # Keep Python reference alive on the Maya control.
        control_widget._elk_ui_instance = ui
        globals()["ELK_UI_INSTANCE"] = ui
        globals().setdefault("ELK_UI_INSTANCES", []).append(ui)

        cmds.workspaceControl(workspace_name, edit=True, visible=True, restore=True)
        cmds.workspaceControl(workspace_name, edit=True, minimumWidth=0, minimumHeight=0, widthProperty="free", heightProperty="free")
        if AUTO_HIDE_MAYA_SHELF and _set_maya_shelf_visibility(False):
            print("[ELK UI][DOCK] Maya native shelf hidden.")
        dock_height = DOCK_HEIGHT_FALLBACK
        if AUTO_RESPONSIVE_DOCK_HEIGHT:
            dock_height = _calc_responsive_dock_height(ui)
        _apply_workspace_height(workspace_name, dock_height)
        print("[ELK UI][DOCK] Responsive height calculated: {} px.".format(dock_height))
        QtCore.QTimer.singleShot(0, ui.reflow)
        QtCore.QTimer.singleShot(100, ui.reflow)
        print("[ELK UI][DOCK] Reflow after dock complete.")
        _maya2022_log("workspaceControl initialisé avec succès")
        return ui

    except Exception as dock_error:
        _maya2022_log("Échec du mode dock, passage en fenêtre flottante", dock_error)
        cmds.warning("[ELK UI][DOCK][WARNING] Dock failed, using floating window fallback. {}".format(dock_error))
        traceback.print_exc()

        # Fallback: standard Qt window, useful if workspaceControl bugs out in a Maya session.
        try:
            main_ptr = omui.MQtUtil.mainWindow()
            parent = wrapInstance(int(main_ptr), QtWidgets.QWidget) if main_ptr else None
        except Exception as parent_lookup_error:
            _maya2022_log("Impossible de récupérer la fenêtre principale Maya", parent_lookup_error)
            parent = None

        win = QtWidgets.QDialog(parent)
        win.setObjectName(WINDOW_NAME + "FallbackWindow")
        win.setWindowTitle("ELK UI")
        win.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        win.setStyleSheet("background:%s;" % BG)
        win.resize(520, 760)
        lay = QtWidgets.QVBoxLayout(win)
        lay.setContentsMargins(0, 0, 0, 0)
        ui = ELKMinimalUI(win, instance_name=workspace_name + "_FallbackUI")
        lay.addWidget(ui)
        win._elk_ui_instance = ui
        globals()["ELK_UI_WINDOW"] = win
        globals()["ELK_UI_INSTANCE"] = ui
        globals().setdefault("ELK_UI_INSTANCES", []).append(ui)
        _maya2022_log("Fenêtre flottante initialisée avec succès")
        win.show()
        return ui

def show_second_instance():
    workspace_name = _build_unique_workspace_name(SECOND_INSTANCE_WORKSPACE_PREFIX)
    return show(close_existing_first=False, workspace_name=workspace_name, floating=True)

try:
    ELK_UI_INSTANCE=show()
except Exception as e:
    cmds.warning("[ELK UI] Launch failed: {}".format(e)); traceback.print_exc()
