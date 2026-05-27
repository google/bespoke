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
from bespoke.unit import Difficulty

DATA_DIR = Path("languages")

ARTICLES = ["der ", "die ", "das ", "Der ", "Die ", "Das "]


def _get_stripped_forms(text: str) -> list[str]:
    forms = [text]
    for article in ARTICLES:
        if text.startswith(article):
            stripped = text[len(article) :].strip()
            if stripped:
                forms.append(stripped)
    return forms


class Language(pydantic.BaseModel):
    # The English word for the spoken language. Not necessarily unique.
    name: str
    # The English word for the written language. May coincide with the name.
    writing_system: str
    # The English word for a way to make the pronounciation more readable.
    phonetic_system: str | None
    # Used for filenames etc. and needs to be unique
    code_name: str

    # Private attributes for lazy loading/lookups
    _units: list[Unit] = pydantic.PrivateAttr(default_factory=list)
    _units_by_id: dict[str, Unit] = pydantic.PrivateAttr(default_factory=dict)
    _units_by_name: dict[str, list[Unit]] = pydantic.PrivateAttr(default_factory=dict)
    _initialized: bool = pydantic.PrivateAttr(default=False)

    def _initialize(self, use_definition: bool | None = None) -> None:
        if self._initialized:
            return

        csv_path = DATA_DIR / self.code_name / "vocabulary.csv"
        if not csv_path.exists():
            return

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if not rows:
                return

            if use_definition is None:
                use_definition = bool(rows[0].get("definition"))
            for row in rows:
                word = row["name"]
                definition = row.get("definition", "")
                difficulty = Difficulty(row["difficulty"])
                unit: Unit
                if use_definition:
                    if not definition:
                        raise ValueError(
                            f"Missing definition for word '{word}' in {csv_path}"
                        )
                    unit = DictionaryUnit(
                        name=word, definition=definition, difficulty=difficulty
                    )
                else:
                    unit = WordUnit(word, difficulty=difficulty)

                self._units.append(unit)
                self._units_by_id[unit.id()] = unit
                self._units_by_name.setdefault(unit.name(), []).append(unit)
                parts = [p.strip() for p in unit.name().split(",")]
                for part in parts:
                    for form in _get_stripped_forms(part):
                        if form != unit.name():
                            self._units_by_name.setdefault(form, []).append(unit)

        self._initialized = True

    def initialize(self, use_definition: bool) -> None:
        self._initialize(use_definition=use_definition)

    def units(self) -> list[Unit]:
        self._initialize()
        return self._units

    def get_by_id(self, unit_id: str) -> Unit | None:
        self._initialize()
        return self._units_by_id.get(unit_id)

    def get_by_name(self, name: str) -> list[Unit]:
        self._initialize()
        return self._units_by_name.get(name, [])

    @classmethod
    def load(cls, path: Path | str) -> Self:
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())

    def has_data(self) -> bool:
        path = DATA_DIR / self.code_name / "vocabulary.csv"
        return path.exists()


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
