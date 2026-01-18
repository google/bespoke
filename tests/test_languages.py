import unittest
from unittest.mock import AsyncMock, patch

from bespoke import Difficulty
from bespoke import languages


class TestLanguageData(unittest.TestCase):
    def test_vocabulary(self) -> None:
        language = languages.JAPANESE
        for d1 in Difficulty:
            for d2 in Difficulty:
                if d1 == d2:
                    continue
                vocabulary1 = language.vocabulary(d1)
                vocabulary2 = language.vocabulary(d2)
                self.assertTrue(set(vocabulary1).isdisjoint(vocabulary2))
                self.assertTrue(set(vocabulary1).isdisjoint(vocabulary2))

    def test_full_vocabulary(self) -> None:
        language = languages.JAPANESE
        vocabulary_a1 = language.vocabulary(Difficulty.A1)
        full_vocabulary = language.full_vocabulary()
        self.assertEqual(vocabulary_a1, full_vocabulary[: len(vocabulary_a1)])

    def test_grammar(self) -> None:
        language = languages.JAPANESE
        for d1 in Difficulty:
            for d2 in Difficulty:
                if d1 == d2:
                    continue
                grammar1 = language.grammar(d1)
                grammar2 = language.grammar(d2)
                self.assertTrue(set(grammar1).isdisjoint(grammar2))


if __name__ == "__main__":
    unittest.main()
