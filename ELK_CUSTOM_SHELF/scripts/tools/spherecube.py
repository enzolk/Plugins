# ELK_META {"label": "Quad Sphere Creator", "short_name": "QSphere", "tooltip": "Génère automatiquement une sphère quad propre à partir d’un cube subdivisé.", "source": "python", "icon_svg": "sphere.svg", "icon_color": "#36d6ff"}
import maya.cmds as cmds

def create_quad_sphere_ui():
    """
    Creates a UI for the Quad Sphere Generator.
    """
    window_name = "quadSphereWindow"
    
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
    
    cmds.window(window_name, title="Quad Sphere Generator", widthHeight=(300, 200))
    cmds.columnLayout(adjustableColumn=True)
    
    # Sphere Radius Slider
    cmds.floatSliderGrp('sphereRadiusSlider', label="Sphere Radius", field=True, minValue=0.1, maxValue=100, value=30, step=0.1)
    
    # Smooth Divisions Slider
    cmds.intSliderGrp('smoothDivisionsSlider', label="Smooth Divisions", field=True, minValue=0, maxValue=6, value=3)
    
    # UV Mapping Checkbox
    cmds.checkBox('uvMappingCheckbox', label="Generate UVs", value=True)
    
    # Generate Button
    cmds.button(label="Generate Quad Sphere", command=generate_quad_sphere)
    
    cmds.showWindow(window_name)

def generate_quad_sphere(*args):
    """
    Generates a quad sphere based on user input from the UI.
    """
    # Retrieve values from UI
    sphere_radius = cmds.floatSliderGrp('sphereRadiusSlider', query=True, value=True)
    smooth_divisions = cmds.intSliderGrp('smoothDivisionsSlider', query=True, value=True)
    generate_uvs = cmds.checkBox('uvMappingCheckbox', query=True, value=True)
    
    # Calculate cube size
    coefficient_value = 2.3  # Recommended coefficient
    cube_size = sphere_radius * coefficient_value
    
    # Create a poly cube
    cube = cmds.polyCube(width=cube_size, height=cube_size, depth=cube_size, name="quadSphereCube")[0]
    
    # Apply smooth divisions
    for _ in range(smooth_divisions):
        cmds.polySmooth(cube, method=0, divisions=1, smoothUVs=1)
    
    # Create a poly sphere for reference
    sphere = cmds.polySphere(radius=sphere_radius, subdivisionsX=20, subdivisionsY=20, name="quadSphereReference")[0]
    
    # Transfer vertex positions from the sphere to the cube
    cmds.select([sphere, cube])
    cmds.transferAttributes(pos=1)
    
    # Delete history and the reference sphere
    cmds.delete(cube, constructionHistory=True)
    cmds.delete(sphere)
    
    # Rename the cube to the final quad sphere
    quad_sphere = cmds.rename(cube, "quadSphere")
    
    # Generate UVs if selected
    if generate_uvs:
        cmds.select(quad_sphere)
        cmds.unfold()
        cmds.layoutUV(quad_sphere, layoutMethod=2)
    
    # Inform the user
    cmds.inViewMessage(amg='Quad Sphere <hl>created successfully</hl>.', pos='midCenter', fade=True)

# Run the UI
create_quad_sphere_ui()