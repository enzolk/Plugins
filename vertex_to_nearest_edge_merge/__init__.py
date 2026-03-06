bl_info = {
    "name": "Merge Selected Vertex to Nearest Non-Connected Edge",
    "author": "Codex",
    "version": (1, 0, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Edit",
    "description": "Find nearest non-connected edge from selected vertex, create point on edge, and merge to it",
    "category": "Mesh",
}

from .vertex_to_nearest_edge_merge import register, unregister

__all__ = ("register", "unregister")
