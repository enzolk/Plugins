# ELK_META {"label": "Creased Edges", "short_name": "", "tooltip": "Apply Crease to selected edges", "source": "python"}
import maya.cmds as cmds

def apply_crease_to_selected_edges(strength=10):
    # Get the currently selected edges
    selected_edges = cmds.ls(selection=True, flatten=True)
    
    if not selected_edges:
        cmds.warning("Please select some edges.")
        return

    # Apply the crease value to the selected edges
    cmds.polyCrease(selected_edges, value=strength)
    print("Crease applied with strength:", strength)

# Automatically apply a crease with strength 10 to the selected edges
apply_crease_to_selected_edges()
