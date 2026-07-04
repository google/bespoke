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

import unittest

from bespoke import Mode
from bespoke.urgency import Rating
from bespoke.urgency import RatingState

DAY = 24 * 60 * 60


class TestRatingState(unittest.TestCase):
    def test_positive_urgency(self) -> None:
        state = RatingState([])
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 0, score=1))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 1, score=3))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 2, score=1))
        self.assertEqual(state.urgency(Mode.LISTEN, DAY * 3), 1.0)
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 3 + 1, score=3))
        self.assertGreater(state.urgency(Mode.LISTEN, DAY * 10), 0.0)

    def test_negative_urgency(self) -> None:
        state = RatingState([])
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 0, score=1))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 1, score=3))
        self.assertLess(state.urgency(Mode.LISTEN, DAY * 2), 0.0)

    def test_cannot_block_positive_urgency(self) -> None:
        state = RatingState([])
        state.add(Rating(mode=Mode.WRITE, time=DAY * 0, score=1))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 1, score=3))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 2 - 1, score=0))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 2, score=1))
        self.assertEqual(state.urgency(Mode.WRITE, DAY * 3), 1.0)

    def test_blocked_negative_urgency(self) -> None:
        state = RatingState([])
        state.add(Rating(mode=Mode.WRITE, time=DAY * 0, score=1))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 1, score=3))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 2, score=1))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 3 - 1, score=0))
        state.add(Rating(mode=Mode.WRITE, time=DAY * 3, score=3))
        self.assertGreater(state.urgency(Mode.WRITE, DAY * 4), 0.0)

    def test_green_introduction_urgency(self) -> None:
        state = RatingState([])
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 0, score=3))
        self.assertLess(state.urgency(Mode.LISTEN, DAY * 21), 0.0)
        state.add(Rating(mode=Mode.SPEAK, time=DAY * 1, score=3))
        self.assertLess(state.urgency(Mode.SPEAK, DAY * 21), 0.0)
        state.add(Rating(mode=Mode.SPEAK, time=DAY * 2, score=1))
        state.add(Rating(mode=Mode.READ, time=DAY * 3, score=3))
        self.assertGreater(state.urgency(Mode.READ, DAY * 21), 0.0)
        self.assertLess(state.urgency(Mode.READ, DAY * 3 + 60 * 60), 0.0)

    def test_get_ratings_copy(self) -> None:
        rating1 = Rating(mode=Mode.LISTEN, time=DAY * 0, score=3)
        state = RatingState([rating1])
        rating2 = Rating(mode=Mode.SPEAK, time=DAY * 1, score=0)
        state.add(rating2)
        ratings = state.ratings()
        self.assertEqual(len(ratings), 2)
        self.assertEqual(ratings[0].mode, Mode.LISTEN)
        self.assertEqual(ratings[1].mode, Mode.SPEAK)
        state.add(rating2)
        self.assertEqual(len(ratings), 2)

    def test_is_touched(self) -> None:
        state = RatingState([])
        self.assertFalse(state.is_touched())
        state.add(Rating(mode=Mode.READ, time=DAY * 0, score=0))
        self.assertFalse(state.is_touched())
        state.add(Rating(mode=Mode.READ, time=DAY * 1, score=1))
        self.assertTrue(state.is_touched())
        state.add(Rating(mode=Mode.READ, time=DAY * 2, score=0))
        self.assertTrue(state.is_touched())

    def test_is_introduced(self) -> None:
        state = RatingState([])
        self.assertFalse(state.is_introduced(Mode.LISTEN))
        self.assertFalse(state.is_introduced(Mode.SPEAK))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 0, score=0))
        self.assertFalse(state.is_introduced(Mode.LISTEN))
        self.assertFalse(state.is_introduced(Mode.SPEAK))
        state.add(Rating(mode=Mode.READ, time=DAY * 1, score=3))
        self.assertFalse(state.is_introduced(Mode.LISTEN))
        self.assertFalse(state.is_introduced(Mode.SPEAK))
        state.add(Rating(mode=Mode.SPEAK, time=DAY * 2, score=1))
        self.assertFalse(state.is_introduced(Mode.LISTEN))
        self.assertFalse(state.is_introduced(Mode.SPEAK))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 3, score=3))
        self.assertTrue(state.is_introduced(Mode.LISTEN))
        self.assertFalse(state.is_introduced(Mode.SPEAK))
        state.add(Rating(mode=Mode.SPEAK, time=DAY * 4, score=3))
        self.assertTrue(state.is_introduced(Mode.LISTEN))
        self.assertTrue(state.is_introduced(Mode.SPEAK))

    def test_is_waiting(self) -> None:
        state = RatingState([])
        self.assertFalse(state.is_waiting(Mode, DAY * 0))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 1, score=1))
        self.assertFalse(state.is_waiting(Mode, DAY * 1))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 2, score=3))
        self.assertFalse(state.is_waiting(Mode, DAY * 2))
        self.assertFalse(state.is_waiting(Mode, DAY * 3))
        self.assertTrue(state.is_waiting(Mode, DAY * 10))

    def test_is_waiting_wrong_mode(self) -> None:
        state = RatingState([])
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 1, score=1))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 2, score=3))
        self.assertTrue(state.is_waiting(Mode, DAY * 10))
        self.assertFalse(state.is_waiting([Mode.SPEAK], DAY * 10))

    def test_can_be_introduced(self) -> None:
        state = RatingState([])
        self.assertTrue(state.can_be_introduced(Mode, DAY * 0))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 0, score=0))
        self.assertFalse(state.can_be_introduced(Mode, DAY * 0 + 1))
        self.assertTrue(state.can_be_introduced(Mode, DAY * 2))
        state.add(Rating(mode=Mode.LISTEN, time=DAY * 2, score=3))
        self.assertTrue(state.can_be_introduced(Mode, DAY * 3))
        state.add(Rating(mode=Mode.SPEAK, time=DAY * 3, score=3))
        self.assertTrue(state.can_be_introduced(Mode, DAY * 4))
        self.assertFalse(state.can_be_introduced([Mode.LISTEN, Mode.SPEAK], DAY * 4))

    def test_stats(self) -> None:
        state = RatingState([])
        self.assertFalse(state.is_known(Mode.READ))
        self.assertFalse(state.is_mature(Mode.READ))
        state.add(Rating(mode=Mode.READ, time=DAY * 1, score=3))
        self.assertTrue(state.is_known(Mode.READ))
        self.assertFalse(state.is_mature(Mode.READ))
        state.add(Rating(mode=Mode.READ, time=DAY * 30, score=3))
        self.assertTrue(state.is_known(Mode.READ))
        self.assertTrue(state.is_mature(Mode.READ))
        self.assertFalse(state.is_known(Mode.WRITE))
        self.assertFalse(state.is_mature(Mode.WRITE))


if __name__ == "__main__":
    unittest.main()
