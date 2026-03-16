bl_info = {
    "name": "Native Add Fill Selection",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Edit",
    "description": "Adapte les objets ajoutés via les opérateurs natifs à la bounding box de la sélection.",
    "category": "3D View",
}

import bpy
import bmesh
from bpy.app.handlers import persistent
from mathutils import Vector


LOG_PREFIX = "[FillSelection]"
_HANDLER_REGISTERED = False
_TRACKER = {
    "known_object_names": set(),
    "last_selection_bounds": None,
    "last_valid_selection_bounds": None,
    "edit_mesh_signatures": {},
}


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
    if not obj or obj.type != 'MESH':
        return []

    if context.mode != 'EDIT_MESH':
        return []

    bm = bmesh.from_edit_mesh(obj.data)
    selected_verts = selected_edit_mesh_vertices(bm)
    return [obj.matrix_world @ vert.co for vert in selected_verts]



def compute_selection_bounds(context):
    log(f"Compute bounds start. Mode={context.mode}, selected_objects={len(context.selected_objects)}")

    points = []

    if context.mode == 'EDIT_MESH':
        edit_points = selected_points_for_edit_mesh(context)
        points.extend(edit_points)
        log(f"EDIT_MESH selected points count={len(edit_points)}")

    if context.mode != 'EDIT_MESH' and not points and context.selected_objects:
        object_points = selected_points_for_object_mode(context)
        points.extend(object_points)
        log(f"OBJECT selection points count={len(object_points)}")

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



def smallest_axis_index(vec: Vector):
    values = [abs(vec.x), abs(vec.y), abs(vec.z)]
    return values.index(min(values))


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


def axis_profile(dimensions: Vector):
    dims = [max(abs(dimensions.x), 0.0001), max(abs(dimensions.y), 0.0001), max(abs(dimensions.z), 0.0001)]
    sorted_indices = sorted(range(3), key=lambda i: dims[i])

    min_idx = sorted_indices[0]
    mid_idx = sorted_indices[1]
    max_idx = sorted_indices[2]

    min_dim = dims[min_idx]
    mid_dim = dims[mid_idx]
    max_dim = dims[max_idx]

    almost_equal = lambda a, b: abs(a - b) <= max(a, b) * 0.08

    is_sphere_like = almost_equal(min_dim, max_dim)
    is_cylinder_like = (max_dim / mid_dim) > 1.4 and almost_equal(mid_dim, min_dim)
    is_disk_like = (mid_dim / min_dim) > 1.4 and almost_equal(max_dim, mid_dim)

    return {
        "min_axis": min_idx,
        "mid_axis": mid_idx,
        "max_axis": max_idx,
        "is_sphere_like": is_sphere_like,
        "is_cylinder_like": is_cylinder_like,
        "is_disk_like": is_disk_like,
    }


def infer_native_primitive_kind(obj):
    name = (obj.name or "").lower()

    if name.startswith("cylinder"):
        return "cylinder"
    if name.startswith("cone"):
        return "cone"
    if name.startswith("circle"):
        return "disk"
    if name.startswith("plane"):
        return "plane"
    if name.startswith("uvsphere") or name.startswith("icosphere"):
        return "sphere"

    return None



def align_flat_object_to_axis(obj, target_axis_index):
    original_dims = obj.dimensions.copy()
    source_axis_index = smallest_axis_index(original_dims)

    if source_axis_index == target_axis_index:
        log(f"{obj.name}: flat axis already aligned to target axis index={target_axis_index}")
        return

    rotate_object_axis_to_axis(obj, source_axis_index, target_axis_index)
    log(
        f"{obj.name}: rotated flat object source_axis={source_axis_index} -> target_axis={target_axis_index}, "
        f"rotation={tuple(round(v, 5) for v in obj.rotation_euler)}"
    )



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


