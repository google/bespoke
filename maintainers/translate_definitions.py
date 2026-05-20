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

"""Tool to translate unit definitions to a native language."""

import argparse
import asyncio
import csv
from pathlib import Path

from bespoke import languages
from bespoke import llm
from bespoke.unit import Unit


async def translate_unit(
    unit: Unit,
    llm_client: llm.LlmClient,
    native_language: languages.Language,
    semaphore: asyncio.Semaphore,
    results: dict[str, str],
) -> None:
    async with semaphore:
        definition = unit.definition()
        if not definition:
            results[unit.id()] = ""
            return
        try:
            translated = await llm_client.translate(definition, native_language)
            results[unit.id()] = translated
        except Exception as e:
            print(f"Error translating {unit.id()}: {e}")
            results[unit.id()] = ""


async def main_async():
    parser = argparse.ArgumentParser(
        description="Translate unit definitions to native language."
    )
    target_choices = {}
    for language in languages.LANGUAGES.values():
        if language.has_data():
            target_choices[language.writing_system] = language
    native_choices = {
        lang.writing_system: lang for lang in languages.LANGUAGES.values()
    }
    parser.add_argument(
        "--target",
        type=str,
        choices=list(target_choices),
        required=True,
        help="The language of the units.",
    )
    parser.add_argument(
        "--native",
        type=str,
        choices=list(native_choices),
        required=True,
        help="The language to translate definitions into.",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output CSV file path.",
    )
    args = parser.parse_args()

    target_language = target_choices[args.target]
    native_language = native_choices[args.native]
    units = target_language.units()
    print(f"Found {len(units)} units in {target_language.writing_system}.")

    llm_client = llm.get_llm_client()
    semaphore = asyncio.Semaphore(16)
    results = {}

    async with asyncio.TaskGroup() as tg:
        for unit in units:
            tg.create_task(
                translate_unit(unit, llm_client, native_language, semaphore, results)
            )
    output_path = Path(args.output)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["unit_id", "translated_definition"])
        for unit in units:
            writer.writerow([unit.id(), results.get(unit.id(), "")])
    print(f"Created {output_path}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
