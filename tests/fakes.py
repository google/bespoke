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
import types

from bespoke import Card
from bespoke import Difficulty
from bespoke import Language
from bespoke import UnitTags
from bespoke import llm
from bespoke.unit import Unit


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

    def vocabulary(self, difficulty: Difficulty) -> list[str]:
        return FAKE_VOCABULARY[difficulty]

    def full_vocabulary(self) -> list[str]:
        return [word for d in Difficulty for word in FAKE_VOCABULARY[d]]

    def grammar(self, difficulty: Difficulty) -> list[str]:
        return FAKE_GRAMMAR[difficulty]

    object.__setattr__(language, "vocabulary", types.MethodType(vocabulary, language))
    object.__setattr__(
        language, "full_vocabulary", types.MethodType(full_vocabulary, language)
    )
    object.__setattr__(language, "grammar", types.MethodType(grammar, language))
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
        units=list(set(unit_tags.values())),
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
        for unit in self._target_language.full_vocabulary():
            card = _fake_card(unit, {unit: unit}, [])
            self._cards[unit] = [card]

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
        for unit in card.units:
            # Intentionally fails if the unit does not exist yet.
            self._cards[unit].append(card)
        return card


class FakeLlmClient(llm.LlmClient):
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
        prefix = "." * random.randint(1, 4)
        suffix = "." * random.randint(1, 4)
        return [f"{prefix}{unit.name()}{suffix}" for unit in units]

    async def tag_sentence(
        self,
        sentence: str,
        language: Language,
        hint: list[str],
    ) -> list[tuple[str, str]]:
        unit = sentence.strip(".")
        return [(unit, unit)]

    async def speak(
        self,
        sentence: str,
        *,
        slowly: bool = False,
    ) -> np.ndarray:
        return np.array([], dtype=np.int16)
