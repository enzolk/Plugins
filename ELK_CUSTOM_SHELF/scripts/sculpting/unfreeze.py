# ELK_META {"label": "Unfreeze Components", "short_name": "UnFrz", "tooltip": "Réactive les composants précédemment figés.", "source": "python", "icon_svg": "lock-open.svg", "icon_color": "#ff5c8a"}
import maya.cmds as mc

def unfreeze_selected_components():
    getSel = getFrozenSelection()
    if getSel:
        for i in getSel[0]:
            mc.setAttr('{}.freeze[{}]'.format(getSel[1], i), False)
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

# Run the script to unfreeze the selected components
unfreeze_selected_components()