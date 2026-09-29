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

from rick import app, config

from support import isolate_rick_home, wait_until

ANSWER = "Lo trovi nella palude a nord del castello."


class FakeBook:
    """Stands in for gui.BookWindow: same thread-safe API, no Tk."""

    def __init__(self, language, on_close=None, on_new_chat=None):
        self.language = language
        self.on_new_chat = on_new_chat
        self.game = "Elden Ring"
        self.statuses = []
        self.turns = []
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


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = isolate_rick_home(self)
        self.recorder = FakeRecorder(self.tmp)
        self.rick = FakeRick()
        self.resets = 0
        self.rick.reset_conversation = lambda: setattr(self, "resets", self.resets + 1)
        self.speaker = FakeSpeaker(self.tmp)
        self.question = "dove trovo lo scudo leggendario?"
        hotkeys = {}
        self.workers = []

        def worker_thread(*args, **kwargs):
            thread = threading.Thread(*args, **kwargs)
            self.workers.append(thread)
            return thread

        patches = {
            "keyboard": mock.Mock(add_hotkey=lambda key, cb: hotkeys.__setitem__(key, cb)),
            "threading": types.SimpleNamespace(Thread=worker_thread, Lock=threading.Lock),
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
        self.press = hotkeys[config.HOTKEY]

    # -- helpers ---------------------------------------------------------
    def ready(self):
        return app._t("status_ready", hotkey=config.HOTKEY)

    def recording(self):
        return app._t("status_recording", hotkey=config.HOTKEY)

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
        expected = app._error_status(self.rick.error)
        self.wait_for_status(expected)
        self.assertIn("Gemini non raggiungibile", expected)
        self.assertEqual(self.book.turns, [])  # errors are never saved to a binder
        self.assert_no_temp_files_left()
        # ...and the next Alt+R still works as usual
        self.press()
        self.assertEqual(self.book.status, self.recording())

    def test_long_error_messages_are_shortened_to_one_line(self):
        status = app._error_status(RuntimeError("x" * 500 + "\n{'error': {...}}"))
        self.assertNotIn("\n", status)
        self.assertLess(len(status), 250)
        self.assertEqual(app._error_status(RuntimeError()).count("RuntimeError"), 1)

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

if __name__ == "__main__":
    unittest.main()
