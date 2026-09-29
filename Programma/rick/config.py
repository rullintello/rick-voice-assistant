import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from . import jsonstore

# Only Rick's own .env (next to main.py). Called with no path, load_dotenv
# also searches every parent folder - so a .env left by some other project
# higher up (with its own keys) could silently take over Rick's settings.
DOTENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(DOTENV_FILE)


def _env_int(name: str, default: int) -> int:
    """A blank or malformed number in .env (e.g. "RICK_SAMPLE_RATE=") falls
    back to the default instead of crashing Rick at import time."""
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.getLogger(__name__).warning("Ignoring invalid %s=%r, using %s", name, raw, default)
        return default


HOTKEY = os.getenv("RICK_HOTKEY", "alt+r")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
ENABLE_WEB_SEARCH = os.getenv("RICK_ENABLE_WEB_SEARCH", "true").strip().lower() in ("1", "true", "yes")

# Per-user key storage so a friend you share the project with only has to
# paste their keys once, in the first-run dialog (see rick/setup_gui.py) -
# saved outside the project folder, never committed to git.
USER_CONFIG_FILE = Path.home() / ".rick" / "config.json"

# Web search results are cached (per normalized question) so repeat questions
# don't re-spend Tavily's free quota.
SEARCH_CACHE_FILE = Path.home() / ".rick" / "search_cache.json"
SEARCH_CACHE_TTL_HOURS = _env_int("RICK_SEARCH_CACHE_TTL_HOURS", 24 * 7)

# Conversation history, saved locally and organized by game title (see
# rick/history.py and the "binders" sidebar in the GUI).
HISTORY_FILE = Path.home() / ".rick" / "history.json"

# Temporary audio (the player's recorded question, Rick's spoken answer) -
# see rick/userdata.py.
TEMP_DIR = Path.home() / ".rick" / "tmp"


def _load_user_config() -> dict:
    data = jsonstore.read_json(USER_CONFIG_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_user_config_key(field: str, value: str) -> None:
    data = _load_user_config()
    data[field] = value.strip()
    jsonstore.write_json(USER_CONFIG_FILE, data)


def get_gemini_api_key() -> str:
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    return _load_user_config().get("gemini_api_key", "").strip()


def save_gemini_api_key(key: str) -> None:
    _save_user_config_key("gemini_api_key", key)


def get_tavily_api_key() -> str:
    env_key = os.getenv("TAVILY_API_KEY", "").strip()
    if env_key:
        return env_key
    return _load_user_config().get("tavily_api_key", "").strip()


def save_tavily_api_key(key: str) -> None:
    _save_user_config_key("tavily_api_key", key)


def get_language() -> str:
    """Returns "it" or "en". Checked in order: RICK_LANGUAGE env var, the
    choice saved from the first-run dialog, then "it" as the default."""
    env_lang = os.getenv("RICK_LANGUAGE", "").strip().lower()
    if env_lang in ("it", "en"):
        return env_lang
    stored = _load_user_config().get("language", "").strip().lower()
    if stored in ("it", "en"):
        return stored
    return "it"


def save_language(language: str) -> None:
    _save_user_config_key("language", language)


WHISPER_MODEL_SIZE = os.getenv("RICK_WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.getenv("RICK_WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("RICK_WHISPER_COMPUTE_TYPE", "int8")

# it-IT-ElsaNeural / en-US-JennyNeural both read as natural adult female
# voices (circa 25-30). it-IT-IsabellaNeural is the only other free Italian
# voice but sounds more childish/youthful.
_DEFAULT_EDGE_VOICE = {"it": "it-IT-ElsaNeural", "en": "en-US-JennyNeural"}


def get_edge_voice() -> str:
    override = os.getenv("RICK_EDGE_VOICE", "").strip()
    return override or _DEFAULT_EDGE_VOICE[get_language()]


EDGE_PITCH = os.getenv("RICK_EDGE_PITCH", "+0Hz")
EDGE_RATE = os.getenv("RICK_EDGE_RATE", "+0%")

SAMPLE_RATE = _env_int("RICK_SAMPLE_RATE", 16000)
MAX_HISTORY_TURNS = _env_int("RICK_MAX_HISTORY_TURNS", 12)

# How many of a game's saved Q&A pairs (see rick/history.py) get fed back to
# Gemini as context - lets Rick answer from its own past answers on that
# game instead of always needing a fresh web search. Capped so a game
# played for months doesn't balloon every single prompt.
MAX_SAVED_HISTORY_ENTRIES = _env_int("RICK_MAX_SAVED_HISTORY_ENTRIES", 10)
