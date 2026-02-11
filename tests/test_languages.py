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

from bespoke import Difficulty
from bespoke import languages


class TestLanguageData(unittest.TestCase):
    def test_vocabulary(self) -> None:
        language = languages.LANGUAGES["japanese"]
        for d1 in Difficulty:
            for d2 in Difficulty:
                if d1 == d2:
                    continue
                vocabulary1 = language.vocabulary(d1)
                vocabulary2 = language.vocabulary(d2)
                self.assertTrue(set(vocabulary1).isdisjoint(vocabulary2))
                self.assertTrue(set(vocabulary1).isdisjoint(vocabulary2))

    def test_full_vocabulary(self) -> None:
        language = languages.LANGUAGES["japanese"]
        vocabulary_a1 = language.vocabulary(Difficulty.A1)
        full_vocabulary = language.full_vocabulary()
        self.assertEqual(vocabulary_a1, full_vocabulary[: len(vocabulary_a1)])

    def test_grammar(self) -> None:
        language = languages.LANGUAGES["japanese"]
        for d1 in Difficulty:
            for d2 in Difficulty:
                if d1 == d2:
                    continue
                grammar1 = language.grammar(d1)
                grammar2 = language.grammar(d2)
                self.assertTrue(set(grammar1).isdisjoint(grammar2))


if __name__ == "__main__":
    unittest.main()
