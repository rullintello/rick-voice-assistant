"""The first-run / Settings dialog (rick/setup_gui.py): API keys hidden
from anyone watching the screen, and still saved correctly; the keys that
start Rick, picked by pressing them."""

import tkinter as tk
import unittest
from unittest import mock

from rick import setup_gui

from support import require_display


def widgets(root, cls):
    found = []
    for child in root.winfo_children():
        if isinstance(child, cls):
            found.append(child)
        found += widgets(child, cls)
    return found


class DialogTestCase(unittest.TestCase):
    def setUp(self):
        require_display(self)

    def run_dialog(self, driver, **kwargs):
        """Runs the (blocking) dialog, with driver(root) inspecting and
        clicking through it from inside its own event loop."""
        real_tk = tk.Tk
        errors = []

        def make_root():
            root = real_tk()

            def drive():
                try:
                    driver(root)
                except BaseException as exc:  # noqa: BLE001 - re-raised below
                    errors.append(exc)
                    root.destroy()

            root.after(50, drive)
            return root

        with mock.patch.object(setup_gui.tk, "Tk", make_root):
            result = setup_gui.ask_for_api_keys(**kwargs)
        if errors:
            raise errors[0]
        return result

    def button(self, root, key):
        texts = {strings[key] for strings in setup_gui.DIALOG_STRINGS.values()}
        return next(b for b in widgets(root, tk.Button) if b.cget("text") in texts)

    def save(self, root):
        self.button(root, "save_button").invoke()


class SetupDialogTest(DialogTestCase):
    def test_keys_are_hidden_even_when_prefilled(self):
        seen = {}

        def driver(root):
            gemini, tavily = widgets(root, tk.Entry)
            seen["show"] = (gemini.cget("show"), tavily.cget("show"))
            seen["values"] = (gemini.get(), tavily.get())
            self.save(root)

        result = self.run_dialog(driver, prefill={"gemini": "gem-123", "tavily": "tvly-456", "language": "it"})
        self.assertEqual(seen["show"], (setup_gui._HIDDEN, setup_gui._HIDDEN))
        self.assertEqual(seen["values"], ("gem-123", "tvly-456"))  # still editable, just not readable
        self.assertEqual((result["gemini"], result["tavily"]), ("gem-123", "tvly-456"))

    def test_show_keys_toggles_visibility(self):
        seen = []

        def driver(root):
            (toggle,) = widgets(root, tk.Checkbutton)
            entries = widgets(root, tk.Entry)
            toggle.invoke()
            seen.append({e.cget("show") for e in entries})
            toggle.invoke()
            seen.append({e.cget("show") for e in entries})
            root.destroy()

        self.run_dialog(driver)
        self.assertEqual(seen, [{""}, {setup_gui._HIDDEN}])

    def test_typed_keys_are_returned(self):
        def driver(root):
            gemini, tavily = widgets(root, tk.Entry)
            gemini.insert(0, "  gem-typed  ")
            self.save(root)

        result = self.run_dialog(driver)
        self.assertEqual(result, {"gemini": "gem-typed", "tavily": "", "language": "it", "hotkey": "alt+r"})

    def test_privacy_note_in_both_languages(self):
        texts = {}

        def driver(root):
            labels = widgets(root, tk.Label)
            texts["it"] = " ".join(l.cget("text") for l in labels)
            it_button, en_button = widgets(root, tk.Radiobutton)
            en_button.invoke()
            texts["en"] = " ".join(l.cget("text") for l in labels)
            root.destroy()

        self.run_dialog(driver)
        self.assertIn("Google Gemini", texts["it"])
        self.assertIn("dati personali", texts["it"])
        self.assertIn("personal information", texts["en"])



