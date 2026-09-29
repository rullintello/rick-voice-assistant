"""The first-run / Settings dialog (rick/setup_gui.py): API keys hidden
from anyone watching the screen, and still saved correctly."""

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


class SetupDialogTest(unittest.TestCase):
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

    def save(self, root):
        next(b for b in widgets(root, tk.Button) if b.cget("command")).invoke()

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
        self.assertEqual(result, {"gemini": "gem-typed", "tavily": "", "language": "it"})

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


if __name__ == "__main__":
    unittest.main()
