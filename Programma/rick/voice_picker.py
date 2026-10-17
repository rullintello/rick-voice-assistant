"""The "Rick's voice" row of the settings window: a list of the voices for
the language picked (rick/voices.py) and a Try button that says a short
line with the selected one."""

import logging
import os
import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import voices
from .hotkey_picker import NOTE_COLOR
from .startup import describe_error

log = logging.getLogger(__name__)

STRINGS = {
    "it": {
        "label": "Voce di Rick:",
        "try": "▶ Prova",
        "trying": "Rick si schiarisce la voce...",
        "note": "Cambia subito, anche con Rick aperto.",
        "backup": "Microsoft non risponde adesso: questa e' la voce di riserva di Windows.",
        "failed": "Non riesco a farlo parlare adesso: {reason}",
        "locked": "Decisa dal file .env (RICK_EDGE_VOICE): per cambiarla modifica quel file.",
    },
    "en": {
        "label": "Rick's voice:",
        "try": "▶ Try",
        "trying": "Rick is clearing his throat...",
        "note": "Changes right away, even with Rick open.",
        "backup": "Microsoft isn't answering right now: this is Windows' backup voice.",
        "failed": "Can't make him speak right now: {reason}",
        "locked": "Set by the .env file (RICK_EDGE_VOICE): edit that file to change it.",
    },
}


def say_sample(language: str, voice: voices.Voice) -> bool:
    """Says voices.SAMPLE with `voice`. Returns False when Microsoft didn't
    answer and Windows' backup voice spoke instead."""
    from . import audio, tts

    path = tts.synthesize(voices.SAMPLE[language], voice=voice)
    try:
        audio.interrupt_playback()
        audio.arm_playback()
        audio.play_audio(path)
    finally:
        if os.path.exists(path):
            os.remove(path)
    return path.endswith(".mp3")


class VoicePicker:
    """Builds the row inside `parent` (pack self.frame to show it).
    `picked` maps a language to the voice id saved for it. `locked_voice`
    (RICK_EDGE_VOICE set in .env) is shown, and tried, instead of a choice.
    `say(language, voice)` speaks a sample (say_sample unless a test swaps it)."""

    def __init__(self, parent, language: str, picked: dict | None = None, locked_voice=None, say=None):
        self.locked_voice = locked_voice
        self.locked = locked_voice is not None
        self._picked = dict(picked or {})
        self._say = say or say_sample
        self._language = language
        self._busy = False

        self.frame = tk.Frame(parent)
        self._title = tk.Label(self.frame, font=("Segoe UI", 11), justify="center")
        self._title.pack(pady=(2, 4))
        row = tk.Frame(self.frame)
        row.pack()
        self.choice = ttk.Combobox(row, state="disabled" if self.locked else "readonly", width=32, font=("Segoe UI", 10))
        self.choice.pack(side="left", padx=(0, 8))
        self.choice.bind("<<ComboboxSelected>>", lambda _event: self._remember())
        self.button = tk.Button(row, font=("Segoe UI", 10), padx=10, command=self.try_voice)
        self.button.pack(side="left")
        self.hint = tk.Label(self.frame, font=("Segoe UI", 9), fg=NOTE_COLOR, justify="center", wraplength=420)
        self.hint.pack(pady=(2, 0))
        self.set_language(language)

    @property
    def voice_id(self) -> str | None:
        """The voice selected for the language the window is set to (None
        when .env decides it: nothing to save)."""
        return None if self.locked else self.voice.id

    @property
    def voice(self) -> voices.Voice:
        if self.locked:
            return self.locked_voice
        return voices.find(self._language, self._picked.get(self._language))

    def set_language(self, language: str) -> None:
        self._language = language
        self._strings = STRINGS[language if language in STRINGS else "it"]
        choices = () if self.locked else voices.for_language(language)
        self.choice.configure(values=[voice.label for voice in choices])
        self.choice.set(self.voice.label)
        self._title.config(text=self._strings["label"])
        self.button.config(text=self._strings["try"])
        self._show_note()

    def _remember(self) -> None:
        label = self.choice.get()
        for voice in voices.for_language(self._language):
            if voice.label == label:
                self._picked[self._language] = voice.id

    def _show_note(self, text: str | None = None, color: str = NOTE_COLOR) -> None:
        if text is None:
            text = self._strings["locked" if self.locked else "note"]
        self.hint.config(text=text, fg=color)

    def try_voice(self) -> None:
        """Says a short line with the selected voice, on a worker thread (it
        takes a second or two): the window stays usable meanwhile. The worker
        never touches Tk itself: it leaves the outcome in a queue that the
        window checks, which works whether or not Tk's mainloop is running."""
        if self._busy:
            return
        self._busy = True
        self.button.config(state="disabled")
        self._show_note(self._strings["trying"])
        language, voice, strings = self._language, self.voice, self._strings
        outcome: "queue.Queue" = queue.Queue()

        def work() -> None:
            try:
                online = self._say(language, voice)
                outcome.put((None, NOTE_COLOR) if online else (strings["backup"], "#b06000"))
            except Exception as exc:
                log.warning("Voice sample failed", exc_info=True)
                outcome.put((strings["failed"].format(reason=describe_error(exc, limit=80)), "red"))

        def check() -> None:
            try:
                text, color = outcome.get_nowait()
            except queue.Empty:
                self.frame.after(50, check)
                return
            self._done(text, color)

        threading.Thread(target=work, daemon=True).start()
        self.frame.after(50, check)

    def _done(self, text, color) -> None:
        self._busy = False
        if not self.frame.winfo_exists():
            return
        self.button.config(state="normal")
        self._show_note(text, color)
