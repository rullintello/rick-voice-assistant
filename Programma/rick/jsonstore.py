"""Crash-safe JSON files for everything Rick keeps under ~/.rick.

Plain Path.write_text() truncates the file first and then writes it, so a
crash or power cut halfway leaves a broken file - and the old readers then
treated "broken" as "empty" and the next save overwrote everything. Here a
write goes to a temporary file that atomically replaces the real one only
once it's complete, and a file that still turns out unreadable is moved
aside (never overwritten) so its data can be recovered.
"""

import json
import logging
import os
import tempfile
import time
from pathlib import Path

_REPLACE_ATTEMPTS = 10
_REPLACE_RETRY_DELAY = 0.05

log = logging.getLogger(__name__)


def read_json(path: Path, default):
    """Returns the parsed file, or `default` if it doesn't exist. A corrupt
    file is renamed to <name>.corrupt-<timestamp> (and logged) rather than
    silently discarded, so the next write can't destroy what's left of it."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        backup = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
        try:
            os.replace(path, backup)
            log.error("%s was unreadable; moved it to %s and started fresh", path, backup)
        except OSError:
            log.exception("%s is unreadable and couldn't be moved aside", path)
        return default


def write_json(path: Path, data) -> None:
    """Atomic replace: readers see either the old file or the new one,
    never a half-written one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
        _replace_with_retry(tmp_name, path)
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def _replace_with_retry(src: str, dst: Path) -> None:
    # On Windows os.replace fails with a sharing violation if another thread
    # happens to have the destination open for reading at that exact moment
    # (e.g. Rick's worker reading history while the window saves it) - a
    # short retry gets past it.
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_RETRY_DELAY)
