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

If you want to be able to learn the language, additionally:

- Add the language constant to `_SUPPORTED_LANGUAGES` below.
- Files f"data/{code_name}/vocabulary_{difficulty}.txt for all difficulties with vocabulary.
- Files f"data/{code_name}/grammar_{difficulty}.txt with grammar concepts in the language.

The txt files have one entry per line. You need at least vocabulary and grammar for A1.
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

    def vocabulary(self, difficulty: Difficulty) -> list[str]:
        return LANGUAGE_DATA[self.code_name].vocabulary(difficulty)

    def full_vocabulary(self) -> list[str]:
        data = LANGUAGE_DATA[self.code_name]
        return [
            word for d in Difficulty for word in data.vocabulary(d)
        ]

    def grammar(self, difficulty: Difficulty) -> list[str]:
        return LANGUAGE_DATA[self.code_name].grammar(difficulty)


def _read_textfile(filename: str) -> list[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Unreadable file '{filename}'")
        return []


def _read_all_difficulties(prefix: str) -> dict[Difficulty, list[str]]:
    content = {}
    all_content = set()
    for difficulty in Difficulty:
        filename = f"data/{prefix}_{difficulty}.txt"
        wordlist = _read_textfile(filename)
        filtered = []
        for word in wordlist:
            if word not in all_content:
                all_content.add(word)
                filtered.append(word)
        content[difficulty] = filtered
    return content


class LanguageData:
    """Lazily initialized vocabulary and grammar lists."""
    def __init__(self, code_name: str) -> None:
        self._code_name = code_name
        self._vocabulary = {}
        self._grammar = {}

    def _initialize(self) -> None:
        if self._vocabulary:
            return
        vocabulary_prefix = f"{self._code_name}/vocabulary"
        grammar_prefix = f"{self._code_name}/grammar"
        self._vocabulary = _read_all_difficulties(vocabulary_prefix)
        self._grammar = _read_all_difficulties(grammar_prefix)

    def vocabulary(self, difficulty: Difficulty) -> list[str]:
        self._initialize()
        return self._vocabulary[difficulty]

    def grammar(self, difficulty: Difficulty) -> list[str]:
        self._initialize()
        return self._grammar[difficulty]


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
# Chinese = Mandarin
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
_SUPPORTED_LANGUAGES = [
    JAPANESE,
    SIMP_CHINESE,
    TRAD_CHINESE,
]
LANGUAGE_DATA = {
    language.code_name: LanguageData(language.code_name) for language in _SUPPORTED_LANGUAGES
}
