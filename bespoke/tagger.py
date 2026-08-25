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

import asyncio
import unicodedata

from bespoke import languages
from bespoke import llm
from bespoke.unit import Unit
from bespoke.unit import UnitTag
from bespoke.unit import UnitTags

PUNCTUATION_TO_PRUNE = ("。", "、", "？", "！", ".", ",", "!", "?", ";", ":")

JAPANESE_GRAMMAR_WORDS: dict[str, str] = {
    # Suru inflections (longest first)
    "したくありませんでした": "する",
    "したくありません": "する",
    "しませんでした": "する",
    "したくなかった": "する",
    "したかったです": "する",
    "しなかった": "する",
    "させられた": "する",
    "させられる": "する",
    "させられて": "する",
    "させません": "する",
    "させました": "する",
    "されません": "する",
    "されました": "する",
    "させたくない": "する",
    "させたくて": "する",
    "したければ": "する",
    "したいです": "する",
    "したくない": "する",
    "したかった": "する",
    "したくて": "する",
    "しないで": "する",
    "しました": "する",
    "しません": "する",
    "させない": "する",
    "させます": "する",
    "されない": "する",
    "されます": "する",
    "できる": "できる",
    "できた": "できる",
    "できて": "できる",
    "できない": "できる",
    "できます": "できる",
    "できれば": "できる",
    "させたい": "する",
    "させる": "する",
    "させた": "する",
    "させて": "する",
    "される": "する",
    "された": "する",
    "されて": "する",
    "しない": "する",
    "します": "する",
    "しよう": "する",
    "すれば": "する",
    "したい": "する",
    "すれ": "する",
    "せよ": "する",
    "しろ": "する",
    "して": "する",
    "した": "する",
    "する": "する",
    # Particles and functional words
    "けれども": "けれども",
    "かしら": "かしら",
    "けれど": "けれど",
    "ばかり": "ばかり",
    "くらい": "くらい",
    "ぐらい": "ぐらい",
    "ながら": "ながら",
    "ならば": "なら",
    "から": "から",
    "まで": "まで",
    "こと": "こと",
    "もの": "もの",
    "だけ": "だけ",
    "しか": "しか",
    "など": "など",
    "ほど": "ほど",
    "ごろ": "ごろ",
    "でも": "でも",
    "かも": "かも",
    "って": "って",
    "より": "より",
    "さえ": "さえ",
    "すら": "すら",
    "こそ": "こそ",
    "べき": "べき",
    "かけて": "かける",
    "っけ": "っけ",
    "くせに": "くせに",
    "ものの": "ものの",
    "どころか": "どころか",
    "ばかりか": "ばかりか",
    "のみならず": "のみならず",
    "まい": "まい",
    "つつ": "つつ",
    "だに": "だに",
    "たりとも": "たりとも",
    "とて": "とて",
    "っこない": "っこない",
    "べからず": "べからず",
    "べく": "べく",
    "っぱなし": "っぱなし",
    "だらけ": "だらけ",
    "たて": "たて",
    "がち": "がち",
    "放題": "放題",
    "ずつ": "ずつ",
    "けど": "けど",
    "ので": "ので",
    "のに": "のに",
    "なら": "なら",
    "かい": "かい",
    "だい": "だい",
    "この": "この",
    "その": "その",
    "あの": "あの",
    "どの": "どの",
    "は": "は",
    "が": "が",
    "を": "を",
    "に": "に",
    "で": "で",
    "と": "と",
    "へ": "へ",
    "か": "か",
    "ね": "ね",
    "よ": "よ",
    "の": "の",
    "も": "も",
    "や": "や",
    "し": "し",
    "な": "な",
    "わ": "わ",
    "さ": "さ",
    "ぞ": "ぞ",
}

EXCLUDED_FROM_PREMATCH = {"し", "さ"}


def grammar_word_occurance(
    occurance: str,
    stem: str,
) -> str | None:
    """Finds the longest matching grammar word pattern for a stem within occurance."""
    patterns = [p for p, s in JAPANESE_GRAMMAR_WORDS.items() if s == stem]
    patterns.sort(key=len, reverse=True)
    for pattern in patterns:
        if pattern in occurance:
            return pattern
    return None


def find_grammar_word_matches(sentence: str) -> list[str]:
    """Finds non-overlapping grammar word stems present in the sentence, longest pattern first."""
    sorted_patterns = [
        p
        for p in sorted(JAPANESE_GRAMMAR_WORDS.keys(), key=len, reverse=True)
        if p not in EXCLUDED_FROM_PREMATCH
    ]
    claimed = [False] * len(sentence)
    matches: list[tuple[int, str]] = []

    for pattern in sorted_patterns:
        start = 0
        while True:
            idx = sentence.find(pattern, start)
            if idx == -1:
                break
            end = idx + len(pattern)
            if not any(claimed[idx:end]):
                for k in range(idx, end):
                    claimed[k] = True
                stem = JAPANESE_GRAMMAR_WORDS[pattern]
                matches.append((idx, stem))
            start = idx + 1

    matches.sort(key=lambda m: m[0])
    return [m[1] for m in matches]


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


def strip_explicit_punctuation(text: str) -> str:
    start = 0
    while start < len(text) and text[start] in PUNCTUATION_TO_PRUNE:
        start += 1
    end = len(text)
    while end > start and text[end - 1] in PUNCTUATION_TO_PRUNE:
        end -= 1
    return text[start:end]


