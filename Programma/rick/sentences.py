"""Rick's answer cut into sentences while Gemini is still writing it, so
that each one can be turned into voice and played as soon as it's
complete (see app.speak). Plain text in, plain text out."""

import re

# Where a sentence ends: . ! ? or ..., maybe with closing quotes or brackets,
# then a space or a new line. "1.5" or "v1.0.2" don't end one.
_END = re.compile(r"[.!?…]+[\"'”’»)\]]*\s+|\n+")
# A shorter sentence waits to go out with the next one: each sentence is a
# request of its own to the voice service, and a tiny one ("Si'.") would be
# over before the next one is ready, leaving a gap.
MIN_CHARS = 30
# A sentence with no end in sight is cut at a comma or a space by this
# length, so the voice doesn't wait for it.
MAX_CHARS = 220


def sentences(pieces):
    """Yields the sentences in `pieces` (the text, in pieces of any size) as
    soon as each one is complete, and what's left at the end."""
    pending = ""
    for piece in pieces:
        pending += piece
        while (cut := _first_cut(pending)) is not None:
            sentence, pending = pending[:cut].strip(), pending[cut:]
            if sentence:
                yield sentence
    rest = pending.strip()
    if rest:
        yield rest


def _first_cut(text: str) -> int | None:
    """Where the first part of `text` worth saying on its own ends, or None
    while it may still go on."""
    for end in _END.finditer(text):
        if len(text[: end.end()].strip()) >= MIN_CHARS:
            return end.end()
    if len(text) > MAX_CHARS:
        comma = text.rfind(", ", 0, MAX_CHARS)
        space = text.rfind(" ", 0, MAX_CHARS)
        if comma > 0:
            return comma + 1
        if space > 0:
            return space
        return MAX_CHARS
    return None
