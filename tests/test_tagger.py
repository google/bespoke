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
from bespoke import Unit
from bespoke import WordUnit
from bespoke import UnitTag
from bespoke import UnitTags
from bespoke import tagger
from tests import fakes


class TestWordTagger(unittest.IsolatedAsyncioTestCase):
    async def test_word_tagger(self) -> None:
        language = fakes.fake_language()

        class FakeWordLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self, sentence: str, language, hint: list[Unit]
            ) -> UnitTags:
                return [UnitTag(occurance="大学生", unit_id="大学生")]

        llm_client = FakeWordLlmClient()
        sentence = "大学生です。"
        hint: list[Unit] = [
            WordUnit("大学生", Difficulty.A1),
            WordUnit("学生", Difficulty.A1),
        ]
        full_vocabulary = ["大学生", "学生"]

        fake_units: list[Unit] = [WordUnit(w, Difficulty.A1) for w in full_vocabulary]
        language._units = fake_units
        language._units_by_id = {u.id(): u for u in fake_units}
        language._units_by_name = {u.name(): [u] for u in fake_units}
        language._initialized = True

        t = tagger.WordTagger(sentence, hint, language)
        self.assertFalse(t.done())

        await t.progress(llm_client)
        self.assertFalse(t.done())
        await t.progress(llm_client)
        self.assertTrue(t.done())

        result = t.tags()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "大学生")
        self.assertEqual(result[0].unit_id, "大学生")

    async def test_long_then_short(self) -> None:
        language = fakes.fake_language()

        class FakeWordLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self, sentence: str, language, hint: list[Unit]
            ) -> UnitTags:
                return [
                    UnitTag(occurance="大学生", unit_id="大学生"),
                    UnitTag(occurance="学生", unit_id="学生"),
                ]

        llm_client = FakeWordLlmClient()
        sentence = "大学生です。"
        hint: list[Unit] = []
        full_vocabulary = ["大学生", "学生"]

        fake_units: list[Unit] = [WordUnit(w, Difficulty.A1) for w in full_vocabulary]
        language._units = fake_units
        language._units_by_id = {u.id(): u for u in fake_units}
        language._units_by_name = {u.name(): [u] for u in fake_units}
        language._initialized = True

        t = tagger.WordTagger(sentence, hint, language)
        await t.progress(llm_client)

        result = t.tags()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "大学生")
        occurrences = [tag.occurance for tag in result]
        self.assertNotIn("学生", occurrences)


class TestDictionaryTagger(unittest.IsolatedAsyncioTestCase):
    async def test_dictionary_tagger(self) -> None:
        language = fakes.fake_language()
        language.name = "Traditional Chinese"

        # Fake dictionary data
        dictionary_data = {
            "學生": [{"definitions": [{"def": "在學校學習的人。"}]}],
            "大學生": [{"definitions": [{"def": "在大學學習的人。"}]}],
        }

        class FakeDisambiguatedLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self, sentence: str, language, hint: list[Unit]
            ) -> UnitTags:
                return [
                    UnitTag(occurance="大學生", unit_id="大學生 - 在大學學習的人。")
                ]

        llm_client = FakeDisambiguatedLlmClient()
        sentence = "我是大學生。"

        fake_units: list[Unit] = []
        for word, entries in dictionary_data.items():
            for entry in entries:
                for d in entry.get("definitions", []):
                    fake_units.append(
                        DictionaryUnit(
                            name=word, definition=d["def"], difficulty=Difficulty.A1
                        )
                    )
        language._units = fake_units
        language._units_by_id = {u.id(): u for u in fake_units}
        language._units_by_name = {}
        for u in fake_units:
            language._units_by_name.setdefault(u.name(), []).append(u)
        language._initialized = True

        t = tagger.DictionaryTagger(sentence, [], language)
        self.assertFalse(t.done())

        await t.progress(llm_client)
        self.assertTrue(t.done())

        result = t.tags()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "大學生")
        self.assertEqual(result[0].unit_id, "大學生 - 在大學學習的人。")


if __name__ == "__main__":
    unittest.main()
