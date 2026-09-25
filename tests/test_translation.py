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

from bespoke import (
    DictionaryUnit,
    Difficulty,
    Language,
    WordUnit,
    languages,
    translation,
)
from tests import fakes


class TranslationFakeLlmClient(fakes.FakeLlmClient):
    """Fake LLM client tailored for translation testing."""

    def __init__(self, translation_map: dict[str, str] | None = None) -> None:
        super().__init__()
        self.translation_map = translation_map or {}
        self.calls: list[str] = []

    async def text_call(self, prompt: str, *, lower_safety: bool = False) -> str:
        self.calls.append(prompt)
        for key, val in self.translation_map.items():
            if key in prompt:
                return val
        return "Standard Translation"

    async def translate(self, sentence: str, language: Language) -> str:
        if sentence in self.translation_map:
            return self.translation_map[sentence]
        return f"Translated {sentence} to {language.name}"


class TestTranslation(unittest.IsolatedAsyncioTestCase):
    def test_validate_translation(self) -> None:
        self.assertTrue(translation.validate_translation("student"))
        self.assertTrue(translation.validate_translation("university student, scholar"))
        self.assertTrue(translation.validate_translation("Haus"))

        # Invalid cases
        self.assertFalse(translation.validate_translation(""))
        self.assertFalse(translation.validate_translation("   "))
        self.assertFalse(translation.validate_translation("student [noun]"))
        self.assertFalse(translation.validate_translation("student (noun)"))
        self.assertFalse(translation.validate_translation("student *noun*"))
        self.assertFalse(translation.validate_translation("student\ncollege"))
        self.assertFalse(translation.validate_translation("student\rcollege"))
        self.assertFalse(
            translation.validate_translation(
                "a" * (translation.MAX_RESPONSE_LENGTH + 1)
            )
        )

    async def test_translate_unit(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["german"]
        unit = WordUnit(word="本", difficulty=Difficulty.A1)
        fake_llm = TranslationFakeLlmClient({"本": "Buch"})

        results: dict[str, str] = {}
        await translation.translate_unit(
            unit=unit,
            target_language=target,
            llm_client=fake_llm,
            native_language=native,
            results=results,
        )
        self.assertEqual(results.get("本"), "Buch")

    async def test_translate_units(self) -> None:
        target = languages.LANGUAGES["japanese"]
        native = languages.LANGUAGES["german"]
        units = [
            WordUnit(word="本", difficulty=Difficulty.A1),
            DictionaryUnit(name="学生", definition="student", difficulty=Difficulty.A1),
        ]
        fake_llm = TranslationFakeLlmClient({"本": "Buch", "学生": "Student"})

        results = await translation.translate_units(
            units=units,
            target_language=target,
            native_language=native,
            llm_client=fake_llm,
            existing_translations={"本": "Existing Buch"},
        )
        self.assertEqual(results.get("本"), "Existing Buch")
        self.assertEqual(results.get("学生 - student"), "Student")


if __name__ == "__main__":
    unittest.main()
