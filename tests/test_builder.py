# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

from bespoke import Difficulty
from bespoke import builder
from bespoke import languages
from tests import fakes
from bespoke.unit import WordUnit


class TestUnitTagsBuilder(unittest.TestCase):
    def test_long_then_short(self) -> None:
        language = languages.LANGUAGES["japanese"]
        full_vocubulary = language.full_vocabulary()
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
        language = languages.LANGUAGES["japanese"]
        unit_producer = builder.UnitProducer(language, 1)
        self.assertFalse(unit_producer.done())
        count = 4
        units, difficulty = unit_producer.draw(count)
        self.assertEqual(len(units), count)
        self.assertEqual(difficulty, Difficulty.A1)
        self.assertFalse(unit_producer.done())

    def test_draw_ignores_initial(self) -> None:
        language = languages.LANGUAGES["japanese"]
        unit_producer = builder.UnitProducer(language, 1)
        vocabulary = language.vocabulary(Difficulty.A1)
        count = 4
        for unit in vocabulary[:-count]:
            unit_producer.register(WordUnit(unit), True)
        units, difficulty = unit_producer.draw(count)
        self.assertEqual(set(u.id() for u in units), set(vocabulary[-count:]))
        self.assertEqual(difficulty, Difficulty.A1)

    def test_register_all_done(self) -> None:
        language = languages.LANGUAGES["japanese"]
        unit_producer = builder.UnitProducer(language, 1)
        for difficulty in Difficulty:
            vocabulary = language.vocabulary(difficulty)
            for unit in vocabulary:
                unit_producer.register(WordUnit(unit), True)
        self.assertTrue(unit_producer.done())


class TestSentenceProducer(unittest.IsolatedAsyncioTestCase):
    async def test_basic_create(self):
        cards_per_call = 8
        language = fakes.fake_language()
        llm_client = fakes.FakeLlmClient()
        sentence_producer = builder.SentenceProducer(
            language,
            llm_client,
            fakes.FAKE_GRAMMAR,
            cards_per_unit=1,
            cards_per_call=cards_per_call,
        )
        self.assertFalse(sentence_producer.done())
        builders, grammar = await sentence_producer.create()
        self.assertEqual(len(builders), cards_per_call)
        self.assertTrue(grammar)
        self.assertFalse(sentence_producer.done())

    async def test_double_create(self):
        cards_per_call = 1
        language = fakes.fake_language()
        llm_client = fakes.FakeLlmClient()
        sentence_producer = builder.SentenceProducer(
            language,
            llm_client,
            fakes.FAKE_GRAMMAR,
            cards_per_unit=1,
            cards_per_call=cards_per_call,
        )
        builders, grammar1 = await sentence_producer.create()
        builder1 = builders[0]
        builders, grammar2 = await sentence_producer.create()
        builder2 = builders[0]
        self.assertNotEqual(builder1.sentence, builder2.sentence)
        self.assertNotEqual(grammar1, grammar2)


class TestDeckBuilder(unittest.IsolatedAsyncioTestCase):
    async def test_creation(self) -> None:
        language = fakes.fake_language()
        card_index = fakes.FakeCardIndex(language)
        llm_client = fakes.FakeLlmClient()
        deck_builder = builder.DeckBuilder(
            language,
            card_index,  # type: ignore
            llm_client,
            fakes.FAKE_GRAMMAR,
        )
        vocabulary_size = len(language.full_vocabulary())
        index_size = len(await card_index.all_cards())
        self.assertEqual(index_size, vocabulary_size)

        await deck_builder.create_cards(
            cards_per_unit=1,
            cards_per_call=8,
        )
        index_size = len(await card_index.all_cards())
        self.assertEqual(index_size, vocabulary_size)

        await deck_builder.create_cards(
            cards_per_unit=2,
            cards_per_call=8,
        )
        index_size = len(await card_index.all_cards())
        self.assertGreaterEqual(index_size, vocabulary_size * 2)


if __name__ == "__main__":
    unittest.main()
