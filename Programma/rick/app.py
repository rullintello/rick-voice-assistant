import logging
import os
import threading

import keyboard

from . import config, userdata
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


def _error_status(exc: BaseException) -> str:
    return _t("status_error", error=describe_error(exc), hotkey=config.HOTKEY)


def ensure_api_keys() -> None:
    if config.get_gemini_api_key():
        return

    from .setup_gui import ask_for_api_keys

    keys = ask_for_api_keys()
    if not keys["gemini"]:
        show_error_dialog("Rick", STRINGS[keys.get("language", "it")]["need_gemini_key"])
        raise SystemExit(0)
    config.save_gemini_api_key(keys["gemini"])
    if keys["tavily"]:
        config.save_tavily_api_key(keys["tavily"])
    config.save_language(keys.get("language", "it"))


def main() -> None:
    userdata.purge_leftover_temp_files()
    ensure_api_keys()

    rick = Rick()
    recorder = Recorder()
    book = BookWindow(
        language=config.get_language(),
        on_close=lambda: os._exit(0),
        on_new_chat=rick.reset_conversation,
    )

    def ready_status() -> str:
        return _t("status_ready", hotkey=config.HOTKEY)

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
        book.set_status(_t("status_recording", hotkey=config.HOTKEY))

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
            final_status = _error_status(exc)
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
                logging.exception("Error handling %s", config.HOTKEY)
                if state["stage"] == "speaking":
                    # interrotto ma la nuova registrazione non e' partita:
                    # il turno finisce qui, e il thread della risposta non
                    # deve rimettere "pronto" sopra all'errore
                    state["turn"] += 1
                    state["stage"] = "idle"
                book.set_status(_error_status(exc))

    keyboard.add_hotkey(config.HOTKEY, on_hotkey)
    book.set_status(ready_status())
    book.run()
