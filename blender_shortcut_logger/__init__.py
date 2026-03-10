bl_info = {
    "name": "Blender Shortcut Logger",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Shortcut Logger",
    "description": "Logs used shortcuts and executed Blender operators with persistent table",
    "category": "Interface",
}

import bpy

from .core import manager
from .operators import (
    SHORTCUTLOGGER_OT_listener,
    SHORTCUTLOGGER_OT_open_ui,
    SHORTCUTLOGGER_OT_start_listener,
    SHORTCUTLOGGER_OT_stop_listener,
)
from .ui import SHORTCUTLOGGER_PT_main, SHORTCUTLOGGER_UL_rows, ShortcutLoggerRow


_CLASSES = (
    ShortcutLoggerRow,
    SHORTCUTLOGGER_UL_rows,
    SHORTCUTLOGGER_OT_listener,
    SHORTCUTLOGGER_OT_open_ui,
    SHORTCUTLOGGER_OT_start_listener,
    SHORTCUTLOGGER_OT_stop_listener,
    SHORTCUTLOGGER_PT_main,
)


def _load_post(_dummy):
    try:
        manager().start()
    except Exception:
        pass


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.shortcut_logger_rows = bpy.props.CollectionProperty(type=ShortcutLoggerRow)
    bpy.types.WindowManager.shortcut_logger_row_index = bpy.props.IntProperty(default=0)

    if _load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_load_post)

    _load_post(None)


def unregister():
    manager().stop()

    if _load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post)

    del bpy.types.WindowManager.shortcut_logger_row_index
    del bpy.types.WindowManager.shortcut_logger_rows

    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
