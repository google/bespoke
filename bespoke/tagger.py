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

"""Tagger implementations for different unit types."""

import abc
import unicodedata

from bespoke import languages
from bespoke import llm
from bespoke.unit import Unit
from bespoke.unit import WordUnit
from bespoke.unit import UnitTag
from bespoke.unit import UnitTags

_MAX_ROUNDS = 3


def clean_length(text: str) -> int:
    """Calculates the length of a string excluding spaces and punctuation."""
    clean_count: int = 0
    for char in text:
        category: str = unicodedata.category(char)
        # Z = Space separator, P = Punctuation
        if not (category.startswith("Z") or category.startswith("P")):
            clean_count += 1
    return clean_count


class Tagger(abc.ABC):
    """Abstract base class for taggers."""

    @abc.abstractmethod
    def sentence(self) -> str:
        """Returns the sentence being tagged."""

    @abc.abstractmethod
    async def create(self, llm_client: llm.LlmClient) -> UnitTags:
        """Creates the tags for the sentence."""


class WordTagger(Tagger):
    """Tagger for WordUnit that uses the baseline tagging logic."""

    DONE_AFTER = 1

    def __init__(
        self,
        sentence: str,
        hint: list[Unit],
        language: languages.Language,
    ) -> None:
        self._sentence = sentence
        self._hint = list(hint)
        self._language = language

    def sentence(self) -> str:
        return self._sentence

    async def create(self, llm_client: llm.LlmClient) -> UnitTags:
        new_tag_list = await llm_client.tag_sentence(
            sentence=self._sentence,
            language=self._language,
            hint=self._hint,
        )

        old_tags = list(self._unit_tags)
        all_tags = [(t.occurance, t.unit_id) for t in new_tag_list] + [
            (word, u.id()) for word, u in self._unit_tags.items()
        ]
        all_tags.sort(key=lambda x: len(x[1]), reverse=True)
        all_tags.sort(key=lambda x: len(x[0]), reverse=True)

        sentence = self._sentence
        used_units = set()
        filtered: dict[str, Unit] = {}
        for word, unit_id in all_tags:
            if word not in sentence:
                continue
            resolved = self._language.get_by_id(unit_id)
            if resolved is None:
                continue
            if not isinstance(resolved, WordUnit):
                continue
            if unit_id in used_units:
                continue
            sentence = sentence.replace(word, "", 1)
            filtered[word] = resolved
            used_units.add(unit_id)

        self._unit_tags = filtered

        if len(old_tags) >= len(self._unit_tags):
            self._no_progress_counter += 1

        if self._no_progress_counter >= self.DONE_AFTER:
            self._done = True

    def done(self) -> bool:
        return self._done

    def tags(self) -> UnitTags:
        return [
            UnitTag(occurance=word, unit_id=u.id())
            for word, u in self._unit_tags.items()
        ]


class DictionaryTagger(Tagger):
    """Tagger for DictionaryUnit that disambiguates homonyms."""

    def __init__(
        self,
        sentence: str,
        hint: list[Unit],
        language: languages.Language,
    ) -> None:
        self._sentence = sentence
        self._language = language
        self._unit_tags: UnitTags = []
        self._done = False
        self._hint = hint

    def sentence(self) -> str:
        return self._sentence

    async def create(self, llm_client: llm.LlmClient) -> UnitTags:
        candidates = set()
        if self._language.code_name in ["japanese", "simp_chinese", "trad_chinese"]:
            for i in range(len(self._sentence)):
                for j in range(i + 1, len(self._sentence) + 1):
                    substring = self._sentence[i:j]
                    unit_ids = self._language.get_by_name(substring)
                    candidates.update(unit_ids)
        else:
            words = self._sentence.split()
            for word in words:
                word = word.strip(".,;!?")
                unit_ids = self._language.get_by_name(word)
                candidates.update(unit_ids)
        hint = self._hint + list(candidates)

        unit_tags = []
        start_indices = []
        is_chinese = self._language.code_name in ["simp_chinese", "trad_chinese"]
        for _ in range(_MAX_ROUNDS):
            suggestions = set()
            if not is_chinese:
                names = await llm_client.suggest_names(
                    sentence=self._sentence, language=self._language
                )
                for name in names:
                    unit_ids = self._language.get_by_name(name.strip())
                    suggestions.update(unit_ids)

            results = await llm_client.tag_sentence(
                sentence=self._sentence,
                language=self._language,
                hint=hint + list(suggestions),
            )
            new_unit_tags = []
            new_start_indices = []
            sentence_index = 0
            for unit_tag in results:
                unit = self._language.get_by_id(unit_tag.unit_id)
                if not unit:
                    continue
                if is_chinese and unit_tag.occurance != unit.name():
                    continue
                start_index = self._sentence.find(unit_tag.occurance, sentence_index)
                if start_index < 0:
                    continue
                for last_unit_tag, last_start_index in zip(unit_tags, start_indices):
                    if sentence_index <= last_start_index < start_index:
                        end_index = last_start_index + len(last_unit_tag.occurance)
                        if end_index < start_index:
                            new_unit_tags.append(last_unit_tag)
                            new_start_indices.append(last_start_index)
                sentence_index = start_index + len(unit_tag.occurance)
                new_unit_tags.append(unit_tag)
                new_start_indices.append(start_index)

            unit_tags = new_unit_tags
            start_indices = new_start_indices
            occurance_length = sum(
                clean_length(unit_tag.occurance) for unit_tag in unit_tags
            )
            if occurance_length >= clean_length(self._sentence):
                break

        return unit_tags
