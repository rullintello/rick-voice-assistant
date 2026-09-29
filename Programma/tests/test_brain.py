import unittest
from unittest import mock

from google.genai import errors as genai_errors

from rick import brain, config, history

from support import isolate_rick_home


def _server_error():
    return genai_errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}})


def _client_error():
    return genai_errors.ClientError(400, {"error": {"code": 400, "message": "bad", "status": "INVALID_ARGUMENT"}})


class FakeModels:
    """Stands in for client.models: records every request, answers from a
    script (a string, None for "no text", or an exception to raise)."""

    def __init__(self):
        self.requests = []
        self.script = []

    def generate_content(self, model, contents, config):
        self.requests.append(contents)
        item = self.script.pop(0) if self.script else "Risposta."
        if isinstance(item, BaseException):
            raise item
        return mock.Mock(text=item)


class BrainTest(unittest.TestCase):
    def setUp(self):
        isolate_rick_home(self)
        self.models = FakeModels()
        client = mock.patch.object(brain.genai, "Client", return_value=mock.Mock(models=self.models))
        client.start()
        self.addCleanup(client.stop)
        search_patch = mock.patch.object(brain.search, "search_web", return_value="")
        self.search_web = search_patch.start()
        self.addCleanup(search_patch.stop)
        web = mock.patch.object(config, "ENABLE_WEB_SEARCH", False)
        web.start()
        self.addCleanup(web.stop)
        sleep = mock.patch.object(brain.time, "sleep")  # retries without waiting
        sleep.start()
        self.addCleanup(sleep.stop)
        self.rick = brain.Rick()

    # -- helpers ---------------------------------------------------------
    def last_request(self):
        return self.models.requests[-1]

    def sent_question(self):
        return self.last_request()[-1].parts[0].text

    def roles(self, contents):
        return [c.role for c in contents]

    # -- saved per-game history ("second brain") -------------------------
    def test_saved_history_is_injected_for_a_named_game(self):
        history.add_entry("Elden Ring", "dove trovo lo scudo?", "Nella palude.")
        self.rick.ask("e la spada?", "Elden Ring")
        sent = self.sent_question()
        self.assertTrue(sent.startswith("e la spada?"))
        self.assertIn("Cronologia salvata per questo gioco", sent)
        self.assertIn("dove trovo lo scudo?", sent)

    def test_untitled_bucket_is_never_injected(self):
        for untitled in (history.NO_GAME_KEY_IT, history.NO_GAME_KEY_EN):
            history.add_entry(untitled, "domanda su Zelda", "risposta")
            self.rick.ask("altra domanda", untitled)
            self.assertNotIn("Cronologia salvata", self.sent_question())

    def test_other_games_never_leak_in(self):
        history.add_entry("Hollow Knight", "domanda hk", "risposta hk")
        self.rick.ask("domanda", "Elden Ring")
        self.assertNotIn("domanda hk", self.sent_question())

    def test_cap_keeps_only_the_most_recent_entries(self):
        for i in range(20):
            history.add_entry("Skyrim", f"q{i}?", f"a{i}.")
        self.rick.ask("nuova", "Skyrim")
        sent = self.sent_question()
        self.assertIn("q19?", sent)
        self.assertIn("q10?", sent)
        self.assertNotIn("q9?", sent)

    def test_cap_zero_or_negative_disables_the_feature(self):
        history.add_entry("Skyrim", "vecchia?", "vecchia.")
        for cap in (0, -3):
            with mock.patch.object(config, "MAX_SAVED_HISTORY_ENTRIES", cap):
                self.rick.ask("nuova", "Skyrim")
                self.assertNotIn("Cronologia salvata", self.sent_question())

    def test_answers_already_in_the_conversation_are_not_sent_twice(self):
        history.add_entry("Zelda", "domanda di ieri?", "risposta di ieri.")
        self.rick.ask("domanda di oggi?", "Zelda")
        # main.py saves each answered turn to the binder right after ask()
        history.add_entry("Zelda", "domanda di oggi?", "Risposta.")
        self.rick.ask("seguito?", "Zelda")
        sent = self.sent_question()
        self.assertIn("domanda di ieri?", sent)       # older session: still useful
        self.assertNotIn("domanda di oggi?", sent)   # already a real turn in the conversation
        self.assertEqual(self.roles(self.last_request()), ["user", "model", "user"])

    # -- conversation scoping --------------------------------------------
    def test_switching_game_starts_a_fresh_conversation(self):
        self.rick.ask("domanda su A", "Gioco A")
        self.rick.ask("domanda su B", "Gioco B")
        self.assertEqual(len(self.last_request()), 1)

    def test_same_game_keeps_the_conversation(self):
        self.rick.ask("prima", "Gioco A")
        self.rick.ask("seconda", "Gioco A")
        self.assertEqual(self.roles(self.last_request()), ["user", "model", "user"])

    def test_reset_conversation_takes_effect_on_the_next_question(self):
        self.rick.ask("prima", history.NO_GAME_KEY_IT)
        self.rick.reset_conversation()
        self.rick.ask("dopo nuova chat", history.NO_GAME_KEY_IT)
        self.assertEqual(len(self.last_request()), 1)

    def test_long_conversations_are_trimmed_to_whole_exchanges(self):
        with mock.patch.object(config, "MAX_HISTORY_TURNS", 12):
            for i in range(10):
                self.rick.ask(f"domanda {i}", "Gioco A")
                request = self.last_request()
                self.assertEqual(request[0].role, "user", f"turn {i}")
                self.assertLessEqual(len(request), 12)
                expected = ["user", "model"] * (len(request) // 2) + ["user"]
                self.assertEqual(self.roles(request), expected)

    # -- web search --------------------------------------------------------
    def test_web_search_query_names_the_game(self):
        with mock.patch.object(config, "ENABLE_WEB_SEARCH", True):
            self.rick.ask("dov'e' la chiave d'argento?", "Resident Evil")
            self.search_web.assert_called_with("Resident Evil dov'e' la chiave d'argento?")
            self.rick.ask("dov'e' la chiave d'argento?", history.NO_GAME_KEY_IT)
            self.search_web.assert_called_with("dov'e' la chiave d'argento?")

    def test_web_results_are_appended_to_the_question(self):
        self.search_web.return_value = "- Wiki: la chiave e' nel municipio"
        with mock.patch.object(config, "ENABLE_WEB_SEARCH", True):
            self.rick.ask("chiave?", "Resident Evil")
        self.assertIn("Risultati di ricerca web", self.sent_question())
        self.assertIn("municipio", self.sent_question())

    # -- failures ------------------------------------------------------------
    def test_failed_question_is_dropped_from_the_conversation(self):
        self.rick.ask("prima", "Gioco A")
        self.models.script = [_client_error()]
        with self.assertRaises(genai_errors.ClientError):
            self.rick.ask("fallita", "Gioco A")
        self.rick.ask("terza", "Gioco A")
        request = self.last_request()
        self.assertEqual(self.roles(request), ["user", "model", "user"])
        self.assertNotIn("fallita", [c.parts[0].text for c in request])

    def test_empty_answer_raises_and_is_not_kept(self):
        self.models.script = [None]
        with self.assertRaises(brain.EmptyAnswerError):
            self.rick.ask("bloccata?", "Gioco A")
        self.rick.ask("di nuovo", "Gioco A")
        self.assertEqual(self.roles(self.last_request()), ["user"])

    def test_overload_is_retried_then_succeeds(self):
        self.models.script = [_server_error(), _server_error(), "Finalmente."]
        self.assertEqual(self.rick.ask("domanda", "Gioco A"), "Finalmente.")
        self.assertEqual(len(self.models.requests), 3)

    def test_persistent_overload_gives_up(self):
        self.models.script = [_server_error()] * 5
        with self.assertRaises(genai_errors.ServerError):
            self.rick.ask("domanda", "Gioco A")
        self.assertEqual(len(self.models.requests), brain._MAX_RETRIES + 1)

    def test_conversation_memory_never_stores_the_augmented_text(self):
        history.add_entry("Zelda", "vecchia?", "vecchia.")
        self.rick.ask("nuova", "Zelda")
        self.assertEqual(self.rick._history[0].parts[0].text, "nuova")


if __name__ == "__main__":
    unittest.main()
