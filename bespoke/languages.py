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

"""Supported languages and related data.

To support your native language to translate into, add:

- A constant of type `Language`.
- An entry in `_ALL_LANGUAGES`.

If you want to be able to learn the language, on top of that:

- Add the language constant to `SUPPORTED_LANGUAGES` below.
- Files f"data/{code_name}_{difficulty).txt for all difficulties with vocabulary.
- A file f"data/{code_name}_grammar.txt with grammar concepts in the language.

The txt files have one entry per line.
"""

from enum import StrEnum
import pydantic
import os


UnitTags = dict[str, str]


class Difficulty(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


DIFFICULTY_EXPLANATIONS = {
    Difficulty.A1: "Beginner, understands and uses simple phrases and sentences.",
    Difficulty.A2: "Basic knowledge of frequently used expressions in areas of immediate relevance.",
    Difficulty.B1: "Intermediate, understands main points of clear standard language.",
    Difficulty.B2: "Independent, can interact with native speakers without strain.",
    Difficulty.C1: "Proficient, can understand demanding, longer clauses and recognise implicit meaning.",
    Difficulty.C2: "Near native, understands virtually everything heard or read with ease.",
}


class Language(pydantic.BaseModel):
    # The English word for the spoken language. Not necessarily unique.
    name: str
    # The English word for the written language. May coincide with the name.
    writing_system: str
    # The English word for a way to make the pronounciation more readable.
    phonetic_system: str | None
    # Used for filenames etc. and needs to be unique
    code_name: str
    # From https://ai.google.dev/gemini-api/docs/live-guide#supported-languages
    live_code: str


ENGLISH = Language(
    name="English",
    writing_system="English",
    phonetic_system=None,
    code_name="english",
    live_code="en-US",
)
GERMAN = Language(
    name="German",
    writing_system="German",
    phonetic_system=None,
    code_name="german",
    live_code="de-DE",
)
FRENCH = Language(
    name="French",
    writing_system="French",
    phonetic_system=None,
    code_name="french",
    live_code="fr-FR",
)
RUSSIAN = Language(
    name="Russian",
    writing_system="Russian",
    phonetic_system=None,
    code_name="russian",
    live_code="ru-RU",
)
POLISH = Language(
    name="Polish",
    writing_system="Polish",
    phonetic_system=None,
    code_name="polish",
    live_code="pl-PL",
)
JAPANESE = Language(
    name="Japanese",
    writing_system="Japanese",
    phonetic_system="Hiragana",
    code_name="japanese",
    live_code="ja-JP",
)
# Next two are Mandarin, should be synonymous.
SIMP_CHINESE = Language(
    name="Chinese",
    writing_system="Simplified Chinese",
    phonetic_system="Pinyin",
    code_name="simp_chinese",
    live_code="cmn-CN",
)
TRAD_CHINESE = Language(
    name="Chinese",
    writing_system="Traditional Chinese",
    phonetic_system="Pinyin",
    code_name="trad_chinese",
    live_code="cmn-CN",
)
_ALL_LANGUAGES = [
    ENGLISH,
    GERMAN,
    FRENCH,
    RUSSIAN,
    POLISH,
    JAPANESE,
    SIMP_CHINESE,
    TRAD_CHINESE,
]
LANGUAGES = {language.code_name: language for language in _ALL_LANGUAGES}


def _read_wordlist(filename: str) -> list[str]:
    words = []
    try:
        with open(filename, "r") as f:
            for word in f.readlines():
                words.append(word.strip())
    except:
        print(f"Unreadable wordlist file '{filename}'")
    return words


def _read_vocabulary(language: Language, verbose: bool = False) -> dict:
    vocabulary = {}
    full_vocabulary = set()
    discarded = 0
    for difficulty in Difficulty:
        filename = f"data/{language.code_name}_{difficulty}.txt"
        if os.path.isfile(filename):
            wordlist = _read_wordlist(filename)
            unique_wordlist = []
            for word in wordlist:
                if verbose:
                    for punctuation in [".", ",", ":", ";", "。", "、"]:
                        if punctuation in word:
                            print(f"Detected puntuation in '{filename}' -> {word}")
                if word in full_vocabulary:
                    discarded += 1
                else:
                    full_vocabulary.add(word)
                    unique_wordlist.append(word)
            vocabulary[difficulty] = unique_wordlist
        else:
            print(f"Missing wordlist file '{filename}'")
    if verbose and discarded:
        print(f"Discarded {discarded} duplicates for {language.writing_system}")
    return vocabulary


SUPPORTED_LANGUAGES = [JAPANESE, SIMP_CHINESE, TRAD_CHINESE]
VOCABULARY = {
    language.code_name: _read_vocabulary(language) for language in SUPPORTED_LANGUAGES
}
GRAMMAR = {
    language.code_name: _read_wordlist(f"data/{language.code_name}_grammar.txt")
    for language in SUPPORTED_LANGUAGES
}
