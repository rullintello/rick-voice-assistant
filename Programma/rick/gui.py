import ctypes
import logging
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox, ttk

from . import history, userdata
from .startup import describe_error

log = logging.getLogger(__name__)

SPONSORS_URL = "https://ko-fi.com/rullintello"

# "Pixel lofi ancient book" palette: warm off-white/cream for the pages,
# dark brown for the shelf of binders, a muted brown-gold accent, and
# forest-green "ink" for the actual page text. The cream/brown areas also
# get a subtle pixel-art paper/wood-grain texture (see _build_sidebar and
# _build_main_pane) - these flat colors are what's used for the smaller
# sub-panels (buttons, listbox) and as the fallback if a texture image
# somehow fails to load.
_PARCHMENT = "#e8e0cd"
_PARCHMENT_DARK = "#dcd0b6"
_INK = "#3b2712"
_LEATHER = "#3a2a1e"
_LEATHER_LIGHT = "#54402f"
_GOLD = "#8a6a45"
_TEXT_GREEN = "#2f6b1f"
_TEXT_GREEN_DARK = "#1e4a12"

_SERIF = "UnifrakturMaguntia"
_FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_TEXTURES_DIR = Path(__file__).resolve().parent.parent / "assets" / "textures"
_PORTRAIT_FILE = Path(__file__).resolve().parent.parent / "assets" / "rick_pixel.png"
# Shelf height (px) below which the portrait is shown at half size.
_PORTRAIT_FULL_SIZE_MIN_HEIGHT = 480


def _load_bundled_fonts() -> None:
    """UnifrakturMaguntia isn't installed on a stock Windows PC, so the file
    under assets/fonts/ is registered for THIS PROCESS ONLY (Windows'
    FR_PRIVATE flag: no install, no admin rights, nothing left behind when
    Rick closes). Tkinter itself falls back to a default font automatically
    if a family name isn't found, so any failure here (including just not
    being on Windows) is safe to ignore - not worth losing the app over
    decorative typography."""
    if sys.platform != "win32":
        return
    try:
        FR_PRIVATE = 0x10
        for font_file in _FONTS_DIR.glob("*.ttf"):
            ctypes.windll.gdi32.AddFontResourceExW(str(font_file), FR_PRIVATE, 0)
    except Exception:
        pass


_load_bundled_fonts()

_STRINGS = {
    "it": {
        "title": "📖 Rick",
        "binders_header": "Raccoglitori",
        "current_game_label": "Gioco attuale:",
        "no_game": history.NO_GAME_KEY_IT,
        "you": "Tu",
        "rick": "Rick",
        "empty_binder": "Questo raccoglitore e' ancora vuoto. Fai una domanda per iniziare a scriverlo.",
        "save_button": "💾 Salva",
        "new_chat_button": "🆕 Nuova chat",
        "delete_button": "🗑️ Elimina",
        "delete_confirm_title": "Elimina raccoglitore",
        "delete_confirm_body": "Eliminare per sempre \"{game}\" e tutta la sua cronologia?",
        "merge_confirm_title": "Unisci raccoglitori",
        "merge_confirm_body": (
            "Esiste gia' un raccoglitore \"{new}\". Spostare li' anche la cronologia di \"{old}\"?\n\n"
            "Per aprirlo e basta, sceglilo dall'elenco."
        ),
        "ui_error": "⚠️ {error} (dettagli in rick.log)",
        "delete_all_button": "Cancella tutti i tuoi dati",
        "delete_all_title": "Cancella tutti i tuoi dati",
        "delete_all_body": (
            "Verranno eliminati per sempre da questo PC:\n\n"
            "- tutti i raccoglitori e la cronologia (anche quello che Rick ricorda dei tuoi giochi)\n"
            "- le chiavi API e la lingua salvate\n"
            "- la cache delle ricerche web e il registro errori\n\n"
            "Cancella solo i dati su questo PC: quello gia' inviato a Google, Tavily e "
            "Microsoft e' gestito da loro, secondo le loro regole sulla privacy.\n\n"
            "Poi Rick si chiudera': al prossimo avvio ti richiedera' le chiavi.\n\nVuoi continuare?"
        ),
        "delete_all_done": "Fatto: tutti i tuoi dati sono stati cancellati da questo PC. Ora Rick si chiude.",
        "support_link": "☕ Offrimi un caffe",
    },
    "en": {
        "title": "📖 Rick",
        "binders_header": "Binders",
        "current_game_label": "Current game:",
        "no_game": history.NO_GAME_KEY_EN,
        "you": "You",
        "rick": "Rick",
        "empty_binder": "This binder is still empty. Ask a question to start filling it.",
        "save_button": "💾 Save",
        "new_chat_button": "🆕 New chat",
        "delete_button": "🗑️ Delete",
        "delete_confirm_title": "Delete binder",
        "delete_confirm_body": "Permanently delete \"{game}\" and all its history?",
        "merge_confirm_title": "Merge binders",
        "merge_confirm_body": (
            "A binder named \"{new}\" already exists. Move \"{old}\"'s history into it too?\n\n"
            "To just open it, pick it from the list."
        ),
        "ui_error": "⚠️ {error} (details in rick.log)",
        "delete_all_button": "Delete all your data",
        "delete_all_title": "Delete all your data",
        "delete_all_body": (
            "This permanently deletes from this PC:\n\n"
            "- every binder and all history (including what Rick remembers about your games)\n"
            "- the saved API keys and language\n"
            "- the web search cache and the error log\n\n"
            "It only deletes data on this PC: whatever was already sent to Google, Tavily and "
            "Microsoft is handled by them, under their own privacy rules.\n\n"
            "Rick will then close: next time it will ask for your keys again.\n\nContinue?"
        ),
        "delete_all_done": "Done: all your data has been deleted from this PC. Rick will now close.",
        "support_link": "☕ Buy me a coffee",
    },
}


