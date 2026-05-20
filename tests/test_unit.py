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

from bespoke import WordUnit


class TestUnit(unittest.TestCase):
    def test_word_unit(self) -> None:
        unit = WordUnit("test", difficulty=Difficulty.A1)
        self.assertEqual(unit.id(), "test")
        self.assertEqual(unit.name(), "test")
        self.assertEqual(unit.definition(), "test")
        self.assertEqual(unit.difficulty(), Difficulty.A1)
        self.assertEqual(str(unit), "test")

    def test_dictionary_unit(self) -> None:
        unit = DictionaryUnit(
            name="test_name",
            definition="test_def",
            difficulty=Difficulty.A1,
        )
        self.assertEqual(unit.id(), "test_name - test_def")
        self.assertEqual(unit.name(), "test_name")
        self.assertEqual(unit.definition(), "test_def")
        self.assertEqual(unit.difficulty(), Difficulty.A1)
        self.assertEqual(str(unit), "test_name - test_def")


if __name__ == "__main__":
    unittest.main()
