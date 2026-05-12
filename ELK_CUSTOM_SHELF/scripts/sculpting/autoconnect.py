# ELK_META {"label": "AutoConnect", "short_name": "", "tooltip": "import maya.cmds as cmds\n\nclass AutoConnectTool:\n    def __init__(self):\n        self.window_name = \"AutoConnectWindow\"\n        self.is_active = False  # Tracks if the toggle is ON\n        self.script_job = None  # Stores script job ID\n\n    def create_ui(self):\n        # Close existing window if already open\n        if cmds.window(self.window_name, exists=True):\n            cmds.deleteUI(self.window_name)\n\n        # Create new window\n        self.window = cmds.window(self.window_name, title=\"Aut", "source": "python", "icon_svg": "brush.svg", "icon_color": "#b277ff"}
import maya.cmds as cmds

class AutoConnectTool:
    def __init__(self):
        self.window_name = "AutoConnectWindow"
        self.is_active = False  # Indique si le mode Auto Connect est activ
        self.script_job = None  # Stocke l'ID du scriptJob
        self.edge_flow_enabled = False  # tat initial de l'option Edge Flow

    def create_ui(self):
        # Fermer la fentre existante si elle est dj ouverte
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)

        # Crer une nouvelle fentre
        self.window = cmds.window(self.window_name, title="Outil Auto Connect", widthHeight=(200, 120))
        cmds.columnLayout(adjustableColumn=True)

        # Bouton de bascule pour Auto Connect
        self.toggle_btn = cmds.button(label="Auto Connect (OFF)", command=self.toggle_auto_connect, bgc=[0.4, 0.4, 0.4])

        # Case  cocher pour activer/dsactiver l'Edge Flow
        self.edge_flow_checkbox = cmds.checkBox(label="Activer Edge Flow", value=self.edge_flow_enabled, changeCommand=self.toggle_edge_flow)

        cmds.showWindow(self.window)

    def toggle_auto_connect(self, *args):
        """Active ou dsactive le mode Auto Connect."""
        self.is_active = not self.is_active

        if self.is_active:
            cmds.button(self.toggle_btn, edit=True, label="Auto Connect (ON)", bgc=[0.2, 0.8, 0.2])
            cmds.warning("Auto Connect est activ. Slectionnez deux sommets ou deux artes.")
            self.start_script_job()
        else:
            cmds.button(self.toggle_btn, edit=True, label="Auto Connect (OFF)", bgc=[0.4, 0.4, 0.4])
            cmds.warning("Auto Connect est dsactiv.")
            self.kill_script_job()

    def toggle_edge_flow(self, state):
        """Active ou dsactive l'option Edge Flow."""
        self.edge_flow_enabled = state
        if self.edge_flow_enabled:
            cmds.warning("Edge Flow activ.")
        else:
            cmds.warning("Edge Flow dsactiv.")

    def start_script_job(self):
        """Dmarre un scriptJob pour surveiller les changements de slection."""
        if self.script_job:
            cmds.scriptJob(kill=self.script_job, force=True)  # Supprime le scriptJob prcdent s'il existe
        self.script_job = cmds.scriptJob(event=["SelectionChanged", self.on_selection_change], protected=True)

    def on_selection_change(self):
        """Vrifie si l'utilisateur a slectionn exactement deux sommets ou deux artes et excute la commande approprie."""
        if not self.is_active:
            return  # Ignorer si le mode Auto Connect est dsactiv

        selected = cmds.ls(selection=True, fl=True)  # Obtenir la slection
        valid_vertices = []
        valid_edges = []

        # Filtrer la slection pour s'assurer qu'il s'agit de sommets ou d'artes
        for sel in selected:
            if ".vtx[" in sel:  # C'est un sommet
                parent_mesh = cmds.listRelatives(sel, parent=True, fullPath=True)  # Obtenir le maillage parent
                if parent_mesh and cmds.nodeType(parent_mesh[0]) == "mesh":
                    valid_vertices.append(sel)
            elif ".e[" in sel:  # C'est une arte
                parent_mesh = cmds.listRelatives(sel, parent=True, fullPath=True)  # Obtenir le maillage parent
                if parent_mesh and cmds.nodeType(parent_mesh[0]) == "mesh":
                    valid_edges.append(sel)

        if len(valid_vertices) == 2 or len(valid_edges) == 2:
            # Excuter la commande pour connecter les composants slectionns
            cmds.polyConnectComponents(ch=1, insertWithEdgeFlow=self.edge_flow_enabled, adjustEdgeFlow=1)
            cmds.warning("Composants connects. Slectionnez les deux prochains sommets ou artes.")
            # Rinitialiser la slection pour permettre  l'utilisateur de choisir de nouveaux composants
            cmds.select(clear=True)

    def kill_script_job(self):
        """Arrte le scriptJob actif en toute scurit."""
        if self.script_job:
            cmds.scriptJob(kill=self.script_job, force=True)
            self.script_job = None

# Excuter le script
tool = AutoConnectTool()
tool.create_ui()