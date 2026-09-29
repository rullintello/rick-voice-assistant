import logging
import threading
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from . import config, history, search

# The SDK logs a one-time warning recommending Chat.send_message over
# Models.generate_content for "automatic function calling" - it fires
# regardless of whether tools/functions are actually configured (Rick uses
# none), so it's just noise here, not a real problem. Silencing only this
# logger keeps real errors from it visible.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

# Gemini occasionally returns these for a few seconds under heavy load
# ("high demand ... usually temporary" per Google's own error message) -
# a short retry clears most of them instead of failing the whole turn.
_RETRYABLE_CODES = {429, 500, 503}
_MAX_RETRIES = 2
_RETRY_DELAY_SECONDS = 1.5

SYSTEM_PROMPT_IT = """Sei Rick, un assistente vocale che aiuta un giocatore in tempo reale mentre gioca ai videogiochi.

Regole:
- Rispondi sempre in italiano, con frasi brevi e naturali: la tua risposta verrà letta ad alta voce da un sintetizzatore vocale, quindi niente markdown, elenchi puntati, tabelle o formattazioni.
- Se il giocatore non sa come procedere, dagli indicazioni pratiche sul prossimo passo (dove andare, cosa fare, chi parlare).
- Se chiede dove trovare un oggetto raro o un collezionabile, fornisci la posizione più precisa che conosci (area/zona, missione, boss, NPC, condizioni particolari per ottenerlo).
- Se non conosci con certezza la risposta per quel gioco o per quella versione/DLC, dillo onestamente invece di inventare, e chiedi il dettaglio che ti manca (nome del gioco, capitolo, area attuale) invece di rispondere a vuoto.
- Vai dritto al punto: 1-2 frasi, massimo 3 solo se davvero servono per spiegare bene il percorso o la posizione. Niente premesse o ripetizioni della domanda: la prima frase deve già contenere l'informazione utile. Approfondisci solo se il giocatore chiede esplicitamente più dettagli.
- Ricorda il gioco e i dettagli che il giocatore ti ha già detto nella conversazione, senza chiederli di nuovo.
- Se trovi una sezione "Cronologia salvata per questo gioco", contiene le tue risposte precedenti su questo stesso gioco (anche di sessioni passate): usale per restare coerente, non ripeterti e rispondere subito se la domanda riguarda qualcosa che avevi già spiegato.
- Se nel messaggio del giocatore trovi una sezione "Risultati di ricerca web", usali per rispondere in modo preciso e aggiornato: parla come se lo sapessi già, senza dire frasi tipo "secondo i risultati di ricerca". Se quella sezione non c'è, rispondi comunque al meglio delle tue conoscenze.
- Se la trascrizione della domanda sembra confusa o con parole senza senso (errori di riconoscimento vocale), prova comunque a capire cosa intendeva il giocatore dal contesto della conversazione; se proprio non riesci, chiedi di ripetere."""

SYSTEM_PROMPT_EN = """You are Rick, a voice assistant that helps a player in real time while they play video games.

Rules:
- Always reply in English, in short natural sentences: your reply will be read aloud by a speech synthesizer, so no markdown, bullet points, tables, or other formatting.
- If the player doesn't know how to proceed, give them practical next steps (where to go, what to do, who to talk to).
- If they ask where to find a rare item or collectible, give the most precise location you know (area/zone, quest, boss, NPC, any special conditions to get it).
- If you're not sure about the answer for that game or that version/DLC, say so honestly instead of making it up, and ask for the missing detail (game title, chapter, current area) instead of answering blindly.
- Get straight to the point: 1-2 sentences, 3 at most and only if you genuinely need them to explain a route or location clearly. No preamble or restating the question: the first sentence should already carry the useful information. Go into more detail only if the player explicitly asks for it.
- Remember the game and details the player already told you in the conversation, don't ask again.
- If you find a "Saved history for this game" section, it has your own past answers about this same game (even from earlier sessions): use it to stay consistent, avoid repeating yourself, and answer right away if the question is about something you already explained.
- If the player's message has a "Web search results" section, use it to answer precisely and up to date: talk as if you already knew it, without saying things like "according to the search results". If that section isn't there, just answer from your own knowledge as best you can.
- If the transcribed question looks confused or has nonsensical words (speech recognition errors), still try to figure out what the player meant from the conversation's context; only if you really can't, ask them to repeat."""

_WEB_RESULTS_LABEL = {"it": "Risultati di ricerca web", "en": "Web search results"}
_SAVED_HISTORY_LABEL = {"it": "Cronologia salvata per questo gioco", "en": "Saved history for this game"}
_QA_PREFIX = {"it": ("D", "R"), "en": ("Q", "A")}
_EMPTY_ANSWER = {
    "it": "Gemini ha restituito una risposta vuota, riprova.",
    "en": "Gemini returned an empty answer, please try again.",
}


class EmptyAnswerError(RuntimeError):
    """Gemini replied with no text (e.g. a safety block). Raised instead of
    returning "" so an empty answer is never spoken, saved to a binder, or
    kept in the conversation (where an empty turn breaks later requests)."""


