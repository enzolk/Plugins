# ELK_META {"label": "Clean Combine Preserve Pivot", "short_name": "CombPV", "tooltip": "Combine plusieurs meshes tout en conservant le pivot, le nom et la position dans la hiérarchie. Nettoie également les groupes temporaires et les transforms.", "source": "python", "icon_svg": "arrow-merge-both.svg", "icon_color": "#ff5d3b"}
import maya.cmds as cmds


def clean_temp_null_groups():
    temp_groups = cmds.ls("temp_null_group*", long=True) or []

    for grp in temp_groups:
        if cmds.objExists(grp):
            try:
                cmds.delete(grp)
            except:
                pass


def merge_and_preserve_pivot():
    selected_objects = cmds.ls(selection=True, type="transform", long=True) or []

    if not selected_objects:
        cmds.warning("Aucun objet transform sélectionné.")
        return

    first_obj = selected_objects[0]

    parent = cmds.listRelatives(first_obj, parent=True, fullPath=True)
    parent = parent[0] if parent else None

    if parent:
        siblings = cmds.listRelatives(parent, children=True, type="transform", fullPath=True) or []
    else:
        siblings = cmds.ls(assemblies=True, long=True) or []

    try:
        original_index = siblings.index(first_obj)
    except ValueError:
        original_index = 0

    original_pivot = cmds.xform(first_obj, query=True, worldSpace=True, rotatePivot=True)
    original_name = first_obj.split("|")[-1]

    try:
        combined_mesh = cmds.polyUnite(
            selected_objects,
            ch=False,
            mergeUVSets=True,
            name=original_name
        )[0]
    except Exception as e:
        cmds.error("Erreur pendant le combine : {}".format(e))
        return

    combined_mesh = cmds.ls(combined_mesh, long=True)[0]

    try:
        cmds.delete(combined_mesh, ch=True)
    except:
        pass

    try:
        cmds.makeIdentity(combined_mesh, apply=True, t=1, r=1, s=1, n=0)
    except Exception as e:
        cmds.warning("Freeze transform impossible : {}".format(e))

    if parent:
        try:
            combined_mesh = cmds.parent(combined_mesh, parent)[0]
        except Exception as e:
            cmds.warning("Impossible de reparenter l'objet : {}".format(e))
    else:
        try:
            combined_mesh = cmds.parent(combined_mesh, world=True)[0]
        except:
            pass

    combined_mesh = cmds.ls(combined_mesh, long=True)[0]

    try:
        short_name = combined_mesh.split("|")[-1]
        if short_name != original_name:
            combined_mesh = cmds.rename(combined_mesh, original_name)
            combined_mesh = cmds.ls(combined_mesh, long=True)[0]
    except Exception as e:
        cmds.warning("Impossible de renommer en '{}': {}".format(original_name, e))

    try:
        cmds.xform(combined_mesh, worldSpace=True, pivots=original_pivot)
    except Exception as e:
        cmds.warning("Impossible de restaurer le pivot : {}".format(e))

    try:
        cmds.reorder(combined_mesh, front=True)
        if original_index > 0:
            cmds.reorder(combined_mesh, relative=original_index)
    except Exception as e:
        cmds.warning("Impossible de restaurer l'ordre dans la hiérarchie : {}".format(e))

    cmds.select(combined_mesh, replace=True)

    print("Merge terminé : pivot conservé, objet replacé dans la hiérarchie.")


clean_temp_null_groups()

try:
    merge_and_preserve_pivot()
finally:
    clean_temp_null_groups()