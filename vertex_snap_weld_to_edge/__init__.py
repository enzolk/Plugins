bl_info = {
    "name": "Vertex Snap Weld To Nearest Edge",
    "author": "GPT-5.2-Codex",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar (N) > Edit",
    "description": "Snap selected vertices to nearest non-connected edges by inserting and welding vertices.",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector
from bpy.props import FloatProperty
from bpy.types import Operator, Panel, PropertyGroup


EPS = 1e-12


def closest_point_on_segment(point: Vector, a: Vector, b: Vector):
    ab = b - a
    ab_len_sq = ab.length_squared
    if ab_len_sq <= EPS:
        return a.copy(), 0.0
    t = (point - a).dot(ab) / ab_len_sq
    t = max(0.0, min(1.0, t))
    return a + ab * t, t


class VSWTE_Props(PropertyGroup):
    max_edge_distance: FloatProperty(
        name="Max Edge Distance",
        description="Maximum distance from selected vertex to nearest non-connected edge",
        default=0.05,
        min=0.0,
        soft_max=10.0,
        precision=4,
    )


class MESH_OT_snap_weld_to_nearest_edge(Operator):
    bl_idname = "mesh.snap_weld_to_nearest_edge"
    bl_label = "Snap Weld To Nearest Edge"
    bl_description = "Project selected vertices to nearest non-connected edge, insert a vertex on edge, then weld"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.edit_object
        return (
            obj is not None
            and obj.type == "MESH"
            and context.mode == "EDIT_MESH"
        )

    def execute(self, context):
        obj = context.edit_object
        me = obj.data
        bm = bmesh.from_edit_mesh(me)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        props = context.scene.vswte_props
        max_dist = props.max_edge_distance

        selected_verts = [v for v in bm.verts if v.select and v.is_valid]
        if not selected_verts:
            self.report({"WARNING"}, "No selected vertices")
            return {"CANCELLED"}

        welded_count = 0

        for src_vert in selected_verts:
            if not src_vert.is_valid:
                continue

            connected_edges = set(src_vert.link_edges)
            nearest_edge = None
            nearest_point = None
            nearest_dist = None

            for edge in bm.edges:
                if edge in connected_edges:
                    continue
                if not edge.is_valid:
                    continue

                a = edge.verts[0].co
                b = edge.verts[1].co
                point_on_edge, _ = closest_point_on_segment(src_vert.co, a, b)
                dist = (src_vert.co - point_on_edge).length

                if nearest_dist is None or dist < nearest_dist:
                    nearest_dist = dist
                    nearest_edge = edge
                    nearest_point = point_on_edge

            if nearest_edge is None or nearest_dist is None:
                continue

            if nearest_dist > max_dist:
                continue

            subdivide_result = bmesh.ops.subdivide_edges(
                bm,
                edges=[nearest_edge],
                cuts=1,
                use_grid_fill=False,
                smooth=0.0,
            )

            new_verts = [g for g in subdivide_result.get("geom_inner", []) if isinstance(g, bmesh.types.BMVert)]
            if not new_verts:
                new_verts = [g for g in subdivide_result.get("geom_split", []) if isinstance(g, bmesh.types.BMVert)]
            if not new_verts:
                continue

            new_vert = min(new_verts, key=lambda v: (v.co - nearest_point).length_squared)

            # Edge slide-style adjustment: move only the inserted vertex along the split edge.
            new_vert.co = nearest_point

            src_vert.co = new_vert.co
            bmesh.ops.weld_verts(bm, targetmap={src_vert: new_vert})
            welded_count += 1

        if welded_count == 0:
            self.report({"INFO"}, "No vertex was close enough to a non-connected edge")
            return {"CANCELLED"}

        bmesh.update_edit_mesh(me, loop_triangles=False, destructive=True)
        self.report({"INFO"}, f"Welded {welded_count} vertex(s)")
        return {"FINISHED"}


class VIEW3D_PT_snap_weld_to_nearest_edge(Panel):
    bl_label = "Snap Weld To Edge"
    bl_idname = "VIEW3D_PT_snap_weld_to_nearest_edge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Edit"

    @classmethod
    def poll(cls, context):
        obj = context.edit_object
        return obj is not None and obj.type == "MESH" and context.mode == "EDIT_MESH"

    def draw(self, context):
        layout = self.layout
        props = context.scene.vswte_props

        col = layout.column(align=True)
        col.prop(props, "max_edge_distance")
        col.operator(MESH_OT_snap_weld_to_nearest_edge.bl_idname, icon="AUTOMERGE_ON")


CLASSES = (
    VSWTE_Props,
    MESH_OT_snap_weld_to_nearest_edge,
    VIEW3D_PT_snap_weld_to_nearest_edge,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.vswte_props = bpy.props.PointerProperty(type=VSWTE_Props)


def unregister():
    if hasattr(bpy.types.Scene, "vswte_props"):
        del bpy.types.Scene.vswte_props
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
