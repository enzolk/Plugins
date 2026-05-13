# ELK_META {"label": "Toggle Rotate Mode", "short_name": "RotMod", "tooltip": "Alterne rapidement différents modes de rotation et d’orientation.", "source": "python", "icon_svg": "rotate.svg", "icon_color": "#ff9f1a"}
import maya.cmds as cmds
 
ctx = cmds.currentCtx()
 
if ctx == 'moveSuperContext':
   
    tool = 'Move'
    mode = cmds.manipMoveContext(tool, q=1, m=1)
    if mode == 0:
        cmds.manipMoveContext(tool, e=1, m=9)
    elif mode == 2:
        cmds.manipMoveContext(tool, e=1, m=9)
    else:
        cmds.manipMoveContext(tool, e=1, m=9)
 
if ctx == 'RotateSuperContext':
   
    tool = 'Rotate'
    mode = cmds.manipRotateContext(tool, q=1, m=1)
   
    if mode == 0:
        cmds.manipRotateContext(tool, e=1, m=9)
    elif mode == 1:
        cmds.manipRotateContext(tool, e=1, m=9)
    else:
        cmds.manipRotateContext(tool, e=1, m=9)
 
if ctx == 'scaleSuperContext':
   
    tool = 'Scale'
    mode = cmds.manipScaleContext(tool, q=1, m=1)
   
    if mode == 0:
        cmds.manipScaleContext(tool, e=1, m=9)
    elif mode == 2:
        cmds.manipScaleContext(tool, e=1, m=9)
    else:
        cmds.manipScaleContext(tool, e=1, m=9)