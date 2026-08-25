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
from bespoke import DictionaryUnit
from bespoke import Unit
from bespoke import UnitTag
from bespoke import UnitTags
from bespoke import WordUnit
from bespoke import languages
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

    def test_strip_explicit_punctuation(self) -> None:
        self.assertEqual(
            tagger.strip_explicit_punctuation("かなくちゃ。"), "かなくちゃ"
        )
        self.assertEqual(tagger.strip_explicit_punctuation("、とき、"), "とき")
        self.assertEqual(tagger.strip_explicit_punctuation("don't"), "don't")

    def test_get_tagging_coverage(self) -> None:
        sentence = "The cat sat on the mat."
        tags = [
            UnitTag(occurance="cat", unit_id="cat"),
            UnitTag(occurance="mat", unit_id="mat"),
        ]
        coverage = tagger.get_tagging_coverage(sentence, tags)
        self.assertAlmostEqual(coverage, 6 / 17)
        self.assertEqual(tagger.get_tagging_coverage("...", []), 0.0)

    def test_japanese_grammar_words_in_vocabulary(self) -> None:
        language = languages.LANGUAGES["japanese"]
        vocab_names = set(u.name() for u in language.units())
        for stem in tagger.JAPANESE_GRAMMAR_WORDS.values():
            self.assertIn(stem, vocab_names)

    def test_grammar_word_occurance(self) -> None:
        self.assertEqual(
            tagger.grammar_word_occurance("導入されている", "する"), "されて"
        )
        self.assertEqual(tagger.grammar_word_occurance("彼こそ", "こそ"), "こそ")
        self.assertEqual(tagger.grammar_word_occurance("それならば", "なら"), "ならば")
        self.assertIsNone(tagger.grammar_word_occurance("猫", "する"))

    def test_find_grammar_word_matches_longest_first(self) -> None:
        sentence = "この業界では最近新しい技術が次々と導入されている。"
        stems = tagger.find_grammar_word_matches(sentence)
        # Verify されて -> する is matched
        self.assertIn("する", stems)
        self.assertIn("この", stems)
        self.assertIn("で", stems)
        self.assertIn("は", stems)
        self.assertIn("が", stems)
        self.assertIn("と", stems)
        # Unsafe single-character particles 'さ' and 'し' must not be matched
        self.assertNotIn("さ", stems)
        self.assertNotIn("し", stems)

    def test_find_grammar_word_matches_particles(self) -> None:
        sentence = "彼こそ本当の意味でのリーダーになりやすい人です。"
        stems = tagger.find_grammar_word_matches(sentence)
        self.assertIn("こそ", stems)
        self.assertIn("の", stems)
        self.assertIn("で", stems)

    def test_find_grammar_word_matches_excludes_unsafe_single_chars(self) -> None:
        sentence = "忙しい仕事のスケジュールにしても休日の計画を立てたい。"
        stems = tagger.find_grammar_word_matches(sentence)
        # "して" -> "する" should match from "にしても"
        self.assertIn("する", stems)
        # 1-character particles around it should match
        self.assertIn("に", stems)
        self.assertIn("も", stems)
        self.assertIn("の", stems)
        self.assertIn("を", stems)
        # Unsafe single-character particles (し, さ) must not be matched in "忙しい"
        self.assertNotIn("し", stems)
        self.assertNotIn("さ", stems)

    def test_find_grammar_word_matches_shitai_and_nara(self) -> None:
        sentence = "東京に行くなら、観光もしたい。"
        stems = tagger.find_grammar_word_matches(sentence)
        self.assertIn("なら", stems)
        self.assertIn("する", stems)
        self.assertIn("に", stems)
        self.assertIn("も", stems)


