# ELK_META {"label": "Sel Crease", "short_name": "", "tooltip": "Select Creased Edges", "source": "python"}
import maya.cmds as cmds

def select_creased_edges():
    # Get the currently selected mesh
    selected_meshes = cmds.ls(selection=True, dag=True, type='mesh')
    
    if not selected_meshes:
        cmds.warning("Please select a mesh.")
        return

    # Switch to edge selection mode and clear the selection
    cmds.selectMode(component=True)
    cmds.selectType(edge=True)
    cmds.select(clear=True)

    # Initialize an empty list to hold the creased edges
    creased_edges = []

    for mesh in selected_meshes:
        # Get all the edges of the mesh
        edges = cmds.polyListComponentConversion(mesh, toEdge=True)
        edges = cmds.filterExpand(edges, selectionMask=32)
        
        if edges:
            for edge in edges:
                # Check if the edge is creased
                crease_value = cmds.polyCrease(edge, query=True, value=True)
                if crease_value[0] > 0.0:
                    creased_edges.append(edge)

    if creased_edges:
        # Select the creased edges
        cmds.select(creased_edges)
        print("Creased edges selected.")
    else:
        cmds.warning("No creased edges found.")

# Run the function
select_creased_edges()
