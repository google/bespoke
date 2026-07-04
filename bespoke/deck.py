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

"""Deck class that presents cards and tracks ratings.

Card choice notes:
- The modes for a new card are introduced in the order they were passed in.
- Cards you know on the first attempt have special treatment, they get paused.
- Different mode, any score, is treated as blue.
- Blue (0): Makes a following green act like a blue for some time.
- Yellow (2): Treated like red
- Green (3): Knowledge level is the longest interval not interrupted by red.
- Red (1): Stops and shortens green intervals, high urgency if last.
"""

import csv
from datetime import datetime
import json
import math
from pathlib import Path
import pydantic
import random
import threading
from typing import Self

from bespoke.card import Card
from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import LANGUAGES
from bespoke.urgency import Mode
from bespoke.unit import Unit
from bespoke.unit import DictionaryUnit

from bespoke.urgency import Rating
from bespoke.urgency import RatingState

TRANSLATIONS_FILE_PATTERN = "translations_{target}_{native}.csv"
TOUCH_TOLERANCE_FACTOR = 1.0
TOUCH_TOLERANCE_BUFFER = 10.0
INTRODUCTION_THRESHOLD = 10.0
INTRODUCE_OUT_OF_ORDER = False
# Card scoring constants
REPORT_PENALTY = 1000000.0
CARD_USAGE_FACTOR = 1000.0
CARD_USAGE_DECAY = 0.1
UNTOUCHED_PENALTY = 200.0
UNINTRODUCED_PENALTY = 100.0
URGENCY_BONUS = 10.0
DIFFICULTY_MATCH_BONUS = 0.1
DIFFICULTY_PENALTY = 0.1


class CardUsage(pydantic.BaseModel):
    time: float
    is_reported: bool = False

    model_config = pydantic.ConfigDict(frozen=True)


