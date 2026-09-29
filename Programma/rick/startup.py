"""Crash visibility for Rick's entry points (main.py, settings.py).

Both run under pythonw.exe with no console, so anything that goes wrong -
including a failed import of an audio library or the Gemini SDK - would
otherwise vanish silently: double-click, nothing happens. This module only
uses the standard library, so it can set up logging and an error dialog
BEFORE anything that might fail gets imported.
"""

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Deliberately not taken from rick.config: that module is one of the things
# whose import can fail, and this has to work regardless.
LOG_FILE = Path.home() / ".rick" / "rick.log"
# rick.log plus 2 older copies: about 3 MB at most, however long Rick is used.
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 2

_ERROR_TITLE = "Rick - errore / error"
_ERROR_BODY = (
    "Rick non e' riuscito ad avviarsi o si e' fermato per un errore.\n"
    "Rick couldn't start, or stopped because of an error.\n\n"
    "Dettagli tecnici / Technical details:\n{log_path}"
)


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        str(LOG_FILE), maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
    )
    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(threadName)s %(message)s",
    )

    def log_uncaught(exc_type, exc_value, exc_tb):
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

    def log_uncaught_in_thread(args):
        if args.exc_type is SystemExit:
            return
        logging.critical(
            "Uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = log_uncaught
    threading.excepthook = log_uncaught_in_thread


def describe_error(exc: BaseException, limit: int = 150) -> str:
    """One short line for a status bar: API errors can carry a whole JSON
    body, which would just be cut off mid-word there (the full error goes to
    the log file)."""
    lines = str(exc).strip().splitlines()
    text = lines[0] if lines else type(exc).__name__
    return text if len(text) <= limit else text[: limit - 3] + "..."


def show_error_dialog(title: str, message: str) -> None:
    """A standalone error popup, usable even when no Rick window exists."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        logging.exception("Couldn't even show the error dialog")


def run(entry) -> None:
    """Runs `entry` (a zero-argument callable that does its own imports) with
    logging configured first and any unexpected failure both logged and shown
    to the user."""
    setup_logging()
    try:
        entry()
    except SystemExit:
        raise
    except Exception:
        logging.exception("Rick stopped because of an unexpected error")
        show_error_dialog(_ERROR_TITLE, _ERROR_BODY.format(log_path=LOG_FILE))
