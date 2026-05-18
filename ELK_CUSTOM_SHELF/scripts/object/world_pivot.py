# ELK_META {"label": "World Pivot", "short_name": "WorldPiv", "tooltip": "Alterne rapidement différents modes de pivot dans Maya.", "source": "python", "icon_svg": "world.svg", "icon_color": "#ffad3b", "apply_elk_ui_style": false, "quick_favorite": false, "secondary_scripts": []}
import maya.cmds as cmds
 
ctx = cmds.currentCtx()
 
if ctx == 'moveSuperContext':
   
    tool = 'Move'
    mode = cmds.manipMoveContext(tool, q=1, m=1)
    if mode == 0:
        cmds.manipMoveContext(tool, e=1, m=2)
    elif mode == 2:
        cmds.manipMoveContext(tool, e=1, m=2)
    else:
        cmds.manipMoveContext(tool, e=1, m=2)
 
if ctx == 'RotateSuperContext':
   
    tool = 'Rotate'
    mode = cmds.manipRotateContext(tool, q=1, m=1)
   
    if mode == 0:
        cmds.manipRotateContext(tool, e=1, m=1)
    elif mode == 1:
        cmds.manipRotateContext(tool, e=1, m=1)
    else:
        cmds.manipRotateContext(tool, e=1, m=1)
 
if ctx == 'scaleSuperContext':
   
    tool = 'Scale'
    mode = cmds.manipScaleContext(tool, q=1, m=1)
   
    if mode == 0:
        cmds.manipScaleContext(tool, e=1, m=2)
    elif mode == 2:
        cmds.manipScaleContext(tool, e=1, m=2)
    else:
        cmds.manipScaleContext(tool, e=1, m=2)