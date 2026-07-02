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

"""Helper functions to determine urgency of a unit.

We considered a Maybe / Yellow / 2 rating at first.
We decided against it for simplicity.
It shouldn't appear, and is treated as No / Red / 1 if it does.
"""

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
import math
import pydantic

MINUTE = 60.0
HOUR = MINUTE * 60.0
DAY = HOUR * 24.0

BLOCK_INTERVAL = HOUR * 20
RED_BLOCK_INTERVAL = MINUTE * 10
MINIMUM_BLOCK_INTERVAL = MINUTE * 1
BLOCK_SCALE_INTERVAL = DAY * 1
INTERVAL_DECAY = 0.5
INTERVAL_FACTOR = 1.8
# Needs to be tuned with block constants to make sense
MODE_INITIAL_GREEN_INTERVAL = HOUR * 1
FULL_INITIAL_GREEN_INTERVAL = DAY * 14
# For stats, we want:
# MODE_INITIAL_GREEN_INTERVAL < KNOWN_AGE < FULL_INITIAL_GREEN_INTERVAL < MATURE_AGE
WAITING_PROJECTION = RED_BLOCK_INTERVAL
KNOWN_AGE = DAY * 1
MATURE_AGE = DAY * 21


class Mode(StrEnum):
    LISTEN = "listen"
    SPEAK = "speak"
    READ = "read"
    WRITE = "write"


class Rating(pydantic.BaseModel):
    mode: Mode
    time: float
    score: int

    model_config = pydantic.ConfigDict(frozen=True)

    def __str__(self) -> str:
        iso_time = datetime.fromtimestamp(self.time).isoformat()
        return f"{iso_time}: {str(self.mode)} -> {self.score}"


class RatingState:
    """Class that estimates learning progress from ratings."""

    def __init__(self, ratings: list[Rating]) -> None:
        self._ratings: list[Rating] = []
        self._last_red: dict[Mode, float] = {}
        self._green_start: dict[Mode, float] = {}
        self._green_end: dict[Mode, float] = {}
        self._green_streak: dict[Mode, float] = {}
        self._block_end = -1e5
        self._is_touched = False
        for rating in ratings:
            self.add(rating)

    def add(self, rating: Rating) -> None:
        if self._ratings and self._ratings[-1].time > rating.time:
            print("Warning: Rejecting rating out of order")
            return
        self._ratings.append(rating)
        match rating.score:
            case 0:
                base_block_interval = BLOCK_INTERVAL
            case 1 | 2:
                self._last_red[rating.mode] = rating.time
                self._green_start.pop(rating.mode, None)
                self._green_end.pop(rating.mode, None)
                green_streak = self._green_streak.get(rating.mode)
                if green_streak is not None:
                    self._green_streak[rating.mode] = green_streak * INTERVAL_DECAY
                base_block_interval = RED_BLOCK_INTERVAL
                self._is_touched = True
            case 3:
                if rating.time > self._block_end:
                    last_red_time = self._last_red.get(rating.mode)
                    if last_red_time is not None:
                        streak = rating.time - last_red_time
                    elif self._last_red:
                        streak = MODE_INITIAL_GREEN_INTERVAL
                    else:
                        streak = FULL_INITIAL_GREEN_INTERVAL
                    green_start = self._green_start.get(rating.mode)
                    if green_start is None:
                        self._green_start[rating.mode] = rating.time
                    else:
                        streak = max(streak, rating.time - green_start)
                    last_streak = self._green_streak.get(rating.mode, 0.0)
                    self._green_end[rating.mode] = rating.time
                    self._green_streak[rating.mode] = max(last_streak, streak)
                base_block_interval = BLOCK_INTERVAL
                self._is_touched = True
            case _:
                base_block_interval = 0.0
                print("Warning: Found unexpected rating score")
        max_green_interval = max(self._green_streak.values(), default=1.0)
        if max_green_interval <= 0.0:
            print("Warning: Negative green streak")
            max_green_interval = 1.0
        block_scale = 1.0 - math.exp(-max_green_interval / BLOCK_SCALE_INTERVAL)
        block_interval = base_block_interval * block_scale
        block_interval = max(block_interval, MINIMUM_BLOCK_INTERVAL)
        self._block_end = max(self._block_end, rating.time + block_interval)

    def ratings(self) -> list[Rating]:
        return list(self._ratings)

    def urgency(self, mode: Mode, current_time: float) -> float:
        if current_time < self._block_end:
            # Blocked
            return -1.0
        green_streak = self._green_streak.get(mode)
        if green_streak is None:
            # Not introduced, meaning no green ever
            return 0.0
        green_end = self._green_end.get(mode)
        if green_end is None:
            # Last was red
            return 1.0
        target_interval = green_streak * INTERVAL_FACTOR
        target = green_end + target_interval
        deviation = (current_time - target) / target_interval
        # tanh centered around target day
        return math.tanh(deviation)

    def is_touched(self) -> bool:
        return self._is_touched

    def is_introduced(self, mode: Mode) -> bool:
        return mode in self._green_streak

    def is_waiting(self, modes: Iterable[Mode], current_time: float) -> bool:
        projected_time = current_time + WAITING_PROJECTION
        return any(self.urgency(mode, projected_time) > 0.0 for mode in modes)

    def is_known(self, mode: Mode) -> bool:
        return self._green_streak.get(mode, 0.0) > KNOWN_AGE

    def is_mature(self, mode: Mode) -> bool:
        return self._green_streak.get(mode, 0.0) > MATURE_AGE