def apply_fill_to_object(obj, bounds, preserve_proportions):
    if not bounds:
        log(f"{obj.name}: no bounds, skip fill.")
        return

    log(f"{obj.name}: applying fill from bounds.")
    obj.location = bounds.center

    raw_size = bounds.size
    target_size = Vector((
        max(raw_size.x, 0.0001),
        max(raw_size.y, 0.0001),
        max(raw_size.z, 0.0001),
    ))

    current_dims = obj.dimensions.copy()
    profile = axis_profile(current_dims)
    target_longest_axis = largest_axis_index(raw_size)
    primitive_kind = infer_native_primitive_kind(obj)

    constrained_axes = []

    if primitive_kind in {"disk", "plane"}:
        source_normal_axis = 2
        rotate_object_axis_to_axis(obj, source_normal_axis, target_longest_axis)
        constrained_axes = [axis for axis in range(3) if axis != target_longest_axis]
        log(
            f"{obj.name}: native {primitive_kind}-like primitive detected (normal axis Z -> {target_longest_axis})."
        )
    elif primitive_kind in {"cylinder", "cone"}:
        source_long_axis = 2
        rotate_object_axis_to_axis(obj, source_long_axis, target_longest_axis)
        constrained_axes = [axis for axis in range(3) if axis != target_longest_axis]
        log(
            f"{obj.name}: native {primitive_kind}-like primitive detected (long axis Z -> {target_longest_axis})."
        )
    elif primitive_kind == "sphere":
        constrained_axes = [0, 1, 2]
        log(f"{obj.name}: native sphere-like primitive detected.")
    elif profile["is_disk_like"]:
        source_normal_axis = profile["min_axis"]
        rotate_object_axis_to_axis(obj, source_normal_axis, target_longest_axis)
        constrained_axes = [axis for axis in range(3) if axis != target_longest_axis]
        log(
            f"{obj.name}: disk-like primitive aligned normal axis {source_normal_axis} -> {target_longest_axis}."
        )
    elif profile["is_cylinder_like"]:
        source_long_axis = profile["max_axis"]
        rotate_object_axis_to_axis(obj, source_long_axis, target_longest_axis)
        constrained_axes = [axis for axis in range(3) if axis != target_longest_axis]
        log(
            f"{obj.name}: cylinder-like primitive aligned long axis {source_long_axis} -> {target_longest_axis}."
        )
    elif profile["is_sphere_like"]:
        constrained_axes = [0, 1, 2]
        log(f"{obj.name}: sphere-like primitive detected.")
    else:
        target_smallest_axis = smallest_axis_index(raw_size)
        align_flat_object_to_axis(obj, target_smallest_axis)

    if preserve_proportions:
        target_size = apply_proportional_constraints(target_size, constrained_axes)
        log(f"{obj.name}: proportional constraints applied on axes={constrained_axes}")

    target_size_local = remap_world_dimensions_to_local_axes(obj, target_size)
    obj.dimensions = target_size_local
    log(
        f"{obj.name}: final location={tuple(round(v, 5) for v in obj.location)}, "
        f"world_target_size={tuple(round(v, 5) for v in target_size)}, "
        f"local_dimensions={tuple(round(v, 5) for v in obj.dimensions)}"
    )



def update_selection_snapshot(context):
    bounds = compute_selection_bounds(context)
    _TRACKER["last_selection_bounds"] = bounds
    if bounds:
        _TRACKER["last_valid_selection_bounds"] = bounds
        log("Selection snapshot updated with valid bounds.")
    else:
        log("Selection snapshot cleared (no active selection). Last valid bounds kept.")



def get_available_scene(context=None):
    if context is not None and hasattr(context, "scene") and context.scene is not None:
        return context.scene

    data = getattr(bpy, "data", None)
    if data is None or not hasattr(data, "scenes"):
        return None

    scenes = data.scenes
    if scenes:
        return scenes[0]

    return None



def refresh_known_objects(scene):
    if scene is None:
        _TRACKER["known_object_names"] = set()
        log("Known object cache cleared: no scene available yet.")
        return

    _TRACKER["known_object_names"] = {obj.name for obj in scene.objects}
    _TRACKER["edit_mesh_signatures"] = {}
    log(f"Known object cache refreshed. count={len(_TRACKER['known_object_names'])}")


def edit_mesh_signature(obj):
    if obj is None or obj.type != 'MESH':
        return None

    mesh = obj.data
    return (len(mesh.vertices), len(mesh.edges), len(mesh.polygons))


def selection_bounds_from_selected_edit_vertices(obj, bm):
    selected_verts = selected_edit_mesh_vertices(bm)
    if not selected_verts:
        return None, []

    points = [obj.matrix_world @ vert.co for vert in selected_verts]
    return build_bounds(points), selected_verts


