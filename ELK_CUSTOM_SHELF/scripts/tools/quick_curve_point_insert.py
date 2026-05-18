# ELK_META {"label": "Quick Curve Point Insert", "short_name": "CVAdd", "tooltip": "Ajoute rapidement des points sur une courbe NURBS sélectionnée.", "source": "python", "icon_svg": "point.svg", "icon_color": "#36d6ff", "apply_elk_ui_style": false, "quick_favorite": false, "secondary_scripts": []}
# -*- coding: utf-8 -*-
import re
import maya.cmds as cmds
import maya.mel as mel


BEZIER_STEP = 3


def _selected_cvs():
    result = []
    for s in cmds.ls(sl=True, fl=True) or []:
        m = re.match(r"(.+)\.cv\[(\d+)\]$", s)
        if m:
            result.append((m.group(1), int(m.group(2))))
    return result


def _shape_transform(node):
    if cmds.nodeType(node) in ("nurbsCurve", "bezierCurve"):
        shape = node
        parent = cmds.listRelatives(shape, p=True, f=True) or []
        return shape, parent[0] if parent else None

    shapes = cmds.listRelatives(node, s=True, f=True) or []
    for s in shapes:
        if cmds.nodeType(s) in ("nurbsCurve", "bezierCurve"):
            return s, node

    return None, None


def _is_bezier(shape):
    return cmds.nodeType(shape) == "bezierCurve"


def _cvs(shape):
    return cmds.ls(shape + ".cv[*]", fl=True) or []


def _pos(cv):
    return cmds.xform(cv, q=True, ws=True, t=True)


def _cv_pos(shape, index):
    return _pos("%s.cv[%d]" % (shape, index))


def _mid(a, b):
    return [(a[i] + b[i]) * 0.5 for i in range(3)]


