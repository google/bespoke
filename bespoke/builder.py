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

from bespoke.card import Card
from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke import llm
from bespoke.unit import Unit
from bespoke.unit import UnitIndex
from bespoke import tagger


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

    def draw(self, count: int) -> tuple[list[Unit], Difficulty]:
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
        assert chosen_difficulty is not None
        return units, chosen_difficulty

    def register(self, unit: Unit, is_fitting: bool) -> None:
        self._card_count[unit.id()] += 1
        if is_fitting:
            self._fitting_count[unit.id()] += 1

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
                if self._fitting_count[unit.id()] < self._cards_per_unit:
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
        unit_index: UnitIndex,
        *,
        cards_per_unit: int,
        cards_per_call: int,
    ) -> None:
        self._language = language
        self._llm_client = llm_client
        self._grammar = grammar
        self._unit_index = unit_index
        self._cards_per_call = cards_per_call
        self._unit_producer = UnitProducer(language, cards_per_unit)
        self._grammar_pools: dict[Difficulty, list[str]] = {}
        # Data structures to quickly operate on difficulties.
        self._difficulty_order = {d: i for i, d in enumerate(Difficulty)}

    async def create(self) -> tuple[list[tagger.Tagger], str]:
        units, difficulty = self._unit_producer.draw(self._cards_per_call)
        grammar = self._sample_grammar(difficulty)
        sentences = await self._llm_client.create_sentences(
            language=self._language,
            difficulty=difficulty,
            grammar=grammar,
            units=units,
        )
        return [
            tagger.create_tagger(
                s,
                [unit.id() for unit in units],
                self._unit_index,
                self._language,
            )
            for s in sentences
        ], grammar

    def register_card(self, card: Card) -> None:
        difficulties = {}
        for unit_id in card.units:
            unit = self._unit_index.get_by_id(unit_id)
            if unit:
                difficulties[unit_id] = unit.difficulty()
        if not difficulties:
            return
        max_difficulty = max(
            difficulties.values(), key=lambda d: self._difficulty_order[d]
        )
        for unit_id, difficulty in difficulties.items():
            is_fitting = difficulty == max_difficulty
            unit = self._unit_index.get_by_id(unit_id)
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
        self._unit_index = UnitIndex()
        for unit in self._language.units():
            self._unit_index.add(unit)
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
        sentence_producer = SentenceProducer(
            self._language,
            self._llm_client,
            self._grammar,
            self._unit_index,
            cards_per_unit=cards_per_unit,
            cards_per_call=cards_per_call,
        )
        for card in await self._card_index.all_cards():
            self._duplicates.add(card.sentence)
            sentence_producer.register_card(card)
        self._start_time = datetime.now()
        print(f"Initialized with {len(self._duplicates)} existing cards")

        semaphore = asyncio.Semaphore(self.MAX_PARALLELISM)
        async with asyncio.TaskGroup() as tg:
            # Don't waste resources on units that don't get created.
            for _ in range(cards_per_unit * 2):
                if sentence_producer.done():
                    break
                builders, grammar = await sentence_producer.create()
                for builder in builders:
                    if builder.sentence() in self._duplicates:
                        print(f"Skipping duplicate sentence {builder.sentence()}")
                        continue
                    self._duplicates.add(builder.sentence())
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
        tagger_instance: tagger.Tagger,
        grammar: str,
    ) -> None:
        try:
            while not tagger_instance.done():
                await tagger_instance.progress(self._llm_client)

            unit_tags = tagger_instance.tags()

            if not unit_tags:
                print(f"Discarding untagged sentence: '{tagger_instance.sentence()}'")
                return

            card_unit_tags = {word: u.id() for word, u in unit_tags.items()}

            card = await self._card_index.create_card(
                self._llm_client,
                tagger_instance.sentence(),
                card_unit_tags,
                notes=[grammar],
            )
            sentence_producer.register_card(card)
            self._created_count += 1
            if self._created_count % 1000 == 0 or self._created_count == 100:
                assert self._start_time is not None
                elapsed = datetime.now() - self._start_time
                time_string = str(elapsed).split(".")[0]
                print(f"{self._created_count:>5} cards after : {time_string}")
        except Exception as e:
            print(f"Error processing sentence '{tagger_instance.sentence()}': {e}")
        finally:
            semaphore.release()
