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

"""Tool to create cards for all words in a language."""

import asyncio
from collections import defaultdict
from datetime import datetime
import random
from typing import Iterator

from bespoke.card import Card
from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import UnitTags
from bespoke import llm


class UnitTagsBuilder:
    """Helper class to iteratively build the UnitTags."""

    DONE_AFTER = 1

    def __init__(self, sentence: str, hint: list[str]) -> None:
        self.sentence = sentence
        self.unit_tags = {}
        self.hint = list(hint)
        self._no_progress_counter = 0

    def add_filtered(
        self,
        new_tag_list: list[str, str],
        vocabulary: list[str],
    ) -> None:
        old_tags = self.unit_tags
        all_tags = new_tag_list + list(self.unit_tags.items())
        all_tags.sort(key=lambda x: len(x[1]), reverse=True)
        all_tags.sort(key=lambda x: len(x[0]), reverse=True)
        sentence = self.sentence
        used_units = set()
        filtered = {}
        for word, unit in all_tags:
            if word not in sentence:
                continue
            if unit not in vocabulary:
                continue
            if unit in used_units:
                continue
            sentence = sentence.replace(word, "", 1)
            filtered[word] = unit
            used_units.add(unit)
        self.unit_tags = filtered
        # Any function that can not increase indefinitely can work here.
        if len(old_tags) >= len(self.unit_tags):
            self._no_progress_counter += 1

    def done(self) -> bool:
        return self._no_progress_counter >= self.DONE_AFTER


class UnitProducer:
    """Helper class that tracks progress for cards per units."""

    # TODO check if the heuristic works
    # otherwise only count fitting cards
    DRAW_BUFFER = 4

    def __init__(
        self,
        language: Language,
        cards_per_unit: int,
    ) -> None:
        self._cards_per_unit = cards_per_unit
        self._card_count = defaultdict(int)
        self._fitting_count = defaultdict(int)
        self._units_remaining = {d: language.vocabulary(d) for d in Difficulty}
        # Lazy initialization to allow register to affect the first draw / done.
        self._unit_pools = {}
        self._done = False

    def draw(self, count: int) -> tuple[list[str], Difficulty]:
        """Returns random units that need more cards.

        You may not call draw when done.
        """
        if not self._unit_pools:
            self._refill()
        units = []
        chosen_difficulty = None
        for difficulty in Difficulty:
            unit_pool = self._unit_pools[difficulty]
            if unit_pool:
                units = unit_pool[:count]
                chosen_difficulty = difficulty
                self._unit_pools[difficulty] = unit_pool[count:]
                break
        if all(not pool for pool in self._unit_pools.values()):
            self._refill()
        return units, chosen_difficulty

    def register(self, unit: str, is_fitting: bool) -> None:
        self._card_count[unit] += 1
        if is_fitting:
            self._fitting_count[unit] += 1

    def done(self) -> bool:
        if not self._unit_pools:
            self._refill()
        return self._done

    def _refill(self) -> None:
        size = 0
        total = 0
        for difficulty in Difficulty:
            remaining = []
            for unit in self._units_remaining[difficulty]:
                if self._fitting_count[unit] < self._cards_per_unit:
                    remaining.append(unit)
                    size += 1
                    total += self._card_count[unit]
            self._units_remaining[difficulty] = remaining
        self._done = not size
        if self._done:
            return

        count_average = total / size
        for difficulty in Difficulty:
            unit_pool = []
            for unit in self._units_remaining[difficulty]:
                if self._card_count[unit] < count_average + self.DRAW_BUFFER:
                    unit_pool.append(unit)
            self._unit_pools[difficulty] = unit_pool


