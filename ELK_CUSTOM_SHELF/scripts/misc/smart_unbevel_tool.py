# ELK_META {"label": "Smart Unbevel Tool", "short_name": "UnBev", "tooltip": "Détecte automatiquement les bevels polygonaux puis tente de reconstruire les surfaces originales via intersections de plans et collapse intelligent des vertices.", "source": "python", "icon_svg": "layout-distribute-vertical.svg", "icon_color": "#ff5d3b"}
import maya.cmds as cmds
import maya.api.OpenMaya as om

WINDOW = "unbevelIntersectionTool"


# ============================================================
# Selection / Mesh utils
# ============================================================

def get_selected_meshes():
    sel = cmds.ls(selection=True, long=True) or []
    meshes = []
    seen = set()

    for obj in sel:
        if "." in obj:
            obj = obj.split(".")[0]

        if not cmds.objExists(obj):
            continue

        if cmds.nodeType(obj) == "mesh":
            shape = obj
            parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if not parents:
                continue
            transform = parents[0]
        else:
            shapes = cmds.listRelatives(obj, shapes=True, fullPath=True, type="mesh") or []
            if not shapes:
                continue
            transform = obj
            shape = shapes[0]

        if transform not in seen:
            meshes.append((transform, shape))
            seen.add(transform)

    return meshes


def get_dag_path(shape):
    sel = om.MSelectionList()
    sel.add(shape)
    return sel.getDagPath(0)


def get_mesh_data(shape):
    dag = get_dag_path(shape)
    mesh = om.MFnMesh(dag)

    points = mesh.getPoints(om.MSpace.kWorld)

    faces = []
    face_edges = []

    poly_it = om.MItMeshPolygon(dag)
    while not poly_it.isDone():
        faces.append(list(poly_it.getVertices()))
        face_edges.append(list(poly_it.getEdges()))
        poly_it.next()

    edge_vertices = {}
    edge_faces = {}

    edge_it = om.MItMeshEdge(dag)
    while not edge_it.isDone():
        eid = edge_it.index()
        v0 = edge_it.vertexId(0)
        v1 = edge_it.vertexId(1)
        edge_vertices[eid] = (v0, v1)
        edge_faces[eid] = list(edge_it.getConnectedFaces())
        edge_it.next()

    face_normals = {}
    for i in range(mesh.numPolygons):
        face_normals[i] = mesh.getPolygonNormal(i, om.MSpace.kWorld).normal()

    return {
        "dag": dag,
        "mesh": mesh,
        "points": points,
        "faces": faces,
        "face_edges": face_edges,
        "edge_vertices": edge_vertices,
        "edge_faces": edge_faces,
        "face_normals": face_normals,
    }


def edge_length(points, a, b):
    return (points[a] - points[b]).length()


def find_edge_id_from_verts(data, a, b):
    wanted = set([a, b])
    for eid, verts in data["edge_vertices"].items():
        if set(verts) == wanted:
            return eid
    return None


# ============================================================
# Bevel detection
# ============================================================

def detect_bevel_faces(shape, max_width=2.0):
    data = get_mesh_data(shape)
    points = data["points"]
    faces = data["faces"]

    result = []

    for face_id, verts in enumerate(faces):
        if len(verts) != 4:
            continue

        v0, v1, v2, v3 = verts

        l01 = edge_length(points, v0, v1)
        l12 = edge_length(points, v1, v2)
        l23 = edge_length(points, v2, v3)
        l30 = edge_length(points, v3, v0)

        width_a = (l12 + l30) * 0.5
        length_a = (l01 + l23) * 0.5

        width_b = (l01 + l23) * 0.5
        length_b = (l12 + l30) * 0.5

        is_a = width_a <= max_width and length_a > width_a * 1.2
        is_b = width_b <= max_width and length_b > width_b * 1.2

        if is_a or is_b:
            result.append(face_id)

    return result


# ============================================================
# Plane intersection
# ============================================================

def get_adjacent_non_self_face(data, edge_id, current_face):
    connected = data["edge_faces"].get(edge_id, [])
    for f in connected:
        if f != current_face:
            return f
    return None


