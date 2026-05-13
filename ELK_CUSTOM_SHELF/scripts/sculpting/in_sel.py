# ELK_META {"label": "Select Inner Faces", "short_name": "InFace", "tooltip": "Sélectionne automatiquement les faces internes d’un mesh.", "source": "python", "icon_svg": "square-rounded.svg", "icon_color": "#ff5c8a"}
import maya.cmds as cmds
import maya.mel as mel

def save_face_selection_on_original_mesh(original_mesh_name):
    # Get the face selection on the duplicate mesh "In_Sel_Temp_Mesh_B"
    face_selection_on_b = cmds.ls(selection=True, fl=True)

    if not face_selection_on_b:
        cmds.warning("No faces selected on In_Sel_Temp_Mesh_B.")
        return

    # Convert the selection to the original mesh
    face_selection_on_original = [face.replace("In_Sel_Temp_Mesh_B", original_mesh_name) for face in face_selection_on_b]

    # Delete the duplicate mesh "In_Sel_Temp_Mesh_B"
    cmds.delete("In_Sel_Temp_Mesh_B")

    # Unhide the original mesh
    cmds.showHidden(original_mesh_name)

    # Select the original mesh in object mode
    cmds.select(original_mesh_name)
    cmds.selectMode(object=True)

    # Switch to face selection mode and clear the selection
    cmds.selectMode(component=True)
    cmds.selectType(facet=True)
    cmds.select(clear=True)

    # Select the corresponding faces on the original mesh
    cmds.select(face_selection_on_original)

    print(f"In_Sel_Temp_Mesh_B has been deleted. Original mesh '{original_mesh_name}' is unhidden. Face selection recovered on original mesh: {face_selection_on_original}")

    # Clean up the script job after it's done
    job_id = cmds.scriptJob(listJobs=True)[-1].split(":")[0]
    cmds.scriptJob(kill=int(job_id), force=True)

def save_clear_duplicate_uv_cut_and_wait_for_uv_shell_selection():
    # Get the current selection (edge or face)
    selection = cmds.ls(selection=True, fl=True)

    if not selection:
        cmds.warning("No selection detected.")
        return

    # Determine if the selection is edge or face
    if ".e[" in selection[0]:
        selection_type = "edge"
    elif ".f[" in selection[0]:
        selection_type = "face"
        # Convert face selection to edge perimeter
        mel.eval('ConvertSelectionToEdgePerimeter;')
        selection = cmds.ls(selection=True, fl=True)
        selection_type = "edge"
    else:
        cmds.warning("Unsupported selection type. Please select edges or faces.")
        return

    # Extract the object from the selection
    objects = list(set([sel.split('.')[0] for sel in selection]))

    if len(objects) > 1:
        cmds.warning("Multiple objects are selected. This script only works with one object at a time.")
        return

    original_mesh_name = objects[0]

    # Clear the selection
    cmds.select(clear=True)

    # Switch to object mode and select the original mesh
    cmds.select(original_mesh_name)
    cmds.selectMode(object=True)

    # Duplicate the original mesh and name it "In_Sel_Temp_Mesh_B"
    duplicate_mesh_name = cmds.duplicate(original_mesh_name, name="In_Sel_Temp_Mesh_B")[0]

    # Hide the original mesh
    cmds.hide(original_mesh_name)

    # Select "In_Sel_Temp_Mesh_B" and apply UV Camera Based Projection
    cmds.select(duplicate_mesh_name)
    cmds.UVCameraBasedProjection()

    # Recover the saved edge selection on "In_Sel_Temp_Mesh_B"
    edge_selection_on_mesh_b = [sel.replace(original_mesh_name, duplicate_mesh_name) for sel in selection]
    cmds.select(edge_selection_on_mesh_b)

    # Perform UV cut using the recovered edge selection on "In_Sel_Temp_Mesh_B"
    cmds.polyMapCut()

    # Switch to UV Shell selection mode on "In_Sel_Temp_Mesh_B" using the provided MEL command
    mel.eval('''
        changeSelectMode -component;
        setComponentPickMask "Facet" true;
        selectType -ocm -alc false;
        selectType -msh true;
        selectType -sf false -se false -suv false -cv false;
    ''')

    print(f"Selection saved on original mesh '{original_mesh_name}'.")
    print(f"Duplicate mesh created and selected: 'In_Sel_Temp_Mesh_B'. Original mesh '{original_mesh_name}' is hidden.")
    print("UV Camera Based Projection applied to 'In_Sel_Temp_Mesh_B'.")
    print("UV cut performed on 'In_Sel_Temp_Mesh_B' using the recovered selection.")
    print("Switched to UV Shell selection mode on 'In_Sel_Temp_Mesh_B'. Please select a UV shell.")

    # Set up a script job to wait for user selection on "In_Sel_Temp_Mesh_B"
    script_job_id = cmds.scriptJob(event=["SelectionChanged", lambda: save_face_selection_on_original_mesh(original_mesh_name)], runOnce=True)

# Execute the function
save_clear_duplicate_uv_cut_and_wait_for_uv_shell_selection()