def _user_turn(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


class Rick:
    def __init__(self):
        self._client = genai.Client(api_key=config.get_gemini_api_key())
        # Recent turns of the CURRENT conversation only: cleared whenever
        # the game changes or a new chat starts, so one game's context never
        # leaks into another's.
        self._history: list[types.Content] = []
        self._history_game: str | None = None
        self._reset_requested = False
        # main.py's state machine already guarantees only one ask() runs at a
        # time, but a lock here means that invariant can never silently break
        # (e.g. a future change) and corrupt the shared conversation history.
        self._lock = threading.Lock()

    def reset_conversation(self) -> None:
        """Forget the current conversation (the GUI's "New chat"). Safe to
        call from any thread and never blocks: it only raises a flag that the
        next ask() acts on, so the window can't freeze waiting for an ask()
        that's still talking to Gemini."""
        self._reset_requested = True

    def ask(self, question: str, game: str = "") -> str:
        with self._lock:
            if self._reset_requested or game != self._history_game:
                self._history = []
                self._history_game = game
                self._reset_requested = False

            self._history.append(_user_turn(question))
            self._trim_history()
            try:
                return self._ask_locked(question, game)
            except BaseException:
                # Drop the question that got no answer, so the conversation
                # keeps alternating user/model instead of stacking user turns.
                if self._history and self._history[-1].role == "user":
                    self._history.pop()
                raise

    def _trim_history(self) -> None:
        """Keeps the last MAX_HISTORY_TURNS messages, always starting on a
        user turn - cutting at a fixed count would otherwise leave an answer
        whose question was dropped at the front."""
        limit = max(config.MAX_HISTORY_TURNS, 1)
        del self._history[:-limit]
        while self._history and self._history[0].role != "user":
            self._history.pop(0)

    def _session_pairs(self) -> set[tuple[str, str]]:
        """(question, answer) pairs already in the current conversation."""
        pairs = set()
        for user, model in zip(self._history, self._history[1:]):
            if user.role == "user" and model.role == "model":
                pairs.add((user.parts[0].text, model.parts[0].text))
        return pairs

    def _saved_history_section(self, game: str, language: str) -> str:
        """Per-game memory that survives restarts (rick/history.py, what the
        GUI's binders show): lets Rick answer what it already answered in an
        earlier session without a fresh web search. Skipped for the untitled
        bucket, which can mix many games, and leaves out the Q&As already in
        the current conversation so they aren't sent twice."""
        limit = config.MAX_SAVED_HISTORY_ENTRIES
        if limit <= 0 or history.is_untitled(game):
            return ""
        in_conversation = self._session_pairs()
        saved = [
            e
            for e in history.get_game_history(game)
            if isinstance(e, dict)
            and e.get("question")
            and e.get("answer")
            and (e["question"], e["answer"]) not in in_conversation
        ][-limit:]
        if not saved:
            return ""
        q_label, a_label = _QA_PREFIX[language]
        lines = "\n".join(f"{q_label}: {e['question']}\n{a_label}: {e['answer']}" for e in saved)
        return f"\n\n[{_SAVED_HISTORY_LABEL[language]}]\n{lines}"

    def _ask_locked(self, question: str, game: str) -> str:
        language = config.get_language()
        contents = list(self._history)
        extra_sections = self._saved_history_section(game, language)

        if config.ENABLE_WEB_SEARCH:
            # "silver key" alone finds (and caches) results for whichever game
            # ranks first - the game name makes both the search and its cache
            # entry specific to the game actually being played.
            query = question if history.is_untitled(game) else f"{game} {question}"
            web_context = search.search_web(query)
            if web_context:
                extra_sections += f"\n\n[{_WEB_RESULTS_LABEL[language]}]\n{web_context}"

        if extra_sections:
            contents[-1] = _user_turn(f"{question}{extra_sections}")

        system_prompt = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_IT
        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            # Shorter answers (see system prompt) means this budget can
            # come down too - it caps worst-case generation+TTS latency
            # without risking real answers getting cut off mid-sentence.
            max_output_tokens=350,
            # Rick needs quick, short spoken answers, not deep reasoning -
            # minimal thinking keeps latency down and leaves the output
            # budget for the actual answer instead of invisible "thoughts".
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
        )

        last_exc: genai_errors.APIError | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._client.models.generate_content(
                    model=config.GEMINI_MODEL, contents=contents, config=gen_config
                )
                break
            except genai_errors.APIError as exc:
                if exc.code not in _RETRYABLE_CODES or attempt == _MAX_RETRIES:
                    raise
                last_exc = exc
                time.sleep(_RETRY_DELAY_SECONDS * (attempt + 1))
        else:
            raise last_exc  # pragma: no cover - loop always breaks or raises above

        answer = (response.text or "").strip()
        if not answer:
            raise EmptyAnswerError(_EMPTY_ANSWER[language])
        self._history.append(types.Content(role="model", parts=[types.Part(text=answer)]))
        return answer
