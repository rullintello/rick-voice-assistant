"""rick/stt.py's local Whisper model: where its files come from, the GPU ->
CPU fallback, and loading it while Rick starts (rick/warmup.py)."""

import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from rick import config, stt, warmup


class FakeWhisperModel:
    calls = []
    fail_on = ()

    def __init__(self, model_size, device, compute_type):
        FakeWhisperModel.calls.append((model_size, device, compute_type))
        if device in FakeWhisperModel.fail_on:
            raise RuntimeError(f"can't load on {device}")


class FakeHub:
    """faster_whisper.utils.download_model: a local copy of the model, or
    none yet (Hugging Face would then download it)."""

    def __init__(self, test):
        self.asked = []  # local_files_only of each call
        self.local = None  # the folder already downloaded, if any
        self.folder = Path(tempfile.mkdtemp(prefix="rick-model-"))
        test.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def download_model(self, size, local_files_only=False):
        self.asked.append(local_files_only)
        if local_files_only:
            if self.local is None:
                raise FileNotFoundError("not in the local cache")
            return str(self.local)
        (self.folder / "model.bin").write_bytes(b"weights")  # "downloaded"
        return str(self.folder)


class ModelTestCase(unittest.TestCase):
    def setUp(self):
        FakeWhisperModel.calls = []
        FakeWhisperModel.fail_on = ()
        self.hub = FakeHub(self)
        module = types.ModuleType("faster_whisper")
        module.WhisperModel = FakeWhisperModel
        utils = types.ModuleType("faster_whisper.utils")
        utils.download_model = self.hub.download_model
        module.utils = utils
        for patcher in (
            mock.patch.dict(sys.modules, {"faster_whisper": module, "faster_whisper.utils": utils}),
            mock.patch.object(stt, "_local_model", None),
            mock.patch.object(config, "WHISPER_MODEL_SIZE", "small"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)


class ModelFilesTest(ModelTestCase):
    def test_the_downloaded_copy_is_used_without_asking_hugging_face(self):
        self.hub.local = self.hub.folder
        (self.hub.folder / "model.bin").write_bytes(b"weights")
        self.assertEqual(stt._model_files(), str(self.hub.folder))
        self.assertEqual(self.hub.asked, [True])  # local files only: no request

    def test_the_first_start_downloads_it(self):
        self.assertEqual(stt._model_files(), str(self.hub.folder))
        self.assertEqual(self.hub.asked, [True, False])

    def test_a_cut_download_is_downloaded_again(self):
        self.hub.local = self.hub.folder  # the folder is there, model.bin isn't
        self.assertEqual(stt._model_files(), str(self.hub.folder))
        self.assertEqual(self.hub.asked, [True, False])

    def test_a_folder_in_env_is_used_as_it_is(self):
        with mock.patch.object(config, "WHISPER_MODEL_SIZE", str(self.hub.folder)):
            self.assertEqual(stt._model_files(), str(self.hub.folder))
        self.assertEqual(self.hub.asked, [])


class LocalModelTest(ModelTestCase):
    def setUp(self):
        super().setUp()
        self.hub.local = self.hub.folder
        (self.hub.folder / "model.bin").write_bytes(b"weights")
        self.files = str(self.hub.folder)

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
        self.assertEqual(FakeWhisperModel.calls, [(self.files, "cuda", "float16"), (self.files, "cpu", "int8")])

    def test_model_is_loaded_only_once(self):
        self.use_device("cpu", "int8")
        self.assertIs(stt._get_local_model(), stt._get_local_model())
        self.assertEqual(FakeWhisperModel.calls, [(self.files, "cpu", "int8")])

    def test_cpu_failure_is_raised_not_retried(self):
        self.use_device("cpu", "int8")
        FakeWhisperModel.fail_on = ("cpu",)
        with self.assertRaises(RuntimeError):
            stt._get_local_model()
        self.assertEqual(FakeWhisperModel.calls, [(self.files, "cpu", "int8")])



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



class WarmUpTest(unittest.TestCase):
    def test_loads_the_speech_model_then_the_voice_library_on_a_thread_that_ends_with_rick(self):
        loaded = []
        with mock.patch.object(warmup.stt, "preload", lambda: loaded.append("speech model")), \
                mock.patch.object(warmup.tts, "preload", lambda: loaded.append("voice library")):
            thread = warmup.start()
            thread.join(5)
        self.assertEqual(loaded, ["speech model", "voice library"])
        self.assertTrue(thread.daemon)

    def test_the_voice_library_failing_to_load_is_only_logged(self):
        with mock.patch.dict(sys.modules, {"edge_tts": None}), self.assertLogs(warmup.tts.log, "WARNING"):
            warmup.tts.preload()  # doesn't raise: the first answer tries again


if __name__ == "__main__":
    unittest.main()
