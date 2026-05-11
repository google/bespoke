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

"""Extensible unit design for learned items."""

from abc import ABC, abstractmethod
from bespoke.languages import Difficulty


class Unit(ABC):
    """Abstract base class for a unit of language knowledge."""

    @abstractmethod
    def id(self) -> str:
        """Key for the unit in files and maps."""

    @abstractmethod
    def name(self) -> str:
        """A non-unique, guessable name for the unit. E.g. a stem form."""

    @abstractmethod
    def definition(self) -> str:
        """Unique explanation of the meaning in the unit's own language."""

    @abstractmethod
    def difficulty(self) -> Difficulty | None:
        """Get the difficulty level of the unit."""

    @abstractmethod
    def translation(self) -> str | None:
        """Get the translation of the unit in the native language."""


class WordUnit(Unit):
    """Simple implementation that uses words as base knowledge."""

    def __init__(self, word: str, difficulty: Difficulty | None = None) -> None:
        self._word = word
        self._difficulty = difficulty

    def id(self) -> str:
        return self._word

    def name(self) -> str:
        return self._word

    def definition(self) -> str:
        return self._word

    def difficulty(self) -> Difficulty | None:
        return self._difficulty

    def translation(self) -> str | None:
        return None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WordUnit):
            return NotImplemented
        return self._word == other._word

    def __hash__(self) -> int:
        return hash(self._word)

    def __str__(self) -> str:
        return self._word


class DictionaryUnit(Unit):
    """Unit implementation that disambiguates homonyms using definitions."""

    def __init__(
        self,
        name: str,
        definition: str,
        difficulty: Difficulty | None = None,
        translation: str | None = None,
    ) -> None:
        self._name = name
        self._definition = definition
        self._difficulty = difficulty
        self._translation = translation

    def id(self) -> str:
        return self._definition

    def name(self) -> str:
        return self._name

    def definition(self) -> str:
        return self._definition

    def difficulty(self) -> Difficulty | None:
        return self._difficulty

    def translation(self) -> str | None:
        return self._translation

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DictionaryUnit):
            return NotImplemented
        return self._definition == other._definition

    def __hash__(self) -> int:
        return hash(self._definition)

    def __str__(self) -> str:
        return self._definition


class UnitIndex:
    """Allows lookup of a Unit by ID or name."""

    def __init__(self) -> None:
        self._units_by_id: dict[str, Unit] = {}
        self._units_by_name: dict[str, list[Unit]] = {}

    def add(self, unit: Unit) -> None:
        self._units_by_id[unit.id()] = unit
        self._units_by_name.setdefault(unit.name(), []).append(unit)

    def get_by_id(self, unit_id: str) -> Unit | None:
        return self._units_by_id.get(unit_id)

    def get_by_name(self, name: str) -> list[Unit]:
        return self._units_by_name.get(name, [])
