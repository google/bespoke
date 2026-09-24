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

"""Class that represent flash cards."""

import asyncio
import hashlib
import json
import os
import random
from collections.abc import Iterable
from pathlib import Path
from typing import Self

import aiofiles  # type: ignore
import numpy as np
import pydantic

from bespoke import database, llm
from bespoke.languages import Language
from bespoke.unit import Unit, UnitTag, UnitTags

CARDS_DIR = Path("cards")


class Card(pydantic.BaseModel):
    id: str
    sentence: str
    native_sentence: str
    audio_filename: str
    slow_audio_filename: str
    native_audio_filename: str
    phonetic: str | None
    unit_tags: UnitTags
    notes: list[str]

    model_config = pydantic.ConfigDict(frozen=True)

    def unit_ids(self) -> list[str]:
        return list({t.unit_id for t in self.unit_tags if t.unit_id})

    @pydantic.model_validator(mode="after")
    def _verify_tags_sorted(self) -> "Card":
        sentence_index = 0
        for tag in self.unit_tags:
            start_idx = self.sentence.find(tag.occurance, sentence_index)
            if start_idx < 0:
                raise ValueError(
                    f"Tag occurance '{tag.occurance}' not found in sentence after index {sentence_index}"
                )
            sentence_index = start_idx + len(tag.occurance)
        return self

    def split_into_parts(self) -> list[UnitTag]:
        parts = []
        sentence_index = 0
        for tag in self.unit_tags:
            start_idx = self.sentence.find(tag.occurance, sentence_index)
            if start_idx >= 0:
                if start_idx > sentence_index:
                    parts.append(
                        UnitTag(
                            occurance=self.sentence[sentence_index:start_idx],
                            unit_id="",
                        )
                    )
                parts.append(tag)
                sentence_index = start_idx + len(tag.occurance)
        if sentence_index < len(self.sentence):
            parts.append(UnitTag(occurance=self.sentence[sentence_index:], unit_id=""))
        return parts

    def __str__(self) -> str:
        parts = []
        for tag in self.split_into_parts():
            if not tag.unit_id:
                parts.append(tag.occurance)
            else:
                parts.append(f"[{tag.occurance}]({tag.unit_id})")
        return f"Card: {''.join(parts)} = {self.native_sentence}"

    def write_json(self, directory: Path) -> None:
        path = directory / f"{self.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json())

    @classmethod
    def load(cls, directory: Path, card_id: str) -> "Card | None":
        path = directory / f"{card_id}.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.model_validate_json(f.read())
        except (OSError, pydantic.ValidationError) as e:
            print(f"Failed to read card from file '{path}': {e}")
        return None

    @classmethod
    async def load_async(cls, directory: Path, card_id: str) -> "Card | None":
        path = directory / f"{card_id}.json"
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                return cls.model_validate_json(content)
        except (OSError, pydantic.ValidationError) as e:
            print(f"Failed to read card from file '{path}': {e}")
        return None


