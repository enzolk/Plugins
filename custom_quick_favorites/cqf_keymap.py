import bpy

addon_keymaps = []

def _addon_key():
    # root package name
    return __package__.split(".")[0] if __package__ else __name__

def _get_prefs():
    try:
        return bpy.context.preferences.addons[_addon_key()].preferences
    except Exception:
        return None

def unregister_keymap():
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    addon_keymaps.clear()

def register_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    prefs = _get_prefs()
    use_plain_q = bool(getattr(prefs, "use_q_instead_of_shift_q", False)) if prefs else False

    km = kc.keymaps.new(name="Window", space_type='EMPTY')

    # If user wants to override native Quick Favorites Q:
    # - use_plain_q=True  -> Q
    # - use_plain_q=False -> Shift+Q (default)
    kmi = km.keymap_items.new(
        "cqf.open_menu",
        type='Q',
        value='PRESS',
        shift=(not use_plain_q),
        ctrl=False,
        alt=False,
        oskey=False,
    )

    addon_keymaps.append((km, kmi))

def refresh_keymap():
    # Safe refresh when user toggles the preference
    try:
        unregister_keymap()
    except Exception:
        pass
    try:
        register_keymap()
    except Exception:
        pass