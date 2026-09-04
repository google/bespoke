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

from pathlib import Path
import tempfile
import unittest
from unittest import mock

import pydantic

from bespoke import Card
from bespoke import CardIndex
from bespoke.languages import LANGUAGES
from bespoke.unit import Difficulty
from bespoke.unit import UnitTag
from bespoke.unit import WordUnit
from tests.fakes import FakeLlmClient


class TestCard(unittest.IsolatedAsyncioTestCase):
    def test_split_into_parts(self) -> None:
        card = Card(
            id="test",
            sentence="大学生は学生より年上です。",
            native_sentence="A university student is older than a student.",
            audio_filename="audio.ogg",
            slow_audio_filename="slow_audio.ogg",
            native_audio_filename="native_audio.ogg",
            phonetic="だいがくせいはがくせいよりとしうえです。",
            unit_tags=[
                UnitTag(occurance="大学生", unit_id="大学生"),
                UnitTag(occurance="学生", unit_id="学生"),
            ],
            notes=[],
        )
        split = [
            UnitTag(occurance="大学生", unit_id="大学生"),
            UnitTag(occurance="は", unit_id=""),
            UnitTag(occurance="学生", unit_id="学生"),
            UnitTag(occurance="より年上です。", unit_id=""),
        ]
        self.assertEqual(card.split_into_parts(), split)

    def test_str(self) -> None:
        card = Card(
            id="test",
            sentence="大学生は学生より年上です。",
            native_sentence="A university student is older than a student.",
            audio_filename="audio.ogg",
            slow_audio_filename="slow_audio.ogg",
            native_audio_filename="native_audio.ogg",
            phonetic="だいがくせいはがくせいよりとしうえです。",
            unit_tags=[
                UnitTag(occurance="大学生", unit_id="大学生"),
                UnitTag(occurance="学生", unit_id="学生"),
            ],
            notes=[],
        )
        str_text = "Card: [大学生](大学生)は[学生](学生)より年上です。 = A university student is older than a student."
        self.assertEqual(str(card), str_text)

    def test_card_validation_sorted(self) -> None:
        Card(
            id="test",
            sentence="ABC",
            native_sentence="abc",
            audio_filename="a.ogg",
            slow_audio_filename="s.ogg",
            native_audio_filename="n.ogg",
            phonetic="abc",
            unit_tags=[
                UnitTag(occurance="A", unit_id="A"),
                UnitTag(occurance="C", unit_id="C"),
            ],
            notes=[],
        )

        with self.assertRaises(pydantic.ValidationError):
            Card(
                id="test",
                sentence="ABC",
                native_sentence="abc",
                audio_filename="a.ogg",
                slow_audio_filename="s.ogg",
                native_audio_filename="n.ogg",
                phonetic="abc",
                unit_tags=[
                    UnitTag(occurance="C", unit_id="C"),
                    UnitTag(occurance="A", unit_id="A"),
                ],
                notes=[],
            )

    def test_card_validation_overlapping(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            Card(
                id="test",
                sentence="ABC",
                native_sentence="abc",
                audio_filename="a.ogg",
                slow_audio_filename="s.ogg",
                native_audio_filename="n.ogg",
                phonetic="abc",
                unit_tags=[
                    UnitTag(occurance="AB", unit_id="AB"),
                    UnitTag(occurance="BC", unit_id="BC"),
                ],
                notes=[],
            )

    def test_old_card_conversion(self) -> None:
        card = Card.load(Path("tests/data"), "old_card_example")
        self.assertIsNotNone(card)
        assert card is not None
        self.assertEqual(card.id, "old_test")
        self.assertEqual(card.sentence, "大学生は学生より年上です。")
        self.assertEqual(set(card.unit_ids()), {"学生", "大学生"})
        self.assertEqual(len(card.unit_tags), 2)
        tags = {(t.occurance, t.unit_id) for t in card.unit_tags}
        self.assertEqual(tags, {("学生", "学生"), ("大学生", "大学生")})

    def test_new_card_loading(self) -> None:
        card = Card.load(Path("tests/data"), "new_card_example")
        self.assertIsNotNone(card)
        assert card is not None
        self.assertEqual(card.id, "old_test")
        self.assertEqual(card.sentence, "大学生は学生より年上です。")
        old_card = Card.load(Path("tests/data"), "old_card_example")
        self.assertIsNotNone(old_card)
        assert old_card is not None
        self.assertEqual(card, old_card)

    async def test_card_index_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            target_lang = LANGUAGES["trad_chinese"]
            native_lang = LANGUAGES["german"]
            card_index = CardIndex(target_lang, native_lang)
            card_index._card_directory = tmp_path / "cards"
            card_index._index_path = tmp_path / "index.json"
            card_index._card_directory.mkdir(parents=True, exist_ok=True)

            card_id = "test_card_id"
            audio_path = tmp_path / "audio.ogg"
            slow_audio_path = tmp_path / "slow.ogg"
            native_audio_path = tmp_path / "native.ogg"

            audio_path.write_bytes(b"audio")
            slow_audio_path.write_bytes(b"slow")
            native_audio_path.write_bytes(b"native")

            card = Card(
                id=card_id,
                sentence="大學生是學生。",
                native_sentence="University student.",
                audio_filename=str(audio_path),
                slow_audio_filename=str(slow_audio_path),
                native_audio_filename=str(native_audio_path),
                phonetic="...",
                unit_tags=[
                    UnitTag(occurance="大學生", unit_id="大學生"),
                    UnitTag(occurance="學生", unit_id="學生"),
                ],
                notes=[],
            )
            card.write_json(card_index._card_directory)
            card_index._add(card)
            student_unit = WordUnit("學生", Difficulty.A1)
            college_unit = WordUnit("大學生", Difficulty.A1)

            self.assertTrue((card_index._card_directory / f"{card_id}.json").exists())
            self.assertTrue(audio_path.exists())
            self.assertTrue(slow_audio_path.exists())
            self.assertTrue(native_audio_path.exists())
            self.assertEqual(card_index.size(college_unit), 1)
            self.assertEqual(card_index.cards(college_unit)[0].id, card_id)

            await card_index.remove(card_id)
            self.assertFalse((card_index._card_directory / f"{card_id}.json").exists())
            self.assertFalse(audio_path.exists())
            self.assertFalse(slow_audio_path.exists())
            self.assertFalse(native_audio_path.exists())
            self.assertEqual(card_index.size(college_unit), 0)
            self.assertEqual(card_index.size(student_unit), 0)

    async def test_card_index_remove_shared_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            target_lang = LANGUAGES["trad_chinese"]
            native_lang = LANGUAGES["german"]
            card_index = CardIndex(target_lang, native_lang)
            card_index._card_directory = tmp_path / "cards"
            card_index._index_path = tmp_path / "index.json"
            card_index._card_directory.mkdir(parents=True, exist_ok=True)

            audio1_path = tmp_path / "audio1.ogg"
            slow1_path = tmp_path / "slow1.ogg"
            audio2_path = tmp_path / "audio2.ogg"
            slow2_path = tmp_path / "slow2.ogg"
            shared_native_path = tmp_path / "shared_native.ogg"

            audio1_path.write_bytes(b"audio1")
            slow1_path.write_bytes(b"slow1")
            audio2_path.write_bytes(b"audio2")
            slow2_path.write_bytes(b"slow2")
            shared_native_path.write_bytes(b"shared_native")

            card1 = Card(
                id="card1_id",
                sentence="大學生是學生。",
                native_sentence="University student.",
                audio_filename=str(audio1_path),
                slow_audio_filename=str(slow1_path),
                native_audio_filename=str(shared_native_path),
                phonetic="...",
                unit_tags=[UnitTag(occurance="學生", unit_id="學生")],
                notes=[],
            )
            card2 = Card(
                id="card2_id",
                sentence="小學生是學生。",
                native_sentence="Elementary student.",
                audio_filename=str(audio2_path),
                slow_audio_filename=str(slow2_path),
                native_audio_filename=str(shared_native_path),
                phonetic="...",
                unit_tags=[UnitTag(occurance="學生", unit_id="學生")],
                notes=[],
            )
            student_unit = WordUnit("學生", Difficulty.A1)

            card1.write_json(card_index._card_directory)
            card2.write_json(card_index._card_directory)
            card_index._add(card1)
            card_index._add(card2)
            self.assertEqual(card_index.size(student_unit), 2)

            await card_index.remove("card1_id")
            self.assertFalse((card_index._card_directory / "card1_id.json").exists())
            self.assertFalse(audio1_path.exists())
            self.assertFalse(slow1_path.exists())
            self.assertTrue(shared_native_path.exists())
            self.assertTrue((card_index._card_directory / "card2_id.json").exists())
            self.assertEqual(card_index.size(student_unit), 1)

            await card_index.remove("card2_id")
            self.assertFalse((card_index._card_directory / "card2_id.json").exists())
            self.assertFalse(audio2_path.exists())
            self.assertFalse(slow2_path.exists())
            self.assertFalse(shared_native_path.exists())
            self.assertEqual(card_index.size(student_unit), 0)

    @mock.patch("bespoke.card._write_ogg")
    async def test_card_index_create_card_allowed(
        self, mock_write_ogg: mock.AsyncMock
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            target_language = LANGUAGES["japanese"]
            native_language = LANGUAGES["english"]
            card_index = CardIndex(target_language, native_language)
            card_index._card_directory = temporary_path / "cards"
            card_index._index_path = temporary_path / "index.json"
            card_index._card_directory.mkdir(parents=True, exist_ok=True)
            fake_llm_client = FakeLlmClient(check_card_allowed=True)
            sentence = "大学生は学生より年上です。"
            unit_tags = [
                UnitTag(occurance="大学生", unit_id="大学生"),
                UnitTag(occurance="学生", unit_id="学生"),
            ]
            created_card = await card_index.create_card(
                llm_client=fake_llm_client,
                sentence=sentence,
                unit_tags=unit_tags,
            )
            self.assertIsNotNone(created_card)
            assert created_card is not None
            self.assertEqual(created_card.sentence, sentence)
            self.assertTrue(
                (card_index._card_directory / f"{created_card.id}.json").exists()
            )
            self.assertTrue(created_card.audio_filename.endswith(".ogg"))
            self.assertTrue(created_card.slow_audio_filename.endswith("_slow.ogg"))
            self.assertTrue(created_card.native_audio_filename.endswith(".ogg"))
            self.assertEqual(mock_write_ogg.await_count, 3)
            student_unit = WordUnit("学生", Difficulty.A1)
            self.assertEqual(card_index.size(student_unit), 1)

    @mock.patch("bespoke.card._write_ogg")
    async def test_card_index_create_card_rejected(
        self, mock_write_ogg: mock.AsyncMock
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            target_language = LANGUAGES["japanese"]
            native_language = LANGUAGES["english"]
            card_index = CardIndex(target_language, native_language)
            card_index._card_directory = temporary_path / "cards"
            card_index._index_path = temporary_path / "index.json"
            card_index._card_directory.mkdir(parents=True, exist_ok=True)
            fake_llm_client = FakeLlmClient(check_card_allowed=False)
            sentence = "大学生は学生より年上です。"
            unit_tags = [
                UnitTag(occurance="大学生", unit_id="大学生"),
                UnitTag(occurance="学生", unit_id="学生"),
            ]
            created_card = await card_index.create_card(
                llm_client=fake_llm_client,
                sentence=sentence,
                unit_tags=unit_tags,
            )
            self.assertIsNone(created_card)
            card_files = list(card_index._card_directory.glob("*.json"))
            self.assertEqual(len(card_files), 0)
            self.assertEqual(mock_write_ogg.await_count, 0)
            student_unit = WordUnit("学生", Difficulty.A1)
            self.assertEqual(card_index.size(student_unit), 0)


if __name__ == "__main__":
    unittest.main()