async def encode_audio_to_ogg(audio: np.ndarray, bitrate: str = "16k") -> bytes:
    """Encodes raw int16 24kHz mono PCM audio array into OGG Opus bytes via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "s16le",
        "-ar",
        "24000",
        "-ac",
        "1",
        "-i",
        "pipe:0",
        "-b:a",
        bitrate,
        "-c:a",
        "libopus",
        "-vbr",
        "on",
        "-f",
        "ogg",
        "pipe:1",
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input=audio.tobytes())
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg audio encoding failed: {stderr.decode()}")
    return stdout


async def _write_ogg(audio: np.ndarray, filename: str, bitrate: str = "16k") -> None:
    data = await encode_audio_to_ogg(audio, bitrate=bitrate)
    async with aiofiles.open(filename, "wb") as f:
        await f.write(data)


async def _write_audio_file(
    llm_client: llm.LlmClient,
    *,
    directory: Path,
    sentence: str,
    slowly: bool,
) -> str:
    sentence_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
    if slowly:
        suffix = "_slow"
    else:
        suffix = ""
    filename = str(directory / f"{sentence_hash}{suffix}.ogg")
    if not os.path.exists(filename):
        audio = await llm_client.speak(sentence, slowly=slowly)
        await _write_ogg(audio, filename)
    return filename


async def _read_cards(directory: Path) -> list[Card]:
    semaphore = asyncio.Semaphore(16)

    async def read_card_file(card_id: str) -> Card | None:
        async with semaphore:
            return await Card.load_async(directory, card_id)

    tasks = [read_card_file(p.stem) for p in directory.glob("*.json")]
    cards = await asyncio.gather(*tasks)
    return [card for card in cards if card is not None]


def _print_or_write_list(items: Iterable[str], name: str) -> None:
    if not items:
        return
    items_list = sorted(items)
    count = len(items_list)
    if count <= 100:
        print(name)
        for item in items_list:
            print(item)
    else:
        filename = name.lower().replace(" ", "_") + ".txt"
        with open(filename, "w", encoding="utf-8") as f:
            for item in items_list:
                f.write(f"{item}\n")
        print(f"{name} written to {filename}")
        print(f"Sample of 10 / {count}:")
        for item in items_list[:10]:
            print(item)


class CardIndex:
    def __init__(
        self,
        target_language: Language,
        native_language: Language,
    ) -> None:
        self._target_language = target_language
        self._native_language = native_language
        target = target_language.code_name
        native = native_language.code_name
        self._index_path = CARDS_DIR / f"index_{target}_{native}.json"
        self._card_directory = CARDS_DIR / f"{target}_{native}"
        self._db_path: Path | None = None
        self._index: dict[str, list[str]] = {}
        self._cache: dict[str, Card] = {}
        self._card_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, target_language: Language, native_language: Language) -> Self:
        obj = cls(target_language, native_language)
        try:
            with open(obj._index_path, "r", encoding="utf-8") as f:
                obj._index = json.load(f)
            if obj._index:
                use_def = " - " in next(iter(obj._index.keys()))
                target_language.initialize(use_definition=use_def)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            print(f"Unable to open {obj._index_path}, creating empty CardIndex.")
        return obj

    @classmethod
    def load_from_db(
        cls,
        target_language: Language,
        native_language: Language,
        db_path: Path | str,
    ) -> Self:
        obj = cls(target_language, native_language)
        obj._db_path = Path(db_path)
        obj._index = database.load_index_from_db(obj._db_path)
        return obj

    async def restart(self) -> None:
        self._index = {}
        self._cache = {}
        cards = await _read_cards(self._card_directory)
        print(f"Starting CardIndex with {len(cards)} cards.")
        for card in cards:
            self._add(card)
        self.save()

    async def check(self) -> None:
        available_cards = await _read_cards(self._card_directory)
        cards = await self.all_cards()
        language_system = self._target_language.writing_system
        print(f"Found {len(cards)} cards for {language_system}")
        available_card_ids = {card.id for card in available_cards}
        indexed_card_ids = {card.id for card in cards}
        missing_in_index = available_card_ids - indexed_card_ids
        missing_on_disk = indexed_card_ids - available_card_ids
        _print_or_write_list(missing_in_index, "Cards missing in index")
        _print_or_write_list(missing_on_disk, "Cards missing on disk")

        audio_filenames = set()
        for path in self._card_directory.glob("*.ogg"):
            audio_filenames.add(str(path))
        card_filenames = set()
        for card in cards:
            card_filenames.add(card.audio_filename)
            card_filenames.add(card.slow_audio_filename)
            card_filenames.add(card.native_audio_filename)
            if card.audio_filename not in audio_filenames:
                print(f"Missing target audio file for '{card.id}'")
            if card.slow_audio_filename not in audio_filenames:
                print(f"Missing slow audio file for '{card.id}'")
            if card.native_audio_filename not in audio_filenames:
                print(f"Missing native audio file for '{card.id}'")
        extra_filenames = audio_filenames - card_filenames
        _print_or_write_list(extra_filenames, "Unused audio files")

    def save(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f)

    def _get_cards_from_db(self, card_ids: list[str]) -> dict[str, Card]:
        if self._db_path is None or not card_ids:
            return {}
        return database.load_cards_from_db(self._db_path, card_ids)

    def _load_card(self, card_id: str) -> Card | None:
        if card_id in self._cache:
            return self._cache[card_id]
        card = Card.load(self._card_directory, card_id)
        if card is not None:
            self._cache[card_id] = card
        return card

    async def _load_card_async(self, card_id: str) -> Card | None:
        if card_id in self._cache:
            return self._cache[card_id]
        card = await Card.load_async(self._card_directory, card_id)
        if card is not None:
            self._cache[card_id] = card
        return card

    def cards(self, unit: Unit, limit: int | None = None) -> list[Card]:
        card_ids = self._index.get(unit.id(), [])
        if limit is not None:
            card_ids = random.sample(card_ids, min(limit, len(card_ids)))
        if self._db_path is not None:
            missing_ids = [cid for cid in card_ids if cid not in self._cache]
            if missing_ids:
                loaded = self._get_cards_from_db(missing_ids)
                self._cache.update(loaded)
            return [self._cache[cid] for cid in card_ids if cid in self._cache]
        cards = []
        for card_id in card_ids:
            card = self._load_card(card_id)
            if card is not None:
                cards.append(card)
        return cards

    async def all_cards(self) -> list[Card]:
        if self._db_path is not None and self._db_path.is_file():
            db_cards = database.load_all_cards_from_db(self._db_path)
            for card in db_cards:
                self._cache[card.id] = card
            return db_cards

        card_ids = set()
        for unit_cards in self._index.values():
            card_ids.update(unit_cards)
        semaphore = asyncio.Semaphore(16)

        async def read_card_file(card_id: str) -> Card | None:
            async with semaphore:
                return await self._load_card_async(card_id)

        tasks = [read_card_file(card_id) for card_id in card_ids]
        raw_cards = await asyncio.gather(*tasks)
        return [card for card in raw_cards if card is not None]

    def size(self, unit: Unit) -> int:
        return len(self._index.get(unit.id(), []))

    async def remove(self, card_id: str) -> None:
        if self._db_path is not None:
            print(f"Cannot remove card '{card_id}' from dataset db '{self._db_path}'")
            return
        card = await self._load_card_async(card_id)
        if card_id in self._cache:
            del self._cache[card_id]
        if card is None:
            print(f"Card JSON not found: {self._card_directory / f'{card_id}.json'}")
            for unit_id in list(self._index.keys()):
                if card_id in self._index[unit_id]:
                    self._index[unit_id].remove(card_id)
                    if not self._index[unit_id]:
                        del self._index[unit_id]
            return

        for path in [card.audio_filename, card.slow_audio_filename]:
            if path:
                try:
                    Path(path).unlink()
                except OSError as e:
                    print(f"Error deleting audio {path}: {e}")
        if card.native_audio_filename:
            try:
                other_cards = await self.all_cards()
                shared = any(
                    other.id != card_id
                    and other.native_audio_filename == card.native_audio_filename
                    for other in other_cards
                )
                if not shared:
                    Path(card.native_audio_filename).unlink()
            except OSError as e:
                print(f"Error deleting native audio {card.native_audio_filename}: {e}")

        card_json_path = self._card_directory / f"{card_id}.json"
        try:
            card_json_path.unlink()
        except OSError as e:
            print(f"Error deleting card JSON {card_json_path}: {e}")

        for unit_id in card.unit_ids():
            if unit_id in self._index and card_id in self._index[unit_id]:
                self._index[unit_id].remove(card_id)
                if not self._index[unit_id]:
                    del self._index[unit_id]

    def _add(self, card: Card) -> None:
        for unit in card.unit_ids():
            card_ids = self._index.get(unit, [])
            card_ids.append(card.id)
            self._index[unit] = card_ids
        self._cache[card.id] = card

    @llm.standard_retry
    async def create_card(
        self,
        llm_client: llm.LlmClient,
        sentence: str,
        unit_tags: UnitTags,
        notes: list[str] | None = None,
    ) -> Card | None:
        if notes is None:
            notes = []
        id = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
        native_sentence = await llm_client.translate(sentence, self._native_language)
        phonetic = await llm_client.to_phonetic(sentence, self._target_language)
        if not await llm_client.check_card(
            sentence=sentence,
            native_sentence=native_sentence,
            phonetic=phonetic,
            unit_tags=unit_tags,
            target_language=self._target_language,
            native_language=self._native_language,
        ):
            tag_details = ", ".join(f"{t.occurance}->{t.unit_id}" for t in unit_tags)
            phonetic_details = f", phonetic='{phonetic}'" if phonetic else ""
            print(
                f"Discarding invalid card: sentence='{sentence}', "
                f"translation='{native_sentence}'{phonetic_details}, "
                f"tags=[{tag_details}]"
            )
            return None
        audio_filename = await _write_audio_file(
            llm_client,
            directory=self._card_directory,
            sentence=sentence,
            slowly=False,
        )
        slow_audio_filename = await _write_audio_file(
            llm_client,
            directory=self._card_directory,
            sentence=sentence,
            slowly=True,
        )
        native_audio_filename = await _write_audio_file(
            llm_client,
            directory=self._card_directory,
            sentence=native_sentence,
            slowly=False,
        )
        card = Card(
            id=id,
            sentence=sentence,
            native_sentence=native_sentence,
            audio_filename=audio_filename,
            slow_audio_filename=slow_audio_filename,
            native_audio_filename=native_audio_filename,
            phonetic=phonetic,
            unit_tags=unit_tags,
            notes=notes,
        )
        card.write_json(self._card_directory)
        self._add(card)
        return card
