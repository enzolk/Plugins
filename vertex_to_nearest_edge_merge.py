bl_info = {
    "name": "Merge Selected Vertex to Nearest Non-Connected Edge",
    "author": "Codex",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Edit",
    "description": "Find nearest non-connected edge from selected vertex, create point on edge, and merge to it",
    "category": "Mesh",
}

import bpy
import bmesh
from mathutils import Vector


def _format_vec(vec: Vector) -> str:
    return f"({vec.x:.6f}, {vec.y:.6f}, {vec.z:.6f})"


def _closest_point_on_segment(point: Vector, seg_a: Vector, seg_b: Vector):
    seg = seg_b - seg_a
    seg_len_sq = seg.length_squared
    if seg_len_sq == 0.0:
        return seg_a.copy(), 0.0
    t = (point - seg_a).dot(seg) / seg_len_sq
    t_clamped = max(0.0, min(1.0, t))
    closest = seg_a + t_clamped * seg
    return closest, t_clamped


class MESH_OT_merge_to_nearest_edge_point(bpy.types.Operator):
    bl_idname = "mesh.merge_to_nearest_edge_point"
    bl_label = "Merge To Nearest Edge Point"
    bl_description = "Merge selected vertex to closest point on nearest non-connected edge"
    bl_options = {'REGISTER', 'UNDO'}

    def log(self, step: str, message: str):
        print(f"[MergeToNearestEdge][{step}] {message}")

    def execute(self, context):
        step = "INIT"
        try:
            self.log(step, "Démarrage de l'outil.")

            obj = context.edit_object
            if obj is None or obj.type != 'MESH':
                self.log(step, "Erreur: aucun mesh en mode édition actif.")
                self.report({'ERROR'}, "Activez un objet Mesh en mode Édition.")
                return {'CANCELLED'}

            if context.mode != 'EDIT_MESH':
                self.log(step, f"Erreur: mode courant = {context.mode}, attendu EDIT_MESH.")
                self.report({'ERROR'}, "Passez en mode Édition mesh.")
                return {'CANCELLED'}

            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            step = "FIND_VERTEX_A"
            selected_verts = [v for v in bm.verts if v.select]
            self.log(step, f"Vertices sélectionnés trouvés: {len(selected_verts)}")

            if len(selected_verts) == 0:
                self.log(step, "Erreur: aucun vertex sélectionné.")
                self.report({'ERROR'}, "Sélectionnez un vertex (A).")
                return {'CANCELLED'}

            active_vert = bm.select_history.active if isinstance(bm.select_history.active, bmesh.types.BMVert) else None
            vertex_a = active_vert if (active_vert and active_vert.select) else selected_verts[0]
            self.log(step, f"Vertex A choisi: index={vertex_a.index}, co={_format_vec(vertex_a.co)}")

            step = "FIND_NEAREST_EDGE"
            nearest_edge = None
            nearest_point = None
            nearest_dist_sq = float('inf')
            nearest_t = 0.0

            non_connected_edges_count = 0
            for edge in bm.edges:
                if vertex_a in edge.verts:
                    continue
                non_connected_edges_count += 1

                v1, v2 = edge.verts
                point_on_edge, t = _closest_point_on_segment(vertex_a.co, v1.co, v2.co)
                dist_sq = (vertex_a.co - point_on_edge).length_squared

                if dist_sq < nearest_dist_sq:
                    nearest_dist_sq = dist_sq
                    nearest_edge = edge
                    nearest_point = point_on_edge
                    nearest_t = t

            self.log(step, f"Edges non-connectées examinées: {non_connected_edges_count}")

            if nearest_edge is None:
                self.log(step, "Erreur: aucune edge non connectée trouvée.")
                self.report({'ERROR'}, "Aucune edge non connectée au vertex A trouvée.")
                return {'CANCELLED'}

            e_v1, e_v2 = nearest_edge.verts
            self.log(
                step,
                (
                    "Edge la plus proche trouvée: "
                    f"index={nearest_edge.index}, verts=({e_v1.index}, {e_v2.index}), "
                    f"t={nearest_t:.6f}, point={_format_vec(nearest_point)}, "
                    f"distance={nearest_dist_sq ** 0.5:.6f}"
                )
            )

            step = "SUBDIVIDE_EDGE"
            old_verts = set(bm.verts)
            self.log(step, f"Subdivision de l'edge index={nearest_edge.index} avec cuts=1")
            result = bmesh.ops.subdivide_edges(
                bm,
                edges=[nearest_edge],
                cuts=1,
                use_grid_fill=False,
            )

            new_verts = [elem for elem in result.get("geom_split", []) if isinstance(elem, bmesh.types.BMVert)]
            if not new_verts:
                # Fallback robuste au cas où geom_split serait vide selon version.
                new_verts = [v for v in bm.verts if v not in old_verts]

            self.log(step, f"Nouveaux vertices créés après subdivision: {len(new_verts)}")

            if len(new_verts) == 0:
                self.log(step, "Erreur: impossible d'identifier le vertex B après subdivision.")
                self.report({'ERROR'}, "Subdivision effectuée mais vertex B introuvable.")
                return {'CANCELLED'}

            vertex_b = min(new_verts, key=lambda v: (v.co - nearest_point).length_squared)
            self.log(step, f"Vertex B identifié: index={vertex_b.index}, co_initiale={_format_vec(vertex_b.co)}")

            step = "MOVE_VERTEX_B"
            vertex_b.co = nearest_point
            self.log(step, f"Vertex B déplacé vers le point projeté: co_finale={_format_vec(vertex_b.co)}")

            step = "MERGE_A_TO_B"
            for v in bm.verts:
                v.select = False
            vertex_a.select = True
            vertex_b.select = True

            try:
                bm.select_history.clear()
            except Exception:
                pass
            bm.select_history.add(vertex_a)
            bm.select_history.add(vertex_b)

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

            self.log(step, f"Merge At Last en cours: A(index={vertex_a.index}) -> B(index={vertex_b.index})")
            merge_result = bpy.ops.mesh.merge(type='LAST')
            self.log(step, f"Résultat opérateur merge: {merge_result}")

            if 'FINISHED' not in merge_result:
                self.log(step, "Erreur: échec de l'opération bpy.ops.mesh.merge(type='LAST').")
                self.report({'ERROR'}, "Échec de l'opération Merge At Last.")
                return {'CANCELLED'}

            step = "DONE"
            self.log(step, "Opération terminée avec succès.")
            self.report({'INFO'}, "Vertex A fusionné vers le point de l'edge la plus proche.")
            return {'FINISHED'}

        except Exception as ex:
            self.log(step, f"Exception capturée: {repr(ex)}")
            self.report({'ERROR'}, f"Erreur pendant l'étape {step}: {ex}")
            return {'CANCELLED'}


class VIEW3D_PT_merge_to_nearest_edge_point(bpy.types.Panel):
    bl_label = "Merge Vertex to Edge Point"
    bl_idname = "VIEW3D_PT_merge_vertex_to_edge_point"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    bl_context = "mesh_edit"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Outil de fusion A -> B")
        col.operator(MESH_OT_merge_to_nearest_edge_point.bl_idname, icon='AUTOMERGE_ON')


classes = (
    MESH_OT_merge_to_nearest_edge_point,
    VIEW3D_PT_merge_to_nearest_edge_point,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
