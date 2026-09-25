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

import csv
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from bespoke import database
from bespoke.card import Card
from bespoke.languages import LANGUAGES, Difficulty, Language
from bespoke.unit import DictionaryUnit, UnitTag, WordUnit
from maintainers.convert_dataset import convert_dataset
from maintainers.package_cards import package_cards
from tests import fakes


class TestDatabase(unittest.TestCase):
    def test_get_dataset_db_path(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        path = database.get_dataset_db_path("cards", target, native)
        self.assertEqual(path, Path("cards/japanese_(english).db"))
        path_str = database.get_dataset_db_path("cards", "German", "French")
        self.assertEqual(path_str, Path("cards/german_(french).db"))

    def test_write_dataset_to_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_write.db"
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
                ],
                notes=["Grammar: より"],
            )
            audio_data = {
                "audio_1.ogg": b"TARGET_AUDIO_1",
                "slow_1.ogg": b"SLOW_AUDIO_1",
                "native_1.ogg": b"NATIVE_AUDIO_1",
            }
            translations = {
                "大学生": "university student",
                "学生 - student": "student",
            }
            vocabulary = [
                WordUnit("大学生", Difficulty.A1),
                DictionaryUnit("学生", "student", Difficulty.A1),
            ]
            card_index = {
                "大学生": ["card_001"],
                "学生 - student": ["card_001"],
            }

            result = database.write_dataset_to_db(
                output_db_path=db_path,
                target=target,
                native=native,
                cards=[card],
                audio_data=audio_data,
                translations=translations,
                vocabulary=vocabulary,
                card_index=card_index,
            )
            self.assertEqual(result, db_path)
            self.assertTrue(db_path.exists())
            self.assertTrue(database.verify_dataset_db(db_path))

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            self.assertTrue(database.EXPECTED_TABLES.keys() <= tables)
            conn.close()

            meta = database.load_metadata_from_db(db_path)
            self.assertEqual(meta["target_language"], "japanese")
            self.assertEqual(meta["native_language"], "english")
            self.assertEqual(meta["card_count"], "1")
            self.assertEqual(meta["audio_count"], "3")

    def _create_sample_files(
        self,
        base_dir: Path,
        target: Language,
        native: Language,
    ) -> Path:
        cards_dir = base_dir / "cards"
        subdir = cards_dir / f"{target.code_name}_{native.code_name}"
        subdir.mkdir(parents=True, exist_ok=True)

        (subdir / "audio_1.ogg").write_bytes(b"TARGET_AUDIO_1")
        (subdir / "slow_1.ogg").write_bytes(b"SLOW_AUDIO_1")
        (subdir / "native_1.ogg").write_bytes(b"NATIVE_AUDIO_1")

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
            ],
            notes=["Grammar: より"],
        )
        card.write_json(subdir)

        trans_file = (
            cards_dir / f"translations_{target.code_name}_{native.code_name}.csv"
        )
        with open(trans_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["unit_id", "translation"])
            writer.writerow(["大学生", "university student"])
            writer.writerow(["学生 - student", "student"])

        vocab_file = cards_dir / f"vocabulary_{target.code_name}.csv"
        with open(vocab_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "definition", "difficulty"])
            writer.writerow(["大学生", "", "A1"])
            writer.writerow(["学生", "student", "A1"])

        index_file = cards_dir / f"index_{target.code_name}_{native.code_name}.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(
                {"大学生": ["card_001"], "学生 - student": ["card_001"]},
                f,
            )

        return cards_dir

    def test_package_cards(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"

            result = package_cards(cards_dir, target, native, db_path)
            self.assertEqual(result, db_path)
            self.assertTrue(db_path.exists())
            self.assertGreater(db_path.stat().st_size, 0)

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            self.assertTrue(database.EXPECTED_TABLES.keys() <= tables)
            conn.close()

    def test_verify_dataset_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            self.assertTrue(database.verify_dataset_db(db_path))
            self.assertFalse(database.verify_dataset_db(tmp_path / "missing.db"))

            corrupt_path = tmp_path / "corrupt.db"
            corrupt_path.write_text("not a db", encoding="utf-8")
            self.assertFalse(database.verify_dataset_db(corrupt_path))

    def test_load_metadata_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            metadata = database.load_metadata_from_db(db_path)
            self.assertEqual(metadata["target_language"], "japanese")
            self.assertEqual(metadata["native_language"], "english")
            self.assertEqual(metadata["card_count"], "1")

    def test_load_card_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            card = database.load_card_from_db(db_path, "card_001")
            self.assertIsNotNone(card)
            assert card is not None
            self.assertEqual(card.id, "card_001")
            self.assertEqual(card.sentence, "大学生は学生より年上です。")
            self.assertEqual(card.phonetic, "だいがくせいはがくせいよりとしうえです。")
            self.assertIsNone(database.load_card_from_db(db_path, "nonexistent"))

    def test_load_cards_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            cards = database.load_cards_from_db(db_path, ["card_001", "nonexistent"])
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards["card_001"].id, "card_001")

    def test_load_all_cards_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            all_cards = database.load_all_cards_from_db(db_path)
            self.assertEqual(len(all_cards), 1)
            self.assertEqual(all_cards[0].id, "card_001")

    def test_get_audio_blob(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            blob = database.get_audio_blob(
                db_path, "cards/japanese_english/audio_1.ogg"
            )
            self.assertEqual(blob, b"TARGET_AUDIO_1")

            blob_basename = database.get_audio_blob(db_path, "audio_1.ogg")
            self.assertEqual(blob_basename, b"TARGET_AUDIO_1")
            self.assertIsNone(database.get_audio_blob(db_path, "nonexistent.ogg"))

    def test_load_translations_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            translations = database.load_translations_from_db(db_path)
            self.assertEqual(translations["大学生"], "university student")
            self.assertEqual(translations["学生 - student"], "student")

    def test_load_vocabulary_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            vocab = database.load_vocabulary_from_db(db_path)
            self.assertEqual(len(vocab), 2)
            vocab_map = {u.id(): u for u in vocab}
            self.assertIn("大学生", vocab_map)
            self.assertIsInstance(vocab_map["大学生"], WordUnit)
            self.assertEqual(vocab_map["大学生"].difficulty(), Difficulty.A1)
            self.assertIn("学生 - student", vocab_map)
            self.assertIsInstance(vocab_map["学生 - student"], DictionaryUnit)
            self.assertEqual(vocab_map["学生 - student"].difficulty(), Difficulty.A1)

    def test_load_index_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            index = database.load_index_from_db(db_path)
            self.assertEqual(index["大学生"], ["card_001"])
            self.assertEqual(index["学生 - student"], ["card_001"])

    def test_import_dataset_from_db(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            imported_dir = tmp_path / "imported"

            package_cards(cards_dir, target, native, db_path)
            database.import_dataset_from_db(db_path, imported_dir)

            card_file = imported_dir / "japanese_english" / "card_001.json"
            self.assertTrue(card_file.exists())
            card = Card.model_validate_json(card_file.read_text(encoding="utf-8"))
            self.assertEqual(card.id, "card_001")

            audio_file = imported_dir / "japanese_english" / "audio_1.ogg"
            self.assertTrue(audio_file.exists())
            self.assertEqual(audio_file.read_bytes(), b"TARGET_AUDIO_1")

    def test_dataset_db_class(self) -> None:
        target = LANGUAGES["japanese"]
        native = LANGUAGES["english"]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            cards_dir = self._create_sample_files(tmp_path, target, native)
            db_path = tmp_path / "dataset.db"
            package_cards(cards_dir, target, native, db_path)

            with database.DatasetDB(db_path) as db:
                self.assertTrue(db.verify())
                self.assertEqual(len(db.get_all_cards()), 1)
                self.assertEqual(len(db.get_cards_for_unit("大学生")), 1)
                self.assertEqual(db.get_audio("audio_1.ogg"), b"TARGET_AUDIO_1")
                self.assertEqual(db.get_translations()["大学生"], "university student")
                self.assertEqual(len(db.get_vocabulary()), 2)
                self.assertEqual(db.get_index()["大学生"], ["card_001"])
                self.assertEqual(db.get_metadata()["target_language"], "japanese")


class ConvertFakeLlmClient(fakes.FakeLlmClient):
    def __init__(self, translation_map: dict[str, str] | None = None) -> None:
        super().__init__()
        self.translation_map = translation_map or {}

    async def text_call(self, prompt: str, *, lower_safety: bool = False) -> str:
        for key, val in self.translation_map.items():
            if key in prompt:
                return val
        return "Standard Translation"

    async def translate(self, sentence: str, language: Language) -> str:
        if sentence in self.translation_map:
            return self.translation_map[sentence]
        return f"Translated {sentence} to {language.name}"

    async def speak(self, sentence: str, *, slowly: bool = False) -> np.ndarray:
        return np.zeros(24000, dtype=np.int16)


class TestDatabaseConvert(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _create_source_db(base_dir: Path, target: Language, native: Language) -> Path:
        cards_dir = base_dir / "cards"
        subdir = cards_dir / f"{target.code_name}_{native.code_name}"
        subdir.mkdir(parents=True, exist_ok=True)

        (subdir / "target_001.ogg").write_bytes(b"OGG_TARGET_REGULAR")
        (subdir / "target_001_slow.ogg").write_bytes(b"OGG_TARGET_SLOW")
        (subdir / "native_001.ogg").write_bytes(b"OGG_NATIVE_ORIGINAL")

        card = Card(
            id="card_001",
            sentence="大学生は学生より年上です。",
            native_sentence="A university student is older than a student.",
            audio_filename=f"cards/{target.code_name}_{native.code_name}/target_001.ogg",
            slow_audio_filename=f"cards/{target.code_name}_{native.code_name}/target_001_slow.ogg",
            native_audio_filename=f"cards/{target.code_name}_{native.code_name}/native_001.ogg",
            phonetic="だいがくせいはがくせいよりとしうえです。",
            unit_tags=[
                UnitTag(occurance="大学生", unit_id="大学生"),
                UnitTag(occurance="学生", unit_id="学生 - student"),
            ],
            notes=["Note 1"],
        )
        card.write_json(subdir)

        trans_file = (
            cards_dir / f"translations_{target.code_name}_{native.code_name}.csv"
        )
        with open(trans_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["unit_id", "translation"])
            writer.writerow(["大学生", "university student"])
            writer.writerow(["学生 - student", "student"])

        vocab_file = cards_dir / f"vocabulary_{target.code_name}.csv"
        with open(vocab_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "definition", "difficulty"])
            writer.writerow(["大学生", "", "A1"])
            writer.writerow(["学生", "student", "A1"])

        index_file = cards_dir / f"index_{target.code_name}_{native.code_name}.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump({"大学生": ["card_001"], "学生 - student": ["card_001"]}, f)

        source_db = base_dir / "japanese_(english).db"
        package_cards(
            cards_dir=cards_dir,
            target=target,
            native=native,
            output_db_path=source_db,
        )
        return source_db

    @mock.patch(
        "maintainers.convert_dataset.encode_audio_to_ogg",
        return_value=b"OggS_NATIVE_CONVERTED_AUDIO",
    )
    async def test_convert_dataset(self, _mock_encode: mock.AsyncMock) -> None:
        target = LANGUAGES["japanese"]
        orig_native = LANGUAGES["english"]
        new_native = LANGUAGES["german"]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            source_db = self._create_source_db(tmp_path, target, orig_native)

            fake_llm = ConvertFakeLlmClient(
                {
                    "大学生は学生より年上です。": "Ein Universitätsstudent ist älter als ein Student.",
                    "大学生": "Universitätsstudent",
                    "学生": "Student",
                }
            )

            result_path = await convert_dataset(
                input_db_path=source_db,
                to_native=new_native,
                output_db_path=None,
                llm_client=fake_llm,
            )

            expected_path = tmp_path / "japanese_(german).db"
            self.assertEqual(result_path, expected_path)
            self.assertTrue(expected_path.exists())
            self.assertTrue(database.verify_dataset_db(expected_path))

            # Inspect converted DB contents
            meta = database.load_metadata_from_db(expected_path)
            self.assertEqual(meta["target_language"], "japanese")
            self.assertEqual(meta["native_language"], "german")
            self.assertEqual(meta["target_language_name"], "Japanese")
            self.assertEqual(meta["native_language_name"], "German")
            self.assertEqual(meta["card_count"], "1")

            cards = database.load_all_cards_from_db(expected_path)
            self.assertEqual(len(cards), 1)
            c = cards[0]
            self.assertEqual(c.id, "card_001")
            self.assertEqual(c.sentence, "大学生は学生より年上です。")
            self.assertEqual(
                c.native_sentence, "Ein Universitätsstudent ist älter als ein Student."
            )
            self.assertEqual(c.phonetic, "だいがくせいはがくせいよりとしうえです。")
            self.assertEqual(c.audio_filename, "cards/japanese_english/target_001.ogg")
            self.assertEqual(
                c.slow_audio_filename, "cards/japanese_english/target_001_slow.ogg"
            )
            self.assertTrue(
                c.native_audio_filename.startswith("cards/japanese_german/")
            )

            # Check audio blobs
            target_blob = database.get_audio_blob(expected_path, "target_001.ogg")
            self.assertEqual(target_blob, b"OGG_TARGET_REGULAR")

            slow_blob = database.get_audio_blob(expected_path, "target_001_slow.ogg")
            self.assertEqual(slow_blob, b"OGG_TARGET_SLOW")

            native_fn = Path(c.native_audio_filename).name
            native_blob = database.get_audio_blob(expected_path, native_fn)
            self.assertIsNotNone(native_blob)
            assert native_blob is not None
            self.assertTrue(native_blob.startswith(b"OggS"))

            # Check translations
            trans = database.load_translations_from_db(expected_path)
            self.assertEqual(trans.get("大学生"), "Universitätsstudent")
            self.assertEqual(trans.get("学生 - student"), "Student")

            # Check vocabulary and index
            vocab = database.load_vocabulary_from_db(expected_path)
            self.assertEqual(len(vocab), 2)
            index = database.load_index_from_db(expected_path)
            self.assertEqual(index["大学生"], ["card_001"])


if __name__ == "__main__":
    unittest.main()
