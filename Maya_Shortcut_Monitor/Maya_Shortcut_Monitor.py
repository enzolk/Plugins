# -*- coding: utf-8 -*-
"""
Maya Shortcut Logger - possible actions only

But :
- écouter les touches clavier / combinaisons
- normaliser correctement la touche (évite Ctrl+\\r pour Ctrl+M)
- logger uniquement les actions POSSIBLES associées au shortcut
- ne PAS logger l'action observée / le contexte courant
- sauvegarder dans un JSON

Compatible Maya PySide2 / PySide6
"""

import os
import json
import time
import traceback

import maya.cmds as cmds
import maya.OpenMayaUI as omui

try:
    from PySide6 import QtCore, QtWidgets, QtGui
    from shiboken6 import wrapInstance
    QT_API = "PySide6"
except ImportError:
    from PySide2 import QtCore, QtWidgets, QtGui
    from shiboken2 import wrapInstance
    QT_API = "PySide2"


# =========================================================
# CONFIG
# =========================================================

LOG_FILE = os.path.join(cmds.internalVar(userAppDir=True), "shortcut_possible_actions_log.json")
PRINT_IN_SCRIPT_EDITOR = True
DEDUP_WINDOW_SECONDS = 0.12


# =========================================================
# QT / MAYA HELPERS
# =========================================================

def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    if ptr is None:
        return None
    return wrapInstance(int(ptr), QtWidgets.QWidget)


def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_log(data):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def safe_str(value):
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return repr(value)


# =========================================================
# KEY NORMALIZATION
# =========================================================

def qt_key_to_maya_key(event):
    """
    Convertit une touche Qt vers une représentation exploitable avec maya.cmds.hotkey().
    Important :
    - si Ctrl/Alt/Meta est actif, NE PAS utiliser event.text()
    - cela évite par ex. Ctrl+M => "\\r"
    """
    key = event.key()
    mods = event.modifiers()

    special_map = {
        QtCore.Qt.Key_Return: "Return",
        QtCore.Qt.Key_Enter: "Return",
        QtCore.Qt.Key_Escape: "Esc",
        QtCore.Qt.Key_Backspace: "Backspace",
        QtCore.Qt.Key_Delete: "Delete",
        QtCore.Qt.Key_Space: "Space",
        QtCore.Qt.Key_Tab: "Tab",
        QtCore.Qt.Key_Home: "Home",
        QtCore.Qt.Key_End: "End",
        QtCore.Qt.Key_PageUp: "Page_Up",
        QtCore.Qt.Key_PageDown: "Page_Down",
        QtCore.Qt.Key_Left: "Left",
        QtCore.Qt.Key_Right: "Right",
        QtCore.Qt.Key_Up: "Up",
        QtCore.Qt.Key_Down: "Down",
        QtCore.Qt.Key_Insert: "Insert",
        QtCore.Qt.Key_F1: "F1",
        QtCore.Qt.Key_F2: "F2",
        QtCore.Qt.Key_F3: "F3",
        QtCore.Qt.Key_F4: "F4",
        QtCore.Qt.Key_F5: "F5",
        QtCore.Qt.Key_F6: "F6",
        QtCore.Qt.Key_F7: "F7",
        QtCore.Qt.Key_F8: "F8",
        QtCore.Qt.Key_F9: "F9",
        QtCore.Qt.Key_F10: "F10",
        QtCore.Qt.Key_F11: "F11",
        QtCore.Qt.Key_F12: "F12",
        QtCore.Qt.Key_Minus: "-",
        QtCore.Qt.Key_Equal: "=",
        QtCore.Qt.Key_Slash: "/",
        QtCore.Qt.Key_Backslash: "\\",
        QtCore.Qt.Key_BracketLeft: "[",
        QtCore.Qt.Key_BracketRight: "]",
        QtCore.Qt.Key_Semicolon: ";",
        QtCore.Qt.Key_Apostrophe: "'",
        QtCore.Qt.Key_Comma: ",",
        QtCore.Qt.Key_Period: ".",
        QtCore.Qt.Key_QuoteLeft: "`",
    }

    if key in special_map:
        return special_map[key]

    # Si modificateur actif, on se base sur key(), jamais sur event.text()
    if mods & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier | QtCore.Qt.MetaModifier):
        if QtCore.Qt.Key_A <= key <= QtCore.Qt.Key_Z:
            return chr(key).lower()
        if QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9:
            return chr(key)
        seq = QtGui.QKeySequence(key).toString()
        return safe_str(seq)

    text = event.text()
    if text and len(text) == 1 and text.isprintable():
        return text.lower()

    if QtCore.Qt.Key_A <= key <= QtCore.Qt.Key_Z:
        return chr(key).lower()

    if QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9:
        return chr(key)

    seq = QtGui.QKeySequence(key).toString()
    return safe_str(seq)


