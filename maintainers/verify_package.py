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

"""Tool to verify the integrity and completeness of a packaged dataset."""

import argparse
from pathlib import Path
import sys

from bespoke import database


EXPECTED_TABLES = database.EXPECTED_TABLES
load_metadata_from_db = database.load_metadata_from_db
resolve_language = database.resolve_language
verify_dataset_db = database.verify_dataset_db


def main():
    parser = argparse.ArgumentParser(
        description="Verify the structural and data integrity of a Bespoke SQLite .db dataset."
    )
    parser.add_argument(
        "db_path",
        type=Path,
        help="Path to the database file.",
    )
    args = parser.parse_args()

    db_path = args.db_path
    if not db_path.exists():
        print(f"Error: DB file does not exist: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Verifying dataset package: {db_path} ({db_path.stat().st_size / (1024 * 1024):.2f} MB)..."
    )
    try:
        meta = database.load_metadata_from_db(db_path)
        print(f"Target language : {meta.get('target_language', 'N/A')}")
        print(f"Native language : {meta.get('native_language', 'N/A')}")
        print(f"Cards count     : {meta.get('card_count', 'N/A')}")
        print(f"Audio count     : {meta.get('audio_count', 'N/A')}")
        print(f"Vocabulary count: {meta.get('vocabulary_count', 'N/A')}")
    except Exception as e:
        print(f"Warning: could not read metadata: {e}")

    valid = database.verify_dataset_db(db_path)
    if valid:
        print(
            "Verification PASSED: All tables, schemas, cards, and audio references are valid."
        )
        return 0
    else:
        print("Verification FAILED: Integrity issues found.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
