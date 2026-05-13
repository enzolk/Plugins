# ELK_META {"label": "Random Bend Deformer", "short_name": "BendRnd", "tooltip": "Outil de déformation procédurale qui ajoute automatiquement des cuts sur un mesh selon sa bounding box, applique des offsets aléatoires lissés puis génère un Bend Deformer contrôlable.", "source": "python", "icon_svg": "brand-terraform.svg", "icon_color": "#ff5d3b"}
import maya.cmds as cmds
import random
import math

WINDOW_NAME = "randomBendDeformUI"


def get_selected_object():
    sel = cmds.ls(selection=True, long=True)
    return sel[0] if sel else None


def get_longest_bb_axis(obj):
    bbox = cmds.exactWorldBoundingBox(obj)
    min_x, min_y, min_z, max_x, max_y, max_z = bbox

    sizes = {
        "x": max_x - min_x,
        "y": max_y - min_y,
        "z": max_z - min_z
    }

    longest_axis = max(sizes, key=sizes.get)
    return longest_axis, sizes[longest_axis], bbox


def update_cut_preview(*args):
    obj = get_selected_object()

    if not obj:
        cmds.text("cutPreviewText", e=True, label="Cuts prévus : aucun objet sélectionné")
        return

    spacing = cmds.floatField("cutSpacingField", q=True, value=True)

    if spacing <= 0:
        cmds.text("cutPreviewText", e=True, label="Distance invalide")
        return

    axis, length, bbox = get_longest_bb_axis(obj)
    cut_count = max(0, int(math.floor(length / spacing)))

    cmds.text(
        "cutPreviewText",
        e=True,
        label="Cuts prévus : {} | Axe : {} | Longueur BB : {:.3f}".format(
            cut_count,
            axis.upper(),
            length
        )
    )


def create_random_bend_deform():
    obj = get_selected_object()

    if not obj:
        cmds.warning("Sélectionne un objet.")
        return

    cut_spacing = cmds.floatField("cutSpacingField", q=True, value=True)

    percent_min = cmds.floatField("percentMinField", q=True, value=True) / 100.0
    percent_max = cmds.floatField("percentMaxField", q=True, value=True) / 100.0

    offset_min = cmds.floatField("offsetMinField", q=True, value=True)
    offset_max = cmds.floatField("offsetMaxField", q=True, value=True)

    smooth_variation = cmds.floatField("smoothVariationField", q=True, value=True)

    use_offset_x = cmds.checkBox("offsetXCheck", q=True, value=True)
    use_offset_y = cmds.checkBox("offsetYCheck", q=True, value=True)
    use_offset_z = cmds.checkBox("offsetZCheck", q=True, value=True)

    curvature_min = cmds.floatField("curvatureMinField", q=True, value=True)
    curvature_max = cmds.floatField("curvatureMaxField", q=True, value=True)

    highbound_min = cmds.floatField("highBoundMinField", q=True, value=True)
    highbound_max = cmds.floatField("highBoundMaxField", q=True, value=True)

    bend_rot_x = cmds.floatField("bendRotXField", q=True, value=True)
    bend_rot_y = cmds.floatField("bendRotYField", q=True, value=True)
    bend_rot_z = cmds.floatField("bendRotZField", q=True, value=True)

    if cut_spacing <= 0:
        cmds.warning("La distance entre cuts doit être supérieure à 0.")
        return

    if not use_offset_x and not use_offset_y and not use_offset_z:
        cmds.warning("Choisis au moins un axe d'offset : X, Y ou Z.")
        return

    if percent_min > percent_max:
        percent_min, percent_max = percent_max, percent_min

    if offset_min > offset_max:
        offset_min, offset_max = offset_max, offset_min

    if curvature_min > curvature_max:
        curvature_min, curvature_max = curvature_max, curvature_min

    if highbound_min > highbound_max:
        highbound_min, highbound_max = highbound_max, highbound_min

    longest_axis, length, bbox = get_longest_bb_axis(obj)
    loop_count = max(0, int(math.floor(length / cut_spacing)))

    min_x, min_y, min_z, max_x, max_y, max_z = bbox

    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    center_z = (min_z + max_z) / 2.0

    if longest_axis == "x":
        start = min_x
        cut_rotation = (0, 90, 0)
    elif longest_axis == "y":
        start = min_y
        cut_rotation = (90, 0, 0)
    else:
        start = min_z
        cut_rotation = (0, 0, 0)

    created_loop_positions = []

    for i in range(1, loop_count + 1):
        t = start + (length / (loop_count + 1)) * i
        created_loop_positions.append(t)

        if longest_axis == "x":
            cut_center = (t, center_y, center_z)
        elif longest_axis == "y":
            cut_center = (center_x, t, center_z)
        else:
            cut_center = (center_x, center_y, t)

        cmds.polyCut(
            obj,
            ch=True,
            pc=cut_center,
            ro=cut_rotation,
            ef=False,
            df=False
        )

    if created_loop_positions:
        percent = random.uniform(percent_min, percent_max)

        loop_amount = max(1, int(round(loop_count * percent)))
        loop_amount = min(loop_amount, len(created_loop_positions))

        selected_loop_positions = sorted(
            random.sample(created_loop_positions, loop_amount)
        )

        tolerance = length / (loop_count + 1) * 0.15
        verts = cmds.ls(obj + ".vtx[*]", flatten=True)

        current_offset = random.uniform(offset_min, offset_max)

        for loop_pos in selected_loop_positions:
            variation = random.uniform(-smooth_variation, smooth_variation)

            current_offset += variation
            current_offset = max(offset_min, min(offset_max, current_offset))

            move_x = current_offset if use_offset_x else 0
            move_y = current_offset if use_offset_y else 0
            move_z = current_offset if use_offset_z else 0

            verts_to_move = []

            for vtx in verts:
                pos = cmds.xform(vtx, q=True, ws=True, t=True)

                axis_pos = {
                    "x": pos[0],
                    "y": pos[1],
                    "z": pos[2]
                }[longest_axis]

                if abs(axis_pos - loop_pos) <= tolerance:
                    verts_to_move.append(vtx)

            if verts_to_move:
                cmds.move(
                    move_x,
                    move_y,
                    move_z,
                    verts_to_move,
                    relative=True,
                    worldSpace=True
                )

    random_curvature = random.uniform(curvature_min, curvature_max)
    random_highbound = random.uniform(highbound_min, highbound_max)

    bend, handle = cmds.nonLinear(
        obj,
        type="bend",
        lowBound=0,
        highBound=random_highbound,
        curvature=random_curvature
    )

    pos = cmds.xform(obj, q=True, ws=True, rp=True)
    cmds.xform(handle, ws=True, t=pos)

    rot = cmds.xform(obj, q=True, ws=True, rotation=True)
    cmds.xform(handle, ws=True, rotation=rot)

    cmds.rotate(
        bend_rot_x,
        bend_rot_y,
        bend_rot_z,
        handle,
        r=True,
        os=True
    )

    cmds.select(obj)

    print("--------------------------------------------------")
    print("Random Bend Created")
    print("Object :", obj)
    print("Axis :", longest_axis)
    print("BB Length :", length)
    print("Cuts :", loop_count)
    print("Offset Axis X :", use_offset_x)
    print("Offset Axis Y :", use_offset_y)
    print("Offset Axis Z :", use_offset_z)
    print("Curvature :", random_curvature)
    print("High Bound :", random_highbound)
    print("--------------------------------------------------")


