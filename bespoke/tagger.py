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

import unicodedata

from bespoke import languages
from bespoke import llm
from bespoke.unit import Unit
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


async def create_tags(
    sentence: str,
    hint: list[Unit],
    language: languages.Language,
    llm_client: llm.LlmClient,
) -> UnitTags:
    """Tags words in a sentence with their dictionary form."""
    candidates = set()
    if language.code_name in ["japanese", "simp_chinese", "trad_chinese"]:
        for i in range(len(sentence)):
            for j in range(i + 1, len(sentence) + 1):
                substring = sentence[i:j]
                units = language.get_by_name(substring)
                candidates.update(units)
    else:
        words = sentence.split()
        for word in words:
            word = word.strip(".,;!?")
            units = language.get_by_name(word)
            candidates.update(units)
    full_hint = hint + list(candidates)

    unit_tags: UnitTags = []
    start_indices: list[int] = []
    is_chinese = language.code_name in ["simp_chinese", "trad_chinese"]
    for _ in range(_MAX_ROUNDS):
        suggestions = set()
        if not is_chinese:
            names = await llm_client.suggest_names(sentence=sentence, language=language)
            for name in names:
                units = language.get_by_name(name.strip())
                suggestions.update(units)

        results = await llm_client.tag_sentence(
            sentence=sentence,
            language=language,
            hint=full_hint + list(suggestions),
        )
        new_unit_tags = []
        new_start_indices = []
        sentence_index = 0
        for unit_tag in results:
            unit = language.get_by_id(unit_tag.unit_id)
            if not unit:
                continue
            if is_chinese and unit_tag.occurance != unit.name():
                continue
            start_index = sentence.find(unit_tag.occurance, sentence_index)
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
        if occurance_length >= clean_length(sentence):
            break

    return unit_tags
