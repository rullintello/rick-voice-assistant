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


if __name__ == "__main__":
    unittest.main()
