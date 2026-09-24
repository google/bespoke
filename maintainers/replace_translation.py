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

"""Tool to replace translations for dictionary units in a dataset .db file."""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path


def load_translations_file(file_path: Path | str) -> dict[str, str]:
    """Loads a mapping of unit_id -> translation from a CSV file.

    Strictly expects a CSV file with header 'unit_id,translation'.
    Raises ValueError or OSError if format is invalid.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Translations file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"Translations file '{path}' is empty.")
        if [col.strip() for col in header] != ["unit_id", "translation"]:
            raise ValueError(
                f"Invalid CSV header in '{path}': expected 'unit_id,translation', got '{','.join(header)}'."
            )

        results: dict[str, str] = {}
        for row_idx, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != 2:
                raise ValueError(
                    f"Invalid row {row_idx} in '{path}': expected 2 columns (unit_id, translation), got {len(row)}."
                )
            unit_id = row[0].strip()
            trans = row[1].strip()
            if not unit_id:
                raise ValueError(
                    f"Invalid row {row_idx} in '{path}': unit_id cannot be empty."
                )
            results[unit_id] = trans

    if not results:
        raise ValueError(f"No translations found in '{path}'.")

    return results


def replace_translations(
    db_path: Path | str,
    replacements: dict[str, str],
) -> int:
    """Replaces translations for specific unit IDs in a SQLite dataset .db file in-place.

    Args:
        db_path: Path to the .db SQLite database.
        replacements: Mapping of {unit_id: new_translation}.

    Returns:
        Number of translations successfully updated or inserted.
    """
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    if not replacements:
        print("No replacements provided.")
        return 0

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='translations'"
        )
        if not cursor.fetchone():
            raise sqlite3.OperationalError(
                "Table 'translations' does not exist in database."
            )

        # Load existing translations
        cursor.execute("SELECT unit_id, translation FROM translations")
        existing_trans = {row[0]: row[1] for row in cursor.fetchall()}

        applied_count = 0
        with conn:
            for unit_id, new_trans in replacements.items():
                if not unit_id:
                    continue

                prev_trans = existing_trans.get(unit_id)
                cursor.execute(
                    "INSERT OR REPLACE INTO translations (unit_id, translation) VALUES (?, ?)",
                    (unit_id, new_trans),
                )
                applied_count += 1
                if prev_trans is not None:
                    print(f"Updated '{unit_id}': '{prev_trans}' -> '{new_trans}'")
                else:
                    print(f"Added translation for '{unit_id}': '{new_trans}'")

            # Update translation_count in metadata if table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'"
            )
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM translations")
                count_row = cursor.fetchone()
                total_trans_count = count_row[0] if count_row else 0
                cursor.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'translation_count'",
                    (str(total_trans_count),),
                )

        return applied_count
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace dictionary unit translations in a .db dataset package."
    )
    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="Path to the .db database file (e.g., cards/japanese_(english).db).",
    )
    parser.add_argument(
        "--unit-id",
        type=str,
        help="Unit ID to replace.",
    )
    parser.add_argument(
        "--translation",
        type=str,
        help="New translation for the unit specified by --unit-id.",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to a CSV file (unit_id,translation) containing replacements.",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(
            f"Error: Database file does not exist: {args.db}",
            file=sys.stderr,
        )
        return 1

    if (args.unit_id and not args.translation) or (
        args.translation and not args.unit_id
    ):
        print(
            "Error: Both --unit-id and --translation must be provided together.",
            file=sys.stderr,
        )
        return 1

    if not args.unit_id and not args.file:
        print(
            "Error: You must specify --unit-id and --translation, or a --file with translations.",
            file=sys.stderr,
        )
        return 1

    replacements: dict[str, str] = {}
    if args.file:
        try:
            file_replacements = load_translations_file(args.file)
            replacements.update(file_replacements)
            print(
                f"Loaded {len(file_replacements)} translation replacement(s) from {args.file}."
            )
        except (OSError, csv.Error, ValueError) as e:
            print(f"Error reading translations file: {e}", file=sys.stderr)
            return 1

    if args.unit_id and args.translation is not None:
        replacements[args.unit_id] = args.translation

    if not replacements:
        print("Error: No valid translations found to apply.", file=sys.stderr)
        return 1

    count = replace_translations(args.db, replacements)
    print(f"Successfully applied {count} translation replacement(s) in {args.db}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
