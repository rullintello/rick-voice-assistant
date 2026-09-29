import tkinter as tk
from tkinter import messagebox

from rick.startup import run

_MESSAGES = {
    "it": {
        "cancelled": "Nessuna modifica salvata (serve comunque una chiave Gemini).",
        "saved": "Impostazioni salvate.",
    },
    "en": {
        "cancelled": "No changes saved (a Gemini key is still required).",
        "saved": "Settings saved.",
    },
}


def _notify(text: str) -> None:
    """settings.py runs with no console (see Settings.bat), so a small
    popup is how the save confirmation actually reaches the user."""
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Rick", text)
    root.destroy()


def main() -> None:
    # Imported here, not at the top, so a failure (e.g. a malformed .env)
    # is caught by run() and shown, instead of silently killing pythonw.
    from rick import config
    from rick.setup_gui import ask_for_api_keys

    prefill = {
        "gemini": config.get_gemini_api_key(),
        "tavily": config.get_tavily_api_key(),
        "language": config.get_language(),
    }
    keys = ask_for_api_keys(prefill=prefill, title="Rick - impostazioni")
    language = keys.get("language", "it")
    if not keys["gemini"]:
        _notify(_MESSAGES[language]["cancelled"])
        return

    config.save_gemini_api_key(keys["gemini"])
    config.save_tavily_api_key(keys["tavily"])
    config.save_language(language)
    _notify(_MESSAGES[language]["saved"])


if __name__ == "__main__":
    run(main)
