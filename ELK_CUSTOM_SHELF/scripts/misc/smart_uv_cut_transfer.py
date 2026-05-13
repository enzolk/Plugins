# ELK_META {"label": "Smart UV Cut Transfer", "short_name": "UVCut", "tooltip": "Analyse les cuts UV d’une sélection source puis les reproduit intelligemment sur une autre sélection avec système d’itérations et safe cuts.", "source": "python", "icon_svg": "transfer.svg", "icon_color": "#ff5d3b"}
import maya.cmds as cmds
import math

WINDOW_NAME = "uv_cut_transfer_tool_safe_cuts"

STORED_UV_CUT_TEMPLATE = None
ITERATION_SOLUTIONS = []
CURRENT_ITERATION = 0
SAFE_CUT_EDGES = []

DEFAULT_MATCH_MARGIN = 0.18
DEFAULT_MAX_ITERATIONS = 8

margin_slider = None
iteration_slider = None
max_iterations_field = None
status_text = None


def flatten_components(components):
    if not components:
        return []
    return cmds.ls(components, flatten=True, long=True) or []


def get_selected_faces():
    sel = cmds.ls(selection=True, flatten=True, long=True) or []
    faces = [x for x in sel if ".f[" in x]

    if not faces:
        faces = flatten_components(cmds.polyListComponentConversion(sel, toFace=True))

    faces = [f for f in faces if ".f[" in f]

    if not faces:
        cmds.warning("Sélectionne des faces.")
        return []

    meshes = set([f.split(".f[")[0] for f in faces])
    if len(meshes) > 1:
        cmds.warning("Sélectionne des faces sur un seul mesh.")
        return []

    return faces


def get_selected_edges():
    sel = cmds.ls(selection=True, flatten=True, long=True) or []
    edges = [x for x in sel if ".e[" in x]

    if not edges:
        edges = flatten_components(cmds.polyListComponentConversion(sel, toEdge=True))

    return sorted(list(set([e for e in edges if ".e[" in e])))


def get_mesh_from_component(component):
    return component.split(".")[0]


def get_vertices_from_edge(edge):
    info = cmds.polyInfo(edge, edgeToVertex=True)
    if not info:
        return []

    parts = info[0].replace(":", " ").split()
    ids = [int(p) for p in parts if p.isdigit()]

    if len(ids) < 3:
        return []

    return ids[-2:]


def get_world_pos(mesh, vtx_id):
    return cmds.xform(
        "{}.vtx[{}]".format(mesh, vtx_id),
        q=True,
        ws=True,
        t=True
    )


