from __future__ import annotations

import bpy

from .core import manager


class SHORTCUTLOGGER_OT_listener(bpy.types.Operator):
    bl_idname = "wm.shortcut_logger_listener"
    bl_label = "Shortcut Logger Listener"
    bl_options = {"INTERNAL"}

    _running = False

    def modal(self, context, event):
        logger = manager()
        if not logger.listening:
            SHORTCUTLOGGER_OT_listener._running = False
            return {"FINISHED"}

        if event.type == "TIMER":
            return {"PASS_THROUGH"}

        logger.process_key_event(context, event)
        return {"PASS_THROUGH"}

    def invoke(self, context, event):
        if SHORTCUTLOGGER_OT_listener._running:
            return {"CANCELLED"}
        SHORTCUTLOGGER_OT_listener._running = True
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}


class SHORTCUTLOGGER_OT_open_ui(bpy.types.Operator):
    bl_idname = "wm.shortcut_logger_open_ui"
    bl_label = "Open Shortcut Logger UI"

    def execute(self, context):
        try:
            bpy.ops.wm.call_panel(name="SHORTCUTLOGGER_PT_main", keep_open=True)
        except Exception:
            self.report({"INFO"}, "Open Sidebar > Shortcut Logger panel")
        return {"FINISHED"}


class SHORTCUTLOGGER_OT_start_listener(bpy.types.Operator):
    bl_idname = "wm.shortcut_logger_start"
    bl_label = "Start Shortcut Logger"

    def execute(self, context):
        manager().start()
        return {"FINISHED"}


class SHORTCUTLOGGER_OT_stop_listener(bpy.types.Operator):
    bl_idname = "wm.shortcut_logger_stop"
    bl_label = "Stop Shortcut Logger"

    def execute(self, context):
        manager().stop()
        return {"FINISHED"}
