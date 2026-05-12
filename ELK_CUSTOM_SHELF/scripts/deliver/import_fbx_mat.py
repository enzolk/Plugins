# ELK_META {"label": "Import FBX Mat", "short_name": "", "tooltip": "Import an FBX, but check if already same materials exists in the scene", "source": "python"}
import maya.cmds as cmds
import maya.mel as mel
import os

def reassign_materials(original_materials):
    # Get a list of all materials in the scene after import
    imported_materials = cmds.ls(mat=True)

    # Iterate through the imported materials and compare with original materials
    for material in imported_materials:
        if material not in original_materials:
            # Extract the base name of the material (without any suffix)
            base_name = material.rstrip("0123456789")

            if base_name in original_materials:
                # If a material with the same base name exists, reassign it
                print(f"Material '{material}' found as existing material '{base_name}'. Reassigning...")
                assigned_objects = cmds.listConnections(material + '.outColor', type='shadingEngine')
                if assigned_objects:
                    for shading_group in assigned_objects:
                        connected_objects = cmds.sets(shading_group, q=True)
                        if connected_objects:
                            cmds.select(connected_objects, r=True)
                            cmds.hyperShade(assign=base_name)
                # Delete the newly imported duplicate material
                cmds.delete(material)
            else:
                print(f"Material '{material}' is unique, keeping it.")
        else:
            print(f"Material '{material}' is an original material, keeping it.")

def import_fbx_without_creating_materials():
    # Open a file dialog to select the FBX file
    fbx_path = cmds.fileDialog2(fileFilter="*.fbx", dialogStyle=2, fileMode=1, caption="Import FBX File")

    # Check if the user selected a file
    if fbx_path:
        fbx_path = fbx_path[0]
        if not os.path.exists(fbx_path):
            cmds.error("File not found.")
            return

        # Store the original materials before import
        original_materials = cmds.ls(materials=True)

        # Import the FBX file
        cmds.file(fbx_path, i=True, type="FBX", ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace=":", options="fbx")

        # Call the function to reassign materials after import
        reassign_materials(original_materials)
    else:
        cmds.error("No file selected.")

# Execute the function to display the file dialog and import the FBX
import_fbx_without_creating_materials()
