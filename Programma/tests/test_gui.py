"""The book window (rick/gui.py): binders, the Save / Delete / New chat
buttons, and answers that arrive while the player is changing binders.
Opens real Tk windows, so it needs a display (skipped automatically
without one; on a headless Linux box run the suite under xvfb-run)."""

import threading
import unittest
from unittest import mock

import rick
from rick import config, gui, history, hotkeys, updates

from support import call_on_tk, flush, isolate_rick_home, require_display, run_with_mainloop
from test_hotkey_picker import press


class GuiTestCase(unittest.TestCase):
    language = "it"

    def setUp(self):
        require_display(self)
        isolate_rick_home(self)
        self.new_chats = 0
        opened = mock.patch.object(gui.webbrowser, "open")
        self.browser_open = opened.start()
        self.addCleanup(opened.stop)
        self.book = gui.BookWindow(
            language=self.language, on_new_chat=self.count_new_chat, shortcut=self.make_shortcut()
        )
        self.addCleanup(self.book.root.destroy)
        self.pump()

    def make_shortcut(self):
        return None  # no "Keys" button, unless a test class gives one

    def count_new_chat(self):
        self.new_chats += 1

    # -- helpers ---------------------------------------------------------
    def pump(self):
        """Runs what BookWindow queued with after(0) (twice: some of those
        callbacks queue a follow-up of their own)."""
        self.book.root.update()
        self.book.root.update()

    def page(self):
        return self.book._text.get("1.0", "end-1c")

    def binders(self):
        return list(self.book._binder_list.get(0, "end"))

    def dropdown(self):
        return list(self.book._game_combo.cget("values"))

    def open_binder(self, game):
        self.book._activate_game(game)
        self.pump()

    def answer(self, game, question, answer="risposta"):
        self.book.append_turn(game, question, answer)
        self.pump()

    def save_as(self, name, confirm=True):
        self.book._game_var.set(name)
        with mock.patch.object(gui.messagebox, "askyesno", return_value=confirm) as ask:
            self.book._on_save_clicked()
        self.pump()
        return ask

    def delete_current(self, confirm=True):
        with mock.patch.object(gui.messagebox, "askyesno", return_value=confirm):
            self.book._on_delete_clicked()
        self.pump()

    def questions(self, game):
        return [e["question"] for e in history.get_game_history(game)]


class BindersTest(GuiTestCase):
    def test_starts_on_an_empty_untitled_page(self):
        self.assertEqual(self.book.current_game(), history.NO_GAME_KEY_IT)
        self.assertEqual(self.page(), self.book._t["empty_binder"])

    def test_answers_are_saved_and_shown(self):
        self.open_binder("Elden Ring")
        self.answer("Elden Ring", "dove trovo lo scudo?", "Nella palude.")
        self.assertEqual(self.questions("Elden Ring"), ["dove trovo lo scudo?"])
        self.assertIn("dove trovo lo scudo?", self.page())
        self.assertIn("Nella palude.", self.page())
        self.assertEqual(self.binders(), ["Elden Ring"])

    def test_dropdown_lists_the_saved_binders(self):
        history.add_entry("Zelda", "q", "a")
        history.add_entry("Elden Ring", "q", "a")
        self.book.refresh_binders()
        self.pump()
        self.assertEqual(self.dropdown(), ["Elden Ring", "Zelda"])
        self.answer("Hollow Knight: Silksong {DLC}", "q")
        self.assertIn("Hollow Knight: Silksong {DLC}", self.dropdown())

    def test_picking_from_the_dropdown_switches_without_merging(self):
        history.add_entry("Zelda", "domanda zelda", "a")
        self.open_binder("Elden Ring")
        self.answer("Elden Ring", "domanda elden", "a")
        self.book._game_var.set("Zelda")
        self.book._game_combo.event_generate("<<ComboboxSelected>>")
        self.pump()
        self.assertEqual(self.book.current_game(), "Zelda")
        self.assertIn("domanda zelda", self.page())
        self.assertEqual(self.questions("Elden Ring"), ["domanda elden"])  # untouched

    def test_typing_alone_renames_nothing(self):
        self.open_binder("Elden Ring")
        self.answer("Elden Ring", "q")
        self.book._game_var.set("Elden Ring GOTY")
        self.pump()
        self.assertEqual(self.book.current_game(), "Elden Ring")
        self.assertEqual(self.binders(), ["Elden Ring"])


