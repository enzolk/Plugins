bl_info = {
    "name": "Origin & Cursor Toolkit",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Edit",
    "description": "Tools to align origin and 3D cursor to cursor/object/component transforms.",
    "category": "3D View",
}

import bpy
from mathutils import Matrix, Vector


COMPONENT_ORIENTATION_NAME = "__OCT_COMPONENT_ORIENTATION__"


def _safe_normalize(v: Vector, fallback: Vector) -> Vector:
    if v.length > 1e-12:
        return v.normalized()
    return fallback.normalized()


def _basis_from_z_and_hint(z_axis: Vector, x_hint: Vector) -> Matrix:
    z = _safe_normalize(z_axis, Vector((0, 0, 1)))
    x = x_hint - z * x_hint.dot(z)
    if x.length <= 1e-12:
        x = Vector((1, 0, 0)) if abs(z.dot(Vector((1, 0, 0)))) < 0.99 else Vector((0, 1, 0))
    x = _safe_normalize(x, Vector((1, 0, 0)))
    y = _safe_normalize(z.cross(x), Vector((0, 1, 0)))
    x = _safe_normalize(y.cross(z), Vector((1, 0, 0)))
    return Matrix((x, y, z)).transposed()


def _selected_component_world_position(context):
    cursor = context.scene.cursor
    old_loc = cursor.location.copy()
    try:
        bpy.ops.view3d.snap_cursor_to_selected()
    except RuntimeError:
        return None
    pos = cursor.location.copy()
    cursor.location = old_loc
    return pos


def _selected_component_world_orientation(context):
    slot = context.scene.transform_orientation_slots[0]
    old_type = slot.type

    try:
        bpy.ops.transform.create_orientation(
            name=COMPONENT_ORIENTATION_NAME,
            use=True,
            overwrite=True,
        )
    except RuntimeError:
        slot.type = old_type
        return None

    custom = slot.custom_orientation
    if not custom:
        slot.type = old_type
        return None

    matrix = custom.matrix.copy()

    # Cleanup through operators (BlendData has no `orientations` collection in Blender 5).
    try:
        slot.type = custom.name
        bpy.ops.transform.delete_orientation()
    except RuntimeError:
        pass

    try:
        slot.type = old_type
    except TypeError:
        slot.type = 'GLOBAL'

    return matrix


def _set_object_origin_orientation_keep_appearance(obj, new_rotation_3x3: Matrix):
    if not obj.data or not hasattr(obj.data, "transform"):
        return False, "Active object type does not support data transform"

    m_old = obj.matrix_world.copy()
    loc = m_old.to_translation()
    scale = m_old.to_scale()

    m_new_3x3 = new_rotation_3x3.normalized() @ Matrix.Diagonal(scale).to_3x3()
    m_new = Matrix.Translation(loc) @ m_new_3x3.to_4x4()

    delta_local = m_new.inverted() @ m_old
    obj.data.transform(delta_local)
    if hasattr(obj.data, "update"):
        obj.data.update()

    obj.matrix_world = m_new
    return True, ""


def _set_origin_to_cursor_allow_edit_mode(context):
    obj = context.active_object
    if not obj:
        return False, "No active object"

    previous_mode = obj.mode
    switched_mode = False

    if previous_mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            switched_mode = True
        except RuntimeError as ex:
            return False, str(ex)

    try:
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
    except RuntimeError as ex:
        return False, str(ex)
    finally:
        if switched_mode:
            try:
                bpy.ops.object.mode_set(mode=previous_mode)
            except RuntimeError:
                pass

    return True, ""


class OCT_OT_OriginPositionToCursor(bpy.types.Operator):
    bl_idname = "oct.origin_position_to_cursor"
    bl_label = "Origin Position to Cursor Position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, msg = _set_origin_to_cursor_allow_edit_mode(context)
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_OriginOrientationToCursor(bpy.types.Operator):
    bl_idname = "oct.origin_orientation_to_cursor"
    bl_label = "Origin Orientation to Cursor Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        rot = context.scene.cursor.matrix.to_3x3()
        ok, msg = _set_object_origin_orientation_keep_appearance(obj, rot)
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_OriginPositionToComponent(bpy.types.Operator):
    bl_idname = "oct.origin_position_to_component"
    bl_label = "Origin Position to Component Position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pos = _selected_component_world_position(context)
        if pos is None:
            self.report({'WARNING'}, "No component selection found")
            return {'CANCELLED'}

        context.scene.cursor.location = pos
        ok, msg = _set_origin_to_cursor_allow_edit_mode(context)
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_OriginOrientationToComponent(bpy.types.Operator):
    bl_idname = "oct.origin_orientation_to_component"
    bl_label = "Origin Orientation to Component Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        rot = _selected_component_world_orientation(context)
        if rot is None:
            self.report({'WARNING'}, "No component orientation available")
            return {'CANCELLED'}

        ok, msg = _set_object_origin_orientation_keep_appearance(obj, rot)
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_CursorOrientationToComponent(bpy.types.Operator):
    bl_idname = "oct.cursor_orientation_to_component"
    bl_label = "Cursor Orientation to Component Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rot = _selected_component_world_orientation(context)
        if rot is None:
            self.report({'WARNING'}, "No component orientation available")
            return {'CANCELLED'}
        context.scene.cursor.rotation_euler = rot.to_euler()
        return {'FINISHED'}


