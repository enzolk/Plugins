# ELK_META {"label": "SmartExporter", "short_name": "", "tooltip": "Smrt Exporter Tool", "source": "python", "icon_svg": "table-export.svg", "icon_color": "#4bc8ff"}
from pathlib import Path
import maya.cmds as cmds
import maya.mel as mel

# ---------- Gestion des labels avec emojis ----------

USE_EMOJI = True  # Mets False si tu veux repasser en ASCII uniquement

def U(hex_code, fallback=""):
    """Retourne un caractre Unicode depuis son code hex, ou fallback."""
    try:
        return chr(int(hex_code, 16)) if USE_EMOJI else fallback
    except:
        return fallback

def L(emoji_hex, text):
    """Construit un label avec emoji + texte (si activ)."""
    emoji = U(emoji_hex, "")
    return f"{emoji} {text}" if emoji else text

# ---------- UI ----------

def show_export_ui():
    if cmds.window("customExportWin", exists=True):
        cmds.deleteUI("customExportWin")

    cmds.window("customExportWin", title="Custom Exporter", sizeable=False)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10,
                      columnAlign="center", columnAttach=("both", 10))

    cmds.optionMenu("exportFormat", label=L("1F4DD", "Format :"))  # ??
    cmds.menuItem(label="fbx")
    cmds.menuItem(label="obj")

    cmds.checkBox("triangulateCheck", label=L("1F9CA", "Triangulation"), value=False)  # ??
    cmds.checkBox("moveToOriginCheck", label=L("1F3AF", "Move to Origin (utilise le pivot)"), value=True)  # ??

    cmds.optionMenu("upAxisMenu", label=L("1F9ED", "UP Axis :"))  # ??
    cmds.menuItem(label="Y")
    cmds.menuItem(label="Z")

    cmds.textFieldButtonGrp("pathField", label=L("1F4C1", "Dossier export :"),  # ??
                            buttonLabel="Parcourir", text="", buttonCommand=browse_folder)
    cmds.textFieldGrp("groupStringField", label=L("1F50E", "Groupe  exporter si contient :"), text="SM_")  # ??

    cmds.checkBox("autoSubdirsCheck", label=L("1F4C2", "Crer Sous-Dossiers (chane des GRP_ uniquement)"), value=True)  # ??

    cmds.button(label=L("1F680", "Exporter la slection"), command=perform_export)  # ??
    cmds.setParent("..")
    cmds.showWindow("customExportWin")

def browse_folder(*args):
    folder = cmds.fileDialog2(dialogStyle=2, fileMode=3)
    if folder:
        cmds.textFieldButtonGrp("pathField", edit=True, text=folder[0])

def perform_export(*args):
    fmt = cmds.optionMenu("exportFormat", query=True, value=True)
    triangulate = cmds.checkBox("triangulateCheck", query=True, value=True)
    move_to_origin = cmds.checkBox("moveToOriginCheck", query=True, value=True)
    up_axis = cmds.optionMenu("upAxisMenu", query=True, value=True)
    path = cmds.textFieldButtonGrp("pathField", query=True, text=True)
    group_identifier = cmds.textFieldGrp("groupStringField", query=True, text=True)
    auto_subdirs = cmds.checkBox("autoSubdirsCheck", query=True, value=True)

    print(f"\n?? Format : {fmt}\n?? Triangulation : {triangulate}\n?? Move to Origin : {move_to_origin}\n?? UP Axis : {up_axis}\n?? Dossier export : {path}\n?? Sous-dossiers auto : {auto_subdirs}\n")

    if not path or not Path(path).exists():
        cmds.confirmDialog(title="Erreur", message="Le chemin dexport est invalide.", button=["OK"])
        return

    sel = cmds.ls(selection=True, long=True)
    if not sel:
        cmds.confirmDialog(title="Erreur", message="Veuillez slectionner au moins un objet.", button=["OK"])
        return

    for obj in sel:
        print(f"?? Analyse de : {obj}")
        export_node(obj, fmt, triangulate, move_to_origin, up_axis, path, group_identifier, auto_subdirs)

    print("\n? Export termin pour tous les objets slectionns.")

# ---------- Helpers noms/chemins ----------