def build_shortcut_label(maya_key, ctrl=False, alt=False, shift=False):
    parts = []
    if ctrl:
        parts.append("Ctrl")
    if alt:
        parts.append("Alt")
    if shift:
        parts.append("Shift")
    parts.append(maya_key)
    return "+".join(parts)


# =========================================================
# MAYA HOTKEY RESOLUTION
# =========================================================

def get_current_hotkey_set():
    try:
        return cmds.hotkeySet(q=True, current=True) or ""
    except Exception:
        return ""


def query_hotkey_name_command(maya_key, ctrl=False, alt=False, shift=False, release=False):
    """
    Résolution directe du raccourci via maya.cmds.hotkey().
    """
    try:
        kwargs = {
            "keyShortcut": maya_key,
            "ctrlModifier": ctrl,
            "altModifier": alt,
            "shiftModifier": shift,
            "query": True,
        }
        if release:
            kwargs["releaseName"] = True
        else:
            kwargs["name"] = True

        result = cmds.hotkey(**kwargs)
        return safe_str(result)
    except Exception:
        return ""


def list_hotkey_context_types():
    """
    Liste des types de contextes hotkey connus via hotkeyCtx(typeArray=True, q=True).
    """
    try:
        result = cmds.hotkeyCtx(typeArray=True, query=True)
        if not result:
            return []
        return [safe_str(x) for x in result]
    except Exception:
        return []


def get_assign_command_count():
    """
    assignCommand manipule un tableau 1-based d'objets de commandes nommées.
    On tente plusieurs flags selon compatibilité/version.
    """
    candidates = [
        {"numElements": True},
        {"numberOfElements": True},
        {"numElements": 1},      # sécurité si certaines versions attendent une valeur
        {"numberOfElements": 1}, # sécurité si certaines versions attendent une valeur
    ]

    for extra in candidates:
        try:
            kwargs = {"query": True}
            kwargs.update(extra)
            result = cmds.assignCommand(**kwargs)
            if isinstance(result, int):
                return result
            if isinstance(result, str) and result.isdigit():
                return int(result)
        except Exception:
            continue

    # fallback progressif
    max_try = 4000
    last_valid = 0
    for i in range(1, max_try + 1):
        try:
            test = cmds.assignCommand(i, query=True, keyString=True)
            # si la requête ne plante pas, l'index existe
            last_valid = i
        except Exception:
            # on continue un peu au cas où il y ait des trous, puis on stoppe
            if i > last_valid + 50:
                break
    return last_valid


def query_assign_command_field(index, **field_flag):
    try:
        kwargs = {"query": True}
        kwargs.update(field_flag)
        return cmds.assignCommand(index, **kwargs)
    except Exception:
        return None


def normalize_key_string_for_compare(key_string):
    """
    Normalisation légère pour comparer les keyString venant d'assignCommand
    avec la touche détectée.
    """
    s = safe_str(key_string).strip()
    if not s:
        return ""

    replacements = {
        "return": "Return",
        "enter": "Return",
        "esc": "Esc",
        "escape": "Esc",
        "space": "Space",
        "pageup": "Page_Up",
        "pagedown": "Page_Down",
    }

    low = s.lower()
    if low in replacements:
        return replacements[low]

    if len(s) == 1:
        return s.lower()

    return s


