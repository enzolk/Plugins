# ELK_META {"label": "TrimAuto", "short_name": "", "tooltip": "Using A trimmed plane as a reference, it automaticly place the UV Shells inside Trimmed Area", "source": "python", "icon_svg": "package-export.svg", "icon_color": "#4bc8ff"}
import maya.cmds as cmds
import random

# Global storage for selections
global_trimmed_plane = None      # Will store the trimmed plane object name
global_uv_shells = []            # Will store a list of UV shell groups (each is a list of UV component names)

# -----------------------------
# Helper functions
# -----------------------------

def get_uv_shells_from_selection(selection):
    """
    Given a list of UV components (from selection), group them by UV shell.
    Returns a list of shells; each shell is a list of UV component names.
    """
    shells = []
    processed = set()
    # Convert selection to UV components
    all_uvs = cmds.polyListComponentConversion(selection, toUV=True)
    if not all_uvs:
        return shells
    all_uvs = cmds.ls(all_uvs, flatten=True)
    
    for uv in all_uvs:
        if uv in processed:
            continue
        # Select one UV and expand to the entire shell:
        cmds.select(uv, replace=True)
        cmds.polySelectConstraint(mode=2, type=0x0010, shell=1)
        shell_group = cmds.ls(selection=True, flatten=True)
        cmds.polySelectConstraint(disable=True)
        if shell_group:
            shells.append(shell_group)
            processed.update(shell_group)
    return shells

def get_uv_shell_bbox(uv_shell):
    """
    Given a list of UV component names, compute the bounding box in UV space.
    Returns a dictionary with minU, maxU, minV, maxV, center_U, center_V, and height.
    """
    minU = minV = 1e9
    maxU = maxV = -1e9
    for uv in uv_shell:
        # Query the UV coordinate; polyEditUV returns [u, v]
        coord = cmds.polyEditUV(uv, query=True)
        if not coord:
            continue
        u, v = coord[0], coord[1]
        minU = min(minU, u)
        maxU = max(maxU, u)
        minV = min(minV, v)
        maxV = max(maxV, v)
    center_U = (minU + maxU) / 2.0
    center_V = (minV + maxV) / 2.0
    height = maxV - minV
    return {
        'minU': minU,
        'maxU': maxU,
        'minV': minV,
        'maxV': maxV,
        'center_U': center_U,
        'center_V': center_V,
        'height': height
    }

def translate_uv_shell(uv_shell, du, dv):
    """
    Translates every UV in the shell by du, dv.
    """
    for uv in uv_shell:
        cmds.polyEditUV(uv, u=du, v=dv, relative=True)

def scale_uv_shell_V(uv_shell, scale_factor, pivotV):
    """
    Scales the UV shell in the V axis by scale_factor relative to the pivotV.
    Each UV's V coordinate is adjusted by a relative offset computed as:
        delta_v = (currentV - pivotV) * (scale_factor - 1)
    so that the scaling occurs about pivotV.
    """
    for uv in uv_shell:
        coord = cmds.polyEditUV(uv, query=True)
        if not coord:
            continue
        v = coord[1]
        delta_v = (v - pivotV) * (scale_factor - 1)
        cmds.polyEditUV(uv, v=delta_v, relative=True)

# -----------------------------
# UI Functions
# -----------------------------

def save_trimmed_plane(*args):
    """
    Save the selected trimmed plane.
    """
    global global_trimmed_plane
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.confirmDialog(title='Error', message='No object selected for trimmed plane.')
        return
    global_trimmed_plane = sel[0]
    cmds.confirmDialog(title='Saved', message='Trimmed plane saved: ' + global_trimmed_plane)

def save_uv_shells(*args):
    """
    Save the selected UV shells.
    """
    global global_uv_shells
    sel = cmds.ls(selection=True)
    if not sel:
        cmds.confirmDialog(title='Error', message='No UV components selected.')
        return
    shells = get_uv_shells_from_selection(sel)
    if not shells:
        cmds.confirmDialog(title='Error', message='Could not determine UV shells from selection.')
        return
    global_uv_shells = shells
    cmds.confirmDialog(title='Saved', message=f'{len(shells)} UV shell(s) saved.')

