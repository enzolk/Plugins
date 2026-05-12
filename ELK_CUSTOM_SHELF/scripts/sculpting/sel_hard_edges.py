# ELK_META {"label": "Sel Hard Edges", "short_name": "", "tooltip": "Select Hard Edges", "source": "python"}
import maya.cmds as cmds

def select_edges_by_angle(min_angle, max_angle):
    """
    Selects edges within the specified angle range without deselecting the initial object.
    """
    # Get the currently selected objects
    selected_objects = cmds.ls(selection=True, long=True)
    
    if not selected_objects:
        cmds.warning("No objects selected.")
        return
    
    # Iterate over each selected object
    for obj in selected_objects:
        # Select all edges of the object
        cmds.select(obj + ".e[*]", replace=True)
        
        # Apply the angle constraint
        cmds.polySelectConstraint(mode=3, type=0x8000, angle=True, anglebound=(min_angle, max_angle))
        
        # Disable the selection constraint
        cmds.polySelectConstraint(disable=True)
        
        # Add the selected edges to the current selection without deselecting the object
        selected_edges = cmds.ls(selection=True, long=True)
        cmds.select(obj, add=True)
        cmds.select(selected_edges, add=True)
    
    print(f"Edges between {min_angle} and {max_angle} selected.")

def select_hardened_edges():
    """
    Selects all hardened (hard) edges on the currently selected objects.
    """
    # Get the currently selected objects
    selected_objects = cmds.ls(selection=True, long=True)
    
    if not selected_objects:
        cmds.warning("No objects selected.")
        return
    
    # Iterate over each selected object
    for obj in selected_objects:
        # Select all edges of the object
        cmds.select(obj + ".e[*]", replace=True)
        
        # Apply the constraint to select hard edges
        cmds.polySelectConstraint(mode=3, type=0x8000, smoothness=1)
        
        # Disable the selection constraint
        cmds.polySelectConstraint(disable=True)
        
        # Add the selected hard edges to the current selection without deselecting the object
        hard_edges = cmds.ls(selection=True, long=True)
        cmds.select(obj, add=True)
        cmds.select(hard_edges, add=True)
    
    print("Hardened edges selected.")

def create_ui():
    """
    Creates a user interface to select predefined angle ranges and hardened edges.
    """
    window_name = "edgeSelectorUI"
    
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    cmds.window(window_name, title="Edge Selector by Angle", widthHeight=(300, 250))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")
    
    cmds.text(label="Select a range of angles:")
    
    # Define presets as (min_angle, max_angle, label)
    presets = [
        (89, 91, "89 - 91"),
        (85, 95, "85 - 95"),
        (80, 100, "80 - 100"),
        (70, 110, "70 - 110"),
        (60, 120, "60 - 120"),
        (50, 130, "50 - 130"),
        (40, 140, "40 - 140"),
        (30, 150, "30 - 150"),
        (20, 160, "20 - 160"),
        (10, 170, "10 - 170"),
        (5, 175, "5 - 175")
    ]
    
    for min_angle, max_angle, label in presets:
        cmds.button(
            label=label,
            command=lambda _, min_angle=min_angle, max_angle=max_angle: select_edges_by_angle(min_angle, max_angle),
            width=250
        )
    
    cmds.separator(height=10, style='in')
    
    cmds.button(
        label="Select Hardened Edges",
        command=lambda _: select_hardened_edges(),
        width=250,
        backgroundColor=(0.8, 0.2, 0.2)
    )
    
    cmds.showWindow(window_name)

# Execute the user interface
create_ui()
