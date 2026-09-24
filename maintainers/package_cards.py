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
import csv
import json
from pathlib import Path

import pydantic

from bespoke import card, database, languages, unit
from bespoke.card import CARDS_DIR


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


def package_cards(
    cards_dir: Path | str = CARDS_DIR,
    target: languages.Language | str = "japanese",
    native: languages.Language | str = "english",
    output_db_path: Path | str | None = None,
) -> Path:
    """Packages cards, audio, translations, vocabulary, and index into SQLite."""
    cards_dir = Path(cards_dir)
    target_lang = database.resolve_language(target)
    native_lang = database.resolve_language(native)

    target_code = target_lang.code_name
    native_code = native_lang.code_name
    card_subdir = cards_dir / f"{target_code}_{native_code}"

    if output_db_path is None:
        output_db_path = database.get_dataset_db_path(
            cards_dir, target_lang, native_lang
        )
    output_db_path = Path(output_db_path)

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
                cards.append(card.Card.model_validate_json(f.read()))
        except (
            OSError,
            pydantic.ValidationError,
            ValueError,
            json.JSONDecodeError,
        ) as e:
            print(f"Warning: Failed to parse card at {card_path}: {e}")

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
                        print(
                            f"Warning: Audio file reference '{audio_ref}' for card '{c.id}' not found on disk"
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
        for u in target_lang.units():
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

    database.write_dataset_to_db(
        output_db_path=output_db_path,
        target=target_lang,
        native=native_lang,
        cards=cards,
        audio_data=audio_data,
        translations=translations,
        vocabulary=vocab_entries,
        card_index=index_map,
    )
    return output_db_path


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
    output_path = database.get_dataset_db_path(CARDS_DIR, target, native)

    print(
        f"Packaging {native.writing_system} -> {target.writing_system} into {output_path}..."
    )
    result = package_cards(
        cards_dir=CARDS_DIR,
        target=target,
        native=native,
        output_db_path=output_path,
    )
    size_mb = result.stat().st_size / (1024 * 1024)
    print(f"Successfully packaged dataset: {result} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
