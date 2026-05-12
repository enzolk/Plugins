# ELK_META {"label": "Select UV Borders", "short_name": "", "tooltip": "Select UV Borders", "source": "python", "icon_svg": "table-import.svg", "icon_color": "#4bc8ff"}
# -*- coding: utf-8 -*-
"""
select_uv_shell_perimeters.py
Safely select the perimeter edges of *every* UV shell on the
currently-selected polygon mesh object(s), whatever flavour of
polyEvaluate your Maya returns.

Usage
-----
1.  Select one or more poly meshes.
2.  Run:
        select_perimeter_edges_all_uv_shells()
"""

import maya.cmds as cmds
import maya.mel as mel


def _uv_components_for_shell(obj, shell_index):
    """
    Return a list of UV component strings for one UV shell on `obj`,
    handling both 'int' and already-formatted strings.
    """
    raw = cmds.polyEvaluate(obj, uvsInShell=shell_index) or []

    # Maya 20182022 usually ? list[int]; some builds ? list[str]
    comps = []
    for item in raw:
        if isinstance(item, int):                       # classic behaviour
            comps.append(f"{obj}.map[{item}]")
        else:                                          # already looks like "something.map[...]"
            comps.append(item)
    return comps


def select_perimeter_edges_all_uv_shells():
    """
    Walk selected transforms, gather every UV-shell perimeter edge,
    then finish with a single unified edge selection.
    """
    xforms = cmds.ls(selection=True, dag=True, type="transform", long=True)
    if not xforms:
        cmds.error("Nothing selected. Please select one or more polygon meshes.")
        return

    perimeter_edges = set()

    for xform in xforms:
        # Only deal with meshes
        if not cmds.listRelatives(xform, s=True, ni=True, type="mesh"):
            cmds.warning(f'"{xform}" is not a polygon mesh - skipped.')
            continue

        shell_count = cmds.polyEvaluate(xform, uvShell=True)
        for shell_id in range(shell_count):
            uv_comps = _uv_components_for_shell(xform, shell_id)
            if not uv_comps:
                continue

            # 1  Select this shells UVs
            cmds.select(uv_comps, r=True)

            # 2  Convert UV selection ? perimeter edges
            mel.eval("ConvertSelectionToEdgePerimeter;")

            # 3  Cache whats now selected
            perimeter_edges.update(cmds.ls(selection=True, flatten=True) or [])

    # 4  Reselect everything we found
    if perimeter_edges:
        cmds.select(list(perimeter_edges), r=True)
        print(f"Selected {len(perimeter_edges)} unique perimeter edges.")
    else:
        cmds.warning("No perimeter edges found on the chosen object(s).")


# Auto-run when executed directly (e.g. from Script Editor Execute button)
if __name__ == "__main__":
    select_perimeter_edges_all_uv_shells()