class SaveTest(GuiTestCase):
    def test_save_renames_the_binder(self):
        self.open_binder("Elden Ring")
        self.answer("Elden Ring", "q")
        self.save_as("Elden Ring GOTY")
        self.assertEqual(self.book.current_game(), "Elden Ring GOTY")
        self.assertEqual(self.questions("Elden Ring GOTY"), ["q"])
        self.assertEqual(self.binders(), ["Elden Ring GOTY"])

    def test_naming_an_empty_chat_creates_no_binder_until_a_question(self):
        self.save_as("Hollow Knight")
        self.assertEqual(self.book.current_game(), "Hollow Knight")
        self.assertEqual(self.binders(), [])
        self.answer("Hollow Knight", "q")
        self.assertEqual(self.binders(), ["Hollow Knight"])

    def test_saving_onto_an_existing_binder_asks_before_merging(self):
        history.add_entry("Zelda", "vecchia", "a")
        self.open_binder("Zeld")
        self.answer("Zeld", "nuova")
        ask = self.save_as("Zelda", confirm=False)
        ask.assert_called_once()
        self.assertEqual(self.book.current_game(), "Zeld")  # nothing changed...
        self.assertEqual(self.book._game_var.get(), "Zeld")  # ...and the field says so
        self.assertEqual(self.questions("Zeld"), ["nuova"])
        self.save_as("Zelda", confirm=True)
        self.assertEqual(self.questions("Zelda"), ["vecchia", "nuova"])
        self.assertEqual(self.binders(), ["Zelda"])

    def test_no_question_when_nothing_would_be_merged(self):
        history.add_entry("Zelda", "q", "a")
        ask = self.save_as("Zelda")  # the untitled page has no entries yet
        ask.assert_not_called()
        self.assertEqual(self.book.current_game(), "Zelda")

    def test_blank_name_is_this_languages_untitled_binder(self):
        self.open_binder("Zelda")
        self.answer("Zelda", "q")
        self.save_as("   ")
        self.assertEqual(self.book.current_game(), history.NO_GAME_KEY_IT)
        self.assertEqual(self.questions(history.NO_GAME_KEY_IT), ["q"])


class EnglishSaveTest(GuiTestCase):
    language = "en"

    def test_blank_name_is_this_languages_untitled_binder(self):
        # it used to move the entries to "Senza titolo" while showing
        # "Untitled", so they looked lost
        self.open_binder("Zelda")
        self.answer("Zelda", "q")
        self.save_as("")
        self.assertEqual(self.book.current_game(), history.NO_GAME_KEY_EN)
        self.assertEqual(self.questions(history.NO_GAME_KEY_EN), ["q"])
        self.assertIn("q", self.page())


class NewChatAndDeleteTest(GuiTestCase):
    def test_new_chat_opens_an_empty_page_and_resets_the_conversation(self):
        self.answer(history.NO_GAME_KEY_IT, "q")
        self.book._on_new_chat_clicked()
        self.pump()
        self.assertEqual(self.book.current_game(), history.NO_GAME_KEY_IT)
        self.assertEqual(self.new_chats, 1)

    def test_delete_removes_the_binder_and_resets_the_conversation(self):
        self.open_binder("Zelda")
        self.answer("Zelda", "q")
        self.delete_current()
        self.assertEqual(history.list_games(), [])
        self.assertEqual(self.binders(), [])
        self.assertEqual(self.book.current_game(), history.NO_GAME_KEY_IT)
        self.assertEqual(self.new_chats, 1)

    def test_delete_can_be_cancelled(self):
        self.open_binder("Zelda")
        self.answer("Zelda", "q")
        self.delete_current(confirm=False)
        self.assertEqual(self.questions("Zelda"), ["q"])
        self.assertEqual(self.new_chats, 0)


class DeleteAllDataTest(GuiTestCase):
    def setUp(self):
        super().setUp()
        self.open_binder("Zelda")
        self.answer("Zelda", "q")
        config.save_gemini_api_key("gem-key")
        closed = mock.patch.object(self.book, "_handle_close")
        self.close = closed.start()
        self.addCleanup(closed.stop)

    def click(self, confirm, during_info=None):
        with mock.patch.object(gui.messagebox, "askyesno", return_value=confirm) as ask, \
             mock.patch.object(gui.messagebox, "showinfo", side_effect=during_info) as info:
            self.book._on_delete_all_clicked()
        self.pump()
        return ask, info

    def test_cancel_keeps_everything(self):
        ask, info = self.click(confirm=False)
        self.assertEqual(ask.call_args.kwargs["default"], "no")  # Enter doesn't wipe by accident
        info.assert_not_called()
        self.close.assert_not_called()
        self.assertEqual(self.questions("Zelda"), ["q"])

    def test_confirm_deletes_everything_and_closes_rick(self):
        _ask, info = self.click(confirm=True)
        info.assert_called_once()
        self.close.assert_called_once()
        self.assertEqual(history.list_games(), [])
        self.assertFalse(config.USER_CONFIG_FILE.exists())

    def test_answer_saved_while_the_done_message_is_open_is_erased_too(self):
        self.click(confirm=True, during_info=lambda *a: history.add_entry("Zelda", "late", "a"))
        self.assertEqual(history.list_games(), [])