def execute_processing(*args):
    """
    For each saved UV shell, find the trimmed plane UV shell with the closest height
    within a tolerance range (as defined in the UI), center it, scale the shell in the V axis
    so that its height matches the target, and then apply a random horizontal (U axis)
    translation. If any UV falls outside the [0,1] U/V area after the random translation,
    the shell is shifted back so that it fully lies within [0,1].
    """
    global global_trimmed_plane, global_uv_shells
    if not global_trimmed_plane:
        cmds.confirmDialog(title='Error', message='No trimmed plane saved.')
        return
    if not global_uv_shells:
        cmds.confirmDialog(title='Error', message='No UV shells saved.')
        return
    
    # Get tolerance percentage from UI
    tolerance_percent = cmds.floatField('toleranceField', query=True, value=True)

    # Get all UV shells from the trimmed plane.
    trimmed_plane_shells = get_uv_shells_from_selection([global_trimmed_plane])
    if not trimmed_plane_shells:
        cmds.confirmDialog(title='Error', message='No UV shells found on the trimmed plane.')
        return

    # Process each saved UV shell.
    for sel_shell in global_uv_shells:
        # Compute bounding box for the selected UV shell.
        bbox_sel = get_uv_shell_bbox(sel_shell)
        height_sel = bbox_sel['height']
        center_sel = (bbox_sel['center_U'], bbox_sel['center_V'])
        
        # Find candidate trimmed plane UV shells within the tolerance range.
        candidate_shells = []
        for t_shell in trimmed_plane_shells:
            bbox_t = get_uv_shell_bbox(t_shell)
            if abs(bbox_t['height'] - height_sel) <= tolerance_percent * height_sel:
                candidate_shells.append((t_shell, bbox_t))
        
        # Choose a target shell.
        if candidate_shells:
            target_shell = random.choice(candidate_shells)
        else:
            # Fallback: choose the shell with the minimum absolute difference.
            min_diff = 1e9
            target_shell = None
            for t_shell in trimmed_plane_shells:
                bbox_t = get_uv_shell_bbox(t_shell)
                diff = abs(bbox_t['height'] - height_sel)
                if diff < min_diff:
                    min_diff = diff
                    target_shell = (t_shell, bbox_t)
        if not target_shell:
            continue  # Skip if no matching shell is found

        t_shell, bbox_target = target_shell
        center_target = (bbox_target['center_U'], bbox_target['center_V'])
        target_height = bbox_target['height']

        # Translate the selected shell to center with the target trimmed plane UV shell.
        du = center_target[0] - center_sel[0]
        dv = center_target[1] - center_sel[1]
        translate_uv_shell(sel_shell, du, dv)

        # Recompute the bounding box after translation.
        bbox_sel = get_uv_shell_bbox(sel_shell)
        height_sel = bbox_sel['height']
        pivotV = bbox_sel['center_V']

        # Scale the selected shell in the V axis so its height matches the target height.
        if height_sel > 0:
            scale_factor = target_height / height_sel
            scale_uv_shell_V(sel_shell, scale_factor, pivotV)
        
        # --- Random Horizontal Translation and Clamping ---
        # Generate a random U offset between -1 and 1.
        rand_u_offset = random.uniform(-1, 1)
        translate_uv_shell(sel_shell, rand_u_offset, 0)
        
        # Check the bounding box after random translation.
        bbox_after = get_uv_shell_bbox(sel_shell)
        du_correction = 0
        dv_correction = 0
        
        # Correct U if out of bounds.
        if bbox_after['minU'] < 0:
            du_correction = -bbox_after['minU']
        elif bbox_after['maxU'] > 1:
            du_correction = 1 - bbox_after['maxU']
        
        # Optionally, check V as well in case it goes out of bounds.
        if bbox_after['minV'] < 0:
            dv_correction = -bbox_after['minV']
        elif bbox_after['maxV'] > 1:
            dv_correction = 1 - bbox_after['maxV']
        
        if du_correction != 0 or dv_correction != 0:
            translate_uv_shell(sel_shell, du_correction, dv_correction)
        
    cmds.confirmDialog(title='Processing Complete', message='All selected UV shells have been centered, scaled, and randomly translated.')

def create_ui():
    """
    Create the interface.
    """
    if cmds.window('uvShellProcessWindow', exists=True):
        cmds.deleteUI('uvShellProcessWindow')
    
    window = cmds.window('uvShellProcessWindow', title='UV Shell Processor', widthHeight=(300, 320))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
    
    cmds.text(label='Step 1: Save Trimmed Plane')
    cmds.button(label='Save Selected Trimmed Plane', command=save_trimmed_plane)
    
    cmds.separator(height=10, style='in')
    
    cmds.text(label='Step 2: Save UV Shells to Process')
    cmds.button(label='Save Selected UV Shells', command=save_uv_shells)
    
    cmds.separator(height=10, style='in')
    
    cmds.text(label='Step 3: Adjust Tolerance, Process, and Random U Translation')
    cmds.text(label='Tolerance Percentage (e.g., 0.10 for 10%):')
    cmds.floatField('toleranceField', value=0.10, minValue=0.0, maxValue=1.0)
    
    cmds.separator(height=10, style='in')
    
    cmds.button(label='Execute', command=execute_processing)
    
    cmds.showWindow(window)

# Run the UI
create_ui()