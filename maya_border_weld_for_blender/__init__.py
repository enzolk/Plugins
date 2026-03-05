bl_info = {
    "name": "Border Vertex Auto Weld (Maya Script Port)",
    "author": "OpenAI",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Search > Border Vertex Auto Weld",
    "description": "Blender port of a Maya script: weld nearby border verts or split nearest edge then weld.",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty


def _point_segment_distance(point: Vector, a: Vector, b: Vector):
    ab = b - a
    denom = ab.dot(ab)
    if denom == 0.0:
        return (point - a).length, a.copy()
    t = (point - a).dot(ab) / denom
    t = max(0.0, min(1.0, t))
    closest = a + (ab * t)
    return (point - closest).length, closest


class MESH_OT_border_vertex_auto_weld(bpy.types.Operator):
    bl_idname = "mesh.border_vertex_auto_weld"
    bl_label = "Border Vertex Auto Weld"
    bl_description = "Weld nearby vertices to selected border vertices, or split nearest edge then weld"
    bl_options = {'REGISTER', 'UNDO'}

    distance_threshold: FloatProperty(
        name="Nearby Vertex Distance",
        default=0.002,
        min=0.0,
        description="Search distance to find a nearby vertex to weld",
    )
    max_edge_distance: FloatProperty(
        name="Max Edge Distance",
        default=0.05,
        min=0.0,
        description="Maximum distance for nearest edge detection",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (
            obj is not None
            and obj.type == 'MESH'
            and context.mode == 'EDIT_MESH'
        )

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        world_matrix = obj.matrix_world
        selected_verts = [v for v in bm.verts if v.select]

        if not selected_verts:
            self.report({'WARNING'}, "Please select at least one vertex.")
            return {'CANCELLED'}

        merged_count = 0
        split_weld_count = 0

        for target in list(selected_verts):
            if not target.is_valid:
                continue

            if not any(edge.is_boundary for edge in target.link_edges):
                self.report({'INFO'}, f"Vertex {target.index} is not on a border and was skipped.")
                continue

            target_world = world_matrix @ target.co

            nearby = []
            for other in bm.verts:
                if not other.is_valid or other == target:
                    continue
                other_world = world_matrix @ other.co
                if (other_world - target_world).length < self.distance_threshold:
                    nearby.append(other)

            if nearby:
                for src in nearby:
                    if src.is_valid and target.is_valid and src != target:
                        bmesh.ops.weld_verts(bm, targetmap={src: target})
                        merged_count += 1
                continue

            connected_edges = set(target.link_edges)
            best_edge = None
            best_distance = float('inf')

            for edge in bm.edges:
                if not edge.is_valid or edge in connected_edges:
                    continue
                v1, v2 = edge.verts
                v1_world = world_matrix @ v1.co
                v2_world = world_matrix @ v2.co
                distance, _ = _point_segment_distance(target_world, v1_world, v2_world)
                if distance < best_distance and distance <= self.max_edge_distance:
                    best_distance = distance
                    best_edge = edge

            if best_edge is None:
                self.report({'INFO'}, f"No edge found within {self.max_edge_distance} units from vertex {target.index}.")
                continue

            split = bmesh.ops.subdivide_edges(
                bm,
                edges=[best_edge],
                cuts=1,
                use_grid_fill=False,
                smooth=0.0,
            )
            new_verts = [g for g in split.get("geom_split", []) if isinstance(g, bmesh.types.BMVert)]
            if not new_verts:
                self.report({'WARNING'}, f"Could not create a vertex on edge {best_edge.index}.")
                continue

            new_vert = new_verts[-1]
            if new_vert.is_valid and target.is_valid:
                bmesh.ops.weld_verts(bm, targetmap={new_vert: target})
                split_weld_count += 1

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=True)
        self.report({'INFO'}, f"Done. Direct welds: {merged_count}, split+weld: {split_weld_count}")
        return {'FINISHED'}


class VIEW3D_PT_auto_weld_vertex_tool(bpy.types.Panel):
    bl_label = "Auto Weld Vertex Tool"
    bl_idname = "VIEW3D_PT_auto_weld_vertex_tool"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Edit"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def draw(self, _context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator(MESH_OT_border_vertex_auto_weld.bl_idname, icon='AUTOMERGE_ON')


classes = (MESH_OT_border_vertex_auto_weld, VIEW3D_PT_auto_weld_vertex_tool)


def menu_func(self, _context):
    self.layout.operator(MESH_OT_border_vertex_auto_weld.bl_idname, icon='AUTOMERGE_ON')


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_MT_edit_mesh_clean.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_edit_mesh_clean.remove(menu_func)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
