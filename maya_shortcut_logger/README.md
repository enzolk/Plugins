# Maya Shortcut Logger

## Installation (Maya)
1. Copy the folder `maya_shortcut_logger` into your Maya scripts directory:
   - Windows: `C:/Users/<you>/Documents/maya/<version>/scripts/`
2. If you already have a `userSetup.py`, merge the content from `maya_shortcut_logger/userSetup.py`.
   Otherwise copy `maya_shortcut_logger/userSetup.py` to your Maya scripts folder root.

## Auto-start
At Maya startup, `userSetup.py` calls:
- `maya_shortcut_logger.auto_start()`

This enables automatic shortcut listening immediately after Maya opens.

## What it does
For each unique shortcut press, it:
1. Detects the shortcut.
2. Resolves possible actions.
3. Observes Maya command output right after the shortcut.
4. Infers the executed action by matching executed commands to possible actions.
5. Stores executed action ↔ shortcut links in a persistent table.

## Open the UI manually
```python
import maya_shortcut_logger
maya_shortcut_logger.open_shortcut_logger_ui()
```

## Disable listening
```python
import maya_shortcut_logger
maya_shortcut_logger.disable_shortcut_listener()
```

## Re-enable listening
```python
import maya_shortcut_logger
maya_shortcut_logger.enable_shortcut_listener()
```

## Persistent table location
Data is saved in Maya prefs:
- `<maya prefs>/maya_shortcut_logger_table.json`

It is auto-loaded on startup and updated whenever a shortcut is matched to an executed action.

## Smart table behavior
The summary table groups links without duplicates:
- no duplicate shortcut,
- no duplicate action,
- shortcuts and actions are grouped by connected relationships.


## Interface behavior
- The summary window stays on top of Maya (always-on-top).
- The table refreshes automatically when a new shortcut→executed-action link is recorded.
- `Refresh` remains available for manual refresh, but is no longer required in normal use.
