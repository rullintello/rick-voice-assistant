import logging
import os
import threading

import keyboard

from . import config, hotkeys, userdata
from .audio import Recorder, arm_playback, chime_start, chime_stop, interrupt_playback, play_audio
from .brain import Rick
from .gui import BookWindow
from .startup import describe_error, show_error_dialog
from .stt import transcribe
from .tts import synthesize

STRINGS = {
    "it": {
        "status_ready": "📖 Pronto — premi {hotkey} per parlare con Rick.",
        "status_recording": "🎙️ In ascolto... premi {hotkey} di nuovo per fermarti.",
        "status_transcribing": "✍️ Trascrizione in corso...",
        "status_thinking": "🤔 Rick sta pensando...",
        "status_speaking": "🗣️ Rick ti risponde...",
        "status_nothing_heard": "Non ho sentito nulla, riprova.",
        "status_error": "⚠️ {error} — premi {hotkey} per riprovare.",
        "error_speech": "Scusa, ho avuto un problema a risponderti. Riprova tra un attimo.",
        "need_gemini_key": "Serve una chiave Gemini per usare Rick.",
    },
    "en": {
        "status_ready": "📖 Ready — press {hotkey} to talk to Rick.",
        "status_recording": "🎙️ Listening... press {hotkey} again to stop.",
        "status_transcribing": "✍️ Transcribing...",
        "status_thinking": "🤔 Rick is thinking...",
        "status_speaking": "🗣️ Rick is answering...",
        "status_nothing_heard": "I didn't hear anything, try again.",
        "status_error": "⚠️ {error} — press {hotkey} to try again.",
        "error_speech": "Sorry, I had trouble answering. Please try again in a moment.",
        "need_gemini_key": "Rick needs a Gemini key to work.",
    },
}


def _t(key: str, **kwargs) -> str:
    text = STRINGS[config.get_language()][key]
    return text.format(**kwargs) if kwargs else text


def _error_status(exc: BaseException, key_label: str) -> str:
    return _t("status_error", error=describe_error(exc), hotkey=key_label)


def ensure_api_keys() -> None:
    if config.get_gemini_api_key():
        return

    from .setup_gui import ask_for_api_keys

    keys = ask_for_api_keys(
        prefill={
            "hotkey": config.get_hotkey(),
            "hotkey_locked": config.hotkey_set_in_env(),
            "locked_voice": config.get_voice() if config.voice_set_in_env() else None,
        }
    )
    if not keys["gemini"]:
        show_error_dialog("Rick", STRINGS[keys.get("language", "it")]["need_gemini_key"])
        raise SystemExit(0)
    config.save_gemini_api_key(keys["gemini"])
    if keys["tavily"]:
        config.save_tavily_api_key(keys["tavily"])
    config.save_language(keys.get("language", "it"))
    if keys.get("hotkey"):
        config.save_hotkey(keys["hotkey"])
    if keys.get("voice"):
        config.save_voice(keys.get("language", "it"), keys["voice"])


class Shortcut:
    """The keys that start/stop listening (Alt+R unless the player picked
    others): registered with keyboard by start(), and changeable while Rick
    runs, from the "Keys" button of the window (see gui.py)."""

    def __init__(self):
        self.keys = config.get_hotkey()
        self.locked = config.hotkey_set_in_env()
        self.on_changed = None  # called after change() switched the keys
        self._on_press = None
        self._remove = None
        self._paused = threading.Event()

    @property
    def label(self) -> str:
        """How the window and the status bar name the keys, e.g. "Alt+R"."""
        return hotkeys.label(self.keys)

    def start(self, on_press) -> None:
        self._on_press = on_press
        try:
            self._remove = self._register(self.keys)
        except ValueError:
            # a name keyboard doesn't know (typed by hand as RICK_HOTKEY in
            # .env): Rick still starts, on Alt+R, and the status bar says so
            logging.exception("Can't use %r as the shortcut, using %s", self.keys, hotkeys.DEFAULT)
            self.keys = hotkeys.DEFAULT
            self._remove = self._register(self.keys)

    def _register(self, keys: str):
        # a new function each time: keyboard files its hotkeys by callback
        # too, so sharing one between the old and new keys would mix them up
        return keyboard.add_hotkey(keys, lambda: self._pressed())

    def _pressed(self) -> None:
        if not self._paused.is_set():
            self._on_press()

    def pause(self, paused: bool) -> None:
        """While the player is picking new keys, pressing the current ones
        must not start a recording."""
        if paused:
            self._paused.set()
        else:
            self._paused.clear()

    def change(self, keys: str) -> bool:
        """Switches to `keys` (accepted by hotkeys.parse) and saves them.
        The new keys are registered before the old ones are removed, so if
        keyboard refuses them Rick keeps working on the old ones (-> False)."""
        keys = hotkeys.parse(keys)
        if keys != self.keys:
            try:
                remove_new = self._register(keys)
            except ValueError:
                logging.exception("Can't use %r as the shortcut, keeping %s", keys, self.keys)
                return False
            remove_old, self._remove, self.keys = self._remove, remove_new, keys
            try:
                remove_old()
            except Exception:  # the new keys work: not worth failing over
                logging.exception("Couldn't remove the old shortcut")
        config.save_hotkey(keys)
        if self.on_changed:
            self.on_changed()
        return True


