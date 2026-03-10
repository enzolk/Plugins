# Copy this file to your Maya scripts directory (or merge its content into your existing userSetup.py)
import maya.utils


def _start_shortcut_logger():
    try:
        import maya_shortcut_logger
        maya_shortcut_logger.auto_start()
    except Exception as exc:
        print("[maya_shortcut_logger] Startup error:", exc)


maya.utils.executeDeferred(_start_shortcut_logger)