def collect_assign_command_matches(maya_key, ctrl=False, alt=False, shift=False, release=False):
    """
    Scanne les assignCommand pour retrouver toutes les commandes possibles associées
    au raccourci détecté.

    Selon les versions de Maya, tous les flags ne sont pas toujours exposés pareil.
    On fait donc un scan tolérant.
    """
    results = []
    count = get_assign_command_count()
    norm_key = normalize_key_string_for_compare(maya_key)

    for i in range(1, count + 1):
        try:
            key_string = query_assign_command_field(i, keyString=True)
            if key_string is None:
                continue

            key_string_norm = normalize_key_string_for_compare(key_string)
            if key_string_norm != norm_key:
                continue

            # Ces flags peuvent varier selon versions / commandes.
            # On lit ce qui est disponible sans casser le script.
            ctrl_flag = query_assign_command_field(i, ctrlModifier=True)
            alt_flag = query_assign_command_field(i, altModifier=True)
            shift_flag = query_assign_command_field(i, shiftModifier=True)
            key_up_flag = query_assign_command_field(i, keyUp=True)

            # Si info dispo, on filtre.
            if ctrl_flag is not None and bool(ctrl_flag) != bool(ctrl):
                continue
            if alt_flag is not None and bool(alt_flag) != bool(alt):
                continue
            if shift_flag is not None and bool(shift_flag) != bool(shift):
                continue
            if key_up_flag is not None and bool(key_up_flag) != bool(release):
                continue

            name = query_assign_command_field(i, name=True)
            annotation = query_assign_command_field(i, annotation=True)
            command = query_assign_command_field(i, command=True)
            data1 = query_assign_command_field(i, data1=True)
            data2 = query_assign_command_field(i, data2=True)
            data3 = query_assign_command_field(i, data3=True)

            item = {
                "source": "assignCommand",
                "index": i,
                "keyString": safe_str(key_string),
                "nameCommand": safe_str(name),
                "annotation": safe_str(annotation),
                "command": safe_str(command),
                "data1": safe_str(data1),
                "data2": safe_str(data2),
                "data3": safe_str(data3),
                "press_type": "release" if release else "press",
                "mods": {
                    "ctrl": bool(ctrl),
                    "alt": bool(alt),
                    "shift": bool(shift),
                }
            }
            results.append(item)

        except Exception:
            continue

    return results


def build_direct_hotkey_action(maya_key, ctrl=False, alt=False, shift=False, release=False):
    """
    Action directe résolue par maya.cmds.hotkey().
    """
    name_cmd = query_hotkey_name_command(
        maya_key=maya_key,
        ctrl=ctrl,
        alt=alt,
        shift=shift,
        release=release
    )

    if not name_cmd:
        return None

    return {
        "source": "hotkey",
        "keyString": maya_key,
        "nameCommand": safe_str(name_cmd),
        "annotation": "",
        "command": "",
        "press_type": "release" if release else "press",
        "mods": {
            "ctrl": bool(ctrl),
            "alt": bool(alt),
            "shift": bool(shift),
        }
    }


def dedupe_possible_actions(actions):
    seen = set()
    cleaned = []

    for a in actions:
        sig = (
            safe_str(a.get("source")),
            safe_str(a.get("keyString")),
            safe_str(a.get("nameCommand")),
            safe_str(a.get("annotation")),
            safe_str(a.get("command")),
            safe_str(a.get("press_type")),
            bool(a.get("mods", {}).get("ctrl")),
            bool(a.get("mods", {}).get("alt")),
            bool(a.get("mods", {}).get("shift")),
        )
        if sig in seen:
            continue
        seen.add(sig)
        cleaned.append(a)

    return cleaned


def resolve_possible_actions(maya_key, ctrl=False, alt=False, shift=False, release=False):
    """
    Retourne uniquement les actions possibles associées au shortcut.
    """
    actions = []

    direct_action = build_direct_hotkey_action(
        maya_key=maya_key,
        ctrl=ctrl,
        alt=alt,
        shift=shift,
        release=release
    )
    if direct_action:
        actions.append(direct_action)

    actions.extend(
        collect_assign_command_matches(
            maya_key=maya_key,
            ctrl=ctrl,
            alt=alt,
            shift=shift,
            release=release
        )
    )

    return dedupe_possible_actions(actions)


# =========================================================
# LOGGER
# =========================================================

