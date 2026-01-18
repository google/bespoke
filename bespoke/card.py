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

import aiofiles
import asyncio
import hashlib
import json
import numpy as np
import pydantic
from typing import Self
import os

from bespoke.languages import Difficulty
from bespoke.languages import Language
from bespoke.languages import UnitTags
from bespoke import llm


class Card(pydantic.BaseModel):
    id: str
    sentence: str
    native_sentence: str
    audio_filename: str
    slow_audio_filename: str
    native_audio_filename: str
    phonetic: str | None
    units: list[str]
    unit_tags: UnitTags
    notes: list[str]

    model_config = pydantic.ConfigDict(frozen=True)

    def __str__(self) -> str:
        parts = []
        for occurance, unit in self.split_into_parts():
            if unit is None:
                parts.append(occurance)
            else:
                parts.append(f"[{occurance}]({unit})")
        return f"Card: {''.join(parts)} = {self.native_sentence}"

    def split_into_parts(self) -> list[tuple[str, str | None]]:
        sorted_tags = list(self.unit_tags.items())
        sorted_tags.sort(key=lambda x: len(x[1]), reverse=True)
        sorted_tags.sort(key=lambda x: len(x[0]), reverse=True)
        result = [(self.sentence, None)]
        for word, unit in sorted_tags:
            new_result = []
            found = False
            for part, tag in result:
                if found or tag is not None or word not in part:
                    new_result.append((part, tag))
                    continue
                prefix, suffix = part.split(word, maxsplit=1)
                if prefix.strip():
                    new_result.append((prefix.strip(), None))
                new_result.append((word, unit))
                if suffix.strip():
                    new_result.append((suffix.strip(), None))
                found = True
            result = new_result
        return result

    def write_json(self, directory: str) -> None:
        filename = os.path.join(directory, f"{self.id}.json")
        with open(filename, "w") as f:
            f.write(self.model_dump_json())


def _load_card(directory: str, card_id: str) -> Card | None:
    filename = os.path.join(directory, f"{card_id}.json")
    try:
        with open(filename, "r") as f:
            return Card.model_validate_json(f.read())
    except pydantic.ValidationError as e:
        print(f"Failed to read card from file '{filename}'")
    except OSError as e:
        print(f"An error occurred while accessing '{filename}': {e}")
    return None


async def _load_card_async(directory: str, card_id: str) -> Card | None:
    filename = os.path.join(directory, f"{card_id}.json")
    try:
        async with aiofiles.open(filename, mode="r") as f:
            return Card.model_validate_json(await f.read())
    except pydantic.ValidationError as e:
        print(f"Failed to read card from file '{filename}'")
    except OSError as e:
        print(f"An error occurred while accessing '{filename}': {e}")
    return None


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
    *,
    directory: str,
    sentence: str,
    language: Language,
    slowly: bool,
) -> str:
    audio = await llm.speak(sentence, language, slowly=slowly)
    sentence_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
    if slowly:
        suffix = "_slow"
    else:
        suffix = ""
    filename = os.path.join(directory, f"{sentence_hash}{suffix}.ogg")
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
        self._index_filename = f"cards/index_{target}_{native}.json"
        self._card_directory = f"cards/{target}_{native}"
        self._index = {}
        os.makedirs(self._card_directory, exist_ok=True)

    @classmethod
    def load(cls, target_language: Language, native_language: Language) -> Self:
        obj = cls(target_language, native_language)
        try:
            with open(obj._index_filename) as f:
                obj._index = json.load(f)
        except:
            print(f"Unable to open {obj._index_filename}, creating empty CardIndex.")
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
        for filename in os.listdir(self._card_directory):
            if filename.endswith(".ogg"):
                audio_filenames.add(f"{self._card_directory}/{filename}")
                continue
            if not filename.endswith(".json"):
                print(f"Unexpected file '{filename}'")
        card_filenames = set()
        for card in cards:
            card_filenames.add(card.audio_filename)
            card_filenames.add(card.slow_audio_filename)
            card_filenames.add(card.native_audio_filename)
            if card.audio_filename not in audio_filenames:
                print(f"Missing target audio file for card '{card.id}'")
            if card.slow_audio_filename not in audio_filenames:
                print(f"Missing slow audio file for '{card.id}'")
            if card.native_audio_filename not in audio_filenames:
                print(f"Missing native audio file for '{card.id}'")
        extra_filenames = audio_filenames - card_filenames
        if extra_filenames:
            print(f"Unused audio files found: {extra_filenames}")

    def save(self) -> None:
        with open(self._index_filename, "w") as f:
            json.dump(self._index, f)

    def cards(self, unit: str) -> list[Card]:
        card_ids = self._index.get(unit, [])
        cards = []
        for card_id in card_ids:
            card = _load_card(self._card_directory, card_id)
            if card is not None:
                cards.append(card)
        return cards

    async def cards_async(self, unit: str) -> list[Card]:
        card_ids = self._index.get(unit, [])
        tasks = []
        for card_id in card_ids:
            if os.path.isfile(os.path.join(self._card_directory, f"{card_id}.json")):
                tasks.append(_load_card_async(self._card_directory, card_id))
        cards = await asyncio.gather(*tasks)
        return [card for card in cards if card is not None]

    async def all_cards(self) -> list[Card]:
        semaphore = asyncio.Semaphore(16)

        async def read_card_file(name: str) -> Card | None:
            async with semaphore:
                return await _load_card_async(
                    self._card_directory, name.removesuffix(".json")
                )

        tasks = []
        for name in os.listdir(self._card_directory):
            if not name.endswith(".json"):
                continue
            tasks.append(read_card_file(name))
        cards = await asyncio.gather(*tasks)
        return [card for card in cards if card is not None]

    def size(self, unit: str) -> int:
        return len(self._index.get(unit, []))

    def _add(self, card: Card) -> None:
        for unit in card.units:
            card_ids = self._index.get(unit, [])
            card_ids.append(card.id)
            self._index[unit] = card_ids

    @llm.standard_retry
    async def create_card(
        self,
        sentence: str,
        unit_tags: UnitTags,
        notes: list[str] = [],
    ) -> Card:
        id = hashlib.sha256(sentence.encode("utf-8")).hexdigest()
        native_sentence = await llm.translate(sentence, self._native_language)
        audio_filename = await _write_audio_file(
            directory=self._card_directory,
            sentence=sentence,
            language=self._target_language,
            slowly=False,
        )
        slow_audio_filename = await _write_audio_file(
            directory=self._card_directory,
            sentence=sentence,
            language=self._target_language,
            slowly=True,
        )
        native_audio_filename = await _write_audio_file(
            directory=self._card_directory,
            sentence=native_sentence,
            language=self._native_language,
            slowly=False,
        )
        phonetic = await llm.to_phonetic(sentence, self._target_language)
        units = list(set(unit_tags.values()))
        card = Card(
            id=id,
            sentence=sentence,
            native_sentence=native_sentence,
            audio_filename=audio_filename,
            slow_audio_filename=slow_audio_filename,
            native_audio_filename=native_audio_filename,
            phonetic=phonetic,
            units=units,
            unit_tags=unit_tags,
            notes=notes,
        )
        card.write_json(self._card_directory)
        self._add(card)
        return card
