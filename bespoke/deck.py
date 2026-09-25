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
- The selected modes for a new card are introduced in random order.
- Cards you know on the first attempt start with a long interval.
- Different mode, any score, is treated as blue.
- Blue (0): Makes a following green act like a blue for some time.
- Yellow (2): Treated like red
- Green (3): Knowledge level is the longest interval not interrupted by red.
- Red (1): Stops and shortens green intervals, high urgency if last.
"""

import csv
import json
import math
import random
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Self

import pydantic

from bespoke.card import Card, CardIndex
from bespoke.languages import LANGUAGES, Language
from bespoke.unit import DictionaryUnit, Difficulty, Unit
from bespoke.urgency import Mode, Rating, RatingState

TRANSLATIONS_FILE_PATTERN = "translations_{target}_{native}.csv"
SOON_URGENT_INTERVAL = 10.0 * 60
IMMEDIATE_URGENCY = 0.5
SOON_URGENT_THRESHOLD = 10
MIN_DRAW_PROBABILITY = 0.05
MIN_DRAW_PROBABILITY_SELECTED = 0.2
# Card scoring constants
REPORT_PENALTY = 1000000.0
CARD_USAGE_FACTOR = 1000.0
CARD_USAGE_DECAY = 0.1
BLOCKED_UNIT_PENALTY = 500.0
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
        self._blocked_units: list[str] = []
        self._blocked_units_set: set[str] = set()
        self._difficulty = Difficulty.A1
        self._modes = list(Mode)

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

    def block_unit(self, unit_id: str) -> None:
        with self._lock:
            if unit_id in self._blocked_units_set:
                self._blocked_units.remove(unit_id)
            self._blocked_units.append(unit_id)
            self._blocked_units_set.add(unit_id)

    def unblock_unit(self, unit_id: str) -> None:
        with self._lock:
            if unit_id in self._blocked_units_set:
                self._blocked_units.remove(unit_id)
                self._blocked_units_set.remove(unit_id)

    def is_blocked(self, unit_id: str) -> bool:
        return unit_id in self._blocked_units_set

    def blocked_units(self) -> list[str]:
        with self._lock:
            return list(reversed(self._blocked_units))

    def _choose_task(self, current_time: float) -> tuple[Mode, str]:
        default_state = RatingState([])

        # Choose an urgent unit to learn
        max_urgency = -1e5
        max_mode = None
        max_unit_id = None
        soon_urgent = 0
        soon_time = current_time + SOON_URGENT_INTERVAL
        available_difficulties = []
        for unit in self._units_with_cards:
            if unit.difficulty() > self._difficulty:
                # Assumes units are sorted by difficulty
                break
            if unit.id() in self._blocked_units_set:
                continue
            state = self._rating_states.get(unit.id(), default_state)
            for mode in self._modes:
                if not state.is_introduced(mode):
                    if unit.difficulty() not in available_difficulties:
                        available_difficulties.append(unit.difficulty())
                    continue
                if state.urgency(mode, soon_time) > 0.0:
                    soon_urgent += 1
                    # Assumes monotonically increasing urgency
                    urgency = state.urgency(mode, current_time)
                    if urgency > max_urgency:
                        max_urgency = urgency
                        max_mode = mode
                        max_unit_id = unit.id()
        if max_urgency > 0.0:
            probability = max(
                max_urgency / IMMEDIATE_URGENCY,
                soon_urgent / SOON_URGENT_THRESHOLD,
            )
            if random.random() < probability:
                assert max_mode is not None
                assert max_unit_id is not None
                return max_mode, max_unit_id

        # If nothing needs to be introduced, new difficulty unlocked
        if not available_difficulties:
            self._difficulty = self._difficulty.saturating_increase()
            if self._difficulty not in available_difficulties:
                available_difficulties.append(self._difficulty)

        # Randomly choose a difficulty for introduction
        first_greens = {d: 0 for d in available_difficulties}
        first_reds = {d: 0 for d in available_difficulties}
        for unit in self._units_with_cards:
            if unit.difficulty() > self._difficulty:
                # Assumes units are sorted by difficulty
                break
            if unit.id() in self._blocked_units_set:
                continue
            if unit.difficulty() not in available_difficulties:
                continue
            state = self._rating_states.get(unit.id(), default_state)
            match state.first_score():
                case 1 | 2:
                    first_reds[unit.difficulty()] += 1
                case 3:
                    first_greens[unit.difficulty()] += 1
        probabilities = {}
        for difficulty in available_difficulties:
            greens = first_greens[difficulty]
            reds = first_reds[difficulty]
            if greens + reds == 0:
                ratio = 0.0
            else:
                ratio = greens / (greens + reds)
            if difficulty == self._difficulty:
                min_probability = MIN_DRAW_PROBABILITY_SELECTED
            else:
                min_probability = MIN_DRAW_PROBABILITY
            probabilities[difficulty] = 1.0 - ratio + ratio * min_probability
        keys = list(probabilities.keys())
        weights = list(probabilities.values())
        chosen = random.choices(keys, weights=weights, k=1)[0]

        # Select the first half-introduced unit, or the first fresh one
        chosen_mode = None
        chosen_unit_id = None
        for unit in self._units_with_cards:
            # Assumes units are sorted by difficulty, falls back to harder unit
            if unit.difficulty() < chosen:
                continue
            if unit.id() in self._blocked_units_set:
                continue
            state = self._rating_states.get(unit.id(), default_state)
            candidate_modes = [
                mode
                for mode in self._modes
                if state.can_be_introduced(mode, current_time)
            ]
            has_introduced_mode = any(state.is_introduced(mode) for mode in self._modes)
            if has_introduced_mode and candidate_modes:
                return random.choice(candidate_modes), unit.id()
            if candidate_modes and chosen_unit_id is None:
                chosen_mode = random.choice(candidate_modes)
                chosen_unit_id = unit.id()
        if chosen_mode is not None:
            assert chosen_unit_id is not None
            return chosen_mode, chosen_unit_id

        if max_mode is not None:
            assert max_unit_id is not None
            return max_mode, max_unit_id
        return random.choice(self._modes), random.choice(self._units_with_cards).id()

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
            if unit_id in self._blocked_units_set:
                score -= BLOCKED_UNIT_PENALTY
                continue
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
                score -= DIFFICULTY_PENALTY
        return score

    def draw(self, current_time: float | None = None) -> tuple[Mode, Card]:
        if current_time is None:
            current_time = datetime.now(UTC).timestamp()
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
            current_time = datetime.now(UTC).timestamp()
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
            current_time = datetime.now(UTC).timestamp()
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

    def stats(self, current_time: float | None = None) -> dict[str, int]:
        if current_time is None:
            current_time = datetime.now(UTC).timestamp()
        waiting = 0
        for unit in self._units_with_cards:
            if unit.difficulty() > self._difficulty:
                # Assumes units are sorted by difficulty
                break
            state = self._rating_states.get(unit.id())
            if state is None:
                continue
            if state.is_waiting(self._modes, current_time):
                waiting += 1
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
                    key: [rating.model_dump() for rating in state.ratings()]
                    for key, state in self._rating_states.items()
                },
                "card_id_uses": {
                    key: [usage.model_dump() for usage in usages]
                    for key, usages in self._card_id_uses.items()
                },
                "difficulty": str(self._difficulty),
                "modes": [str(m) for m in self._modes],
                "blocked_units": list(self._blocked_units),
            }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @classmethod
    def load(
        cls,
        filename: Path | str,
        card_index: CardIndex | None = None,
    ) -> Self:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        target_language = LANGUAGES[data["target_language"]]
        native_language = LANGUAGES[data["native_language"]]
        if card_index is None:
            card_index = CardIndex.load(target_language, native_language)
        deck = cls(target_language, native_language, card_index)
        for unit_id, ratings_data in data["ratings"].items():
            ratings = [Rating.model_validate(r) for r in ratings_data]
            rating_state = RatingState(ratings)
            deck._rating_states[unit_id] = rating_state
        for card_id, usage_data in data["card_id_uses"].items():
            usages = [CardUsage.model_validate(u) for u in usage_data]
            deck._card_id_uses[card_id] = usages
        deck._difficulty = Difficulty(data["difficulty"])
        deck.set_modes([Mode(m) for m in data["modes"]])
        deck._blocked_units = list(data.get("blocked_units", []))
        deck._blocked_units_set = set(deck._blocked_units)
        return deck