def apply_fill_to_selected_edit_mesh(obj, bounds, preserve_proportions):
    if not bounds:
        return

    bm = bmesh.from_edit_mesh(obj.data)
    current_bounds, selected_verts = selection_bounds_from_selected_edit_vertices(obj, bm)

    if not current_bounds or not selected_verts:
        log(f"{obj.name}: no selected edit vertices to transform.")
        return

    source_size = current_bounds.size
    target_size = bounds.size

    factors = [
        (target_size[index] / source_size[index]) if abs(source_size[index]) > 1e-8 else 1.0
        for index in range(3)
    ]

    if preserve_proportions:
        uniform = max(factors)
        factors = [uniform, uniform, uniform]

    inverse_world = obj.matrix_world.inverted()

    for vert in selected_verts:
        world = obj.matrix_world @ vert.co
        offset = world - current_bounds.center
        transformed = Vector((
            offset.x * factors[0],
            offset.y * factors[1],
            offset.z * factors[2],
        ))
        new_world = bounds.center + transformed
        vert.co = inverse_world @ new_world

    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    log(
        f"{obj.name}: edit-mode fill applied with scale={tuple(round(f, 5) for f in factors)}, "
        f"target_center={tuple(round(v, 5) for v in bounds.center)}"
    )


def find_recent_primitive_add_operator(context):
    wm = getattr(context, "window_manager", None)
    operators = getattr(wm, "operators", None)
    if not operators:
        return None

    for op in reversed(list(operators)):
        op_id = getattr(op, "bl_idname", "") or ""
        if op_id.startswith("MESH_OT_primitive_") and op_id.endswith("_add"):
            return op

    return None


def infer_primitive_from_operator(op):
    if op is None:
        return None

    mapping = {
        "MESH_OT_primitive_plane_add": "plane",
        "MESH_OT_primitive_cube_add": "cube",
        "MESH_OT_primitive_circle_add": "circle",
        "MESH_OT_primitive_uv_sphere_add": "uv_sphere",
        "MESH_OT_primitive_ico_sphere_add": "ico_sphere",
        "MESH_OT_primitive_cylinder_add": "cylinder",
        "MESH_OT_primitive_cone_add": "cone",
        "MESH_OT_primitive_torus_add": "torus",
    }
    return mapping.get(getattr(op, "bl_idname", ""))


def primitive_operator_kwargs(op):
    if op is None:
        return {}

    allowed = {
        "size", "radius", "radius1", "radius2", "depth", "vertices", "segments",
        "ring_count", "subdivisions", "end_fill_type", "fill_type", "calc_uvs",
        "major_segments", "minor_segments", "abso_major_rad", "abso_minor_rad",
        "major_radius", "minor_radius",
    }

    props = getattr(op, "properties", None)
    if props is None:
        return {}

    kwargs = {}
    for key in props.keys():
        if key in allowed:
            kwargs[key] = props.get(key)

    kwargs["enter_editmode"] = False
    kwargs["align"] = 'WORLD'
    kwargs["location"] = (0.0, 0.0, 0.0)
    kwargs["rotation"] = (0.0, 0.0, 0.0)
    return kwargs


def recreate_primitive_object(context, primitive_kind, source_op=None):
    add_ops = {
        "plane": bpy.ops.mesh.primitive_plane_add,
        "cube": bpy.ops.mesh.primitive_cube_add,
        "circle": bpy.ops.mesh.primitive_circle_add,
        "uv_sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "ico_sphere": bpy.ops.mesh.primitive_ico_sphere_add,
        "cylinder": bpy.ops.mesh.primitive_cylinder_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
    }

    op = add_ops.get(primitive_kind)
    if op is None:
        return None

    kwargs = primitive_operator_kwargs(source_op)

    try:
        op(**kwargs)
    except TypeError:
        op()

    return context.active_object


def remove_recent_edit_mode_geometry(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    selected_verts = [vert for vert in bm.verts if vert.select]

    if not selected_verts:
        return False

    bmesh.ops.delete(bm, geom=selected_verts, context='VERTS')
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=True)
    return True


def process_edit_mode_addition(context):
    if context.mode != 'EDIT_MESH':
        return

    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return

    current_signature = edit_mesh_signature(obj)
    if current_signature is None:
        return

    previous_signature = _TRACKER["edit_mesh_signatures"].get(obj.name)
    _TRACKER["edit_mesh_signatures"][obj.name] = current_signature

    if previous_signature is None or previous_signature == current_signature:
        return

    if not context.scene.fill_selection_enabled:
        return

    bounds = _TRACKER["last_valid_selection_bounds"]
    if bounds is None:
        log(f"{obj.name}: edit topology changed but no stored bounds to apply.")
        return

    recent_op = find_recent_primitive_add_operator(context)
    primitive_kind = infer_primitive_from_operator(recent_op)
    if primitive_kind is None:
        log(f"{obj.name}: edit topology changed but no supported primitive operator detected.")
        return

    log(f"{obj.name}: detected edit-mode primitive add '{primitive_kind}', converting to object workflow.")

    if not remove_recent_edit_mode_geometry(obj):
        log(f"{obj.name}: unable to isolate freshly added geometry; abort conversion.")
        return

    bpy.ops.object.mode_set(mode='OBJECT')

    new_obj = recreate_primitive_object(context, primitive_kind, source_op=recent_op)
    if new_obj is None:
        log(f"{obj.name}: failed to recreate primitive '{primitive_kind}' in object mode.")
        return

    apply_fill_to_object(new_obj, bounds, context.scene.fill_selection_preserve_proportions)
    refresh_known_objects(context.scene)
    log(f"{obj.name}: edit-mode primitive converted to '{new_obj.name}' object and filled.")



