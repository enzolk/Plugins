"""Compatibility shim for the Blender Shortcut Logger add-on package.

Install and enable the `blender_shortcut_logger` folder as an add-on.
"""

from blender_shortcut_logger import register, unregister


if __name__ == "__main__":
    register()
