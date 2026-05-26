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

from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke import llm
from bespoke.unit import Unit
from bespoke import tagger


class UnitProducer:
    """Helper class that tracks progress for cards per units."""

    # Used to not draw cards when they were registered often enough.
    DRAW_BUFFER = 4

    def __init__(
        self,
        language: Language,
        cards_per_unit: int,
        num_existing_cards: int,
    ) -> None:
        self._cards_per_unit = cards_per_unit
        self._card_count: dict[str, int] = defaultdict(int)
        self._fitting_count: dict[str, int] = defaultdict(int)
        self._units_remaining: dict[Difficulty, list[Unit]] = {
            d: [] for d in Difficulty
        }
        for unit in language.units():
            self._units_remaining[unit.difficulty()].append(unit)
        # Lazy initialization to allow register to affect the first draw / done.
        self._unit_pools: dict[Difficulty, list[Unit]] = {}
        self._done = False

        num_units = len(language.units())
        initial_draw_count = num_existing_cards // num_units if num_units > 0 else 0
        self._draw_count: dict[str, int] = defaultdict(lambda: initial_draw_count)

    def draw(self, count: int) -> tuple[list[Unit], Difficulty]:
        """Returns random units that need more cards.

        You may not call draw when done.
        """
        self._refill_if_empty()
        units = []
        chosen_difficulty = None
        for difficulty in Difficulty:
            unit_pool = self._unit_pools[difficulty]
            if unit_pool:
                units = unit_pool[:count]
                for u in units:
                    self._draw_count[u.id()] += 1
                chosen_difficulty = difficulty
                self._unit_pools[difficulty] = unit_pool[count:]
                break
        assert chosen_difficulty is not None
        return units, chosen_difficulty

    def register(self, unit: Unit, is_fitting: bool) -> None:
        self._card_count[unit.id()] += 1
        if is_fitting:
            self._fitting_count[unit.id()] += 1

    def done(self) -> bool:
        self._refill_if_empty()
        return self._done

    def _refill_if_empty(self) -> None:
        if self._unit_pools and any(pool for pool in self._unit_pools.values()):
            return
        size = 0
        total = 0
        for difficulty in Difficulty:
            remaining = []
            for unit in self._units_remaining[difficulty]:
                if (
                    self._fitting_count[unit.id()] < self._cards_per_unit
                    and self._draw_count[unit.id()] < self._cards_per_unit * 2
                ):
                    remaining.append(unit)
                    size += 1
                    total += self._card_count[unit.id()]
            self._units_remaining[difficulty] = remaining
        self._done = not size
        if self._done:
            return

        count_average = total / size
        for difficulty in Difficulty:
            unit_pool = []
            for unit in self._units_remaining[difficulty]:
                if self._card_count[unit.id()] < count_average + self.DRAW_BUFFER:
                    unit_pool.append(unit)
            self._unit_pools[difficulty] = unit_pool


