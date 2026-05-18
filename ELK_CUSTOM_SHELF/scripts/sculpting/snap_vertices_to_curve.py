# ELK_META {"label": "Snap Vertices To Curve", "short_name": "VtxCrv", "tooltip": "Déplace automatiquement des vertices sélectionnés vers la courbe NURBS la plus proche.", "source": "python", "icon_svg": "route.svg", "icon_color": "#36d6ff", "apply_elk_ui_style": true, "secondary_scripts": []}
import maya.cmds as cmds
import maya.api.OpenMaya as om

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

# Liste de sets :
# chaque entre = {"curve": curveTransformName, "verts": [vtx components]}
stored_sets = []


# ---------------------------------------------------------------------------
# Utils
# ---------------------------------------------------------------------------

def get_dag_path(obj):
    """
    Returns an MDagPath pointing to the nurbsCurve shape of the given object.
    """
    sel = om.MSelectionList()
    sel.add(obj)
    dag_path = sel.getDagPath(0)

    if dag_path.node().hasFn(om.MFn.kTransform):
        try:
            dag_path.extendToShape()
        except RuntimeError:
            pass

    return dag_path


def ensure_transform(node):
    """
    S'assure qu'on a un transform (pas juste le shape).
    """
    if not cmds.objExists(node):
        return None
    if cmds.nodeType(node) == "transform":
        return node
    parent = cmds.listRelatives(node, parent=True, fullPath=True)
    return parent[0] if parent else node


def find_closest_point_on_curve(curve, point, sample_rate=100):
    """
    Trouve le point le plus proche sur une curve par sampling.
    """
    dag_path = get_dag_path(curve)
    curve_fn = om.MFnNurbsCurve(dag_path)

    closest_point = None
    min_distance = float('inf')
    start_param, end_param = curve_fn.knotDomain

    for i in range(sample_rate + 1):
        t = start_param + (end_param - start_param) * (float(i) / float(sample_rate))
        curve_point = curve_fn.getPointAtParam(t, om.MSpace.kWorld)
        distance = om.MPoint(point).distanceTo(curve_point)

        if distance < min_distance:
            min_distance = distance
            closest_point = curve_point

    return closest_point


def move_vertices_to_curve(curve, vertices, sample_rate=100):
    """
    Dplace chaque vertex de 'vertices' vers le point le plus proche sur 'curve'.
    """
    for vert in vertices:
        try:
            vert_pos = cmds.pointPosition(vert, world=True)
        except RuntimeError:
            cmds.warning("Impossible de rcuprer la position de : {}".format(vert))
            continue

        closest_point = find_closest_point_on_curve(curve, vert_pos, sample_rate)
        if closest_point and isinstance(closest_point, om.MPoint):
            try:
                cmds.move(closest_point.x, closest_point.y, closest_point.z,
                          vert, worldSpace=True, absolute=True)
            except Exception as e:
                cmds.warning("chec du dplacement du vertex {} : {}".format(vert, e))
        else:
            cmds.warning("Impossible de dterminer un point proche sur la courbe pour : {}".format(vert))


# ---------------------------------------------------------------------------
# Grouping des edges en sets connects
# ---------------------------------------------------------------------------

def parse_index_from_component(comp):
    """
    Ex: 'pCube1.vtx[12]' -> 12
    """
    if '[' not in comp or ']' not in comp:
        return None
    inside = comp[comp.find('[') + 1:comp.find(']')]
    try:
        return int(inside.split(':')[0])
    except ValueError:
        return None


