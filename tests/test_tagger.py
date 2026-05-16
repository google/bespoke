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
from bespoke import UnitIndex
from bespoke import WordUnit
from bespoke import tagger
from tests import fakes


class TestWordTagger(unittest.IsolatedAsyncioTestCase):
    async def test_word_tagger(self) -> None:
        language = fakes.fake_language()

        class FakeWordLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(self, sentence: str, language, hint: list[str]):
                return [("大学生", "大学生")]

        llm_client = FakeWordLlmClient()
        sentence = "大学生です。"
        hint = ["大学生", "学生"]
        full_vocabulary = ["大学生", "学生"]

        unit_index = UnitIndex()
        for w in full_vocabulary:
            unit_index.add(WordUnit(w, Difficulty.A1))

        t = tagger.WordTagger(sentence, hint, unit_index, language)
        self.assertFalse(t.done())

        await t.progress(llm_client)
        self.assertFalse(t.done())
        await t.progress(llm_client)
        self.assertTrue(t.done())

        result = t.tags()
        self.assertIn("大学生", result)
        self.assertEqual(result["大学生"].id(), "大学生")

    async def test_long_then_short(self) -> None:
        language = fakes.fake_language()

        class FakeWordLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(self, sentence: str, language, hint: list[str]):
                return [("大学生", "大学生"), ("学生", "学生")]

        llm_client = FakeWordLlmClient()
        sentence = "大学生です。"
        hint: list[str] = []
        full_vocabulary = ["大学生", "学生"]

        unit_index = UnitIndex()
        for w in full_vocabulary:
            unit_index.add(WordUnit(w, Difficulty.A1))

        t = tagger.WordTagger(sentence, hint, unit_index, language)
        await t.progress(llm_client)

        result = t.tags()
        self.assertIn("大学生", result)
        self.assertNotIn("学生", result)


class TestDictionaryTagger(unittest.IsolatedAsyncioTestCase):
    async def test_dictionary_tagger(self) -> None:
        language = fakes.fake_language()

        # Fake dictionary data
        dictionary_data = {
            "學生": [{"definitions": [{"def": "在學校學習的人。"}]}],
            "大學生": [{"definitions": [{"def": "在大學學習的人。"}]}],
        }

        class FakeDisambiguatedLlmClient(fakes.FakeLlmClient):
            async def tag_sentence_disambiguated(
                self, sentence: str, language, hints: str
            ):
                return [("大學生", "大學生", 0)]

        llm_client = FakeDisambiguatedLlmClient()
        sentence = "我是大學生。"

        unit_index = UnitIndex()
        for word, entries in dictionary_data.items():
            for entry in entries:
                for d in entry.get("definitions", []):
                    unit_index.add(
                        DictionaryUnit(
                            name=word, definition=d["def"], difficulty=Difficulty.A1
                        )
                    )

        t = tagger.DictionaryTagger(sentence, [], unit_index, language)
        self.assertFalse(t.done())

        await t.progress(llm_client)
        self.assertTrue(t.done())

        result = t.tags()
        self.assertIn("大學生", result)
        self.assertEqual(result["大學生"].id(), "在大學學習的人。")


if __name__ == "__main__":
    unittest.main()