class BookWindow:
    """The GUI: a shelf of "binders" (one per game, on the left) and an open
    "page" (the current binder's transcript, on the right). Every public
    method here is safe to call from any thread - they all marshal onto the
    Tk main thread via root.after(), since Tkinter itself is not thread-safe."""

    def __init__(self, language: str, on_close=None, on_new_chat=None):
        self._t = _STRINGS[language if language in _STRINGS else "it"]
        self._on_close = on_close
        # Called when the conversation should start over even though the
        # active binder may keep the same name ("New chat" while already in
        # the untitled one, or deleting it) - main.py makes Rick forget it.
        self._on_new_chat = on_new_chat
        self._game_lock = threading.Lock()
        self._current_game = ""
        # Binders renamed/deleted while an answer for them may still be on
        # its way (Rick thinking): append_turn() follows these instead of
        # saving under the old name and bringing that binder back to life.
        # Only touched on the Tk thread.
        self._renamed: dict[str, str] = {}
        self._deleted: set[str] = set()

        self.root = tk.Tk()
        self.root.title("Rick")
        self.root.geometry("820x560")
        # Below this, the sidebar's buttons/list and the status bar start
        # clipping/overlapping instead of shrinking gracefully - simplest
        # robust fix is to just not allow the window to get that small.
        self.root.minsize(640, 420)
        self.root.configure(bg=_LEATHER)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.root.report_callback_exception = self._report_callback_exception

        # Tk garbage-collects a PhotoImage as soon as nothing references it,
        # which would make the textures and portrait below vanish - this list
        # is just there to keep them alive for the window's lifetime.
        self._images: list[tk.PhotoImage] = []

        # Packed before the sidebar/main pane: pack() carves cavity space in
        # packing order, and the main pane's fill="both"+expand=True would
        # otherwise claim the entire remaining window before this gets a
        # chance to reserve its own strip at the bottom.
        self._build_status_bar()
        self._build_sidebar()
        self._build_main_pane()

        self.refresh_binders()
        self._activate_game("")

    def _add_background_texture(self, parent: tk.Widget, filename: str) -> None:
        """Fills `parent` with a tiled pixel-art texture image, sitting
        behind whatever gets packed into it afterwards. If the file is
        missing or Tk can't load it, `parent` just keeps its own flat
        background color instead - a decorative texture isn't worth
        crashing Rick over."""
        try:
            image = tk.PhotoImage(file=str(_TEXTURES_DIR / filename))
        except Exception:
            return
        self._images.append(image)
        background = tk.Label(parent, image=image, borderwidth=0)
        background.place(x=0, y=0, relwidth=1, relheight=1)
        background.lower()

    def _add_portrait(self, parent: tk.Widget) -> None:
        """Rick's pixel-art portrait (the black wizard cat), in a gold frame.
        Drawn at 32x32 and shown at 4x with PhotoImage.zoom (no smoothing),
        so every pixel stays crisp. Decorative like the textures: if the file is missing or can't
        be loaded, the window just goes without it."""
        try:
            art = tk.PhotoImage(file=str(_PORTRAIT_FILE))
        except Exception:
            return
        small, large = art.zoom(2), art.zoom(4)
        self._images += [small, large]
        portrait = tk.Label(
            parent,
            image=large,
            borderwidth=0,
            bg=_LEATHER,
            highlightthickness=3,
            highlightbackground=_GOLD,
            highlightcolor=_GOLD,
        )
        portrait.pack(pady=(14, 0))

        def fit(event: tk.Event) -> None:
            # In a short window the full-size portrait would squeeze the list
            # below it to a sliver: drop to half size (still crisp) to leave it room.
            # Keyed on the shelf's height, which the portrait doesn't change,
            # so switching can't make it flip back and forth.
            wanted = large if event.height >= _PORTRAIT_FULL_SIZE_MIN_HEIGHT else small
            if portrait.cget("image") != str(wanted):
                portrait.configure(image=wanted)

        parent.bind("<Configure>", fit, add="+")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        sidebar = tk.Frame(self.root, bg=_LEATHER, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self._add_background_texture(sidebar, "wood_pixel.png")
        self._add_portrait(sidebar)

        tk.Label(
            sidebar,
            text=self._t["binders_header"],
            font=(_SERIF, 13, "bold"),
            bg=_LEATHER,
            fg=_PARCHMENT,
        ).pack(pady=(10, 4), padx=12, anchor="w")

        tk.Label(
            sidebar,
            text=self._t["current_game_label"],
            font=(_SERIF, 9),
            bg=_LEATHER,
            fg=_GOLD,
        ).pack(padx=12, anchor="w", pady=(8, 2))

        # Typing here is just a draft name - it only takes effect when
        # "Salva"/"Save" is clicked (see _on_save_clicked). Picking an
        # EXISTING game from this same field's own dropdown switches to it
        # immediately instead, same as clicking it in the list below: that's
        # choosing something that already exists, not renaming anything.
        self._game_var = tk.StringVar()
        self._game_combo = ttk.Combobox(sidebar, textvariable=self._game_var, font=(_SERIF, 10))
        self._game_combo.pack(padx=12, fill="x")
        self._game_combo.bind("<<ComboboxSelected>>", lambda _e: self._activate_game(self._game_var.get()))

        button_row = tk.Frame(sidebar, bg=_LEATHER)
        button_row.pack(padx=12, pady=(8, 0), fill="x")
        tk.Button(
            button_row,
            text=self._t["save_button"],
            font=(_SERIF, 9),
            command=self._on_save_clicked,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(
            button_row,
            text=self._t["delete_button"],
            font=(_SERIF, 9),
            command=self._on_delete_clicked,
        ).pack(side="left", expand=True, fill="x")

        tk.Button(
            sidebar,
            text=self._t["new_chat_button"],
            font=(_SERIF, 9),
            command=self._on_new_chat_clicked,
        ).pack(padx=12, pady=(6, 0), fill="x")

        tk.Frame(sidebar, bg=_LEATHER_LIGHT, height=1).pack(fill="x", padx=12, pady=12)

        # Packed (side="bottom") before list_frame below, which otherwise
        # claims the whole remaining cavity via fill="both"+expand=True and
        # would leave this with no space to reserve - same lesson as the
        # status bar fix.
        support_link = tk.Label(
            sidebar,
            text=self._t["support_link"],
            font=(_SERIF, 9, "underline"),
            bg=_PARCHMENT,
            fg=_LEATHER,
            cursor="hand2",
            padx=8,
            pady=3,
        )
        support_link.pack(side="bottom", pady=(0, 12))
        support_link.bind("<Button-1>", lambda _e: webbrowser.open(SPONSORS_URL))

        list_frame = tk.Frame(sidebar, bg=_LEATHER)
        list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        self._binder_list = tk.Listbox(
            list_frame,
            font=(_SERIF, 11),
            bg=_LEATHER_LIGHT,
            fg=_PARCHMENT,
            selectbackground=_GOLD,
            selectforeground=_INK,
            activestyle="none",
            relief="flat",
            highlightthickness=0,
            yscrollcommand=scrollbar.set,
        )
        self._binder_list.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._binder_list.yview)
        self._binder_list.bind("<<ListboxSelect>>", lambda _e: self._on_binder_clicked())

    def _build_main_pane(self) -> None:
        main = tk.Frame(self.root, bg=_PARCHMENT)
        main.pack(side="left", fill="both", expand=True)
        self._add_background_texture(main, "paper_pixel.png")

        tk.Label(
            main,
            text=self._t["title"],
            # Not bold: this font has only one weight, so "bold" is a
            # synthetic/fake thickening that fills in the lowercase k's
            # loop and makes it unreadable at a glance. Plain + bigger
            # reads far more clearly while staying fully gothic.
            font=(_SERIF, 26),
            bg=_PARCHMENT,
            fg=_TEXT_GREEN,
        ).pack(pady=(16, 0))
        tk.Frame(main, bg=_GOLD, height=2).pack(fill="x", padx=40, pady=(6, 12))

        # Packed (side="bottom") before the page, which would otherwise claim
        # all the space first - same lesson as the status bar. Small and off
        # to the side on purpose: it's rare, and not to be hit by accident.
        tk.Button(
            main,
            text=self._t["delete_all_button"],
            font=(_SERIF, 9),
            command=self._on_delete_all_clicked,
        ).pack(side="bottom", anchor="e", padx=24, pady=(0, 8))

        text_frame = tk.Frame(main, bg=_PARCHMENT)
        text_frame.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        self._text = tk.Text(
            text_frame,
            font=(_SERIF, 13),
            bg=_PARCHMENT_DARK,
            fg=_TEXT_GREEN,
            wrap="word",
            relief="flat",
            padx=14,
            pady=12,
            state="disabled",
            yscrollcommand=scrollbar.set,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        # Same reasoning as the title: plain weight instead of synthetic
        # bold, "Tu:"/"Rick:" are still told apart by color.
        self._text.tag_configure("you", font=(_SERIF, 13), foreground=_TEXT_GREEN, spacing3=2)
        self._text.tag_configure("rick", font=(_SERIF, 13), foreground=_TEXT_GREEN_DARK, spacing3=2)
        self._text.tag_configure("body", font=(_SERIF, 13), foreground=_TEXT_GREEN, spacing3=14)
        self._text.tag_configure("divider", font=(_SERIF, 12), foreground=_GOLD, justify="center", spacing3=14)
        self._text.tag_configure("empty", font=(_SERIF, 12, "italic"), foreground=_LEATHER_LIGHT)

    def _build_status_bar(self) -> None:
        self._status_var = tk.StringVar(value="")
        status = tk.Label(
            self.root,
            textvariable=self._status_var,
            font=(_SERIF, 10, "italic"),
            bg=_PARCHMENT,
            fg=_TEXT_GREEN,
            anchor="w",
            justify="left",
        )
        status.pack(side="bottom", fill="x", padx=24, pady=(0, 10))
        # An error message plus "press Alt+R to try again" can be longer than
        # a narrow window: wrap onto a second line instead of cutting it off.
        status.bind("<Configure>", lambda e: status.configure(wraplength=max(e.width - 8, 100)))

    # ------------------------------------------------------------------
    # Game switching (runs on the Tk thread - called from event handlers)
    # ------------------------------------------------------------------
    def _on_binder_clicked(self) -> None:
        selection = self._binder_list.curselection()
        if not selection:
            return
        game = self._binder_list.get(selection[0])
        self._activate_game(game)

    def _on_save_clicked(self) -> None:
        """Renames the currently active binder to whatever's typed in the
        field (moving its saved entries, if any), and makes the new name
        active. This is the only thing that ever renames a binder - typing
        alone, without clicking this, never touches saved data. Renaming
        onto another binder that already has entries merges the two, so
        that asks first."""
        old_name = self.current_game()
        # resolved here, not left to history.rename_game: a blank name means
        # THIS language's untitled bucket, the one the page will then show
        new_name = self._game_var.get().strip() or self._t["no_game"]
        if new_name == old_name:
            return
        games = history.list_games()
        if old_name in games and new_name in games and not messagebox.askyesno(
            self._t["merge_confirm_title"],
            self._t["merge_confirm_body"].format(old=old_name, new=new_name),
        ):
            self._game_var.set(old_name)
            return
        history.rename_game(old_name, new_name)
        self._renamed[old_name] = new_name
        self._activate_game(new_name)
        self.refresh_binders()

    def _on_new_chat_clicked(self) -> None:
        """Starts a fresh, empty conversation - doesn't touch any saved
        binder until a real question gets asked (or "Salva"/"Save" is used
        to name it first)."""
        self._activate_game("")
        if self._on_new_chat:
            self._on_new_chat()

    def _on_delete_clicked(self) -> None:
        game = self.current_game()
        if not messagebox.askyesno(
            self._t["delete_confirm_title"],
            self._t["delete_confirm_body"].format(game=game),
        ):
            return
        history.delete_game(game)
        self._deleted.add(game)
        self._activate_game("")
        if self._on_new_chat:
            self._on_new_chat()
        self.refresh_binders()

    def _on_delete_all_clicked(self) -> None:
        if not messagebox.askyesno(
            self._t["delete_all_title"],
            self._t["delete_all_body"],
            icon="warning",
            default="no",
        ):
            return
        userdata.delete_all()
        messagebox.showinfo(self._t["delete_all_title"], self._t["delete_all_done"])
        # Again, right before closing: while that message was open, an answer
        # Rick was still working on could have been saved (the dialog keeps
        # Tk's event loop running). Closing then stops Rick for good, so
        # neither the keys nor the conversation stay in memory either.
        userdata.delete_all()
        self._handle_close()

    def _activate_game(self, game: str) -> None:
        """Makes `game` the active binder: new questions get saved under it,
        and its saved history is loaded into the page. An empty/blank name
        always resolves to the localized "no game" bucket, so what's shown
        here and what append_turn() later saves under always agree."""
        game = game.strip() or self._t["no_game"]
        # (re)opening a name makes it a live binder again, whatever happened
        # to an older binder with the same name
        self._renamed.pop(game, None)
        self._deleted.discard(game)
        with self._game_lock:
            self._current_game = game
        self._game_var.set(game)
        self._render_history(game)
        self._select_in_list(game)

    def _render_history(self, game: str) -> None:
        entries = history.get_game_history(game)
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._page_has_entries = bool(entries)
        if not entries:
            self._text.insert("end", self._t["empty_binder"], "empty")
        else:
            for i, entry in enumerate(entries):
                self._insert_entry(entry["question"], entry["answer"], divider_first=i > 0)
        self._text.configure(state="disabled")
        self._text.see("end")

    def _insert_entry(self, question: str, answer: str, divider_first: bool) -> None:
        """Appends one Q&A pair's widgets to the (already state="normal")
        Text widget. Doesn't touch the history file - see append_turn()."""
        if divider_first:
            self._text.insert("end", "\n\n❧\n\n", "divider")
        self._text.insert("end", f"{self._t['you']}: ", "you")
        self._text.insert("end", question + "\n", "body")
        self._text.insert("end", f"{self._t['rick']}: ", "rick")
        self._text.insert("end", answer, "body")

    def _select_in_list(self, game: str) -> None:
        items = self._binder_list.get(0, "end")
        self._binder_list.selection_clear(0, "end")
        if game in items:
            self._binder_list.selection_set(items.index(game))

    # ------------------------------------------------------------------
    # Thread-safe public API (called from main.py's worker threads)
    # ------------------------------------------------------------------
    def current_game(self) -> str:
        with self._game_lock:
            return self._current_game

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self._status_var.set(text))

    def append_turn(self, game: str, question: str, answer: str) -> None:
        """Adds a Q&A pair to `game`'s binder and persists it there. `game`
        should be whatever current_game() returned when the question was
        asked - the caller captures it up front (rather than this method
        re-reading current_game() itself) so a game switch made while Rick
        is still thinking can't file the answer under the wrong binder.
        Only updates the visible page if that binder is still the one open;
        otherwise it's saved silently and will show up when it's reopened."""

        def _do() -> None:
            target = self._resolve_binder(game)
            if target is None:
                log.info("Not saving an answer for deleted binder %r", game)
                return
            history.add_entry(target, question, answer)
            if target == self.current_game():
                self._text.configure(state="normal")
                if not self._page_has_entries:
                    self._text.delete("1.0", "end")
                self._insert_entry(question, answer, divider_first=self._page_has_entries)
                self._page_has_entries = True
                self._text.configure(state="disabled")
                self._text.see("end")
            self.refresh_binders()

        self.root.after(0, _do)

    def _resolve_binder(self, game: str) -> str | None:
        """Where an answer asked under `game` belongs now: following any
        renames made since, or None if that binder was deleted."""
        seen = set()
        while game in self._renamed and game not in seen:
            seen.add(game)
            game = self._renamed[game]
        return None if game in self._deleted else game

    def refresh_binders(self) -> None:
        def _do() -> None:
            current = self._binder_list.get(0, "end")
            games = history.list_games()
            # the "current game" dropdown offers the same binders as the list
            self._game_combo["values"] = games
            if list(current) == games:
                return
            self._binder_list.delete(0, "end")
            for game in games:
                self._binder_list.insert("end", game)
            self._select_in_list(self.current_game())

        self.root.after(0, _do)

    # ------------------------------------------------------------------
    def _report_callback_exception(self, exc_type, exc_value, exc_tb) -> None:
        """Tk prints errors from button clicks and after() callbacks to a
        console Rick doesn't have (pythonw): log them and say so instead."""
        log.error("Error in a window callback", exc_info=(exc_type, exc_value, exc_tb))
        self._status_var.set(self._t["ui_error"].format(error=describe_error(exc_value)))

    def _handle_close(self) -> None:
        if self._on_close:
            self._on_close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
