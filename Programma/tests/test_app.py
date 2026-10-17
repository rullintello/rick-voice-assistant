"""Rick's Alt+R state machine (rick/app.py), driven the way the real app is:
the test thread plays the part of keyboard's listener thread calling
on_hotkey(), while each question is handled on app.py's own worker thread.
Microphone, speakers, Whisper, Gemini, the voice and the window are all
fakes, so these run anywhere - no display, no audio device, no network."""

import os
import tempfile
import threading
import types
import unittest
from unittest import mock

from rick import app, config, updates

from support import isolate_rick_home, wait_until

ANSWER = "Lo trovi nella palude a nord del castello."


class FakeBook:
    """Stands in for gui.BookWindow: same thread-safe API, no Tk."""

    def __init__(self, language, on_close=None, on_new_chat=None, shortcut=None):
        self.language = language
        self.on_new_chat = on_new_chat
        self.shortcut = shortcut  # app.Shortcut: the window's "Keys" button drives it
        self.shortcut_shown = 0
        self.game = "Elden Ring"
        self.statuses = []
        self.turns = []
        self.when_running_calls = []  # what main() asked to run once the window goes
        self.updates_shown = []
        self._lock = threading.Lock()

    def set_status(self, text):
        with self._lock:
            self.statuses.append(text)

    @property
    def status(self):
        with self._lock:
            return self.statuses[-1] if self.statuses else ""

    def current_game(self):
        return self.game

    def append_turn(self, game, question, answer):
        with self._lock:
            self.turns.append((game, question, answer))

    def show_shortcut(self):
        self.shortcut_shown += 1

    def show_update(self, version):
        self.updates_shown.append(version)

    def when_running(self, fn):
        self.when_running_calls.append(fn)

    def run(self):
        pass  # the real one blocks in Tk's mainloop; the test drives instead


class FakeRecorder:
    def __init__(self, tmp):
        self.tmp = tmp
        self.starts = 0
        self.start_error = None
        self.recording = False
        self.wav_files = []

    def start(self):
        if self.start_error is not None:
            raise self.start_error
        self.starts += 1
        self.recording = True

    def stop(self):
        assert self.recording, "stop() without a successful start()"
        self.recording = False
        fd, path = tempfile.mkstemp(suffix=".wav", dir=self.tmp)
        os.close(fd)
        self.wav_files.append(path)
        return path


class FakeRick:
    def __init__(self):
        self.asked = []
        self.error = None
        self.gate = None  # a threading.Event to hold ask() "thinking"

    def ask(self, question, game=""):
        self.asked.append((question, game))
        if self.gate is not None:
            assert self.gate.wait(5), "test never released ask()"
        if self.error is not None:
            raise self.error
        return ANSWER

    def reset_conversation(self):
        pass


class FakeSpeaker:
    """synthesize/play_audio/arm_playback/interrupt_playback, with the real
    interrupt semantics: an interrupt stops the current voice, and stays in
    effect until the next arm_playback()."""

    def __init__(self, tmp):
        self.tmp = tmp
        self.spoken = []
        self.mp3_files = []
        self.interrupts = 0
        self.block = False  # True: play_audio lasts until interrupted
        self.linger = None  # an Event: an interrupted play_audio returns only once it's set
        self.playing = threading.Event()
        self._stop = threading.Event()

    def synthesize(self, text):
        self.spoken.append(text)
        fd, path = tempfile.mkstemp(suffix=".mp3", dir=self.tmp)
        os.close(fd)
        self.mp3_files.append(path)
        return path

    def arm_playback(self):
        self._stop.clear()

    def play_audio(self, path):
        assert os.path.exists(path)
        self.playing.set()
        if self.block:
            self._stop.wait(5)
            if self.linger is not None:
                assert self.linger.wait(5), "test never released the old turn"

    def interrupt_playback(self):
        self.interrupts += 1
        self._stop.set()