@persistent
def depsgraph_fill_handler(scene, depsgraph):
    context = bpy.context

    if not context or not hasattr(context, "scene") or context.scene is None:
        return

    enabled = context.scene.fill_selection_enabled
    current_names = {obj.name for obj in scene.objects}
    known_names = _TRACKER["known_object_names"]
    new_names = current_names - known_names

    if not enabled:
        if new_names:
            log(f"Feature disabled: observed {len(new_names)} new objects, no transform applied.")
        _TRACKER["known_object_names"] = current_names
        process_edit_mode_addition(context)
        _TRACKER["last_selection_bounds"] = None
        _TRACKER["last_valid_selection_bounds"] = None
        return

    if new_names:
        log(f"Detected new objects={list(new_names)}")
        bounds = _TRACKER["last_selection_bounds"]

        if bounds is None:
            log("No previous selection bounds stored. New object(s) keep native behavior.")
        else:
            for name in new_names:
                obj = scene.objects.get(name)
                if obj is None:
                    log(f"Object '{name}' not found in scene at apply time.")
                    continue
                apply_fill_to_object(obj, bounds, context.scene.fill_selection_preserve_proportions)
    else:
        process_edit_mode_addition(context)

    _TRACKER["known_object_names"] = {obj.name for obj in scene.objects}
    update_selection_snapshot(context)



def on_toggle_fill_selection(self, context):
    state = context.scene.fill_selection_enabled
    log(f"UI toggle changed. fill_selection_enabled={state}")
    if state:
        refresh_known_objects(context.scene)
        update_selection_snapshot(context)



class VIEW3D_PT_fill_selection_settings(bpy.types.Panel):
    bl_label = "Fill Selection (Native Add)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "fill_selection_enabled", text="Enable Fill Selection")
        layout.prop(context.scene, "fill_selection_preserve_proportions", text="Conserver les proportions")
        layout.label(text="Works with native Shift+A operators")


CLASSES = (
    VIEW3D_PT_fill_selection_settings,
)



def register_handlers():
    global _HANDLER_REGISTERED
    if _HANDLER_REGISTERED:
        return

    bpy.app.handlers.depsgraph_update_post.append(depsgraph_fill_handler)
    _HANDLER_REGISTERED = True
    log("depsgraph handler registered.")



def unregister_handlers():
    global _HANDLER_REGISTERED
    if not _HANDLER_REGISTERED:
        return

    try:
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_fill_handler)
    except ValueError:
        pass

    _HANDLER_REGISTERED = False
    log("depsgraph handler unregistered.")



def register():
    log("Register add-on start.")
    bpy.types.Scene.fill_selection_enabled = bpy.props.BoolProperty(
        name="Enable Fill Selection",
        description="Ajuste automatiquement les objets ajoutés à la bounding box de la sélection",
        default=False,
        update=on_toggle_fill_selection,
    )
    bpy.types.Scene.fill_selection_preserve_proportions = bpy.props.BoolProperty(
        name="Conserver les proportions",
        description="Conserve les proportions pour éviter la déformation des sphères, cylindres et disques",
        default=False,
    )

    for cls in CLASSES:
        bpy.utils.register_class(cls)

    register_handlers()
    refresh_known_objects(get_available_scene(bpy.context))
    log("Register add-on complete.")



def unregister():
    log("Unregister add-on start.")
    unregister_handlers()

    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

    if hasattr(bpy.types.Scene, "fill_selection_enabled"):
        del bpy.types.Scene.fill_selection_enabled
    if hasattr(bpy.types.Scene, "fill_selection_preserve_proportions"):
        del bpy.types.Scene.fill_selection_preserve_proportions

    _TRACKER["known_object_names"] = set()
    _TRACKER["last_selection_bounds"] = None
    _TRACKER["last_valid_selection_bounds"] = None
    log("Unregister add-on complete.")


if __name__ == "__main__":
    register()
