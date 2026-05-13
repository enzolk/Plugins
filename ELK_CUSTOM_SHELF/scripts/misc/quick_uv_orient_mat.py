# ELK_META {"label": "Quick UV Orient Mat", "short_name": "UVMat", "tooltip": "Assign a temporary UV Mat.", "source": "python", "icon_svg": "grid-4x4.svg", "icon_color": "#ff5d3b"}
# -*- coding: utf-8 -*-

import os
import maya.cmds as cmds

WINDOW_NAME = "QuickUVOrientPreview_UI"

MAT_NAME = "TMP_QuickUVOrientPreview_MAT"
SG_NAME = "TMP_QuickUVOrientPreview_SG"
FILE_NODE_NAME = "TMP_QuickUVOrientPreview_FILE"
PLACE2D_NAME = "TMP_QuickUVOrientPreview_PLACE2D"

PREVIOUS_ASSIGNMENTS = {}


def get_script_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except:
        return cmds.internalVar(userScriptDir=True)


def get_texture_path():
    possible_paths = []

    try:
        possible_paths.append(os.path.join(get_script_dir(), "Arrow_Small.png"))
    except:
        pass

    user_profile = os.environ.get("USERPROFILE", "")

    if user_profile:
        possible_paths.append(
            os.path.join(
                user_profile,
                "Documents",
                "maya",
                "scripts",
                "QuickUVOrientPreview",
                "Arrow_Small.png"
            )
        )

        try:
            maya_version = cmds.about(version=True)
            possible_paths.append(
                os.path.join(
                    user_profile,
                    "Documents",
                    "maya",
                    maya_version,
                    "scripts",
                    "QuickUVOrientPreview",
                    "Arrow_Small.png"
                )
            )
        except:
            pass

    for path in possible_paths:
        clean_path = path.replace("\\", "/")
        if os.path.exists(clean_path):
            return clean_path

    cmds.warning(
        "Texture Arrow_Small.png introuvable. Chemins testés :\n{}".format(
            "\n".join([p.replace("\\", "/") for p in possible_paths])
        )
    )
    return None


def get_selected_mesh_transforms():
    selection = cmds.ls(selection=True, long=True) or []
    meshes = []

    for obj in selection:
        if "." in obj:
            obj = obj.split(".")[0]

        if not cmds.objExists(obj):
            continue

        if cmds.nodeType(obj) == "mesh":
            parents = cmds.listRelatives(obj, parent=True, fullPath=True) or []
            if parents:
                meshes.append(parents[0])
        else:
            shapes = cmds.listRelatives(
                obj,
                shapes=True,
                noIntermediate=True,
                type="mesh",
                fullPath=True
            ) or []
            if shapes:
                meshes.append(obj)

    return list(dict.fromkeys(meshes))


def get_shape(transform):
    shapes = cmds.listRelatives(
        transform,
        shapes=True,
        noIntermediate=True,
        type="mesh",
        fullPath=True
    ) or []

    return shapes[0] if shapes else None


def store_previous_material(transform):
    shape = get_shape(transform)

    if not shape:
        return

    shading_engines = cmds.listConnections(shape, type="shadingEngine") or []
    PREVIOUS_ASSIGNMENTS[transform] = list(dict.fromkeys(shading_engines))


def cleanup_preview_nodes():
    for node in [
        SG_NAME,
        MAT_NAME,
        FILE_NODE_NAME,
        PLACE2D_NAME
    ]:
        if not cmds.objExists(node):
            continue

        try:
            cmds.lockNode(node, lock=False)
        except:
            pass

        try:
            cmds.delete(node)
        except:
            pass


