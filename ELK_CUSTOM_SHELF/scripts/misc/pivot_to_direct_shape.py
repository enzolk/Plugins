# ELK_META {"label": "Pivot To Direct Shape", "short_name": "PivotP", "tooltip": "Replace le pivot des transforms sélectionnés en utilisant uniquement les shapes directes du parent, sans prendre en compte les enfants ou descendants.", "source": "python", "icon_svg": "target.svg", "icon_color": "#ff5d3b"}
import maya.cmds as cmds


def get_direct_shapes_bbox(transform):
    """
    Calcule la bounding box uniquement à partir des shapes directes du transform.
    Ignore totalement les enfants / descendants.
    """
    shapes = cmds.listRelatives(
        transform,
        shapes=True,
        noIntermediate=True,
        fullPath=True
    ) or []

    valid_bboxes = []

    for shape in shapes:
        try:
            bbox = cmds.exactWorldBoundingBox(shape)
            valid_bboxes.append(bbox)
        except:
            pass

    if not valid_bboxes:
        return None

    min_x = min(b[0] for b in valid_bboxes)
    min_y = min(b[1] for b in valid_bboxes)
    min_z = min(b[2] for b in valid_bboxes)

    max_x = max(b[3] for b in valid_bboxes)
    max_y = max(b[4] for b in valid_bboxes)
    max_z = max(b[5] for b in valid_bboxes)

    return (
        min_x, min_y, min_z,
        max_x, max_y, max_z
    )


def reset_pivot_selected_parents_independently():
    selection = cmds.ls(selection=True, long=True, type="transform")

    if not selection:
        cmds.warning("Sélectionne au moins un transform.")
        return

    # Important :
    # On garde exactement les objets sélectionnés.
    # On ne filtre pas les enfants sélectionnés.
    # Donc Locator_01, Locator_02 et Locator_03 seront tous traités séparément.
    for obj in selection:
        bbox = get_direct_shapes_bbox(obj)

        if bbox is None:
            cmds.warning(
                "Aucune shape directe trouvée pour : {} | enfants ignorés.".format(obj)
            )
            continue

        min_x, min_y, min_z, max_x, max_y, max_z = bbox

        center = (
            (min_x + max_x) * 0.5,
            (min_y + max_y) * 0.5,
            (min_z + max_z) * 0.5
        )

        cmds.xform(
            obj,
            worldSpace=True,
            pivots=center
        )

        print("[PIVOT RESET - DIRECT SHAPE ONLY] {}".format(obj))

    print("Done.")


reset_pivot_selected_parents_independently()