class AnswersInFlightTest(GuiTestCase):
    """app.py captures the active binder when a question is asked, and
    hands it to append_turn() once Rick has answered - seconds later."""

    def test_answer_lands_in_the_binder_it_was_asked_in(self):
        self.open_binder("Elden Ring")
        root = self.book.root

        def worker():  # the way app.py's worker thread does it
            game = self.book.current_game()
            call_on_tk(root, lambda: self.book._activate_game("Hollow Knight"))
            self.book.append_turn(game, "dove trovo lo scudo?", "Nella palude.")
            flush(root)

        run_with_mainloop(root, worker)
        self.assertEqual(self.questions("Elden Ring"), ["dove trovo lo scudo?"])
        self.assertEqual(self.questions("Hollow Knight"), [])
        self.assertEqual(self.page(), self.book._t["empty_binder"])

    def test_renamed_while_thinking_follows_the_new_name(self):
        self.open_binder("Zeld")
        self.answer("Zeld", "prima")
        asked_in = self.book.current_game()
        self.save_as("Zelda")
        self.answer(asked_in, "seconda")
        self.assertEqual(self.questions("Zelda"), ["prima", "seconda"])
        self.assertEqual(self.binders(), ["Zelda"])  # "Zeld" didn't come back
        self.assertIn("seconda", self.page())

    def test_renamed_twice_while_thinking(self):
        self.open_binder("A")
        self.answer("A", "q1")
        self.save_as("B")
        self.save_as("C")
        self.answer("A", "q2")
        self.assertEqual(self.questions("C"), ["q1", "q2"])
        self.assertEqual(self.binders(), ["C"])

    def test_deleted_while_thinking_stays_deleted(self):
        self.open_binder("Zelda")
        self.answer("Zelda", "prima")
        self.delete_current()
        self.answer("Zelda", "risposta in ritardo")
        self.assertEqual(history.list_games(), [])
        self.assertEqual(self.page(), self.book._t["empty_binder"])

    def test_a_deleted_name_can_be_used_again(self):
        self.open_binder("Zelda")
        self.answer("Zelda", "vecchia")
        self.delete_current()
        self.save_as("Zelda")
        self.answer("Zelda", "nuova")
        self.assertEqual(self.questions("Zelda"), ["nuova"])


class WindowTest(GuiTestCase):
    def test_errors_in_callbacks_are_logged_and_shown(self):
        # with pythonw there's no console for Tk to print them to
        with self.assertLogs(gui.log, "ERROR"):
            self.book.root.after(0, lambda: history.add_entry(None, "q", "a"))
            self.pump()
        self.assertIn("rick.log", self.book._status_var.get())

    def test_status_bar_stays_visible_at_minimum_size(self):
        self.book.set_status("pronto")
        self.book.root.geometry("640x420")
        self.pump()
        status = next(
            w for w in self.book.root.winfo_children()
            if isinstance(w, gui.tk.Label) and str(w.cget("textvariable")) == str(self.book._status_var)
        )
        self.assertGreater(status.winfo_height(), 5)
        self.assertEqual(self.book.root.minsize(), (640, 420))

    def portraits(self):
        sidebar = self.book._binder_list.master.master
        return [
            w for w in sidebar.winfo_children()
            if isinstance(w, gui.tk.Label) and w.cget("image") and w.winfo_manager() == "pack"
        ]

    def resize(self, geometry):
        self.book.root.geometry(geometry)
        self.pump()

    def test_portrait_is_shown_pixel_doubled(self):
        self.resize("820x560")
        (portrait,) = self.portraits()
        self.assertEqual(portrait.winfo_reqwidth(), 128 + 2 * 3)  # 32px art at 4x, gold frame

    def test_short_window_shrinks_the_portrait_and_keeps_the_list_usable(self):
        self.resize("640x420")
        (portrait,) = self.portraits()
        self.assertEqual(portrait.winfo_reqwidth(), 64 + 2 * 3)
        self.assertGreaterEqual(self.book._binder_list.winfo_height(), 60)
        self.resize("820x560")  # and back
        self.assertEqual(portrait.winfo_reqwidth(), 128 + 2 * 3)

    def test_support_link_opens_ko_fi(self):
        def find(widget):
            for child in widget.winfo_children():
                if isinstance(child, gui.tk.Label) and child.cget("text") == self.book._t["support_link"]:
                    return child
                found = find(child)
                if found:
                    return found
            return None

        link = find(self.book.root)
        self.assertEqual(str(link.cget("cursor")), "hand2")
        link.event_generate("<Button-1>")
        self.pump()
        self.browser_open.assert_called_once_with(gui.SPONSORS_URL)


