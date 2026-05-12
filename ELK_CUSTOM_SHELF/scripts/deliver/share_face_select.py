# ELK_META {"label": "Share Face Select", "short_name": "", "tooltip": "Select faces that share the same space", "source": "python", "icon_svg": "lasso-polygon.svg", "icon_color": "#4bc8ff"}
import maya.cmds as cmds
import math

# ---------- Utilitaires gomtrie ----------
def _round_with_tol(p, eps):
    return (round(p[0] / eps) * eps,
            round(p[1] / eps) * eps,
            round(p[2] / eps) * eps)

def _get_mesh_shape_from_selection():
    sel = cmds.ls(selection=True, dag=True, shapes=True, type='mesh')
    if not sel:
        sel_tr = cmds.ls(selection=True, type='transform')
        if len(sel_tr) != 1:
            cmds.warning("Slectionne exactement un mesh (transform ou shape).")
            return None
        shapes = cmds.listRelatives(sel_tr[0], s=True, fullPath=True, type='mesh') or []
        if not shapes:
            cmds.warning("Objet slectionn invalide (pas de mesh).")
            return None
        return shapes[0]
    if len(sel) > 1:
        cmds.warning("Plusieurs meshes slectionns  je prends le premier.")
    return sel[0]

def _cache_vertex_positions(mesh_shape):
    vtx_count = cmds.polyEvaluate(mesh_shape, vertex=True)
    if not vtx_count:
        return {}
    vtx_comps = [f"{mesh_shape}.vtx[{i}]" for i in range(vtx_count)]
    flat = cmds.xform(vtx_comps, q=True, ws=True, t=True)
    return {i: (flat[3*i], flat[3*i+1], flat[3*i+2]) for i in range(vtx_count)}

def _face_vertices_indices(mesh_shape, face_index):
    info = cmds.polyInfo(f"{mesh_shape}.f[{face_index}]", faceToVertex=True)
    if not info:
        return []
    tokens = info[0].replace(',', ' ').split()
    vtx_ids = []
    for tok in tokens:
        try:
            vtx_ids.append(int(tok))
        except:
            pass
    return vtx_ids

def _dedupe_positions_with_tol(positions, eps):
    seen = set()
    out = []
    for p in positions:
        q = _round_with_tol(p, eps)
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out

def get_face_signature(mesh_shape, face_index, vtx_pos_cache, eps):
    vtx_ids = _face_vertices_indices(mesh_shape, face_index)
    if not vtx_ids:
        return None
    positions = [vtx_pos_cache[i] for i in vtx_ids]
    q_positions = _dedupe_positions_with_tol(positions, eps)
    q_positions.sort()  # insensible  l'ordre
    return tuple(q_positions)

# ---------- Logique de slection ----------
def find_identical_faces(mesh_shape, tolerance):
    face_count = cmds.polyEvaluate(mesh_shape, face=True)
    if not face_count or face_count < 2:
        cmds.warning("Mesh trop petit ou invalide.")
        return []

    vtx_pos_cache = _cache_vertex_positions(mesh_shape)
    groups = {}
    for f in range(face_count):
        sig = get_face_signature(mesh_shape, f, vtx_pos_cache, eps=tolerance)
        if sig is None:
            continue
        groups.setdefault(sig, []).append(f)

    # Ne garder que les groupes avec au moins 2 faces identiques
    dup_groups = [inds for inds in groups.values() if len(inds) > 1]
    return dup_groups

def select_identical_faces(tolerance=0.01, select_all=False):
    mesh_shape = _get_mesh_shape_from_selection()
    if not mesh_shape:
        return

    dup_groups = find_identical_faces(mesh_shape, tolerance)
    if not dup_groups:
        cmds.warning("Aucune face identique trouve (tolrance = {}).".format(tolerance))
        return

    if select_all:
        chosen = [f"{mesh_shape}.f[{i}]" for group in dup_groups for i in group]
    else:
        chosen = [f"{mesh_shape}.f[{group[0]}]" for group in dup_groups]

    cmds.select(chosen, r=True)
    mode = "toutes les faces des groupes" if select_all else "1 face par groupe"
    print("Tolrance utilise:", tolerance)
    print("Mode:", mode)
    print("Slection:", chosen)

# ---------- Interface utilisateur ----------
def show_identical_faces_ui():
    if cmds.window("identicalFacesWin", exists=True):
        cmds.deleteUI("identicalFacesWin")

    win = cmds.window("identicalFacesWin", title="Faces identiques - Tolrance", sizeable=False)
    col = cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAlign="center")

    cmds.text(label="Tolrance (monde) :", align="center")
    # floatSliderGrp avec champ de saisie (field=True) pour valeurs prcises comme 0.0025
    tol_grp = cmds.floatSliderGrp(
        "tolSliderGrp",
        field=True,
        minValue=0.0001,
        maxValue=1.0,
        value=0.01,
        fieldMinValue=0.000001,  # autorise la saisie en dessous si besoin
        fieldMaxValue=100.0,     # autorise la saisie plus large si besoin
        precision=6,             # affichage lisible 0.002500
        step=0.0001              # pas du slider; la saisie texte permet du plus fin
    )

    # Boutons de presets pratiques
    row = cmds.rowLayout(numberOfColumns=5, adjustableColumn=5, columnAlign=(1, "center"))
    for preset in (0.1, 0.01, 0.005, 0.0025):
        cmds.button(label=str(preset),
                    c=lambda *_ , v=preset: cmds.floatSliderGrp(tol_grp, e=True, value=v))
    cmds.setParent('..')

    # Option slectionner tout le groupe
    sel_all_chk = cmds.checkBox("selAllChk", label="Slectionner TOUTES les faces de chaque groupe", value=False)

    # Bouton d'action
    def _run(*args):
        tol = cmds.floatSliderGrp(tol_grp, q=True, value=True)
        select_all = cmds.checkBox(sel_all_chk, q=True, value=True)
        # clamp minimal de scurit
        tol = max(1e-8, float(tol))
        select_identical_faces(tolerance=tol, select_all=select_all)

    cmds.button(label="Dtecter & Slectionner", command=_run, bgc=(0.3, 0.6, 0.3), height=30)
    cmds.separator(h=8, style='in')
    cmds.text(label="Astuce : utilise le champ texte pour entrer des valeurs fines (ex : 0.0025).", align="center")
    cmds.showWindow(win)

# Lancer l'UI
show_identical_faces_ui()