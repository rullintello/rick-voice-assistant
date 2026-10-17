"""rick/stt.py's local Whisper model loading: the GPU -> CPU fallback."""

import sys
import types
import unittest
from unittest import mock

from rick import config, stt


class FakeWhisperModel:
    calls = []
    fail_on = ()

    def __init__(self, model_size, device, compute_type):
        FakeWhisperModel.calls.append((model_size, device, compute_type))
        if device in FakeWhisperModel.fail_on:
            raise RuntimeError(f"can't load on {device}")


class LocalModelTest(unittest.TestCase):
    def setUp(self):
        FakeWhisperModel.calls = []
        FakeWhisperModel.fail_on = ()
        module = types.ModuleType("faster_whisper")
        module.WhisperModel = FakeWhisperModel
        for patcher in (
            mock.patch.dict(sys.modules, {"faster_whisper": module}),
            mock.patch.object(stt, "_local_model", None),
            mock.patch.object(config, "WHISPER_MODEL_SIZE", "small"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def use_device(self, device, compute_type):
        for patcher in (
            mock.patch.object(config, "WHISPER_DEVICE", device),
            mock.patch.object(config, "WHISPER_COMPUTE_TYPE", compute_type),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_falls_back_to_cpu_when_the_gpu_is_unavailable(self):
        self.use_device("cuda", "float16")
        FakeWhisperModel.fail_on = ("cuda",)
        # logged, not printed: Rick runs without a console
        with self.assertLogs(stt.log, "WARNING"):
            model = stt._get_local_model()
        self.assertIsInstance(model, FakeWhisperModel)
        self.assertEqual(FakeWhisperModel.calls, [("small", "cuda", "float16"), ("small", "cpu", "int8")])

    def test_model_is_loaded_only_once(self):
        self.use_device("cpu", "int8")
        self.assertIs(stt._get_local_model(), stt._get_local_model())
        self.assertEqual(FakeWhisperModel.calls, [("small", "cpu", "int8")])

    def test_cpu_failure_is_raised_not_retried(self):
        self.use_device("cpu", "int8")
        FakeWhisperModel.fail_on = ("cpu",)
        with self.assertRaises(RuntimeError):
            stt._get_local_model()
        self.assertEqual(FakeWhisperModel.calls, [("small", "cpu", "int8")])



class PreloadTest(unittest.TestCase):
    """The model is loaded when Rick starts, not at the first question."""

    def setUp(self):
        self.heard = []
        patcher = mock.patch.object(stt, "_local_model", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_model(self, fail=None):
        test = self

        class Model:
            def transcribe(self, audio, language, vad_filter):
                test.heard.append((len(audio), language, vad_filter))
                if fail:
                    raise fail
                return iter(()), None

        return Model()

    def test_loads_the_model_and_the_silence_filter_once(self):
        model = self.fake_model()
        with mock.patch.object(stt, "_load_local_model", return_value=model) as load, \
                self.assertLogs(stt.log, "INFO") as logged:
            stt.preload()
            self.assertIs(stt._get_local_model(), model)  # the first question finds it ready
        load.assert_called_once()
        self.assertEqual(self.heard, [(16000, config.get_language(), True)])  # a second of silence
        self.assertIn("Speech model ready", logged.output[-1])

    def test_a_failure_is_logged_and_the_first_question_tries_again(self):
        with mock.patch.object(stt, "_load_local_model", side_effect=OSError("no space left")), \
                self.assertLogs(stt.log, "WARNING"):
            stt.preload()  # doesn't raise
        model = self.fake_model()
        with mock.patch.object(stt, "_load_local_model", return_value=model):
            self.assertIs(stt._get_local_model(), model)

    def test_a_failing_warm_up_keeps_the_model(self):
        model = self.fake_model(fail=RuntimeError("onnxruntime missing"))
        with mock.patch.object(stt, "_load_local_model", return_value=model) as load, \
                self.assertLogs(stt.log, "WARNING"):
            stt.preload()
            self.assertIs(stt._get_local_model(), model)
        load.assert_called_once()

    def test_runs_on_a_thread_that_ends_with_rick(self):
        with mock.patch.object(stt, "preload") as preload:
            thread = stt.preload_in_background()
            thread.join(5)
        preload.assert_called_once()
        self.assertTrue(thread.daemon)


if __name__ == "__main__":
    unittest.main()