def plane_intersection_line(n1, p1, n2, p2):
    n1 = om.MVector(n1).normal()
    n2 = om.MVector(n2).normal()

    direction = n1 ^ n2
    denom = direction * direction

    if denom < 1e-10:
        return None, None

    k1 = n1 * om.MVector(p1)
    k2 = n2 * om.MVector(p2)

    point_vec = ((n2 * k1) - (n1 * k2)) ^ direction
    point_vec = point_vec / denom

    return om.MPoint(point_vec), direction.normal()


def project_point_on_line(point, line_point, line_dir):
    v = om.MVector(point - line_point)
    t = v * line_dir
    projected = line_point + (line_dir * t)
    return om.MPoint(projected)


# ============================================================
# Unbevel logic
# ============================================================

def compute_unbevel_targets_for_face(data, face_id):
    points = data["points"]
    faces = data["faces"]
    normals = data["face_normals"]

    verts = faces[face_id]
    if len(verts) != 4:
        return []

    v0, v1, v2, v3 = verts

    l01 = edge_length(points, v0, v1)
    l12 = edge_length(points, v1, v2)
    l23 = edge_length(points, v2, v3)
    l30 = edge_length(points, v3, v0)

    width_a = (l12 + l30) * 0.5
    width_b = (l01 + l23) * 0.5

    if width_a < width_b:
        long_edge_1 = find_edge_id_from_verts(data, v0, v1)
        long_edge_2 = find_edge_id_from_verts(data, v2, v3)
        collapse_pairs = [(v0, v3), (v1, v2)]
    else:
        long_edge_1 = find_edge_id_from_verts(data, v1, v2)
        long_edge_2 = find_edge_id_from_verts(data, v3, v0)
        collapse_pairs = [(v0, v1), (v3, v2)]

    if long_edge_1 is None or long_edge_2 is None:
        return []

    support_face_1 = get_adjacent_non_self_face(data, long_edge_1, face_id)
    support_face_2 = get_adjacent_non_self_face(data, long_edge_2, face_id)

    if support_face_1 is None or support_face_2 is None:
        return []

    n1 = normals[support_face_1]
    n2 = normals[support_face_2]

    p1 = points[data["faces"][support_face_1][0]]
    p2 = points[data["faces"][support_face_2][0]]

    line_point, line_dir = plane_intersection_line(n1, p1, n2, p2)

    if line_point is None:
        return []

    targets = []

    for a, b in collapse_pairs:
        pa = points[a]
        pb = points[b]

        mid = om.MPoint(
            (pa.x + pb.x) * 0.5,
            (pa.y + pb.y) * 0.5,
            (pa.z + pb.z) * 0.5
        )

        target = project_point_on_line(mid, line_point, line_dir)
        targets.append((a, b, target))

    return targets


def preview_bevel_faces(*args):
    meshes = get_selected_meshes()
    if not meshes:
        cmds.warning("Sélectionne un ou plusieurs meshes.")
        return

    max_width = cmds.floatField("unbevel_maxWidth", query=True, value=True)

    all_faces = []
    total = 0

    for transform, shape in meshes:
        if not cmds.objExists(transform):
            continue

        faces = detect_bevel_faces(shape, max_width=max_width)

        for f in faces:
            all_faces.append("{}.f[{}]".format(transform, f))

        total += len(faces)

    if not all_faces:
        cmds.warning("Aucune face de bevel détectée.")
        return

    cmds.select(all_faces, replace=True)
    print("[Unbevel] Faces détectées sur tous les objets :", total)


