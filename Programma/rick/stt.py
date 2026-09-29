import logging
import threading

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


def _load_local_model():
    from faster_whisper import WhisperModel

    try:
        return WhisperModel(
            config.WHISPER_MODEL_SIZE,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )
    except Exception:
        # RICK_WHISPER_DEVICE=cuda is a nice speed win on a gaming PC's
        # GPU, but only if CUDA/cuDNN are actually installed - if that
        # load fails for any reason, fall back to CPU instead of crashing
        # Rick entirely over what's meant to be an optional speedup.
        if config.WHISPER_DEVICE == "cpu":
            raise
        # logged, not printed: Rick runs with no console (pythonw)
        log.warning("GPU unavailable for transcription, using the CPU", exc_info=True)
        return WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe(wav_path: str) -> str:
    language = config.get_language()
    model = _get_local_model()
    # vad_filter trims out silence/background noise (useful with game audio
    # bleeding into the mic) so Whisper focuses on the actual speech.
    segments, _info = model.transcribe(wav_path, language=language, vad_filter=True)
    return " ".join(segment.text for segment in segments).strip()
