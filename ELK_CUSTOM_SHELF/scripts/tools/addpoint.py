# ELK_META {"label": "AddPoint", "short_name": "", "tooltip": "Add Curve Point Quickly", "source": "python", "icon_svg": "tools-kitchen-2.svg", "icon_color": "#36d6ff"}
import maya.cmds as cmds
import re

def insert_knot_rebuild():
    sel = cmds.ls(sl=True, fl=True)
    if not sel or len(sel) != 1 or ".cv[" not in sel[0]:
        cmds.warning("Veuillez slectionner un seul CV sur une courbe.")
        return

    # Extraire le nom de la courbe et l'index du CV
    match = re.match(r"(.+)\.cv\[(\d+)\]", sel[0])
    if not match:
        cmds.warning("Nom de CV invalide.")
        return

    curve = match.group(1)
    index = int(match.group(2))

    # Obtenir la liste des CV actuels
    cvs = cmds.ls(f"{curve}.cv[*]", fl=True)
    positions = [cmds.pointPosition(cv, world=True) for cv in cvs]
    num_cvs = len(positions)

    # Dterminer les deux points entre lesquels insrer
    if index < num_cvs - 1:
        i1, i2 = index, index + 1
    elif index > 0:
        i1, i2 = index - 1, index
    else:
        cmds.warning("Impossible d'insrer un point ici.")
        return

    # Calculer le point milieu
    mid = [(a + b) / 2.0 for a, b in zip(positions[i1], positions[i2])]

    # Crer nouvelle liste de points avec le point insr
    new_positions = positions[:i2] + [mid] + positions[i2:]

    # Obtenir degr et nom de forme
    degree = cmds.getAttr(curve + ".degree")
    shape = cmds.listRelatives(curve, shapes=True)[0]

    # Supprimer lancienne courbe
    cmds.delete(curve)

    # Crer nouvelle courbe avec mme nom
    new_curve = cmds.curve(p=new_positions, degree=degree, name=curve)
    print(f"Nouvelle courbe cre avec point insr entre CV[{i1}] et CV[{i2}]")

# Excuter
insert_knot_rebuild()