def create_preview_material():
    texture_path = get_texture_path()

    if not texture_path or not os.path.exists(texture_path):
        cmds.warning("Texture introuvable : {}".format(texture_path))
        return None

    # Important :
    # On recrée toujours un setup propre pour éviter un ancien shading group corrompu.
    cleanup_preview_nodes()

    mat = cmds.shadingNode(
        "standardSurface",
        asShader=True,
        name=MAT_NAME
    )

    sg = cmds.sets(
        renderable=True,
        noSurfaceShader=True,
        empty=True,
        name=SG_NAME
    )

    try:
        cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
    except:
        pass

    file_node = cmds.shadingNode(
        "file",
        asTexture=True,
        isColorManaged=True,
        name=FILE_NODE_NAME
    )

    place2d = cmds.shadingNode(
        "place2dTexture",
        asUtility=True,
        name=PLACE2D_NAME
    )

    cmds.setAttr(file_node + ".fileTextureName", texture_path, type="string")

    connections = [
        ("coverage", "coverage"),
        ("translateFrame", "translateFrame"),
        ("rotateFrame", "rotateFrame"),
        ("mirrorU", "mirrorU"),
        ("mirrorV", "mirrorV"),
        ("stagger", "stagger"),
        ("wrapU", "wrapU"),
        ("wrapV", "wrapV"),
        ("repeatUV", "repeatUV"),
        ("offset", "offset"),
        ("rotateUV", "rotateUV"),
        ("noiseUV", "noiseUV"),
        ("vertexUvOne", "vertexUvOne"),
        ("vertexUvTwo", "vertexUvTwo"),
        ("vertexUvThree", "vertexUvThree"),
        ("vertexCameraOne", "vertexCameraOne"),
        ("outUV", "uvCoord"),
        ("outUvFilterSize", "uvFilterSize"),
    ]

    for src, dst in connections:
        try:
            cmds.connectAttr(
                place2d + "." + src,
                file_node + "." + dst,
                force=True
            )
        except:
            pass

    try:
        cmds.connectAttr(file_node + ".outColor", mat + ".baseColor", force=True)
    except:
        pass

    try:
        cmds.connectAttr(file_node + ".outColor", mat + ".emissionColor", force=True)
    except:
        pass

    try:
        cmds.setAttr(mat + ".base", 0.0)
        cmds.setAttr(mat + ".emission", 1.0)
        cmds.setAttr(mat + ".roughness", 1.0)
    except:
        pass

    return sg


def apply_uv_preview_material():
    meshes = get_selected_mesh_transforms()

    if not meshes:
        cmds.warning("Sélectionne au moins un mesh.")
        return

    sg = create_preview_material()

    if not sg:
        return

    for mesh in meshes:
        store_previous_material(mesh)

        try:
            cmds.sets(mesh, edit=True, forceElement=sg)
        except Exception as e:
            cmds.warning(
                "Impossible d'assigner le matériau à {} : {}".format(mesh, e)
            )

    cmds.inViewMessage(
        amg="Quick UV Orient Preview <hl>appliqué</hl>.",
        pos="midCenter",
        fade=True
    )


def reset_uv_preview_material():
    global PREVIOUS_ASSIGNMENTS

    for mesh, shading_engines in PREVIOUS_ASSIGNMENTS.items():
        if not cmds.objExists(mesh):
            continue

        restored = False

        if shading_engines:
            for sg in shading_engines:
                if not cmds.objExists(sg):
                    continue

                try:
                    cmds.sets(mesh, edit=True, forceElement=sg)
                    restored = True
                    break
                except:
                    pass

        if not restored:
            try:
                cmds.sets(mesh, edit=True, forceElement="initialShadingGroup")
            except:
                pass

    cleanup_preview_nodes()
    PREVIOUS_ASSIGNMENTS = {}

    cmds.inViewMessage(
        amg="Quick UV Orient Preview <hl>reset</hl>.",
        pos="midCenter",
        fade=True
    )


def show_ui():
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)

    cmds.window(
        WINDOW_NAME,
        title="Quick UV Orient Preview",
        sizeable=False
    )

    cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=8,
        columnAlign="center"
    )

    cmds.text(
        label="Quick UV Orient Preview",
        height=28,
        align="center"
    )

    cmds.button(
        label="Apply Arrow Preview Material",
        height=34,
        command=lambda *_: apply_uv_preview_material()
    )

    cmds.button(
        label="Reset Previous Material",
        height=34,
        command=lambda *_: reset_uv_preview_material()
    )

    cmds.separator(height=8)

    cmds.text(
        label="Texture attendue : Arrow_Small.png",
        align="center"
    )

    cmds.showWindow(WINDOW_NAME)


show_ui()