def _basename_from_longname(longname):
    short = longname.split("|")[-1]
    return short.split(":")[-1]

def _ancestors_from_longname(longname):
    parts = [p for p in longname.split("|") if p]
    if len(parts) <= 1:
        return []
    ancestors = parts[:-1]
    return [a.split(":")[-1] for a in ancestors]

def _group_folder_chain(longname):
    ancestors = _ancestors_from_longname(longname)
    return [a for a in ancestors if a.startswith("GRP_")]

# ---------- Export logique ----------

def export_node(node, fmt, triangulate, move_to_origin, up_axis, export_path, identifier, auto_subdirs):
    name = _basename_from_longname(node)
    if identifier in name:
        _export_single_node(node, name, fmt, triangulate, move_to_origin, up_axis, export_path, auto_subdirs)
    else:
        children = cmds.listRelatives(node, children=True, type="transform", fullPath=True) or []
        if not children:
            shapes = cmds.listRelatives(node, shapes=True, fullPath=True)
            if shapes:
                _export_single_node(node, name, fmt, triangulate, move_to_origin, up_axis, export_path, auto_subdirs)
        else:
            for child in children:
                export_node(child, fmt, triangulate, move_to_origin, up_axis, export_path, identifier, auto_subdirs)

def _get_scene_up_axis():
    return cmds.upAxis(query=True, axis=True).upper()

def _apply_up_axis_correction(temp_node, desired_up, fmt):
    desired = desired_up.upper()
    scene_up = _get_scene_up_axis()
    if scene_up == desired:
        return
    if fmt.lower() == "fbx":
        sign = -1 if (scene_up == "Y" and desired == "Z") else +1
    else:
        sign = +1 if (scene_up == "Y" and desired == "Z") else -1
    cmds.rotate(90 * sign, 0, 0, temp_node, relative=True, os=True)

def _export_single_node(original_node, name, fmt, triangulate, move_to_origin, up_axis, export_path, auto_subdirs):
    dest_dir = Path(export_path).joinpath(*_group_folder_chain(original_node)) if auto_subdirs else Path(export_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    export_file = dest_dir / f"{name}.{fmt}"

    temp = cmds.duplicate(original_node, name=f"{name}_tempExport")[0]
    try: cmds.parent(temp, world=True)
    except: pass

    _apply_up_axis_correction(temp, up_axis, fmt)

    if fmt == "obj" and triangulate:
        meshes = cmds.listRelatives(temp, allDescendents=True, type="mesh", fullPath=True) or []
        if meshes:
            parents = list({cmds.listRelatives(m, parent=True, fullPath=True)[0] for m in meshes})
            cmds.select(parents, r=True)
            cmds.polyTriangulate()

    if move_to_origin:
        rp = cmds.xform(temp, q=True, ws=True, rp=True)
        cmds.move(-rp[0], -rp[1], -rp[2], temp, r=True, ws=True)

    cmds.makeIdentity(temp, apply=True, translate=True, rotate=True, scale=True)

    cmds.select(temp, replace=True)

    try:
        if fmt == "fbx":
            mel.eval('FBXResetExport;')
            mel.eval(f'FBXExportUpAxis "{up_axis.upper()}";')
            mel.eval('FBXExportSmoothingGroups -v true;')
            mel.eval('FBXExportTangents -v true;')
            mel.eval('FBXExportSmoothMesh -v true;')
            mel.eval('FBXExportHardEdges -v false;')
            mel.eval('FBXExportBakeComplexAnimation -v false;')
            mel.eval('FBXExportInputConnections -v true;')
            mel.eval('FBXExportInAscii -v false;')
            mel.eval(f'FBXExportTriangulate -v {"true" if triangulate else "false"};')
            mel.eval(f'FBXExport -f "{export_file.as_posix()}" -s;')
        elif fmt == "obj":
            cmds.file(
                export_file.as_posix(),
                force=True,
                options="groups=1;ptgroups=1;materials=1;smoothing=1;normals=1",
                typ="OBJexport",
                pr=True,
                es=True
            )
    except Exception as e:
        print(f"? ERREUR export {name} : {e}")

    cmds.delete(temp)

# ---------- Lancer UI ----------
show_export_ui()