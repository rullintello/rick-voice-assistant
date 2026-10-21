import logging
import os
import threading
import time

from . import config

log = logging.getLogger(__name__)

_local_model = None
_model_lock = threading.Lock()  # loading takes seconds: never do it twice at once


def _get_local_model():
    global _local_model
    with _model_lock:
        if _local_model is None:
            _local_model = _load_local_model()
    return _local_model


def _model_files() -> str:
    """The folder with the speech model's files: the copy downloaded on the
    first start. Hugging Face is asked only when there's no complete copy
    yet. Asking it at every start (whether the model changed) was a request
    each time, and a wait for its timeout when offline."""
    from faster_whisper.utils import download_model

    model = config.WHISPER_MODEL_SIZE
    if os.path.isdir(model):  # RICK_WHISPER_MODEL_SIZE can name a folder
        return model
    try:
        files = download_model(model, local_files_only=True)
    except Exception:  # not downloaded yet
        files = None
    if not files or not os.path.isfile(os.path.join(files, "model.bin")):  # missing, or a cut download
        files = download_model(model)
    return files


def _load_local_model():
    from faster_whisper import WhisperModel

    files = _model_files()
    try:
        return WhisperModel(files, device=config.WHISPER_DEVICE, compute_type=config.WHISPER_COMPUTE_TYPE)
    except Exception:
        # RICK_WHISPER_DEVICE=cuda is a nice speed win on a gaming PC's
        # GPU, but only if CUDA/cuDNN are actually installed - if that
        # load fails for any reason, fall back to CPU instead of crashing
        # Rick entirely over what's meant to be an optional speedup.
        if config.WHISPER_DEVICE == "cpu":
            raise
        # logged, not printed: Rick runs with no console (pythonw)
        log.warning("GPU unavailable for transcription, using the CPU", exc_info=True)
        return WhisperModel(files, device="cpu", compute_type="int8")


def preload() -> None:
    """Gets the speech model ready before the first question: loading it
    takes seconds on a CPU (more the first time, while Windows scans the
    freshly installed libraries, and much more on the very first start,
    when it's downloaded), which the player would otherwise wait through
    after their first question. A second of silence also loads the filter
    that skips silence (vad_filter below), without running Whisper itself.
    A failure is only logged: the first question tries again and says why."""
    started = time.monotonic()
    try:
        import numpy as np

        segments, _info = _get_local_model().transcribe(
            np.zeros(16000, dtype=np.float32), language=config.get_language(), vad_filter=True
        )
        list(segments)
    except Exception:
        log.warning("Couldn't get the speech model ready in advance", exc_info=True)
        return
    log.info("Speech model ready in %.1fs", time.monotonic() - started)


def transcribe(wav_path: str) -> str:
    language = config.get_language()
    model = _get_local_model()
    # vad_filter trims out silence/background noise (useful with game audio
    # bleeding into the mic) so Whisper focuses on the actual speech.
    segments, _info = model.transcribe(wav_path, language=language, vad_filter=True)
    return " ".join(segment.text for segment in segments).strip()
