"""Rick's shortcut (rick/hotkeys.py and its settings in rick/config.py):
which keys the settings window accepts, how they're saved and shown, and
which setting wins."""

import json
import os
import unittest

from rick import config, hotkeys
from rick.hotkeys import HotkeyError

from support import isolate_rick_home


class BuildTest(unittest.TestCase):
    def assertRejected(self, reason, modifiers, key):
        with self.assertRaises(HotkeyError) as raised:
            hotkeys.build(modifiers, key)
        self.assertEqual(raised.exception.reason, reason)

    def test_letters_and_numbers_need_ctrl_or_alt(self):
        self.assertEqual(hotkeys.build({"alt"}, "r"), "alt+r")
        self.assertEqual(hotkeys.build({"ctrl"}, "7"), "ctrl+7")
        self.assertEqual(hotkeys.build({"shift", "alt"}, "R"), "alt+shift+r")
        # alone, or with just Shift, they'd fire while typing or playing
        self.assertRejected("modifier", set(), "r")
        self.assertRejected("modifier", {"shift"}, "r")
        self.assertRejected("modifier", set(), "7")

    def test_function_keys_work_alone_too(self):
        self.assertEqual(hotkeys.build(set(), "F9"), "f9")
        self.assertEqual(hotkeys.build({"shift"}, "f12"), "shift+f12")
        self.assertEqual(hotkeys.build({"ctrl", "alt"}, "f1"), "ctrl+alt+f1")

    def test_only_letters_numbers_and_f1_to_f12(self):
        for key in ("space", "tab", "enter", "escape", "f13", "ò", "kp_1", ""):
            self.assertRejected("key", {"ctrl"}, key)
        self.assertRejected("key", {"windows"}, "r")

    def test_everyday_shortcuts_are_refused(self):
        for modifiers, key in (({"ctrl"}, "c"), ({"ctrl"}, "v"), ({"ctrl"}, "z"), ({"alt"}, "f4")):
            self.assertRejected("reserved", modifiers, key)
        self.assertEqual(hotkeys.build({"ctrl", "shift"}, "c"), "ctrl+shift+c")  # not an everyday one

    def test_one_combination_is_always_written_one_way(self):
        self.assertEqual(hotkeys.build(["shift", "alt", "ctrl"], "X"), "ctrl+alt+shift+x")
        self.assertEqual(hotkeys.build(["Control"], "k"), "ctrl+k")


class ParseTest(unittest.TestCase):
    def test_normalizes_what_people_type(self):
        self.assertEqual(hotkeys.parse("Alt + R"), "alt+r")
        self.assertEqual(hotkeys.parse("SHIFT+ctrl+F9"), "ctrl+shift+f9")

    def test_refuses_what_build_refuses_and_typos(self):
        for text in ("", "alt+", "+r", "alt+alt+r", "r", "ctrl+c", "ctrl+space", "alt+r+t"):
            with self.subTest(text=text), self.assertRaises(HotkeyError):
                hotkeys.parse(text)

    def test_every_valid_combination_survives_a_save_and_reload(self):
        for modifiers in (["alt"], ["ctrl"], ["ctrl", "shift"], ["ctrl", "alt", "shift"]):
            for key in sorted(hotkeys.KEYS):
                try:
                    hotkey = hotkeys.build(modifiers, key)
                except HotkeyError:
                    continue  # the reserved ones
                self.assertEqual(hotkeys.parse(hotkey), hotkey)
                self.assertEqual(hotkeys.parse(hotkeys.label(hotkey)), hotkey)


class LabelTest(unittest.TestCase):
    def test_how_the_keys_are_shown(self):
        self.assertEqual(hotkeys.label("alt+r"), "Alt+R")
        self.assertEqual(hotkeys.label("ctrl+shift+f9"), "Ctrl+Shift+F9")
        self.assertEqual(hotkeys.label("ctrl+alt+7"), "Ctrl+Alt+7")
        self.assertEqual(hotkeys.label("page up"), "Page Up")  # any name typed in .env


class TkEventTest(unittest.TestCase):
    """The pieces the settings window reads off Tk's key events."""

    def test_modifier_keys(self):
        self.assertEqual(hotkeys.modifier_of("Control_R"), "ctrl")
        self.assertEqual(hotkeys.modifier_of("Alt_L"), "alt")
        self.assertEqual(hotkeys.modifier_of("Shift_L"), "shift")
        self.assertIsNone(hotkeys.modifier_of("r"))

    def test_modifiers_in_state(self):
        self.assertEqual(hotkeys.modifiers_in_state(0x1 | 0x4, windows=False), {"shift", "ctrl"})
        self.assertEqual(hotkeys.modifiers_in_state(0x8, windows=False), {"alt"})
        self.assertEqual(hotkeys.modifiers_in_state(0x20000, windows=True), {"alt"})
        # on Windows 0x8 is Num Lock: reading it as Alt would invent a modifier
        self.assertEqual(hotkeys.modifiers_in_state(0x8, windows=True), set())

    def test_keys_on_windows_come_from_the_key_not_the_character(self):
        self.assertEqual(hotkeys.key_of("exclam", 0x31, windows=True), "1")  # Shift+1, Italian layout
        self.assertEqual(hotkeys.key_of("R", 0x52, windows=True), "r")
        self.assertEqual(hotkeys.key_of("F9", 0x78, windows=True), "f9")
        self.assertIsNone(hotkeys.key_of("space", 0x20, windows=True))

    def test_keys_elsewhere_come_from_the_keysym(self):
        self.assertEqual(hotkeys.key_of("R", 27, windows=False), "r")
        self.assertEqual(hotkeys.key_of("F11", 95, windows=False), "f11")
        self.assertIsNone(hotkeys.key_of("exclam", 10, windows=False))


class ConfigTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)

    def test_alt_r_until_something_is_picked(self):
        self.assertEqual(config.get_hotkey(), "alt+r")
        self.assertFalse(config.hotkey_set_in_env())

    def test_picked_keys_are_saved_in_one_form(self):
        config.save_hotkey("Shift + Ctrl + F9")
        self.assertEqual(config.get_hotkey(), "ctrl+shift+f9")
        self.assertEqual(json.loads(config.USER_CONFIG_FILE.read_text())["hotkey"], "ctrl+shift+f9")

    def test_saving_refused_keys_writes_nothing(self):
        with self.assertRaises(HotkeyError):
            config.save_hotkey("ctrl+c")
        self.assertFalse(config.USER_CONFIG_FILE.exists())

    def test_env_wins_over_the_settings_window(self):
        config.save_hotkey("ctrl+shift+f9")
        os.environ["RICK_HOTKEY"] = "Ctrl+Shift+R"  # restored by isolate_rick_home
        self.assertTrue(config.hotkey_set_in_env())
        self.assertEqual(config.get_hotkey(), "ctrl+shift+r")

    def test_env_can_still_name_any_key_keyboard_knows(self):
        os.environ["RICK_HOTKEY"] = "Page Up"
        self.assertEqual(config.get_hotkey(), "page up")

    def test_a_broken_saved_value_falls_back_to_alt_r(self):
        for broken in ("r", "ctrl+c", 5, ["alt", "r"]):
            with self.subTest(broken=broken):
                config.USER_CONFIG_FILE.write_text(json.dumps({"hotkey": broken}))
                with self.assertLogs("rick.config", "WARNING"):
                    self.assertEqual(config.get_hotkey(), "alt+r")


if __name__ == "__main__":
    unittest.main()
