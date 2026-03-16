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



def selected_points_for_edit_mesh(context):
    obj = context.active_object
    if not obj or obj.type != 'MESH':
        return []

    if context.mode != 'EDIT_MESH':
        return []

    bm = bmesh.from_edit_mesh(obj.data)
    selected_verts = [vert for vert in bm.verts if vert.select]
    points = [obj.matrix_world @ vert.co for vert in selected_verts]

    if points:
        return points

    selected_edges = [edge for edge in bm.edges if edge.select]
    for edge in selected_edges:
        points.extend([obj.matrix_world @ edge.verts[0].co, obj.matrix_world @ edge.verts[1].co])

    if points:
        return points

    selected_faces = [face for face in bm.faces if face.select]
    for face in selected_faces:
        for vert in face.verts:
            points.append(obj.matrix_world @ vert.co)

    return points



def compute_selection_bounds(context):
    log(f"Compute bounds start. Mode={context.mode}, selected_objects={len(context.selected_objects)}")

    points = []

    if context.mode == 'EDIT_MESH':
        edit_points = selected_points_for_edit_mesh(context)
        points.extend(edit_points)
        log(f"EDIT_MESH selected points count={len(edit_points)}")

    if not points and context.selected_objects:
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



def align_flat_object_to_axis(obj, target_axis_index):
    original_dims = obj.dimensions.copy()
    source_axis_index = smallest_axis_index(original_dims)

    if source_axis_index == target_axis_index:
        log(f"{obj.name}: flat axis already aligned to target axis index={target_axis_index}")
        return

    axes = [Vector((1.0, 0.0, 0.0)), Vector((0.0, 1.0, 0.0)), Vector((0.0, 0.0, 1.0))]
    source_axis = axes[source_axis_index]
    target_axis = axes[target_axis_index]

    delta_quaternion = source_axis.rotation_difference(target_axis)
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = delta_quaternion.to_euler('XYZ')
    log(
        f"{obj.name}: rotated flat object source_axis={source_axis_index} -> target_axis={target_axis_index}, "
        f"rotation={tuple(round(v, 5) for v in obj.rotation_euler)}"
    )



def apply_fill_to_object(obj, bounds):
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
    current_min = min(abs(current_dims.x), abs(current_dims.y), abs(current_dims.z))
    current_max = max(abs(current_dims.x), abs(current_dims.y), abs(current_dims.z), 0.0001)
    is_flat = (current_min / current_max) < 0.05

    if is_flat:
        target_smallest_axis = smallest_axis_index(raw_size)
        log(f"{obj.name}: detected flat primitive. Target smallest axis={target_smallest_axis}")
        align_flat_object_to_axis(obj, target_smallest_axis)

    obj.dimensions = target_size
    log(
        f"{obj.name}: final location={tuple(round(v, 5) for v in obj.location)}, "
        f"dimensions={tuple(round(v, 5) for v in obj.dimensions)}"
    )



def update_selection_snapshot(context):
    bounds = compute_selection_bounds(context)
    _TRACKER["last_selection_bounds"] = bounds
    if bounds:
        log("Selection snapshot updated with valid bounds.")
    else:
        log("Selection snapshot cleared (no active selection).")



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
    log(f"Known object cache refreshed. count={len(_TRACKER['known_object_names'])}")



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
        _TRACKER["last_selection_bounds"] = None
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
                apply_fill_to_object(obj, bounds)

    _TRACKER["known_object_names"] = current_names
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

    _TRACKER["known_object_names"] = set()
    _TRACKER["last_selection_bounds"] = None
    log("Unregister add-on complete.")


if __name__ == "__main__":
    register()