class SentenceProducer:
    """Helper class that produces sentences for the card pipeline."""

    def __init__(
        self,
        language: Language,
        llm_client: llm.LlmClient,
        grammar: dict[Difficulty, list[str]],
        *,
        cards_per_unit: int,
        cards_per_call: int,
        num_existing_cards: int,
    ) -> None:
        self._language = language
        self._llm_client = llm_client
        self._grammar = grammar
        self._cards_per_call = cards_per_call
        self._unit_producer = UnitProducer(language, cards_per_unit, num_existing_cards)
        self._grammar_pools: dict[Difficulty, list[str]] = {}
        # Data structures to quickly operate on difficulties.
        self._difficulty_order = {d: i for i, d in enumerate(Difficulty)}

    async def create(self) -> tuple[list[str], list[Unit], str]:
        units, difficulty = self._unit_producer.draw(self._cards_per_call)
        grammar = self._sample_grammar(difficulty)
        sentences = await self._llm_client.create_sentences(
            language=self._language,
            difficulty=difficulty,
            grammar=grammar,
            units=units,
        )
        return sentences, units, grammar

    def register_card(self, unit_ids: list[str]) -> None:
        difficulties = {}
        for unit_id in unit_ids:
            unit = self._language.get_by_id(unit_id)
            if unit:
                difficulties[unit_id] = unit.difficulty()
        if not difficulties:
            return
        max_difficulty = max(
            difficulties.values(), key=lambda d: self._difficulty_order[d]
        )
        for unit_id, difficulty in difficulties.items():
            is_fitting = difficulty == max_difficulty
            unit = self._language.get_by_id(unit_id)
            if unit:
                self._unit_producer.register(unit, is_fitting)

    def done(self) -> bool:
        return self._unit_producer.done()

    def _sample_grammar(self, difficulty: Difficulty) -> str:
        grammar_pool = self._grammar_pools.get(difficulty, [])
        if not grammar_pool:
            for d in Difficulty:
                grammar_pool += list(self._grammar.get(d, []))
                if d == difficulty:
                    break
            random.shuffle(grammar_pool)
        grammar = grammar_pool.pop()
        self._grammar_pools[difficulty] = grammar_pool
        return grammar


class DeckBuilder:
    MAX_PARALLELISM = 16

    def __init__(
        self,
        target_language: Language,
        card_index: CardIndex,
        llm_client: llm.LlmClient,
        grammar: dict[Difficulty, list[str]],
    ) -> None:
        self._language = target_language
        self._card_index = card_index
        self._llm_client = llm_client
        self._grammar = grammar
        self._duplicates: set[str] = set()
        self._start_time: datetime | None = None
        self._created_count = 0

    async def create_cards(
        self,
        *,
        cards_per_unit: int,
        cards_per_call: int,
    ) -> None:
        self._duplicates = set()
        all_cards = await self._card_index.all_cards()
        sentence_producer = SentenceProducer(
            self._language,
            self._llm_client,
            self._grammar,
            cards_per_unit=cards_per_unit,
            cards_per_call=cards_per_call,
            num_existing_cards=len(all_cards),
        )
        for card in all_cards:
            self._duplicates.add(card.sentence)
            sentence_producer.register_card(card.unit_ids())
        self._start_time = datetime.now()
        print(f"Initialized with {len(self._duplicates)} existing cards")

        semaphore = asyncio.Semaphore(self.MAX_PARALLELISM)
        async with asyncio.TaskGroup() as tg:
            # Don't waste resources on units that don't get created.
            while not sentence_producer.done():
                sentences, units, grammar = await sentence_producer.create()
                for sentence in sentences:
                    if sentence in self._duplicates:
                        print(f"Skipping duplicate sentence {sentence}")
                        continue
                    self._duplicates.add(sentence)
                    await semaphore.acquire()
                    tg.create_task(
                        self._complete_card(
                            semaphore, sentence_producer, sentence, units, grammar
                        )
                    )
                self._card_index.save()

    async def _complete_card(
        self,
        semaphore: asyncio.Semaphore,
        sentence_producer: SentenceProducer,
        sentence: str,
        units: list[Unit],
        grammar: str,
    ) -> None:
        try:
            unit_tags = await tagger.create_tags(
                sentence=sentence,
                hint=units,
                language=self._language,
                llm_client=self._llm_client,
            )
            if not unit_tags:
                print(f"Discarding untagged sentence: '{sentence}'")
                return

            card = await self._card_index.create_card(
                self._llm_client,
                sentence,
                unit_tags,
                notes=[grammar],
            )
            sentence_producer.register_card(card.unit_ids())
            self._created_count += 1
            if self._created_count % 1000 == 0 or self._created_count == 100:
                assert self._start_time is not None
                elapsed = datetime.now() - self._start_time
                time_string = str(elapsed).split(".")[0]
                print(f"{self._created_count:>5} cards after : {time_string}")
        except Exception as e:
            print(f"Error processing sentence '{sentence}': {e}")
        finally:
            semaphore.release()
