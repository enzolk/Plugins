bl_info = {
    "name": "Cursor Auto Attach (Vertex/Edge/Face) - Edit+Object + Manual Cursor Editing (Timer Safe)",
    "author": "ChatGPT",
    "version": (2, 1, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar (N) > Cursor",
    "description": "Auto-attach 3D Cursor to nearest mesh component. Cursor stays editable and compatible with other cursor tools (timer poll + depsgraph follow).",
    "category": "3D View",
}

from . import cursor_follow


def register():
    cursor_follow.register()


def unregister():
    cursor_follow.unregister()
