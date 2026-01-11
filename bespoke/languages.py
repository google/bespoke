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

To support your native language to translate into, add a Language config file
to the `DATA_DIR` directory.

If you want to be able to learn the language, additionally navigate to
-> `DATA_DIR` -> `language.code_name`
and add the files:

- `vocabulary_{difficulty}.txt` for all difficulties with vocabulary.
- `grammar_{difficulty}.txt` with grammar concepts in the language.

The txt files have one entry per line. You need at least the files for A1.
"""

from enum import StrEnum
from pathlib import Path
import pydantic
from typing import Self
import os


UnitTags = dict[str, str]

DATA_DIR = Path("languages")


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
        return [word for d in Difficulty for word in data.vocabulary(d)]

    def grammar(self, difficulty: Difficulty) -> list[str]:
        return LANGUAGE_DATA[self.code_name].grammar(difficulty)

    @classmethod
    def load(cls, path: Path | str) -> Self:
        with open(path, "r", encoding="utf-8") as f:
            return Language.model_validate_json(f.read())

    def has_data(self) -> bool:
        for prefix in ["vocabulary", "grammar"]:
            path = DATA_DIR / self.code_name / f"{prefix}_{Difficulty.A1}.txt"
            if not path.exists():
                return False
        return True


def _read_textfile(path: Path | str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Unreadable file '{path}'")
        return []


class LanguageData:
    """Lazily initialized vocabulary and grammar lists."""

    def __init__(self, code_name: str) -> None:
        self._code_name = code_name
        self._vocabulary = {}
        self._grammar = {}

    def _initialize(self) -> None:
        if self._vocabulary:
            return
        self._vocabulary = self._read_all_difficulties("vocabulary")
        self._grammar = self._read_all_difficulties("grammar")

    def vocabulary(self, difficulty: Difficulty) -> list[str]:
        self._initialize()
        return self._vocabulary[difficulty]

    def grammar(self, difficulty: Difficulty) -> list[str]:
        self._initialize()
        return self._grammar[difficulty]

    def _read_all_difficulties(self, prefix: str) -> dict[Difficulty, list[str]]:
        content = {}
        all_content = set()
        for difficulty in Difficulty:
            path = DATA_DIR / self._code_name / f"{prefix}_{difficulty}.txt"
            wordlist = _read_textfile(path)
            filtered = []
            for word in wordlist:
                if word not in all_content:
                    all_content.add(word)
                    filtered.append(word)
            content[difficulty] = filtered
        return content


_ALL_LANGUAGES = [Language.load(path) for path in DATA_DIR.glob("*.json")]
LANGUAGES = {language.code_name: language for language in _ALL_LANGUAGES}
LANGUAGE_DATA = {
    code_name: LanguageData(code_name)
    for code_name, language in LANGUAGES.items()
    if language.has_data()
}
