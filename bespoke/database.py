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

"""Database operations using SQLite for cards and vocabulary."""

from __future__ import annotations

import csv
from datetime import datetime
from datetime import timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any

from bespoke import card
from bespoke import languages
from bespoke import unit

CARDS_DIR: Path = Path("cards")
logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    sentence TEXT NOT NULL,
    native_sentence TEXT NOT NULL,
    phonetic TEXT,
    audio_filename TEXT NOT NULL,
    slow_audio_filename TEXT NOT NULL,
    native_audio_filename TEXT NOT NULL,
    unit_tags_json TEXT NOT NULL,
    notes_json TEXT NOT NULL,
    json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audio (
    filename TEXT PRIMARY KEY,
    data BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS translations (
    unit_id TEXT PRIMARY KEY,
    translation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vocabulary (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    definition TEXT,
    difficulty TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_index (
    unit_id TEXT NOT NULL,
    card_id TEXT NOT NULL,
    PRIMARY KEY (unit_id, card_id)
);
"""

EXPECTED_TABLES: dict[str, set[str]] = {
    "metadata": {"key", "value"},
    "cards": {
        "id",
        "sentence",
        "native_sentence",
        "phonetic",
        "audio_filename",
        "slow_audio_filename",
        "native_audio_filename",
        "unit_tags_json",
        "notes_json",
        "json",
    },
    "audio": {"filename", "data"},
    "translations": {"unit_id", "translation"},
    "vocabulary": {"id", "name", "definition", "difficulty"},
    "card_index": {"unit_id", "card_id"},
}


def _resolve_audio_file(
    audio_ref: str, cards_dir: Path, card_subdir: Path
) -> Path | None:
    if not audio_ref:
        return None
    p = Path(audio_ref)
    candidates = [
        p,
        cards_dir / p,
        card_subdir / p,
        card_subdir / p.name,
        cards_dir / p.name,
    ]
    if audio_ref.startswith("cards/"):
        stripped = audio_ref[len("cards/") :]
        candidates.extend(
            [
                cards_dir / stripped,
                card_subdir / Path(stripped).name,
                cards_dir / Path(stripped).name,
            ]
        )
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def resolve_language(
    language: str | languages.Language,
) -> languages.Language:
    """Resolves a language string or returns the Language object."""
    if isinstance(language, languages.Language):
        return language
    normalized = str(language).strip().lower().replace(" ", "_")
    if normalized in languages.LANGUAGES:
        return languages.LANGUAGES[normalized]
    for language_item in languages.LANGUAGES.values():
        if (
            language_item.code_name.lower() == normalized
            or language_item.writing_system.lower().replace(" ", "_") == normalized
            or language_item.name.lower().replace(" ", "_") == normalized
        ):
            return language_item
    raise ValueError(
        f"Unknown language '{language}'. Available: {list(languages.LANGUAGES.keys())}"
    )


def get_audio_blob(db_path: Path | str, filename: str) -> bytes | None:
    """Retrieves raw binary audio data from the database."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return None
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM audio WHERE filename = ?", (filename,))
        row = cursor.fetchone()
        if row:
            return bytes(row[0])
        basename = Path(filename).name
        if basename != filename:
            cursor.execute("SELECT data FROM audio WHERE filename = ?", (basename,))
            row = cursor.fetchone()
            if row:
                return bytes(row[0])
        return None
    finally:
        conn.close()


def load_card_from_db(db_path: Path | str, card_id: str) -> card.Card | None:
    """Loads a single Card from the database."""
    cards = load_cards_from_db(db_path, [card_id])
    return cards.get(card_id)


def load_cards_from_db(
    db_path: Path | str, card_ids: list[str]
) -> dict[str, card.Card]:
    """Loads a batch of Cards from the database by ID."""
    db_path = Path(db_path)
    if not db_path.is_file() or not card_ids:
        return {}
    result: dict[str, card.Card] = {}
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        chunk_size = 900
        for i in range(0, len(card_ids), chunk_size):
            chunk = card_ids[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            cursor.execute(
                f"SELECT id, json FROM cards WHERE id IN ({placeholders})",
                chunk,
            )
            for cid, json_data in cursor.fetchall():
                try:
                    c = card.Card.model_validate_json(json_data)
                except Exception:
                    old_c = card.OldCard.model_validate_json(json_data)
                    c = old_c.to_card()
                result[cid] = c
    finally:
        conn.close()
    return result


def load_all_cards_from_db(db_path: Path | str) -> list[card.Card]:
    """Loads all Card objects from the database."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return []
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, json FROM cards")
        cards = []
        for _, json_data in cursor.fetchall():
            try:
                c = card.Card.model_validate_json(json_data)
            except Exception:
                old_c = card.OldCard.model_validate_json(json_data)
                c = old_c.to_card()
            cards.append(c)
        return cards
    finally:
        conn.close()


def load_translations_from_db(db_path: Path | str) -> dict[str, str]:
    """Loads unit translations dictionary from the database."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT unit_id, translation FROM translations")
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def load_vocabulary_from_db(db_path: Path | str) -> list[unit.Unit]:
    """Loads Unit objects from the database vocabulary table."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return []
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, definition, difficulty FROM vocabulary")
        units: list[unit.Unit] = []
        for _, name, definition, diff_str in cursor.fetchall():
            difficulty = languages.Difficulty(diff_str)
            if definition:
                units.append(
                    unit.DictionaryUnit(
                        name=name, definition=definition, difficulty=difficulty
                    )
                )
            else:
                units.append(unit.WordUnit(word=name, difficulty=difficulty))
        return units
    finally:
        conn.close()


def load_index_from_db(db_path: Path | str) -> dict[str, list[str]]:
    """Loads card index mapping from the database."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT unit_id, card_id FROM card_index")
        index_map: dict[str, list[str]] = {}
        for unit_id, card_id in cursor.fetchall():
            index_map.setdefault(unit_id, []).append(card_id)
        return index_map
    finally:
        conn.close()


def load_metadata_from_db(db_path: Path | str) -> dict[str, str]:
    """Loads metadata key-value dictionary from the database."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM metadata")
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def export_dataset_to_db(
    cards_dir: Path | str = CARDS_DIR,
    target: languages.Language | str = "japanese",
    native: languages.Language | str = "english",
    output_db_path: Path | str | None = None,
) -> Path:
    """Exports cards, audio, translations, vocabulary, and index to SQLite."""
    cards_dir = Path(cards_dir)
    target = resolve_language(target)
    native = resolve_language(native)

    target_code = target.code_name
    native_code = native.code_name
    card_subdir = cards_dir / f"{target_code}_{native_code}"

    if output_db_path is None:
        output_db_path = cards_dir / f"{target_code}.db"
    output_db_path = Path(output_db_path)
    output_db_path.parent.mkdir(parents=True, exist_ok=True)
    if output_db_path.exists():
        output_db_path.unlink()

    # 1. Discover card files
    card_paths: list[Path] = []
    if card_subdir.is_dir():
        card_paths.extend(sorted(card_subdir.glob("*.json")))
    if not card_paths and cards_dir.is_dir():
        card_paths.extend(
            sorted(
                [p for p in cards_dir.glob("*.json") if not p.name.startswith("index_")]
            )
        )

    cards: list[card.Card] = []
    for card_path in card_paths:
        try:
            with open(card_path, "r", encoding="utf-8") as f:
                content = f.read()
                try:
                    c = card.Card.model_validate_json(content)
                except Exception:
                    old_c = card.OldCard.model_validate_json(content)
                    c = old_c.to_card()
                cards.append(c)
        except Exception as e:
            logger.warning("Failed to parse card at %s: %s", card_path, e)

    # 2. Discover audio files
    audio_data: dict[str, bytes] = {}
    for c in cards:
        for audio_ref in [
            c.audio_filename,
            c.slow_audio_filename,
            c.native_audio_filename,
        ]:
            if audio_ref:
                base_name = Path(audio_ref).name
                if base_name not in audio_data:
                    found_path = _resolve_audio_file(audio_ref, cards_dir, card_subdir)
                    if found_path is not None:
                        audio_data[base_name] = found_path.read_bytes()
                    else:
                        logger.warning(
                            "Audio file reference '%s' for card '%s' not found on disk",
                            audio_ref,
                            c.id,
                        )

    if card_subdir.is_dir():
        for ogg_path in sorted(card_subdir.glob("*.ogg")):
            if ogg_path.name not in audio_data:
                audio_data[ogg_path.name] = ogg_path.read_bytes()

    # 3. Discover translations
    translations: dict[str, str] = {}
    trans_candidates = [
        cards_dir / f"translations_{target_code}_{native_code}.csv",
        card_subdir / "translations.csv",
        cards_dir / "translations.csv",
    ]
    for trans_path in trans_candidates:
        if trans_path.is_file():
            with open(trans_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "unit_id" in row and "translation" in row:
                        translations[row["unit_id"]] = row["translation"]
            break

    # 4. Discover vocabulary
    vocab_entries: dict[str, tuple[str, str, str, str]] = {}
    vocab_candidates = [
        cards_dir / f"vocabulary_{target_code}.csv",
        cards_dir / target_code / "vocabulary.csv",
        cards_dir / "vocabulary.csv",
    ]
    for vocab_path in vocab_candidates:
        if vocab_path.is_file():
            with open(vocab_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get("name", "")
                    definition = row.get("definition", "")
                    diff = row.get("difficulty", "A1")
                    unit_id = f"{name} - {definition}" if definition else name
                    vocab_entries[unit_id] = (unit_id, name, definition, diff)
            break

    if not vocab_entries:
        for u in target.units():
            definition = u.definition() if isinstance(u, unit.DictionaryUnit) else ""
            diff = str(u.difficulty())
            vocab_entries[u.id()] = (u.id(), u.name(), definition, diff)

    # 5. Discover index
    index_map: dict[str, list[str]] = {}
    index_candidates = [
        cards_dir / f"index_{target_code}_{native_code}.json",
        card_subdir / "index.json",
    ]
    for index_path in index_candidates:
        if index_path.is_file():
            with open(index_path, "r", encoding="utf-8") as f:
                index_map = json.load(f)
            break

    if not index_map:
        for c in cards:
            for unit_id in c.unit_ids():
                index_map.setdefault(unit_id, []).append(c.id)

    # 6. Write to SQLite
    conn = sqlite3.connect(output_db_path)
    try:
        with conn:
            conn.executescript(CREATE_TABLES_SQL)

            # Metadata
            now_iso = datetime.now(timezone.utc).isoformat()
            metadata = {
                "target_language": target_code,
                "native_language": native_code,
                "target_language_name": target.name,
                "native_language_name": native.name,
                "created_at": now_iso,
                "version": "1.0",
                "card_count": str(len(cards)),
                "audio_count": str(len(audio_data)),
                "vocabulary_count": str(len(vocab_entries)),
                "translation_count": str(len(translations)),
            }
            conn.executemany(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                list(metadata.items()),
            )

            # Cards
            cards_rows = [
                (
                    c.id,
                    c.sentence,
                    c.native_sentence,
                    c.phonetic,
                    c.audio_filename,
                    c.slow_audio_filename,
                    c.native_audio_filename,
                    json.dumps(
                        [t.model_dump() for t in c.unit_tags],
                        ensure_ascii=False,
                    ),
                    json.dumps(c.notes, ensure_ascii=False),
                    c.model_dump_json(),
                )
                for c in cards
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO cards (
                    id, sentence, native_sentence, phonetic,
                    audio_filename, slow_audio_filename, native_audio_filename,
                    unit_tags_json, notes_json, json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                cards_rows,
            )

            # Audio
            audio_rows = [(fn, data) for fn, data in audio_data.items()]
            conn.executemany(
                "INSERT OR REPLACE INTO audio (filename, data) VALUES (?, ?)",
                audio_rows,
            )

            # Translations
            trans_rows = [(uid, trans) for uid, trans in translations.items()]
            conn.executemany(
                "INSERT OR REPLACE INTO translations (unit_id, translation) VALUES (?, ?)",
                trans_rows,
            )

            # Vocabulary
            vocab_rows = list(vocab_entries.values())
            conn.executemany(
                "INSERT OR REPLACE INTO vocabulary (id, name, definition, difficulty) VALUES (?, ?, ?, ?)",
                vocab_rows,
            )

            # Card Index
            index_rows = []
            for unit_id, card_ids in index_map.items():
                for card_id in card_ids:
                    index_rows.append((unit_id, card_id))
            conn.executemany(
                "INSERT OR REPLACE INTO card_index (unit_id, card_id) VALUES (?, ?)",
                index_rows,
            )
        conn.execute("VACUUM")
    finally:
        conn.close()

    return output_db_path


def import_dataset_from_db(
    db_path: Path | str,
    output_dir: Path | str,
) -> None:
    """Extracts dataset contents from SQLite to filesystem directory."""
    db_path = Path(db_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    meta = load_metadata_from_db(db_path)
    target_code = meta.get("target_language", "target")
    native_code = meta.get("native_language", "native")
    card_subdir = output_dir / f"{target_code}_{native_code}"
    card_subdir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()

        # 1. Extract Cards
        cursor.execute("SELECT id, json FROM cards")
        for card_id, card_json in cursor.fetchall():
            card_file = card_subdir / f"{card_id}.json"
            with open(card_file, "w", encoding="utf-8") as f:
                f.write(card_json)

        # 2. Extract Audio
        cursor.execute("SELECT filename, data FROM audio")
        for filename, data in cursor.fetchall():
            base_name = Path(filename).name
            target_audio_file = card_subdir / base_name
            target_audio_file.write_bytes(data)

        # 3. Extract Translations
        cursor.execute("SELECT unit_id, translation FROM translations")
        trans_rows = cursor.fetchall()
        if trans_rows:
            trans_file = output_dir / f"translations_{target_code}_{native_code}.csv"
            with open(trans_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["unit_id", "translation"])
                for uid, trans in trans_rows:
                    writer.writerow([uid, trans])

        # 4. Extract Vocabulary
        cursor.execute("SELECT id, name, definition, difficulty FROM vocabulary")
        vocab_rows = cursor.fetchall()
        if vocab_rows:
            vocab_file = output_dir / f"vocabulary_{target_code}.csv"
            with open(vocab_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "definition", "difficulty"])
                for _, name, definition, diff in vocab_rows:
                    writer.writerow([name, definition, diff])

        # 5. Extract Card Index
        cursor.execute("SELECT unit_id, card_id FROM card_index")
        index_map: dict[str, list[str]] = {}
        for unit_id, card_id in cursor.fetchall():
            index_map.setdefault(unit_id, []).append(card_id)
        if index_map:
            index_file = output_dir / f"index_{target_code}_{native_code}.json"
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index_map, f, indent=2, ensure_ascii=False)
    finally:
        conn.close()


def verify_dataset_db(db_path: Path | str) -> bool:
    """Validates table schemas, audio blobs, JSON parsing, and index integrity."""
    db_path = Path(db_path)
    if not db_path.is_file():
        logger.error("DB file does not exist: %s", db_path)
        return False

    try:
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    except Exception as e:
        logger.error("Failed to connect to SQLite DB: %s", e)
        return False

    try:
        cursor = conn.cursor()

        # 1. Verify tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        for table_name, req_cols in EXPECTED_TABLES.items():
            if table_name not in existing_tables:
                logger.error("Missing table: %s", table_name)
                return False
            cursor.execute(f"PRAGMA table_info({table_name})")
            table_cols = {row[1] for row in cursor.fetchall()}
            missing_cols = req_cols - table_cols
            if missing_cols:
                logger.error("Table %s missing columns: %s", table_name, missing_cols)
                return False

        # 2. Verify metadata
        cursor.execute("SELECT key, value FROM metadata")
        meta = {row[0]: row[1] for row in cursor.fetchall()}
        if "target_language" not in meta or not meta["target_language"]:
            logger.error("Missing target_language in metadata")
            return False
        if "native_language" not in meta or not meta["native_language"]:
            logger.error("Missing native_language in metadata")
            return False

        # 3. Verify audio map
        cursor.execute("SELECT filename, LENGTH(data) FROM audio")
        audio_rows = cursor.fetchall()
        audio_map: dict[str, int] = {}
        for fn, length in audio_rows:
            if length is None or length <= 0:
                logger.error("Audio file '%s' has empty binary data", fn)
                return False
            audio_map[fn] = length
            audio_map[Path(fn).name] = length

        # 4. Verify cards
        cursor.execute(
            """
            SELECT id, sentence, native_sentence, phonetic,
                   audio_filename, slow_audio_filename, native_audio_filename,
                   unit_tags_json, notes_json, json
            FROM cards
            """
        )
        card_rows = cursor.fetchall()
        card_ids_in_cards: set[str] = set()
        card_unit_ids_map: dict[str, list[str]] = {}

        for row in card_rows:
            (
                c_id,
                sentence,
                native_sentence,
                phonetic,
                audio_fn,
                slow_audio_fn,
                native_audio_fn,
                unit_tags_json,
                notes_json,
                full_json,
            ) = row

            if not c_id or not sentence or not native_sentence:
                logger.error("Card has empty required text fields: %s", c_id)
                return False

            card_ids_in_cards.add(c_id)

            try:
                c = card.Card.model_validate_json(full_json)
            except Exception as e:
                try:
                    old_c = card.OldCard.model_validate_json(full_json)
                    c = old_c.to_card()
                except Exception as e2:
                    logger.error("Invalid card JSON for %s: %s / %s", c_id, e, e2)
                    return False

            try:
                parsed_tags = json.loads(unit_tags_json)
                if not isinstance(parsed_tags, list):
                    logger.error("unit_tags_json is not a list for %s", c_id)
                    return False
            except Exception as e:
                logger.error("Invalid unit_tags_json for %s: %s", c_id, e)
                return False

            try:
                parsed_notes = json.loads(notes_json)
                if not isinstance(parsed_notes, list):
                    logger.error("notes_json is not a list for %s", c_id)
                    return False
            except Exception as e:
                logger.error("Invalid notes_json for %s: %s", c_id, e)
                return False

            for a_fn, field_name in [
                (audio_fn, "audio_filename"),
                (slow_audio_fn, "slow_audio_filename"),
                (native_audio_fn, "native_audio_filename"),
            ]:
                if not a_fn:
                    logger.error("Card %s has empty %s", c_id, field_name)
                    return False
                if a_fn not in audio_map and Path(a_fn).name not in audio_map:
                    logger.error(
                        "Card %s references audio '%s' which is not in audio table",
                        c_id,
                        a_fn,
                    )
                    return False

            card_unit_ids_map[c_id] = c.unit_ids()

        # 5. Verify vocabulary
        cursor.execute("SELECT id, name, definition, difficulty FROM vocabulary")
        for v_id, name, definition, diff_str in cursor.fetchall():
            if not v_id or not name:
                logger.error("Vocabulary row has empty id or name: %s", v_id)
                return False
            try:
                languages.Difficulty(diff_str)
            except ValueError:
                logger.error(
                    "Invalid difficulty '%s' in vocabulary for %s", diff_str, v_id
                )
                return False

        # 6. Verify translations
        cursor.execute("SELECT unit_id, translation FROM translations")
        for u_id, trans in cursor.fetchall():
            if not u_id or not trans:
                logger.error("Translation row has empty unit_id or translation")
                return False

        # 7. Verify index consistency
        cursor.execute("SELECT unit_id, card_id FROM card_index")
        index_rows = cursor.fetchall()
        indexed_card_ids: set[str] = set()
        index_entries_set: set[tuple[str, str]] = set()

        for u_id, c_id in index_rows:
            if c_id not in card_ids_in_cards:
                logger.error("card_index references non-existent card_id '%s'", c_id)
                return False
            indexed_card_ids.add(c_id)
            index_entries_set.add((u_id, c_id))

        for c_id, unit_ids in card_unit_ids_map.items():
            for u_id in unit_ids:
                if (u_id, c_id) not in index_entries_set:
                    logger.error(
                        "Card %s contains unit %s but missing from card_index",
                        c_id,
                        u_id,
                    )
                    return False

        return True
    except Exception as e:
        logger.error("verify_dataset_db encountered exception: %s", e)
        return False
    finally:
        conn.close()


class DatasetDB:
    """Convenience reader for packaged SQLite datasets."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "DatasetDB":
        self._conn = sqlite3.connect(f"file:{self.db_path.resolve()}?mode=ro", uri=True)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                f"file:{self.db_path.resolve()}?mode=ro", uri=True
            )
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_card(self, card_id: str) -> card.Card | None:
        return load_card_from_db(self.db_path, card_id)

    def get_all_cards(self) -> list[card.Card]:
        return load_all_cards_from_db(self.db_path)

    def get_cards_for_unit(self, unit_id: str) -> list[card.Card]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT c.json FROM cards c
            JOIN card_index idx ON c.id = idx.card_id
            WHERE idx.unit_id = ?
            """,
            (unit_id,),
        )
        cards = []
        for (card_json,) in cursor.fetchall():
            try:
                cards.append(card.Card.model_validate_json(card_json))
            except Exception:
                old_card = card.OldCard.model_validate_json(card_json)
                cards.append(old_card.to_card())
        return cards

    def get_audio(self, filename: str) -> bytes | None:
        return get_audio_blob(self.db_path, filename)

    def get_translations(self) -> dict[str, str]:
        return load_translations_from_db(self.db_path)

    def get_vocabulary(self) -> list[unit.Unit]:
        return load_vocabulary_from_db(self.db_path)

    def get_index(self) -> dict[str, list[str]]:
        return load_index_from_db(self.db_path)

    def get_metadata(self) -> dict[str, str]:
        return load_metadata_from_db(self.db_path)

    def verify(self) -> bool:
        return verify_dataset_db(self.db_path)
