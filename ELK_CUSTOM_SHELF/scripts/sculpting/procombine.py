# ELK_META {"label": "Clean Combine", "short_name": "ClnCmb", "tooltip": "Combine plusieurs meshes tout en conservant une hiérarchie propre et en appliquant des cleanups.", "source": "python", "icon_svg": "layers-intersect.svg", "icon_color": "#ff5c8a"}
# combine_and_preserve_hierarchy.py
import maya.cmds as cmds
import re

def _get_mesh_transforms_in_selection():
    """Return ordered list of transform nodes that actually carry mesh shapes.
    Expands groups; if a selected transform has no mesh descendants but itself is a mesh, keep it."""
    sel = cmds.ls(selection=True, type='transform') or []
    if not sel:
        cmds.error("Aucun objet slectionn.")
        return []
    out = []
    seen = set()
    for obj in sel:
        # All descendant transforms
        descendants = cmds.listRelatives(obj, allDescendents=True, type='transform') or []
        # Check meshes on each descendant
        for t in descendants + [obj]:
            if t in seen:
                continue
            shapes = cmds.listRelatives(t, shapes=True, noIntermediate=True, type='mesh') or []
            if shapes:
                out.append(t)
                seen.add(t)
    # keep order as discovered
    return out

def combine_and_preserve_hierarchy():
    cmds.undoInfo(openChunk=True)
    try:
        selected_objects = _get_mesh_transforms_in_selection()
        if not selected_objects:
            cmds.error("Aucun mesh valide trouv dans la slection.")
            return

        # Map temp -> original short name (for final rename)
        original_names = {}
        temp_names = []

        # Temporarily rename to avoid conflicts (simple, unique)
        for i, obj in enumerate(selected_objects):
            temp_name = "temp_object_{:04d}".format(i)
            original_names[temp_name] = obj  # store original path/name
            new_name = cmds.rename(obj, temp_name)
            temp_names.append(new_name)

        # Find target (highest polycount) and remember its original parent before we rearrange
        target_name = None
        target_parent = None
        highest_poly = -1
        for t in temp_names:
            if cmds.listRelatives(t, shapes=True, noIntermediate=True, type='mesh'):
                faces = cmds.polyEvaluate(t, face=True)
                if faces > highest_poly:
                    highest_poly = faces
                    target_name = t
        if target_name:
            # parent of target BEFORE temporary grouping
            target_parent = cmds.listRelatives(target_name, parent=True)

        combined_mesh = None
        temp_group = None

        if len(temp_names) == 1:
            # Rien  combiner : on travaille directement sur l'objet
            combined_mesh = temp_names[0]
        else:
            # Cre un groupe temporaire au monde & y parent les objets
            temp_group = cmds.group(empty=True, name="temp_group", world=True)
            try:
                cmds.parent(temp_names, temp_group)
            except Exception as e:
                cmds.warning("chec du parentage dans le groupe temporaire : {}".format(e))

            # Combine
            try:
                combined_mesh = cmds.polyUnite(temp_names, ch=False, mergeUVSets=True, name="combinedMesh#")[0]
            except Exception as e:
                cmds.error("chec du combine (polyUnite) : {}".format(e))
                return

        # Nettoyage : delete history + freeze
        try:
            cmds.delete(combined_mesh, ch=True)
            cmds.makeIdentity(combined_mesh, apply=True, t=1, r=1, s=1, n=0)
        except Exception as e:
            cmds.warning("Nettoyage partiel (delete history / freeze) : {}".format(e))

        # Re-parent vers la hirarchie d'origine du target si connue
        if target_parent:
            try:
                cmds.parent(combined_mesh, target_parent[0])
            except Exception as e:
                cmds.warning("chec du re-parent vers le parent d'origine : {}".format(e))
        else:
            # Au monde sinon
            try:
                cmds.parent(combined_mesh, world=True)
            except Exception as e:
                cmds.warning("chec du parentage au monde : {}".format(e))

        # Supprime le groupe temporaire s'il existe encore
        if temp_group and cmds.objExists(temp_group):
            try:
                cmds.delete(temp_group)
            except Exception as e:
                cmds.warning("chec de suppression du groupe temporaire : {}".format(e))

        # Si le parent n'a plus qu'un enfant (le mesh combin), on "aplati" un niveau
        parent_group = cmds.listRelatives(combined_mesh, parent=True)
        if parent_group:
            children = cmds.listRelatives(parent_group[0], children=True) or []
            if len(children) == 1 and children[0] == combined_mesh:
                grandparent = cmds.listRelatives(parent_group[0], parent=True)
                if grandparent:
                    cmds.parent(combined_mesh, grandparent[0])
                else:
                    cmds.parent(combined_mesh, world=True)
                try:
                    cmds.delete(parent_group[0])
                except Exception as e:
                    cmds.warning("chec de suppression du parent vide : {}".format(e))

        # Dterminer le nom final d'aprs l'objet cible (celui au polycount max)
        # On veut le shortName original, sans suffixe _PartX
        final_name = None
        if target_name:
            original_target = original_names.get(target_name, target_name)
            # Rcuprer uniquement le shortName (sans chemin hirarchique)
            short = original_target.split('|')[-1]
            short = re.sub(r'_Part\d+$', '', short)
            final_name = short

        if final_name:
            try:
                combined_mesh = cmds.rename(combined_mesh, final_name)
            except Exception as e:
                cmds.warning("chec du renommage final '{}': {}".format(final_name, e))

        # Merge vertices lgers (tolrance 0.01)
        try:
            # Assure qu'on vise bien les sommets du shape du transform renomm
            cmds.select("{}.vtx[*]".format(combined_mesh), r=True)
            cmds.polyMergeVertex(d=0.01, am=1, ch=1)
        except Exception as e:
            cmds.warning("chec du merge vertices : {}".format(e))

        # Slection propre
        cmds.select(clear=True)
        cmds.selectMode(object=True)

        print("Mesh final '{}' cr/merg et replac correctement.".format(combined_mesh))

    finally:
        cmds.undoInfo(closeChunk=True)

# Excuter
if __name__ == "__main__":
    combine_and_preserve_hierarchy()