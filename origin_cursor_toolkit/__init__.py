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
import bmesh
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
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)

        active = bm.select_history.active
        if active and getattr(active, "select", False):
            if isinstance(active, bmesh.types.BMVert):
                return obj.matrix_world @ active.co.copy()
            if isinstance(active, bmesh.types.BMEdge):
                center = (active.verts[0].co + active.verts[1].co) * 0.5
                return obj.matrix_world @ center
            if isinstance(active, bmesh.types.BMFace):
                return obj.matrix_world @ active.calc_center_median()

        selected_verts = [v for v in bm.verts if v.select]
        if selected_verts:
            local_pos = sum((v.co for v in selected_verts), Vector((0.0, 0.0, 0.0))) / len(selected_verts)
            return obj.matrix_world @ local_pos

        selected_edges = [e for e in bm.edges if e.select]
        if selected_edges:
            edge_centers = [(e.verts[0].co + e.verts[1].co) * 0.5 for e in selected_edges]
            local_pos = sum(edge_centers, Vector((0.0, 0.0, 0.0))) / len(edge_centers)
            return obj.matrix_world @ local_pos

        selected_faces = [f for f in bm.faces if f.select]
        if selected_faces:
            face_centers = [f.calc_center_median() for f in selected_faces]
            local_pos = sum(face_centers, Vector((0.0, 0.0, 0.0))) / len(face_centers)
            return obj.matrix_world @ local_pos

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

    previous_mode = obj.mode
    switched_mode = False

    if previous_mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            switched_mode = True
        except RuntimeError as ex:
            return False, str(ex)

    try:
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
    finally:
        if switched_mode:
            try:
                bpy.ops.object.mode_set(mode=previous_mode)
            except RuntimeError:
                pass

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


def _selected_or_active_objects(context):
    selected = list(context.selected_objects)
    if selected:
        return selected
    if context.active_object:
        return [context.active_object]
    return []


def _apply_to_each_selected_object(context, operation):
    selected_objects = _selected_or_active_objects(context)
    if not selected_objects:
        return False, "No active object"

    view_layer = context.view_layer
    previous_active = view_layer.objects.active
    previous_selection = [obj for obj in context.selectable_objects if obj.select_get()]

    previous_mode = previous_active.mode if previous_active else 'OBJECT'
    switched_mode = False
    if previous_active and previous_mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
            switched_mode = True
        except RuntimeError as ex:
            return False, str(ex)

    try:
        for obj in selected_objects:
            if obj.name not in bpy.data.objects:
                continue

            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            view_layer.objects.active = obj

            ok, msg = operation(obj)
            if not ok:
                return False, msg
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in previous_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)

        if previous_active and previous_active.name in bpy.data.objects:
            view_layer.objects.active = previous_active

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
        ok, msg = _apply_to_each_selected_object(
            context,
            lambda _obj: _set_origin_to_cursor_allow_edit_mode(context),
        )
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_OriginOrientationToCursor(bpy.types.Operator):
    bl_idname = "oct.origin_orientation_to_cursor"
    bl_label = "Origin Orientation to Cursor Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rot = context.scene.cursor.matrix.to_3x3()
        ok, msg = _apply_to_each_selected_object(
            context,
            lambda obj: _set_object_origin_orientation_keep_appearance(obj, rot),
        )
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

        cursor = context.scene.cursor
        previous_cursor_location = cursor.location.copy()

        def _move_origin_to_component(_obj):
            cursor.location = pos
            return _set_origin_to_cursor_allow_edit_mode(context)

        try:
            ok, msg = _apply_to_each_selected_object(context, _move_origin_to_component)
        finally:
            cursor.location = previous_cursor_location

        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_OriginOrientationToComponent(bpy.types.Operator):
    bl_idname = "oct.origin_orientation_to_component"
    bl_label = "Origin Orientation to Component Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rot = _selected_component_world_orientation(context)
        if rot is None:
            self.report({'WARNING'}, "No component orientation available")
            return {'CANCELLED'}

        ok, msg = _apply_to_each_selected_object(
            context,
            lambda obj: _set_object_origin_orientation_keep_appearance(obj, rot),
        )
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
        selected = _selected_or_active_objects(context)
        if not selected:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}
        context.scene.cursor.rotation_euler = selected[-1].matrix_world.to_3x3().to_euler()
        return {'FINISHED'}


class OCT_OT_ResetCursorPositionObject(bpy.types.Operator):
    bl_idname = "oct.reset_cursor_position_object"
    bl_label = "Reset Cursor Position to Object Origin Position"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected = _selected_or_active_objects(context)
        if not selected:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}
        context.scene.cursor.location = selected[-1].matrix_world.to_translation()
        return {'FINISHED'}


