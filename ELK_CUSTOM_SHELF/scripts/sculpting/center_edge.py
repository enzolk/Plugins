# ELK_META {"label": "Center Edge", "short_name": "", "tooltip": "Select the center edge of the selected obect", "source": "python", "icon_svg": "border-top.svg", "icon_color": "#b277ff"}
import maya.cmds as cmds
import maya.OpenMaya as om

def on_button_click(axis):
    select_center_edge_loop(axis)
    cmds.deleteUI("centerAxisWin")

def create_ui():
    if cmds.window("centerAxisWin", exists=True):
        cmds.deleteUI("centerAxisWin")

    cmds.window("centerAxisWin", title="Select Center Axis")
    cmds.columnLayout(adjustableColumn=True)
    
    cmds.text(label="Choose the center axis:")
    
    cmds.button(label="X Axis", command=lambda x: on_button_click('x'))
    cmds.button(label="Y Axis", command=lambda x: on_button_click('y'))
    cmds.button(label="Z Axis", command=lambda x: on_button_click('z'))
    
    cmds.showWindow("centerAxisWin")

def select_center_edge_loop(center_axis):
    # Get the selected object
    selected_objects = cmds.ls(selection=True)
    if not selected_objects:
        om.MGlobal.displayError("Please select an object.")
        return
    
    selected_object = selected_objects[0]
    
    # Get the bounding box of the object
    bbox = cmds.exactWorldBoundingBox(selected_object)
    
    # Determine the center plane position
    center_pos = {
        'x': (bbox[0] + bbox[3]) / 2,
        'y': (bbox[1] + bbox[4]) / 2,
        'z': (bbox[2] + bbox[5]) / 2
    }
    
    # Create a very thin box along the selected axis
    tolerance = 0.1
    min_bounds = list(bbox[:3])
    max_bounds = list(bbox[3:])
    
    if center_axis == 'x':
        min_bounds[0] = center_pos['x'] - tolerance
        max_bounds[0] = center_pos['x'] + tolerance
    elif center_axis == 'y':
        min_bounds[1] = center_pos['y'] - tolerance
        max_bounds[1] = center_pos['y'] + tolerance
    elif center_axis == 'z':
        min_bounds[2] = center_pos['z'] - tolerance
        max_bounds[2] = center_pos['z'] + tolerance
    
    # Convert to tuples
    min_bounds = tuple(min_bounds)
    max_bounds = tuple(max_bounds)
    
    # Find edges within the box
    edge_ids = cmds.polyListComponentConversion(selected_object, toEdge=True)
    edge_ids = cmds.filterExpand(edge_ids, selectionMask=32, expand=True)
    
    selected_edges = []
    for edge in edge_ids:
        vertices = cmds.polyInfo(edge, edgeToVertex=True)[0].split()[2:4]
        vertices = [int(v) for v in vertices]
        positions = [cmds.pointPosition(f"{selected_object}.vtx[{v}]") for v in vertices]
        
        in_box = all(
            min_bounds[i] <= positions[0][i] <= max_bounds[i] and
            min_bounds[i] <= positions[1][i] <= max_bounds[i]
            for i in range(3)
        )
        
        if in_box:
            selected_edges.append(edge)
    
    # Select the edges
    if selected_edges:
        cmds.select(selected_edges)
    else:
        om.MGlobal.displayWarning("No edges found in the specified plane.")

# Run the UI
create_ui()