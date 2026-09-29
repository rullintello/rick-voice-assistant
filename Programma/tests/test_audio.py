"""rick/audio.py against a fake sounddevice, so no real audio device is
needed: the microphone recorder's error recovery, and interrupting Rick's
voice (including in the moment just before it starts)."""

import threading
import types
import unittest
from unittest import mock

from pathlib import Path

import numpy as np
import soundfile as sf

from rick import audio, config

from support import isolate_rick_home


class FakeSounddevice:
    """sd.play/wait/stop with the same global, one-playback-at-a-time
    semantics as sounddevice's convenience functions."""

    def __init__(self):
        self.played = []
        self.stops = 0
        self.hold = False  # True: a playback lasts until stop()
        self.play_error = None
        self.started = threading.Event()
        self._done = threading.Event()
        self._done.set()
        self.streams = []
        self.stream_start_error = None
        self.stream_stop_error = None

    # -- output ----------------------------------------------------------
    def play(self, samples, samplerate):
        if self.play_error is not None:
            raise self.play_error
        self.played.append(len(samples))
        self._done.clear()
        self.started.set()
        if not self.hold:
            self._done.set()

    def wait(self):
        assert self._done.wait(5), "playback never ended"

    def stop(self):
        self.stops += 1
        self._done.set()

    # -- input -----------------------------------------------------------
    def InputStream(self, samplerate, channels, callback):
        fake = self

        class Stream:
            def __init__(self):
                self.callback = callback
                self.started = self.closed = False
                fake.streams.append(self)

            def start(self):
                if fake.stream_start_error is not None:
                    raise fake.stream_start_error
                self.started = True

            def stop(self):
                if fake.stream_stop_error is not None:
                    raise fake.stream_stop_error
                self.started = False

            def close(self):
                self.closed = True

        return Stream()


class AudioTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = isolate_rick_home(self)
        self.sd = FakeSounddevice()
        patcher = mock.patch.object(audio, "sd", self.sd)
        patcher.start()
        self.addCleanup(patcher.stop)
        audio.arm_playback()  # module state: no interrupt left from another test


class PlaybackTest(AudioTestCase):
    def setUp(self):
        super().setUp()
        self.decoding = threading.Event()
        self.decoded = threading.Event()
        self.decoded.set()

        def decode_file(path, output_format):
            self.decoding.set()
            assert self.decoded.wait(5)
            return types.SimpleNamespace(samples=[0] * 800, nchannels=1, sample_rate=16000)

        patcher = mock.patch.object(audio.miniaudio, "decode_file", decode_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def play_in_background(self):
        thread = threading.Thread(target=audio.play_audio, args=("answer.mp3",))
        thread.start()
        self.addCleanup(thread.join, 5)
        return thread

    def test_voice_plays(self):
        audio.play_audio("answer.mp3")
        self.assertEqual(self.sd.played, [800])

    def test_interrupt_stops_the_voice_and_waits_for_it(self):
        self.sd.hold = True
        thread = self.play_in_background()
        self.assertTrue(self.sd.started.wait(5))
        audio.interrupt_playback()
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertGreaterEqual(self.sd.stops, 1)

    def test_interrupt_just_before_the_voice_starts_still_wins(self):
        # Alt+R pressed while the answer's mp3 is still being decoded: there's
        # nothing for sd.stop() to stop yet, so without the interrupt flag
        # the answer would start right after, over the new recording.
        self.decoded.clear()
        thread = self.play_in_background()
        self.assertTrue(self.decoding.wait(5))
        audio.interrupt_playback()
        self.decoded.set()
        thread.join(5)
        self.assertEqual(self.sd.played, [])

    def test_next_answer_plays_again_once_armed(self):
        audio.interrupt_playback()
        audio.arm_playback()
        audio.play_audio("answer.mp3")
        self.assertEqual(self.sd.played, [800])

    def test_chimes_are_not_silenced_by_an_interrupt(self):
        audio.interrupt_playback()  # right before the "listening" chime
        audio.chime_start()
        self.assertEqual(len(self.sd.played), 1)

    def test_chime_failure_never_raises(self):
        self.sd.play_error = OSError("no output device")
        audio.chime_start()
        audio.chime_stop()


class RecorderTest(AudioTestCase):
    def feed(self, recorder, seconds=0.2, level=0.1):
        frames = int(recorder.samplerate * seconds)
        recorder._stream.callback(np.full((frames, 1), level, dtype="float32"), frames, None, None)

    def test_recording_is_written_to_a_wav_file(self):
        recorder = audio.Recorder()
        recorder.start()
        self.feed(recorder, level=0.5)  # quiet enough to be boosted, loud enough not to hit the gain cap
        path = recorder.stop()
        self.assertEqual(Path(path).parent, config.TEMP_DIR)  # Rick's folder, not the shared temp
        data, samplerate = sf.read(path)
        self.assertEqual(samplerate, recorder.samplerate)
        self.assertEqual(len(data), int(recorder.samplerate * 0.2))
        self.assertAlmostEqual(float(np.abs(data).max()), 0.95, places=2)  # normalized

    def test_a_mic_that_failed_to_start_can_be_retried(self):
        recorder = audio.Recorder()
        self.sd.stream_start_error = OSError("Invalid device")
        with self.assertRaises(OSError):
            recorder.start()
        self.assertTrue(self.sd.streams[0].closed)
        self.sd.stream_start_error = None  # mic plugged back in
        recorder.start()
        self.assertEqual(len(self.sd.streams), 2)  # a real new stream, not a no-op
        self.assertTrue(self.sd.streams[1].started)

    def test_a_stream_that_fails_to_stop_does_not_wedge_the_recorder(self):
        recorder = audio.Recorder()
        recorder.start()
        self.sd.stream_stop_error = OSError("device lost")
        with self.assertRaises(OSError):
            recorder.stop()
        self.assertTrue(self.sd.streams[0].closed)
        self.sd.stream_stop_error = None
        recorder.start()
        self.assertEqual(len(self.sd.streams), 2)

    def test_failed_wav_write_leaves_no_temp_file(self):
        recorder = audio.Recorder()
        recorder.start()
        self.feed(recorder)
        with mock.patch.object(audio.sf, "write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                recorder.stop()
        self.assertEqual(list(config.TEMP_DIR.glob("*")), [])


if __name__ == "__main__":
    unittest.main()
