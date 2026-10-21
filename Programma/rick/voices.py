"""The voices offered in the settings window: Microsoft's free online voices
(through edge-tts), a few per language, each with the speed and pitch that
make it sound like Rick. Plain data, no Tk and no edge-tts import."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str  # what's saved in config.json
    label: str  # what the settings window shows (in the voice's own language)
    name: str  # the edge-tts voice
    gender: str  # "male" / "female": a matching Windows voice is preferred as the backup
    rate: str = "+0%"
    pitch: str = "+0Hz"


VOICES = {
    "it": (
        Voice("giuseppe", "Giuseppe (maschile)", "it-IT-GiuseppeMultilingualNeural", "male"),
        Voice("diego", "Diego (maschile)", "it-IT-DiegoNeural", "male"),
        Voice("diego_deep", "Diego, piu' grave (maschile)", "it-IT-DiegoNeural", "male", "-6%", "-12Hz"),
        Voice("elsa", "Elsa (femminile)", "it-IT-ElsaNeural", "female"),
        Voice("isabella", "Isabella (femminile)", "it-IT-IsabellaNeural", "female"),
    ),
    "en": (
        Voice("andrew_deep", "Andrew, deeper (male)", "en-US-AndrewMultilingualNeural", "male", "-6%", "-12Hz"),
        Voice("andrew", "Andrew (male)", "en-US-AndrewMultilingualNeural", "male"),
        Voice("brian", "Brian (male)", "en-US-BrianMultilingualNeural", "male"),
        Voice("jenny", "Jenny (female)", "en-US-JennyNeural", "female"),
        Voice("emma", "Emma (female)", "en-US-EmmaMultilingualNeural", "female"),
    ),
}

# Rick is a he: a male voice unless the player picks another one
DEFAULT = {"it": "giuseppe", "en": "andrew_deep"}

# What the settings window's "Try" button says.
SAMPLE = {
    "it": "Ciao, sono Rick. Bloccato di nuovo? Tranquillo, ci penso io.",
    "en": "Hi, I'm Rick. Stuck again? Relax, I've got you.",
}


def for_language(language: str) -> tuple:
    return VOICES[language if language in VOICES else "it"]


def find(language: str, voice_id) -> Voice:
    """The voice saved as `voice_id` for `language`, or that language's
    default one (nothing saved yet, or an id this version doesn't have)."""
    choices = for_language(language)
    for voice in choices:
        if voice.id == voice_id:
            return voice
    default = DEFAULT[language if language in DEFAULT else "it"]
    return next(voice for voice in choices if voice.id == default)
