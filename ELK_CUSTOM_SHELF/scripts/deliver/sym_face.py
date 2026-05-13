# ELK_META {"label": "Find Non Symmetrical Faces", "short_name": "SymChk", "tooltip": "Recherche les faces non symétriques dans un mesh.", "source": "python", "icon_svg": "mirror.svg", "icon_color": "#f2c94c"}
import maya.cmds as cmds
import maya.api.OpenMaya as om

def get_selected_faces():
    """Returns a list of selected faces."""
    return cmds.filterExpand(selectionMask=34)  # 34 is the selection mask for polygon faces

def get_vertex_positions(face, mesh):
    """Returns the local space positions of the vertices of a given face."""
    vertices = cmds.polyInfo(face, faceToVertex=True)[0].split()[2:]
    positions = [cmds.pointPosition(f"{mesh}.vtx[{v}]", local=True) for v in vertices]
    return positions

def calculate_face_center(vertices):
    """Calculates the center of a face given its vertices' positions."""
    avg_position = [sum(axis) / len(axis) for axis in zip(*vertices)]
    return avg_position

def find_mirrored_faces(mesh, tolerance=0.001):
    """Finds all faces with their mirrored counterparts."""
    mirrored_faces = set()
    face_centers = {}
    
    for face in cmds.ls(f"{mesh}.f[*]", flatten=True):
        vertices = get_vertex_positions(face, mesh)
        center = calculate_face_center(vertices)
        mirrored_center = (-center[0], center[1], center[2])  # Mirroring across the X-axis

        # Round centers to avoid floating-point issues and use as dictionary keys
        rounded_center = tuple(round(c, 4) for c in center)
        rounded_mirrored_center = tuple(round(c, 4) for c in mirrored_center)

        # Store the face's center
        face_centers[rounded_center] = face

        # Check if the mirrored position exists in the recorded centers
        if rounded_mirrored_center in face_centers:
            mirrored_faces.add(face)
            mirrored_faces.add(face_centers[rounded_mirrored_center])

    return mirrored_faces

def select_faces_without_mirrors():
    selected_faces = get_selected_faces()
    if not selected_faces:
        cmds.warning("Please select some faces.")
        return

    mesh = selected_faces[0].split('.')[0]
    mirrored_faces = find_mirrored_faces(mesh)
    faces_without_mirrors = [face for face in selected_faces if face not in mirrored_faces]

    if faces_without_mirrors:
        cmds.select(faces_without_mirrors)
        print(f"Faces without mirrored counterparts: {faces_without_mirrors}")
    else:
        cmds.warning("All selected faces have mirrored counterparts.")

# Run the function to select faces without mirrored counterparts
select_faces_without_mirrors()