class MissingPortraitTest(GuiTestCase):
    def setUp(self):
        missing = mock.patch.object(gui, "_PORTRAIT_FILE", gui._PORTRAIT_FILE.with_name("nope.png"))
        missing.start()
        self.addCleanup(missing.stop)
        super().setUp()

    def test_window_works_without_the_portrait(self):
        sidebar = self.book._binder_list.master.master
        packed_images = [
            w for w in sidebar.winfo_children()
            if isinstance(w, gui.tk.Label) and w.cget("image") and w.winfo_manager() == "pack"
        ]
        self.assertEqual(packed_images, [])
        self.answer(history.NO_GAME_KEY_IT, "q")
        self.assertIn("q", self.page())


class FakeShortcut:
    """Stands in for app.Shortcut: the keys Rick listens on."""

    def __init__(self, keys="alt+r", locked=False, works=True):
        self.keys, self.locked, self.works = keys, locked, works
        self.paused = []
        self.changes = []

    @property
    def label(self):
        return hotkeys.label(self.keys)

    def pause(self, paused):
        self.paused.append(paused)

    def change(self, keys):
        self.changes.append(keys)
        if self.works:
            self.keys = keys
        return self.works


class KeysButtonTest(GuiTestCase):
    """The "Keys" button: new keys picked in a small window, in use at once."""

    def make_shortcut(self):
        self.shortcut = FakeShortcut()
        return self.shortcut

    def button_text(self):
        return self.book._keys_button.cget("text")

    def open_dialog(self):
        self.book._keys_button.invoke()
        self.pump()
        return self.book._keys_dialog

    def test_button_shows_the_keys_in_use(self):
        self.assertEqual(self.button_text(), "⌨️ Tasti: Alt+R")

    def test_picking_and_saving_switches_the_keys(self):
        dialog = self.open_dialog()
        self.assertEqual(self.shortcut.paused, [True])  # Alt+R can't start a recording meanwhile
        self.assertTrue(dialog["picker"].capturing)  # ready for the keys straight away
        self.assertEqual(dialog["save"].cget("state"), "disabled")
        press(dialog["picker"], "Control_L", "Shift_L", "F9")
        self.assertEqual(dialog["save"].cget("state"), "normal")
        dialog["save"].invoke()
        self.pump()
        self.assertEqual(self.shortcut.changes, ["ctrl+shift+f9"])
        self.assertEqual(self.shortcut.paused, [True, False])
        self.assertIsNone(self.book._keys_dialog)
        self.assertFalse(dialog["window"].winfo_exists())
        self.assertEqual(self.button_text(), "⌨️ Tasti: Ctrl+Shift+F9")

    def test_cancel_changes_nothing(self):
        dialog = self.open_dialog()
        press(dialog["picker"], "Alt_L", "k")
        self.book._close_keys_dialog()  # Annulla, or the window's X
        self.pump()
        self.assertEqual(self.shortcut.changes, [])
        self.assertEqual(self.shortcut.paused, [True, False])
        self.assertEqual(self.button_text(), "⌨️ Tasti: Alt+R")

    def test_keys_this_pc_refuses_are_explained_and_the_old_ones_kept(self):
        self.shortcut.works = False
        dialog = self.open_dialog()
        press(dialog["picker"], "Alt_L", "k")
        dialog["save"].invoke()
        self.pump()
        self.assertIn("Alt+R", dialog["problem"].cget("text"))
        self.assertTrue(dialog["window"].winfo_exists())  # still open, to try other keys
        self.assertEqual(self.shortcut.paused, [True])
        self.assertEqual(self.button_text(), "⌨️ Tasti: Alt+R")
        self.book._close_keys_dialog()
        self.assertEqual(self.shortcut.paused, [True, False])

    def test_a_second_click_brings_back_the_same_window(self):
        first = self.open_dialog()
        self.assertIs(self.open_dialog(), first)
        self.assertEqual(self.shortcut.paused, [True])

    def test_shown_after_app_falls_back_to_alt_r(self):
        self.shortcut.keys = "f9"
        self.book.show_shortcut()  # thread-safe
        self.pump()
        self.assertEqual(self.button_text(), "⌨️ Tasti: F9")

    def test_closing_twice_is_harmless(self):
        self.book._keys_button.invoke()
        self.pump()
        self.book._close_keys_dialog()
        self.book._close_keys_dialog()  # twice: harmless
        self.assertEqual(self.shortcut.paused, [True, False])