class TestCreateTags(unittest.IsolatedAsyncioTestCase):
    async def test_create_tags_basic(self) -> None:
        language = fakes.fake_language()
        language.code_name = "english"

        class FakeLlmClient(fakes.FakeLlmClient):
            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
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
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                return [
                    UnitTag(occurance="gehe", unit_id="gehen - schrittweises bewegen")
                ]

            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
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
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
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
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
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
            def __init__(self) -> None:
                self.round = 0

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                self.round += 1
                if self.round == 1:
                    return [UnitTag(occurance="cat", unit_id="cat")]
                else:
                    return [UnitTag(occurance="mat", unit_id="mat")]

            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
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

    async def test_create_tags_japanese_basic(self) -> None:
        language = fakes.fake_language()
        language.code_name = "japanese"
        units: list[Unit] = [
            WordUnit("猫", Difficulty.A1),
            WordUnit("が", Difficulty.A1),
            WordUnit("いる", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        class FakeJapaneseLlmClient(fakes.FakeLlmClient):
            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
                return ["猫", "が", "いる"]

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                return [
                    UnitTag(occurance="猫", unit_id="猫"),
                    UnitTag(occurance="が", unit_id="が"),
                    UnitTag(occurance="います", unit_id="いる"),
                ]

        llm_client = FakeJapaneseLlmClient()
        sentence = "猫がいます。"
        result = await tagger.create_tags(sentence, [], language, llm_client)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].occurance, "猫")
        self.assertEqual(result[0].unit_id, "猫")
        self.assertEqual(result[1].occurance, "が")
        self.assertEqual(result[1].unit_id, "が")
        self.assertEqual(result[2].occurance, "います")
        self.assertEqual(result[2].unit_id, "いる")

    async def test_create_tags_japanese_multi_round_suggestions(self) -> None:
        language = fakes.fake_language()
        language.code_name = "japanese"
        units: list[Unit] = [
            WordUnit("ご飯", Difficulty.A1),
            WordUnit("を", Difficulty.A1),
            WordUnit("食べる", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        class FakeJapaneseMultiRoundLlmClient(fakes.FakeLlmClient):
            def __init__(self) -> None:
                self.tag_calls: int = 0
                self.received_hints: list[list[Unit]] = []

            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
                if self.tag_calls == 0:
                    return ["ご飯", "を"]
                return ["食べる"]

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                self.tag_calls += 1
                self.received_hints.append(list(hint))
                if self.tag_calls == 1:
                    return [
                        UnitTag(occurance="ご飯", unit_id="ご飯"),
                        UnitTag(occurance="を", unit_id="を"),
                    ]
                else:
                    return [
                        UnitTag(occurance="ご飯", unit_id="ご飯"),
                        UnitTag(occurance="を", unit_id="を"),
                        UnitTag(occurance="食べました", unit_id="食べる"),
                    ]

        llm_client = FakeJapaneseMultiRoundLlmClient()
        sentence = "ご飯を食べました。"
        result = await tagger.create_tags(sentence, [], language, llm_client)
        self.assertEqual(llm_client.tag_calls, 2)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].occurance, "ご飯")
        self.assertEqual(result[1].occurance, "を")
        self.assertEqual(result[2].occurance, "食べました")
        self.assertEqual(result[2].unit_id, "食べる")
        # Verify second round received the new hint for 食べる
        second_hints = llm_client.received_hints[1]
        self.assertTrue(any(u.name() == "食べる" for u in second_hints))

    async def test_create_tags_japanese_suru_rule_b(self) -> None:
        language = fakes.fake_language()
        language.code_name = "japanese"
        units: list[Unit] = [
            WordUnit("発生", Difficulty.A1),
            WordUnit("する", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        class FakeSuruLlmClient(fakes.FakeLlmClient):
            def __init__(self) -> None:
                self.received_hints: list[Unit] = []

            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
                return ["発生"]

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                self.received_hints = list(hint)
                return [
                    UnitTag(occurance="発生", unit_id="発生"),
                    UnitTag(occurance="した", unit_id="する"),
                ]

        llm_client = FakeSuruLlmClient()
        sentence = "発生した。"
        result = await tagger.create_tags(sentence, [], language, llm_client)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].occurance, "発生")
        self.assertEqual(result[1].occurance, "した")
        self.assertEqual(result[1].unit_id, "する")
        # Verify する was added to hints via Rule B
        self.assertTrue(any(u.name() == "する" for u in llm_client.received_hints))

    async def test_create_tags_japanese_impossible_tag_filtered(self) -> None:
        language = fakes.fake_language()
        language.code_name = "japanese"
        units: list[Unit] = [
            WordUnit("私", Difficulty.A1),
            WordUnit("は", Difficulty.A1),
            WordUnit("猫", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        class FakeImpossibleTagLlmClient(fakes.FakeLlmClient):
            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
                return ["私", "は", "猫"]

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                # Returns "猫" which is not in the sentence, and "私" out of order
                return [
                    UnitTag(occurance="は", unit_id="は"),
                    UnitTag(occurance="猫", unit_id="猫"),
                    UnitTag(occurance="私", unit_id="私"),
                ]

        llm_client = FakeImpossibleTagLlmClient()
        sentence = "私は。"
        result = await tagger.create_tags(sentence, [], language, llm_client)
        # "は" appears at index 1 -> matches.
        # "猫" is not in sentence -> impossible (dropped).
        # "私" appears at index 0 which is < current_index (2) -> impossible (dropped).
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].occurance, "は")
        self.assertEqual(result[0].unit_id, "は")

    async def test_create_tags_japanese_grammar_word_post_filtering(self) -> None:
        language = fakes.fake_language()
        language.code_name = "japanese"
        units: list[Unit] = [
            WordUnit("導入", Difficulty.A1),
            WordUnit("する", Difficulty.A1),
            WordUnit("彼", Difficulty.A1),
            WordUnit("こそ", Difficulty.A1),
            WordUnit("言う", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        class FakeGrammarPostFilterLlmClient(fakes.FakeLlmClient):
            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
                return ["導入", "する", "彼", "こそ", "言う"]

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                return [
                    UnitTag(occurance="導入", unit_id="導入"),
                    UnitTag(occurance="導入されている", unit_id="する"),
                    UnitTag(occurance="彼こそ", unit_id="こそ"),
                    UnitTag(occurance="言える", unit_id="言う"),
                    UnitTag(occurance="猫", unit_id="する"),  # hallucination
                ]

        llm_client = FakeGrammarPostFilterLlmClient()
        sentence = "導入されている彼こそ言える。"
        result = await tagger.create_tags(sentence, [], language, llm_client)
        # Verify:
        # "導入されている" with unit "する" normalized to "されて"
        # "彼こそ" with unit "こそ" normalized to "こそ"
        # "言える" with regular lexical unit "言う" passes through without being dropped
        # "猫" with unit "する" dropped
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0].occurance, "導入")
        self.assertEqual(result[1].occurance, "されて")
        self.assertEqual(result[1].unit_id, "する")
        self.assertEqual(result[2].occurance, "こそ")
        self.assertEqual(result[2].unit_id, "こそ")
        self.assertEqual(result[3].occurance, "言える")
        self.assertEqual(result[3].unit_id, "言う")

    async def test_create_tags_japanese_suru_and_continuous(self) -> None:
        language = fakes.fake_language()
        language.code_name = "japanese"
        units: list[Unit] = [
            WordUnit("私", Difficulty.A1),
            WordUnit("が", Difficulty.A1),
            WordUnit("注目", Difficulty.A1),
            WordUnit("する", Difficulty.A1),
            WordUnit("いる", Difficulty.A1),
            WordUnit("の", Difficulty.A1),
            WordUnit("は", Difficulty.A1),
            WordUnit("ゲーム", Difficulty.A1),
            WordUnit("業界", Difficulty.A1),
            WordUnit("成長", Difficulty.A1),
            WordUnit("だ", Difficulty.A1),
        ]
        language._units = units
        language._units_by_id = {u.id(): u for u in units}
        language._units_by_name = {u.name(): [u] for u in units}
        language._initialized = True

        class FakeLlmClient(fakes.FakeLlmClient):
            def __init__(self) -> None:
                self.received_hints: list[Unit] = []

            async def suggest_names(
                self, sentence: str, language: languages.Language
            ) -> list[str]:
                return [
                    "私",
                    "が",
                    "注目",
                    "する",
                    "いる",
                    "の",
                    "は",
                    "ゲーム",
                    "業界",
                    "成長",
                    "だ",
                ]

            async def tag_sentence(
                self,
                sentence: str,
                language: languages.Language,
                hint: list[Unit],
                marked_sentence: str | None = None,
                existing_tags: list[UnitTag] | None = None,
            ) -> UnitTags:
                self.received_hints = list(hint)
                return [
                    UnitTag(occurance="私", unit_id="私"),
                    UnitTag(occurance="が", unit_id="が"),
                    UnitTag(occurance="注目", unit_id="注目"),
                    UnitTag(occurance="して", unit_id="する"),
                    UnitTag(occurance="いる", unit_id="いる"),
                    UnitTag(occurance="の", unit_id="の"),
                    UnitTag(occurance="は", unit_id="は"),
                    UnitTag(occurance="ゲーム", unit_id="ゲーム"),
                    UnitTag(occurance="業界", unit_id="業界"),
                    UnitTag(occurance="の", unit_id="の"),
                    UnitTag(occurance="成長", unit_id="成長"),
                    UnitTag(occurance="だ", unit_id="だ"),
                ]

        llm_client = FakeLlmClient()
        sentence = "私が注目しているのはゲーム業界の成長だ。"
        result = await tagger.create_tags(sentence, [], language, llm_client)

        # Verify all 12 tags and 100% coverage
        self.assertEqual(len(result), 12)
        self.assertEqual(result[3].occurance, "して")
        self.assertEqual(result[3].unit_id, "する")
        self.assertEqual(result[4].occurance, "いる")
        self.assertEqual(result[4].unit_id, "いる")

    def test_japanese_few_shot_prompts_included(self) -> None:
        from bespoke import llm

        language = fakes.fake_language()
        language.code_name = "japanese"
        language.writing_system = "Japanese (Kanji and Kana)"

        suggest_prompt = llm._build_suggest_names_prompt("テスト", language)
        self.assertIn("注目している", suggest_prompt)
        self.assertIn("安くて美味しいし", suggest_prompt)

        tag_prompt = llm._build_tag_sentence_prompt(
            "テスト", language, [WordUnit("テスト", Difficulty.A1)]
        )
        self.assertIn("注目している", tag_prompt)
        self.assertIn("導入されている", tag_prompt)
        self.assertIn("これといった", tag_prompt)


if __name__ == "__main__":
    unittest.main()
