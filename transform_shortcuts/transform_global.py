bl_info = {
    "name": "Transform Shortcut: Global",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Tool > Transform Shortcuts",
    "description": "Set transform orientation to Global and pivot point to Bounding Box Center",
    "category": "3D View",
}

import bpy


class VIEW3D_OT_set_global_transform(bpy.types.Operator):
    bl_idname = "view3d.set_global_transform"
    bl_label = "Set Global Transform"
    bl_description = "Set Transform Orientation to Global and Pivot Point to Bounding Box Center"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.scene.tool_settings is not None

    def execute(self, context):
        scene = context.scene
        scene.transform_orientation_slots[0].type = 'GLOBAL'
        scene.tool_settings.transform_pivot_point = 'BOUNDING_BOX_CENTER'
        return {'FINISHED'}


class VIEW3D_PT_transform_shortcuts_global(bpy.types.Panel):
    bl_label = "Transform Shortcuts"
    bl_idname = "VIEW3D_PT_transform_shortcuts_global"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        layout.operator(VIEW3D_OT_set_global_transform.bl_idname, icon='ORIENTATION_GLOBAL')


classes = (
    VIEW3D_OT_set_global_transform,
    VIEW3D_PT_transform_shortcuts_global,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
