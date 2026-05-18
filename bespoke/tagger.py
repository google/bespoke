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
from bespoke import languages
from bespoke import llm
from bespoke.unit import Unit


class Tagger(abc.ABC):
    """Abstract base class for taggers."""

    @abc.abstractmethod
    def sentence(self) -> str:
        """Returns the sentence being tagged."""

    @abc.abstractmethod
    def hint(self) -> list[str]:
        """Returns the hints (targeted units) used for this sentence."""

    @abc.abstractmethod
    async def progress(self, llm_client: llm.LlmClient) -> None:
        """Progresses the tagging."""

    @abc.abstractmethod
    def done(self) -> bool:
        """Returns True if tagging is complete."""

    @abc.abstractmethod
    def tags(self) -> dict[str, Unit]:
        """Returns the map from non-overlapping substrings to Unit."""


class WordTagger(Tagger):
    """Tagger for WordUnit that uses the baseline tagging logic."""

    DONE_AFTER = 1

    def __init__(
        self,
        sentence: str,
        hint: list[str],
        language: languages.Language,
    ) -> None:
        self._sentence = sentence
        self._hint = list(hint)
        self._language = language
        self._unit_tags: dict[str, Unit] = {}
        self._no_progress_counter = 0
        self._done = False

    def sentence(self) -> str:
        return self._sentence

    def hint(self) -> list[str]:
        return self._hint

    async def progress(self, llm_client: llm.LlmClient) -> None:
        if self._done:
            return

        new_tag_list = await llm_client.tag_sentence(
            sentence=self._sentence,
            language=self._language,
            hint=self._hint,
        )

        old_tags = dict(self._unit_tags)
        all_tags = new_tag_list + [
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

    def tags(self) -> dict[str, Unit]:
        return self._unit_tags


class DictionaryTagger(Tagger):
    """Tagger for DictionaryUnit that disambiguates homonyms."""

    def __init__(
        self,
        sentence: str,
        hint: list[str],
        language: languages.Language,
    ) -> None:
        self._sentence = sentence
        self._hint = list(hint)
        self._language = language
        self._unit_tags: dict[str, Unit] = {}
        self._done = False

    def sentence(self) -> str:
        return self._sentence

    def hint(self) -> list[str]:
        return self._hint

    async def progress(self, llm_client: llm.LlmClient) -> None:
        if self._done:
            return

        # Find candidates by looking up all substrings of the sentence
        candidates = set()
        sentence = self.sentence()
        for i in range(len(sentence)):
            for j in range(i + 1, len(sentence) + 1):
                substring = sentence[i:j]
                if self._language.get_by_name(substring):
                    candidates.add(substring)

        # Construct hints string
        hint_lines = []
        for word in candidates:
            units = self._language.get_by_name(word)
            for idx, u in enumerate(units):
                hint_lines.append(f"Word: {word}, Index: {idx} - {u.definition()}")
        hints_str = "\n".join(hint_lines)

        results = await llm_client.tag_sentence_disambiguated(
            sentence=self.sentence(),
            language=self._language,
            hints=hints_str,
        )

        for occurance, word, idx in results:
            try:
                units = self._language.get_by_name(word)
                selected_unit = units[idx]
                self._unit_tags[occurance] = selected_unit
            except IndexError as e:
                print(f"Error resolving tag for {word} at index {idx}: {e}")

        self._done = True

    def done(self) -> bool:
        return self._done

    def tags(self) -> dict[str, Unit]:
        return self._unit_tags
