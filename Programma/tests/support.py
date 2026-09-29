"""Shared helpers for Rick's tests. Run the suite from the Programma folder:

    python -m unittest discover -s tests

GUI tests open real (briefly visible) Tk windows; on a machine with no
display they're skipped automatically.
"""

import logging
import os
import queue
import shutil
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

from rick import config, startup

# Many tests deliberately drive error paths that log exceptions; without a
# handler Python prints each one to stderr, burying the actual test results.
logging.getLogger().addHandler(logging.NullHandler())


def isolate_rick_home(test: unittest.TestCase) -> Path:
    """Points every file Rick reads/writes under ~/.rick at a throwaway
    folder, and pins the env vars tests depend on, so tests never touch (or
    get influenced by) the real user's keys, history or .env."""
    tmp = Path(tempfile.mkdtemp(prefix="rick-test-"))
    test.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
    for attr, filename in (
        ("USER_CONFIG_FILE", "config.json"),
        ("SEARCH_CACHE_FILE", "search_cache.json"),
        ("HISTORY_FILE", "history.json"),
        ("TEMP_DIR", "tmp"),
    ):
        patcher = mock.patch.object(config, attr, tmp / filename)
        patcher.start()
        test.addCleanup(patcher.stop)
    log_file = mock.patch.object(startup, "LOG_FILE", tmp / "rick.log")
    log_file.start()
    test.addCleanup(log_file.stop)
    env = mock.patch.dict(
        os.environ,
        {"GEMINI_API_KEY": "test-key", "RICK_LANGUAGE": "it", "TAVILY_API_KEY": ""},
    )
    env.start()
    test.addCleanup(env.stop)
    return tmp


def require_display(test: unittest.TestCase) -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        test.skipTest(f"no display available: {exc}")
    root.destroy()


def wait_until(predicate, timeout: float = 5.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def call_on_tk(root: tk.Tk, fn, timeout: float = 5.0):
    """Runs fn on the Tk thread and returns its result. Because it's queued
    with after(0), it also acts as a sync point: anything scheduled with
    after(0) before it (e.g. by BookWindow's thread-safe methods) has
    already run by the time it returns."""
    results: "queue.Queue" = queue.Queue()

    def run():
        try:
            results.put((True, fn()))
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            results.put((False, exc))

    root.after(0, run)
    ok, value = results.get(timeout=timeout)
    if not ok:
        raise value
    return value


def flush(root: tk.Tk) -> None:
    """Twice, because some callbacks schedule a follow-up after(0) of their
    own (append_turn -> refresh_binders)."""
    call_on_tk(root, lambda: None)
    call_on_tk(root, lambda: None)


def run_with_mainloop(root: tk.Tk, driver) -> None:
    """Runs driver() on a background thread while root's mainloop spins on
    this (main) thread - the same arrangement as the real app, where Rick's
    work happens off the Tk thread. Failures inside driver are re-raised
    here so they fail the test properly."""
    errors = []

    def wrapped():
        try:
            driver()
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            errors.append(exc)
        finally:
            root.after(0, root.quit)

    thread = threading.Thread(target=wrapped, daemon=True)
    thread.start()
    root.mainloop()
    thread.join(timeout=10)
    if errors:
        raise errors[0]
