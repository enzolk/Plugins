# ELK_META {"label": "Uniform Spacing Tool", "short_name": "SpaceR", "tooltip": "Espace uniformément plusieurs objets sélectionnés selon une distance définie.", "source": "python", "icon_svg": "spacing-horizontal.svg", "icon_color": "#ff5c8a"}
import maya.cmds as cmds

def espacer_objets():
    # Vrifier le nombre d'objets slectionns
    objets_selectionnes = cmds.ls(selection=True)
    nombre_objets = len(objets_selectionnes)

    if nombre_objets < 2:
        cmds.warning("Veuillez slectionner au moins deux objets.")
        return

    # Fonction pour appliquer l'espacement
    def appliquer_espacement(*args):
        try:
            espacement = float(cmds.textField(espacement_champ, query=True, text=True))
        except ValueError:
            cmds.warning("Veuillez entrer une valeur numrique valide pour l'espacement.")
            return

        axe = cmds.radioButtonGrp(axe_boutons, query=True, select=True)
        axes = {1: 'x', 2: 'y', 3: 'z'}
        axe_selectionne = axes.get(axe, 'x')

        espace = cmds.radioButtonGrp(espace_boutons, query=True, select=True)
        espaces = {1: 'world', 2: 'object'}
        espace_selectionne = espaces.get(espace, 'world')

        # Index de l'axe : 0 pour x, 1 pour y, 2 pour z
        index_axe = {'x': 0, 'y': 1, 'z': 2}[axe_selectionne]

        # Obtenir la position du premier objet
        if espace_selectionne == 'world':
            position_depart = cmds.xform(objets_selectionnes[0], query=True, worldSpace=True, translation=True)
        else:
            position_depart = cmds.xform(objets_selectionnes[0], query=True, objectSpace=True, translation=True)

        # Espacer les objets
        for i in range(1, nombre_objets):
            nouvelle_position = position_depart[:]
            nouvelle_position[index_axe] += i * espacement
            if espace_selectionne == 'world':
                cmds.xform(objets_selectionnes[i], worldSpace=True, translation=nouvelle_position)
            else:
                cmds.xform(objets_selectionnes[i], objectSpace=True, translation=nouvelle_position)

    # Crer la fentre
    if cmds.window("espacementFenetre", exists=True):
        cmds.deleteUI("espacementFenetre", window=True)

    cmds.window("espacementFenetre", title="Espacement des Objets", widthHeight=(300, 200))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAlign="center")

    # Champ de texte pour la distance d'espacement
    cmds.text(label="Distance d'espacement :")
    espacement_champ = cmds.textField()

    # Boutons radio pour slectionner l'axe
    cmds.text(label="Slectionnez l'axe :")
    axe_boutons = cmds.radioButtonGrp(labelArray3=['X', 'Y', 'Z'], numberOfRadioButtons=3, select=1)

    # Boutons radio pour slectionner l'espace
    cmds.text(label="Slectionnez l'espace :")
    espace_boutons = cmds.radioButtonGrp(labelArray2=['Monde', 'Objet'], numberOfRadioButtons=2, select=1)

    # Bouton pour appliquer l'espacement
    cmds.button(label="Appliquer l'espacement", command=appliquer_espacement)

    cmds.showWindow("espacementFenetre")

espacer_objets()