class OCT_OT_CursorPositionToComponent(bpy.types.Operator):
    bl_idname = "oct.cursor_position_to_component"
    bl_label = "Cursor Position to Component Position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pos = _selected_component_world_position(context)
        if pos is None:
            self.report({'WARNING'}, "No component selection found")
            return {'CANCELLED'}
        context.scene.cursor.location = pos
        return {'FINISHED'}


class OCT_OT_ResetCursorOrientationWorld(bpy.types.Operator):
    bl_idname = "oct.reset_cursor_orientation_world"
    bl_label = "Reset Cursor Orientation to World"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.cursor.rotation_euler = (0.0, 0.0, 0.0)
        return {'FINISHED'}


class OCT_OT_ResetCursorPositionWorld(bpy.types.Operator):
    bl_idname = "oct.reset_cursor_position_world"
    bl_label = "Reset Cursor Position to World"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.cursor.location = (0.0, 0.0, 0.0)
        return {'FINISHED'}


class OCT_OT_ResetCursorOrientationObject(bpy.types.Operator):
    bl_idname = "oct.reset_cursor_orientation_object"
    bl_label = "Reset Cursor Orientation to Object Local Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}
        context.scene.cursor.rotation_euler = obj.matrix_world.to_3x3().to_euler()
        return {'FINISHED'}


class OCT_OT_ResetCursorPositionObject(bpy.types.Operator):
    bl_idname = "oct.reset_cursor_position_object"
    bl_label = "Reset Cursor Position to Object Origin Position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}
        context.scene.cursor.location = obj.matrix_world.to_translation()
        return {'FINISHED'}


class OCT_OT_AimCursorZ(bpy.types.Operator):
    bl_idname = "oct.aim_cursor_z"
    bl_label = "Aim Cursor (Z)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = _selected_component_world_position(context)
        if target is None:
            self.report({'WARNING'}, "No component selection found")
            return {'CANCELLED'}

        cursor = context.scene.cursor
        origin = cursor.location.copy()
        z_axis = target - origin
        if z_axis.length <= 1e-12:
            self.report({'WARNING'}, "Cursor is already at target")
            return {'CANCELLED'}

        x_hint = cursor.matrix.to_3x3().col[0].xyz
        rot = _basis_from_z_and_hint(z_axis, x_hint)
        cursor.rotation_euler = rot.to_euler()
        return {'FINISHED'}


class OCT_OT_AimOriginZ(bpy.types.Operator):
    bl_idname = "oct.aim_origin_z"
    bl_label = "Aim Origin (Z)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        target = _selected_component_world_position(context)
        if target is None:
            self.report({'WARNING'}, "No component selection found")
            return {'CANCELLED'}

        origin = obj.matrix_world.to_translation()
        z_axis = target - origin
        if z_axis.length <= 1e-12:
            self.report({'WARNING'}, "Object origin is already at target")
            return {'CANCELLED'}

        x_hint = obj.matrix_world.to_3x3().col[0].xyz
        rot = _basis_from_z_and_hint(z_axis, x_hint)
        ok, msg = _set_object_origin_orientation_keep_appearance(obj, rot)
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class VIEW3D_PT_OriginCursorToolkit(bpy.types.Panel):
    bl_label = "Origin Cursor Toolkit"
    bl_idname = "VIEW3D_PT_origin_cursor_toolkit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("oct.origin_position_to_cursor", icon='PIVOT_CURSOR')
        col.operator("oct.origin_orientation_to_cursor", icon='ORIENTATION_CURSOR')
        col.separator()
        col.operator("oct.origin_position_to_component", icon='PIVOT_CURSOR')
        col.operator("oct.origin_orientation_to_component", icon='ORIENTATION_CURSOR')
        col.separator()
        col.operator("oct.cursor_position_to_component", icon='CURSOR')
        col.operator("oct.cursor_orientation_to_component", icon='ORIENTATION_CURSOR')
        col.separator()
        col.operator("oct.reset_cursor_position_world", icon='WORLD')
        col.operator("oct.reset_cursor_orientation_world", icon='WORLD')
        col.operator("oct.reset_cursor_position_object", icon='OBJECT_ORIGIN')
        col.operator("oct.reset_cursor_orientation_object", icon='OBJECT_ORIGIN')
        col.separator()
        col.operator("oct.aim_cursor_z", icon='TRACKING')
        col.operator("oct.aim_origin_z", icon='TRACKING_FORWARDS')


classes = (
    OCT_OT_OriginPositionToCursor,
    OCT_OT_OriginOrientationToCursor,
    OCT_OT_OriginPositionToComponent,
    OCT_OT_OriginOrientationToComponent,
    OCT_OT_CursorOrientationToComponent,
    OCT_OT_CursorPositionToComponent,
    OCT_OT_ResetCursorOrientationWorld,
    OCT_OT_ResetCursorPositionWorld,
    OCT_OT_ResetCursorOrientationObject,
    OCT_OT_ResetCursorPositionObject,
    OCT_OT_AimCursorZ,
    OCT_OT_AimOriginZ,
    VIEW3D_PT_OriginCursorToolkit,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
