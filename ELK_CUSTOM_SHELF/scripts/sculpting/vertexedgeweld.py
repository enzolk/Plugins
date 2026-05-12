# ELK_META {"label": "VertexEdgeWeld", "short_name": "", "tooltip": "A Maya tool that identifies the closest edge to a selected vertex, inserts a vertex in the middle of this edge, and then seamlessly welds the new vertex to the selected vertex for precise geometry adjustments.", "source": "python"}
import maya.cmds as cmds
import maya.api.OpenMaya as om

def get_vertices_within_distance(target_vertex, distance_threshold):
    """Finds vertices within a specified distance from the target vertex."""
    target_position = om.MPoint(cmds.pointPosition(target_vertex, world=True))
    mesh = target_vertex.split('.')[0]
    vertices = cmds.ls(f"{mesh}.vtx[*]", fl=True)
    nearby_vertices = []

    for vertex in vertices:
        if vertex != target_vertex:
            position = om.MPoint(cmds.pointPosition(vertex, world=True))
            if (position - target_position).length() < distance_threshold:
                nearby_vertices.append(vertex)
    
    return nearby_vertices

def get_closest_edge_to_vertex(vertex, max_edge_distance):
    # Get the selected vertex's position
    vertex_position = cmds.pointPosition(vertex, world=True)
    vertex_position = om.MPoint(vertex_position)

    # Get the mesh name from the vertex
    mesh = vertex.split('.')[0]

    # Get all the edges in the mesh
    edges = cmds.ls(f"{mesh}.e[*]", fl=True)
    connected_edges = cmds.polyListComponentConversion(vertex, fromVertex=True, toEdge=True)
    connected_edges = cmds.ls(connected_edges, fl=True)

    # Find the closest edge that isn't connected to the vertex
    min_distance = float('inf')
    closest_edge = None

    for edge in edges:
        if edge not in connected_edges:
            # Get the vertices of the edge
            edge_vertices = cmds.polyInfo(edge, edgeToVertex=True)[0].split()[2:4]
            v1 = f"{mesh}.vtx[{edge_vertices[0]}]"
            v2 = f"{mesh}.vtx[{edge_vertices[1]}]"
            
            # Get positions of the vertices
            v1_position = cmds.pointPosition(v1, world=True)
            v2_position = cmds.pointPosition(v2, world=True)
            
            # Convert positions to MPoint
            v1_position = om.MPoint(v1_position)
            v2_position = om.MPoint(v2_position)

            # Calculate edge vector and check for zero-length edge
            edge_vector = v2_position - v1_position
            if edge_vector.length() == 0:
                continue

            # Find the closest point on the edge to the vertex
            vertex_vector = vertex_position - v1_position
            projection = (vertex_vector * edge_vector) / (edge_vector * edge_vector)
            projection = max(0, min(1, projection))
            closest_point = v1_position + projection * edge_vector

            # Calculate distance
            distance = (closest_point - vertex_position).length()
            if distance < min_distance and distance <= max_edge_distance:
                min_distance = distance
                closest_edge = edge

    return closest_edge, min_distance

def insert_vertex_at_middle_of_edge(edge):
    # Insert a vertex in the middle of the specified edge
    cmds.polySubdivideEdge(edge, divisions=1)
    # Get the newly created vertex
    new_vertex = cmds.polyListComponentConversion(edge, fromEdge=True, toVertex=True)
    new_vertex = cmds.ls(new_vertex, flatten=True)[-1]  # Get the last vertex in the list
    return new_vertex

def target_weld_vertices(source_vertex, target_vertex):
    # Get the position of the target vertex
    target_position = cmds.pointPosition(target_vertex, world=True)
    
    # Move the source vertex to the target vertex position
    cmds.move(target_position[0], target_position[1], target_position[2], source_vertex, absolute=True, worldSpace=True)
    
    # Merge the vertices
    cmds.polyMergeVertex([source_vertex, target_vertex], distance=0.000001)

def is_vertex_on_border(vertex):
    """Checks if the given vertex is on a border (open edge)."""
    edges = cmds.polyListComponentConversion(vertex, fromVertex=True, toEdge=True)
    edges = cmds.ls(edges, fl=True)
    for edge in edges:
        # Get the number of faces connected to the edge
        faces = cmds.polyListComponentConversion(edge, fromEdge=True, toFace=True)
        faces = cmds.ls(faces, fl=True)
        if len(faces) == 1:  # An edge with only one connected face is a border edge
            return True
    return False

# Example usage
selected_vertices = cmds.ls(selection=True, flatten=True)
distance_threshold = 0.002  # For nearby vertex detection
max_edge_distance = 0.05     # Maximum distance for edge detection

if selected_vertices:
    for target_vertex in selected_vertices:
        # Check if the vertex is on a border
        if is_vertex_on_border(target_vertex):
            # Check for nearby vertices to merge
            nearby_vertices = get_vertices_within_distance(target_vertex, distance_threshold)
            if nearby_vertices:
                for nearby_vertex in nearby_vertices:
                    print(f"Merging {target_vertex} with nearby vertex {nearby_vertex}")
                    target_weld_vertices(nearby_vertex, target_vertex)
            else:
                # No nearby vertices, proceed with finding the closest edge within max_edge_distance
                closest_edge, distance = get_closest_edge_to_vertex(target_vertex, max_edge_distance)
                if closest_edge:
                    print(f"The closest edge to {target_vertex} is {closest_edge} with a distance of {distance}")
                    new_vertex = insert_vertex_at_middle_of_edge(closest_edge)
                    target_weld_vertices(new_vertex, target_vertex)
                    print(f"Target welded vertex {new_vertex} to {target_vertex}")
                else:
                    print(f"No edge found within {max_edge_distance} units from {target_vertex}")
        else:
            print(f"Vertex {target_vertex} is not on a border and will be skipped.")
else:
    print("Please select at least one vertex.")
