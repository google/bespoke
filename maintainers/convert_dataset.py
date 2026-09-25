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

"""Tool to convert an existing SQLite dataset .db to a new native language."""

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

from bespoke import database, languages, llm, translation
from bespoke.card import CARDS_DIR, Card, encode_audio_to_ogg


async def convert_dataset(
    input_db_path: Path | str,
    to_native: languages.Language | str,
    output_db_path: Path | str | None = None,
    llm_client: llm.LlmClient | None = None,
    parallelism: int = 16,
) -> Path:
    """Converts a dataset SQLite .db to a new native language directly."""
    input_db_path = Path(input_db_path)
    if not input_db_path.is_file():
        raise FileNotFoundError(f"Input database not found: {input_db_path}")

    meta = database.load_metadata_from_db(input_db_path)
    target_code = meta.get("target_language")
    if not target_code:
        raise ValueError(f"Missing target_language in metadata for {input_db_path}")
    target_lang = database.resolve_language(target_code)
    new_native_lang = database.resolve_language(to_native)

    if output_db_path is None:
        output_db_path = database.get_dataset_db_path(
            input_db_path.parent, target_lang, new_native_lang
        )
    output_db_path = Path(output_db_path)

    if llm_client is None:
        llm_client = llm.get_llm_client()

    cards = database.load_all_cards_from_db(input_db_path)
    vocabulary = database.load_vocabulary_from_db(input_db_path)
    card_index = database.load_index_from_db(input_db_path)

    # Retain existing target audio and slow audio
    audio_data: dict[str, bytes] = {}
    for c in cards:
        for audio_ref in [c.audio_filename, c.slow_audio_filename]:
            if audio_ref:
                base_name = Path(audio_ref).name
                if base_name not in audio_data:
                    blob = database.get_audio_blob(input_db_path, audio_ref)
                    if blob is not None:
                        audio_data[base_name] = blob

    print(f"Translating {len(vocabulary)} vocabulary units...")
    new_translations = await translation.translate_units(
        units=vocabulary,
        target_language=target_lang,
        native_language=new_native_lang,
        llm_client=llm_client,
        parallelism=parallelism,
    )

    print(f"Translating {len(cards)} cards and generating audio...")
    semaphore = asyncio.Semaphore(parallelism)

    @llm.standard_retry
    async def process_card(
        index: int, target_card: Card
    ) -> tuple[int, Card, str, bytes]:
        async with semaphore:
            raw_translated = await llm_client.translate(
                target_card.sentence, new_native_lang
            )
            new_native_sentence = raw_translated.strip().strip("\"'“”«»‘`")
            audio_array = await llm_client.speak(new_native_sentence, slowly=False)
            ogg_bytes = await encode_audio_to_ogg(audio_array)

            native_hash = hashlib.sha256(
                new_native_sentence.encode("utf-8")
            ).hexdigest()
            native_filename = f"cards/{target_lang.code_name}_{new_native_lang.code_name}/{native_hash}.ogg"
            base_native_filename = f"{native_hash}.ogg"

            new_card = Card(
                id=target_card.id,
                sentence=target_card.sentence,
                native_sentence=new_native_sentence,
                phonetic=target_card.phonetic,
                audio_filename=target_card.audio_filename,
                slow_audio_filename=target_card.slow_audio_filename,
                native_audio_filename=native_filename,
                unit_tags=target_card.unit_tags,
                notes=target_card.notes,
            )
            return index, new_card, base_native_filename, ogg_bytes

    tasks = [process_card(index, c) for index, c in enumerate(cards)]
    converted_cards: list[Card | None] = [None] * len(cards)
    for index, future in enumerate(asyncio.as_completed(tasks), 1):
        card_position, new_card, base_native_filename, ogg_bytes = await future
        converted_cards[card_position] = new_card
        audio_data[base_native_filename] = ogg_bytes
        if index % 1000 == 0 or index == len(cards):
            print(f"Converted {index}/{len(cards)} cards...")

    new_cards: list[Card] = [c for c in converted_cards if c is not None]

    database.write_dataset_to_db(
        output_db_path=output_db_path,
        target=target_lang,
        native=new_native_lang,
        cards=new_cards,
        audio_data=audio_data,
        translations=new_translations,
        vocabulary=vocabulary,
        card_index=card_index,
    )

    if not database.verify_dataset_db(output_db_path):
        raise RuntimeError(
            f"Verification failed for converted database: {output_db_path}"
        )

    return output_db_path


async def main_async() -> None:
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
        description="Convert a dataset .db into a new native language."
    )
    parser.add_argument(
        "--target",
        type=str,
        required=True,
        choices=list(target_choices),
        help="The language of the dataset you are learning.",
    )
    parser.add_argument(
        "--from-native",
        type=str,
        required=True,
        choices=list(native_choices),
        help="The current native language of the source dataset.",
    )
    parser.add_argument(
        "--to-native",
        type=str,
        required=True,
        choices=list(native_choices),
        help="The new native language to translate into.",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        default=16,
        help="Parallelism limit for LLM calls (default: 16).",
    )
    args = parser.parse_args()

    target_lang = database.resolve_language(args.target)
    from_native_lang = database.resolve_language(args.from_native)
    to_native_lang = database.resolve_language(args.to_native)

    input_db_path = database.get_dataset_db_path(
        CARDS_DIR, target_lang, from_native_lang
    )

    if not input_db_path.exists():
        print(
            f"Error: Source dataset DB not found at '{input_db_path}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_db_path = database.get_dataset_db_path(
        CARDS_DIR, target_lang, to_native_lang
    )

    llm_client = llm.get_llm_client()
    print(
        f"Converting dataset {input_db_path} ({target_lang.writing_system}) to native language: "
        f"{to_native_lang.writing_system} ({output_db_path})..."
    )
    result_path = await convert_dataset(
        input_db_path=input_db_path,
        to_native=to_native_lang,
        output_db_path=output_db_path,
        llm_client=llm_client,
        parallelism=args.parallelism,
    )
    size_mb = result_path.stat().st_size / (1024 * 1024)
    print(f"Successfully converted dataset: {result_path} ({size_mb:.2f} MB)")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
