bl_info = {
    "name": "Transform Shortcut: Cursor",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Tool > Transform Shortcuts",
    "description": "Set transform orientation and pivot point to 3D Cursor",
    "category": "3D View",
}

import bpy


class VIEW3D_OT_set_cursor_transform(bpy.types.Operator):
    bl_idname = "view3d.set_cursor_transform"
    bl_label = "Set Cursor Transform"
    bl_description = "Set Transform Orientation to Cursor and Pivot Point to 3D Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.scene.tool_settings is not None

    def execute(self, context):
        scene = context.scene
        scene.transform_orientation_slots[0].type = 'CURSOR'
        scene.tool_settings.transform_pivot_point = 'CURSOR'
        return {'FINISHED'}


class VIEW3D_PT_transform_shortcuts_cursor(bpy.types.Panel):
    bl_label = "Transform Shortcuts"
    bl_idname = "VIEW3D_PT_transform_shortcuts_cursor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        layout.operator(VIEW3D_OT_set_cursor_transform.bl_idname, icon='PIVOT_CURSOR')


classes = (
    VIEW3D_OT_set_cursor_transform,
    VIEW3D_PT_transform_shortcuts_cursor,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
