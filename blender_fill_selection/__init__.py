bl_info = {
    "name": "Fill Selection Primitives",
    "author": "Codex",
    "version": (2, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Edit",
    "description": "Crée des primitives Fill Selection dédiées à partir de la sélection active.",
    "category": "3D View",
}

import bpy
import bmesh
from mathutils import Vector


LOG_PREFIX = "[FillSelection]"


class SelectionBounds:
    def __init__(self, minimum: Vector, maximum: Vector):
        self.minimum = minimum
        self.maximum = maximum

    @property
    def center(self):
        return (self.minimum + self.maximum) * 0.5

    @property
    def size(self):
        return self.maximum - self.minimum


def log(message):
    print(f"{LOG_PREFIX} {message}")


def vector_min(a: Vector, b: Vector):
    return Vector((min(a.x, b.x), min(a.y, b.y), min(a.z, b.z)))


def vector_max(a: Vector, b: Vector):
    return Vector((max(a.x, b.x), max(a.y, b.y), max(a.z, b.z)))


def build_bounds(points):
    if not points:
        return None

    minimum = points[0].copy()
    maximum = points[0].copy()

    for point in points[1:]:
        minimum = vector_min(minimum, point)
        maximum = vector_max(maximum, point)

    return SelectionBounds(minimum, maximum)


def selected_points_for_object_mode(context):
    points = []
    for obj in context.selected_objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    return points


def selected_edit_mesh_vertices(bm):
    vertices = {vert for vert in bm.verts if vert.select}

    if vertices:
        return list(vertices)

    for edge in bm.edges:
        if edge.select:
            vertices.update(edge.verts)

    if vertices:
        return list(vertices)

    for face in bm.faces:
        if face.select:
            vertices.update(face.verts)

    return list(vertices)


def selected_points_for_edit_mesh(context):
    obj = context.active_object
    if not obj or obj.type != 'MESH' or context.mode != 'EDIT_MESH':
        return []

    bm = bmesh.from_edit_mesh(obj.data)
    selected_verts = selected_edit_mesh_vertices(bm)
    return [obj.matrix_world @ vert.co for vert in selected_verts]


def compute_selection_bounds(context):
    points = []

    if context.mode == 'EDIT_MESH':
        points.extend(selected_points_for_edit_mesh(context))
    else:
        points.extend(selected_points_for_object_mode(context))

    bounds = build_bounds(points)
    if bounds:
        log(
            "Bounds computed "
            f"min={tuple(round(v, 5) for v in bounds.minimum)}, "
            f"max={tuple(round(v, 5) for v in bounds.maximum)}, "
            f"center={tuple(round(v, 5) for v in bounds.center)}, "
            f"size={tuple(round(v, 5) for v in bounds.size)}"
        )
    else:
        log("No bounds computed (empty selection).")

    return bounds


def largest_axis_index(vec: Vector):
    values = [abs(vec.x), abs(vec.y), abs(vec.z)]
    return values.index(max(values))


def rotate_object_axis_to_axis(obj, source_axis_index, target_axis_index):
    if source_axis_index == target_axis_index:
        return

    basis = [Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0))]
    source_axis = basis[source_axis_index]
    target_axis = basis[target_axis_index]

    delta_quaternion = source_axis.rotation_difference(target_axis)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = delta_quaternion.to_euler('XYZ')


def apply_proportional_constraints(target_size, constrained_axes):
    if not constrained_axes:
        return target_size

    locked_value = max(target_size[index] for index in constrained_axes)
    for index in constrained_axes:
        target_size[index] = locked_value
    return target_size


def remap_world_dimensions_to_local_axes(obj, world_dimensions: Vector):
    rotation_matrix = obj.rotation_euler.to_matrix()
    basis = [Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0))]

    local_dimensions = Vector((0.0, 0.0, 0.0))
    used_world_axes = set()

    for local_axis_index, axis_vector in enumerate(basis):
        world_axis_vector = rotation_matrix @ axis_vector
        components = [abs(world_axis_vector.x), abs(world_axis_vector.y), abs(world_axis_vector.z)]

        for world_axis_index in sorted(range(3), key=lambda idx: components[idx], reverse=True):
            if world_axis_index not in used_world_axes:
                used_world_axes.add(world_axis_index)
                local_dimensions[local_axis_index] = world_dimensions[world_axis_index]
                break

    return local_dimensions


