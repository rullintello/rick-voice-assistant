"""The book window (rick/gui.py): binders, the Save / Delete / New chat
buttons, and answers that arrive while the player is changing binders.
Opens real Tk windows, so it needs a display (skipped automatically
without one; on a headless Linux box run the suite under xvfb-run)."""

import unittest
from unittest import mock

from rick import config, gui, history

from support import call_on_tk, flush, isolate_rick_home, require_display, run_with_mainloop


class GuiTestCase(unittest.TestCase):
    language = "it"

    def setUp(self):
        require_display(self)
        isolate_rick_home(self)
        self.new_chats = 0
        opened = mock.patch.object(gui.webbrowser, "open")
        self.browser_open = opened.start()
        self.addCleanup(opened.stop)
        self.book = gui.BookWindow(language=self.language, on_new_chat=self.count_new_chat)
        self.addCleanup(self.book.root.destroy)
        self.pump()

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


if __name__ == "__main__":
    unittest.main()
