import tkinter as tk
import webbrowser

GEMINI_KEY_URL = "https://aistudio.google.com/apikey"
TAVILY_KEY_URL = "https://app.tavily.com"

# Keys are shown as dots by default: gamers often stream or share their
# screen, and a key read off a stream can be used by anyone.
_HIDDEN = "•"

DIALOG_STRINGS = {
    "it": {
        "gemini_label": "Per usare Rick serve una chiave API Gemini (gratuita).\nIncollala qui sotto:",
        "gemini_link": "Non hai una chiave? Creala gratis qui (nessuna carta richiesta)",
        "tavily_label": "Facoltativa: chiave Tavily, per far cercare a Rick sul web\n"
        "(wiki, guide) prima di risponderti. Lascia vuoto per saltarla.",
        "tavily_link": "Creane una gratis qui (nessuna carta richiesta)",
        "error_missing_gemini": "Incolla prima la chiave Gemini.",
        "show_keys": "Mostra le chiavi",
        "privacy_note": "Rick non invia nessun dato allo sviluppatore e le chiavi restano solo su questo PC.\n"
        "Le tue domande vengono inviate a Google Gemini per ottenere la risposta:\n"
        "non dire a Rick dati personali. Creando le chiavi accetti i termini di Google e Tavily.",
        "save_button": "Salva e avvia",
    },
    "en": {
        "gemini_label": "Rick needs a Gemini API key (free) to work.\nPaste it below:",
        "gemini_link": "Don't have a key? Create one for free here (no card required)",
        "tavily_label": "Optional: Tavily key, so Rick can search the web\n"
        "(wikis, guides) before answering. Leave blank to skip it.",
        "tavily_link": "Create one for free here (no card required)",
        "error_missing_gemini": "Paste your Gemini key first.",
        "show_keys": "Show keys",
        "privacy_note": "Rick sends no data to its developer, and your keys stay on this PC only.\n"
        "Your questions are sent to Google Gemini to get an answer:\n"
        "don't tell Rick personal information. Creating the keys means accepting Google's and Tavily's terms.",
        "save_button": "Save and start",
    },
}


def ask_for_api_keys(prefill: dict | None = None, title: str = "Rick - configurazione iniziale") -> dict:
    """Shows a dialog asking for the language, the Gemini (required) and
    Tavily (optional, for web search) API keys. `prefill` (with the same
    keys as the return value) lets this double as a "change settings"
    screen - see settings.py. Returns {"gemini": "", "tavily": "",
    "language": "it"} - "gemini" is "" only if the dialog was cancelled."""
    prefill = prefill or {}
    result = {"gemini": "", "tavily": "", "language": prefill.get("language", "it")}

    root = tk.Tk()
    root.title(title)
    root.resizable(False, False)

    tk.Label(
        root,
        text="Lingua di Rick / Rick's language:",
        font=("Segoe UI", 11),
        justify="center",
    ).pack(padx=24, pady=(24, 4))

    language_var = tk.StringVar(value=prefill.get("language", "it"))
    lang_frame = tk.Frame(root)
    lang_frame.pack(pady=(0, 14))

    gemini_label = tk.Label(root, font=("Segoe UI", 11), justify="center")
    gemini_label.pack(padx=24, pady=(0, 10))

    gemini_entry = tk.Entry(root, width=48, font=("Segoe UI", 10), show=_HIDDEN)
    gemini_entry.insert(0, prefill.get("gemini", ""))
    gemini_entry.pack(padx=24, pady=(0, 4))
    gemini_entry.focus_set()

    error_label = tk.Label(root, text="", fg="red", font=("Segoe UI", 9))
    error_label.pack()

    gemini_link = tk.Label(
        root, fg="#2b6cb0", cursor="hand2", font=("Segoe UI", 9, "underline")
    )
    gemini_link.pack(pady=(2, 14))
    gemini_link.bind("<Button-1>", lambda _event: webbrowser.open(GEMINI_KEY_URL))

    tavily_label = tk.Label(root, font=("Segoe UI", 11), justify="center")
    tavily_label.pack(padx=24, pady=(0, 10))

    tavily_entry = tk.Entry(root, width=48, font=("Segoe UI", 10), show=_HIDDEN)
    tavily_entry.insert(0, prefill.get("tavily", ""))
    tavily_entry.pack(padx=24, pady=(0, 4))

    tavily_link = tk.Label(
        root, fg="#2b6cb0", cursor="hand2", font=("Segoe UI", 9, "underline")
    )
    tavily_link.pack(pady=(2, 14))
    tavily_link.bind("<Button-1>", lambda _event: webbrowser.open(TAVILY_KEY_URL))

    show_keys_var = tk.BooleanVar(value=False)

    def toggle_keys() -> None:
        for entry in (gemini_entry, tavily_entry):
            entry.config(show="" if show_keys_var.get() else _HIDDEN)

    show_keys = tk.Checkbutton(
        root, variable=show_keys_var, command=toggle_keys, font=("Segoe UI", 9)
    )
    show_keys.pack(pady=(0, 10))

    privacy_note = tk.Label(root, font=("Segoe UI", 9), fg="#555555", justify="center")
    privacy_note.pack(padx=24, pady=(0, 12))

    save_button = tk.Button(root, font=("Segoe UI", 10), padx=12, pady=6)

    def apply_language(*_args) -> None:
        strings = DIALOG_STRINGS[language_var.get()]
        gemini_label.config(text=strings["gemini_label"])
        gemini_link.config(text=strings["gemini_link"])
        tavily_label.config(text=strings["tavily_label"])
        tavily_link.config(text=strings["tavily_link"])
        show_keys.config(text=strings["show_keys"])
        privacy_note.config(text=strings["privacy_note"])
        save_button.config(text=strings["save_button"])
        error_label.config(text="")

    tk.Radiobutton(
        lang_frame,
        text="🇮🇹 Italiano",
        variable=language_var,
        value="it",
        font=("Segoe UI", 10),
        command=apply_language,
    ).pack(side="left", padx=10)
    tk.Radiobutton(
        lang_frame,
        text="🇬🇧 English",
        variable=language_var,
        value="en",
        font=("Segoe UI", 10),
        command=apply_language,
    ).pack(side="left", padx=10)

    def on_save() -> None:
        gemini_key = gemini_entry.get().strip()
        if not gemini_key:
            error_label.config(text=DIALOG_STRINGS[language_var.get()]["error_missing_gemini"])
            return
        result["gemini"] = gemini_key
        result["tavily"] = tavily_entry.get().strip()
        result["language"] = language_var.get()
        root.destroy()

    save_button.config(command=on_save)
    save_button.pack(pady=(0, 20))
    gemini_entry.bind("<Return>", lambda _event: on_save())
    tavily_entry.bind("<Return>", lambda _event: on_save())

    apply_language()

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_width()) // 2
    y = (root.winfo_screenheight() - root.winfo_height()) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()
    return result
