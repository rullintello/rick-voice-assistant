"""rick/tts.py: the voice file handed back, the switch to Windows' own
voice when Microsoft's online voice fails, and no temp files left behind."""

import sys
import unittest
import wave
from pathlib import Path
from unittest import mock

from rick import config, tts

from support import isolate_rick_home


def writes(content: bytes):
    def render(text, out_path):
        with open(out_path, "wb") as f:
            f.write(content + text.encode())
    return render


def fails(message):
    def render(text, out_path):
        raise OSError(message)
    return render


class SynthesizeTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        for name, value in (("_online_unavailable_until", 0.0), ("_HAS_WINDOWS_VOICES", True)):
            patcher = mock.patch.object(tts, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def use(self, online, windows):
        for name, value in (("_render_online", online), ("_render_windows", windows)):
            patcher = mock.patch.object(tts, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()

    def test_online_voice_when_it_works(self):
        self.use(writes(b"mp3:"), fails("must not be used"))
        path = tts.synthesize("ciao")
        self.assertEqual(Path(path).parent, config.TEMP_DIR)
        self.assertTrue(path.endswith(".mp3"))
        self.assertEqual(self.read(path), b"mp3:ciao")

    def test_windows_voice_when_the_online_one_is_refused(self):
        # what the user saw: edge-tts answering 403 "Invalid response status"
        self.use(fails("403, message='Invalid response status'"), writes(b"wav:"))
        with self.assertLogs(tts.log, "WARNING"):
            path = tts.synthesize("ciao")
        self.assertTrue(path.endswith(".wav"))
        self.assertEqual(self.read(path), b"wav:ciao")
        self.assertEqual(list(config.TEMP_DIR.glob("*.mp3")), [])  # failed attempt cleaned up

    def test_online_voice_is_retried_only_after_a_pause(self):
        online = mock.Mock(side_effect=fails("403"))
        self.use(online, writes(b"wav:"))
        with mock.patch.object(tts.time, "monotonic", return_value=1000.0):
            tts.synthesize("uno")
            tts.synthesize("due")  # straight to Windows' voice, no new failed attempt
        self.assertEqual(online.call_count, 1)
        with mock.patch.object(tts.time, "monotonic", return_value=1000.0 + tts._ONLINE_RETRY_AFTER_SECONDS):
            tts.synthesize("tre")
        self.assertEqual(online.call_count, 2)

    def test_no_voice_at_all_gives_a_readable_error_and_no_temp_files(self):
        self.use(fails("403"), fails("no SAPI voices"))
        with self.assertRaises(tts.VoiceUnavailableError) as raised:
            tts.synthesize("ciao")
        self.assertIn("scritta nel libro", str(raised.exception))  # not the raw 403 and URL
        self.assertEqual(list(config.TEMP_DIR.glob("*")), [])

    def test_without_windows_voices_the_online_one_is_always_retried(self):
        online = mock.Mock(side_effect=fails("offline"))
        self.use(online, fails("must not be used"))
        with mock.patch.object(tts, "_HAS_WINDOWS_VOICES", False):
            for _ in range(2):
                with self.assertRaises(tts.VoiceUnavailableError):
                    tts.synthesize("ciao")
        self.assertEqual(online.call_count, 2)


@unittest.skipUnless(sys.platform == "win32", "Windows' built-in voices only exist on Windows")
class RealWindowsVoiceTest(unittest.TestCase):
    """Runs on the Windows CI machines: speaks for real through SAPI."""

    def setUp(self):
        self.tmp = isolate_rick_home(self)
        import comtypes.client

        voices = comtypes.client.CreateObject("SAPI.SpVoice").GetVoices()
        if voices.Count == 0:
            self.skipTest("no Windows voices installed on this machine")

    def test_speaks_into_a_playable_wav(self):
        path = self.tmp / "voce.wav"
        tts._render_windows("Lo trovi nel forte del Lago di Liurnia.", str(path))
        with wave.open(str(path)) as wav:
            seconds = wav.getnframes() / wav.getframerate()
        self.assertGreater(seconds, 0.5)  # real speech, not an empty file
        import miniaudio  # the same decoder Rick plays answers with

        self.assertGreater(miniaudio.decode_file(str(path)).num_frames, 0)


if __name__ == "__main__":
    unittest.main()