class SentenceProducer:
    """Helper class that produces sentences for the card pipeline."""

    def __init__(
        self,
        language: Language,
        *,
        cards_per_unit: int,
        cards_per_call: int,
    ) -> None:
        self._language = language
        self._cards_per_call = cards_per_call
        self._unit_producer = UnitProducer(language, cards_per_unit)
        self._grammar_pools = {}
        # Data structures to quickly operate on difficulties.
        self._difficulty_order = {d: i for i, d in enumerate(Difficulty)}
        self._difficulty_map = {}
        for difficulty in Difficulty:
            for word in self._language.vocabulary(difficulty):
                self._difficulty_map[word] = difficulty

    async def create(self) -> tuple[list[UnitTagsBuilder], str]:
        units, difficulty = self._unit_producer.draw(self._cards_per_call)
        grammar = self._sample_grammar(difficulty)
        sentences = await llm.create_sentences(
            language=self._language,
            difficulty=difficulty,
            grammar=grammar,
            units=units,
        )
        return [UnitTagsBuilder(s, units) for s in sentences], grammar

    def register_card(self, card: Card) -> None:
        difficulties = {u: self._difficulty_map[u] for u in card.units}
        max_difficulty = max(
            difficulties.values(), key=lambda d: self._difficulty_order[d]
        )
        for unit, difficulty in difficulties.items():
            is_fitting = difficulty == max_difficulty
            self._unit_producer.register(unit, is_fitting)

    def done(self) -> bool:
        return self._unit_producer.done()

    def _sample_grammar(self, difficulty: Difficulty) -> str:
        grammar_pool = self._grammar_pools.get(difficulty, [])
        if not grammar_pool:
            for d in Difficulty:
                grammar_pool += self._language.grammar(d)
                if d == difficulty:
                    break
            random.shuffle(grammar_pool)
        grammar = grammar_pool.pop()
        self._grammar_pools[difficulty] = grammar_pool
        return grammar


class DeckBuilder:
    MAX_PARALLELISM = 64

    def __init__(
        self,
        target_language: Language,
        native_language: Language,
    ) -> None:
        self._language = target_language
        self._card_index = CardIndex.load(target_language, native_language)
        self._full_vocabulary = self._language.full_vocabulary()
        self._duplicates = set()
        self._start_time = None
        self._created_count = 0

    async def create_cards(
        self,
        *,
        cards_per_unit: int,
        cards_per_call: int,
    ) -> None:
        self._duplicates = set()
        sentence_producer = SentenceProducer(self._language, cards_per_unit=cards_per_unit, cards_per_call=cards_per_call)
        for card in await self._card_index.all_cards():
            self._duplicates.add(card.sentence)
            sentence_producer.register_card(card)
        self._start_time = datetime.now()
        print(f"Initialized with {len(self._duplicates)} existing cards")

        semaphore = asyncio.Semaphore(self.MAX_PARALLELISM)
        async with asyncio.TaskGroup() as tg:
            while not sentence_producer.done():
                builders, grammar = await sentence_producer.create()
                for builder in builders:
                    if builder.sentence in self._duplicates:
                        print(f"Skipping duplicate sentence {builder.sentence}")
                        continue
                    self._duplicates.add(builder.sentence)
                    await semaphore.acquire()
                    tg.create_task(
                        self._complete_card(
                            semaphore, sentence_producer, builder, grammar
                        )
                    )
                self._card_index.save()

    async def _complete_card(
        self,
        semaphore: asyncio.Semaphore,
        sentence_producer: SentenceProducer,
        builder: UnitTagsBuilder,
        grammar: str,
    ) -> Card:
        try:
            for unit in self._full_vocabulary:
                if unit in builder.sentence and unit not in builder.hint:
                    builder.hint.append(unit)
            while not builder.done():
                new_tag_list = await llm.tag_sentence(
                    sentence=builder.sentence,
                    language=self._language,
                    hint=builder.hint,
                )
                builder.add_filtered(new_tag_list, self._full_vocabulary)
            card = await self._card_index.create_card(
                builder.sentence, builder.unit_tags, notes=[grammar]
            )
            sentence_producer.register_card(card)
            self._created_count += 1
            if self._created_count % 1000 == 0 or self._created_count == 100:
                elapsed = datetime.now() - self._start_time
                time_string = str(elapsed).split('.')[0]
                print(f"{self._created_count:>5} cards after : {time_string}")
        except Exception as e:
            print(f"Error processing sentence '{builder.sentence}': {e}")
        finally:
            semaphore.release()
