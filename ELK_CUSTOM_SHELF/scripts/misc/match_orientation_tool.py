# ELK_META {"label": "Match Orientation Tool", "short_name": "MatchT", "tooltip": "Aligne automatiquement l’orientation d’un objet sur un autre via analyse PCA, ICP et matching spatial avancé tout en conservant les pivots", "source": "python", "icon_svg": "clipboard-copy.svg", "icon_color": "#ff5d3b"}
import maya.cmds as cmds
import maya.api.OpenMaya as om
import numpy as np
import itertools
import time
 
 
MAX_SAMPLE_POINTS = 800
ICP_ITERATIONS = 25
VERBOSE_LOGS = True
 
 
# ------------------------------------------------------------
# Units
# ------------------------------------------------------------
 
UNIT_TO_CM = {
    "mm": 0.1,
    "millimeter": 0.1,
    "cm": 1.0,
    "centimeter": 1.0,
    "m": 100.0,
    "meter": 100.0,
    "km": 100000.0,
    "kilometer": 100000.0,
    "in": 2.54,
    "inch": 2.54,
    "ft": 30.48,
    "foot": 30.48,
    "yd": 91.44,
    "yard": 91.44,
}
 
 
def get_scene_unit_to_cm():
    unit = cmds.currentUnit(q=True, linear=True)
    return UNIT_TO_CM.get(unit, 1.0)
 
 
def ui_units_to_cm(vec):
    return np.array(vec, dtype=np.float64) * get_scene_unit_to_cm()
 
 
def cm_to_ui_units(vec):
    return np.array(vec, dtype=np.float64) / get_scene_unit_to_cm()
 
 
# ------------------------------------------------------------
# Logs
# ------------------------------------------------------------
 
def log(message):
    if VERBOSE_LOGS:
        print("[MATCH ORIENT] {}".format(message))
 
 
def log_step(title):
    log("")
    log("--------------------------------------------------")
    log(title)
    log("--------------------------------------------------")
 
 
def log_vector(label, vec):
    log("{} : X={:.6f}, Y={:.6f}, Z={:.6f}".format(label, vec[0], vec[1], vec[2]))
 
 
def log_matrix(label, matrix):
    log(label)
    matrix = np.array(matrix)
    rows, cols = matrix.shape
 
    for r in range(rows):
        log("    [{}]".format(", ".join(["{:.6f}".format(matrix[r, c]) for c in range(cols)])))
 
 
# ------------------------------------------------------------
# Utils Maya
# ------------------------------------------------------------
 
def get_mesh_shape(transform):
    shapes = cmds.listRelatives(transform, shapes=True, fullPath=True) or []
 
    for shape in shapes:
        if cmds.nodeType(shape) == "mesh":
            return shape
 
    return None
 
 
def get_world_vertices(transform):
    shape = get_mesh_shape(transform)
    if not shape:
        raise RuntimeError("{} n'est pas un mesh valide.".format(transform))
 
    sel = om.MSelectionList()
    sel.add(shape)
    dag = sel.getDagPath(0)
 
    mesh_fn = om.MFnMesh(dag)
    points = mesh_fn.getPoints(om.MSpace.kWorld)
 
    return np.array([[p.x, p.y, p.z] for p in points], dtype=np.float64)
 
 
def sample_points(points, max_points=MAX_SAMPLE_POINTS):
    if len(points) <= max_points:
        return points.copy()
 
    indices = np.linspace(0, len(points) - 1, max_points).astype(int)
    return points[indices].copy()
 
 
def save_world_pivots(obj):
    log("Sauvegarde des pivots monde pour : {}".format(obj))
 
    unit = cmds.currentUnit(q=True, linear=True)
    factor = get_scene_unit_to_cm()
 
    log("Unité scène : {} | facteur vers cm : {}".format(unit, factor))
 
    rotate_pivot_ui = cmds.xform(obj, q=True, ws=True, rotatePivot=True)
    scale_pivot_ui = cmds.xform(obj, q=True, ws=True, scalePivot=True)
 
    rotate_pivot_cm = ui_units_to_cm(rotate_pivot_ui)
    scale_pivot_cm = ui_units_to_cm(scale_pivot_ui)
 
    log_vector("Rotate Pivot sauvegardé UI", rotate_pivot_ui)
    log_vector("Rotate Pivot sauvegardé CM", rotate_pivot_cm)
    log_vector("Scale Pivot sauvegardé UI", scale_pivot_ui)
    log_vector("Scale Pivot sauvegardé CM", scale_pivot_cm)
 
    return {
        "rotatePivot": rotate_pivot_cm,
        "scalePivot": scale_pivot_cm,
    }
 
 
