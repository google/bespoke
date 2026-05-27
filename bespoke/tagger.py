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

_MAX_ROUNDS = 5


def is_punctuation_or_space(char: str) -> bool:
    cat = unicodedata.category(char)
    return cat.startswith("P") or cat.startswith("Z")


def is_more_than_punctuation(text: str) -> bool:
    return any(not is_punctuation_or_space(c) for c in text)


def strip_punctuation_and_space(text: str) -> str:
    start = 0
    while start < len(text) and is_punctuation_or_space(text[start]):
        start += 1
    end = len(text)
    while end > start and is_punctuation_or_space(text[end - 1]):
        end -= 1
    return text[start:end]


async def create_tags(
    sentence: str,
    hint: list[Unit],
    language: languages.Language,
    llm_client: llm.LlmClient,
) -> UnitTags:
    """Tags words in a sentence with their dictionary form."""
    unit_tags: UnitTags = []
    start_indices: list[int] = []
    is_chinese = language.code_name in ["simp_chinese", "trad_chinese"]
    missing_parts = [sentence]
    marked_sentence = None

    for round in range(_MAX_ROUNDS):
        if round == 0:
            suggestions = set(hint)
        else:
            suggestions = set()
        for part in missing_parts:
            if language.code_name in ["japanese", "simp_chinese", "trad_chinese"]:
                for i in range(len(part)):
                    for j in range(i + 1, len(part) + 1):
                        substring = part[i:j]
                        units = language.get_by_name(substring)
                        suggestions.update(units)
            else:
                words = part.split()
                for word in words:
                    word = strip_punctuation_and_space(word)
                    units = language.get_by_name(word)
                    suggestions.update(units)
        if not is_chinese:
            names = await llm_client.suggest_names(sentence=sentence, language=language)
            for name in names:
                units = language.get_by_name(name.strip())
                suggestions.update(units)

        results = await llm_client.tag_sentence(
            sentence=sentence,
            language=language,
            hint=list(suggestions),
            marked_sentence=marked_sentence,
        )

        new_unit_tags = []
        new_start_indices = []
        sentence_index = 0
        for last_unit_tag, last_start_index in zip(
            unit_tags + [None], start_indices + [len(sentence)]
        ):
            while results:
                unit_tag = results.pop(0)
                unit = language.get_by_id(unit_tag.unit_id)
                if not unit:
                    continue
                if is_chinese and unit_tag.occurance != unit.name():
                    if unit.name() in unit_tag.occurance:
                        print(f"Consider '{unit_tag.occurance}' for the vocabulary.")
                        unit_tag.occurance = unit.name()
                    else:
                        continue
                start_index = sentence.find(unit_tag.occurance, sentence_index)
                if start_index < 0:
                    continue
                if start_index < last_start_index:
                    end_index = start_index + len(unit_tag.occurance)
                    if end_index <= last_start_index:
                        new_unit_tags.append(unit_tag)
                        new_start_indices.append(start_index)
                        sentence_index = end_index
                else:
                    # Belongs to a later gap
                    results.insert(0, unit_tag)
                    break
            if last_unit_tag is not None:
                new_unit_tags.append(last_unit_tag)
                new_start_indices.append(last_start_index)
                sentence_index = last_start_index + len(last_unit_tag.occurance)
        unit_tags = new_unit_tags
        start_indices = new_start_indices

        missing_parts = []
        marked_parts = []
        current_index = 0
        for unit_tag, start_index in zip(unit_tags, start_indices):
            gap = sentence[current_index:start_index]
            if is_more_than_punctuation(gap):
                missing_parts.append(gap)
                marked_parts.append(f"[{gap}]")
            else:
                marked_parts.append(gap)
            marked_parts.append(unit_tag.occurance)
            current_index = start_index + len(unit_tag.occurance)
        gap = sentence[current_index:]
        if is_more_than_punctuation(gap):
            missing_parts.append(gap)
            marked_parts.append(f"[{gap}]")
        else:
            marked_parts.append(gap)
        marked_sentence = "".join(marked_parts)

        if not missing_parts:
            break

    return unit_tags
