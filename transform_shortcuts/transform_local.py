import bpy


class VIEW3D_OT_set_local_transform(bpy.types.Operator):
    bl_idname = "view3d.set_local_transform"
    bl_label = "Transform Local"
    bl_description = "Set Transform Orientation to Local and Pivot Point to Individual Origins"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and context.scene.tool_settings is not None

    def execute(self, context):
        scene = context.scene
        scene.transform_orientation_slots[0].type = 'LOCAL'
        scene.tool_settings.transform_pivot_point = 'INDIVIDUAL_ORIGINS'
        return {'FINISHED'}


classes = (VIEW3D_OT_set_local_transform,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
