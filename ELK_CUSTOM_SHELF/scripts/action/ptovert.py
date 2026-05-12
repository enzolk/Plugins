# ELK_META {"label": "PtoVert", "short_name": "", "tooltip": "Snap the pivot to the nearest Vertex", "source": "python"}
import maya.api.OpenMaya as om
import maya.cmds as cmds

def move_pivot_to_nearest_vertex():
    # Get the selected object
    selection = cmds.ls(selection=True, long=True)
    if not selection:
        cmds.warning("Please select an object.")
        return

    obj = selection[0]

    # Get the current pivot position in world space
    pivot_pos = cmds.xform(obj, query=True, worldSpace=True, rotatePivot=True)
    pivot_point = om.MPoint(pivot_pos)

    # Get the DAG path of the object
    sel_list = om.MSelectionList()
    sel_list.add(obj)
    dag_path = sel_list.getDagPath(0)

    # Ensure the object has a mesh
    try:
        mesh = om.MFnMesh(dag_path)
    except:
        cmds.warning("Selected object does not have a mesh.")
        return

    # Initialize variables to find the nearest vertex
    closest_vertex_index = None
    min_distance = float('inf')

    # Iterate through each vertex to find the closest one
    for i in range(mesh.numVertices):
        vertex_point = mesh.getPoint(i, om.MSpace.kWorld)
        distance = (vertex_point - pivot_point).length()
        if distance < min_distance:
            min_distance = distance
            closest_vertex_index = i

    # If a closest vertex is found, move the pivot to its position
    if closest_vertex_index is not None:
        closest_vertex_pos = mesh.getPoint(closest_vertex_index, om.MSpace.kWorld)
        cmds.xform(obj, worldSpace=True, pivots=(closest_vertex_pos.x, closest_vertex_pos.y, closest_vertex_pos.z))
        print(f"Pivot moved to vertex {closest_vertex_index} at position {closest_vertex_pos}.")
    else:
        cmds.warning("No vertices found on the mesh.")

# Execute the function
move_pivot_to_nearest_vertex()