class ShortcutPickerTest(DialogTestCase):
    """The "Change" button: press it, then the keys you want."""

    PREFILL = {"gemini": "gem-123", "language": "it"}

    HINTS = ("hotkey_note", "hotkey_capturing", "hotkey_locked",
             "hotkey_error_key", "hotkey_error_modifier", "hotkey_error_reserved")

    def keys_shown(self, root):
        """The text of the box showing the keys (the only framed label)."""
        return next(l for l in widgets(root, tk.Label) if l.cget("relief") == "groove").cget("text")

    def hint(self, root):
        hints = {strings[k] for strings in setup_gui.DIALOG_STRINGS.values() for k in self.HINTS}
        return next(l for l in widgets(root, tk.Label) if l.cget("text") in hints)

    def bring_to_front(self, root, widget=None):
        """Tk only delivers keys to a window that has the keyboard focus. A
        machine may refuse to hand it over (Windows can keep a background
        process from taking the foreground): then these tests can't press
        keys there, so they're skipped rather than reported as failures."""
        (widget or root).focus_force()
        root.update()
        if root.focus_get() is None:
            self.skipTest("this machine won't give the test window the keyboard focus")

    def press(self, root, *keysyms):
        """Presses (and keeps down) each key, then releases them all, in the
        widget that has the focus - as a player would."""
        target = root.focus_get()
        self.assertIsNotNone(target, "nothing is waiting for the keys")
        for keysym in keysyms:
            target.event_generate("<KeyPress>", keysym=keysym)
        for keysym in reversed(keysyms):
            target.event_generate("<KeyRelease>", keysym=keysym)
        root.update()

    def change(self, root):
        self.bring_to_front(root)  # as when the player clicks on the window
        self.button(root, "hotkey_change").invoke()
        root.update()

    def test_alt_r_is_shown_and_kept_by_default(self):
        seen = {}

        def driver(root):
            seen["keys"] = self.keys_shown(root)
            self.save(root)

        result = self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(seen["keys"], "Alt+R")
        self.assertEqual(result["hotkey"], "alt+r")

    def test_pressing_new_keys_picks_them(self):
        seen = {}

        def driver(root):
            self.change(root)
            seen["waiting"] = self.keys_shown(root)
            self.press(root, "Control_L", "Shift_L", "F9")
            seen["picked"] = self.keys_shown(root)
            self.save(root)

        result = self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(seen["waiting"], setup_gui.DIALOG_STRINGS["it"]["hotkey_waiting"])
        self.assertEqual(seen["picked"], "Ctrl+Shift+F9")
        self.assertEqual(result["hotkey"], "ctrl+shift+f9")

    def test_refused_keys_explain_why_and_keep_waiting(self):
        seen = {}
        strings = setup_gui.DIALOG_STRINGS["it"]

        def driver(root):
            self.change(root)
            self.press(root, "r")  # a bare letter: would fire while typing
            seen["no_modifier"] = self.hint(root).cget("text")
            self.press(root, "Control_L", "c")  # copy
            seen["reserved"] = self.hint(root).cget("text")
            self.press(root, "Alt_L", "space")
            seen["bad_key"] = self.hint(root).cget("text")
            seen["still_waiting"] = self.keys_shown(root)
            self.press(root, "Alt_L", "k")
            self.save(root)

        result = self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(seen["no_modifier"], strings["hotkey_error_modifier"])
        self.assertEqual(seen["reserved"], strings["hotkey_error_reserved"])
        self.assertEqual(seen["bad_key"], strings["hotkey_error_key"])
        self.assertEqual(seen["still_waiting"], strings["hotkey_waiting"])
        self.assertEqual(result["hotkey"], "alt+k")

    def test_escape_keeps_the_old_keys(self):
        seen = {}

        def driver(root):
            self.change(root)
            self.press(root, "Escape")
            seen["keys"] = self.keys_shown(root)
            self.press(root, "Alt_L", "k")  # no longer listening
            self.save(root)

        result = self.run_dialog(driver, prefill=dict(self.PREFILL, hotkey="ctrl+shift+r"))
        self.assertEqual(seen["keys"], "Ctrl+Shift+R")
        self.assertEqual(result["hotkey"], "ctrl+shift+r")

    def test_typing_in_the_key_fields_never_changes_the_shortcut(self):
        def driver(root):
            gemini, _tavily = widgets(root, tk.Entry)
            self.bring_to_front(root, gemini)
            self.press(root, "Alt_L", "k")
            self.save(root)

        result = self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(result["hotkey"], "alt+r")

    def test_keys_set_in_env_are_shown_but_locked(self):
        seen = {}

        def driver(root):
            seen["keys"] = self.keys_shown(root)
            seen["button"] = self.button(root, "hotkey_change").cget("state")
            seen["hint"] = self.hint(root).cget("text")
            self.save(root)

        result = self.run_dialog(driver, prefill=dict(self.PREFILL, hotkey="ctrl+shift+r", hotkey_locked=True))
        self.assertEqual(seen["keys"], "Ctrl+Shift+R")
        self.assertEqual(seen["button"], "disabled")
        self.assertEqual(seen["hint"], setup_gui.DIALOG_STRINGS["it"]["hotkey_locked"])
        self.assertIsNone(result["hotkey"])  # nothing to save: .env decides


if __name__ == "__main__":
    unittest.main()
