"""Is a newer Rick out? GitHub is asked at most once a day (its answer is
kept in ~/.rick/update_check.json meanwhile), and the window shows a notice
when there is one (gui.BookWindow.show_update).

What's sent is an ordinary request for the latest release of Rick's
repository: nothing about the player, their keys or their questions. GitHub
sees the IP address, as any website does. RICK_CHECK_UPDATES=false in .env
turns this off."""

import json
import logging
import re
import threading
import time
import urllib.request

from . import __version__, config, jsonstore

log = logging.getLogger(__name__)

REPOSITORY = "rullintello/rick-voice-assistant"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
# What the notice opens: always this page, never a link that came over the
# network, so a tampered answer can't send the player anywhere else.
DOWNLOAD_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"

# How old GitHub's last answer can be before it's asked again.
CHECK_EVERY = 24 * 60 * 60
# How often a running Rick looks at that (Rick may stay open for days).
_LOOK_EVERY = 60 * 60
_TIMEOUT = 10
# GitHub's answer is a few KB; anything this big is not that answer.
_MAX_ANSWER_BYTES = 1_000_000


def parse_version(text) -> tuple | None:
    """(1, 0, 2) for "v1.0.2" or "1.0.2", (1, 1, 0) for "1.1". None for
    anything else, pre-releases included ("v1.1.0-beta")."""
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"v?(\d{1,4})\.(\d{1,4})(?:\.(\d{1,4}))?", text.strip())
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def fetch_latest() -> str:
    """The version of the newest release published on GitHub, e.g. "1.0.3"
    (drafts and pre-releases don't count). Raises when GitHub can't be
    reached or answers something else."""
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"Rick/{__version__}"},
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        body = response.read(_MAX_ANSWER_BYTES + 1)
    if len(body) > _MAX_ANSWER_BYTES:
        raise ValueError("GitHub's answer is too big")
    answer = json.loads(body)
    tag = answer.get("tag_name") if isinstance(answer, dict) else None
    if parse_version(tag) is None:
        raise ValueError(f"unexpected release tag {tag!r}")
    return tag.strip().lstrip("v")


def latest_version(now: float | None = None, fetch=fetch_latest) -> str | None:
    """The newest version: GitHub's answer from less than a day ago if
    there is one, else GitHub's answer now. When GitHub can't be reached,
    the last answer saved, however old (None if there's none)."""
    now = time.time() if now is None else now
    saved = jsonstore.read_json(config.UPDATE_CHECK_FILE, {})
    saved = saved if isinstance(saved, dict) else {}
    saved_latest = saved.get("latest") if parse_version(saved.get("latest")) else None
    checked_at = saved.get("checked_at")
    # a check "in the future" means the clock was changed: ask again
    if saved_latest and isinstance(checked_at, (int, float)) and 0 <= now - checked_at < CHECK_EVERY:
        return saved_latest
    try:
        latest = fetch()
    except Exception as exc:  # offline, GitHub down or rate-limited: try again later
        log.info("Couldn't check for a newer Rick: %s", exc)
        return saved_latest
    try:
        jsonstore.write_json(config.UPDATE_CHECK_FILE, {"checked_at": now, "latest": latest})
    except OSError:
        log.warning("Couldn't save the update check", exc_info=True)
    return latest


def newer_version(now: float | None = None, fetch=fetch_latest) -> str | None:
    """The newest version if it's newer than this one, else None."""
    latest = latest_version(now, fetch)
    if latest and parse_version(latest) > parse_version(__version__):
        return latest
    return None


def watch(on_newer, newer=None, sleep=None) -> None:
    """Runs for as long as Rick does: calls on_newer(version) when a newer
    version is found, once for each version (the player may have closed the
    notice). Nothing here can stop it, and it never stops Rick either."""
    newer, sleep = newer or newer_version, sleep or time.sleep
    told = None
    while True:
        try:
            version = newer()
            if version and version != told:
                told = version
                on_newer(version)
        except Exception:
            log.exception("Update check failed")
        sleep(_LOOK_EVERY)


def start(on_newer) -> threading.Thread:
    """watch() on its own thread, which ends with Rick."""
    thread = threading.Thread(target=watch, args=(on_newer,), name="update-check", daemon=True)
    thread.start()
    return thread
