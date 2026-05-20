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
import unittest
import pydantic

from bespoke import Card
from bespoke.unit import UnitTag


class TestCard(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
