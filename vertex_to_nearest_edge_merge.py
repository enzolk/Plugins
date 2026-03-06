bl_info = {
    "name": "Merge Selected Vertex to Nearest Non-Connected Edge",
    "author": "Codex",
    "version": (1, 0, 1),
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

    def _merge_single_vertex(self, bm, vertex_a):
        step = "FIND_NEAREST_EDGE"
        vertex_a_initial_index = vertex_a.index
        vertex_a_initial_co = vertex_a.co.copy()
        self.log(step, f"Vertex A choisi: index={vertex_a.index}, co={_format_vec(vertex_a.co)}")

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
            raise RuntimeError("Aucune edge non connectée au vertex A trouvée.")

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
            raise RuntimeError("Subdivision effectuée mais vertex B introuvable.")

        vertex_b = min(new_verts, key=lambda v: (v.co - nearest_point).length_squared)
        self.log(step, f"Vertex B identifié: index={vertex_b.index}, co_initiale={_format_vec(vertex_b.co)}")

        bm.verts.index_update()
        bm.verts.ensure_lookup_table()

        if not vertex_a.is_valid:
            self.log(
                step,
                (
                    "Référence de Vertex A invalide après subdivision; "
                    f"tentative de récupération par index initial={vertex_a_initial_index}."
                )
            )
            recovered_a = None
            for vert in bm.verts:
                if vert.index == vertex_a_initial_index and vert.is_valid:
                    recovered_a = vert
                    break

            if recovered_a is None:
                recovered_a = min(
                    (vert for vert in bm.verts if vert.is_valid),
                    key=lambda v: (v.co - vertex_a_initial_co).length_squared,
                    default=None,
                )

            if recovered_a is None:
                raise RuntimeError("Vertex A invalide après subdivision.")

            vertex_a = recovered_a
            self.log(step, f"Vertex A récupéré: index={vertex_a.index}, co={_format_vec(vertex_a.co)}")

        step = "MOVE_VERTEX_B"
        vertex_b.co = nearest_point
        self.log(step, f"Vertex B déplacé vers le point projeté: co_finale={_format_vec(vertex_b.co)}")

        step = "MERGE_A_TO_B"
        if not vertex_a.is_valid or not vertex_b.is_valid:
            raise RuntimeError(
                "Vertex invalide détecté avant la fusion "
                f"(A_valide={vertex_a.is_valid}, B_valide={vertex_b.is_valid})."
            )

        self.log(step, f"Fusion BMesh en cours: A(index={vertex_a.index}) -> B(index={vertex_b.index})")
        bmesh.ops.pointmerge(
            bm,
            verts=[vertex_a, vertex_b],
            merge_co=nearest_point.copy(),
        )
        self.log(step, "Fusion BMesh terminée.")

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
            ordered_verts = selected_verts[:]
            if active_vert and active_vert.select:
                ordered_verts = [active_vert] + [v for v in selected_verts if v != active_vert]

            step = "PROCESS_VERTICES"
            self.log(step, f"Traitement séquentiel de {len(ordered_verts)} vertex(s).")
            processed_count = 0
            for vertex_a in ordered_verts:
                if not vertex_a.is_valid:
                    self.log(step, "Vertex ignoré car invalide avant traitement.")
                    continue

                self.log(step, f"Traitement du vertex #{processed_count + 1}")
                self._merge_single_vertex(bm, vertex_a)
                processed_count += 1

            if processed_count == 0:
                self.log(step, "Erreur: aucun vertex valide à traiter.")
                self.report({'ERROR'}, "Aucun vertex valide à traiter.")
                return {'CANCELLED'}

            # IMPORTANT: la topologie est modifiée (subdivide + merge),
            # il faut donc forcer une mise à jour destructive pour éviter
            # des caches de dessin incohérents côté Blender.
            bm.normal_update()
            bmesh.update_edit_mesh(obj.data, loop_triangles=True, destructive=True)
            self.log(step, f"Fusion BMesh terminée pour {processed_count} vertex(s).")

            step = "DONE"
            self.log(step, "Opération terminée avec succès.")
            self.report({'INFO'}, f"{processed_count} vertex(s) fusionné(s) vers leur edge la plus proche.")
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
