"""rick/userdata.py: Rick's temp audio folder, and "Delete all my data"."""

import logging
import os
import time
import unittest
import unittest.mock

from rick import config, history, jsonstore, startup, userdata

from support import isolate_rick_home


class TempFilesTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)

    def age(self, path, seconds):
        old = time.time() - seconds
        os.utime(path, (old, old))

    def test_temp_files_live_in_rick_s_own_folder(self):
        path = userdata.new_temp_path(".wav")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(os.path.dirname(path), str(config.TEMP_DIR))

    def test_leftovers_from_a_previous_run_are_swept_at_startup(self):
        leftover = userdata.new_temp_path(".wav")
        self.age(leftover, 3600)
        in_use = userdata.new_temp_path(".mp3")  # e.g. another Rick, mid-answer
        userdata.purge_leftover_temp_files()
        self.assertFalse(os.path.exists(leftover))
        self.assertTrue(os.path.exists(in_use))

    def test_sweeping_never_touches_rick_s_memory(self):
        history.add_entry("Elden Ring", "q", "a")
        self.age(userdata.new_temp_path(".wav"), 3600)
        userdata.purge_leftover_temp_files()
        self.assertEqual(len(history.get_game_history("Elden Ring")), 1)

    def test_nothing_to_sweep_is_fine(self):
        userdata.purge_leftover_temp_files()  # folder doesn't even exist yet


class DeleteAllTest(unittest.TestCase):
    def setUp(self):
        self.tmp = isolate_rick_home(self)

    def test_everything_is_erased(self):
        history.add_entry("Elden Ring", "q", "a")
        config.save_gemini_api_key("gem-key")
        jsonstore.write_json(config.SEARCH_CACHE_FILE, {"k": {"ts": 0, "context": "c"}})
        (self.tmp / "history.json.corrupt-20260101-000000").write_text("{old")
        (self.tmp / ".config.json.abc123.tmp").write_text('{"gemini_api_key": "gem-key"}')
        userdata.new_temp_path(".wav")
        startup.LOG_FILE.write_text("old log\n")
        (self.tmp / "rick.log.1").write_text("older log\n")

        userdata.delete_all()

        self.assertEqual(history.list_games(), [])
        with unittest.mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            self.assertEqual(config.get_gemini_api_key(), "")
        leftovers = sorted(p.name for p in self.tmp.rglob("*") if p.is_file())
        self.assertEqual(leftovers, [])

    def test_open_log_is_emptied_in_place(self):
        # while Rick runs, its log is open - Windows won't delete an open file
        handler = logging.FileHandler(startup.LOG_FILE, encoding="utf-8")
        root = logging.getLogger()
        root.addHandler(handler)
        self.addCleanup(handler.close)
        self.addCleanup(root.removeHandler, handler)
        root.error("a line mentioning Zelda")
        userdata.delete_all()
        handler.flush()
        text = startup.LOG_FILE.read_text(encoding="utf-8")
        self.assertNotIn("Zelda", text)

    def test_open_log_is_found_under_another_spelling_of_its_path(self):
        # On Windows the same folder can be spelled two ways (RUNNER~1 vs
        # runneradmin): the log must be recognised as the same file anyway.
        # A symlinked folder gives the same "two names, one file" on Linux.
        alias = self.tmp.parent / (self.tmp.name + "-alias")
        try:
            alias.symlink_to(self.tmp, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("can't create a symlink here")
        self.addCleanup(alias.unlink)
        handler = logging.FileHandler(alias / startup.LOG_FILE.name, encoding="utf-8")
        root = logging.getLogger()
        root.addHandler(handler)
        self.addCleanup(handler.close)
        self.addCleanup(root.removeHandler, handler)
        root.error("a line mentioning Zelda")
        with unittest.mock.patch.object(userdata, "remove_quietly"):  # like Windows: an open file can't be deleted
            userdata.delete_all()
        handler.flush()
        self.assertNotIn("Zelda", startup.LOG_FILE.read_text(encoding="utf-8"))

    def test_nothing_saved_yet_is_fine(self):
        userdata.delete_all()


if __name__ == "__main__":
    unittest.main()
