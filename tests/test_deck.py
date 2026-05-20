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

from bespoke import Deck
from bespoke import Difficulty
from bespoke import Mode
from bespoke import languages
from tests import fakes


class TestDeck(unittest.TestCase):
    def test_draw(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore
        deck.set_modes([Mode.LISTEN, Mode.SPEAK])
        mode, card = deck.draw()
        unit = [u for u in target.units() if u.difficulty() == Difficulty.A1][0]
        self.assertEqual(mode, Mode.LISTEN)
        self.assertEqual(card.sentence, unit.name())

    def test_rate(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore
        deck.set_modes([Mode.LISTEN, Mode.SPEAK])
        mode, card = deck.draw()
        unit_a1_0 = [u for u in target.units() if u.difficulty() == Difficulty.A1][0]
        self.assertEqual(card.unit_ids(), [unit_a1_0.id()])
        deck.rate(unit_a1_0, mode, 3)
        _mode, card = deck.draw()
        unit_a1_1 = [u for u in target.units() if u.difficulty() == Difficulty.A1][1]
        self.assertEqual(card.unit_ids(), [unit_a1_1.id()])

    def test_assume_known(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore
        deck.set_assume_known(Difficulty.A2)
        _mode, card = deck.draw()
        unit = [u for u in target.units() if u.difficulty() == Difficulty.B1][0]
        self.assertEqual(card.sentence, unit.name())


if __name__ == "__main__":
    unittest.main()
