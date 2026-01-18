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

import datetime
import json
import numpy as np
import pydantic
import random
from typing import Self

from bespoke.card import Card
from bespoke.card import CardIndex
from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import LANGUAGES
from bespoke.urgency import Mode
from bespoke.urgency import Rating
from bespoke.urgency import compute_urgency
from bespoke.urgency import needs_introduction

MINIMUM_TOUCH_RATIO = 0.5
TOUCH_MARGIN = 10
# Card scoring constants
REPORT_PENALTY = 1000000.0
CARD_USAGE_FACTOR = 100.0
CARD_USAGE_DECAY = 0.01
NONTARGET_PENALTY = 20000.0
UNTOUCHED_PENALTY = 10000.0
INTRODUCTION_BONUS = 1.0
URGENCY_BONUS = 2.0
DIFFICULTY_MATCH_BONUS = 0.1
DIFFICULTY_PENALTY = 0.1


def _is_untouched(history: list[Rating]) -> bool:
    return all(rating.score == 0 for rating in history)


class UrgencyState(pydantic.BaseModel):
    """Helper class to store temporary info about urgencies."""

    is_touched: bool
    needs_introduction: bool
    is_target: bool
    urgency: float
    mode: Mode


class CardUsage(pydantic.BaseModel):
    time: float
    is_reported: bool = False

    model_config = pydantic.ConfigDict(frozen=True)


