"""Cutting Rick's answer into sentences while Gemini writes it
(rick/sentences.py), so each one is said as soon as it's complete."""

import unittest

from rick import sentences
from rick.sentences import MAX_CHARS, MIN_CHARS


def cut(*pieces):
    return list(sentences.sentences(pieces))


class SentencesTest(unittest.TestCase):
    def test_each_sentence_comes_out_as_soon_as_it_is_complete(self):
        read = []

        def pieces():
            for piece in ("Lo trovi nella palude ", "a nord del castello. Atten", "to al drago di guardia."):
                read.append(piece)
                yield piece

        out = sentences.sentences(pieces())
        self.assertEqual(next(out), "Lo trovi nella palude a nord del castello.")
        self.assertEqual(len(read), 2)  # without waiting for the rest
        self.assertEqual(list(out), ["Attento al drago di guardia."])

    def test_question_and_exclamation_marks_ellipses_quotes_and_new_lines(self):
        self.assertEqual(
            cut("Hai gia' parlato con il fabbro del villaggio? Ottimo, allora vai alla miniera! "
                "Poi cerca la chiave nella cassa... Il fabbro dice \"torna stanotte.\" "
                "Una riga che finisce senza punto\nE poi un'altra riga"),
            [
                "Hai gia' parlato con il fabbro del villaggio?",
                "Ottimo, allora vai alla miniera!",
                "Poi cerca la chiave nella cassa...",
                "Il fabbro dice \"torna stanotte.\"",
                "Una riga che finisce senza punto",
                "E poi un'altra riga",
            ],
        )

    def test_short_sentences_go_out_with_the_next_one(self):
        self.assertEqual(
            cut("Si'. Ok. Lo trovi nella palude a nord del castello. Fine."),
            ["Si'. Ok. Lo trovi nella palude a nord del castello.", "Fine."],
        )
        self.assertLess(len("Si'. Ok."), MIN_CHARS)

    def test_numbers_and_versions_are_not_sentence_ends(self):
        self.assertEqual(
            cut("Con la patch 1.0.2 serve il livello 3.5 ", "per entrare nella torre, poi sali."),
            ["Con la patch 1.0.2 serve il livello 3.5 per entrare nella torre, poi sali."],
        )

    def test_a_sentence_without_an_end_is_cut_at_a_comma_then_a_space(self):
        long_one = "parola, " * 40
        first, *rest = cut(long_one)
        self.assertLessEqual(len(first), MAX_CHARS)
        self.assertTrue(first.endswith(","))
        no_commas = "parola " * 60
        first, *rest = cut(no_commas)
        self.assertLessEqual(len(first), MAX_CHARS)
        self.assertEqual(" ".join([first, *rest]), no_commas.strip())
        self.assertEqual(cut("x" * (MAX_CHARS + 10)), ["x" * MAX_CHARS, "x" * 10])

    def test_nothing_in_nothing_out(self):
        self.assertEqual(cut(), [])
        self.assertEqual(cut("", "  ", "\n"), [])
        self.assertEqual(cut("Fine"), ["Fine"])


if __name__ == "__main__":
    unittest.main()
