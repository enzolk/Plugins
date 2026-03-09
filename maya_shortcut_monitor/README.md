# Maya Shortcut Monitor

## Structure

```text
maya_shortcut_monitor/
├── __init__.py
├── shortcut_tracker.py      # Script principal
├── shortcuts_used.json      # Sauvegarde persistante
└── README.md
```

## Installation rapide

1. Copiez le dossier `maya_shortcut_monitor` dans un dossier présent dans votre `PYTHONPATH` Maya (ex: dossier scripts utilisateur).
2. Dans Maya (Script Editor > Python), lancez:

```python
import maya_shortcut_monitor.shortcut_tracker as st
st.start_tracker()
```

3. Utilisez Maya normalement. Le fichier `shortcuts_used.json` sera mis à jour automatiquement.
4. Pour arrêter l'écoute:

```python
st.stop_tracker()
```

## Données enregistrées

Chaque entrée contient:
- `shortcut`
- `command`
- `category`
- `hits`
- `last_seen`

Le tri dans le JSON est fait par catégorie:
- Sélection
- Transformation
- Modélisation
- UV
- Affichage
- Animation
- Autres
