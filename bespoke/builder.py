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
import random
from typing import Iterator

from bespoke.card import Card
from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import UnitTags
from bespoke.languages import GRAMMAR
from bespoke.languages import VOCABULARY
from bespoke import llm


class UnitTagsBuilder:
  """Helper class to iteratively build the UnitTags."""
  DONE_AFTER = 2

  def __init__(self, sentence: str) -> None:
    self.sentence = sentence
    self.unit_tags = {}
    self._no_progress_counter = 0

  def add_filtered(
    self,
    new_tag_list: list[str, str],
    vocabulary: list[str],
  ) -> None:
    old_tags = self.unit_tags
    all_tags = new_tag_list + list(self.unit_tags.items())
    all_tags.sort(reverse=True)
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
    if len(old_tags) >= len(self.unit_tags):
      self._no_progress_counter += 1

  def done(self) -> bool:
    return self._no_progress_counter >= self.DONE_AFTER


class UnitPool:
  """Helper class that tracks progress for cards per units."""
  def __init__(
    self,
    target_language: Language,
    card_index: CardIndex,
    difficulty: Difficulty
  ) -> None:
    self._card_index = card_index
    self._difficulty = difficulty
    self._vocabulary = VOCABULARY[target_language.code_name]
    self._grammar = GRAMMAR[target_language.code_name]
    self._card_count = {v: 0 for v in self._vocabulary}
    self._fitting_card_count = {v: 0 for v in self._vocabulary}
    self._difficulty_order = {d: i for i, d in enumerate(Difficulty)}
    self._count_limit = 0
    self._fitting_limit = 0

  def __iter__(self) -> Iterator[tuple[list[str], str]]:
    pass

  def register_card_units(self, difficulties: dict[str, Difficulty]) -> None:
    max_difficulty = max(difficulties.values(), key=lambda d: self._difficulty_order[d])
    for unit, difficulty in difficulties.items():
      if unit not in self._card_count:
        continue
      if difficulty != self._difficulty:
        print(f"Difficulty mismatch detected for {unit}")
      self._card_count[unit] += 1
      if difficulty == max_difficulty:
        self._fitting_card_count[unit] += 1

  def get_averages(self) -> tuple[int, int]:
    size = len(self._card_count)
    count_average = sum(self._card_count.values()) / size
    fitting_average = sum(self._fitting_card_count.values()) / size
    return count_average, fitting_average

  def set_limit(self, count_limit: int, fitting_limit: int) -> None:
    self._count_limit = count_limit
    self._fitting_limit = fitting_limit

  def done(self) -> done:
    pass


class SentenceProducer:
  """Helper class that produces sentences for the card pipeline."""
  def __init__(
    self,
    language: Language,
    card_index: CardIndex,
    cards: list[Card],
  ) -> None:
    self._language = language
    self._card_index = card_index
    cards
    self._vocabulary = VOCABULARY[target_language.code_name]
    self._grammar = GRAMMAR[target_language.code_name]
    self._difficulty_map = {}
    for difficulty, words in self._vocabulary.items():
      for word in words:
        self._difficulty_map[word] = difficulty
    difficulties = {u: self._difficulty_map[u] for u in card.units}
    for pool in self._unit_pools.values():
      pool.register_card_units(difficulties)

    async def create(self) -> list[str]:
      return await llm.create_sentences(
        language=self._language,
        difficulty=difficulty,
        grammar=grammar_to_learn,
        units=units_to_learn,
      )

    def done(self) -> bool:
      return False

class DeckBuilder:
  MAX_PARALLELISM = 16

  def __init__(
    self,
    target_language: Language,
    native_language: Language,
  ) -> None:
    self._language = target_language
    self._card_index = CardIndex.load(target_language, native_language)
    self._full_vocabulary = [
      word for words in VOCABULARY[target_language.code_name].values() for word in words
    ]
    self._duplicates = set()

  async def create_cards(
    self,
    *,
    cards_per_unit: int,
    cards_per_call: int,
    verbose: bool = False,
  ) -> None:
    self._duplicates = set()
    cards = await self._card_index.all_cards()
    for card in cards:
      self._duplicates.add(card.sentence)
    sentence_producer = SentenceProducer(self._language, self._card_index, cards)
    print("Initialization complete")

    semaphore = asyncio.Semaphore(self.MAX_PARALLELISM)
    async with asyncio.TaskGroup() as tg:
      while not sentence_producer.done():
        sentences = await sentence_producer.create()
        for sentence in sentences:
          if sentence in self._duplicates:
            print(f"Skipping duplicate sentence {sentence}")
            continue
          self._duplicates.add(sentence)
          await semaphore.acquire()
          tg.create_task(self._complete_card(semaphore, sentence, units_to_learn, grammar_to_learn))
        self._card_index.save()

  async def _complete_card(self, semaphore: asyncio.Semaphore, sentence: str, potential_units: list[str], prompted_grammar: str) -> Card:
    async with semaphore:
      builder = UnitTagsBuilder(sentence)
      while not builder.done():
        # TODO use prompted_units
        new_tag_list = await llm.tag_sentence(
          sentence=builder.sentence,
          language=self._language,
          unit_tags=builder.unit_tags,
        )
        builder.add_filtered(new_tag_list, self._full_vocabulary)
      await self._card_index.create_card(
        builder.sentence, builder.unit_tags, notes=[prompted_grammar]
      )

  async def old_create_cards(
    self,
    *,
    cards_per_unit: int,
    cards_per_call: int,
    verbose: bool = False,
  ) -> None:
    grammar = []
    missing = self._total_missing(cards_per_unit)
    while missing > 0:
      for difficulty in Difficulty:
        units = self._get_missing_units(difficulty, cards_per_unit)
        while units:
          if not grammar:
            grammar = list(self._grammar)
            random.shuffle(grammar)
          grammar_to_learn = grammar.pop()
          units_to_learn = units[-cards_per_call:]
          units = units[:-cards_per_call]
          sentences = await llm.create_sentences(
            language=self._target_language,
            difficulty=difficulty,
            grammar=grammar_to_learn,
            units=units_to_learn,
          )
          builders = await self._tag_sentences(sentences)
          tasks = []
          for builder in builders:
            tasks.append(
              self._card_index.create_card(
                builder.sentence, builder.unit_tags, notes=[grammar_to_learn]
              )
            )
          cards = await asyncio.gather(*tasks)
          if verbose:
            for unit in units_to_learn:
              if all(unit not in card.units for card in cards):
                print(f"The unit '{unit}' was requested, but no generated.")
                for card in cards:
                  print(card)
          self._card_index.save()
      new_missing = self._total_missing(cards_per_unit)
      if new_missing >= missing:
        if new_missing > missing:
          print("Something went wrong, cards were deleted.")
        print(f"Stopping with {new_missing} missing cards.")
        break
      missing = new_missing
      necessary = cards_per_unit * len(self._full_vocabulary)
      done = necessary - missing
      print(f"Generated {done} out of {necessary} mandatory cards")

  def _get_missing_units(
    self,
    difficulty: Difficulty,
    cards_per_unit: int,
  ) -> list[str]:
    units = list(self._vocabulary.get(difficulty, []))
    random.shuffle(units)
    return [u for u in units if self._card_index.size(u) < cards_per_unit]

  def _total_missing(self, cards_per_unit: int) -> int:
    total = 0
    for unit in self._full_vocabulary:
      total += max(0, cards_per_unit - self._card_index.size(unit))
    return total
