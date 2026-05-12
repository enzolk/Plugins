# ELK_META {"label": "UV Transfer", "short_name": "", "tooltip": "Transfer the UV between two objects", "source": "python"}
import maya.cmds as cmds

def transfer_uvs_to_target(source_obj):
    # Get the currently selected object as the target object
    target_obj = cmds.ls(selection=True, long=True)
    
    if not target_obj:
        cmds.warning("No target object selected.")
        return
    
    target_obj = target_obj[0]

    # Verify that both source and target have the same topology
    if cmds.polyEvaluate(source_obj, face=True) != cmds.polyEvaluate(target_obj, face=True):
        cmds.warning("Source and target objects do not have the same topology.")
        return

    # Transfer UVs from source to target using polyTransfer
    try:
        cmds.polyTransfer(target_obj, uv=1, alternateObject=source_obj)
        cmds.warning(f"UVs transferred from {source_obj} to {target_obj} successfully.")
    except Exception as e:
        cmds.warning(f"Failed to transfer UVs: {e}")

    # Clear selection
    cmds.select(clear=True)

    # Schedule the cleanup of the scriptJob
    cmds.evalDeferred(kill_script_job)

def kill_script_job():
    global my_script_job
    if cmds.scriptJob(exists=my_script_job):
        cmds.scriptJob(kill=my_script_job, force=True)

def on_target_selected():
    # Get the source object stored in a global variable
    source_obj = cmds.optionVar(q="sourceObj")
    if source_obj:
        transfer_uvs_to_target(source_obj)
    else:
        cmds.warning("No source object found.")

def transfer_uvs():
    # Get the selected objects
    selected_objects = cmds.ls(selection=True, long=True)
    
    if len(selected_objects) != 1:
        cmds.warning("Please select the source object only.")
        return
    
    source_obj = selected_objects[0]
    cmds.optionVar(sv=("sourceObj", source_obj))
    
    # Notify the user to select the target object
    cmds.warning("Please select the target object to transfer UVs to.")
    
    # Set up a scriptJob to wait for the next selection
    global my_script_job
    my_script_job = cmds.scriptJob(event=["SelectionChanged", on_target_selected], runOnce=True)

# Run the function
transfer_uvs()
