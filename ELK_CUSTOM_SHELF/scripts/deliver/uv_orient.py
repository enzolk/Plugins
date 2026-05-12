# ELK_META {"label": "UV Orient", "short_name": "", "tooltip": "Orient UV shells In the same direction", "source": "python"}
import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
import math
import re

# ------------------------------
# Fonction de log
# ------------------------------

def logMessage(msg):
    """Affiche un message si la case  cocher 'Activer le log' est active."""
    if cmds.checkBox("activeLogCB", query=True, value=True):
        print(msg)

# ------------------------------
# Fonctions utilitaires
# ------------------------------

def getFaceIndices(faceList):
    """
    Extrait les indices de face depuis une liste de composants (ex : "pCube.f[23]").
    """
    indices = []
    for comp in faceList:
        m = re.search(r'\[(\d+)\]', comp)
        if m:
            indices.append(int(m.group(1)))
    return indices

def getUVShells():
    """
    Retourne une liste de shells UV, chaque shell tant une liste de composants UV.
    """
    sel = cmds.ls(selection=True, flatten=True)
    if not sel:
        cmds.error("Veuillez slectionner des UVs dans un UV shell.")
    uvSel = cmds.polyListComponentConversion(sel, toUV=True)
    uvSel = cmds.ls(uvSel, flatten=True)
    
    shells = []
    processed = set()
    for uv in uvSel:
        if uv in processed:
            continue
        cmds.select(uv)
        cmds.polySelectConstraint(mode=2, type=0x0010, shell=1)
        shellGroup = cmds.ls(selection=True, flatten=True)
        cmds.polySelectConstraint(disable=True)
        if shellGroup:
            shells.append(shellGroup)
            processed.update(shellGroup)
    logMessage("UV Shells trouvs: %s" % shells)
    return shells

def getFacesFromUVShell(uvShell):
    """
    Convertit un UV shell en faces correspondantes.
    """
    cmds.select(uvShell)
    faceSel = cmds.polyListComponentConversion(toFace=True)
    faceSel = cmds.ls(faceSel, flatten=True)
    logMessage("Faces du shell: %s" % faceSel)
    return faceSel

def getBoundingBox3D(components):
    """
    Retourne la bounding box 3D [xmin, ymin, zmin, xmax, ymax, zmax] des composants donns.
    """
    bb = cmds.exactWorldBoundingBox(components)
    logMessage("Bounding box 3D: %s" % bb)
    return bb

def getBoundingBoxUV(uvShell):
    """
    Calcule la bounding box UV ([uMin, vMin, uMax, vMax]) du shell UV.
    """
    u_vals = []
    v_vals = []
    for uv in uvShell:
        coord = cmds.polyEditUV(uv, query=True)
        if coord:
            u_vals.append(coord[0])
            v_vals.append(coord[1])
    if not u_vals or not v_vals:
        return None
    bbuv = [min(u_vals), min(v_vals), max(u_vals), max(v_vals)]
    logMessage("Bounding box UV: %s" % bbuv)
    return bbuv

def getShellVertices(faceSel):
    """
    Retourne les vertices (en 3D) correspondant  la slection de faces.
    """
    cmds.select(faceSel)
    vertSel = cmds.polyListComponentConversion(toVertex=True)
    vertSel = cmds.ls(vertSel, flatten=True)
    logMessage("Vertices du shell: %s" % vertSel)
    return vertSel

def getVertexPosition(vertex):
    """
    Retourne la position 3D du vertex sous forme de tuple (x, y, z).
    """
    pos = cmds.pointPosition(vertex, world=True)
    return pos

def getVertexUV(vertex, uvShell):
    """
    Retourne la coordonne UV associe au vertex, filtre par le shell UV.
    """
    uvList = cmds.polyListComponentConversion(vertex, fromVertex=True, toUV=True)
    uvList = cmds.ls(uvList, flatten=True)
    for uv in uvList:
        if uv in uvShell:
            coord = cmds.polyEditUV(uv, query=True)
            return coord
    return None

def computeWeightedAverageNormal(faceList, dagPath):
    """
    Calcule la normale moyenne pondre par l'aire pour les faces dont les indices
    sont dans faceList. Renvoie un om.MVector.
    """
    totalArea = 0.0
    sumNormal = om.MVector(0, 0, 0)
    itPoly = om.MItMeshPolygon(dagPath)
    faceIndices = set(faceList)
    while not itPoly.isDone():
        idx = itPoly.index()
        if idx in faceIndices:
            normal = itPoly.getNormal(0, om.MSpace.kWorld)
            area = itPoly.getArea()
            totalArea += area
            sumNormal += normal * area
        itPoly.next()
    if totalArea > 0:
        avg = sumNormal / totalArea
        logMessage("Normale moyenne pondre: %s" % avg)
        return avg
    else:
        return om.MVector(0, 0, 0)

# ------------------------------
# Traitement d'un UV shell
# ------------------------------

