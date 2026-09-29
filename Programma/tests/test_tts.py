"""rick/tts.py: the voice file handed back, and no temp files left behind
when the voice service fails (e.g. offline)."""

import unittest
from pathlib import Path
from unittest import mock

from rick import config, tts

from support import isolate_rick_home


class SynthesizeTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)

    def test_returns_the_rendered_file(self):
        def render(text, out_path):
            with open(out_path, "wb") as f:
                f.write(b"mp3 bytes for " + text.encode())

        with mock.patch.object(tts, "_render", render):
            path = tts.synthesize("ciao")
        self.assertEqual(Path(path).parent, config.TEMP_DIR)
        with open(path, "rb") as f:
            self.assertEqual(f.read(), b"mp3 bytes for ciao")

    def test_failure_leaves_no_temp_file(self):
        with mock.patch.object(tts, "_render", side_effect=OSError("offline")):
            for _ in range(3):
                with self.assertRaises(OSError):
                    tts.synthesize("ciao")
        self.assertEqual(list(config.TEMP_DIR.glob("*")), [])


if __name__ == "__main__":
    unittest.main()