def get_tagging_coverage(sentence: str, unit_tags: UnitTags) -> float:
    """Returns the ratio of non-punctuation/non-space characters covered by unit tags."""
    clean_total = sum(1 for c in sentence if not is_punctuation_or_space(c))
    if clean_total == 0:
        return 0.0

    tagged_indices: set[int] = set()
    current_idx = 0
    for tag in unit_tags:
        start_idx = sentence.find(tag.occurance, current_idx)
        if start_idx != -1:
            for i in range(start_idx, start_idx + len(tag.occurance)):
                if not is_punctuation_or_space(sentence[i]):
                    tagged_indices.add(i)
            current_idx = start_idx + len(tag.occurance)

    return len(tagged_indices) / clean_total


async def create_tags(
    sentence: str,
    hint: list[Unit],
    language: languages.Language,
    llm_client: llm.LlmClient,
) -> UnitTags:
    """Tags words in a sentence with their dictionary form."""
    if language.code_name in ["simp_chinese", "trad_chinese"]:
        return await _create_tags_chinese(sentence, hint, language, llm_client)
    elif language.code_name == "japanese":
        return await _create_tags_japanese(sentence, hint, language, llm_client)
    else:
        return await _create_tags_general(sentence, hint, language, llm_client)


async def _create_tags_japanese(
    sentence: str,
    hint: list[Unit],
    language: languages.Language,
    llm_client: llm.LlmClient,
) -> UnitTags:
    """Tags words in a Japanese sentence using iterative LLM refinement."""
    max_rounds = 4
    known_units = {}
    for unit in hint:
        known_units[unit.id()] = unit

    # Add grammar words using longest-first matching to prevent 1-char false positives
    for stem in find_grammar_word_matches(sentence):
        for unit in language.get_by_name(stem):
            known_units[unit.id()] = unit

    last_filtered_tags: list[UnitTag] = []

    for round_index in range(max_rounds):
        suggested_names = await llm_client.suggest_names(
            sentence=sentence,
            language=language,
        )
        added_new_unit = False
        for name in suggested_names:
            name_clean = strip_explicit_punctuation(name.strip())
            if not name_clean:
                continue
            for unit in language.get_by_name(name_clean):
                if unit.id() not in known_units:
                    known_units[unit.id()] = unit
                    added_new_unit = True

        tags = await llm_client.tag_sentence(
            sentence=sentence,
            language=language,
            hint=list(known_units.values()),
            existing_tags=list(last_filtered_tags) if last_filtered_tags else None,
        )

        new_filtered_tags: list[UnitTag] = []
        current_index = 0
        for tag in tags:
            occurance = strip_explicit_punctuation(tag.occurance)
            if not occurance or not tag.unit_id:
                continue
            found_unit = language.get_by_id(tag.unit_id)
            if not found_unit:
                continue
            if found_unit.name() in JAPANESE_GRAMMAR_WORDS.values():
                shortened = grammar_word_occurance(occurance, found_unit.name())
                if shortened:
                    occurance = shortened
                else:
                    continue
            start_index = sentence.find(occurance, current_index)
            if start_index != -1:
                new_filtered_tags.append(
                    UnitTag(occurance=occurance, unit_id=found_unit.id())
                )
                current_index = start_index + len(occurance)

        if (
            len(new_filtered_tags) > 0
            and get_tagging_coverage(sentence, new_filtered_tags) >= 1.0
        ):
            return new_filtered_tags
        if not added_new_unit and new_filtered_tags == last_filtered_tags:
            return new_filtered_tags
        last_filtered_tags = new_filtered_tags

    return last_filtered_tags


async def _create_tags_chinese(
    sentence: str,
    hint: list[Unit],
    language: languages.Language,
    llm_client: llm.LlmClient,
) -> UnitTags:
    """Tags words in a Chinese sentence with 100% character coverage requirement."""
    max_rounds = 5
    unit_tags: UnitTags = []
    start_indices: list[int] = []
    missing_parts = [sentence]
    marked_sentence = None

    for round in range(max_rounds):
        if round == 0:
            suggestions = set(hint)
        else:
            suggestions = set()
        for part in missing_parts:
            for i in range(len(part)):
                for j in range(i + 1, len(part) + 1):
                    substring = part[i:j]
                    units = language.get_by_name(substring)
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
                unit_tag.occurance = strip_explicit_punctuation(unit_tag.occurance)
                if not unit_tag.occurance:
                    continue
                unit = language.get_by_id(unit_tag.unit_id)
                if not unit:
                    continue
                if unit_tag.occurance != unit.name():
                    if unit.name() in unit_tag.occurance:
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


async def _create_tags_general(
    sentence: str,
    hint: list[Unit],
    language: languages.Language,
    llm_client: llm.LlmClient,
) -> UnitTags:
    """Tags words for languages without specialized implementations."""
    max_rounds = 2
    unit_tags: UnitTags = []
    start_indices: list[int] = []
    missing_parts = [sentence]
    marked_sentence = None

    for round in range(max_rounds):
        if round == 0:
            suggestions = set(hint)
        else:
            suggestions = set()

        for part in missing_parts:
            words = part.split()
            for word in words:
                word = strip_punctuation_and_space(word)
                units = language.get_by_name(word)
                suggestions.update(units)

        suggested_name_lists = await asyncio.gather(
            *[
                llm_client.suggest_names(sentence=sentence, language=language)
                for _ in range(3)
            ]
        )
        for names in suggested_name_lists:
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
                unit_tag.occurance = strip_explicit_punctuation(unit_tag.occurance)
                if not unit_tag.occurance:
                    continue
                unit = language.get_by_id(unit_tag.unit_id)
                if not unit:
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