class AppHarness(unittest.TestCase):
    """Starts app.main() with every outside piece faked (see the module
    docstring); the test classes below drive it."""

    # the keys Rick should end up listening on, and how the status bar names them
    hotkey, key_label = "alt+r", "Alt+R"

    def prepare_settings(self):
        """For subclasses: settings in place before Rick starts."""

    def setUp(self):
        self.tmp = isolate_rick_home(self)
        self.prepare_settings()
        self.recorder = FakeRecorder(self.tmp)
        self.rick = FakeRick()
        self.resets = 0
        self.rick.reset_conversation = lambda: setattr(self, "resets", self.resets + 1)
        self.speaker = FakeSpeaker(self.tmp)
        self.question = "dove trovo lo scudo leggendario?"
        self.registered = {}
        self.hotkey_attempts = []
        self.workers = []

        self.unknown_to_keyboard = {"ctrl+nosuchkey"}

        def add_hotkey(key, callback):
            # like keyboard: a key name it doesn't know fails at registration,
            # and what comes back removes the hotkey
            self.hotkey_attempts.append(key)
            if key in self.unknown_to_keyboard:
                raise ValueError(f"Key {key!r} is not mapped to any known key.")
            self.registered[key] = callback
            return lambda: self.registered.pop(key)

        def worker_thread(*args, **kwargs):
            thread = threading.Thread(*args, **kwargs)
            self.workers.append(thread)
            return thread

        patches = {
            "keyboard": mock.Mock(add_hotkey=add_hotkey),
            "threading": types.SimpleNamespace(Thread=worker_thread, Lock=threading.Lock, Event=threading.Event),
            "Recorder": lambda: self.recorder,
            "Rick": lambda: self.rick,
            "transcribe": lambda path: self.question,
            "synthesize": self.speaker.synthesize,
            "play_audio": self.speaker.play_audio,
            "arm_playback": self.speaker.arm_playback,
            "interrupt_playback": self.speaker.interrupt_playback,
            "chime_start": lambda: None,
            "chime_stop": lambda: None,
        }
        for name, value in patches.items():
            patcher = mock.patch.object(app, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        books = []
        with mock.patch.object(app, "BookWindow", lambda **kw: books.append(FakeBook(**kw)) or books[-1]):
            app.main()
        self.book = books[0]
        self.assertEqual(list(self.registered), [self.hotkey])
        self.press = self.registered[self.hotkey]

    # -- helpers ---------------------------------------------------------
    def ready(self):
        return app._t("status_ready", hotkey=self.key_label)

    def recording(self):
        return app._t("status_recording", hotkey=self.key_label)

    def wait_for_status(self, text):
        self.assertTrue(wait_until(lambda: self.book.status == text),
                        f"status never became {text!r}, last: {self.book.status!r}")

    def ask_one_question(self):
        self.press()  # idle -> recording
        self.assertEqual(self.book.status, self.recording())
        self.press()  # recording -> thinking (worker thread)

    def join_worker(self, index):
        self.workers[index].join(5)
        self.assertFalse(self.workers[index].is_alive())

    def assert_no_temp_files_left(self):
        for path in self.recorder.wav_files + self.speaker.mp3_files:
            self.assertFalse(os.path.exists(path), path)



class AppTest(AppHarness):
    # -- the happy path ----------------------------------------------------
    def test_a_normal_turn(self):
        self.assertEqual(self.book.status, self.ready())
        self.ask_one_question()
        self.wait_for_status(self.ready())
        self.assertEqual(self.rick.asked, [(self.question, "Elden Ring")])
        self.assertEqual(self.book.turns, [("Elden Ring", self.question, ANSWER)])
        self.assertEqual(self.speaker.spoken, [ANSWER])
        self.assert_no_temp_files_left()

    def test_new_chat_in_the_window_resets_rick_s_conversation(self):
        self.book.on_new_chat()
        self.assertEqual(self.resets, 1)

    def test_nothing_heard_is_said_and_rick_is_not_asked(self):
        self.question = ""
        self.ask_one_question()
        self.wait_for_status(self.ready())
        self.assertEqual(self.speaker.spoken, [app._t("status_nothing_heard")])
        self.assertEqual(self.rick.asked, [])
        self.assertEqual(self.book.turns, [])

    def test_alt_r_is_ignored_while_rick_is_thinking(self):
        self.rick.gate = threading.Event()
        self.ask_one_question()
        self.assertTrue(wait_until(lambda: self.rick.asked))
        self.press()
        self.assertEqual(self.recorder.starts, 1)
        self.rick.gate.set()
        self.wait_for_status(self.ready())

    # -- errors --------------------------------------------------------------
    def test_error_stays_visible_after_the_spoken_apology(self):
        self.rick.error = RuntimeError("Gemini non raggiungibile")
        self.ask_one_question()
        self.assertTrue(wait_until(lambda: app._t("error_speech") in self.speaker.spoken))
        expected = app._error_status(self.rick.error, self.key_label)
        self.wait_for_status(expected)
        self.assertIn("Gemini non raggiungibile", expected)
        self.assertEqual(self.book.turns, [])  # errors are never saved to a binder
        self.assert_no_temp_files_left()
        # ...and the next Alt+R still works as usual
        self.press()
        self.assertEqual(self.book.status, self.recording())

    def test_long_error_messages_are_shortened_to_one_line(self):
        status = app._error_status(RuntimeError("x" * 500 + "\n{'error': {...}}"), self.key_label)
        self.assertNotIn("\n", status)
        self.assertLess(len(status), 250)
        self.assertEqual(app._error_status(RuntimeError(), self.key_label).count("RuntimeError"), 1)

    def test_microphone_failure_does_not_kill_alt_r(self):
        # keyboard runs hotkey callbacks with no error handling: an exception
        # escaping on_hotkey would kill its thread, and Alt+R with it
        self.recorder.start_error = OSError("Error opening InputStream: Invalid device")
        self.press()  # must not raise
        self.assertIn("Invalid device", self.book.status)
        self.recorder.start_error = None  # mic plugged back in
        self.ask_one_question()
        self.wait_for_status(self.ready())
        self.assertEqual(self.book.turns, [("Elden Ring", self.question, ANSWER)])

    # -- interrupting Rick -------------------------------------------------
    def interrupt_mid_answer(self):
        self.speaker.block = True
        self.ask_one_question()
        self.assertTrue(self.speaker.playing.wait(5))
        self.assertEqual(self.book.status, app._t("status_speaking"))
        self.press()  # speaking -> recording

    def test_interrupting_rick_starts_a_new_recording(self):
        self.interrupt_mid_answer()
        self.assertEqual(self.speaker.interrupts, 1)
        self.assertEqual(self.recorder.starts, 2)
        self.join_worker(0)
        # the interrupted turn winding down must not flip back to "ready"
        # (or to idle: the next press has to stop THIS recording)
        self.assertEqual(self.book.status, self.recording())
        self.speaker.block = False
        self.press()
        self.wait_for_status(self.ready())
        self.assertEqual(len(self.book.turns), 2)
        self.assert_no_temp_files_left()

    def test_late_interrupted_turn_cannot_end_the_next_one(self):
        self.speaker.linger = threading.Event()
        self.interrupt_mid_answer()
        self.speaker.block = False
        self.rick.gate = threading.Event()
        self.press()  # the next question: Rick is thinking about it...
        self.assertTrue(wait_until(lambda: len(self.rick.asked) == 2))
        self.speaker.linger.set()  # ...when the old turn finally winds down
        self.join_worker(0)
        self.assertEqual(self.book.status, app._t("status_thinking"))
        self.press()  # still thinking, so still ignored
        self.assertEqual(self.recorder.starts, 2)
        self.rick.gate.set()
        self.wait_for_status(self.ready())
        self.assertEqual(len(self.book.turns), 2)

    def test_failed_restart_after_an_interrupt_keeps_the_error_visible(self):
        self.speaker.block = True
        self.ask_one_question()
        self.assertTrue(self.speaker.playing.wait(5))
        self.recorder.start_error = OSError("microphone busy")
        self.press()  # interrupts, then can't record
        self.assertIn("microphone busy", self.book.status)
        self.join_worker(0)
        # the interrupted answer's thread finishing must not cover the error
        self.assertIn("microphone busy", self.book.status)
        self.recorder.start_error = None
        self.speaker.block = False
        self.press()
        self.assertEqual(self.book.status, self.recording())

class UpdateCheckTest(AppHarness):
    """The check for a newer Rick (rick/updates.py) starts with the window
    and reports to it."""

    def test_starts_once_the_window_runs(self):
        (start_check,) = self.book.when_running_calls
        with mock.patch.object(updates, "start", lambda on_newer: on_newer("9.9.9")):
            start_check()  # the check finds 9.9.9 and tells the window
        self.assertEqual(self.book.updates_shown, ["9.9.9"])


class UpdateCheckOffTest(AppHarness):
    def prepare_settings(self):
        patcher = mock.patch.object(config, "CHECK_FOR_UPDATES", False)  # RICK_CHECK_UPDATES=false
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_not_started(self):
        self.assertEqual(self.book.when_running_calls, [])


class PickedShortcutTest(AppTest):
    """Every turn above again, on keys picked in the settings window."""

    hotkey, key_label = "ctrl+shift+f9", "Ctrl+Shift+F9"

    def prepare_settings(self):
        config.save_hotkey("Ctrl+Shift+F9")

    def test_status_bar_names_the_picked_keys(self):
        self.assertIn("Ctrl+Shift+F9", self.book.status)
        self.assertNotIn("Alt+R", self.book.status)


class UnknownShortcutInEnvTest(AppTest):
    """RICK_HOTKEY in .env naming a key keyboard doesn't know: Rick still
    starts, listening on Alt+R, and every turn above works the same."""

    def prepare_settings(self):
        os.environ["RICK_HOTKEY"] = "ctrl+nosuchkey"  # restored by isolate_rick_home

    def test_falls_back_to_alt_r(self):
        self.assertEqual(self.hotkey_attempts, ["ctrl+nosuchkey", "alt+r"])
        self.assertEqual(self.book.status, self.ready())


class ChangeKeysWhileRunningTest(AppHarness):
    """The window's "Keys" button (gui.py) calls app.Shortcut: new keys work
    right away, without restarting Rick."""

    def change(self, keys):
        return self.book.shortcut.change(keys)

    def test_new_keys_work_at_once_and_the_old_ones_stop(self):
        self.assertTrue(self.change("Ctrl+K"))
        self.assertEqual(list(self.registered), ["ctrl+k"])  # Alt+R removed
        self.assertEqual(config.get_hotkey(), "ctrl+k")  # still there after a restart
        self.assertEqual(self.book.status, app._t("status_ready", hotkey="Ctrl+K"))
        self.registered["ctrl+k"]()  # idle -> recording, on the new keys
        self.assertEqual(self.book.status, app._t("status_recording", hotkey="Ctrl+K"))

    def test_keys_keyboard_refuses_leave_the_old_ones_working(self):
        self.unknown_to_keyboard.add("ctrl+f12")
        self.assertFalse(self.change("ctrl+f12"))
        self.assertEqual(list(self.registered), ["alt+r"])
        self.assertEqual(config.get_hotkey(), "alt+r")
        self.ask_one_question()
        self.wait_for_status(self.ready())

    def test_current_keys_do_nothing_while_new_ones_are_picked(self):
        self.book.shortcut.pause(True)  # the "Keys" window is open
        self.press()
        self.assertEqual(self.recorder.starts, 0)
        self.book.shortcut.pause(False)
        self.press()
        self.assertEqual(self.book.status, self.recording())

    def test_a_question_under_way_keeps_its_status(self):
        self.press()  # recording
        self.assertTrue(self.change("ctrl+k"))
        self.assertEqual(self.book.status, self.recording())  # not "ready"
        self.registered["ctrl+k"]()  # recording -> thinking, on the new keys
        self.wait_for_status(app._t("status_ready", hotkey="Ctrl+K"))
        self.assertEqual(self.book.turns, [("Elden Ring", self.question, ANSWER)])

    def test_the_window_shows_the_keys_after_a_fallback(self):
        self.assertEqual(self.book.shortcut_shown, 1)
        self.assertEqual(self.book.shortcut.label, "Alt+R")


if __name__ == "__main__":
    unittest.main()
