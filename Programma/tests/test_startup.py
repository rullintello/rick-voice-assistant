import logging.handlers
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from rick import config, startup

PROGRAMMA_DIR = Path(__file__).resolve().parent.parent


class EnvIntTest(unittest.TestCase):
    def test_valid_value(self):
        with mock.patch.dict("os.environ", {"RICK_X": "42"}):
            self.assertEqual(config._env_int("RICK_X", 7), 42)

    def test_blank_falls_back_to_default(self):
        with mock.patch.dict("os.environ", {"RICK_X": "  "}):
            self.assertEqual(config._env_int("RICK_X", 7), 7)

    def test_missing_falls_back_to_default(self):
        with mock.patch.dict("os.environ", {}, clear=False):
            self.assertEqual(config._env_int("RICK_DEFINITELY_NOT_SET", 7), 7)

    def test_malformed_falls_back_to_default(self):
        with mock.patch.dict("os.environ", {"RICK_X": "ten"}):
            self.assertEqual(config._env_int("RICK_X", 7), 7)


class RunTest(unittest.TestCase):
    def setUp(self):
        for name in ("setup_logging", "show_error_dialog"):
            patcher = mock.patch.object(startup, name)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_failure_is_shown_to_the_user(self):
        def entry():
            raise ImportError("PortAudio library not found")

        startup.run(entry)

        self.setup_logging.assert_called_once()
        self.show_error_dialog.assert_called_once()
        title, body = self.show_error_dialog.call_args.args
        self.assertIn(str(startup.LOG_FILE), body)

    def test_success_shows_nothing(self):
        startup.run(lambda: None)
        self.show_error_dialog.assert_not_called()

    def test_system_exit_is_not_treated_as_a_crash(self):
        def entry():
            raise SystemExit(0)

        with self.assertRaises(SystemExit):
            startup.run(entry)
        self.show_error_dialog.assert_not_called()


class SetupLoggingTest(unittest.TestCase):
    def test_creates_log_folder_and_installs_hooks(self):
        folder = Path(tempfile.mkdtemp()) / "nested" / ".rick"
        self.addCleanup(shutil.rmtree, folder.parent.parent, ignore_errors=True)
        # restore the real hooks afterwards: setup_logging replaces them
        # process-wide, which must not leak into the rest of the test run
        self.addCleanup(setattr, sys, "excepthook", sys.excepthook)
        self.addCleanup(setattr, threading, "excepthook", threading.excepthook)
        original_sys_hook, original_thread_hook = sys.excepthook, threading.excepthook

        with mock.patch.object(startup, "LOG_FILE", folder / "rick.log"), \
             mock.patch("logging.basicConfig") as basic_config:
            startup.setup_logging()

        self.assertTrue(folder.is_dir())
        basic_config.assert_called_once()
        (handler,) = basic_config.call_args.kwargs["handlers"]
        self.addCleanup(handler.close)
        # capped in size, instead of growing for as long as Rick is used
        self.assertIsInstance(handler, logging.handlers.RotatingFileHandler)
        self.assertEqual(handler.maxBytes, startup.LOG_MAX_BYTES)
        self.assertEqual(handler.backupCount, startup.LOG_BACKUPS)
        self.assertIsNot(sys.excepthook, original_sys_hook)
        self.assertIsNot(threading.excepthook, original_thread_hook)


class EntryPointImportsTest(unittest.TestCase):
    """The whole point of main.py/settings.py being thin: importing them must
    not pull in anything that can fail (audio libs, Gemini SDK, .env
    parsing) before run() has set up logging and the error dialog."""

    def _modules_loaded_by_importing(self, module: str) -> set:
        code = f"import sys, {module}; print('\\n'.join(sys.modules))"
        out = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROGRAMMA_DIR,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return set(out.split())

    def test_main_defers_risky_imports(self):
        loaded = self._modules_loaded_by_importing("main")
        for risky in ("rick.app", "rick.config", "keyboard", "sounddevice", "google.genai"):
            self.assertNotIn(risky, loaded)

    def test_only_rick_s_own_dotenv_is_loaded(self):
        # load_dotenv() with no path would also search every parent folder
        code = (
            "import dotenv; calls = []\n"
            "dotenv.load_dotenv = lambda *a, **k: calls.append(a)\n"
            "from rick import config; print(repr(calls))"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=PROGRAMMA_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        self.assertEqual(out, repr([(Path(PROGRAMMA_DIR).resolve() / ".env",)]))

    def test_settings_defers_risky_imports(self):
        loaded = self._modules_loaded_by_importing("settings")
        for risky in ("rick.config", "dotenv"):
            self.assertNotIn(risky, loaded)


if __name__ == "__main__":
    unittest.main()