def processUVShell(uvShell, uvTolerance):
    """
    Pour un UV shell, effectue les tapes suivantes :
      - Calcule la bounding box 3D des faces associes et extrait le Y minimum.
      - Calcule la normale moyenne pondre par l'aire des faces.
      - Selon la direction de la normale (horizontale ou verticale), dfinit les coins cibles :
          * Si horizontal (normal principalement en X/Z) : 4 coins.
          * Sinon (normal principalement en Y) : 2 coins, ici (xmin, ymin, zmax) et (xmax, ymin, zmax).
      - Pour chaque coin, recherche le vertex dont la position 3D est la plus proche.
      - **VRIFICATION UV MODIFIE :**
            1. Calcule la bounding box 2D des UVs associs aux vertex identifis.
            2. Si cette bounding box est plus longue verticalement (V) que horizontalement (U),
               applique polyRotateUVs 90 1 et recalcule, jusqu' 4 tentatives maximum.
            3. Ensuite, compte le pourcentage d'UV du shell qui sont au-dessus de la V minimale
               des UV des vertex identifis. Si ce pourcentage est infrieur au seuil dfini (via l'interface),
               applique polyRotateUVs 180 1.
      - Retourne la liste des vertex identifis.
    """
    logMessage("Traitement du shell UV: %s" % uvShell)
    faceSel = getFacesFromUVShell(uvShell)
    if not faceSel:
        cmds.warning("Aucune face trouve pour ce shell.")
        return []
    bb3d = getBoundingBox3D(faceSel)  # [xmin, ymin, zmin, xmax, ymax, zmax]
    xmin, ymin, zmin, xmax, ymax, zmax = bb3d
    verts = getShellVertices(faceSel)
    if not verts:
        cmds.warning("Aucun vertex trouv pour ce shell.")
        return []
    
    # Calcul de la normale moyenne pondre par l'aire
    faceIndices = getFaceIndices(faceSel)
    selList = om.MSelectionList()
    selList.add(faceSel[0])
    dagPath = selList.getDagPath(0)
    avgNormal = computeWeightedAverageNormal(faceIndices, dagPath)
    
    # Dfinir les coins cibles selon l'orientation de la normale
    if abs(avgNormal.y) < max(abs(avgNormal.x), abs(avgNormal.z)):
        corners = [
            (xmin, ymin, zmin),
            (xmin, ymin, zmax),
            (xmax, ymin, zmax),
            (xmax, ymin, zmin)
        ]
    else:
        # Pour une normale principalement oriente en Y, on cible les coins en Z+
        corners = [
            (xmin, ymin, zmax),
            (xmax, ymin, zmax)
        ]
    logMessage("Coins cibles en 3D: %s" % corners)
    
    # Pour chaque coin, trouver le vertex le plus proche
    selectedVerts = []
    for corner in corners:
        bestVert = None
        bestDist = float('inf')
        for v in verts:
            pos = getVertexPosition(v)
            dist = math.sqrt((pos[0]-corner[0])**2 + (pos[1]-corner[1])**2 + (pos[2]-corner[2])**2)
            if dist < bestDist:
                bestDist = dist
                bestVert = v
        if bestVert:
            logMessage("Vertex choisi pour le coin %s: %s (distance = %s)" % (corner, bestVert, bestDist))
            selectedVerts.append(bestVert)
    
    # Calculer la bounding box UV du shell et la valeur minimale de V
    bbuv = getBoundingBoxUV(uvShell)
    if bbuv is None:
        cmds.warning("Impossible de calculer la bounding box UV pour ce shell.")
        return selectedVerts
    allUVs = []
    for v in verts:
        uv = getVertexUV(v, uvShell)
        if uv:
            allUVs.append(uv)
    if not allUVs:
        cmds.warning("Impossible de rcuprer les UVs du shell.")
        return selectedVerts
    minV = min(uv[1] for uv in allUVs)
    logMessage("Valeur minV du shell: %s" % minV)
    
    # VRIFICATION UV MODIFIE
    # 5a. Calculer la bounding box 2D des UVs associs aux vertex identifis
    identifiedUVs = [getVertexUV(v, uvShell) for v in selectedVerts if getVertexUV(v, uvShell) is not None]
    if identifiedUVs:
        minU_id = min(uv[0] for uv in identifiedUVs)
        maxU_id = max(uv[0] for uv in identifiedUVs)
        minV_id = min(uv[1] for uv in identifiedUVs)
        maxV_id = max(uv[1] for uv in identifiedUVs)
        boxWidth = maxU_id - minU_id
        boxHeight = maxV_id - minV_id
        logMessage("Bounding box 2D des vertex identifis: width = %s, height = %s" % (boxWidth, boxHeight))
        
        # 5b. Si la bounding box est plus longue verticalement (V > U), appliquer des rotations de 90 (max 4 tentatives)
        attempts = 0
        while boxHeight > boxWidth and attempts < 4:
            logMessage("Bounding box verticale dominante. Rotation de 90, tentative #%s" % (attempts+1))
            mel.eval('polyRotateUVs 90 1')
            identifiedUVs = [getVertexUV(v, uvShell) for v in selectedVerts if getVertexUV(v, uvShell) is not None]
            if not identifiedUVs:
                break
            minU_id = min(uv[0] for uv in identifiedUVs)
            maxU_id = max(uv[0] for uv in identifiedUVs)
            minV_id = min(uv[1] for uv in identifiedUVs)
            maxV_id = max(uv[1] for uv in identifiedUVs)
            boxWidth = maxU_id - minU_id
            boxHeight = maxV_id - minV_id
            logMessage("Aprs rotation, bounding box 2D: width = %s, height = %s" % (boxWidth, boxHeight))
            attempts += 1
        
        # 5c. Vrifier le pourcentage d'UV du shell qui sont au-dessus de la V minimale des UV des vertex identifis
        identified_minV = min(uv[1] for uv in identifiedUVs)
        allUVsShell = []
        for uv in uvShell:
            coord = cmds.polyEditUV(uv, query=True)
            if coord:
                allUVsShell.append(coord)
        if allUVsShell:
            countAbove = sum(1 for uv in allUVsShell if uv[1] > identified_minV)
            fraction = countAbove / float(len(allUVsShell))
            logMessage("Fraction d'UV au-dessus de la V minimale identifie: %s" % fraction)
            threshold = cmds.floatFieldGrp("uvPercentageField", query=True, value=True)[0] / 100.0
            if fraction < threshold:
                logMessage("Fraction insuffisante (< %s%%). Rotation de 180." % (threshold*100))
                mel.eval('polyRotateUVs 180 1')
    
    return selectedVerts