def vec_sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def vec_len(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def vec_norm(v):
    l = vec_len(v)
    if l < 0.000001:
        return [0.0, 0.0, 0.0]
    return [v[0] / l, v[1] / l, v[2] / l]


def vec_mid(a, b):
    return [
        (a[0] + b[0]) * 0.5,
        (a[1] + b[1]) * 0.5,
        (a[2] + b[2]) * 0.5
    ]


def distance(a, b):
    return math.sqrt(
        (a[0] - b[0]) ** 2 +
        (a[1] - b[1]) ** 2 +
        (a[2] - b[2]) ** 2
    )


def get_edges_from_faces(faces):
    edges = cmds.polyListComponentConversion(faces, toEdge=True)
    edges = flatten_components(edges)
    return sorted(list(set(edges)))


def get_selection_bbox(faces):
    vertices = flatten_components(cmds.polyListComponentConversion(faces, toVertex=True))

    positions = [
        cmds.xform(v, q=True, ws=True, t=True)
        for v in vertices
    ]

    min_pos = [
        min(p[0] for p in positions),
        min(p[1] for p in positions),
        min(p[2] for p in positions)
    ]

    max_pos = [
        max(p[0] for p in positions),
        max(p[1] for p in positions),
        max(p[2] for p in positions)
    ]

    size = [
        max(max_pos[0] - min_pos[0], 0.0001),
        max(max_pos[1] - min_pos[1], 0.0001),
        max(max_pos[2] - min_pos[2], 0.0001)
    ]

    diag = max(vec_len(size), 0.0001)

    return min_pos, size, diag


def normalize_pos(pos, bbox_min, bbox_size):
    return [
        (pos[0] - bbox_min[0]) / bbox_size[0],
        (pos[1] - bbox_min[1]) / bbox_size[1],
        (pos[2] - bbox_min[2]) / bbox_size[2]
    ]


def is_uv_cut_edge(edge):
    uvs = flatten_components(cmds.polyListComponentConversion(edge, toUV=True))
    return len(set(uvs)) > 2


def get_edge_data(edge, bbox_min, bbox_size, bbox_diag):
    if not cmds.objExists(edge):
        return None

    mesh = get_mesh_from_component(edge)
    vtx_ids = get_vertices_from_edge(edge)

    if len(vtx_ids) != 2:
        return None

    p1 = get_world_pos(mesh, vtx_ids[0])
    p2 = get_world_pos(mesh, vtx_ids[1])

    mid = vec_mid(p1, p2)
    direction = vec_norm(vec_sub(p2, p1))
    length = vec_len(vec_sub(p2, p1))

    return {
        "edge": edge,
        "mid_norm": normalize_pos(mid, bbox_min, bbox_size),
        "dir_abs": [
            abs(direction[0]),
            abs(direction[1]),
            abs(direction[2])
        ],
        "length_norm": length / bbox_diag
    }


def edge_score(source_data, target_data):
    pos_score = distance(source_data["mid_norm"], target_data["mid_norm"])
    dir_score = distance(source_data["dir_abs"], target_data["dir_abs"])
    length_score = abs(source_data["length_norm"] - target_data["length_norm"])

    return (
        pos_score * 1.0 +
        dir_score * 0.35 +
        length_score * 0.35
    )


def update_status(message):
    if status_text and cmds.control(status_text, exists=True):
        cmds.text(status_text, e=True, label=message)
    print(message)


def store_uv_cuts_from_selection():
    global STORED_UV_CUT_TEMPLATE
    global ITERATION_SOLUTIONS
    global CURRENT_ITERATION

    ITERATION_SOLUTIONS = []
    CURRENT_ITERATION = 0

    faces = get_selected_faces()
    if not faces:
        return

    bbox_min, bbox_size, bbox_diag = get_selection_bbox(faces)
    edges = get_edges_from_faces(faces)

    cut_edges_data = []

    for edge in edges:
        if is_uv_cut_edge(edge):
            data = get_edge_data(edge, bbox_min, bbox_size, bbox_diag)
            if data:
                cut_edges_data.append(data)

    if not cut_edges_data:
        cmds.warning("Aucun cut UV détecté dans la sélection source.")
        return

    STORED_UV_CUT_TEMPLATE = {
        "cut_edges": cut_edges_data,
        "count": len(cut_edges_data)
    }

    update_status("Cuts UV mémorisés : {}".format(len(cut_edges_data)))

    cmds.inViewMessage(
        amg="Cuts UV mémorisés : <hl>{}</hl>".format(len(cut_edges_data)),
        pos="midCenter",
        fade=True
    )


def add_safe_cut_edges():
    global SAFE_CUT_EDGES

    edges = get_selected_edges()

    if not edges:
        cmds.warning("Sélectionne une ou plusieurs edges à forcer en UV Cut.")
        return

    SAFE_CUT_EDGES = sorted(list(set(SAFE_CUT_EDGES + edges)))

    cmds.select(SAFE_CUT_EDGES, replace=True)

    update_status("Safe UV Cut edges enregistrées : {}".format(len(SAFE_CUT_EDGES)))

    cmds.inViewMessage(
        amg="Safe UV Cut edges : <hl>{}</hl>".format(len(SAFE_CUT_EDGES)),
        pos="midCenter",
        fade=True
    )


def clear_safe_cut_edges():
    global SAFE_CUT_EDGES

    SAFE_CUT_EDGES = []

    update_status("Safe UV Cut edges effacées.")

    cmds.inViewMessage(
        amg="Safe UV Cut edges effacées.",
        pos="midCenter",
        fade=True
    )


def select_safe_cut_edges():
    if not SAFE_CUT_EDGES:
        cmds.warning("Aucune Safe UV Cut edge enregistrée.")
        return

    existing_edges = [e for e in SAFE_CUT_EDGES if cmds.objExists(e)]

    if not existing_edges:
        cmds.warning("Les Safe UV Cut edges enregistrées n'existent plus.")
        return

    cmds.select(existing_edges, replace=True)

    update_status("Safe UV Cut edges sélectionnées : {}".format(len(existing_edges)))


def build_safe_edge_data_list(bbox_min, bbox_size, bbox_diag):
    safe_data_list = []

    for safe_edge in SAFE_CUT_EDGES:
        if not cmds.objExists(safe_edge):
            continue

        data = get_edge_data(
            safe_edge,
            bbox_min,
            bbox_size,
            bbox_diag
        )

        if data:
            safe_data_list.append(data)

    return safe_data_list


def is_too_close_to_safe_cut(target_data, safe_data_list, margin):
    target_edge = target_data["edge"]

    if target_edge in SAFE_CUT_EDGES:
        return True

    for safe_data in safe_data_list:
        safe_distance = distance(
            target_data["mid_norm"],
            safe_data["mid_norm"]
        )

        same_direction = distance(
            target_data["dir_abs"],
            safe_data["dir_abs"]
        ) < 0.25

        if safe_distance <= margin and same_direction:
            return True

    return False


def build_iteration_solutions():
    global ITERATION_SOLUTIONS
    global CURRENT_ITERATION

    if not STORED_UV_CUT_TEMPLATE:
        cmds.warning("Aucun template mémorisé.")
        return

    faces = get_selected_faces()
    if not faces:
        return

    margin = cmds.floatSliderGrp(margin_slider, q=True, value=True)
    max_iterations = max(1, cmds.intField(max_iterations_field, q=True, value=True))

    bbox_min, bbox_size, bbox_diag = get_selection_bbox(faces)
    candidate_edges = get_edges_from_faces(faces)

    target_edges_data = []

    for edge in candidate_edges:
        data = get_edge_data(edge, bbox_min, bbox_size, bbox_diag)
        if data:
            target_edges_data.append(data)

    safe_data_list = build_safe_edge_data_list(
        bbox_min,
        bbox_size,
        bbox_diag
    )

    all_candidates = []

    for source_cut in STORED_UV_CUT_TEMPLATE["cut_edges"]:
        candidates = []

        for target_data in target_edges_data:
            if is_too_close_to_safe_cut(target_data, safe_data_list, margin):
                continue

            score = edge_score(source_cut, target_data)

            if score <= margin:
                candidates.append({
                    "edge": target_data["edge"],
                    "score": score
                })

        candidates.sort(key=lambda x: x["score"])

        if candidates:
            all_candidates.append(candidates)

    if not all_candidates and not SAFE_CUT_EDGES:
        cmds.warning("Aucun edge candidat trouvé. Augmente la marge.")
        return

    solutions = []

    for iteration_id in range(max_iterations):
        used_edges = set()
        solution_edges = []

        for candidates in all_candidates:
            chosen = None
            start_id = iteration_id % len(candidates)
            ordered_candidates = candidates[start_id:] + candidates[:start_id]

            for candidate in ordered_candidates:
                if candidate["edge"] not in used_edges:
                    chosen = candidate
                    break

            if chosen:
                used_edges.add(chosen["edge"])
                solution_edges.append(chosen["edge"])

        safe_existing = [e for e in SAFE_CUT_EDGES if cmds.objExists(e)]
        final_edges = sorted(list(set(solution_edges + safe_existing)))

        if final_edges and final_edges not in solutions:
            solutions.append(final_edges)

    ITERATION_SOLUTIONS = solutions
    CURRENT_ITERATION = 0

    if not ITERATION_SOLUTIONS:
        cmds.warning("Aucune solution générée.")
        return

    refresh_iteration_slider()
    preview_current_iteration()

    update_status(
        "Solutions générées : {} | Safe cuts inclus : {}".format(
            len(ITERATION_SOLUTIONS),
            len(SAFE_CUT_EDGES)
        )
    )


def refresh_iteration_slider():
    if not iteration_slider:
        return

    count = len(ITERATION_SOLUTIONS)

    cmds.intSliderGrp(
        iteration_slider,
        e=True,
        minValue=1,
        maxValue=max(count, 1),
        fieldMinValue=1,
        fieldMaxValue=max(count, 1),
        value=1
    )


def preview_current_iteration():
    if not ITERATION_SOLUTIONS:
        cmds.warning("Aucune solution à preview.")
        return

    edges = ITERATION_SOLUTIONS[CURRENT_ITERATION]
    edges = [e for e in edges if cmds.objExists(e)]

    if not edges:
        cmds.warning("Iteration vide.")
        return

    cmds.select(edges, replace=True)

    update_status(
        "Preview iteration {} / {} | Edges : {} | Safe : {}".format(
            CURRENT_ITERATION + 1,
            len(ITERATION_SOLUTIONS),
            len(edges),
            len(SAFE_CUT_EDGES)
        )
    )


def set_iteration_from_slider():
    global CURRENT_ITERATION

    if not ITERATION_SOLUTIONS:
        return

    value = cmds.intSliderGrp(iteration_slider, q=True, value=True)
    CURRENT_ITERATION = max(0, min(value - 1, len(ITERATION_SOLUTIONS) - 1))

    preview_current_iteration()


def next_iteration():
    global CURRENT_ITERATION

    if not ITERATION_SOLUTIONS:
        cmds.warning("Génère d'abord les iterations.")
        return

    CURRENT_ITERATION = (CURRENT_ITERATION + 1) % len(ITERATION_SOLUTIONS)

    cmds.intSliderGrp(iteration_slider, e=True, value=CURRENT_ITERATION + 1)
    preview_current_iteration()


def previous_iteration():
    global CURRENT_ITERATION

    if not ITERATION_SOLUTIONS:
        cmds.warning("Génère d'abord les iterations.")
        return

    CURRENT_ITERATION = (CURRENT_ITERATION - 1) % len(ITERATION_SOLUTIONS)

    cmds.intSliderGrp(iteration_slider, e=True, value=CURRENT_ITERATION + 1)
    preview_current_iteration()


def apply_current_iteration():
    if not ITERATION_SOLUTIONS:
        cmds.warning("Aucune iteration à appliquer.")
        return

    edges = ITERATION_SOLUTIONS[CURRENT_ITERATION]
    safe_existing = [e for e in SAFE_CUT_EDGES if cmds.objExists(e)]

    edges = sorted(list(set(edges + safe_existing)))
    existing_edges = [e for e in edges if cmds.objExists(e)]

    if not existing_edges:
        cmds.warning("Aucun edge valide à couper.")
        return

    try:
        cmds.polyMapCut(existing_edges, constructionHistory=False)
    except Exception:
        cmds.select(existing_edges, replace=True)
        try:
            cmds.polyMapCut()
        except Exception as e:
            cmds.warning("Erreur pendant polyMapCut : {}".format(e))
            return

    cmds.select(existing_edges, replace=True)

    cmds.inViewMessage(
        amg="Cuts UV appliqués | Iteration <hl>{}</hl> | Safe cuts <hl>{}</hl>".format(
            CURRENT_ITERATION + 1,
            len(safe_existing)
        ),
        pos="midCenter",
        fade=True
    )

    update_status(
        "Cuts appliqués | Edges totales : {} | Safe cuts : {}".format(
            len(existing_edges),
            len(safe_existing)
        )
    )


def clear_data():
    global STORED_UV_CUT_TEMPLATE
    global ITERATION_SOLUTIONS
    global CURRENT_ITERATION
    global SAFE_CUT_EDGES

    STORED_UV_CUT_TEMPLATE = None
    ITERATION_SOLUTIONS = []
    CURRENT_ITERATION = 0
    SAFE_CUT_EDGES = []

    refresh_iteration_slider()

    update_status("Données effacées.")

    cmds.inViewMessage(
        amg="Données UV Cut Transfer effacées.",
        pos="midCenter",
        fade=True
    )


def build_ui():
    global margin_slider
    global iteration_slider
    global max_iterations_field
    global status_text

    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(
        WINDOW_NAME,
        title="UV Cut Transfer Tool - Safe Cuts",
        sizeable=True,
        resizeToFitChildren=False,
        widthHeight=(450, 430)
    )

    main_layout = cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=8,
        columnAttach=("both", 10)
    )

    cmds.text(
        label="1. Sélectionne les faces source avec les cuts UV",
        align="left"
    )

    cmds.button(
        label="Store UV Cuts From Selection",
        height=35,
        command=lambda *_: store_uv_cuts_from_selection()
    )

    cmds.separator(height=8, style="in")

    cmds.text(
        label="2. Sélectionne les faces cible proches",
        align="left"
    )

    margin_slider = cmds.floatSliderGrp(
        label="Match Margin",
        field=True,
        minValue=0.01,
        maxValue=1.0,
        fieldMinValue=0.001,
        fieldMaxValue=10.0,
        value=DEFAULT_MATCH_MARGIN,
        precision=3,
        columnWidth3=(100, 60, 220),
        adjustableColumn=3
    )

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(260, 80)
    )

    cmds.text(
        label="Nombre max d'iterations",
        align="left"
    )

    max_iterations_field = cmds.intField(
        value=DEFAULT_MAX_ITERATIONS,
        minValue=1
    )

    cmds.setParent(main_layout)

    cmds.button(
        label="Generate Iterations / Preview Best",
        height=35,
        command=lambda *_: build_iteration_solutions()
    )

    iteration_slider = cmds.intSliderGrp(
        label="Iteration",
        field=True,
        minValue=1,
        maxValue=1,
        fieldMinValue=1,
        fieldMaxValue=1,
        value=1,
        columnWidth3=(100, 60, 220),
        adjustableColumn=3,
        changeCommand=lambda *_: set_iteration_from_slider()
    )

    cmds.rowLayout(
        numberOfColumns=2,
        adjustableColumn=1,
        columnWidth2=(210, 210)
    )

    cmds.button(
        label="Previous",
        height=32,
        command=lambda *_: previous_iteration()
    )

    cmds.button(
        label="Next",
        height=32,
        command=lambda *_: next_iteration()
    )

    cmds.setParent(main_layout)

    cmds.separator(height=8, style="in")

    cmds.text(
        label="Safe UV Cuts : edges forcées sur la cible",
        align="left"
    )

    cmds.rowLayout(
        numberOfColumns=3,
        adjustableColumn=1,
        columnWidth3=(150, 150, 150)
    )

    cmds.button(
        label="Add Safe UV Cut Edges",
        height=32,
        command=lambda *_: add_safe_cut_edges()
    )

    cmds.button(
        label="Select Safe",
        height=32,
        command=lambda *_: select_safe_cut_edges()
    )

    cmds.button(
        label="Clear Safe",
        height=32,
        command=lambda *_: clear_safe_cut_edges()
    )

    cmds.setParent(main_layout)

    cmds.button(
        label="Apply Current Iteration",
        height=40,
        backgroundColor=(0.35, 0.55, 0.35),
        command=lambda *_: apply_current_iteration()
    )

    cmds.separator(height=8, style="in")

    cmds.button(
        label="Clear All Stored Data",
        height=28,
        command=lambda *_: clear_data()
    )

    status_text = cmds.text(
        label="Aucune donnée mémorisée.",
        align="left",
        height=40,
        wordWrap=True
    )

    cmds.showWindow(WINDOW_NAME)


build_ui()