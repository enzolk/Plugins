# ELK_META {"label": "Open Borders", "short_name": "", "tooltip": "Find the open borders", "source": "python"}
import maya.cmds as cmds

def get_open_border_vertices():
    """Select vertices around every open border of all selected meshes."""
    selected_objects = cmds.ls(selection=True, type="transform")

    if not selected_objects:
        cmds.warning("Please select at least one mesh object.")
        return

    all_border_vertices = []

    for selected_object in selected_objects:
        shapes = cmds.listRelatives(selected_object, shapes=True, type='mesh', fullPath=True)
        if not shapes:
            cmds.warning(f"Selected object '{selected_object}' has no mesh shapes.")
            continue

        mesh = shapes[0]

        # Get all edges of the mesh
        all_edges = cmds.ls(cmds.polyListComponentConversion(mesh, toEdge=True), fl=True)

        # Find all border edges (edges connected to only one face)
        border_edges = []
        for edge in all_edges:
            connected_faces_info = cmds.polyInfo(edge, edgeToFace=True)
            if connected_faces_info:
                connected_faces = connected_faces_info[0].split()[2:]  # Remove "FACE" and other labels
                if len(connected_faces) == 1:  # Border edge has only one connected face
                    border_edges.append(edge)

        if not border_edges:
            cmds.warning(f"No open borders found for '{selected_object}'.")
            continue

        # Convert border edges to vertices
        border_vertices = cmds.ls(cmds.polyListComponentConversion(border_edges, fromEdge=True, toVertex=True), fl=True)

        all_border_vertices.extend(border_vertices)

    if not all_border_vertices:
        cmds.warning("No open border vertices found for any selected objects.")
        return

    # Select the vertices around the open borders
    cmds.select(all_border_vertices, replace=True)
    print(f"Selected open border vertices: {all_border_vertices}")

# Run the function to select open border vertices
get_open_border_vertices()