def _dist2(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def _anchor_indices(count):
    return [i for i in range(count) if i % BEZIER_STEP == 0]


def _last_anchor_index(count):
    anchors = _anchor_indices(count)
    return anchors[-1] if anchors else count - 1


def _append_point(transform, p):
    try:
        cmds.curve(transform, a=True, p=p)
        return True
    except Exception:
        try:
            cmds.select(transform, r=True)
            cmds.curve(a=True, p=p)
            return True
        except Exception:
            try:
                mel.eval(
                    'curve -a -p {0} {1} {2} "{3}";'.format(
                        p[0], p[1], p[2], transform
                    )
                )
                return True
            except Exception:
                return False


def _extend_bezier_end(shape, transform, selected_anchor_index):
    count = len(_cvs(shape))

    if selected_anchor_index % BEZIER_STEP != 0:
        cmds.warning(
            "Sur une Bezier, sélectionne un point principal/anchor : cv[0], cv[3], cv[6], cv[9], etc."
        )
        return None

    last_anchor = _last_anchor_index(count)

    if selected_anchor_index != last_anchor:
        cmds.warning("Pour étendre une Bezier, sélectionne le dernier anchor de la curve.")
        return None

    current = _cv_pos(shape, last_anchor)

    prev_anchor = last_anchor - BEZIER_STEP
    if prev_anchor >= 0:
        previous = _cv_pos(shape, prev_anchor)
    else:
        previous = [current[0] - 1.0, current[1], current[2]]

    direction = [
        current[0] - previous[0],
        current[1] - previous[1],
        current[2] - previous[2],
    ]

    handle_1 = [
        current[0] + direction[0] / 3.0,
        current[1] + direction[1] / 3.0,
        current[2] + direction[2] / 3.0,
    ]

    handle_2 = [
        current[0] + direction[0] * 2.0 / 3.0,
        current[1] + direction[1] * 2.0 / 3.0,
        current[2] + direction[2] * 2.0 / 3.0,
    ]

    new_anchor = [
        current[0] + direction[0],
        current[1] + direction[1],
        current[2] + direction[2],
    ]

    before_count = len(_cvs(shape))

    for p in (handle_1, handle_2, new_anchor):
        if not _append_point(transform, p):
            cmds.warning("Impossible d'ajouter un CV à la Bezier.")
            return None

    shape, transform = _shape_transform(transform)
    after_count = len(_cvs(shape))

    if after_count <= before_count:
        cmds.warning("Aucun CV n'a été ajouté.")
        return None

    new_anchor_index = last_anchor + BEZIER_STEP
    new_cv = "%s.cv[%d]" % (shape, new_anchor_index)

    if cmds.objExists(new_cv):
        cmds.select(new_cv, r=True)
        return new_cv

    return None


def _nearest_param(transform, pos):
    shape = cmds.listRelatives(transform, s=True, f=True)[0]

    node = cmds.createNode("nearestPointOnCurve")
    cmds.connectAttr(shape + ".worldSpace[0]", node + ".inputCurve", f=True)
    cmds.setAttr(node + ".inPosition", pos[0], pos[1], pos[2], type="double3")

    param = cmds.getAttr(node + ".parameter")
    cmds.delete(node)

    return param


def _closest_anchor(shape, target_pos):
    cvs = _cvs(shape)
    count = len(cvs)

    best = None
    best_dist = 999999999.0

    for i in _anchor_indices(count):
        cv = "%s.cv[%d]" % (shape, i)
        if not cmds.objExists(cv):
            continue

        d = _dist2(_pos(cv), target_pos)

        if d < best_dist:
            best_dist = d
            best = cv

    return best


def _closest_cv(shape, target_pos):
    best = None
    best_dist = 999999999.0

    for cv in _cvs(shape):
        d = _dist2(_pos(cv), target_pos)

        if d < best_dist:
            best_dist = d
            best = cv

    return best


def add_cv_to_selected_curve():
    selected = _selected_cvs()

    if len(selected) not in (1, 2):
        cmds.warning("Sélectionne 1 ou 2 CV d'une curve.")
        return

    curve_node = selected[0][0]

    if any(c[0] != curve_node for c in selected):
        cmds.warning("Les CV doivent appartenir à la même curve.")
        return

    shape, transform = _shape_transform(curve_node)

    if not shape or not transform:
        cmds.warning("Curve invalide.")
        return

    is_bezier = _is_bezier(shape)
    count = len(_cvs(shape))
    indices = sorted([i for _, i in selected])

    if count < 2:
        cmds.warning("La curve doit avoir au moins 2 CV.")
        return

    # ---------------------------------------------------------
    # Cas BEZIER
    # ---------------------------------------------------------
    if is_bezier:
        for i in indices:
            if i % BEZIER_STEP != 0:
                cmds.warning(
                    "Sur une Bezier, sélectionne uniquement les anchors : cv[0], cv[3], cv[6], cv[9], etc."
                )
                return

        if len(indices) == 1:
            i = indices[0]
            last_anchor = _last_anchor_index(count)

            # Dernier anchor : vraie extension Bezier
            if i == last_anchor:
                new_cv = _extend_bezier_end(shape, transform, i)
                print("[Curve CV Inserter] Anchor Bezier ajouté :", new_cv)
                return

            # Sinon midpoint entre cet anchor et le suivant
            next_anchor = i + BEZIER_STEP

            if next_anchor >= count:
                cmds.warning("Impossible de trouver l'anchor suivant.")
                return

            new_pos = _mid(_cv_pos(shape, i), _cv_pos(shape, next_anchor))

        else:
            a, b = indices
            new_pos = _mid(_cv_pos(shape, a), _cv_pos(shape, b))

        try:
            param = _nearest_param(transform, new_pos)

            cmds.insertKnotCurve(
                transform,
                ch=False,
                rpo=True,
                p=param
            )

            shape, transform = _shape_transform(transform)

            new_anchor = _closest_anchor(shape, new_pos)

            if not new_anchor:
                cmds.warning("Impossible d'identifier le nouvel anchor Bezier.")
                return

            cmds.xform(new_anchor, ws=True, t=new_pos)
            cmds.select(new_anchor, r=True)

            print("[Curve CV Inserter] Anchor Bezier ajouté au midpoint :", new_anchor)
            return

        except Exception as e:
            cmds.warning("Impossible d'insérer un anchor Bezier : %s" % e)
            return

    # ---------------------------------------------------------
    # Cas NURBS classique
    # ---------------------------------------------------------
    points = [_pos(cv) for cv in _cvs(shape)]

    if len(indices) == 1:
        i = indices[0]

        if i == count - 1:
            p0 = points[i]
            p1 = points[i - 1]

            new_pos = [
                p0[0] + (p0[0] - p1[0]),
                p0[1] + (p0[1] - p1[1]),
                p0[2] + (p0[2] - p1[2]),
            ]

            if not _append_point(transform, new_pos):
                cmds.warning("Impossible d'étendre la NURBS curve.")
                return

            shape, transform = _shape_transform(transform)
            new_cv = _closest_cv(shape, new_pos)
            cmds.select(new_cv, r=True)

            print("[Curve CV Inserter] CV NURBS ajouté en extension :", new_cv)
            return

        new_pos = _mid(points[i], points[i + 1])

    else:
        a, b = indices
        new_pos = _mid(points[a], points[b])

    try:
        param = _nearest_param(transform, new_pos)

        cmds.insertKnotCurve(
            transform,
            ch=False,
            rpo=True,
            p=param
        )

        shape, transform = _shape_transform(transform)
        new_cv = _closest_cv(shape, new_pos)

        cmds.xform(new_cv, ws=True, t=new_pos)
        cmds.select(new_cv, r=True)

        print("[Curve CV Inserter] CV NURBS ajouté :", new_cv)

    except Exception as e:
        cmds.warning("Impossible d'ajouter le CV : %s" % e)


add_cv_to_selected_curve()