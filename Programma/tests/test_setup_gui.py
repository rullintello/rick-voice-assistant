"""The first-run / Settings dialog (rick/setup_gui.py): API keys hidden
from anyone watching the screen, and still saved correctly; the keys that
start Rick, picked by pressing them."""

import tkinter as tk
import unittest
from unittest import mock

from rick import hotkey_picker, setup_gui

from support import require_display
from test_hotkey_picker import press


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
    """The keys row of the dialog (rick/hotkey_picker.py, tested in depth in
    test_hotkey_picker.py): what it starts from and what the dialog returns."""

    PREFILL = {"gemini": "gem-123", "language": "it"}

    def setUp(self):
        super().setUp()
        self.pickers = []
        test = self

        class RecordedPicker(hotkey_picker.HotkeyPicker):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                test.pickers.append(self)

        patcher = mock.patch.object(setup_gui, "HotkeyPicker", RecordedPicker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_alt_r_is_shown_and_kept_by_default(self):
        seen = {}

        def driver(root):
            seen["keys"] = self.pickers[0].box.cget("text")
            self.save(root)

        result = self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(seen["keys"], "Alt+R")
        self.assertEqual(result["hotkey"], "alt+r")

    def test_picked_keys_are_returned(self):
        def driver(root):
            picker = self.pickers[0]
            picker.button.invoke()
            press(picker, "Control_L", "Shift_L", "F9")
            self.save(root)

        result = self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(result["hotkey"], "ctrl+shift+f9")

    def test_saving_while_still_waiting_keeps_the_old_keys(self):
        def driver(root):
            self.pickers[0].button.invoke()
            self.save(root)

        result = self.run_dialog(driver, prefill=dict(self.PREFILL, hotkey="ctrl+shift+r"))
        self.assertEqual(result["hotkey"], "ctrl+shift+r")

    def test_the_row_follows_the_language(self):
        seen = {}

        def driver(root):
            _it, en_button = widgets(root, tk.Radiobutton)
            en_button.invoke()
            seen["button"] = self.pickers[0].button.cget("text")
            root.destroy()

        self.run_dialog(driver, prefill=self.PREFILL)
        self.assertEqual(seen["button"], hotkey_picker.STRINGS["en"]["change"])

    def test_keys_set_in_env_are_shown_but_locked(self):
        seen = {}

        def driver(root):
            picker = self.pickers[0]
            seen["keys"] = picker.box.cget("text")
            seen["button"] = picker.button.cget("state")
            self.save(root)

        result = self.run_dialog(driver, prefill=dict(self.PREFILL, hotkey="ctrl+shift+r", hotkey_locked=True))
        self.assertEqual(seen["keys"], "Ctrl+Shift+R")
        self.assertEqual(seen["button"], "disabled")
        self.assertIsNone(result["hotkey"])  # nothing to save: .env decides


if __name__ == "__main__":
    unittest.main()