class LockedKeysButtonTest(GuiTestCase):
    def make_shortcut(self):
        self.shortcut = FakeShortcut("ctrl+shift+r", locked=True)
        return self.shortcut

    def test_keys_from_env_can_be_seen_but_not_changed(self):
        self.book._keys_button.invoke()
        self.pump()
        dialog = self.book._keys_dialog
        self.assertFalse(dialog["picker"].capturing)
        self.assertEqual(dialog["save"].winfo_manager(), "")  # no Save button at all
        self.book._close_keys_dialog()
        self.assertEqual(self.shortcut.changes, [])


class NoShortcutTest(GuiTestCase):
    def test_no_keys_button_without_a_shortcut(self):
        self.assertIsNone(self.book._keys_button)



class UpdateNoticeTest(GuiTestCase):
    """The strip over the page that says a newer Rick is out (the check
    itself is rick/updates.py)."""

    def banner_shown(self):
        return self.book._update_banner.winfo_manager() == "pack"

    def notice(self):
        return self.book._update_link.cget("text")

    def test_hidden_until_a_newer_version_is_found(self):
        self.assertFalse(self.banner_shown())

    def test_shown_over_the_page_from_the_checks_thread(self):
        def driver():
            # like updates.watch: called on its own thread while Tk runs
            self.book.show_update("1.0.3")
            call_on_tk(self.book.root, lambda: None)

        run_with_mainloop(self.book.root, driver)
        self.assertTrue(self.banner_shown())
        self.assertEqual(
            self.notice(),
            f"🆕 Nuova versione: Rick 1.0.3 (tu hai la {rick.__version__}). Se qualcosa non funziona, "
            "l'aggiornamento potrebbe averlo gia' risolto: clicca qui per scaricarlo",
        )
        main = self.book._update_banner.master
        order = main.pack_slaves()
        self.assertLess(order.index(self.book._update_banner), order.index(self.book._text.master))

    def test_click_opens_the_download_page(self):
        self.book.show_update("1.0.3")
        self.pump()
        self.book._update_link.event_generate("<Button-1>")
        self.pump()
        self.browser_open.assert_called_once_with(updates.DOWNLOAD_PAGE)

    def test_x_hides_it_and_a_later_version_shows_it_again(self):
        self.book.show_update("1.0.3")
        self.pump()
        self.book._update_hide.event_generate("<Button-1>")
        self.pump()
        self.assertFalse(self.banner_shown())
        self.book.show_update("1.0.4")
        self.pump()
        self.assertTrue(self.banner_shown())
        self.assertIn("1.0.4", self.notice())
        self.browser_open.assert_not_called()

    def test_the_page_and_the_x_stay_usable_at_minimum_size(self):
        self.book.show_update("1.0.3")
        for geometry in ("820x560", "640x420"):
            with self.subTest(geometry=geometry):
                self.book.root.geometry(geometry)
                self.pump()
                self.assertGreater(self.book._update_banner.winfo_height(), 10)
                self.assertGreater(self.book._text.winfo_height(), 60)
                self.assertTrue(self.book._update_hide.winfo_ismapped())  # the long notice leaves it room
                self.assertGreater(self.book._update_hide.winfo_width(), 10)

    def test_when_running_waits_for_the_window(self):
        calls = []
        self.book.when_running(lambda: calls.append(threading.current_thread()))
        self.assertEqual(calls, [])
        self.pump()
        self.assertEqual(calls, [threading.main_thread()])


class EnglishUpdateNoticeTest(GuiTestCase):
    language = "en"

    def test_notice_in_english(self):
        self.book.show_update("1.1")
        self.pump()
        self.assertEqual(
            self.book._update_link.cget("text"),
            f"🆕 New version: Rick 1.1 (you have {rick.__version__}). If something isn't working, "
            "the update may already fix it: click here to download it",
        )


if __name__ == "__main__":
    unittest.main()
