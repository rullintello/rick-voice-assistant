import asyncio

from . import config, userdata


async def _edge_tts_save(text: str, voice: str, out_path: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(
        text, voice, rate=config.EDGE_RATE, pitch=config.EDGE_PITCH
    )
    await communicate.save(out_path)


def synthesize(text: str) -> str:
    """Renders text to speech and returns the path to an audio file, which
    the caller deletes once it's been played."""
    path = userdata.new_temp_path(".mp3")
    try:
        _render(text, path)
    except BaseException:
        # Nobody else knows this path yet: without this, every failed attempt
        # (e.g. while offline) would leave an empty .mp3 behind.
        userdata.remove_quietly(path)
        raise
    return path


def _render(text: str, out_path: str) -> None:
    # edge-tts: Microsoft Edge's online voices - free, no API key needed
    asyncio.run(_edge_tts_save(text, config.get_edge_voice(), out_path))
