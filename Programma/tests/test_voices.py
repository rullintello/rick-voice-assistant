"""Rick's voice: the voices offered (rick/voices.py), the one saved per
language (rick/config.py), what's sent to edge-tts and the Windows backup
voice (rick/tts.py), and the settings window's voice row
(rick/voice_picker.py)."""

import json
import os
import threading
import time
import tkinter as tk
import types
import unittest
from unittest import mock

from rick import config, tts, voice_picker, voices

from support import isolate_rick_home, require_display


class CatalogTest(unittest.TestCase):
    def test_every_language_has_distinct_voices_and_a_sample(self):
        for language, choices in voices.VOICES.items():
            self.assertEqual(len({v.id for v in choices}), len(choices), language)
            self.assertEqual(len({v.label for v in choices}), len(choices), language)
            self.assertIn(language, voices.SAMPLE)
            self.assertTrue(all(v.gender in ("male", "female") for v in choices))
            self.assertTrue(all(v.name.startswith(("it-IT-", "en-US-")) for v in choices))

    def test_rick_is_a_he_by_default(self):
        self.assertEqual(voices.find("it", None).name, "it-IT-GiuseppeMultilingualNeural")
        en = voices.find("en", None)
        self.assertEqual((en.name, en.rate, en.pitch), ("en-US-AndrewMultilingualNeural", "-6%", "-12Hz"))
        self.assertTrue(all(voices.find(lang, None).gender == "male" for lang in voices.VOICES))

    def test_an_unknown_id_falls_back_to_the_default(self):
        self.assertEqual(voices.find("it", "nonexistent").id, "giuseppe")
        self.assertEqual(voices.find("it", "andrew").id, "giuseppe")  # an English voice for Italian
        self.assertEqual(voices.find("xx", None).id, "giuseppe")


class ConfigTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)

    def test_each_language_keeps_its_own_voice(self):
        config.save_voice("it", "diego")
        config.save_voice("en", "brian")
        self.assertEqual(config.get_voice("it").id, "diego")
        self.assertEqual(config.get_voice("en").id, "brian")
        self.assertEqual(config.get_voice().id, "diego")  # isolate_rick_home: Rick speaks Italian
        self.assertEqual(json.loads(config.USER_CONFIG_FILE.read_text())["voices"], {"it": "diego", "en": "brian"})

    def test_unknown_voices_are_not_saved(self):
        with self.assertRaises(ValueError):
            config.save_voice("it", "brian")
        self.assertFalse(config.USER_CONFIG_FILE.exists())

    def test_a_broken_saved_value_falls_back_to_the_default(self):
        for broken in ({"voices": "diego"}, {"voices": {"it": 5}}, {"voices": {"it": "gone"}}):
            config.USER_CONFIG_FILE.write_text(json.dumps(broken))
            self.assertEqual(config.get_voice("it").id, "giuseppe", broken)

    def test_env_decides_when_set(self):
        config.save_voice("it", "diego")
        os.environ["RICK_EDGE_VOICE"] = "it-IT-IsabellaNeural"  # restored by isolate_rick_home
        with mock.patch.object(config, "EDGE_RATE", "+10%"), mock.patch.object(config, "EDGE_PITCH", "+5Hz"):
            voice = config.get_voice()
        self.assertTrue(config.voice_set_in_env())
        self.assertEqual((voice.name, voice.rate, voice.pitch), ("it-IT-IsabellaNeural", "+10%", "+5Hz"))


class SpeechTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        patcher = mock.patch.object(tts, "_online_unavailable_until", 0.0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_picked_voice_reaches_edge_tts_with_its_speed_and_pitch(self):
        config.save_voice("it", "diego_deep")
        sent = {}

        class FakeCommunicate:
            def __init__(self, text, voice, rate, pitch):
                sent.update(text=text, voice=voice, rate=rate, pitch=pitch)

            async def save(self, path):
                with open(path, "wb") as f:
                    f.write(b"mp3")

        with mock.patch.dict("sys.modules", {"edge_tts": types.SimpleNamespace(Communicate=FakeCommunicate)}):
            path = tts.synthesize("ciao")
        self.assertTrue(path.endswith(".mp3"))
        self.assertEqual(sent, {"text": "ciao", "voice": "it-IT-DiegoNeural", "rate": "-6%", "pitch": "-12Hz"})

    def test_the_windows_backup_gets_the_picked_voices_gender(self):
        config.save_voice("it", "elsa")
        asked = {}

        def windows(text, path, gender):
            asked["gender"] = gender
            with open(path, "wb") as f:
                f.write(b"wav")

        def refused(text, path, voice):
            raise OSError("403")

        with mock.patch.object(tts, "_HAS_WINDOWS_VOICES", True), \
                mock.patch.object(tts, "_render_online", refused), \
                mock.patch.object(tts, "_render_windows", windows), \
                self.assertLogs(tts.log, "WARNING"):
            tts.synthesize("ciao")
        self.assertEqual(asked["gender"], "female")

    def test_a_voice_can_be_given_for_one_line(self):
        used = []

        def online(text, path, voice):
            used.append(voice.id)
            with open(path, "wb") as f:
                f.write(b"mp3")

        with mock.patch.object(tts, "_render_online", online):
            tts.synthesize("ciao", voice=voices.find("en", "brian"))
            tts.synthesize("ciao")
        self.assertEqual(used, ["brian", "giuseppe"])


class FakeToken:
    def __init__(self, name, **attributes):
        self.name, self.attributes = name, attributes

    def GetAttribute(self, name):
        if name not in self.attributes:
            raise OSError("no such attribute")  # what SAPI does
        return self.attributes[name]


class WindowsVoicePickTest(unittest.TestCase):
    ZIRA = FakeToken("Zira", Language="409", Gender="Female")
    DAVID = FakeToken("David", Language="409", Gender="Male")
    ELSA = FakeToken("Elsa", Language="410", Gender="Female")
    ODD = FakeToken("Odd")  # no attributes at all

    def pick(self, tokens, languages, gender):
        token = tts.pick_windows_voice(tokens, languages, gender)
        return token.name if token else None

    def test_same_language_and_gender_first(self):
        self.assertEqual(self.pick([self.ODD, self.ZIRA, self.DAVID], {"409"}, "male"), "David")
        self.assertEqual(self.pick([self.DAVID, self.ZIRA], {"409"}, "female"), "Zira")

    def test_then_just_the_language(self):
        # Italian Windows ships only a female voice: better than English
        self.assertEqual(self.pick([self.DAVID, self.ELSA], {"410"}, "male"), "Elsa")

    def test_else_windows_default(self):
        self.assertIsNone(self.pick([self.DAVID, self.ODD], {"410"}, "male"))


class VoicePickerTest(unittest.TestCase):
    def setUp(self):
        require_display(self)
        self.root = tk.Tk()
        self.addCleanup(self.root.destroy)
        self.said = []
        self.answer = True  # what the fake say() reports: True = Microsoft spoke
        self.done = threading.Event()

    def say(self, language, voice):
        self.said.append((language, voice.id))
        self.done.set()
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def make(self, language="it", picked=None, locked_voice=None):
        picker = voice_picker.VoicePicker(self.root, language, picked, locked_voice=locked_voice, say=self.say)
        picker.frame.pack()
        return picker

    def select(self, picker, voice_id):
        label = next(v.label for v in voices.VOICES[picker._language] if v.id == voice_id)
        picker.choice.set(label)
        picker.choice.event_generate("<<ComboboxSelected>>")

    def press_try(self, picker):
        self.done.clear()
        picker.button.invoke()
        self.assertTrue(self.done.wait(5))
        deadline = time.monotonic() + 5  # the result comes back through after(0)
        while picker._busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(picker._busy, "the Try button never came back")
        return picker.hint.cget("text")

    def test_starts_on_the_saved_voice_or_the_default(self):
        self.assertEqual(self.make().choice.get(), "Giuseppe (maschile)")
        self.assertEqual(self.make("it", {"it": "elsa"}).choice.get(), "Elsa (femminile)")
        self.assertEqual(self.make("en").choice.get(), "Andrew, deeper (male)")

    def test_offers_only_the_languages_own_voices(self):
        picker = self.make()
        self.assertEqual(list(picker.choice.cget("values")), [v.label for v in voices.VOICES["it"]])
        picker.set_language("en")
        self.assertEqual(list(picker.choice.cget("values")), [v.label for v in voices.VOICES["en"]])
        self.assertEqual(picker._title.cget("text"), voice_picker.STRINGS["en"]["label"])

    def test_each_language_remembers_its_pick(self):
        picker = self.make()
        self.select(picker, "diego")
        picker.set_language("en")
        self.select(picker, "brian")
        self.assertEqual(picker.voice_id, "brian")
        picker.set_language("it")
        self.assertEqual(picker.voice_id, "diego")
        self.assertEqual(picker.choice.get(), "Diego (maschile)")

    def test_try_speaks_the_selected_voice(self):
        picker = self.make()
        self.select(picker, "elsa")
        self.assertEqual(self.press_try(picker), voice_picker.STRINGS["it"]["note"])
        self.assertEqual(self.said, [("it", "elsa")])
        self.assertEqual(picker.button.cget("state"), "normal")

    def test_try_says_when_windows_backup_spoke(self):
        self.answer = False
        self.assertEqual(self.press_try(self.make()), voice_picker.STRINGS["it"]["backup"])

    def test_try_explains_a_failure(self):
        self.answer = OSError("no sound device")
        with self.assertLogs(voice_picker.log, "WARNING"):
            text = self.press_try(self.make())
        self.assertIn("no sound device", text)

    def test_voice_from_env_is_shown_and_tried_but_not_offered(self):
        env_voice = voices.Voice("env", "it-IT-IsabellaNeural", "it-IT-IsabellaNeural", gender="")
        picker = self.make(locked_voice=env_voice)
        self.assertEqual(str(picker.choice.cget("state")), "disabled")
        self.assertEqual(picker.choice.get(), "it-IT-IsabellaNeural")
        self.assertIsNone(picker.voice_id)
        self.press_try(picker)
        self.assertEqual(self.said, [("it", "env")])


if __name__ == "__main__":
    unittest.main()
