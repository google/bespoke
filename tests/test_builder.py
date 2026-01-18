import unittest
from unittest.mock import AsyncMock, patch

from bespoke import Difficulty
from bespoke import Language
from bespoke import builder
from bespoke import languages


class TestUnitTagsBuilder(unittest.TestCase):
    def test_long_then_short(self) -> None:
        full_vocubulary = languages.JAPANESE.full_vocabulary()
        sentence = "大学生です。"
        long = "大学生"
        short = "学生"
        unit_tags_builder = builder.UnitTagsBuilder(sentence, [])
        unit_tags_builder.add_filtered([(long, long)], full_vocubulary)
        unit_tags = dict(unit_tags_builder.unit_tags)
        self.assertIn(long, unit_tags)
        for _ in range(builder.UnitTagsBuilder.DONE_AFTER):
            self.assertFalse(unit_tags_builder.done())
            unit_tags_builder.add_filtered([(short, short)], full_vocubulary)
            self.assertEqual(unit_tags, unit_tags_builder.unit_tags)
        self.assertTrue(unit_tags_builder.done())


class TestUnitProducer(unittest.TestCase):
    def test_basic_draw(self) -> None:
        unit_producer = builder.UnitProducer(languages.JAPANESE, 1)
        self.assertFalse(unit_producer.done())
        count = 4
        units, difficulty = unit_producer.draw(count)
        self.assertEqual(len(units), count)
        self.assertEqual(difficulty, Difficulty.A1)
        self.assertFalse(unit_producer.done())

    def test_draw_ignores_initial(self) -> None:
        unit_producer = builder.UnitProducer(languages.JAPANESE, 1)
        vocabulary = languages.JAPANESE.vocabulary(Difficulty.A1)
        count = 4
        for unit in vocabulary[:-count]:
            unit_producer.register(unit, True)
        units, difficulty = unit_producer.draw(count)
        self.assertEqual(set(units), set(vocabulary[-count:]))
        self.assertEqual(difficulty, Difficulty.A1)

    def test_register_all_done(self) -> None:
        unit_producer = builder.UnitProducer(languages.JAPANESE, 1)
        for difficulty in Difficulty:
            vocabulary = languages.JAPANESE.vocabulary(difficulty)
            for unit in vocabulary:
                unit_producer.register(unit, True)
        self.assertTrue(unit_producer.done())


async def mock_create_sentences(
    language: Language,
    difficulty: Difficulty,
    grammar: str,
    units: list[str],
) -> list[str]:
    return units


class TestSentenceProducer(unittest.IsolatedAsyncioTestCase):
    @patch("bespoke.builder.llm.create_sentences", side_effect=mock_create_sentences)
    async def test_basic_create(self, mock_llm):
        cards_per_call = 8
        sentence_producer = builder.SentenceProducer(languages.JAPANESE, cards_per_unit=1, cards_per_call=cards_per_call)
        self.assertFalse(sentence_producer.done())
        builders, grammar = await sentence_producer.create()
        self.assertEqual(len(builders), cards_per_call)
        self.assertTrue(grammar)
        self.assertFalse(sentence_producer.done())

    @patch("bespoke.builder.llm.create_sentences", side_effect=mock_create_sentences)
    async def test_double_create(self, mock_llm):
        cards_per_call = 1
        sentence_producer = builder.SentenceProducer(languages.JAPANESE, cards_per_unit=1, cards_per_call=cards_per_call)
        builders, grammar1 = await sentence_producer.create()
        builder1 = builders[0]
        builders, grammar2 = await sentence_producer.create()
        builder2 = builders[0]
        self.assertNotEqual(builder1.sentence, builder2.sentence)
        self.assertNotEqual(grammar1, grammar2)


if __name__ == "__main__":
    unittest.main()