class MayaShortcutPossibleActionsLogger(QtCore.QObject):
    def __init__(self, parent=None):
        super(MayaShortcutPossibleActionsLogger, self).__init__(parent)
        self.log_data = load_log()
        self.last_emit = {}

    def should_skip_event(self, shortcut_label, press_type):
        now = time.time()
        key = (shortcut_label, press_type)
        last_time = self.last_emit.get(key, 0.0)
        if (now - last_time) < DEDUP_WINDOW_SECONDS:
            return True
        self.last_emit[key] = now
        return False

    def eventFilter(self, obj, event):
        try:
            if event.type() not in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
                return False

            if event.isAutoRepeat():
                return False

            if event.key() in (
                QtCore.Qt.Key_Control,
                QtCore.Qt.Key_Shift,
                QtCore.Qt.Key_Alt,
                QtCore.Qt.Key_Meta
            ):
                return False

            mods = event.modifiers()
            ctrl = bool(mods & QtCore.Qt.ControlModifier)
            alt = bool(mods & QtCore.Qt.AltModifier)
            shift = bool(mods & QtCore.Qt.ShiftModifier)

            maya_key = qt_key_to_maya_key(event)
            if not maya_key:
                return False

            press_type = "press" if event.type() == QtCore.QEvent.KeyPress else "release"
            shortcut_label = build_shortcut_label(maya_key, ctrl=ctrl, alt=alt, shift=shift)

            if self.should_skip_event(shortcut_label, press_type):
                return False

            possible_actions = resolve_possible_actions(
                maya_key=maya_key,
                ctrl=ctrl,
                alt=alt,
                shift=shift,
                release=(press_type == "release")
            )

            entry = {
                "timestamp": time.time(),
                "qt_api": QT_API,
                "shortcut": shortcut_label,
                "maya_key": maya_key,
                "mods": {
                    "ctrl": ctrl,
                    "alt": alt,
                    "shift": shift
                },
                "press_type": press_type,
                "current_hotkey_set": get_current_hotkey_set(),
                "known_hotkey_context_types": list_hotkey_context_types(),
                "possible_actions": possible_actions
            }

            self.log_data.append(entry)
            save_log(self.log_data)

            if PRINT_IN_SCRIPT_EDITOR:
                print("[ShortcutPossibleActions] {}".format(
                    json.dumps(entry, ensure_ascii=False)
                ))

        except Exception:
            print("[ShortcutPossibleActions][ERROR]")
            traceback.print_exc()

        return False


# =========================================================
# INSTALL / UNINSTALL
# =========================================================

_SHORTCUT_POSSIBLE_ACTIONS_LOGGER = None


def install_shortcut_possible_actions_logger():
    global _SHORTCUT_POSSIBLE_ACTIONS_LOGGER

    app = QtWidgets.QApplication.instance()
    if app is None:
        cmds.warning("QApplication introuvable.")
        return

    if _SHORTCUT_POSSIBLE_ACTIONS_LOGGER is not None:
        cmds.warning("Le logger est déjà installé.")
        return

    _SHORTCUT_POSSIBLE_ACTIONS_LOGGER = MayaShortcutPossibleActionsLogger(parent=maya_main_window())
    app.installEventFilter(_SHORTCUT_POSSIBLE_ACTIONS_LOGGER)

    print("Shortcut Possible Actions Logger installé.")
    print("Qt API :", QT_API)
    print("Log file :", LOG_FILE)


def uninstall_shortcut_possible_actions_logger():
    global _SHORTCUT_POSSIBLE_ACTIONS_LOGGER

    app = QtWidgets.QApplication.instance()
    if app is None:
        cmds.warning("QApplication introuvable.")
        return

    if _SHORTCUT_POSSIBLE_ACTIONS_LOGGER is None:
        cmds.warning("Aucun logger installé.")
        return

    app.removeEventFilter(_SHORTCUT_POSSIBLE_ACTIONS_LOGGER)
    _SHORTCUT_POSSIBLE_ACTIONS_LOGGER.deleteLater()
    _SHORTCUT_POSSIBLE_ACTIONS_LOGGER = None

    print("Shortcut Possible Actions Logger désinstallé.")


def open_shortcut_possible_actions_log():
    if os.path.exists(LOG_FILE):
        print("Log file:", LOG_FILE)
    else:
        cmds.warning("Aucun fichier log trouvé.")


# =========================================================
# AUTO START
# =========================================================

install_shortcut_possible_actions_logger()