# ELK_META {"label": "ProSeparate", "short_name": "", "tooltip": "Separate", "source": "python"}
import maya.cmds as cmds

def separate_and_rename_simple():
    # Variable to store the initial face selection
    saved_faces = []
    original_object = None

    # Check if the selection is a face selection
    selected_faces = cmds.ls(selection=True, fl=True)
    if selected_faces and ".f[" in selected_faces[0]:
        # Save the face selection
        saved_faces = selected_faces

        # Extract the object name from the selected face
        original_object = selected_faces[0].split(".f[")[0]
        
        # Perform polyChipOff to separate the faces
        cmds.polyChipOff(selected_faces, keepFacesTogether=True)
        
        # Switch to object selection mode and select the object
        cmds.selectMode(object=True)
        cmds.select(original_object)
    else:
        # Get the selected objects (if no faces were selected)
        selected_objects = cmds.ls(selection=True, type='transform')
        if not selected_objects:
            cmds.error("No objects selected.")
            return
        original_object = selected_objects[0]

    # Proceed with separation and renaming
    separated_parts = cmds.polySeparate(original_object)

    # Filter out non-transform nodes that might have been included
    separated_parts = [part for part in separated_parts if cmds.nodeType(part) == 'transform']
    
    # Store the name of the newly renamed object for face deletion later
    renamed_object_name = None

    # Delete history and freeze transformations on each part
    for i, part in enumerate(separated_parts):
        # Rename the part
        new_name = f"{original_object}_Part{i+1}"
        renamed_part = cmds.rename(part, new_name)

        # Save the renamed object name if it corresponds to the original object
        if i == 0:
            renamed_object_name = renamed_part

        # Clean up the part
        cmds.delete(renamed_part, ch=True)
        cmds.makeIdentity(renamed_part, apply=True, t=1, r=1, s=1, n=0)

    # Remove the saved faces using the renamed object
    if saved_faces and renamed_object_name:
        # Update the face selection with the new object name
        updated_faces = [face.replace(original_object, renamed_object_name) for face in saved_faces]
        cmds.select(updated_faces)
        cmds.delete()

    print("Separation, cleanup, renaming, and face removal completed successfully.")

# Execute the function
separate_and_rename_simple()