class Deck:
    def __init__(
        self,
        target_language: Language,
        native_language: Language,
        card_index: CardIndex,
    ) -> None:
        self._target_language = target_language
        self._native_language = native_language
        self._card_index = card_index
        self._rating_states: dict[str, RatingState] = {}
        self._card_id_uses: dict[str, list[CardUsage]] = {}
        self._difficulty = Difficulty.A1
        self._modes = list(Mode)
        self._assume_known: Difficulty | None = None

        self._lock = threading.Lock()
        self._translations: dict[str, str] = {}
        filename = TRANSLATIONS_FILE_PATTERN.format(
            target=target_language.code_name, native=native_language.code_name
        )
        translations_file = Path("cards") / filename
        if translations_file.exists():
            with open(translations_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._translations[row["unit_id"]] = row["translation"]
        self._units_with_cards = []
        for unit in self._target_language.units():
            if self._card_index.size(unit):
                self._units_with_cards.append(unit)
        self._known_unit_modes = 0
        self._mature_unit_modes = 0

    def translated_unit(self, unit_id: str) -> str:
        translated = self._translations.get(unit_id, "")
        if translated:
            return translated
        unit = self._target_language.get_by_id(unit_id)
        if isinstance(unit, DictionaryUnit) and unit.definition():
            return unit.definition()
        return ""

    def _choose_task(self, current_time: float) -> tuple[Mode, str]:
        default_state = RatingState([])

        # First loop over units until first unintroduced
        max_urgency = -1e5
        max_mode = None
        max_unit_id = None
        introduction_index = 0
        introduction_mode = None
        introduction_unit_id = None
        introduction_is_touched = False
        for i, unit in enumerate(self._units_with_cards):
            state = self._rating_states.get(unit.id(), default_state)
            is_skipped = (
                self._assume_known is not None
                and unit.difficulty() <= self._assume_known
            )
            for mode in self._modes:
                urgency = state.urgency(mode, current_time)
                if urgency > max_urgency:
                    max_urgency = urgency
                    max_mode = mode
                    max_unit_id = unit.id()
                if not is_skipped and urgency >= 0.0 and not state.is_introduced(mode):
                    introduction_index = i
                    introduction_mode = mode
                    introduction_unit_id = unit.id()
                    introduction_is_touched = state.is_touched()
                    break
            if introduction_mode is not None:
                break
        if max_mode is None or max_unit_id is None:
            raise ValueError("No units found")

        if max_urgency > 0.0:
            # Case 1: Urgent unit earlier than all new units
            return max_mode, max_unit_id
        if introduction_mode is None or introduction_unit_id is None:
            # Case 2: No new units need to be introduced right now
            print("Nothing needs to be learned right now")
            return max_mode, max_unit_id

        # Second loop over units after first unintroduced
        tolerance = introduction_index * TOUCH_TOLERANCE_FACTOR + TOUCH_TOLERANCE_BUFFER
        tolerance = max(int(tolerance), 1)
        tolerance_index = introduction_index + tolerance
        total_pressure = 0.0
        max_pressure = 0.0
        max_pressure_mode = None
        max_pressure_unit_id = None
        for i, unit in enumerate(
            self._units_with_cards[introduction_index:tolerance_index]
        ):
            if not self._card_index.size(unit):
                continue
            state = self._rating_states.get(unit.id(), default_state)
            index_factor = 1.0 - i / tolerance
            assert 0.0 <= index_factor <= 1.0
            for mode in self._modes:
                urgency = state.urgency(mode, current_time)
                if urgency > 0.0:
                    pressure = urgency * index_factor
                    total_pressure += pressure
                    if pressure > max_pressure:
                        max_pressure = pressure
                        max_pressure_mode = mode
                        max_pressure_unit_id = unit.id()
                elif (
                    INTRODUCE_OUT_OF_ORDER
                    and not introduction_is_touched
                    and state.is_touched()
                    and not state.is_introduced(mode)
                ):
                    introduction_mode = mode
                    introduction_unit_id = unit.id()
                    introduction_is_touched = True

        if total_pressure > INTRODUCTION_THRESHOLD:
            # Case 3: Prioritze learning over introduction
            assert max_pressure_mode is not None
            assert max_pressure_unit_id is not None
            return max_pressure_mode, max_pressure_unit_id
        else:
            # Case 4: Prioritze introduction over learning
            return introduction_mode, introduction_unit_id

    def _score_card(
        self,
        card: Card,
        mode: Mode,
        current_time: float,
    ) -> float:
        default_state = RatingState([])
        score = 0.0
        for usage in self._card_id_uses.get(card.id, []):
            if usage.is_reported:
                score -= REPORT_PENALTY
            days = (current_time - usage.time) / 60.0 / 60.0 / 24.0
            if days >= 0.0:
                score -= CARD_USAGE_FACTOR * math.exp(-CARD_USAGE_DECAY * days)
        for unit_id in card.unit_ids():
            state = self._rating_states.get(unit_id, default_state)
            if not state.is_touched():
                score -= UNTOUCHED_PENALTY
            elif not state.is_introduced(mode):
                score -= UNINTRODUCED_PENALTY
            urgency = state.urgency(mode, current_time)
            if urgency > 0.0:
                score += URGENCY_BONUS * max(urgency, 0.1)
            unit = self._target_language.get_by_id(unit_id)
            unit_difficulty = unit.difficulty() if unit else Difficulty.A1
            if unit_difficulty == self._difficulty:
                score += DIFFICULTY_MATCH_BONUS
            elif unit_difficulty > self._difficulty:
                score += DIFFICULTY_PENALTY
        return score

    def draw(self, current_time: float | None = None) -> tuple[Mode, Card]:
        if current_time is None:
            current_time = datetime.now().timestamp()
        mode, unit_id = self._choose_task(current_time)
        unit = self._target_language.get_by_id(unit_id)
        if unit is None:
            raise ValueError(f"Unit {unit_id} not found in index")
        cards = self._card_index.cards(unit, limit=1000)
        if not cards:
            print(f"No cards found for unit '{unit_id}', showing random card.")
            self.rate(unit, mode, 0)
            unit = random.choice(self._units_with_cards)
            # Limit number of scored cards to improve worst case performance
            cards = self._card_index.cards(unit, limit=1000)
        scored_cards = [
            (self._score_card(card, mode, current_time), card) for card in cards
        ]
        _, best_card = max(scored_cards, key=lambda pair: pair[0])
        return mode, best_card

    def rate(
        self, unit: Unit, mode: Mode, score: int, current_time: float | None = None
    ) -> None:
        if current_time is None:
            current_time = datetime.now().timestamp()
        with self._lock:
            rating = Rating(mode=mode, time=current_time, score=score)
            rating_state = self._rating_states.get(unit.id(), RatingState([]))
            if mode in self._modes:
                self._known_unit_modes -= rating_state.is_known(mode)
                self._mature_unit_modes -= rating_state.is_mature(mode)
            rating_state.add(rating)
            self._rating_states[unit.id()] = rating_state
            if mode in self._modes:
                self._known_unit_modes += rating_state.is_known(mode)
                self._mature_unit_modes += rating_state.is_mature(mode)

    def log_usage(
        self, card_id: str, is_reported: bool = False, current_time: float | None = None
    ) -> None:
        if current_time is None:
            current_time = datetime.now().timestamp()
        with self._lock:
            usages = self._card_id_uses.get(card_id, [])
            usage = CardUsage(time=current_time, is_reported=is_reported)
            usages.append(usage)
            self._card_id_uses[card_id] = usages

    def set_difficulty(self, difficulty: Difficulty) -> None:
        with self._lock:
            self._difficulty = difficulty

    def set_modes(self, modes: list[Mode]) -> None:
        with self._lock:
            self._modes = modes
            self._known_unit_modes = 0
            self._mature_unit_modes = 0
            for state in self._rating_states.values():
                for mode in self._modes:
                    if state.is_known(mode):
                        self._known_unit_modes += 1
                    if state.is_mature(mode):
                        self._mature_unit_modes += 1

    def set_assume_known(self, difficulty: Difficulty | None) -> None:
        with self._lock:
            self._assume_known = difficulty

    def stats(self, current_time: float | None = None) -> dict[str, int]:
        if current_time is None:
            current_time = datetime.now().timestamp()
        waiting = 0
        for unit in self._units_with_cards:
            state = self._rating_states.get(unit.id())
            is_skipped = (
                self._assume_known is not None
                and unit.difficulty() <= self._assume_known
            )
            if state is None:
                if not is_skipped:
                    break
                continue
            if state.is_waiting(self._modes, current_time):
                waiting += 1
            if not is_skipped and state.can_be_introduced(self._modes, current_time):
                break
        return {
            "waiting": waiting,
            "known": self._known_unit_modes // len(self._modes),
            "mature": self._mature_unit_modes // len(self._modes),
        }

    def save(self, filename: Path | str) -> None:
        with self._lock:
            data = {
                "target_language": self._target_language.code_name,
                "native_language": self._native_language.code_name,
                "ratings": {
                    key: list(rating.model_dump() for rating in state.ratings())
                    for key, state in self._rating_states.items()
                },
                "card_id_uses": {
                    key: list(usage.model_dump() for usage in usages)
                    for key, usages in self._card_id_uses.items()
                },
                "difficulty": str(self._difficulty),
                "modes": [str(m) for m in self._modes],
            }
            if self._assume_known is not None:
                data["assume_known"] = str(self._assume_known)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, filename: Path | str) -> Self:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        target_language = LANGUAGES[data["target_language"]]
        native_language = LANGUAGES[data["native_language"]]
        card_index = CardIndex.load(target_language, native_language)
        deck = cls(target_language, native_language, card_index)
        for unit_id, ratings_data in data["ratings"].items():
            ratings = list(Rating.model_validate(r) for r in ratings_data)
            rating_state = RatingState(ratings)
            deck._rating_states[unit_id] = rating_state
        for card_id, usage_data in data["card_id_uses"].items():
            usages = list(CardUsage.model_validate(u) for u in usage_data)
            deck._card_id_uses[card_id] = usages
        deck._difficulty = Difficulty(data["difficulty"])
        deck.set_modes([Mode(m) for m in data["modes"]])
        assume_known = data.get("assume_known")
        if assume_known is not None:
            deck._assume_known = Difficulty(assume_known)
        return deck
