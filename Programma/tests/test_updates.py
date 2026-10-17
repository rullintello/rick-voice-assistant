"""Telling the player a newer Rick is out (rick/updates.py): reading
GitHub's answer, asking at most once a day, and the thread that keeps
checking while Rick is open. GitHub itself is faked: no network needed."""

import io
import json
import threading
import unittest
from unittest import mock

import rick
from rick import config, jsonstore, updates

from support import isolate_rick_home

NOW = 1_800_000_000.0
DAY = updates.CHECK_EVERY


class VersionTest(unittest.TestCase):
    def test_release_tags(self):
        self.assertEqual(updates.parse_version("v1.0.2"), (1, 0, 2))
        self.assertEqual(updates.parse_version(" 1.0.2 "), (1, 0, 2))
        self.assertEqual(updates.parse_version("v1.1"), (1, 1, 0))
        self.assertGreater(updates.parse_version("1.0.10"), updates.parse_version("1.0.9"))  # numbers, not text

    def test_anything_else_is_not_a_version(self):
        for text in (None, 5, "", "v", "1", "latest", "v1.1.0-beta", "1.0.2.1", "v1.0.x", "1.0.2\nhi"):
            with self.subTest(text=text):
                self.assertIsNone(updates.parse_version(text))

    def test_this_rick_has_a_version(self):
        # the release's tag on GitHub must be "v" + this
        self.assertIsNotNone(updates.parse_version(rick.__version__))


