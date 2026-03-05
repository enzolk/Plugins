import bpy


class VIEW3D_OT_set_global_transform(bpy.types.Operator):
    bl_idname = "view3d.set_global_transform"
    bl_label = "Transform Global"
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


classes = (VIEW3D_OT_set_global_transform,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
