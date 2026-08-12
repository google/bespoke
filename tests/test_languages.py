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

from bespoke import DictionaryUnit
from bespoke import Difficulty
from bespoke import Language
from bespoke import languages


class TestLanguageData(unittest.TestCase):
    def test_units(self) -> None:
        language = languages.LANGUAGES["japanese"]
        units = language.units()
        self.assertNotEqual(units[0].name(), units[1].name())
        self.assertEqual(bool(units[0].definition()), bool(units[1].definition()))
        self.assertEqual(units[0].difficulty(), Difficulty.A1)

    def test_load_grammar(self) -> None:
        grammar = languages.load_grammar("japanese")
        for d1 in Difficulty:
            for d2 in Difficulty:
                if d1 == d2:
                    continue
                grammar1 = grammar[d1]
                grammar2 = grammar[d2]
                self.assertTrue(set(grammar1).isdisjoint(grammar2))

    def test_get_by_id_and_get_by_name(self) -> None:
        language = languages.LANGUAGES["japanese"]
        units = language.units()
        first_unit = units[0]
        self.assertEqual(language.get_by_id(first_unit.id()), first_unit)
        by_name = language.get_by_name(first_unit.name())
        self.assertIn(first_unit, by_name)

    def test_set_units(self) -> None:
        language = Language(
            name="Test Language",
            writing_system="Test",
            phonetic_system=None,
            code_name="test_lang",
        )
        unit = DictionaryUnit(
            name="injected", definition="test def", difficulty=Difficulty.A1
        )
        language.set_units([unit])
        self.assertTrue(language.has_data())
        self.assertEqual(len(language.units()), 1)
        self.assertEqual(language.units()[0].name(), "injected")
        self.assertEqual(language.get_by_id("injected - test def"), unit)


if __name__ == "__main__":
    unittest.main()