def restore_world_pivots(obj, pivot_data_cm):
    log("Restauration des pivots monde pour : {}".format(obj))
 
    rotate_pivot_ui = cm_to_ui_units(pivot_data_cm["rotatePivot"])
    scale_pivot_ui = cm_to_ui_units(pivot_data_cm["scalePivot"])
 
    log_vector("Rotate Pivot à restaurer CM", pivot_data_cm["rotatePivot"])
    log_vector("Rotate Pivot à restaurer UI", rotate_pivot_ui)
    log_vector("Scale Pivot à restaurer CM", pivot_data_cm["scalePivot"])
    log_vector("Scale Pivot à restaurer UI", scale_pivot_ui)
 
    cmds.xform(obj, ws=True, preserve=True, rotatePivot=rotate_pivot_ui.tolist())
    cmds.xform(obj, ws=True, preserve=True, scalePivot=scale_pivot_ui.tolist())
 
    log("Pivots restaurés avec succès pour : {}".format(obj))
 
 
def transform_saved_pivots(pivot_data_cm, r, t):
    log("Transformation des pivots sauvegardés de A en centimètres.")
 
    transformed_rotate = apply_transform(np.array([pivot_data_cm["rotatePivot"]]), r, t)[0]
    transformed_scale = apply_transform(np.array([pivot_data_cm["scalePivot"]]), r, t)[0]
 
    log_vector("Rotate Pivot transformé CM", transformed_rotate)
    log_vector("Scale Pivot transformé CM", transformed_scale)
 
    return {
        "rotatePivot": transformed_rotate,
        "scalePivot": transformed_scale,
    }
 
 
def freeze_and_bake_pivot(obj):
    log("Freeze Transform + Center Pivot temporaire sur : {}".format(obj))
 
    cmds.select(obj, r=True)
 
    try:
        cmds.makeIdentity(obj, apply=True, t=True, r=True, s=True, n=False, pn=True)
        log("Freeze transform réussi pour : {}".format(obj))
    except Exception as e:
        cmds.warning("Freeze transform impossible sur {} : {}".format(obj, e))
 
    try:
        cmds.xform(obj, centerPivots=True)
        log("Center pivot temporaire réussi pour : {}".format(obj))
    except Exception as e:
        cmds.warning("Center/Bake pivot impossible sur {} : {}".format(obj, e))
 
 
# ------------------------------------------------------------
# Maths
# ------------------------------------------------------------
 
def nearest_neighbor_bruteforce(source, target):
    nearest = []
    distances = []
    chunk_size = 200
 
    for i in range(0, len(source), chunk_size):
        src_chunk = source[i:i + chunk_size]
 
        diff = src_chunk[:, None, :] - target[None, :, :]
        dist_sq = np.sum(diff * diff, axis=2)
 
        idx = np.argmin(dist_sq, axis=1)
        d = np.sqrt(np.min(dist_sq, axis=1))
 
        nearest.append(target[idx])
        distances.append(d)
 
    return np.vstack(nearest), np.concatenate(distances)
 
 
def best_fit_transform(source, target):
    source_center = np.mean(source, axis=0)
    target_center = np.mean(target, axis=0)
 
    source_centered = source - source_center
    target_centered = target - target_center
 
    h = source_centered.T @ target_centered
 
    u, s, vt = np.linalg.svd(h)
    r = vt.T @ u.T
 
    if np.linalg.det(r) < 0:
        vt[-1, :] *= -1
        r = vt.T @ u.T
 
    t = target_center - r @ source_center
 
    return r, t
 
 
def apply_transform(points, r, t):
    return (r @ points.T).T + t
 
 
def compute_pca_axes(points):
    center = np.mean(points, axis=0)
    centered = points - center
 
    cov = np.cov(centered.T)
    values, vectors = np.linalg.eigh(cov)
 
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
 
    if np.linalg.det(vectors) < 0:
        vectors[:, -1] *= -1
 
    log_vector("Centre PCA CM", center)
    log("Valeurs propres PCA : {:.6f}, {:.6f}, {:.6f}".format(values[0], values[1], values[2]))
    log_matrix("Axes PCA", vectors)
 
    return center, vectors
 
 
def generate_orientation_candidates(a_axes, b_axes):
    candidates = []
 
    permutations = list(itertools.permutations([0, 1, 2]))
    signs = list(itertools.product([-1, 1], repeat=3))
 
    for perm in permutations:
        permuted_a = a_axes[:, perm]
 
        for sign in signs:
            signed_a = permuted_a * np.array(sign)
 
            if np.linalg.det(signed_a) < 0:
                continue
 
            r = b_axes @ signed_a.T
 
            if np.linalg.det(r) > 0:
                candidates.append(r)
 
    log("Candidates valides : {}".format(len(candidates)))
    return candidates
 
 
def score_alignment(source, target):
    _, distances = nearest_neighbor_bruteforce(source, target)
    return np.mean(distances)
 
 
# ------------------------------------------------------------
# Matrix Maya
# ------------------------------------------------------------
 
def get_world_matrix_np(obj):
    m = cmds.xform(obj, q=True, ws=True, matrix=True)
    return np.array(m, dtype=np.float64).reshape((4, 4))
 
 
def set_world_matrix_np(obj, m):
    cmds.xform(obj, ws=True, matrix=m.reshape(16).tolist())
 
 