def show_random_bend_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(WINDOW_NAME, title="Random Bend Deformer", widthHeight=(430, 700))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)

    cmds.text(label="Random Bend Deformer", align="center", height=30)
    cmds.separator(height=8)

    cmds.text(label="Cuts selon la Bounding Box", align="left")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Distance entre cuts")
    cmds.floatField("cutSpacingField", value=50.0, precision=3, changeCommand=update_cut_preview)
    cmds.setParent("..")

    cmds.text("cutPreviewText", label="Sélectionne un objet", align="left")

    cmds.button(label="Update Cut Preview", height=28, command=update_cut_preview)

    cmds.separator(height=10)

    cmds.text(label="Déformation lissée des loops", align="left")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="% loops min")
    cmds.floatField("percentMinField", value=10.0, precision=2)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="% loops max")
    cmds.floatField("percentMaxField", value=70.0, precision=2)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Offset min")
    cmds.floatField("offsetMinField", value=-10.0, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Offset max")
    cmds.floatField("offsetMaxField", value=10.0, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Smooth variation")
    cmds.floatField("smoothVariationField", value=2.0, precision=3)
    cmds.setParent("..")

    cmds.text(label="Offset Axis", align="left")

    cmds.rowLayout(numberOfColumns=3)
    cmds.checkBox("offsetXCheck", label="X", value=False)
    cmds.checkBox("offsetYCheck", label="Y", value=True)
    cmds.checkBox("offsetZCheck", label="Z", value=False)
    cmds.setParent("..")

    cmds.separator(height=10)

    cmds.text(label="Bend Settings", align="left")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Curvature min")
    cmds.floatField("curvatureMinField", value=-8.0, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Curvature max")
    cmds.floatField("curvatureMaxField", value=8.0, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="High Bound min")
    cmds.floatField("highBoundMinField", value=0.75, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="High Bound max")
    cmds.floatField("highBoundMaxField", value=10.0, precision=3)
    cmds.setParent("..")

    cmds.separator(height=10)

    cmds.text(label="Bend Direction Offset", align="left")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Rotate X")
    cmds.floatField("bendRotXField", value=90.0, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Rotate Y")
    cmds.floatField("bendRotYField", value=0.0, precision=3)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, adjustableColumn=2)
    cmds.text(label="Rotate Z")
    cmds.floatField("bendRotZField", value=90.0, precision=3)
    cmds.setParent("..")

    cmds.separator(height=10)

    cmds.button(
        label="Create Random Bend",
        height=42,
        command=lambda *_: create_random_bend_deform()
    )

    cmds.showWindow(WINDOW_NAME)
    update_cut_preview()


show_random_bend_ui()