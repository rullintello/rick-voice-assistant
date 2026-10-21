"""What's slow to load the first time, loaded on a background thread while
Rick starts, so the first question doesn't wait for it: the speech model
(stt.preload) and the online voice's library (tts.preload)."""

import threading

from . import stt, tts


def warm_up() -> None:
    stt.preload()
    tts.preload()


def start() -> threading.Thread:
    """warm_up() on its own thread, which ends with Rick."""
    thread = threading.Thread(target=warm_up, name="warm-up", daemon=True)
    thread.start()
    return thread
