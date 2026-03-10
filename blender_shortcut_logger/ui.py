from __future__ import annotations

import bpy

from .core import manager


class SHORTCUTLOGGER_UL_rows(bpy.types.UIList):
    bl_idname = "SHORTCUTLOGGER_UL_rows"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.shortcuts)
        row.label(text=item.actions)


class ShortcutLoggerRow(bpy.types.PropertyGroup):
    shortcuts: bpy.props.StringProperty(name="Shortcuts")
    actions: bpy.props.StringProperty(name="Actions")


class SHORTCUTLOGGER_PT_main(bpy.types.Panel):
    bl_label = "Shortcut Logger"
    bl_idname = "SHORTCUTLOGGER_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Shortcut Logger"

    def draw(self, context):
        layout = self.layout
        logger = manager()
        wm = context.window_manager

        row = layout.row(align=True)
        if logger.listening:
            row.operator("wm.shortcut_logger_stop", icon="PAUSE")
        else:
            row.operator("wm.shortcut_logger_start", icon="PLAY")
        row.operator("wm.shortcut_logger_open_ui", icon="WINDOW")

        _sync_rows(wm)
        layout.template_list("SHORTCUTLOGGER_UL_rows", "", wm, "shortcut_logger_rows", wm, "shortcut_logger_row_index")


def _sync_rows(wm: bpy.types.WindowManager) -> None:
    rows = manager().store.grouped_rows()
    wm.shortcut_logger_rows.clear()
    for shortcuts, actions in rows:
        item = wm.shortcut_logger_rows.add()
        item.shortcuts = ", ".join(shortcuts)
        item.actions = ", ".join(actions)