def build_row_vector_delta_matrix(r_col, t_col):
    m = np.identity(4, dtype=np.float64)
    m[:3, :3] = r_col.T
    m[3, :3] = t_col
    return m
 
 
# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
 
def match_object_a_orientation_to_b():
    start_time = time.time()
 
    log_step("START - Match Object A Orientation To B")
 
    selection = cmds.ls(sl=True, long=True, type="transform") or []
 
    if len(selection) != 2:
        cmds.warning("Sélectionne exactement 2 objets : d'abord Objet A, puis Objet B.")
        return
 
    obj_a = selection[0]
    obj_b = selection[1]
 
    log("Objet A : {}".format(obj_a))
    log("Objet B : {}".format(obj_b))
 
    original_pivots_a = None
    original_pivots_b = None
 
    try:
        log_step("STEP 01 - Sauvegarde des pivots originaux")
        original_pivots_a = save_world_pivots(obj_a)
        original_pivots_b = save_world_pivots(obj_b)
 
        log_step("STEP 02 - Freeze Transform + Center Pivot temporaire")
        freeze_and_bake_pivot(obj_a)
        freeze_and_bake_pivot(obj_b)
 
        log_step("STEP 03 - Récupération des vertices monde en CM")
        points_a = get_world_vertices(obj_a)
        points_b = get_world_vertices(obj_b)
 
        log("Objet A vertices : {}".format(len(points_a)))
        log("Objet B vertices : {}".format(len(points_b)))
 
        log_step("STEP 04 - Échantillonnage")
        sample_a = sample_points(points_a)
        sample_b = sample_points(points_b)
 
        if len(sample_a) < 3 or len(sample_b) < 3:
            cmds.warning("Pas assez de vertices pour calculer un alignement.")
            restore_world_pivots(obj_a, original_pivots_a)
            restore_world_pivots(obj_b, original_pivots_b)
            return
 
        log_step("STEP 05 - PCA")
        center_a, axes_a = compute_pca_axes(sample_a)
        center_b, axes_b = compute_pca_axes(sample_b)
 
        log_step("STEP 06 - Candidates PCA")
        candidates = generate_orientation_candidates(axes_a, axes_b)
 
        best_score = None
        best_r = None
        best_t = None
 
        log_step("STEP 07 - Test candidates")
        for index, r in enumerate(candidates):
            t = center_b - r @ center_a
            transformed = apply_transform(sample_a, r, t)
            score = score_alignment(transformed, sample_b)
 
            log("Candidate {} : score {:.6f}".format(index + 1, score))
 
            if best_score is None or score < best_score:
                best_score = score
                best_r = r
                best_t = t
 
        log("Best score PCA : {:.6f}".format(best_score))
        log_matrix("Best rotation", best_r)
        log_vector("Best translation CM", best_t)
 
        log_step("STEP 08 - ICP")
 
        current_points = apply_transform(sample_a, best_r, best_t)
 
        total_r = best_r.copy()
        total_t = best_t.copy()
 
        for i in range(ICP_ITERATIONS):
            nearest_points, distances = nearest_neighbor_bruteforce(current_points, sample_b)
 
            delta_r, delta_t = best_fit_transform(current_points, nearest_points)
 
            current_points = apply_transform(current_points, delta_r, delta_t)
 
            total_r = delta_r @ total_r
            total_t = delta_r @ total_t + delta_t
 
            log("ICP {} / {} : mean distance {:.6f}".format(
                i + 1,
                ICP_ITERATIONS,
                np.mean(distances)
            ))
 
        final_score = score_alignment(current_points, sample_b)
 
        log("Final score ICP : {:.6f}".format(final_score))
        log_matrix("Rotation finale", total_r)
        log_vector("Translation finale CM", total_t)
 
        log_step("STEP 09 - Application transformation Objet A")
 
        current_matrix = get_world_matrix_np(obj_a)
        delta_matrix = build_row_vector_delta_matrix(total_r, total_t)
        new_matrix = current_matrix @ delta_matrix
 
        set_world_matrix_np(obj_a, new_matrix)
 
        log_step("STEP 10 - Restauration pivots")
 
        transformed_pivots_a = transform_saved_pivots(original_pivots_a, total_r, total_t)
 
        restore_world_pivots(obj_a, transformed_pivots_a)
        restore_world_pivots(obj_b, original_pivots_b)
 
        cmds.select(obj_a, r=True)
 
        elapsed = time.time() - start_time
 
        print("--------------------------------")
        print("Alignement terminé.")
        print("Score initial PCA : {:.6f}".format(best_score))
        print("Score final ICP   : {:.6f}".format(final_score))
        print("Amélioration      : {:.6f}".format(best_score - final_score))
        print("Temps total       : {:.3f} secondes".format(elapsed))
        print("--------------------------------")
 
    except Exception as e:
        cmds.warning("Erreur pendant l'alignement : {}".format(e))
 
        if original_pivots_a is not None:
            restore_world_pivots(obj_a, original_pivots_a)
 
        if original_pivots_b is not None:
            restore_world_pivots(obj_b, original_pivots_b)
 
 
# Exécution
match_object_a_orientation_to_b()