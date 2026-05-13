# ELK_META {"label": "Freeze Components", "short_name": "Freeze", "tooltip": "Fige les composants sélectionnés afin de verrouiller temporairement leur comportement.", "source": "python", "icon_svg": "lock.svg", "icon_color": "#ff5c8a"}
import maya.cmds as mc

def freeze_selected_components():
    getSel = getFrozenSelection()
    if getSel:
        for i in getSel[0]:
            mc.setAttr('{}.freeze[{}]'.format(getSel[1], i), True)
        freezeVpRefresh()

def getFrozenSelection():
    getSel = mc.polyListComponentConversion(ff=True, fe=True, fv=True, tv=True)
    if getSel:
        getSel = mc.ls(getSel, fl=True)
        getIndices = [int(x.split('[')[1].split(']')[0]) for x in getSel]
        getTransform = getSel[0].split('.')[0]
        return getIndices, getTransform
    return None

def freezeVpRefresh():
    if mc.contextInfo('sculptMeshCacheContext', ex=True):
        if mc.currentCtx() == 'sculptMeshCacheContext':
            mc.setToolTo('selectSuperContext')
            mc.setToolTo('sculptMeshCacheContext')
        else:
            mc.setToolTo('sculptMeshCacheContext')

# Run the script to freeze the selected components
freeze_selected_components()