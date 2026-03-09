# Maya Shortcut Monitor

## Structure

```text
maya_shortcut_monitor/
├── .gitignore
├── __init__.py
├── shortcut_tracker.py      # Script principal
├── shortcuts_used.json      # Sauvegarde persistante
└── README.md
```

## Initialiser le script dans Maya

> Compatibilité Qt : le script supporte automatiquement `shiboken2/PySide2` (Maya 2022-2024)
> et `shiboken6/PySide6` (Maya 2025+).

### Option 1 (rapide, manuel via Script Editor)

1. Copiez le dossier `maya_shortcut_monitor` dans votre dossier de scripts Maya.
   - Windows (par défaut): `C:/Users/<vous>/Documents/maya/scripts/`
   - Linux (par défaut): `~/maya/scripts/`
   - macOS (par défaut): `~/Library/Preferences/Autodesk/maya/scripts/`

2. Ouvrez **Maya > Script Editor > onglet Python** puis lancez:

```python
import maya_shortcut_monitor.shortcut_tracker as st
st.start_tracker()
```

3. Pour arrêter le tracker:

```python
st.stop_tracker()
```

---

### Option 2 (auto au démarrage Maya via `userSetup.py`)

Ajoutez ce bloc dans votre `userSetup.py` (dans le même dossier scripts Maya):

```python
import maya.utils

def _start_shortcut_monitor():
    import maya_shortcut_monitor.shortcut_tracker as st
    st.start_tracker()

maya.utils.executeDeferred(_start_shortcut_monitor)
```

> `executeDeferred` évite de démarrer trop tôt avant l’initialisation complète de l’UI Maya.

---

### Option 3 (bouton Shelf)

1. Ouvrez le Script Editor, exécutez:

```python
import maya_shortcut_monitor.shortcut_tracker as st
st.start_tracker()
```

2. Sélectionnez les lignes puis **File > Save Script to Shelf**.
3. Créez un second bouton avec:

```python
import maya_shortcut_monitor.shortcut_tracker as st
st.stop_tracker()
```

## Vérifier que ça fonctionne

- Après `st.start_tracker()`, la console affiche: `[ShortcutTracker] Tracking started.`
- Une fenêtre **Maya Shortcut Monitor** s'ouvre automatiquement dans Maya.
- Utilisez quelques raccourcis: le tableau de la fenêtre se met à jour.
- Le tracking privilégie l'action réellement exécutée (commande `repeatLast`) pour mieux gérer les raccourcis contextuels.
- Le tracker croise maintenant plusieurs signaux d'exécution (`repeatLast`, `undoInfo`, outil actif, mapping hotkey + `ctxClient`) pour mieux distinguer les raccourcis ambigus selon le contexte.
- Si disponible, il écoute aussi la sortie des commandes Maya (`MCommandMessage`) pour capturer la commande réellement exécutée (ex: `FrameSelectedWithoutChildren`) avant les fallbacks.
- Les sorties parasites (ex: `# Result:`, valeurs numériques seules, refresh HUD/UI comme `dR_*`) sont filtrées pour éviter des faux positifs comme `"1"`.
- Les commandes techniques de changement d’outil (ex: `setToolTo nexMultiCutCtx1`) sont normalisées en libellés lisibles (ex: `Tool: Multi-Cut`).
- Les commandes MEL/Python brutes sont aussi remappées vers des labels lisibles quand possible (ex: `fitPanel -selectedNoChildren` → `Frame Selected without children`).
- Le fallback vers `Tool: ...` est désormais limité aux vrais raccourcis de changement d’outil (Q/W/E/R/T/Y) pour éviter des faux positifs sur des touches comme `Ctrl+Z`, `D`, `N`.
- Ouvrez `maya_shortcut_monitor/shortcuts_used.json` : vous devez voir des entrées avec:
  - `shortcut`
  - `command`
  - `category`
  - `context`
  - `hits`
  - `last_seen`

## Données enregistrées

Le tri dans le JSON est fait par catégorie:
- Sélection
- Transformation
- Modélisation
- UV
- Affichage
- Animation
- Autres
