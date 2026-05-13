# ELK_META {"label": "Namespace Cleaner", "short_name": "NameSp", "tooltip": "Supprime automatiquement les namespaces soit sur les objets sélectionnés, soit sur toute la scène Maya. Permet de nettoyer rapidement les imports et références.", "source": "python", "icon_svg": "eraser.svg", "icon_color": "#ff5d3b"}
# ============================================================
# REMOVE NAMESPACES
# ------------------------------------------------------------
# - Si rien n'est sélectionné :
#     -> supprime TOUS les namespaces de la scène
#
# - Si des objets sont sélectionnés :
#     -> supprime uniquement les namespaces
#        des objets sélectionnés
#
# Compatible Maya Python
# ============================================================

import maya.cmds as cmds


# ------------------------------------------------------------
# Remove namespace from selected objects only
# ------------------------------------------------------------
def remove_namespace_from_selection():
    selection = cmds.ls(selection=True, long=True)

    if not selection:
        return False

    processed = []

    for obj in selection:

        short_name = obj.split("|")[-1]

        if ":" not in short_name:
            continue

        new_name = short_name.split(":")[-1]

        try:
            cmds.rename(obj, new_name)
            processed.append(short_name)

        except Exception as e:
            print("Impossible de renommer :", short_name)
            print(e)

    print("Namespaces supprimés sur les objets sélectionnés.")
    return True


# ------------------------------------------------------------
# Remove ALL namespaces from scene
# ------------------------------------------------------------
def remove_all_namespaces():

    namespaces = cmds.namespaceInfo(listOnlyNamespaces=True, recurse=True) or []

    # Ignore default Maya namespaces
    ignored = {"UI", "shared"}

    namespaces = [ns for ns in namespaces if ns not in ignored]

    # Sort deepest first
    namespaces.sort(key=lambda x: x.count(":"), reverse=True)

    for ns in namespaces:

        try:
            cmds.namespace(removeNamespace=ns, mergeNamespaceWithRoot=True)
            print("Namespace supprimé :", ns)

        except Exception as e:
            print("Impossible de supprimer :", ns)
            print(e)

    print("Tous les namespaces ont été supprimés.")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
if not remove_namespace_from_selection():
    remove_all_namespaces()