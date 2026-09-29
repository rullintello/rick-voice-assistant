import contextlib
import logging
import queue
import threading

import miniaudio
import numpy as np
import sounddevice as sd
import soundfile as sf

from . import config, userdata

log = logging.getLogger(__name__)

# sounddevice's play()/wait()/stop() convenience functions share global state
# under the hood - calling them from two threads at once (e.g. a chime on the
# hotkey thread while the previous answer is still mid-playback on the worker
# thread) is a race that can crash. Every playback goes through _play_samples,
# serialized by this lock, so only one is ever in flight.
_playback_lock = threading.Lock()

# Interrupting Rick (Alt+R while he talks) must win even when it lands in the
# gap before his voice actually starts - the mp3 still being decoded, say.
# sd.stop() alone would then stop nothing, and the answer would start a moment
# later, right over (and into) the new recording. So an interrupt also raises
# this flag, and a voice playback checks it atomically with starting (both
# under _interrupt_lock): it's either skipped, or already playing and stopped
# by sd.stop() - never neither.
_interrupt_lock = threading.Lock()
_interrupted = False


def _normalize(audio: np.ndarray, target_peak: float = 0.95, max_gain: float = 8.0) -> np.ndarray:
    """Boosts a quiet recording up to a consistent volume before Whisper sees
    it - a mic that's too quiet (low input volume, sitting far from the
    player) hurts transcription accuracy as much as a bad model choice does.
    Capped so a near-silent clip's noise floor doesn't get blown up."""
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    if peak < 1e-4:
        return audio
    gain = min(target_peak / peak, max_gain)
    return (audio * gain).astype(np.float32)


class Recorder:
    """Push-to-talk style recorder: start() begins capture, stop() writes a wav file."""

    def __init__(self, samplerate: int = config.SAMPLE_RATE, channels: int = 1):
        self.samplerate = samplerate
        self.channels = channels
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        self._queue.put(indata.copy())

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._queue = queue.Queue()
            stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                callback=self._callback,
            )
            # Only remembered once it's really running: a stream that failed
            # to start (mic unplugged, or busy in another app) left behind
            # here would make every later start() think it's already
            # recording, and Rick would never listen again.
            try:
                stream.start()
            except BaseException:
                with contextlib.suppress(Exception):
                    stream.close()
                raise
            self._stream = stream

    def stop(self) -> str:
        with self._lock:
            stream, self._stream = self._stream, None
            if stream is None:
                raise RuntimeError("Recording was never started")
            # Forgotten before stopping, so even a stream that errors out
            # here can't wedge the next start() (see above).
            try:
                stream.stop()
            finally:
                stream.close()

        chunks = []
        while not self._queue.empty():
            chunks.append(self._queue.get())

        if not chunks:
            audio = np.zeros((0, self.channels), dtype="float32")
        else:
            audio = np.concatenate(chunks, axis=0)
            audio = _normalize(audio)

        path = userdata.new_temp_path(".wav")
        try:
            sf.write(path, audio, self.samplerate)
        except BaseException:
            userdata.remove_quietly(path)  # nobody else knows this path yet
            raise
        return path


def arm_playback() -> None:
    """Clears a previous interrupt so the next play_audio() plays. Call it
    when Rick is about to speak a new answer."""
    global _interrupted
    with _interrupt_lock:
        _interrupted = False


def _play_samples(samples: np.ndarray, samplerate: int, interruptible: bool = False) -> None:
    with _playback_lock:
        with _interrupt_lock:
            if interruptible and _interrupted:
                return
            sd.play(samples, samplerate)
        sd.wait()


def play_audio(path: str) -> None:
    """Plays wav/mp3/etc. Uses miniaudio's built-in decoders - no ffmpeg
    install required (that was a recurring setup headache on Windows)."""
    decoded = miniaudio.decode_file(path, output_format=miniaudio.SampleFormat.SIGNED16)
    samples = np.array(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
    if decoded.nchannels > 1:
        samples = samples.reshape((-1, decoded.nchannels))
    _play_samples(samples, decoded.sample_rate, interruptible=True)


def interrupt_playback() -> None:
    """Stops Rick's voice - including one that hasn't started yet (see
    _interrupted) - and blocks until that playback has actually finished
    unwinding, so a chime started right after this call can't race with it
    (see _play_samples). Stays in effect until the next arm_playback()."""
    global _interrupted
    with _interrupt_lock:
        _interrupted = True
        sd.stop()
    if _playback_lock.acquire(timeout=3.0):
        _playback_lock.release()


def _chime_note(frequency: float, duration: float, volume: float) -> np.ndarray:
    """A single bell-like note: fundamental + a quiet octave harmonic, with a
    quick pluck/decay envelope instead of a flat (and easy to miss) tone."""
    t = np.linspace(0, duration, int(config.SAMPLE_RATE * duration), endpoint=False)
    envelope = np.exp(-3.0 * t / duration)
    wave = np.sin(2 * np.pi * frequency * t) + 0.4 * np.sin(2 * np.pi * frequency * 2 * t)
    return (volume * envelope * wave).astype(np.float32)


def _play_chime(frequencies: list[float], note_duration: float = 0.11, volume: float = 0.6) -> None:
    """Chimes are only feedback, so this never raises: with no working
    speakers (unplugged, or grabbed by another app) Rick can still listen and
    write his answers in the book."""
    try:
        notes = np.concatenate([_chime_note(f, note_duration, volume) for f in frequencies])
        _play_samples(notes, config.SAMPLE_RATE)
    except Exception:
        log.warning("Couldn't play a chime", exc_info=True)


def chime_start() -> None:
    """A quick rising magical sparkle - the console isn't visible while a game
    has focus, so this is how you tell recording actually started."""
    _play_chime([659.25, 783.99, 987.77])  # E5 - G5 - B5, rising


def chime_stop() -> None:
    """The same sparkle in reverse - recording captured, done listening."""
    _play_chime([987.77, 783.99, 659.25])  # B5 - G5 - E5, falling