def group_edges_into_sets(edges):
    """
    edges : liste de composants edge (pCube1.e[10], etc.)
    Retourne une liste de listes : chaque sous-liste = un set d'edges connects.
    On gre les meshes sparment (pas de sets mlangeant plusieurs meshes).
    """
    edge_sets = []

    # 1) Regrouper par mesh
    mesh_to_edges = {}
    for e in edges:
        long_e = cmds.ls(e, long=True)[0]
        mesh = long_e.split('.')[0]
        mesh_to_edges.setdefault(mesh, []).append(long_e)

    # 2) Pour chaque mesh, on dcoupe en composants connects
    for mesh, mesh_edges in mesh_to_edges.items():
        # Maps temporaires
        edge_to_verts = {}
        vertex_to_edges = {}

        # Pr-calcul : quels vertices pour chaque edge
        for edge in mesh_edges:
            verts = cmds.polyListComponentConversion(edge, toVertex=True)
            verts = cmds.ls(verts, flatten=True) or []
            v_indices = []

            for v in verts:
                idx = parse_index_from_component(v)
                if idx is None:
                    continue
                v_indices.append(idx)
                vertex_to_edges.setdefault(idx, []).append(edge)

            edge_to_verts[edge] = v_indices

        unvisited = set(mesh_edges)

        # BFS / DFS pour trouver les composants connects
        while unvisited:
            start = next(iter(unvisited))
            unvisited.remove(start)
            component = [start]
            queue = [start]

            while queue:
                current = queue.pop(0)
                for v_idx in edge_to_verts.get(current, []):
                    for neighbor in vertex_to_edges.get(v_idx, []):
                        if neighbor in unvisited:
                            unvisited.remove(neighbor)
                            queue.append(neighbor)
                            component.append(neighbor)

            edge_sets.append(component)

    return edge_sets


# ---------------------------------------------------------------------------
# STEP 1  Crer les curves, rebuild, stocker les sets de verts
# ---------------------------------------------------------------------------

def create_curves_and_store_vertices(spans=6, degree=3):
    """
    -  partir d'une slection d'edges (possiblement plusieurs lots)
    - Regroupe en sets d'edges connects
    - Pour chaque set :
        * cre une curve (polyToCurve)
        * rebuildCurve (spans, degree)
        * delete history + freeze
        * convertit ce set d'edges en vertices
        * stocke {curve, verts} dans stored_sets
    - Slectionne toutes les curves cres pour dition
    """
    global stored_sets
    stored_sets = []  # reset

    # Rcuprer la slection d'edges
    edge_sel = cmds.ls(selection=True, flatten=True)
    if not edge_sel:
        cmds.warning("Veuillez d'abord slectionner au moins un edge.")
        return

    edge_sel = cmds.filterExpand(edge_sel, sm=32) or []
    if not edge_sel:
        cmds.warning("La slection doit contenir des edges de polygone.")
        return

    # Regrouper en sets d'edges connects
    edge_sets = group_edges_into_sets(edge_sel)
    if not edge_sets:
        cmds.warning("Aucun set d'edges valide trouv.")
        return

    all_curves = []

    for edge_set in edge_sets:
        # 1) Convertir ce set d'edges en vertices (et stocker)
        verts = cmds.polyListComponentConversion(edge_set, toVertex=True)
        verts = cmds.ls(verts, flatten=True) or []
        if not verts:
            cmds.warning("Impossible de convertir un set d'edges en vertices.")
            continue

        # 2) Crer la curve pour ce set
        cmds.select(edge_set, r=True)
        try:
            curve_list = cmds.polyToCurve(form=2, degree=1, conformToSmoothMeshPreview=0)
        except RuntimeError as e:
            cmds.warning("chec de polyToCurve sur un set d'edges : {}".format(e))
            continue

        if not curve_list:
            cmds.warning("polyToCurve n'a pas cr de courbe pour un set d'edges.")
            continue

        curve = ensure_transform(curve_list[0])

        # 3) Rebuild la curve
        try:
            rebuild_result = cmds.rebuildCurve(curve,
                                               ch=1, rpo=1, rt=0, end=1,
                                               kr=0, kcp=0, kep=1, kt=0,
                                               s=spans, d=degree, tol=0.01)
        except RuntimeError as e:
            cmds.warning("chec de rebuildCurve : {}".format(e))
            continue

        if isinstance(rebuild_result, (list, tuple)):
            curve = ensure_transform(rebuild_result[0])
        else:
            curve = ensure_transform(rebuild_result)

        if not curve:
            cmds.warning("Impossible de rcuprer le transform de la courbe rebuild.")
            continue

        # 4) Delete history + freeze
        try:
            cmds.delete(curve, ch=True)
            cmds.makeIdentity(curve, apply=True, t=1, r=1, s=1, n=0, pn=1)
        except RuntimeError as e:
            cmds.warning("Problme delete history / freeze : {}".format(e))

        # 5) Stocker ce set
        stored_sets.append({
            "curve": curve,
            "verts": verts
        })
        all_curves.append(curve)

    if not stored_sets:
        cmds.warning("Aucun set de courbe/vertices n'a pu tre cr.")
        return

    # Slectionner toutes les curves pour les modifier si besoin
    cmds.select(all_curves)

    cmds.inViewMessage(
        assistMessage='Curves created for each edge set. Edit them if needed, then use Step 2 to project & auto-delete.',
        position='midCenter',
        fade=True
    )


