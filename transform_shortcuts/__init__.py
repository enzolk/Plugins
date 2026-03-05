bl_info = {
    "name": "Transform Shortcuts",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Edit > Transform shortcut",
    "description": "Quick buttons for cursor/global transform orientation and pivot",
    "category": "3D View",
}

import bpy

from . import transform_cursor, transform_global


class VIEW3D_PT_transform_shortcuts(bpy.types.Panel):
    bl_label = "Transform shortcut"
    bl_idname = "VIEW3D_PT_transform_shortcuts"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator(
            transform_cursor.VIEW3D_OT_set_cursor_transform.bl_idname,
            text="Transform Cursor",
            icon='PIVOT_CURSOR',
        )
        col.operator(
            transform_global.VIEW3D_OT_set_global_transform.bl_idname,
            text="Transform Global",
            icon='ORIENTATION_GLOBAL',
        )


classes = (VIEW3D_PT_transform_shortcuts,)


def register():
    transform_cursor.register()
    transform_global.register()
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    transform_global.unregister()
    transform_cursor.unregister()