# ------------------------------
# Traitement des UV shells slectionns
# ------------------------------

def processSelectedUVShells(uvTolerance, selectIdentified):
    """
    Pour chaque UV shell slectionn, excute le traitement dcrit et, si selectIdentified est True,
    slectionne tous les vertex identifis  la fin.
    """
    shells = getUVShells()
    if not shells:
        cmds.error("Aucun UV shell trouv dans la slection.")
    allIdentifiedVerts = []
    for shell in shells:
        cmds.select(shell)
        vertsIdentified = processUVShell(shell, uvTolerance)
        if vertsIdentified:
            allIdentifiedVerts.extend(vertsIdentified)
    cmds.select(clear=True)
    if selectIdentified and allIdentifiedVerts:
        cmds.select(allIdentifiedVerts, replace=True)
        logMessage("Vertex identifis slectionns: %s" % allIdentifiedVerts)
        cmds.confirmDialog(title='Traitement termin', message='Les UV shells ont t traits et les vertex identifis sont slectionns.')
    else:
        cmds.confirmDialog(title='Traitement termin', message='Les UV shells ont t traits.')

# ------------------------------
# Interface utilisateur
# ------------------------------

def createUI():
    """
    Cre une interface utilisateur pour dfinir :
      - La tolrance UV pour la vrification des UV (en units UV).
      - Le pourcentage minimum d'UV du shell devant tre au-dessus des UV des vertex identifis.
      - Si les vertex identifis doivent tre slectionns  la fin.
      - Si le log doit tre activ.
    """
    windowName = "uvShellCorrectionWindow"
    if cmds.window(windowName, exists=True):
        cmds.deleteUI(windowName)
    window = cmds.window(windowName, title="Correction UV Shells", widthHeight=(320, 240))
    cmds.columnLayout(adjustableColumn=True, columnAlign="center")
    cmds.text(label="Tolrance pour la vrification V- (units UV):", align="center", height=20)
    cmds.floatFieldGrp("uvToleranceField", numberOfFields=1, label="Tolrance:", value1=0.01, precision=4)
    cmds.separator(height=10, style="in")
    cmds.checkBox("selectIdentifiedVertsCB", label="Slectionner les vertex identifis", value=True)
    cmds.separator(height=10, style="in")
    cmds.text(label="Pourcentage minimum d'UV au-dessus (en %):", align="center", height=20)
    cmds.floatFieldGrp("uvPercentageField", numberOfFields=1, label="Pourcentage:", value1=90.0, precision=2)
    cmds.separator(height=10, style="in")
    cmds.checkBox("activeLogCB", label="Activer le log", value=False)
    cmds.separator(height=10, style="in")
    cmds.button(label="Traiter les UV shells", command=lambda *args: onProcessUI())
    cmds.separator(height=10, style="in")
    cmds.button(label="Fermer", command=lambda *args: cmds.deleteUI(window, window=True))
    cmds.showWindow(window)

def onProcessUI():
    uvTol = cmds.floatFieldGrp("uvToleranceField", query=True, value=True)[0]
    selectIdentified = cmds.checkBox("selectIdentifiedVertsCB", query=True, value=True)
    processSelectedUVShells(uvTol, selectIdentified)

# Excuter l'interface
createUI()
