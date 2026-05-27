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
from bespoke import Unit
from bespoke import WordUnit
from bespoke import DictionaryUnit
from bespoke import UnitTag
from bespoke import UnitTags
from bespoke import tagger
from tests import fakes


class TestTaggerHelpers(unittest.TestCase):
    def test_is_punctuation_or_space(self) -> None:
        self.assertTrue(tagger.is_punctuation_or_space(" "))
        self.assertTrue(tagger.is_punctuation_or_space("，"))
        self.assertTrue(tagger.is_punctuation_or_space("."))
        self.assertFalse(tagger.is_punctuation_or_space("A"))
        self.assertFalse(tagger.is_punctuation_or_space("你"))

    def test_is_more_than_punctuation(self) -> None:
        self.assertTrue(tagger.is_more_than_punctuation("A"))
        self.assertTrue(tagger.is_more_than_punctuation("你"))
        self.assertTrue(tagger.is_more_than_punctuation("，你。"))
        self.assertFalse(tagger.is_more_than_punctuation("，。"))
        self.assertFalse(tagger.is_more_than_punctuation("  "))

    def test_strip_punctuation_and_space(self) -> None:
        self.assertEqual(tagger.strip_punctuation_and_space("  abc  "), "abc")
        self.assertEqual(tagger.strip_punctuation_and_space("，abc。"), "abc")
        self.assertEqual(tagger.strip_punctuation_and_space(" ， abc 。"), "abc")
        self.assertEqual(tagger.strip_punctuation_and_space("abc"), "abc")
        self.assertEqual(tagger.strip_punctuation_and_space("  "), "")


class TestCreateTags(unittest.IsolatedAsyncioTestCase):
    async def test_create_tags_basic(self) -> None:
        language = fakes.fake_language()
        language.code_name = "english"

        class FakeLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self,
                sentence: str,
                language,
                hint: list[Unit],
                marked_sentence: str | None = None,
            ) -> UnitTags:
                return [
                    UnitTag(occurance="cat", unit_id="cat"),
                    UnitTag(occurance="mat", unit_id="mat"),
                ]

        llm_client = FakeLlmClient()
        sentence = "The cat sat on the mat."
        units: list[Unit] = [
            WordUnit("cat", Difficulty.A1),
            WordUnit("mat", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        result = await tagger.create_tags(sentence, units, language, llm_client)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].occurance, "cat")
        self.assertEqual(result[1].occurance, "mat")

    async def test_create_tags_german(self) -> None:
        language = fakes.fake_language()
        language.code_name = "german"

        class FakeLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self,
                sentence: str,
                language,
                hint: list[Unit],
                marked_sentence: str | None = None,
            ) -> UnitTags:
                return [
                    UnitTag(occurance="gehe", unit_id="gehen - schrittweises bewegen")
                ]

            async def suggest_names(self, sentence: str, language) -> list[str]:
                return ["gehen"]

        llm_client = FakeLlmClient()
        sentence = "Ich gehe."
        units: list[Unit] = [
            DictionaryUnit("gehen", "schrittweises bewegen", Difficulty.A1)
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        result = await tagger.create_tags(sentence, [], language, llm_client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "gehe")
        self.assertEqual(result[0].unit_id, "gehen - schrittweises bewegen")

    async def test_create_tags_chinese(self) -> None:
        language = fakes.fake_language()
        language.code_name = "simp_chinese"

        class FakeLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self,
                sentence: str,
                language,
                hint: list[Unit],
                marked_sentence: str | None = None,
            ) -> UnitTags:
                return [UnitTag(occurance="大學生", unit_id="大學生")]

        llm_client = FakeLlmClient()
        sentence = "我是大學生。"
        units: list[Unit] = [WordUnit("大學生", Difficulty.A1)]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        result = await tagger.create_tags(sentence, units, language, llm_client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "大學生")

    async def test_create_tags_not_in_dictionary(self) -> None:
        language = fakes.fake_language()
        language.code_name = "english"

        class FakeLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self,
                sentence: str,
                language,
                hint: list[Unit],
                marked_sentence: str | None = None,
            ) -> UnitTags:
                return [
                    UnitTag(occurance="cat", unit_id="cat"),
                    UnitTag(occurance="unknown", unit_id="unknown"),
                ]

        llm_client = FakeLlmClient()
        sentence = "The cat is unknown."
        units: list[Unit] = [WordUnit("cat", Difficulty.A1)]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        result = await tagger.create_tags(sentence, units, language, llm_client)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "cat")

    async def test_create_tags_merge_logic(self) -> None:
        language = fakes.fake_language()
        language.code_name = "english"

        class FakeLlmClient(fakes.FakeLlmClient):
            def __init__(self):
                self.round = 0

            async def tag_sentence(
                self,
                sentence: str,
                language,
                hint: list[Unit],
                marked_sentence: str | None = None,
            ) -> UnitTags:
                self.round += 1
                if self.round == 1:
                    return [UnitTag(occurance="cat", unit_id="cat")]
                else:
                    return [UnitTag(occurance="mat", unit_id="mat")]

            async def suggest_names(self, sentence: str, language) -> list[str]:
                return []

        llm_client = FakeLlmClient()
        sentence = "The cat sat on the mat."
        units: list[Unit] = [
            WordUnit("cat", Difficulty.A1),
            WordUnit("mat", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        result = await tagger.create_tags(sentence, units, language, llm_client)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].occurance, "cat")
        self.assertEqual(result[1].occurance, "mat")


if __name__ == "__main__":
    unittest.main()