def apply_fill_to_object(obj, primitive_kind, bounds, preserve_proportions):
    obj.location = bounds.center

    raw_size = bounds.size
    target_size = Vector((
        max(raw_size.x, 0.0001),
        max(raw_size.y, 0.0001),
        max(raw_size.z, 0.0001),
    ))

    target_longest_axis = largest_axis_index(raw_size)
    constrained_axes = []

    if primitive_kind in {"disc", "cylinder"}:
        rotate_object_axis_to_axis(obj, 2, target_longest_axis)
        constrained_axes = [axis for axis in range(3) if axis != target_longest_axis]
    elif primitive_kind == "sphere":
        constrained_axes = [0, 1, 2]

    if preserve_proportions:
        target_size = apply_proportional_constraints(target_size, constrained_axes)

    target_size_local = remap_world_dimensions_to_local_axes(obj, target_size)
    obj.dimensions = target_size_local


def create_primitive_object(context, primitive_kind):
    add_ops = {
        "cube": bpy.ops.mesh.primitive_cube_add,
        "cylinder": bpy.ops.mesh.primitive_cylinder_add,
        "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "disc": bpy.ops.mesh.primitive_circle_add,
    }

    op = add_ops[primitive_kind]

    kwargs = {
        "enter_editmode": False,
        "align": 'WORLD',
        "location": (0.0, 0.0, 0.0),
        "rotation": (0.0, 0.0, 0.0),
    }

    if primitive_kind == "disc":
        kwargs["fill_type"] = 'NGON'

    try:
        op(**kwargs)
    except TypeError:
        op()

    return context.active_object


def mark_object_as_fill_selection_primitive(obj, primitive_kind):
    obj.fill_selection_is_managed = True
    obj.fill_selection_primitive_kind = primitive_kind

    if primitive_kind in {"cylinder", "disc"} and obj.fill_selection_vertices < 3:
        obj.fill_selection_vertices = 32

    if primitive_kind == "sphere":
        if obj.fill_selection_segments < 3:
            obj.fill_selection_segments = 32
        if obj.fill_selection_rings < 2:
            obj.fill_selection_rings = 16


def regenerate_fill_selection_mesh(obj):
    if not obj or obj.type != 'MESH':
        return False

    primitive_kind = obj.fill_selection_primitive_kind
    if primitive_kind not in {"cylinder", "sphere", "disc"}:
        return False

    if obj.data.users > 1:
        obj.data = obj.data.copy()

    original_dimensions = obj.dimensions.copy()

    bm = bmesh.new()
    try:
        if primitive_kind == "cylinder":
            bmesh.ops.create_cone(
                bm,
                cap_ends=True,
                cap_tris=False,
                segments=max(3, obj.fill_selection_vertices),
                radius1=1.0,
                radius2=1.0,
                depth=2.0,
            )
        elif primitive_kind == "sphere":
            bmesh.ops.create_uvsphere(
                bm,
                u_segments=max(3, obj.fill_selection_segments),
                v_segments=max(2, obj.fill_selection_rings),
                radius=1.0,
            )
        elif primitive_kind == "disc":
            bmesh.ops.create_circle(
                bm,
                cap_ends=True,
                cap_tris=False,
                segments=max(3, obj.fill_selection_vertices),
                radius=1.0,
            )

        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()

    obj.dimensions = original_dimensions
    return True


class FILL_SELECTION_OT_add_primitive(bpy.types.Operator):
    bl_idname = "mesh.fill_selection_add_primitive"
    bl_label = "Fill Selection Primitive"
    bl_options = {'REGISTER', 'UNDO'}

    primitive_kind: bpy.props.EnumProperty(
        name="Primitive",
        items=(
            ("cube", "Cube", "Fill Selection Cube"),
            ("cylinder", "Cylinder", "Fill Selection Cylinder"),
            ("sphere", "Sphere", "Fill Selection Sphere"),
            ("disc", "Disc", "Fill Selection Disc"),
        ),
    )

    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT', 'EDIT_MESH'}

    def execute(self, context):
        bounds = compute_selection_bounds(context)
        if bounds is None:
            self.report({'WARNING'}, "Aucune sélection valide pour calculer la bounding box.")
            return {'CANCELLED'}

        preserve_proportions = context.scene.fill_selection_preserve_proportions

        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')

        new_obj = create_primitive_object(context, self.primitive_kind)
        if new_obj is None:
            self.report({'ERROR'}, "Impossible de créer la primitive.")
            return {'CANCELLED'}

        apply_fill_to_object(new_obj, self.primitive_kind, bounds, preserve_proportions)
        mark_object_as_fill_selection_primitive(new_obj, self.primitive_kind)
        log(f"Created {self.primitive_kind} as '{new_obj.name}'.")
        return {'FINISHED'}


