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
"""

from collections import defaultdict
from datetime import datetime
from enum import StrEnum
import numpy as np
import pydantic

BLOCK_INTERVAL = 60 * 60 * 20
INTERVAL_DECAY = 0.5
INTERVAL_FACTOR = 0.8
ALL_GREEN_MINIMUM = 14 * 24 * 60 * 60


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


# Ignores yellow so far
def _extract_good_interval(
    history: list[Rating], mode: Mode
) -> tuple[float | None, float]:
    first_good = None
    last_good = None
    good_block = -1e5
    good_interval_length = 1.0
    has_red = False
    has_green = False
    for rating in history:
        if rating.mode == mode:
            # We treat yellow as red for now.
            if rating.score in [1, 2]:
                has_red = True
                good_interval_length *= INTERVAL_DECAY
                first_good = None
                last_good = None
            elif rating.score == 3 and rating.time > good_block:
                has_green = True
                last_good = rating.time
                if first_good is None:
                    first_good = rating.time
                else:
                    good_interval_length = max(
                        good_interval_length, rating.time - first_good
                    )

        good_block = rating.time + BLOCK_INTERVAL
    if has_green and not has_red:
        good_interval_length = max(good_interval_length, ALL_GREEN_MINIMUM)
    return last_good, good_interval_length


def needs_introduction(history: list[Rating], modes: list[Mode]) -> Mode | None:
    if not modes:
        return None
    if not history:
        return modes[0]
    # Perfect start detection
    greens = defaultdict(int)
    first_score = defaultdict(int)
    last_time = history[0].time - 2.0 * BLOCK_INTERVAL
    for rating in history:
        if rating.score == 3:
            greens[rating.mode] += 1
        is_blocked = rating.time < last_time + BLOCK_INTERVAL
        last_time = rating.time
        if first_score[rating.mode] > 0:
            continue
        match rating.score:
            case 0:
                pass
            case 1:
                first_score[rating.mode] = rating.score
            case 2:
                first_score[rating.mode] = rating.score
            case 3:
                if not is_blocked:
                    first_score[rating.mode] = rating.score
            case _:
                assert False, "Unknown score"

    MIN_GREENS = 2
    if any(s == 3 for s in first_score.values()) and all(
        s in [0, 3] for s in first_score.values()
    ):
        return None
    for mode in modes:
        if greens[mode] < MIN_GREENS and first_score[mode] != 3:
            return mode
    return None


def compute_urgency(
    history: list[Rating],
    mode: Mode,
    current_time: float,
) -> float:
    # Default value for new units
    if not history or all([r.mode != mode or r.score == 0 for r in history]):
        return 0.0
    # High priority when last rated feedback was failure
    last_non_zero = next(
        r for r in reversed(history) if r.mode == mode and r.score != 0
    )
    if last_non_zero.score in [1, 2]:
        return 1.0
    # Low priority if card is in block
    if current_time < history[-1].time + BLOCK_INTERVAL:
        return -1.0
    last_good, good_interval_length = _extract_good_interval(history, mode)
    if last_good is None:
        return 1.0
    # Return sigmoid scaled with the forgetting interval length centered at target day
    target_interval = good_interval_length * INTERVAL_FACTOR
    target = last_good + target_interval
    deviation = (current_time - target) / target_interval
    return 1.0 / (1.0 + np.exp(-deviation)) - 0.5
