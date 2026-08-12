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

"""Tool to package a dataset into a single SQLite .db file."""

import argparse

from bespoke.card import CARDS_DIR
from bespoke import database
from bespoke import languages


CREATE_TABLES_SQL = database.CREATE_TABLES_SQL
DatasetDB = database.DatasetDB
EXPECTED_TABLES = database.EXPECTED_TABLES
export_dataset_to_db = database.export_dataset_to_db
get_audio_blob = database.get_audio_blob
import_dataset_from_db = database.import_dataset_from_db
load_all_cards_from_db = database.load_all_cards_from_db
load_card_from_db = database.load_card_from_db
load_cards_from_db = database.load_cards_from_db
load_index_from_db = database.load_index_from_db
load_metadata_from_db = database.load_metadata_from_db
load_translations_from_db = database.load_translations_from_db
load_vocabulary_from_db = database.load_vocabulary_from_db
resolve_language = database.resolve_language


def main():
    target_choices = {}
    for language in languages.LANGUAGES.values():
        if language.has_data():
            target_choices[language.writing_system] = language
            target_choices[language.code_name] = language

    native_choices = {}
    for language in languages.LANGUAGES.values():
        native_choices[language.writing_system] = language
        native_choices[language.code_name] = language

    parser = argparse.ArgumentParser(
        description="Package cards and vocabulary into a dataset."
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        choices=list(target_choices),
        help="The language you are learning.",
    )
    parser.add_argument(
        "--native",
        type=str,
        required=True,
        choices=list(native_choices),
        help="A language that you know.",
    )
    args = parser.parse_args()

    target = database.resolve_language(args.target)
    native = database.resolve_language(args.native)
    output_path = CARDS_DIR / f"{target.code_name}.db"

    print(
        f"Packaging {native.writing_system} -> {target.writing_system} into {output_path}..."
    )
    result = database.export_dataset_to_db(
        cards_dir=CARDS_DIR,
        target=target,
        native=native,
        output_db_path=output_path,
    )
    size_mb = result.stat().st_size / (1024 * 1024)
    print(f"Successfully packaged dataset: {result} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
