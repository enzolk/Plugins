# ELK_META {"label": "Smooth_Crease", "short_name": "", "tooltip": "Set mesh options to receive creasing correctly", "source": "python"}
import maya.cmds as cmds

def set_subdiv_display_on_selection():
    """
    For ALL selected objects (even if components are selected),
    set these mesh shape attrs:
      - useGlobalSmoothDrawType = 0
      - propagateEdgeHardness   = 1
      - smoothDrawType          = 0  (Maya Catmull-Clark)
    """
    sel = cmds.ls(sl=True, fl=True, long=True) or []
    if not sel:
        cmds.warning("Please select one or more mesh objects (or components).")
        return

    # Convert any component selection to transforms (object selection)
    objs = cmds.ls(sl=True, o=True, long=True) or []
    if not objs:
        # Fallback: force object mode and re-query
        try:
            cmds.select(sel, r=True)
            cmds.selectMode(object=True)
        except Exception:
            pass
        objs = cmds.ls(sl=True, type="transform", long=True) or []

    if not objs:
        cmds.warning("No transform objects found in selection.")
        return

    updated_shapes = 0

    for obj in objs:
        # Get non-intermediate mesh shapes under transform
        shapes = cmds.listRelatives(obj, shapes=True, noIntermediate=True, fullPath=True) or []
        for sh in shapes:
            if cmds.nodeType(sh) != "mesh":
                continue

            # Safe-set each attribute only if it exists on this node
            if cmds.attributeQuery("useGlobalSmoothDrawType", node=sh, exists=True):
                cmds.setAttr(sh + ".useGlobalSmoothDrawType", 0)

            if cmds.attributeQuery("propagateEdgeHardness", node=sh, exists=True):
                cmds.setAttr(sh + ".propagateEdgeHardness", 1)

            if cmds.attributeQuery("smoothDrawType", node=sh, exists=True):
                cmds.setAttr(sh + ".smoothDrawType", 0)

            updated_shapes += 1

    # Restore selection (transforms)
    try:
        cmds.select(objs, r=True)
    except Exception:
        pass

    print("[SubdivDisplay] Updated {} mesh shape(s) on {} object(s).".format(updated_shapes, len(objs)))

# Run
set_subdiv_display_on_selection()
