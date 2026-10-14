"""Rick's keyboard shortcut: which combinations the settings window accepts,
how they're written for the `keyboard` library ("ctrl+shift+f9") and how
they're shown to the player ("Ctrl+Shift+F9").

Plain functions with no Tk and no `keyboard` import, so the settings window,
the config and the tests all share one set of rules.
"""

import string

DEFAULT = "alt+r"

# Always saved in this order, so one combination is always written one way.
MODIFIERS = ("ctrl", "alt", "shift")
_MODIFIER_ALIASES = {"control": "ctrl"}

_FUNCTION_KEYS = tuple(f"f{n}" for n in range(1, 13))
KEYS = frozenset(string.ascii_lowercase) | frozenset(string.digits) | frozenset(_FUNCTION_KEYS)

# Shortcuts people press all the time while using the PC: as Rick's
# shortcut they'd keep starting him by accident (Rick doesn't swallow the
# keys, so the program in focus still gets them too).
_RESERVED = frozenset({"alt+f4", "ctrl+a", "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+y", "ctrl+z"})


class HotkeyError(ValueError):
    """A combination Rick won't use. `reason` says why, for the settings
    window: "key" (not a letter, a number or F1-F12), "modifier" (a letter
    or number alone, or with just Shift: it would fire while typing or
    playing) or "reserved" (an everyday shortcut, see _RESERVED)."""

    def __init__(self, reason: str, text: str = ""):
        super().__init__(f"{reason}: {text!r}")
        self.reason = reason


def build(modifiers, key: str) -> str:
    """The combination of `modifiers` (any of "ctrl", "alt", "shift") plus
    one `key`, in keyboard's syntax. Raises HotkeyError if Rick shouldn't
    use it."""
    key = key.strip().lower()
    if key not in KEYS:
        raise HotkeyError("key", key)
    chosen = set()
    for modifier in modifiers:
        modifier = modifier.strip().lower()
        modifier = _MODIFIER_ALIASES.get(modifier, modifier)
        if modifier not in MODIFIERS:
            raise HotkeyError("key", modifier)
        chosen.add(modifier)
    # F1-F12 are fine alone; a letter or number needs Ctrl or Alt, or Rick
    # would start every time it's typed in a chat or pressed in a game.
    if key not in _FUNCTION_KEYS and not chosen & {"ctrl", "alt"}:
        raise HotkeyError("modifier", key)
    hotkey = "+".join([m for m in MODIFIERS if m in chosen] + [key])
    if hotkey in _RESERVED:
        raise HotkeyError("reserved", hotkey)
    return hotkey


def parse(text: str) -> str:
    """A saved or typed combination ("Alt + R", "ctrl+shift+F9") in the one
    form build() gives. Raises HotkeyError if it isn't one Rick accepts."""
    parts = [part.strip() for part in str(text).split("+")]
    if not all(parts):
        raise HotkeyError("key", text)
    *modifiers, key = parts
    if len(set(m.lower() for m in modifiers)) != len(modifiers):
        raise HotkeyError("key", text)  # "alt+alt+r": a typo, not a choice
    return build(modifiers, key)


def label(hotkey: str) -> str:
    """How a combination is shown to the player: "ctrl+shift+f9" becomes
    "Ctrl+Shift+F9". Also fine for any other name `keyboard` knows (set by
    hand in .env), e.g. "page up" -> "Page Up"."""
    return "+".join(_label_part(part.strip()) for part in hotkey.split("+"))


def _label_part(part: str) -> str:
    if len(part) == 1 or part in _FUNCTION_KEYS:
        return part.upper()
    return " ".join(word.capitalize() for word in part.split())


# --- reading the combination from the settings window's key events ----------
# Tk names the modifier keys themselves like this (left and right versions;
# X11 sometimes reports Alt as Meta).
_TK_MODIFIER_KEYS = {
    "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt", "Meta_L": "alt", "Meta_R": "alt",
    "Shift_L": "shift", "Shift_R": "shift",
}

# Modifier bits of a Tk event's `state`. Alt is a different bit on Windows;
# there 0x8 means Num Lock, so reading it as Alt would invent a modifier.
_STATE_SHIFT, _STATE_CTRL = 0x1, 0x4
_STATE_ALT = {True: 0x20000, False: 0x8}


def modifier_of(keysym: str) -> str | None:
    """"ctrl", "alt" or "shift" if the Tk key event is that modifier key."""
    return _TK_MODIFIER_KEYS.get(keysym)


def modifiers_in_state(state: int, windows: bool) -> set:
    """The modifiers a Tk key event says are held down."""
    held = set()
    if state & _STATE_SHIFT:
        held.add("shift")
    if state & _STATE_CTRL:
        held.add("ctrl")
    if state & _STATE_ALT[windows]:
        held.add("alt")
    return held


def key_of(keysym: str, keycode: int, windows: bool) -> str | None:
    """The key a Tk key event stands for, if it's one Rick can use (see
    KEYS), else None.

    On Windows Tk's keycode is the Windows virtual-key code, which stays the
    same whatever Shift does to the character (Shift+1 on an Italian
    keyboard is keysym "exclam", but still the "1" key)."""
    if windows:
        if 0x30 <= keycode <= 0x39 or 0x41 <= keycode <= 0x5A:  # 0-9, A-Z
            return chr(keycode).lower()
        if 0x70 <= keycode <= 0x7B:  # F1-F12
            return f"f{keycode - 0x6F}"
    name = keysym.lower()
    return name if name in KEYS else None