class Deck:
    def __init__(
        self,
        target_language: Language,
        native_language: Language,
    ) -> None:
        self._target_language = target_language
        self._native_language = native_language
        self._card_index = CardIndex.load(target_language, native_language)
        self._ratings: dict[str, list[Rating]] = {}
        self._card_id_uses: dict[str, list[CardUsage]] = {}
        self._difficulty = Difficulty.A1
        self._modes = list(Mode)
        self._full_vocabulary = target_language.full_vocabulary()
        self._difficulty_map = {}
        for difficulty in Difficulty:
            for word in self._target_language.vocabulary(difficulty):
                self._difficulty_map[word] = difficulty

    def _compute_urgencies(self, current_time: float) -> dict[UrgencyState]:
        urgency_states = {}
        touched = 0
        has_reached_threshold = False
        for i, unit in enumerate(self._full_vocabulary):
            if (touched + TOUCH_MARGIN) / (i + TOUCH_MARGIN) < MINIMUM_TOUCH_RATIO:
                has_reached_threshold = True
            history = self._ratings.get(unit)
            if history is None or _is_untouched(history):
                urgency_states[unit] = UrgencyState(
                    is_touched=False,
                    needs_introduction=False,
                    is_target=not has_reached_threshold,
                    urgency=0.0,
                    mode=self._modes[0],
                )
                continue
            touched += 1
            highest_urgency, mode = max(
                (compute_urgency(history, m, current_time), m) for m in self._modes
            )
            introduction_mode = needs_introduction(history, self._modes)
            if introduction_mode is not None:
                mode = introduction_mode
            urgency_states[unit] = UrgencyState(
                is_touched=True,
                needs_introduction=introduction_mode is not None,
                is_target=not has_reached_threshold,
                urgency=highest_urgency,
                mode=mode,
            )
        return urgency_states

    def _choose_task(
        self,
        urgency_states: dict[UrgencyState],
    ) -> tuple[Mode, str]:
        target_states = []
        for unit in self._full_vocabulary:
            if not self._card_index.size(unit):
                continue
            state = urgency_states[unit]
            if state.is_target:
                target_states.append((unit, state))
            else:
                # Optimization, from here, nothing is a target.
                break

        # Step 1: Return the first urgent unit.
        for unit, state in target_states:
            if state.urgency > 0.0:
                return state.mode, unit

        # Step 2: Touched and needs introduction.
        for unit, state in target_states:
            if state.needs_introduction:
                return state.mode, unit

        # Step 3: Untouched, but a target.
        for unit, state in target_states:
            if not state.is_touched:
                return state.mode, unit

        # Step 4: Highest urgency.
        if not target_states:
            raise ValueError(f"No units found")
        unit, state = max(target_states, key=lambda s: s[1].urgency)
        return state.mode, unit

    def _score_card(
        self,
        card: Card,
        urgency_states: dict[UrgencyState],
        current_time: float,
    ) -> float:
        score = 0
        timestamps = []
        for usage in self._card_id_uses.get(card.id, []):
            timestamps.append(usage.time)
            if usage.is_reported:
                score -= REPORT_PENALTY
        days = (current_time - np.array(timestamps)) / 60.0 / 60.0 / 24.0
        score -= CARD_USAGE_FACTOR * np.sum(np.exp(-CARD_USAGE_DECAY * days)).item()
        for unit in card.units:
            state = urgency_states[unit]
            if not state.is_target:
                score -= NONTARGET_PENALTY
            if not state.is_touched:
                score -= UNTOUCHED_PENALTY
            if state.needs_introduction:
                score += INTRODUCTION_BONUS
            if state.urgency > 0.0:
                score += URGENCY_BONUS
            unit_difficulty = self._difficulty_map.get(unit, Difficulty.A1)
            if unit_difficulty == self._difficulty:
                score += DIFFICULTY_MATCH_BONUS
            elif unit_difficulty > self._difficulty:
                score += DIFFICULTY_PENALTY
        return score

    def draw(self) -> tuple[Mode, Card]:
        current_time = datetime.datetime.now().timestamp()
        urgency_states = self._compute_urgencies(current_time)
        mode, unit = self._choose_task(urgency_states)
        cards = self._card_index.cards(unit)
        if not cards:
            print(f"No cards found for unit '{unit}', showing any card.")
            self.rate(unit, mode, 0)
            for unit in self._full_vocabulary:
                cards = self._card_index.cards(unit)
                if cards:
                    break
        random.shuffle(cards)
        scored_cards = [
            (self._score_card(card, urgency_states, current_time), card)
            for card in cards
        ]
        _, best_card = max(scored_cards, key=lambda pair: pair[0])
        return mode, best_card

    def rate(self, unit: str, mode: Mode, score: int) -> None:
        time = datetime.datetime.now().timestamp()
        rating = Rating(mode=mode, time=time, score=score)
        ratings = self._ratings.get(unit, [])
        ratings.append(rating)
        self._ratings[unit] = ratings

    def log_usage(self, card_id: str, is_reported: bool = False) -> None:
        usages = self._card_id_uses.get(card_id, [])
        time = datetime.datetime.now().timestamp()
        usage = CardUsage(time=time, is_reported=is_reported)
        usages.append(usage)
        self._card_id_uses[card_id] = usages

    def set_difficulty(self, difficulty: Difficulty) -> None:
        self._difficulty = difficulty

    def set_modes(self, modes: list[Mode]) -> None:
        self._modes = modes

    def log_feedback(self, modes: list[Mode]) -> None:
        self._modes = modes

    def stats(self) -> dict[str, int]:
        current_time = datetime.datetime.now().timestamp()
        urgency_states = self._compute_urgencies(current_time)
        waiting = 0
        satisfied = 0
        for state in urgency_states.values():
            if state.is_target and state.urgency > 0.0:
                waiting += 1
            if state.is_touched and state.urgency <= 0.0:
                satisfied += 1
        return {
            "waiting": waiting,
            "satisfied": satisfied,
        }

    def save(self, filename: str) -> None:
        data = {
            "target_language": self._target_language.code_name,
            "native_language": self._native_language.code_name,
            "ratings": {
                key: list(rating.model_dump() for rating in ratings)
                for key, ratings in self._ratings.items()
            },
            "card_id_uses": {
                key: list(usage.model_dump() for usage in usages)
                for key, usages in self._card_id_uses.items()
            },
            "difficulty": str(self._difficulty),
            "modes": [str(m) for m in self._modes],
        }
        with open(filename, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, filename: str) -> Self:
        with open(filename, "r") as f:
            data = json.load(f)
        deck = cls(
            LANGUAGES[data["target_language"]],
            LANGUAGES[data["native_language"]],
        )
        for key, ratings_data in data["ratings"].items():
            ratings = list(Rating.model_validate(r) for r in ratings_data)
            deck._ratings[key] = ratings
        for key, usage_data in data["card_id_uses"].items():
            usages = list(CardUsage.model_validate(u) for u in usage_data)
            deck._card_id_uses[key] = usages
        deck._difficulty = Difficulty(data["difficulty"])
        deck._modes = [Mode(m) for m in data["modes"]]
        return deck
