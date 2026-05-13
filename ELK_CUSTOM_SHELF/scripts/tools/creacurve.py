# ELK_META {"label": "Curve Between Vertices", "short_name": "VtxCrv", "tooltip": "Génère une courbe entre deux vertices sélectionnés.", "source": "python", "icon_svg": "line.svg", "icon_color": "#36d6ff"}
import maya.api.OpenMaya as om
import maya.cmds as cmds

def get_selected_vertices():
    sel = om.MGlobal.getActiveSelectionList()
    positions = []

    for i in range(sel.length()):
        dagPath, component = sel.getComponent(i)
        if component.apiType() == om.MFn.kMeshVertComponent:
            mfnMesh = om.MFnMesh(dagPath)
            indices = om.MFnSingleIndexedComponent(component).getElements()
            for index in indices:
                pos = mfnMesh.getPoint(index, om.MSpace.kWorld)
                positions.append(om.MVector(pos))

    return positions

def create_bezier_curve(p0, p1):
    direction = p1 - p0
    length = direction.length()

    p0_tangent = p0 + direction.normal() * (length * 0.25)
    p1_tangent = p1 - direction.normal() * (length * 0.25)

    bezier_points = [
        (p0.x, p0.y, p0.z),
        (p0_tangent.x, p0_tangent.y, p0_tangent.z),
        (p1_tangent.x, p1_tangent.y, p1_tangent.z),
        (p1.x, p1.y, p1.z)
    ]

    cmds.curve(p=bezier_points, degree=3)

def bezier_between_selected_vertices():
    verts = get_selected_vertices()
    if len(verts) != 2:
        om.MGlobal.displayWarning("Veuillez slectionner exactement 2 vertex.")
        return

    create_bezier_curve(verts[0], verts[1])

# Lancer la fonction principale
bezier_between_selected_vertices()