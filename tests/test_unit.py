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

from bespoke.unit import WordUnit, UnitIndex


class TestUnit(unittest.TestCase):
    def test_word_unit(self) -> None:
        unit = WordUnit("test")
        self.assertEqual(unit.id(), "test")
        self.assertEqual(unit.name(), "test")
        self.assertEqual(unit.definition(), "test")
        self.assertEqual(str(unit), "test")

    def test_unit_index(self) -> None:
        index = UnitIndex()
        unit1 = WordUnit("apple")
        unit2 = WordUnit("banana")

        index.add(unit1)
        index.add(unit2)

        self.assertEqual(index.get_by_id("apple"), unit1)
        self.assertEqual(index.get_by_id("banana"), unit2)
        self.assertIsNone(index.get_by_id("cherry"))

        self.assertEqual(index.get_by_name("apple"), [unit1])
        self.assertEqual(index.get_by_name("banana"), [unit2])
        self.assertEqual(index.get_by_name("cherry"), [])


if __name__ == "__main__":
    unittest.main()
