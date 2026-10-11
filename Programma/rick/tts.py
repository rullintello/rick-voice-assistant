import asyncio
import logging
import sys
import time

from . import config, userdata

log = logging.getLogger(__name__)

# The online voice relies on Microsoft Edge's read-aloud service, which isn't
# an official API: it can refuse requests (403) or be unreachable (offline).
# On Windows, Rick then speaks with the voices built into Windows itself.
_HAS_WINDOWS_VOICES = sys.platform == "win32"
# After the online voice fails, Windows' voice is used for this long before
# the online one is tried again - so a blocked service costs one failed
# attempt every few minutes, not a delay on every single answer.
_ONLINE_RETRY_AFTER_SECONDS = 10 * 60
_online_unavailable_until = 0.0

# Windows voice languages are LCIDs in hex: 410 = Italian, 409/809/... = English
_WINDOWS_VOICE_LANGUAGES = {"it": {"410"}, "en": {"409", "809", "c09", "1009", "1409"}}
_SSFM_CREATE_FOR_WRITE = 3  # SpFileStream.Open mode
_SVSF_IS_NOT_XML = 16  # speak the text as-is, never parse it as SAPI XML

_UNAVAILABLE = {
    "it": "La voce di Rick non e' disponibile in questo momento: la risposta e' comunque scritta nel libro.",
    "en": "Rick's voice isn't available right now: the answer is still written in the book.",
}


class VoiceUnavailableError(RuntimeError):
    """No voice could speak. Carries a short, readable message for the
    status bar; the technical details of each failure go to the log."""


def synthesize(text: str) -> str:
    """Renders text to speech and returns the path to an audio file, which
    the caller deletes once it's been played: Microsoft's online voice when
    it works, otherwise (on Windows) the voice built into Windows."""
    global _online_unavailable_until
    if time.monotonic() >= _online_unavailable_until:
        try:
            return _to_temp_file(".mp3", _render_online, text)
        except Exception:
            log.warning("Online voice (edge-tts) failed", exc_info=True)
            if _HAS_WINDOWS_VOICES:
                _online_unavailable_until = time.monotonic() + _ONLINE_RETRY_AFTER_SECONDS
    if _HAS_WINDOWS_VOICES:
        try:
            return _to_temp_file(".wav", _render_windows, text)
        except Exception:
            log.warning("Windows voice failed too", exc_info=True)
    raise VoiceUnavailableError(_UNAVAILABLE[config.get_language()])


def _to_temp_file(suffix: str, render, text: str) -> str:
    path = userdata.new_temp_path(suffix)
    try:
        render(text, path)
    except BaseException:
        # Nobody else knows this path yet: without this, every failed attempt
        # (e.g. while offline) would leave an empty file behind.
        userdata.remove_quietly(path)
        raise
    return path


async def _edge_tts_save(text: str, voice: str, out_path: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text, voice, rate=config.EDGE_RATE, pitch=config.EDGE_PITCH
    )
    await communicate.save(out_path)


def _render_online(text: str, out_path: str) -> None:
    # edge-tts: Microsoft Edge's online voices - free, no API key needed
    asyncio.run(_edge_tts_save(text, config.get_edge_voice(), out_path))


def _render_windows(text: str, out_path: str) -> None:
    """Windows' built-in voices (SAPI, through COM): always installed, work
    offline and send nothing anywhere. Uses a voice in Rick's language when
    one is installed (Italian Windows ships one), else Windows' default."""
    import comtypes
    import comtypes.client

    # COM must be initialised on each thread that uses it, and Rick speaks
    # from a new worker thread every turn. Deliberately never uninitialised:
    # a COM object still referenced afterwards (e.g. by an exception's
    # traceback) would then be released too late and crash the process.
    comtypes.CoInitialize()
    voice = comtypes.client.CreateObject("SAPI.SpVoice")
    wanted = _WINDOWS_VOICE_LANGUAGES.get(config.get_language(), set())
    voices = voice.GetVoices()
    for i in range(voices.Count):
        token = voices.Item(i)
        try:
            languages = set(token.GetAttribute("Language").lower().split(";"))
        except Exception:  # a voice without a Language attribute: skip it
            continue
        if languages & wanted:
            voice.Voice = token
            break
    stream = comtypes.client.CreateObject("SAPI.SpFileStream")
    stream.Open(out_path, _SSFM_CREATE_FOR_WRITE)
    try:
        voice.AudioOutputStream = stream
        voice.Speak(text, _SVSF_IS_NOT_XML)
    finally:
        stream.Close()
