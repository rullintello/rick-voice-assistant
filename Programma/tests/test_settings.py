"""settings.py (opened by Settings.bat): what gets saved, and the popup
telling the player to restart Rick when the keys changed."""

import os
import unittest
from unittest import mock

import settings
from rick import config, setup_gui

from support import isolate_rick_home


class SettingsTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        os.environ["GEMINI_API_KEY"] = ""  # keys come from config.json here
        config.save_gemini_api_key("gem-123")
        self.notices = []
        notify = mock.patch.object(settings, "_notify", self.notices.append)
        notify.start()
        self.addCleanup(notify.stop)

    def run_settings(self, **answer):
        """Runs settings.main() with the dialog answering `answer`; returns
        what the dialog was pre-filled with."""
        seen = {}

        def dialog(prefill, title):
            seen.update(prefill)
            return dict(
                {"gemini": "gem-123", "tavily": "", "language": "it", "hotkey": prefill["hotkey"], "voice": None},
                **answer,
            )

        with mock.patch.object(setup_gui, "ask_for_api_keys", dialog):
            settings.main()
        return seen

    def test_new_keys_are_saved_and_a_restart_is_asked(self):
        prefill = self.run_settings(hotkey="ctrl+shift+f9")
        self.assertEqual(prefill["hotkey"], "alt+r")
        self.assertEqual(config.get_hotkey(), "ctrl+shift+f9")
        (notice,) = self.notices
        self.assertIn("Impostazioni salvate", notice)
        self.assertIn("chiudilo e riaprilo", notice)
        self.assertIn("Ctrl+Shift+F9", notice)

    def test_same_keys_need_no_restart(self):
        self.run_settings()
        self.assertEqual(self.notices, ["Impostazioni salvate."])

    def test_keys_from_env_are_left_alone(self):
        os.environ["RICK_HOTKEY"] = "ctrl+shift+r"  # restored by isolate_rick_home
        prefill = self.run_settings(hotkey=None)
        self.assertTrue(prefill["hotkey_locked"])
        self.assertEqual(prefill["hotkey"], "ctrl+shift+r")
        self.assertNotIn("hotkey", config._load_user_config())
        self.assertEqual(self.notices, ["Impostazioni salvate."])

    def test_the_picked_voice_is_saved_for_the_language(self):
        prefill = self.run_settings(voice="diego", language="it")
        self.assertEqual(prefill["voices"], {"it": "giuseppe", "en": "andrew_deep"})
        self.assertIsNone(prefill["locked_voice"])
        self.assertEqual(config.get_voice("it").id, "diego")
        self.assertEqual(config.get_voice("en").id, "andrew_deep")  # untouched

    def test_a_voice_from_env_is_left_alone(self):
        os.environ["RICK_EDGE_VOICE"] = "it-IT-IsabellaNeural"  # restored by isolate_rick_home
        prefill = self.run_settings(voice=None)
        self.assertEqual(prefill["locked_voice"].name, "it-IT-IsabellaNeural")
        self.assertNotIn("voices", config._load_user_config())

    def test_cancelling_saves_nothing(self):
        self.run_settings(gemini="", hotkey="ctrl+shift+f9")
        self.assertEqual(config.get_hotkey(), "alt+r")
        self.assertIn("Nessuna modifica", self.notices[0])


if __name__ == "__main__":
    unittest.main()