def collapse_one_mesh(transform, max_width, iterations, merge_distance):
    total_faces = 0
    total_pairs = 0

    for it in range(iterations):
        if not cmds.objExists(transform):
            break

        shapes = cmds.listRelatives(transform, shapes=True, fullPath=True, type="mesh") or []
        if not shapes:
            break

        shape = shapes[0]

        data = get_mesh_data(shape)
        bevel_faces = detect_bevel_faces(shape, max_width=max_width)

        if not bevel_faces:
            print("[Unbevel] {} | Itération {} : aucune face détectée.".format(transform, it + 1))
            break

        vertex_targets = {}
        merge_vertices = []

        for face_id in bevel_faces:
            targets = compute_unbevel_targets_for_face(data, face_id)

            if not targets:
                continue

            for a, b, target in targets:
                vertex_targets[a] = target
                vertex_targets[b] = target
                merge_vertices.append(a)
                merge_vertices.append(b)
                total_pairs += 1

            total_faces += 1

        if not vertex_targets:
            print("[Unbevel] {} | Aucun target calculé.".format(transform))
            break

        for vid, target in vertex_targets.items():
            cmds.xform(
                "{}.vtx[{}]".format(transform, vid),
                worldSpace=True,
                translation=(target.x, target.y, target.z)
            )

        cmds.select(
            ["{}.vtx[{}]".format(transform, v) for v in sorted(set(merge_vertices))],
            replace=True
        )

        cmds.polyMergeVertex(
            distance=merge_distance,
            constructionHistory=False
        )

        cmds.select(transform, replace=True)
        cmds.polySoftEdge(transform, angle=0, constructionHistory=False)

        try:
            cmds.delete(transform, constructionHistory=True)
        except:
            pass

        print("[Unbevel] {} | Itération {} terminée.".format(transform, it + 1))

    return total_faces, total_pairs


def collapse_bevels_to_intersection(*args):
    meshes = get_selected_meshes()

    if not meshes:
        cmds.warning("Sélectionne un ou plusieurs meshes.")
        return

    max_width = cmds.floatField("unbevel_maxWidth", query=True, value=True)
    iterations = cmds.intField("unbevel_iterations", query=True, value=True)
    merge_distance = cmds.floatField("unbevel_mergeDistance", query=True, value=True)

    selected_transforms = [m[0] for m in meshes]

    cmds.undoInfo(openChunk=True)

    try:
        global_faces = 0
        global_pairs = 0
        processed = []

        for transform, shape in meshes:
            if not cmds.objExists(transform):
                continue

            print("\n[Unbevel] ----------------------------------------")
            print("[Unbevel] Objet :", transform)

            faces_count, pairs_count = collapse_one_mesh(
                transform,
                max_width,
                iterations,
                merge_distance
            )

            global_faces += faces_count
            global_pairs += pairs_count
            processed.append(transform)

        if processed:
            cmds.select(processed, replace=True)
        else:
            cmds.select(selected_transforms, replace=True)

        print("\n[Unbevel] ========================================")
        print("[Unbevel] Traitement multi-objets terminé.")
        print("[Unbevel] Objets traités :", len(processed))
        print("[Unbevel] Total faces traitées :", global_faces)
        print("[Unbevel] Total paires mergées :", global_pairs)

    finally:
        cmds.undoInfo(closeChunk=True)


# ============================================================
# UI
# ============================================================

def show_ui():
    if cmds.window(WINDOW, exists=True):
        cmds.deleteUI(WINDOW)

    cmds.window(WINDOW, title="Unbevel To 90° Intersection", sizeable=False)

    cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=8,
        columnOffset=("both", 10)
    )

    cmds.text(
        label="Unbevel To 90° Intersection",
        height=28,
        align="center"
    )

    cmds.text(
        label="Fonctionne sur un ou plusieurs objets sélectionnés.",
        align="center"
    )

    cmds.separator(height=10)

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Max bevel width")
    cmds.floatField("unbevel_maxWidth", value=2.0, precision=4)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Merge distance")
    cmds.floatField("unbevel_mergeDistance", value=0.001, precision=6)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Iterations")
    cmds.intField("unbevel_iterations", value=1, minValue=1)
    cmds.setParent("..")

    cmds.separator(height=10)

    cmds.button(
        label="01 - Preview Detected Bevel Faces",
        height=35,
        command=preview_bevel_faces
    )

    cmds.button(
        label="02 - Collapse Bevels To 90° Intersection",
        height=42,
        backgroundColor=(0.35, 0.45, 0.35),
        command=collapse_bevels_to_intersection
    )

    cmds.separator(height=10)

    cmds.text(
        label="Sélectionne plusieurs meshes, puis lance le Collapse.\n"
              "Chaque objet est traité séparément.",
        align="center"
    )

    cmds.showWindow(WINDOW)


show_ui()