class FILL_SELECTION_OT_rebuild_primitive(bpy.types.Operator):
    bl_idname = "mesh.fill_selection_rebuild_primitive"
    bl_label = "Rebuild Primitive"
    bl_description = "Reconstruit la primitive Fill Selection avec les paramètres courants"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None and
            obj.type == 'MESH' and
            getattr(obj, "fill_selection_is_managed", False)
        )

    def execute(self, context):
        obj = context.active_object

        if not regenerate_fill_selection_mesh(obj):
            self.report({'WARNING'}, "Objet non pris en charge pour la reconstruction Fill Selection.")
            return {'CANCELLED'}

        log(f"Rebuilt {obj.fill_selection_primitive_kind} for '{obj.name}'.")
        return {'FINISHED'}


class VIEW3D_PT_fill_selection_settings(bpy.types.Panel):
    bl_label = "Fill Selection"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        layout.prop(context.scene, "fill_selection_preserve_proportions", text="Proportional Transform")

        col = layout.column(align=True)
        col.operator("mesh.fill_selection_add_primitive", text="Fill Selection Cube").primitive_kind = "cube"
        col.operator("mesh.fill_selection_add_primitive", text="Fill Selection Cylinder").primitive_kind = "cylinder"
        col.operator("mesh.fill_selection_add_primitive", text="Fill Selection Sphere").primitive_kind = "sphere"
        col.operator("mesh.fill_selection_add_primitive", text="Fill Selection Disc").primitive_kind = "disc"

        if obj and obj.type == 'MESH' and getattr(obj, "fill_selection_is_managed", False):
            box = layout.box()
            box.label(text="Selected Fill Selection Primitive")
            primitive_kind = obj.fill_selection_primitive_kind

            if primitive_kind in {"cylinder", "disc"}:
                box.prop(obj, "fill_selection_vertices", text="Vertices")
            elif primitive_kind == "sphere":
                box.prop(obj, "fill_selection_segments", text="Segments")
                box.prop(obj, "fill_selection_rings", text="Rings")

            box.operator("mesh.fill_selection_rebuild_primitive", text="Apply Parameter Changes")


CLASSES = (
    FILL_SELECTION_OT_add_primitive,
    FILL_SELECTION_OT_rebuild_primitive,
    VIEW3D_PT_fill_selection_settings,
)


def register():
    bpy.types.Scene.fill_selection_preserve_proportions = bpy.props.BoolProperty(
        name="Proportional Transform",
        description="Conserve les proportions pour les primitives concernées",
        default=False,
    )

    bpy.types.Object.fill_selection_is_managed = bpy.props.BoolProperty(
        name="Fill Selection Managed",
        description="Objet créé par Fill Selection et reconstructible",
        default=False,
    )
    bpy.types.Object.fill_selection_primitive_kind = bpy.props.EnumProperty(
        name="Fill Selection Primitive Type",
        items=(
            ("cube", "Cube", "Fill Selection Cube"),
            ("cylinder", "Cylinder", "Fill Selection Cylinder"),
            ("sphere", "Sphere", "Fill Selection Sphere"),
            ("disc", "Disc", "Fill Selection Disc"),
        ),
        default="cube",
    )
    bpy.types.Object.fill_selection_vertices = bpy.props.IntProperty(
        name="Vertices",
        description="Nombre de vertices pour les primitives supportées",
        default=32,
        min=3,
        soft_max=256,
    )
    bpy.types.Object.fill_selection_segments = bpy.props.IntProperty(
        name="Segments",
        description="Nombre de segments pour la UV sphere",
        default=32,
        min=3,
        soft_max=256,
    )
    bpy.types.Object.fill_selection_rings = bpy.props.IntProperty(
        name="Rings",
        description="Nombre de rings pour la UV sphere",
        default=16,
        min=2,
        soft_max=256,
    )

    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Scene, "fill_selection_preserve_proportions"):
        del bpy.types.Scene.fill_selection_preserve_proportions

    if hasattr(bpy.types.Object, "fill_selection_rings"):
        del bpy.types.Object.fill_selection_rings
    if hasattr(bpy.types.Object, "fill_selection_segments"):
        del bpy.types.Object.fill_selection_segments
    if hasattr(bpy.types.Object, "fill_selection_vertices"):
        del bpy.types.Object.fill_selection_vertices
    if hasattr(bpy.types.Object, "fill_selection_primitive_kind"):
        del bpy.types.Object.fill_selection_primitive_kind
    if hasattr(bpy.types.Object, "fill_selection_is_managed"):
        del bpy.types.Object.fill_selection_is_managed


if __name__ == "__main__":
    register()
