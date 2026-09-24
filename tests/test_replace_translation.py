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

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bespoke import database
from bespoke.card import Card
from bespoke.languages import LANGUAGES, Difficulty
from bespoke.unit import DictionaryUnit, UnitTag, WordUnit
from maintainers import replace_translation


class TestReplaceTranslation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.db_path = self.tmp_path / "test_deck.db"

        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        card = Card(
            id="card_001",
            sentence="大学生は学生より年上です。",
            native_sentence="A university student is older than a student.",
            audio_filename="cards/japanese_english/audio_1.ogg",
            slow_audio_filename="cards/japanese_english/slow_1.ogg",
            native_audio_filename="cards/japanese_english/native_1.ogg",
            phonetic="だいがくせいはがくせいよりとしうえです。",
            unit_tags=[
                UnitTag(occurance="大学生", unit_id="大学生"),
                UnitTag(occurance="学生", unit_id="学生 - student"),
                UnitTag(occurance="年上", unit_id="年上 - older"),
            ],
            notes=[],
        )
        audio_data = {
            "audio_1.ogg": b"AUDIO1",
            "slow_1.ogg": b"SLOW1",
            "native_1.ogg": b"NATIVE1",
        }
        translations = {
            "大学生": "university student",
            "学生 - student": "student",
            "年上 - older": "older",
        }
        vocabulary = [
            WordUnit("大学生", Difficulty.A1),
            DictionaryUnit("学生", "student", Difficulty.A1),
            DictionaryUnit("年上", "older", Difficulty.A1),
        ]
        card_index = {
            "大学生": ["card_001"],
            "学生 - student": ["card_001"],
            "年上 - older": ["card_001"],
        }

        database.write_dataset_to_db(
            output_db_path=self.db_path,
            target=target,
            native=native,
            cards=[card],
            audio_data=audio_data,
            translations=translations,
            vocabulary=vocabulary,
            card_index=card_index,
        )

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_replace_single_translation(self) -> None:
        count = replace_translation.replace_translations(
            self.db_path, {"学生 - student": "pupil / student"}
        )
        self.assertEqual(count, 1)

        trans = database.load_translations_from_db(self.db_path)
        self.assertEqual(trans["学生 - student"], "pupil / student")
        self.assertEqual(trans["大学生"], "university student")
        self.assertEqual(trans["年上 - older"], "older")

    def test_insert_new_translation_unit(self) -> None:
        count = replace_translation.replace_translations(
            self.db_path, {"新しい単語": "new word"}
        )
        self.assertEqual(count, 1)

        trans = database.load_translations_from_db(self.db_path)
        self.assertEqual(trans["新しい単語"], "new word")
        meta = database.load_metadata_from_db(self.db_path)
        self.assertEqual(meta.get("translation_count"), "4")

    def test_load_translations_file_strict_valid(self) -> None:
        csv_path = self.tmp_path / "fixes.csv"
        csv_path.write_text(
            "unit_id,translation\n大学生,college student\n年上 - older,elder\n",
            encoding="utf-8",
        )
        replacements = replace_translation.load_translations_file(csv_path)
        self.assertEqual(
            replacements,
            {"大学生": "college student", "年上 - older": "elder"},
        )

        count = replace_translation.replace_translations(self.db_path, replacements)
        self.assertEqual(count, 2)

        trans = database.load_translations_from_db(self.db_path)
        self.assertEqual(trans["大学生"], "college student")
        self.assertEqual(trans["年上 - older"], "elder")
        # Ensure unmentioned translations are untouched
        self.assertEqual(trans["学生 - student"], "student")

    def test_load_translations_file_invalid_header(self) -> None:
        csv_path = self.tmp_path / "invalid_header.csv"
        csv_path.write_text("word,meaning\n大学生,college student\n")
        with self.assertRaises(ValueError):
            replace_translation.load_translations_file(csv_path)

    def test_load_translations_file_invalid_row_columns(self) -> None:
        csv_path = self.tmp_path / "invalid_row.csv"
        csv_path.write_text("unit_id,translation\n大学生,student,extra\n")
        with self.assertRaises(ValueError):
            replace_translation.load_translations_file(csv_path)

    def test_load_translations_file_empty_unit_id(self) -> None:
        csv_path = self.tmp_path / "empty_unit.csv"
        csv_path.write_text("unit_id,translation\n,student\n")
        with self.assertRaises(ValueError):
            replace_translation.load_translations_file(csv_path)

    def test_cli_single_unit(self) -> None:
        with patch(
            "sys.argv",
            [
                "replace_translation",
                "--db",
                str(self.db_path),
                "--unit-id",
                "大学生",
                "--translation",
                "college student",
            ],
        ):
            code = replace_translation.main()
            self.assertEqual(code, 0)

        trans = database.load_translations_from_db(self.db_path)
        self.assertEqual(trans["大学生"], "college student")

    def test_cli_file_input(self) -> None:
        csv_path = self.tmp_path / "fixes.csv"
        csv_path.write_text(
            "unit_id,translation\n大学生,undergrad\n",
            encoding="utf-8",
        )
        with patch(
            "sys.argv",
            [
                "replace_translation",
                "--db",
                str(self.db_path),
                "--file",
                str(csv_path),
            ],
        ):
            code = replace_translation.main()
            self.assertEqual(code, 0)

        trans = database.load_translations_from_db(self.db_path)
        self.assertEqual(trans["大学生"], "undergrad")

    def test_cli_invalid_file(self) -> None:
        csv_path = self.tmp_path / "bad.csv"
        csv_path.write_text("wrong_header,translation\nfoo,bar\n")
        with patch(
            "sys.argv",
            [
                "replace_translation",
                "--db",
                str(self.db_path),
                "--file",
                str(csv_path),
            ],
        ):
            code = replace_translation.main()
            self.assertEqual(code, 1)

    def test_cli_missing_db(self) -> None:
        missing_db = self.tmp_path / "missing.db"
        with patch(
            "sys.argv",
            [
                "replace_translation",
                "--db",
                str(missing_db),
                "--unit-id",
                "foo",
                "--translation",
                "bar",
            ],
        ):
            code = replace_translation.main()
            self.assertEqual(code, 1)

    def test_cli_missing_arguments(self) -> None:
        with patch(
            "sys.argv",
            [
                "replace_translation",
                "--db",
                str(self.db_path),
            ],
        ):
            code = replace_translation.main()
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
