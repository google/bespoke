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

- `vocabulary.csv` with entries for at least A1.
- `grammar_{difficulty}.txt` with grammar concepts in the language, at least A1.

The txt files are one entry per line.
The csv is a table with name, definition and difficulty.
"""

import csv

from pathlib import Path
import pydantic
from typing import Self
from bespoke.unit import DictionaryUnit
from bespoke.unit import Unit
from bespoke.unit import WordUnit
from bespoke.difficulty import Difficulty


UnitTags = dict[str, str]

DATA_DIR = Path("languages")


class Language(pydantic.BaseModel):
    # The English word for the spoken language. Not necessarily unique.
    name: str
    # The English word for the written language. May coincide with the name.
    writing_system: str
    # The English word for a way to make the pronounciation more readable.
    phonetic_system: str | None
    # Used for filenames etc. and needs to be unique
    code_name: str

    def units(self) -> list[Unit]:
        return LANGUAGE_DATA[self.code_name].units()

    @classmethod
    def load(cls, path: Path | str) -> Self:
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def has_data(self) -> bool:
        path = DATA_DIR / self.code_name / "vocabulary.csv"
        return path.exists()


class LanguageData:
    """Lazily initialized vocabulary lists from CSV."""

    def __init__(self, code_name: str) -> None:
        self._code_name = code_name
        self._units: list[Unit] = []

    def _initialize(self) -> None:
        if self._units:
            return

        csv_path = DATA_DIR / self._code_name / "vocabulary.csv"
        if not csv_path.exists():
            print(f"File not found: {csv_path}")
            return

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                return

            use_definition = bool(rows[0].get("definition"))
            for row in rows:
                word = row["name"]
                definition = row.get("definition", "")
                difficulty = Difficulty(row["difficulty"])
                if use_definition:
                    if not definition:
                        raise ValueError(
                            f"Missing definition for word '{word}' in {csv_path}"
                        )
                    self._units.append(
                        DictionaryUnit(
                            name=word, definition=definition, difficulty=difficulty
                        )
                    )
                else:
                    if definition:
                        print(f"Unexpected definition for word '{word}' in {csv_path}")
                    self._units.append(WordUnit(word, difficulty=difficulty))

    def units(self) -> list[Unit]:
        self._initialize()
        return self._units


def load_grammar(code_name: str) -> dict[Difficulty, list[str]]:
    grammar = {}
    for difficulty in Difficulty:
        path = DATA_DIR / code_name / f"grammar_{difficulty}.txt"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                grammar[difficulty] = [line.strip() for line in f if line.strip()]
        else:
            grammar[difficulty] = []
    return grammar


_ALL_LANGUAGES = [Language.load(path) for path in DATA_DIR.glob("*.json")]
LANGUAGES = {language.code_name: language for language in _ALL_LANGUAGES}
LANGUAGE_DATA = {
    code_name: LanguageData(code_name)
    for code_name, language in LANGUAGES.items()
    if language.has_data()
}
