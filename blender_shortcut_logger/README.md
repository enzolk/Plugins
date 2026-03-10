# Blender Shortcut Logger

Addon Blender (3.6+ / 4.x) pour tracer les raccourcis utilisés, lister les actions possibles depuis les keymaps, détecter l'opérateur réellement exécuté, puis stocker les relations de manière persistante.

## Installation
1. Zippez le dossier `blender_shortcut_logger/` (ou copiez-le dans votre dossier d'addons).
2. Dans Blender: **Edit > Preferences > Add-ons > Install...** puis sélectionnez l'archive.
3. Activez **Blender Shortcut Logger**.

## Auto-démarrage
Dès activation de l'addon, l'écoute démarre automatiquement.
L'écoute est aussi relancée après chargement d'un fichier `.blend` via un handler `load_post`.

## Commandes disponibles
- **Open UI**: `bpy.ops.wm.shortcut_logger_open_ui()`
- **Stop listener**: `bpy.ops.wm.shortcut_logger_stop()`
- **Start listener**: `bpy.ops.wm.shortcut_logger_start()`

Le panneau principal est visible dans:
- **View3D > Sidebar (N) > Shortcut Logger**

## Persistance JSON
- Fichier persistant principal:
  - `<Blender config>/blender_shortcut_logger/shortcut_table.json`
- Fichier d'initialisation dans l'addon:
  - `blender_shortcut_logger/data/shortcut_table.json`

Le JSON contient les liens `shortcut -> actions exécutées`, sans doublons.

## Logique de regroupement du tableau
Le tableau regroupe les correspondances via composantes connexes shortcut/action:
- pas de doublon shortcut,
- pas de doublon action,
- plusieurs actions d'un même shortcut sur la même ligne logique,
- une action liée à plusieurs shortcuts regroupée intelligemment.

## Logs console
Format concis:

```text
Shortcut : "Ctrl+Y"
Possible actions :
  - Redo Last (screen.repeat_last)
Executed action :
  - Redo Last (screen.repeat_last)
```

## Limites connues / fallback
- Blender ne fournit pas un hook global "operator executed from key" aussi direct que Maya.
- L'inférence d'action exécutée repose sur un snapshot de `window_manager.operators` juste après la frappe.
- Certains contextes (raccourci consommé par gizmo/outil modal/interactions spécifiques) peuvent ne pas produire de match.
- Dans ces cas, les actions possibles restent listées et le log affiche `No match`.
