import os
import unittest
from unittest import mock

from rick import config, history, jsonstore, search

from support import isolate_rick_home


class JsonStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = isolate_rick_home(self)
        self.path = self.tmp / "data.json"

    def test_round_trip(self):
        jsonstore.write_json(self.path, {"a": [1, "è"]})
        self.assertEqual(jsonstore.read_json(self.path, None), {"a": [1, "è"]})

    def test_missing_file_returns_default(self):
        self.assertEqual(jsonstore.read_json(self.path, {"x": 1}), {"x": 1})

    def test_corrupt_file_is_moved_aside_not_destroyed(self):
        self.path.write_text('{"half-writ', encoding="utf-8")
        self.assertEqual(jsonstore.read_json(self.path, {}), {})
        self.assertFalse(self.path.exists())
        backups = list(self.tmp.glob("data.json.corrupt-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), '{"half-writ')

    def test_failed_write_leaves_old_file_and_no_temp_files(self):
        jsonstore.write_json(self.path, {"old": True})
        with self.assertRaises(TypeError):
            jsonstore.write_json(self.path, {"not serializable": object()})
        self.assertEqual(jsonstore.read_json(self.path, None), {"old": True})
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["data.json"])

    def test_retries_when_destination_is_briefly_locked(self):
        real_replace = os.replace
        calls = {"n": 0}

        def flaky_replace(src, dst):
            calls["n"] += 1
            if calls["n"] < 3:
                raise PermissionError("[WinError 32] file in use")
            return real_replace(src, dst)

        with mock.patch.object(jsonstore.os, "replace", flaky_replace), \
             mock.patch.object(jsonstore, "_REPLACE_RETRY_DELAY", 0):
            jsonstore.write_json(self.path, {"ok": 1})
        self.assertEqual(jsonstore.read_json(self.path, None), {"ok": 1})
        self.assertEqual(calls["n"], 3)


class HistoryTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)

    def _entry(self, question, timestamp):
        return {"question": question, "answer": "a", "timestamp": timestamp}

    def test_add_and_get(self):
        history.add_entry("Elden Ring", "q1", "a1")
        history.add_entry("Elden Ring", "q2", "a2")
        self.assertEqual([e["question"] for e in history.get_game_history("Elden Ring")], ["q1", "q2"])
        self.assertEqual(history.get_game_history("Nope"), [])

    def test_list_games_most_recent_first(self):
        # explicit timestamps: the order must not depend on the OS clock's
        # resolution between two back-to-back calls
        jsonstore.write_json(config.HISTORY_FILE, {
            "Old": [self._entry("q", "2026-01-01T00:00:00+00:00")],
            "Newest": [self._entry("q", "2026-03-01T00:00:00.000002+00:00")],
            "Mid": [self._entry("q", "2026-03-01T00:00:00+00:00")],
        })
        self.assertEqual(history.list_games(), ["Newest", "Mid", "Old"])

    def test_timestamps_have_sub_second_precision(self):
        history.add_entry("Zelda", "q", "a")
        self.assertRegex(history.get_game_history("Zelda")[0]["timestamp"], r"\.\d{6}\+00:00$")

    def test_rename_moves_entries(self):
        history.add_entry("Zeld", "q", "a")
        history.rename_game("Zeld", "Zelda")
        self.assertEqual(history.get_game_history("Zeld"), [])
        self.assertEqual(len(history.get_game_history("Zelda")), 1)

    def test_merge_keeps_chronological_order(self):
        jsonstore.write_json(config.HISTORY_FILE, {
            "A": [self._entry("a-old", "2026-01-01T00:00:00+00:00"),
                  self._entry("a-new", "2026-03-01T00:00:00+00:00")],
            "B": [self._entry("b-mid", "2026-02-01T00:00:00+00:00")],
        })
        history.rename_game("A", "B")
        self.assertEqual([e["question"] for e in history.get_game_history("B")],
                         ["a-old", "b-mid", "a-new"])

    def test_rename_to_blank_is_a_no_op(self):
        history.add_entry("Zelda", "q", "a")
        history.rename_game("Zelda", "   ")
        self.assertEqual(len(history.get_game_history("Zelda")), 1)
        self.assertEqual(history.list_games(), ["Zelda"])

    def test_delete(self):
        history.add_entry("Zelda", "q", "a")
        history.delete_game("Zelda")
        self.assertEqual(history.list_games(), [])
        history.delete_game("Zelda")  # already gone: no error

    def test_corrupt_history_is_preserved_for_recovery(self):
        config.HISTORY_FILE.write_text('{"Zelda": [{"question": "q"', encoding="utf-8")
        history.add_entry("Elden Ring", "q", "a")
        self.assertEqual(history.list_games(), ["Elden Ring"])
        backups = list(config.HISTORY_FILE.parent.glob("history.json.corrupt-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn("Zelda", backups[0].read_text(encoding="utf-8"))

    def test_is_untitled(self):
        for name in ("", "  ", history.NO_GAME_KEY_IT, history.NO_GAME_KEY_EN):
            self.assertTrue(history.is_untitled(name), name)
        self.assertFalse(history.is_untitled("Elden Ring"))


class UserConfigTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)

    def test_keys_and_language_round_trip(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "", "RICK_LANGUAGE": ""}):
            config.save_gemini_api_key("  gem  ")
            config.save_language("en")
            self.assertEqual(config.get_gemini_api_key(), "gem")
            self.assertEqual(config.get_language(), "en")

    def test_env_var_overrides_stored_value(self):
        config.save_language("en")
        with mock.patch.dict(os.environ, {"RICK_LANGUAGE": "it"}):
            self.assertEqual(config.get_language(), "it")


class SearchCacheTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        env = mock.patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"})
        env.start()
        self.addCleanup(env.stop)
        client_cls = mock.patch.object(search, "TavilyClient")
        self.client_cls = client_cls.start()
        self.addCleanup(client_cls.stop)
        self.client_cls.return_value.search.return_value = {
            "results": [{"title": "T", "content": "C", "url": "U"}]
        }

    def test_second_identical_query_is_served_from_cache(self):
        first = search.search_web("Elden Ring scudo")
        second = search.search_web("  elden ring SCUDO ")
        self.assertEqual(first, second)
        self.assertEqual(self.client_cls.return_value.search.call_count, 1)

    def test_malformed_cache_entry_is_ignored_not_fatal(self):
        key = search._cache_key("q")
        jsonstore.write_json(config.SEARCH_CACHE_FILE, {key: {"unexpected": True}})
        self.assertIn("C", search.search_web("q"))

    def test_network_error_falls_back_to_stale_cache(self):
        key = search._cache_key("q")
        jsonstore.write_json(config.SEARCH_CACHE_FILE, {key: {"ts": 0, "context": "old result"}})
        self.client_cls.return_value.search.side_effect = OSError("offline")
        self.assertEqual(search.search_web("q"), "old result")

    def test_no_key_means_no_search(self):
        with mock.patch.dict(os.environ, {"TAVILY_API_KEY": ""}):
            self.assertEqual(search.search_web("q"), "")
        self.client_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
