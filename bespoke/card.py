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

import aiofiles  # type: ignore
import asyncio
import hashlib
import json
import numpy as np
import os
from pathlib import Path
import pydantic
from typing import Self

from bespoke.languages import Language
from bespoke import llm
from bespoke.unit import Unit
from bespoke.unit import UnitTag
from bespoke.unit import UnitTags

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
        return list(set(t.unit_id for t in self.unit_tags if t.unit_id))

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
                content = f.read()
                try:
                    return cls.model_validate_json(content)
                except pydantic.ValidationError:
                    try:
                        old_card = OldCard.model_validate_json(content)
                        return old_card.to_card()
                    except pydantic.ValidationError:
                        print(f"Failed to read card from file '{path}'")
        except OSError as e:
            print(f"An error occurred while accessing '{path}': {e}")
        return None

    @classmethod
    async def load_async(cls, directory: Path, card_id: str) -> "Card | None":
        path = directory / f"{card_id}.json"
        try:
            async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                try:
                    return cls.model_validate_json(content)
                except pydantic.ValidationError:
                    try:
                        old_card = OldCard.model_validate_json(content)
                        return old_card.to_card()
                    except pydantic.ValidationError:
                        print(f"Failed to read card from file '{path}'")
        except OSError as e:
            print(f"An error occurred while accessing '{path}': {e}")
        return None


class OldCard(pydantic.BaseModel):
    id: str
    sentence: str
    native_sentence: str
    audio_filename: str
    slow_audio_filename: str
    native_audio_filename: str
    phonetic: str | None
    units: list[str]
    unit_tags: dict[str, str]
    notes: list[str]

    def to_card(self) -> Card:
        new_unit_tags = [
            UnitTag(occurance=k, unit_id=v) for k, v in self.unit_tags.items()
        ]
        new_unit_tags.sort(key=lambda tag: self.sentence.find(tag.occurance))
        return Card(
            id=self.id,
            sentence=self.sentence,
            native_sentence=self.native_sentence,
            audio_filename=self.audio_filename,
            slow_audio_filename=self.slow_audio_filename,
            native_audio_filename=self.native_audio_filename,
            phonetic=self.phonetic,
            unit_tags=new_unit_tags,
            notes=self.notes,
        )


async def _write_ogg(audio: np.ndarray, filename: str, bitrate="16k") -> None:
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
        filename,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input=audio.tobytes())
    if process.returncode != 0:
        print(f"Error writing {filename}: {stderr.decode()}")


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
        self._index: dict[str, list[str]] = {}
        self._card_directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, target_language: Language, native_language: Language) -> Self:
        obj = cls(target_language, native_language)
        try:
            with open(obj._index_path, "r", encoding="utf-8") as f:
                obj._index = json.load(f)
            if obj._index:
                use_def = all(" - " in k for k in obj._index.keys())
                target_language.initialize(use_definition=use_def)
        except Exception:
            print(f"Unable to open {obj._index_path}, creating empty CardIndex.")
        return obj

    async def restart(self) -> None:
        self._index = {}
        cards = await self.all_cards()
        print(f"Starting CardIndex with {len(cards)} cards.")
        for card in cards:
            self._add(card)
        self.save()

    async def check(self) -> None:
        cards = await self.all_cards()
        language_system = self._target_language.writing_system
        print(f"Found {len(cards)} cards for {language_system}")
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
        if extra_filenames:
            print(f"Unused audio files found: {extra_filenames}")

    def save(self) -> None:
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f)

    def cards(self, unit: Unit) -> list[Card]:
        card_ids = self._index.get(unit.id(), [])
        cards = []
        for card_id in card_ids:
            card = Card.load(self._card_directory, card_id)
            if card is not None:
                cards.append(card)
        return cards

    async def cards_async(self, unit: Unit) -> list[Card]:
        card_ids = self._index.get(unit.id(), [])
        tasks = []
        for card_id in card_ids:
            tasks.append(Card.load_async(self._card_directory, card_id))
        cards = await asyncio.gather(*tasks)
        return [card for card in cards if card is not None]

    async def all_cards(self) -> list[Card]:
        semaphore = asyncio.Semaphore(16)

        async def read_card_file(card_id: str) -> Card | None:
            async with semaphore:
                return await Card.load_async(self._card_directory, card_id)

        tasks = [read_card_file(p.stem) for p in self._card_directory.glob("*.json")]
        cards = await asyncio.gather(*tasks)
        return [card for card in cards if card is not None]

    def size(self, unit: Unit) -> int:
        return len(self._index.get(unit.id(), []))

    def _add(self, card: Card) -> None:
        for unit in card.unit_ids():
            card_ids = self._index.get(unit, [])
            card_ids.append(card.id)
            self._index[unit] = card_ids

    @llm.standard_retry
    async def create_card(
        self,
        llm_client: llm.LlmClient,
        sentence: str,
        unit_tags: UnitTags,
        notes: list[str] = [],
    ) -> Card:
        id = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
        native_sentence = await llm_client.translate(sentence, self._native_language)
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
        phonetic = await llm_client.to_phonetic(sentence, self._target_language)
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
