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

DAY = 24 * 60 * 60


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
        a1_units = [u for u in target.units() if u.difficulty() == Difficulty.A1]
        unit_a1_0 = a1_units[0]
        self.assertEqual(card.unit_ids(), [unit_a1_0.id()])
        deck.rate(unit_a1_0, mode, 3)
        _mode, card = deck.draw()
        unit_a1_1 = a1_units[1]
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

    def test_introduce_first_card(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore
        first_unit = target.units()[0]
        mode, card = deck.draw(current_time=1)
        self.assertEqual(card.unit_tags[0].unit_id, first_unit.id())
        deck.rate(first_unit, mode, 3, current_time=2)
        _mode, card = deck.draw(current_time=3)
        self.assertNotEqual(card.unit_tags[0].unit_id, first_unit.id())

    def test_draw_failed_unit(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore

        units = target.units()[:3]
        _unit1, unit2, _unit3 = units
        for days in [0, 100]:
            for i, mode in enumerate(Mode):
                for unit in units:
                    deck.rate(unit, mode, 3, current_time=DAY * (days + i))

        deck.rate(unit2, Mode.SPEAK, 1, current_time=DAY * 200)
        mode, card = deck.draw(current_time=DAY * 201)
        self.assertEqual(card.unit_tags[0].unit_id, unit2.id())
        self.assertEqual(mode, Mode.SPEAK)

    def test_draw_unblocked_mode(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore

        units = target.units()[:3]
        _unit1, unit2, _unit3 = units
        for days in [0, 100]:
            for i, mode in enumerate(Mode):
                for unit in units:
                    deck.rate(unit, mode, 3, current_time=DAY * (days + i))

        deck.rate(unit2, Mode.LISTEN, 1, current_time=DAY * 200)
        deck.rate(unit2, Mode.SPEAK, 1, current_time=DAY * 200)

        mode, card = deck.draw(current_time=DAY * 201)
        self.assertEqual(card.unit_tags[0].unit_id, unit2.id())
        self.assertIn(mode, [Mode.LISTEN, Mode.SPEAK])

    def test_introduce_new_when_urgent_is_blocked(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore

        units = target.units()[:3]
        _unit1, unit2, unit3 = units
        for days in [0, 100]:
            for i, mode in enumerate(Mode):
                for unit in units[:2]:
                    deck.rate(unit, mode, 3, current_time=DAY * (days + i))

        deck.rate(unit2, Mode.LISTEN, 1, current_time=DAY * 200)
        deck.rate(unit2, Mode.LISTEN, 0, current_time=DAY * 201 - 1)
        mode, card = deck.draw(current_time=DAY * 201)
        self.assertEqual(card.unit_tags[0].unit_id, unit3.id())

    def test_stats(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["english"]
        index = fakes.FakeCardIndex(target, native)
        deck = Deck(target, native, index)  # type: ignore
        deck.set_modes([Mode.LISTEN, Mode.SPEAK])

        units = target.units()[:3]
        unit1, unit2, unit3 = units

        deck.rate(unit1, Mode.LISTEN, 3, current_time=DAY * 0)
        deck.rate(unit1, Mode.SPEAK, 3, current_time=DAY * 1)
        deck.rate(unit1, Mode.LISTEN, 3, current_time=DAY * 100)
        deck.rate(unit1, Mode.SPEAK, 3, current_time=DAY * 101)
        deck.rate(unit2, Mode.LISTEN, 1, current_time=DAY * 0.0)
        deck.rate(unit2, Mode.LISTEN, 3, current_time=DAY * 0.5)
        deck.rate(unit2, Mode.SPEAK, 1, current_time=DAY * 1.0)
        deck.rate(unit2, Mode.SPEAK, 3, current_time=DAY * 1.5)
        deck.rate(unit3, Mode.LISTEN, 1, current_time=DAY * 90)
        deck.rate(unit3, Mode.SPEAK, 1, current_time=DAY * 91)
        deck.rate(unit3, Mode.LISTEN, 3, current_time=DAY * 100)
        deck.rate(unit3, Mode.SPEAK, 3, current_time=DAY * 101)

        stats = deck.stats(current_time=DAY * 102)
        self.assertEqual(stats["waiting"], 1)
        self.assertEqual(stats["known"], 2)
        self.assertEqual(stats["mature"], 1)


if __name__ == "__main__":
    unittest.main()
