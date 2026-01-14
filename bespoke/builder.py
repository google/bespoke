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

from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import UnitTags
from bespoke.languages import GRAMMAR
from bespoke.languages import VOCABULARY
from bespoke import llm


# Helper class to iteratively build the UnitTags
class UnitTagsBuilder:
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

  def check_progress(self, old_tags: UnitTags) -> None:
    if len(old_tags) >= len(self.unit_tags):
      self._no_progress_counter += 1

  def done(self) -> bool:
    return self._no_progress_counter >= self.DONE_AFTER


class DeckBuilder:
  def __init__(
    self,
    target_language: Language,
    native_language: Language,
  ) -> None:
    self._target_language = target_language
    self._native_language = native_language
    self._card_index = CardIndex.load(target_language, native_language)
    self._vocabulary = VOCABULARY[target_language.code_name]
    self._full_vocabulary = [
      word for words in self._vocabulary.values() for word in words
    ]
    self._grammar = GRAMMAR[target_language.code_name]

  async def create_cards(
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

  async def _tag_sentences(
    self,
    sentences: list[str],
  ) -> list[UnitTagsBuilder]:
    builders = [UnitTagsBuilder(sentence) for sentence in sentences]
    while not all(builder.done() for builder in builders):
      used_builders = []
      tasks = []
      for builder in builders:
        if not builder.done():
          used_builders.append(builder)
          tasks.append(
            llm.tag_sentence(
              sentence=builder.sentence,
              language=self._target_language,
              unit_tags=builder.unit_tags,
            )
          )
      all_new_tags = await asyncio.gather(*tasks)
      for builder, new_tag_list in zip(used_builders, all_new_tags):
        old_tags = builder.unit_tags
        builder.add_filtered(new_tag_list, self._full_vocabulary)
        builder.check_progress(old_tags)
    return builders