def main() -> None:
    userdata.purge_leftover_temp_files()
    ensure_api_keys()

    rick = Rick()
    recorder = Recorder()
    shortcut = Shortcut()
    book = BookWindow(
        language=config.get_language(),
        on_close=lambda: os._exit(0),
        on_new_chat=rick.reset_conversation,
        shortcut=shortcut,
    )

    def ready_status() -> str:
        return _t("status_ready", hotkey=shortcut.label)

    # stage: "idle" -> "recording" -> "thinking" -> "speaking" -> "idle"
    # (o "speaking" -> "recording" direttamente, se interrotto con Alt+R).
    # turn: cresce a ogni nuova registrazione. Il thread che elabora una
    # domanda ricorda il proprio turno e tocca stage/stato solo finche' e'
    # ancora quello attuale: un thread interrotto che finisce in ritardo non
    # puo' cosi' sovrascrivere il turno successivo.
    state = {"stage": "idle", "turn": 0}
    lock = threading.Lock()

    def start_recording() -> None:
        chime_start()
        recorder.start()  # se fallisce (niente microfono) lo stage non cambia
        state["turn"] += 1
        state["stage"] = "recording"
        book.set_status(_t("status_recording", hotkey=shortcut.label))

    def show_status(turn: int, text: str) -> None:
        with lock:
            if state["turn"] == turn:
                book.set_status(text)

    def finish_turn(turn: int, status: str | None = None) -> None:
        """Riporta lo stage a "idle" e mostra `status` (di default "pronto"),
        a meno che nel frattempo non sia gia' partito un nuovo turno (Alt+R
        premuto per interrompere Rick mentre parlava)."""
        with lock:
            if state["turn"] == turn:
                state["stage"] = "idle"
                book.set_status(status or ready_status())

    def speak(text: str, turn: int) -> None:
        """Unico punto che fa "parlare" Rick: sintetizza, passa a "speaking"
        solo se il turno e' ancora nostro, riproduce, e ripulisce sempre il
        file temporaneo. Usato sia per le risposte normali sia per i messaggi
        di errore/silenzio, cosi' la transizione di stato non va duplicata
        (e potenzialmente dimenticata) in piu' punti."""
        path = None
        try:
            path = synthesize(text)
            with lock:
                if state["turn"] != turn:
                    return  # interrotto/riavviato nel frattempo
                state["stage"] = "speaking"
                # sotto lo stesso lock di on_hotkey: un'interruzione arriva
                # per forza dopo, quindi non puo' venire annullata da questa
                arm_playback()
                book.set_status(_t("status_speaking"))
            play_audio(path)
        finally:
            if path and os.path.exists(path):
                os.remove(path)

    def process_recording(turn: int) -> None:
        wav_path = None
        final_status = None
        try:
            wav_path = recorder.stop()
            chime_stop()
            show_status(turn, _t("status_transcribing"))
            question = transcribe(wav_path)
            if not question:
                show_status(turn, _t("status_nothing_heard"))
                speak(_t("status_nothing_heard"), turn)
                return

            # capturing the active game now (not after rick.ask() returns)
            # so switching games while Rick is thinking can't file this
            # answer under the wrong binder
            game = book.current_game()
            show_status(turn, _t("status_thinking"))
            answer = rick.ask(question, game)
            book.append_turn(game, question, answer)
            speak(answer, turn)
        except Exception as exc:  # keep the assistant alive across errors
            logging.exception("Error handling a turn")
            # stays in the status bar after the spoken apology, until the
            # next Alt+R, so what went wrong can actually be read
            final_status = _error_status(exc, shortcut.label)
            show_status(turn, final_status)
            try:
                speak(_t("error_speech"), turn)
            except Exception:
                logging.exception("Error while trying to speak the error message")
        finally:
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)
            finish_turn(turn, final_status)

    def handle_hotkey() -> None:
        stage = state["stage"]

        if stage == "idle":
            start_recording()

        elif stage == "recording":
            state["stage"] = "thinking"
            threading.Thread(target=process_recording, args=(state["turn"],), daemon=True).start()

        elif stage == "speaking":
            interrupt_playback()  # ferma solo la voce di Rick, non la registrazione
            start_recording()

        # stage == "thinking": Rick sta ancora elaborando la risposta, ignora

    def on_hotkey() -> None:
        # keyboard chiama questa funzione sul proprio thread, senza gestione
        # errori: un'eccezione non presa (es. microfono staccato o occupato)
        # ucciderebbe quel thread, e Alt+R smetterebbe di funzionare in
        # silenzio fino al riavvio di Rick.
        with lock:
            try:
                handle_hotkey()
            except Exception as exc:
                logging.exception("Error handling %s", shortcut.keys)
                if state["stage"] == "speaking":
                    # interrotto ma la nuova registrazione non e' partita:
                    # il turno finisce qui, e il thread della risposta non
                    # deve rimettere "pronto" sopra all'errore
                    state["turn"] += 1
                    state["stage"] = "idle"
                book.set_status(_error_status(exc, shortcut.label))

    def show_new_keys() -> None:
        # the "ready" line names the keys: refresh it, unless a question is
        # under way (its own status comes back to "ready" when it's done)
        with lock:
            if state["stage"] == "idle":
                book.set_status(ready_status())

    shortcut.start(on_hotkey)
    shortcut.on_changed = show_new_keys
    book.show_shortcut()  # start() may have fallen back to Alt+R
    book.set_status(ready_status())
    book.run()
