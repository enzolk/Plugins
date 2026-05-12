# ELK_META {"label": "ProInst", "short_name": "", "tooltip": "import maya.cmds as cmds\n\ndef rename_freeze_instance():\n    \"\"\"Renomme l'objet slectionn, applique Freeze Transform et Bake Pivot,\n    cre une instance avec un nom unique et replace l'objet original au centre du monde.\"\"\"\n    \n    selected_objects = cmds.ls(selection=True)\n    \n    if not selected_objects:\n        cmds.warning(\"Aucun objet slectionn ! Veuillez slectionner un objet  renommer.\")\n        return\n    \n    def get_unique_name(base_name):\n        \"\"\"Gnre un nom unique en ajoutant un su", "source": "python", "icon_svg": "click.svg", "icon_color": "#ff9f2e"}
import maya.cmds as cmds

def rename_freeze_instance():
    """Renomme l'objet slectionn, applique Freeze Transform et Bake Pivot,
    cre une instance avec un nom unique et replace l'objet original au centre du monde."""
    
    selected_objects = cmds.ls(selection=True)
    
    if not selected_objects:
        cmds.warning("Aucun objet slectionn ! Veuillez slectionner un objet  renommer.")
        return
    
    def get_unique_name(base_name):
        """Gnre un nom unique en ajoutant un suffixe numrique si ncessaire."""
        count = 1
        unique_name = base_name
        while cmds.objExists(unique_name):
            unique_name = f"{base_name}_{count}"
            count += 1
        return unique_name
    
    def apply_changes(*args):
        new_name = cmds.textField(rename_field, query=True, text=True)
        if new_name:
            # Renommer l'objet slectionn
            renamed_object = cmds.rename(selected_objects[0], new_name)
            
            # Appliquer Freeze Transformations
            cmds.makeIdentity(renamed_object, apply=True, translate=True, rotate=True, scale=True, normal=False)
            
            # Appliquer Bake Pivot
            cmds.BakeCustomPivot()
            
            # Obtenir la position actuelle de l'objet
            position = cmds.xform(renamed_object, query=True, worldSpace=True, translation=True)
            
            # Gnrer un nom unique pour l'instance
            instance_name = get_unique_name(f"{new_name}_Instance")
            
            # Crer une instance avec un nom unique
            instance_object = cmds.instance(renamed_object, name=instance_name)[0]
            
            # Remettre l'instance  la mme position
            cmds.xform(instance_object, worldSpace=True, translation=position)
            
            # Placer l'objet original au centre du monde
            cmds.xform(renamed_object, worldSpace=True, translation=[0, 0, 0])
            
            # Fermer la fentre aprs application
            cmds.deleteUI(window, window=True)
        else:
            cmds.warning("Veuillez entrer un nom valide.")
    
    # Cration de la fentre
    window = "renameWindow"
    if cmds.window(window, exists=True):
        cmds.deleteUI(window)
    
    window = cmds.window(window, title="Renommer et grer l'instance", widthHeight=(350, 150))
    cmds.columnLayout(adjustableColumn=True)
    
    cmds.text(label=f"Renommer : {selected_objects[0]}", align="center")
    rename_field = cmds.textField(text=selected_objects[0])
    cmds.button(label="Appliquer", command=apply_changes)
    
    cmds.showWindow(window)

# Excuter la fonction
rename_freeze_instance()