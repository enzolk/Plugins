# ELK_META {"label": "edgeSel", "short_name": "", "tooltip": "This script selects edges in a Maya mesh based on the area of their adjacent faces and their length. Users can define min/max thresholds for both criteria via a UI.", "source": "python"}
import maya.cmds as cmds
import maya.api.OpenMaya as om

def selectEdgesBasedOnFaceArea(minArea, maxArea, minEdge, maxEdge):
    """
    Slectionne toutes les artes dont :
      - Toutes les faces adjacentes ont une aire comprise entre minArea et maxArea.
      - La longueur de l'arte est comprise entre minEdge et maxEdge.
    """
    # Vrifier qu'un objet est slectionn
    sel = cmds.ls(selection=True, long=True)
    if not sel:
        cmds.error("Veuillez slectionner un objet maillage.")
    
    meshName = sel[0]
    
    # Prparer l'API OpenMaya pour itrer sur le maillage
    selList = om.MSelectionList()
    selList.add(meshName)
    dagPath = selList.getDagPath(0)
    
    # Calculer l'aire de chaque face et stocker dans un dictionnaire
    faceArea = {}
    polyIter = om.MItMeshPolygon(dagPath)
    while not polyIter.isDone():
        faceIndex = polyIter.index()
        area = polyIter.getArea()
        faceArea[faceIndex] = area
        polyIter.next()
    
    # Itrer sur les artes et vrifier les conditions sur les faces et la longueur de l'arte
    selectedEdges = []
    edgeIter = om.MItMeshEdge(dagPath)
    while not edgeIter.isDone():
        connectedFaces = edgeIter.getConnectedFaces()
        allFacesInRange = True
        for faceIdx in connectedFaces:
            area = faceArea.get(faceIdx, 0)
            if area < minArea or area > maxArea:
                allFacesInRange = False
                break
        
        if allFacesInRange and connectedFaces:
            # Rcuprer les positions des deux extrmits de l'arte
            p0 = edgeIter.point(0, om.MSpace.kWorld)
            p1 = edgeIter.point(1, om.MSpace.kWorld)
            edgeLength = p0.distanceTo(p1)
            
            # Vrifier que la longueur est dans le range spcifi
            if minEdge <= edgeLength <= maxEdge:
                edgeIndex = edgeIter.index()
                edgeComponent = "{}.e[{}]".format(meshName, edgeIndex)
                selectedEdges.append(edgeComponent)
        edgeIter.next()
    
    # Slectionner les artes ou vider la slection si aucune ne correspond
    if selectedEdges:
        cmds.select(selectedEdges, replace=True)
        print("Artes slectionnes :", selectedEdges)
    else:
        cmds.select(clear=True)
        print("Aucune arte ne rpond aux critres.")

def createUI():
    """
    Cre une interface utilisateur pour dfinir l'intervalle d'aire et de taille des artes.
    """
    # Si la fentre existe dj, on la supprime
    if cmds.window("edgeSelectorWindow", exists=True):
        cmds.deleteUI("edgeSelectorWindow")
    
    window = cmds.window("edgeSelectorWindow", title="Slection d'artes par aire des faces et taille", widthHeight=(300, 200))
    cmds.columnLayout(adjustableColumn=True, columnAlign="center")
    
    cmds.text(label="Dfinir l'intervalle d'aire des faces", align="center", height=20)
    cmds.floatFieldGrp("areaRangeField", numberOfFields=2, label="Aire (Min, Max):", value1=0.5, value2=2.0)
    
    cmds.separator(height=10, style="in")
    
    cmds.text(label="Dfinir l'intervalle de taille des artes", align="center", height=20)
    cmds.floatFieldGrp("edgeRangeField", numberOfFields=2, label="Taille (Min, Max):", value1=0.1, value2=5.0)
    
    cmds.separator(height=10, style="in")
    
    cmds.button(label="Slectionner les artes", command=lambda *args: onSelectEdges())
    
    cmds.separator(height=10, style="in")
    
    cmds.button(label="Fermer", command=lambda *args: cmds.deleteUI(window, window=True))
    
    cmds.showWindow(window)

def onSelectEdges():
    """
    Rcupre les valeurs saisies et appelle la fonction de slection.
    """
    areaValues = cmds.floatFieldGrp("areaRangeField", query=True, value=True)
    edgeValues = cmds.floatFieldGrp("edgeRangeField", query=True, value=True)
    if areaValues and len(areaValues) >= 2 and edgeValues and len(edgeValues) >= 2:
        minArea = areaValues[0]
        maxArea = areaValues[1]
        minEdge = edgeValues[0]
        maxEdge = edgeValues[1]
        selectEdgesBasedOnFaceArea(minArea, maxArea, minEdge, maxEdge)
    else:
        cmds.error("Veuillez entrer des valeurs valides pour l'aire et la taille des artes.")

# Excuter l'interface utilisateur
createUI()
