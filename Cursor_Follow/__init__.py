"""Blender add-on entrypoint for Cursor Follow."""

from .cursor_follow import bl_info, register, unregister

__all__ = ("bl_info", "register", "unregister")