class OCT_OT_ResetCursorPositionSelectedBBox(bpy.types.Operator):
    bl_idname = "oct.reset_cursor_position_selected_bbox"
    bl_label = "Reset Cursor Position to Object Bounding Box"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected = _selected_or_active_objects(context)
        if not selected:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        ref_obj = selected[-1]
        bbox_world = [ref_obj.matrix_world @ Vector(corner) for corner in ref_obj.bound_box]
        context.scene.cursor.location = sum(bbox_world, Vector((0.0, 0.0, 0.0))) / len(bbox_world)
        return {'FINISHED'}


class OCT_OT_ResetOriginOrientationWorld(bpy.types.Operator):
    bl_idname = "oct.reset_origin_orientation_world"
    bl_label = "Reset Origin Orientation to World Orientation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ok, msg = _apply_to_each_selected_object(
            context,
            lambda obj: _set_object_origin_orientation_keep_appearance(obj, Matrix.Identity(3)),
        )
        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_ResetOriginPositionSelectedBBox(bpy.types.Operator):
    bl_idname = "oct.reset_origin_position_selected_bbox"
    bl_label = "Reset Origin Position to Object Bounding Box"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        cursor = context.scene.cursor
        previous_cursor_location = cursor.location.copy()

        def _move_origin_to_bbox(obj):
            bbox_world = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            target_pos = sum(bbox_world, Vector((0.0, 0.0, 0.0))) / len(bbox_world)
            cursor.location = target_pos
            return _set_origin_to_cursor_allow_edit_mode(context)

        ok, msg = _apply_to_each_selected_object(context, _move_origin_to_bbox)
        cursor.location = previous_cursor_location

        if not ok:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        return {'FINISHED'}


class OCT_OT_ResetOriginEachToOwnBBox(bpy.types.Operator):
    bl_idname = "oct.reset_origin_each_to_own_bbox"
    bl_label = "Reset Origin to Each Object Bounding Box"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = list(context.selected_objects)
        if not selected_objects:
            self.report({'WARNING'}, "No selected objects")
            return {'CANCELLED'}

        cursor = context.scene.cursor
        previous_cursor_location = cursor.location.copy()

        view_layer = context.view_layer
        previous_active = view_layer.objects.active
        previous_selection = [obj for obj in context.selectable_objects if obj.select_get()]

        previous_mode = previous_active.mode if previous_active else 'OBJECT'
        switched_mode = False
        if previous_active and previous_mode != 'OBJECT':
            try:
                bpy.ops.object.mode_set(mode='OBJECT')
                switched_mode = True
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}

        try:
            for obj in selected_objects:
                bbox_world = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
                target_pos = sum(bbox_world, Vector((0.0, 0.0, 0.0))) / len(bbox_world)

                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                view_layer.objects.active = obj

                cursor.location = target_pos
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        finally:
            cursor.location = previous_cursor_location

            bpy.ops.object.select_all(action='DESELECT')
            for obj in previous_selection:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)

            if previous_active and previous_active.name in bpy.data.objects:
                view_layer.objects.active = previous_active

            if switched_mode:
                try:
                    bpy.ops.object.mode_set(mode=previous_mode)
                except RuntimeError:
                    pass

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
        target = _selected_component_world_position(context)
        if target is None:
            self.report({'WARNING'}, "No component selection found")
            return {'CANCELLED'}

        def _aim_origin_z(obj):
            origin = obj.matrix_world.to_translation()
            z_axis = target - origin
            if z_axis.length <= 1e-12:
                return False, "Object origin is already at target"

            x_hint = obj.matrix_world.to_3x3().col[0].xyz
            rot = _basis_from_z_and_hint(z_axis, x_hint)
            return _set_object_origin_orientation_keep_appearance(obj, rot)

        ok, msg = _apply_to_each_selected_object(context, _aim_origin_z)
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
        col.operator("oct.reset_cursor_position_selected_bbox", icon='SHADING_BBOX')
        col.operator("oct.reset_cursor_orientation_object", icon='OBJECT_ORIGIN')
        col.operator("oct.reset_origin_orientation_world", icon='WORLD')
        col.operator("oct.reset_origin_position_selected_bbox", icon='SHADING_BBOX')
        col.operator("oct.reset_origin_each_to_own_bbox", icon='SHADING_BBOX')
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
    OCT_OT_ResetCursorPositionSelectedBBox,
    OCT_OT_ResetOriginOrientationWorld,
    OCT_OT_ResetOriginPositionSelectedBBox,
    OCT_OT_ResetOriginEachToOwnBBox,
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