# ---------------------------------------------------------------------------
# STEP 2  Projeter tous les sets + supprimer leurs curves
# ---------------------------------------------------------------------------

def project_all_stored_sets(sample_rate=100):
    """
    Pour chaque set stock :
      - projette ses vertices sur sa curve
      - supprime la curve
    """
    global stored_sets

    if not stored_sets:
        cmds.warning("Aucun set stock. Lance d'abord Step 1.")
        return

    for data in stored_sets:
        curve = data.get("curve")
        verts = data.get("verts") or []

        if not curve or not cmds.objExists(curve):
            cmds.warning("Courbe introuvable pour un set, ignor.")
            continue

        if not verts:
            cmds.warning("Vertices manquants pour un set, ignor.")
            continue

        move_vertices_to_curve(curve, verts, sample_rate=sample_rate)

        # Supprimer la curve aprs projection
        try:
            cmds.delete(curve)
        except:
            pass

    stored_sets = []

    cmds.select(clear=True)
    cmds.inViewMessage(
        assistMessage='All stored vertex sets projected to their curves. Curves auto-deleted.',
        position='midCenter',
        fade=True
    )


# ---------------------------------------------------------------------------
# One-click  Step1 + Step2
# ---------------------------------------------------------------------------

def one_click_project(spans=6, degree=3, sample_rate=100):
    """
    Workflow full auto :
    - Cre les curves et stocke les sets (pour chaque groupe dedges connects)
    - Projette chaque set sur sa curve
    - Supprime les curves
    """
    create_curves_and_store_vertices(spans=spans, degree=degree)
    if stored_sets:
        project_all_stored_sets(sample_rate=sample_rate)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def ui_step1(*_):
    spans = cmds.intSliderGrp("projSpansField", q=True, value=True)
    create_curves_and_store_vertices(spans=spans, degree=3)


def ui_step2(*_):
    sample_rate = cmds.intSliderGrp("projSampleField", q=True, value=True)
    project_all_stored_sets(sample_rate=sample_rate)


def ui_one_click(*_):
    spans = cmds.intSliderGrp("projSpansField", q=True, value=True)
    sample_rate = cmds.intSliderGrp("projSampleField", q=True, value=True)
    one_click_project(spans=spans, degree=3, sample_rate=sample_rate)


def show_project_ui():
    if cmds.window("projCurveWin", exists=True):
        cmds.deleteUI("projCurveWin")

    win = cmds.window("projCurveWin",
                      title="Project Vertices to Curves (multi edge sets)",
                      sizeable=False)

    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")

    cmds.intSliderGrp("projSpansField",
                      label="Rebuild spans",
                      field=True,
                      minValue=1,
                      maxValue=50,
                      value=6)

    cmds.intSliderGrp("projSampleField",
                      label="Sample rate",
                      field=True,
                      minValue=10,
                      maxValue=500,
                      value=100)

    cmds.separator(h=10, style="in")

    cmds.button(label="Step 1  Create curves & store vertex sets",
                height=30,
                command=ui_step1)

    cmds.button(label="Step 2  Project all sets + auto-delete curves",
                height=30,
                command=ui_step2)

    cmds.separator(h=10, style="in")

    cmds.button(label="One-click  Create, project & auto-delete (all sets)",
                height=30,
                command=ui_one_click)

    cmds.setParent("..")
    cmds.showWindow(win)


show_project_ui()