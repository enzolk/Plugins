bl_info = {
    "name": "Custom Quick Favorites (Shift+Q) - Per Mode / Sections / Config File",
    "author": "EnzoLK",
    "version": (1, 5, 0),
    "blender": (5, 0, 0),
    "location": "Right-click any UI element + Shift+Q",
    "description": "Custom Quick Favorites with fixed context modes, sections, editable items (text/tooltip), manual add (search/capture), and portable JSON config.",
    "category": "Interface",
}

from . import cqf_types
from . import cqf_multi_popup
from . import cqf_operators
from . import cqf_custom_script
from . import cqf_keymap

def register():
    cqf_types.register()
    cqf_multi_popup.register()
    cqf_operators.register()
    cqf_custom_script.register()
    cqf_keymap.register_keymap()

def unregister():
    cqf_keymap.unregister_keymap()
    cqf_custom_script.unregister()
    cqf_operators.unregister()
    cqf_multi_popup.unregister()
    cqf_types.unregister()