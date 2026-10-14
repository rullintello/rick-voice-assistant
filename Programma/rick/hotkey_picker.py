"""The "keys to talk to Rick" control, shared by the settings window
(rick/setup_gui.py) and the "Keys" button of Rick's own window (gui.py): a
box showing the keys, a Change button and a hint line under them.

After Change, the next combination pressed while the box has the keyboard
focus becomes the new keys, if rick/hotkeys.py accepts it; otherwise the
hint says why and it keeps waiting. Esc, or clicking elsewhere, cancels.
"""

import sys
import tkinter as tk

from . import hotkeys

_WINDOWS = sys.platform == "win32"
NOTE_COLOR = "#555555"
_ERROR_COLOR = "red"
_WAITING_COLOR = "#fff4c2"  # the keys box while it's waiting for new keys

STRINGS = {
    "it": {
        "label": "Tasti per parlare con Rick:",
        "change": "Cambia",
        "waiting": "Premi i nuovi tasti...",
        "note": "Scegli tasti che il tuo gioco non usa.",
        "capturing": "Premi la combinazione che vuoi, oppure Esc per annullare.",
        "error_key": "Usa una lettera, un numero o un tasto da F1 a F12.",
        "error_modifier": "Con una lettera o un numero tieni premuto anche Ctrl o Alt.",
        "error_reserved": "Questa combinazione la usano gia' Windows o i programmi: scegline un'altra.",
        "locked": "Decisi dal file .env (RICK_HOTKEY): per cambiarli modifica quel file.",
    },
    "en": {
        "label": "Keys to talk to Rick:",
        "change": "Change",
        "waiting": "Press the new keys...",
        "note": "Pick keys your game doesn't use.",
        "capturing": "Press the combination you want, or Esc to cancel.",
        "error_key": "Use a letter, a number or a key from F1 to F12.",
        "error_modifier": "With a letter or a number, also hold Ctrl or Alt.",
        "error_reserved": "Windows or other programs already use this one: pick another.",
        "locked": "Set by the .env file (RICK_HOTKEY): edit that file to change them.",
    },
}


class HotkeyPicker:
    """Builds the control inside `parent` (pack self.frame to show it).
    `hotkey` is the starting combination in keyboard's syntax; `locked`
    (RICK_HOTKEY set in .env) shows it without allowing changes.
    `on_picked(hotkey)` runs after each accepted combination."""

    def __init__(self, parent, language: str, hotkey: str, locked: bool = False, on_picked=None):
        self.hotkey = hotkey or hotkeys.DEFAULT
        self.locked = locked
        self._on_picked = on_picked
        self._strings = STRINGS[language if language in STRINGS else "it"]
        self._capturing = False
        self._held: set = set()

        self.frame = tk.Frame(parent)
        self._title = tk.Label(self.frame, font=("Segoe UI", 11), justify="center")
        self._title.pack(pady=(4, 6))
        row = tk.Frame(self.frame)
        row.pack()
        self.box = tk.Label(row, font=("Segoe UI", 11, "bold"), width=22, relief="groove", padx=8, pady=4)
        self.box.pack(side="left", padx=(0, 8))
        self._idle_color = self.box.cget("bg")
        self.button = tk.Button(row, font=("Segoe UI", 10), padx=10, command=self.start)
        self.button.pack(side="left")
        if locked:
            self.button.config(state="disabled")
        self.hint = tk.Label(self.frame, font=("Segoe UI", 9), fg=NOTE_COLOR, justify="center")
        self.hint.pack(pady=(4, 0))

        # The box reads the keys while it has the focus (start() gives it),
        # so nothing gets typed into the window's other fields meanwhile.
        self.box.bind("<KeyPress>", self.key_pressed)
        self.box.bind("<KeyRelease>", self.key_released)
        self.box.bind("<FocusOut>", lambda _event: self.cancel())
        self.set_language(language)

    @property
    def capturing(self) -> bool:
        return self._capturing

    def set_language(self, language: str) -> None:
        self._strings = STRINGS[language if language in STRINGS else "it"]
        self._title.config(text=self._strings["label"])
        self.button.config(text=self._strings["change"])
        if self._capturing:
            self._show_waiting()
        else:
            self._show_keys()

    def start(self) -> None:
        """Waits for the next combination pressed (the Change button)."""
        if self.locked:
            return
        self._capturing = True
        self._held.clear()
        self._show_waiting()
        self.box.focus_set()

    def cancel(self) -> None:
        """Stops waiting and keeps the keys as they were (Esc, focus lost)."""
        if self._capturing:
            self._capturing = False
            self._held.clear()
            self._show_keys()

    # --- key events (bound to the box; also called directly by tests) ------
    def key_pressed(self, event):
        if not self._capturing:
            return None
        if event.keysym == "Escape":
            self.cancel()
            return "break"
        modifier = hotkeys.modifier_of(event.keysym)
        if modifier:
            self._held.add(modifier)
            return "break"
        key = hotkeys.key_of(event.keysym, event.keycode, _WINDOWS)
        held = self._held | hotkeys.modifiers_in_state(event.state, _WINDOWS)
        try:
            if key is None:
                raise hotkeys.HotkeyError("key", event.keysym)
            picked = hotkeys.build(held, key)
        except hotkeys.HotkeyError as exc:
            # keeps waiting: the hint says what to press instead
            self.hint.config(text=self._strings[f"error_{exc.reason}"], fg=_ERROR_COLOR)
            return "break"
        self.hotkey = picked
        self._capturing = False
        self._held.clear()
        self._show_keys()
        if self._on_picked:
            self._on_picked(picked)
        return "break"

    def key_released(self, event):
        modifier = hotkeys.modifier_of(event.keysym)
        if modifier:
            self._held.discard(modifier)
        return "break" if self._capturing else None

    # --- what's shown --------------------------------------------------------
    def _show_keys(self) -> None:
        self.box.config(text=hotkeys.label(self.hotkey), bg=self._idle_color)
        self.hint.config(text=self._strings["locked" if self.locked else "note"], fg=NOTE_COLOR)

    def _show_waiting(self) -> None:
        self.box.config(text=self._strings["waiting"], bg=_WAITING_COLOR)
        self.hint.config(text=self._strings["capturing"], fg=NOTE_COLOR)
