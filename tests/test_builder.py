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


class TestUnitProducer(unittest.TestCase):
    def test_basic_draw(self) -> None:
        language = languages.LANGUAGES["japanese"]
        unit_producer = builder.UnitProducer(language, 1, 0)
        self.assertFalse(unit_producer.done())
        count = 4
        units, difficulty = unit_producer.draw(count)
        self.assertEqual(len(units), count)
        self.assertEqual(difficulty, Difficulty.A1)
        self.assertFalse(unit_producer.done())

    def test_draw_ignores_initial(self) -> None:
        language = languages.LANGUAGES["japanese"]
        unit_producer = builder.UnitProducer(language, 1, 0)
        vocabulary = [u for u in language.units() if u.difficulty() == Difficulty.A1]
        count = 4
        for u in vocabulary[:-count]:
            unit_producer.register(u, True)
        units, difficulty = unit_producer.draw(count)
        self.assertEqual(
            set(u.id() for u in units), set(u.id() for u in vocabulary[-count:])
        )
        self.assertEqual(difficulty, Difficulty.A1)

    def test_register_all_done(self) -> None:
        language = languages.LANGUAGES["japanese"]
        unit_producer = builder.UnitProducer(language, 1, 0)
        for difficulty in Difficulty:
            vocabulary = [u for u in language.units() if u.difficulty() == difficulty]
            for u in vocabulary:
                unit_producer.register(u, True)
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
            num_existing_cards=0,
        )
        self.assertFalse(sentence_producer.done())
        sentences, units, grammar = await sentence_producer.create()
        self.assertEqual(len(sentences), cards_per_call)
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
            num_existing_cards=0,
        )
        sentences1, units1, grammar1 = await sentence_producer.create()
        sentences2, units2, grammar2 = await sentence_producer.create()
        self.assertNotEqual(sentences1[0], sentences2[0])
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
        vocabulary_size = len(language.units())
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
