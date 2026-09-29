"""Everything Rick keeps on disk about its user, in one place: the folder
for temporary audio (a recording of the player's voice, Rick's spoken
answer), and erasing it all for the window's "Delete all my data".

Rick's memory - the binders in history.json, which the "second brain"
reads - is only ever touched by delete_all(), never by the temp cleanup."""

import contextlib
import logging
import os
import tempfile
import time
from pathlib import Path

from . import config, startup

log = logging.getLogger(__name__)

# A temp file older than this at startup is a leftover (Rick was closed or
# crashed mid-question), not one a second, still-running Rick is using.
_LEFTOVER_AGE_SECONDS = 5 * 60


def new_temp_path(suffix: str) -> str:
    """A new empty file in Rick's own temp folder (~/.rick/tmp) - not the
    shared Windows temp folder, where a recording left behind would stay
    forever. The caller deletes it once done; anything left anyway is swept
    at the next start (see purge_leftover_temp_files)."""
    config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(suffix=suffix, dir=config.TEMP_DIR)
    # Closed right away: Windows won't let another writer (soundfile,
    # edge-tts, ...) open this same path while a handle is still open.
    os.close(fd)
    return path


def remove_quietly(path: "str | Path") -> None:
    with contextlib.suppress(OSError):
        os.remove(path)


def purge_leftover_temp_files() -> None:
    """Deletes recordings/answers left behind by a previous run."""
    _purge_temp_files(older_than=_LEFTOVER_AGE_SECONDS)


def _purge_temp_files(older_than: float) -> None:
    if not config.TEMP_DIR.is_dir():
        return
    now = time.time()
    for path in config.TEMP_DIR.iterdir():
        with contextlib.suppress(OSError):
            if path.is_file() and now - path.stat().st_mtime >= older_than:
                path.unlink()


def delete_all() -> None:
    """Erases everything Rick has saved about its user: every binder (so
    also the "second brain"), the saved API keys and language, the search
    cache, leftover audio and the log - including the backup/temp copies
    jsonstore can leave next to each file, which hold the same data."""
    for path in (config.HISTORY_FILE, config.USER_CONFIG_FILE, config.SEARCH_CACHE_FILE):
        remove_quietly(path)
        for copy in (*path.parent.glob(f"{path.name}.corrupt-*"), *path.parent.glob(f".{path.name}.*.tmp")):
            remove_quietly(copy)
    _purge_temp_files(older_than=0)
    _clear_log()
    log.info("All user data deleted at the user's request")


def _clear_log() -> None:
    """The log can't simply be deleted while Rick is writing to it (Windows
    refuses to delete an open file), so the open one is emptied in place."""
    log_file = Path(startup.LOG_FILE)
    emptied = False
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_file.resolve():
            with contextlib.suppress(OSError, ValueError):
                handler.acquire()
                try:
                    if handler.stream:
                        handler.stream.seek(0)
                        handler.stream.truncate()
                        emptied = True
                finally:
                    handler.release()
    if not emptied:
        remove_quietly(log_file)
    for rotated in log_file.parent.glob(f"{log_file.name}.*"):
        remove_quietly(rotated)
