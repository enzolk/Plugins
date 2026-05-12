# ELK_META {"label": "Obj_A", "short_name": "", "tooltip": "import maya.cmds as cmds\n \nctx = cmds.currentCtx()\n \nif ctx == '...", "source": "python", "icon_svg": "cube.svg", "icon_color": "#5ee06c"}
import maya.cmds as cmds
 
ctx = cmds.currentCtx()
 
if ctx == 'moveSuperContext':
   
    tool = 'Move'
    mode = cmds.manipMoveContext(tool, q=1, m=1)
    if mode == 0:
        cmds.manipMoveContext(tool, e=1, m=0)
    elif mode == 2:
        cmds.manipMoveContext(tool, e=1, m=0)
    else:
        cmds.manipMoveContext(tool, e=1, m=0)
 
if ctx == 'RotateSuperContext':
   
    tool = 'Rotate'
    mode = cmds.manipRotateContext(tool, q=1, m=1)
   
    if mode == 0:
        cmds.manipRotateContext(tool, e=1, m=0) 
    elif mode == 1:
        cmds.manipRotateContext(tool, e=1, m=0) 
    else:
        cmds.manipRotateContext(tool, e=1, m=0) 
 
if ctx == 'scaleSuperContext':
   
    tool = 'Scale'
    mode = cmds.manipScaleContext(tool, q=1, m=1)
   
    if mode == 0:
        cmds.manipScaleContext(tool, e=1, m=0)
    elif mode == 2:
        cmds.manipScaleContext(tool, e=1, m=0)
    else:
        cmds.manipScaleContext(tool, e=1, m=0)