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

import numpy as np
import random

from bespoke import Card
from bespoke import Difficulty
from bespoke import Language
from bespoke import Unit
from bespoke import UnitTag
from bespoke import UnitTags
from bespoke import WordUnit
from bespoke import llm


FAKE_VOCABULARY = {
    Difficulty.A1: [
        "それ",
        "見る",
        "円",
        "多い",
        "家",
        "これ",
        "新しい",
        "私",
        "仕事",
        "始める",
    ],
    Difficulty.A2: ["奥", "得意"],
    Difficulty.B1: ["上がる", "業界"],
    Difficulty.B2: [],
    Difficulty.C1: [],
    Difficulty.C2: [],
}
FAKE_GRAMMAR = {
    Difficulty.A1: ["だけ", "だろう"],
    Difficulty.A2: ["かい"],
    Difficulty.B1: ["ばいい"],
    Difficulty.B2: [],
    Difficulty.C1: [],
    Difficulty.C2: [],
}


def fake_language() -> Language:
    language = Language(
        name="Japanese",
        writing_system="Japanese",
        phonetic_system="Hiragana",
        code_name="japanese",
    )

    fake_units: list[Unit] = [
        WordUnit(w, difficulty=d) for d in Difficulty for w in FAKE_VOCABULARY[d]
    ]
    language._units = fake_units
    language._units_by_id = {u.id(): u for u in fake_units}
    for unit in fake_units:
        language._units_by_name.setdefault(unit.name(), []).append(unit)
    language._initialized = True

    return language


def _fake_card(
    sentence: str,
    unit_tags: UnitTags,
    notes: list[str] = [],
) -> Card:
    return Card(
        id=sentence,
        sentence=sentence,
        native_sentence="dummy",
        audio_filename="fake.ogg",
        slow_audio_filename="slow.ogg",
        native_audio_filename="native.ogg",
        phonetic="phonetic",
        unit_tags=unit_tags,
        notes=notes,
    )


class FakeCardIndex:
    def __init__(
        self,
        target_language: Language,
        native_language: Language | None = None,
    ) -> None:
        del native_language
        self._target_language = target_language
        self._cards = {}
        for unit in self._target_language.units():
            card = _fake_card(
                unit.name(), [UnitTag(occurance=unit.name(), unit_id=unit.id())], []
            )
            self._cards[unit.id()] = [card]

    def save(self) -> None:
        pass

    def cards(self, unit: Unit) -> list[Card]:
        return self._cards.get(unit.id(), [])

    async def all_cards(self) -> list[Card]:
        unique_cards = {}
        for cards in self._cards.values():
            for card in cards:
                unique_cards[card.id] = card
        return list(unique_cards.values())

    def size(self, unit: Unit) -> int:
        return len(self.cards(unit))

    async def create_card(
        self,
        llm_client: llm.LlmClient,
        sentence: str,
        unit_tags: UnitTags,
        notes: list[str] = [],
    ) -> Card:
        card = _fake_card(sentence, unit_tags, notes)
        for unit_str in card.unit_ids():
            # Intentionally fails if the unit does not exist yet.
            self._cards[unit_str].append(card)
        return card


class FakeLlmClient(llm.LlmClient):
    async def suggest_names(self, sentence: str, language: Language) -> list[str]:
        names = []
        for unit in language.units():
            if unit.name() in sentence:
                names.append(unit.name())
        return names

    async def translate(self, sentence: str, language: Language) -> str:
        return f"In {language.name}: {sentence}"

    async def to_phonetic(self, sentence: str, language: Language) -> str | None:
        return f"{language.phonetic_system}: {sentence}"

    async def create_sentences(
        self,
        language: Language,
        difficulty: Difficulty,
        grammar: str,
        units: list[Unit],
    ) -> list[str]:
        prefix = "." * random.randint(1, 100)
        suffix = "." * random.randint(1, 100)
        return [f"{prefix}{unit.name()}{suffix}" for unit in units]

    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[Unit],
        marked_sentence: str | None = None,
    ) -> UnitTags:
        unit = sentence.strip(".")
        return [UnitTag(occurance=unit, unit_id=unit)]

    async def tag_sentence_disambiguated(
        self,
        sentence: str,
        language: Language,
        hints: str,
    ) -> list[tuple[str, str, int]]:
        return []

    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        return np.array([], dtype=np.int16)
