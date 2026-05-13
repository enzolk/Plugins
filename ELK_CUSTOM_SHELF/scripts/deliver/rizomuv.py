# ELK_META {"label": "Send To RizomUV", "short_name": "Rizom", "tooltip": "Envoie automatiquement les UVs sélectionnées vers RizomUV.", "source": "python", "icon_svg": "send.svg", "icon_color": "#f2c94c"}
import maya.cmds as cmds
import subprocess, tempfile, os, platform
import maya.mel as mel

###########################################################################
#  Change the RizomUV path to your location                               #
###########################################################################
rizomPath = r'C:\Program Files\Rizom Lab\RizomUV 2023.0\rizomuv.exe'
#osx path is usually "/Applications/RizomUV.2018.0.app"
################## DONT TOUCH ANYTHING BELOW THIS LINE ####################

def sendToRizom(*args):
  obj = cmds.ls( selection=True, geometry=True, ap=True, dag=True)

  exportFile = tempfile.gettempdir() + os.sep + "ODRizomExport.obj"
  cmds.file(exportFile, f=1, pr=1, typ="OBJexport", es=1, op="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")
  if cmds.checkBox('uvcheck', query=True, value=True):
    cmd = '"' + rizomPath + '" "' + exportFile + '"'
  else:
    cmd = '"' + rizomPath + '" /nu "' + exportFile + '"'
  if platform.system() == "Windows":
    subprocess.Popen(cmd)
  else:
    subprocess.Popen(["open", "-a", rizomPath, "--args", exportFile])

def getFromRizom(*args):
  originalOBJs = cmds.ls( selection=True, geometry=True, ap=True, dag=True)
  exportFile = tempfile.gettempdir() + os.sep + "ODRizomExport.obj"

  if cmds.checkBox('linecheck', query=True, value=True):
    f = open(exportFile, "r")
    lines = f.readlines()
    f.close()

    f = open(exportFile, "w")
    for line in lines:
      if not line.startswith("#ZOMPROPERTIES"):
        f.write(line)
    f.close()

  cmds.file(exportFile, i=1, typ="OBJ", pr=1, op="mo=1", ns="ODRIZUV")
  
  cmds.select("ODRIZUV*:*")
  importedOBJs = cmds.ls(selection=True, geometry=True, o=True, s=False)
  cmds.select(clear=True)

  actualReplacedUVOJBs = []
  for obj in originalOBJs:
    for imp in importedOBJs:
      if obj.replace("Shape", "") in imp:
        cmds.polyTransfer(obj.replace("Shape", ""), vc=0, uv=1, v=0, ao=imp[:-5])
        actualReplacedUVOJBs.append(obj.replace("Shape", ""))
        break

  for obj in importedOBJs:
    cmds.select(obj[:-5], r=True)
    cmds.delete()

  for obj in actualReplacedUVOJBs:
    cmds.select(obj, add=True)

def rizomAutoRoundtrip(*args):

  originalOBJs = cmds.ls( selection=True, geometry=True, ap=True, dag=True)
  exportFile = tempfile.gettempdir() + os.sep + "ODRizomExport.obj"
  cmds.file(exportFile, f=1, pr=1, typ="OBJexport", es=1, op="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1")

  luascript = """ZomLoad({File={Path="odfilepath", ImportGroups=true, XYZ=true}, NormalizeUVW=true})
--U3dSymmetrySet({Point={0, 0, 0}, Normal={1, 0, 0}, Threshold=0.01, Enabled=true, UPos=0.5, LocalMode=false})
ZomSelect({PrimType="Edge", Select=true, ResetBefore=true, ProtectMapName="Protect", FilterIslandVisible=true, Auto={Skeleton={}, Open=true, PipesCutter=true, HandleCutter=true}})
ZomCut({PrimType="Edge"})
ZomUnfold({PrimType="Edge", MinAngle=1e-005, Mix=1, Iterations=1, PreIterations=5, StopIfOutOFDomain=false, RoomSpace=0, PinMapName="Pin", ProcessNonFlats=true, ProcessSelection=true, ProcessAllIfNoneSelected=true, ProcessJustCut=true, BorderIntersections=true, TriangleFlips=true})
ZomIslandGroups({Mode="DistributeInTilesEvenly", MergingPolicy=8322, GroupPath="RootGroup"})
ZomPack({ProcessTileSelection=false, RecursionDepth=1, RootGroup="RootGroup", Scaling={Mode=2}, Rotate={}, Translate=true, LayoutScalingMode=2})
ZomSave({File={Path="odfilepath", UVWProps=true}, __UpdateUIObjFileName=true})
ZomQuit()
"""

  f = open(tempfile.gettempdir() + os.sep + "riz.lua", "w")
  f.write(luascript.replace("odfilepath", exportFile.replace("\\", "/")))
  f.close()

  cmd = '"' + rizomPath + '" -cfi "' + tempfile.gettempdir() + os.sep + "riz.lua" + '"'
  if platform.system() == "Windows":
    subprocess.call(cmd, shell=False)
  else:
    os.system('open -W "' + rizomPath + '" --args -cfi "'+tempfile.gettempdir() + os.sep + 'riz.lua"')
    #subprocess.Popen(["open", "-a", rizomPath, "--args", " -cfi ", tempfile.gettempdir() + os.sep + "riz.lua"])

  if cmds.checkBox('linecheck', query=True, value=True):
    f = open(exportFile, "r")
    lines = f.readlines()
    f.close()

    f = open(exportFile, "w")
    for line in lines:
      if not line.startswith("#ZOMPROPERTIES"):
        f.write(line)
    f.close()

  cmds.file(exportFile, i=1, typ="OBJ", pr=1, op="mo=1", ns="ODRIZUV")
  
  cmds.select("ODRIZUV*:*")
  importedOBJs = cmds.ls(selection=True, geometry=True, o=True, s=False)
  cmds.select(clear=True)

  actualReplacedUVOJBs = []
  for obj in originalOBJs:
    for imp in importedOBJs:
      if obj.replace("Shape", "") in imp:
        cmds.polyTransfer(obj.replace("Shape", ""), vc=0, uv=1, v=0, ao=imp[:-5])
        actualReplacedUVOJBs.append(obj.replace("Shape", ""))
        break

  for obj in importedOBJs:
    cmds.select(obj[:-5], r=True)
    cmds.delete()

  for obj in actualReplacedUVOJBs:
    cmds.select(obj, add=True)

# UI
cmds.window(title="OD Maya <-> RizomUV Bridge" )
cmds.columnLayout()
cmds.button( label='Send To RizomUV', width=300, command=sendToRizom)
cmds.checkBox('uvcheck', label='Transfer Existing UVs to Rizom', align='center')
cmds.button( label='Get From RizomUV', width=300, command=getFromRizom)
cmds.checkBox('linecheck', label='Long Line Check (intermediate Rizom fix for long lines)', align='center')
cmds.button( label='RizomUV Automatic Roundtrip', width=300, command=rizomAutoRoundtrip)
cmds.showWindow()