class FakeAnswer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FetchTest(unittest.TestCase):
    def answer(self, body):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        sent = {}

        def urlopen(request, timeout):
            sent.update(request=request, timeout=timeout)
            return FakeAnswer(body)

        with mock.patch.object(updates.urllib.request, "urlopen", urlopen):
            return updates.fetch_latest(), sent

    def test_reads_the_latest_releases_tag(self):
        latest, sent = self.answer({"tag_name": "v1.0.3", "name": "Rick 1.0.3", "body": "..."})
        self.assertEqual(latest, "1.0.3")
        request = sent["request"]
        self.assertEqual(request.full_url, "https://api.github.com/repos/rullintello/rick-voice-assistant/releases/latest")
        self.assertEqual(request.get_header("User-agent"), f"Rick/{rick.__version__}")  # nothing else about the player
        self.assertLessEqual(sent["timeout"], 30)

    def test_an_unexpected_answer_is_an_error(self):
        for body in ({"message": "Not Found"}, {"tag_name": "nightly"}, [], b"", b"<html>"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.answer(body)

    def test_an_oversized_answer_is_refused(self):
        with self.assertRaises(ValueError):
            self.answer(b" " * (updates._MAX_ANSWER_BYTES + 1))


class LatestVersionTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        self.asked = 0
        self.github = "1.0.3"  # what the fake GitHub answers (an exception: it fails)

    def fetch(self):
        self.asked += 1
        if isinstance(self.github, Exception):
            raise self.github
        return self.github

    def latest(self, now=NOW):
        return updates.latest_version(now, fetch=self.fetch)

    def saved(self):
        return jsonstore.read_json(config.UPDATE_CHECK_FILE, None)

    def test_github_is_asked_at_most_once_a_day(self):
        self.assertEqual(self.latest(), "1.0.3")
        self.assertEqual(self.saved(), {"checked_at": NOW, "latest": "1.0.3"})
        self.github = "1.0.4"
        self.assertEqual(self.latest(NOW + DAY - 60), "1.0.3")  # the saved answer
        self.assertEqual(self.asked, 1)
        self.assertEqual(self.latest(NOW + DAY), "1.0.4")
        self.assertEqual(self.asked, 2)

    def test_a_clock_set_back_asks_again(self):
        self.latest()
        self.latest(NOW - 60)
        self.assertEqual(self.asked, 2)

    def test_offline_gives_the_last_answer_however_old(self):
        self.latest()
        self.github = OSError("no internet")
        with self.assertLogs(updates.log, "INFO"):
            self.assertEqual(self.latest(NOW + 30 * DAY), "1.0.3")
        self.assertEqual(self.saved()["checked_at"], NOW)  # tried again next time

    def test_offline_with_nothing_saved(self):
        self.github = OSError("no internet")
        with self.assertLogs(updates.log, "INFO"):
            self.assertIsNone(self.latest())
        self.assertIsNone(self.saved())

    def test_a_broken_saved_answer_is_asked_again(self):
        for broken in ([], {"latest": "1.0.3"}, {"checked_at": "today", "latest": "1.0.3"},
                       {"checked_at": NOW, "latest": "nightly"}):
            with self.subTest(broken=broken):
                jsonstore.write_json(config.UPDATE_CHECK_FILE, broken)
                self.asked = 0
                self.assertEqual(self.latest(), "1.0.3")
                self.assertEqual(self.asked, 1)

    def test_an_unreadable_file_is_asked_again(self):
        config.UPDATE_CHECK_FILE.write_text("{half")
        with self.assertLogs("rick.jsonstore", "ERROR"):
            self.assertEqual(self.latest(), "1.0.3")

    def test_a_failed_save_still_answers(self):
        with mock.patch.object(updates.jsonstore, "write_json", side_effect=PermissionError("locked")), \
                self.assertLogs(updates.log, "WARNING"):
            self.assertEqual(self.latest(), "1.0.3")


class NewerVersionTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        patcher = mock.patch.object(updates, "__version__", "1.0.2")
        patcher.start()
        self.addCleanup(patcher.stop)

    def newer(self, latest):
        return updates.newer_version(NOW, fetch=lambda: latest)

    def test_only_a_newer_version_counts(self):
        self.assertEqual(self.newer("1.0.3"), "1.0.3")
        jsonstore.write_json(config.UPDATE_CHECK_FILE, {})
        self.assertEqual(self.newer("1.1"), "1.1")
        for same_or_older in ("1.0.2", "1.0", "0.9.9"):
            with self.subTest(latest=same_or_older):
                jsonstore.write_json(config.UPDATE_CHECK_FILE, {})
                self.assertIsNone(self.newer(same_or_older))

    def test_nothing_when_github_cant_be_reached(self):
        def offline():
            raise OSError("no internet")

        with self.assertLogs(updates.log, "INFO"):
            self.assertIsNone(updates.newer_version(NOW, fetch=offline))


class Stop(BaseException):
    """Ends watch()'s endless loop, from the fake sleep."""


class WatchTest(unittest.TestCase):
    def watch(self, answers, on_newer=None):
        told, sleeps = [], []
        answers = iter(answers)

        def newer():
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            return answer

        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 6:
                raise Stop

        def tell(version):
            told.append(version)
            if on_newer:
                on_newer(version)

        with self.assertRaises(Stop):
            updates.watch(tell, newer=newer, sleep=sleep)
        return told, sleeps

    def test_tells_each_new_version_once(self):
        told, sleeps = self.watch([None, "1.0.3", "1.0.3", "1.0.3", "1.0.4", "1.0.4"])
        self.assertEqual(told, ["1.0.3", "1.0.4"])
        self.assertTrue(all(0 < seconds <= DAY for seconds in sleeps))

    def test_keeps_going_after_an_error(self):
        with self.assertLogs(updates.log, "ERROR"):
            told, _ = self.watch([RuntimeError("bug"), "1.0.3", None, None, None, None])
        self.assertEqual(told, ["1.0.3"])

    def test_a_failing_notice_is_not_fatal_either(self):
        def window_gone(version):
            raise RuntimeError("window gone")

        with self.assertLogs(updates.log, "ERROR"):
            told, sleeps = self.watch(["1.0.3"] * 6, on_newer=window_gone)
        self.assertEqual((told, len(sleeps)), (["1.0.3"], 6))

    def test_start_runs_it_on_a_thread_that_ends_with_rick(self):
        found = threading.Event()
        # SystemExit: ends the thread quietly (Python doesn't report it)
        with mock.patch.object(updates, "newer_version", return_value="1.0.3"), \
                mock.patch.object(updates.time, "sleep", side_effect=SystemExit):
            thread = updates.start(lambda version: found.set())
            self.assertTrue(found.wait(5))
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertTrue(thread.daemon)


if __name__ == "__main__":
    unittest.main()
