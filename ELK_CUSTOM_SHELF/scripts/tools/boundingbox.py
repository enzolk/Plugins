# ELK_META {"label": "BoundingBox", "short_name": "", "tooltip": "import maya.cmds as cmds\n\n# Define a function to fill the selection in Maya\ndef fillSelection():\n    # Get the current selection\n    sel = cmds.ls(selection=True)\n    \n    # If there is nothing selected, do nothing\n    if not sel:\n        return\n    \n    # Get the bounding box of the current selection\n    boundingBox = cmds.exactWorldBoundingBox(sel)\n    \n    # Create a cube with the same dimensions as the bounding box\n    cube = cmds.polyCube(w=boundingBox[3]-boundingBox[0], h=boundingBox[4]-bo", "source": "python", "icon_svg": "tools-kitchen-2.svg", "icon_color": "#36d6ff"}
import maya.cmds as cmds

# Define a function to fill the selection in Maya
def fillSelection():
    # Get the current selection
    sel = cmds.ls(selection=True)
    
    # If there is nothing selected, do nothing
    if not sel:
        return
    
    # Get the bounding box of the current selection
    boundingBox = cmds.exactWorldBoundingBox(sel)
    
    # Create a cube with the same dimensions as the bounding box
    cube = cmds.polyCube(w=boundingBox[3]-boundingBox[0], h=boundingBox[4]-boundingBox[1], d=boundingBox[5]-boundingBox[2])
    
    # Position the cube at the center of the bounding box
    cmds.move(boundingBox[0]+(boundingBox[3]-boundingBox[0])/2, boundingBox[1]+(boundingBox[4]-boundingBox[1])/2, boundingBox[2]+(boundingBox[5]-boundingBox[2])/2)

# Call the function to fill the selection
fillSelection()