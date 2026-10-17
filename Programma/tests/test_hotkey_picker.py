"""The "keys to talk to Rick" control (rick/hotkey_picker.py), shared by the
settings window and the "Keys" button of Rick's window.

Keys are fed straight to the picker's handlers, the way Tk calls them,
instead of through the operating system: a test machine may not give a
window the keyboard focus (a Windows CI runner hung waiting for it), and
what's being tested is what happens to the keys, not Tk's focus handling.
"""

import tkinter as tk
import types
import unittest

from rick import hotkey_picker
from rick.hotkey_picker import HotkeyPicker

from support import free_tk_after_test, require_display

IT = hotkey_picker.STRINGS["it"]
EN = hotkey_picker.STRINGS["en"]


def press(picker, *keysyms, state=0):
    """Each key down in order, then all of them up: a combination pressed
    the usual way. keycode 0 keeps Windows' virtual-key path out of it (it's
    covered in test_hotkeys.py), so this runs the same everywhere."""
    for keysym in keysyms:
        picker.key_pressed(types.SimpleNamespace(keysym=keysym, keycode=0, state=state))
    for keysym in reversed(keysyms):
        picker.key_released(types.SimpleNamespace(keysym=keysym, keycode=0, state=state))


class PickerTest(unittest.TestCase):
    def setUp(self):
        require_display(self)
        self.root = tk.Tk()
        free_tk_after_test(self, "root")
        self.addCleanup(self.root.destroy)
        self.picked = []

    def make(self, hotkey="alt+r", locked=False, language="it"):
        picker = HotkeyPicker(self.root, language, hotkey, locked=locked, on_picked=self.picked.append)
        picker.frame.pack()
        return picker

    def test_shows_the_keys_and_a_tip(self):
        picker = self.make("ctrl+shift+r")
        self.assertEqual(picker.box.cget("text"), "Ctrl+Shift+R")
        self.assertEqual(picker.hint.cget("text"), IT["note"])
        self.assertEqual(picker.button.cget("text"), IT["change"])
        self.assertFalse(picker.capturing)

    def test_change_waits_for_new_keys(self):
        picker = self.make()
        picker.button.invoke()
        self.assertTrue(picker.capturing)
        self.assertEqual(picker.box.cget("text"), IT["waiting"])
        self.assertEqual(picker.hint.cget("text"), IT["capturing"])
        self.assertNotEqual(picker.box.cget("bg"), picker._idle_color)  # highlighted

    def test_pressing_a_combination_picks_it(self):
        picker = self.make()
        picker.start()
        press(picker, "Control_L", "Shift_L", "F9")
        self.assertEqual(picker.hotkey, "ctrl+shift+f9")
        self.assertEqual(picker.box.cget("text"), "Ctrl+Shift+F9")
        self.assertEqual(self.picked, ["ctrl+shift+f9"])
        self.assertFalse(picker.capturing)
        self.assertEqual(picker.hint.cget("text"), IT["note"])
        self.assertEqual(picker.box.cget("bg"), picker._idle_color)

    def test_modifiers_already_held_count_too(self):
        # held before Change was pressed: no KeyPress seen for them, only
        # the state Tk reports with the key (0x4 = Ctrl on every system)
        picker = self.make()
        picker.start()
        press(picker, "k", state=0x4)
        self.assertEqual(picker.hotkey, "ctrl+k")

    def test_refused_combinations_say_why_and_keep_waiting(self):
        picker = self.make()
        picker.start()
        for keys, reason in ((("r",), "modifier"), (("Control_L", "c"), "reserved"), (("Alt_L", "space"), "key")):
            press(picker, *keys)
            self.assertEqual(picker.hint.cget("text"), IT[f"error_{reason}"], keys)
            self.assertTrue(picker.capturing)
            self.assertEqual(picker.hotkey, "alt+r")
        press(picker, "Alt_L", "k")
        self.assertEqual(self.picked, ["alt+k"])

    def test_a_released_modifier_no_longer_counts(self):
        picker = self.make()
        picker.start()
        press(picker, "Control_L")  # pressed and let go
        press(picker, "k")
        self.assertEqual(picker.hint.cget("text"), IT["error_modifier"])
        self.assertTrue(picker.capturing)

    def test_escape_keeps_the_old_keys(self):
        picker = self.make("ctrl+shift+r")
        picker.start()
        press(picker, "Escape")
        self.assertFalse(picker.capturing)
        self.assertEqual(picker.box.cget("text"), "Ctrl+Shift+R")
        press(picker, "Alt_L", "k")  # no longer listening
        self.assertEqual(picker.hotkey, "ctrl+shift+r")
        self.assertEqual(self.picked, [])

    def test_keys_are_ignored_unless_waiting(self):
        picker = self.make()
        self.assertIsNone(picker.key_pressed(types.SimpleNamespace(keysym="k", keycode=0, state=0x4)))
        self.assertEqual(picker.hotkey, "alt+r")

    def test_keys_reach_it_through_the_box_and_losing_focus_cancels(self):
        picker = self.make()
        for event in ("<KeyPress>", "<KeyRelease>", "<FocusOut>"):
            self.assertTrue(picker.box.bind(event), event)
        picker.start()
        picker.cancel()  # what <FocusOut> calls
        self.assertFalse(picker.capturing)
        self.assertEqual(picker.box.cget("text"), "Alt+R")

    def test_keys_set_in_env_are_shown_but_locked(self):
        picker = self.make("ctrl+shift+r", locked=True)
        self.assertEqual(picker.button.cget("state"), "disabled")
        self.assertEqual(picker.hint.cget("text"), IT["locked"])
        picker.start()
        self.assertFalse(picker.capturing)

    def test_switching_language(self):
        picker = self.make()
        picker.set_language("en")
        self.assertEqual(picker.hint.cget("text"), EN["note"])
        picker.start()
        picker.set_language("it")
        self.assertEqual(picker.box.cget("text"), IT["waiting"])
        self.assertEqual(picker.button.cget("text"), IT["change"])


if __name__ == "__main__":
    unittest.main()
