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

from bespoke import DictionaryUnit
from bespoke import Unit
from bespoke import WordUnit
from bespoke import languages
from bespoke import llm


def validate_translation(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if any(char in text for char in ["[", "]", "(", ")", "*", "\n", "\r"]):
        return False
    if len(text) > 100:
        return False
    return True


async def translate_unit(
    unit: Unit,
    target_language: languages.Language,
    llm_client: llm.LlmClient,
    native_language: languages.Language,
    results: dict[str, str],
    name_to_definitions: dict[str, list[str]],
) -> None:
    target = target_language.writing_system
    native = native_language.writing_system
    name = unit.name()

    if isinstance(unit, WordUnit):
        task = f"Translate the word '{name}' into {native}."
        instructions = f"Provide only the direct translation equivalents in {native}."
    elif isinstance(unit, DictionaryUnit):
        task = (
            f"Translate the word '{name}' into {native}.\n"
            f"The specific meaning referred to is defined as: "
            f"'{unit.definition()}'."
        )
        other_definitions = [
            d for d in name_to_definitions.get(name, []) if d != unit.definition()
        ]
        if other_definitions:
            definitions_list = "\n".join(f"- '{d}'" for d in other_definitions)
            task += (
                f"\n\nNote that the word '{name}' has other meanings defined "
                f"as follows:\n{definitions_list}\n"
                "Your translation MUST NOT cover those other meanings. "
                "Choose translations that apply specifically to the target "
                "meaning only."
            )
        instructions = (
            f"Provide the most precise translation in {native} that fits "
            f"the definition. Do NOT translate the definition itself. "
            f"Translate only the word '{name}'."
        )
    else:
        raise ValueError(f"Unknown unit type: {type(unit)}")

    prompt = (
        f"You are a lexicographer translating from {target} to {native}.\n"
        f"{task}\n\n"
        "Rules:\n"
        f"1. {instructions}\n"
        "2. Separate multiple synonyms with commas.\n"
        f"3. Do NOT include the original word '{name}' or any {target} "
        "characters in your response.\n"
        "4. Do NOT include any pronunciation, or phonetics.\n"
        "5. Do NOT include grammatical labels, parts of speech, gender "
        "abbreviations, or explanations (do NOT write 'Noun', 'Verb', "
        "'(f)', '(m)', etc.).\n"
        "6. Do NOT use markdown formatting (no bold, no italics, "
        "no asterisks).\n"
        "7. The output must be on a single line.\n\n"
        "8. The output will be automatically processed, return no other text.\n"
    )

    translated = ""
    for attempt in range(3):
        try:
            raw_translated = await llm_client.text_call(prompt)
            raw_translated = raw_translated.strip()
            if validate_translation(raw_translated):
                translated = raw_translated
                break
            else:
                print(
                    f"Warning: Attempt {attempt + 1} for {unit.id()} "
                    f"failed validation: '{raw_translated}'"
                )
        except Exception as e:
            print(f"Error for {unit.id()}: {e}")
            await asyncio.sleep(1)

    if translated:
        results[unit.id()] = translated
    else:
        print(f"Error: Failed to translate {unit.id()} after 3 attempts.")


async def main_async():
    parser = argparse.ArgumentParser(
        description="Translate units to generate dictionary entries."
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
        help="The language of the units to be translated.",
    )
    parser.add_argument(
        "--native",
        type=str,
        choices=list(native_choices),
        required=True,
        help="The native language to translate into.",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path. Defaults to cards/translations_{target}_{native}.csv",
    )
    args = parser.parse_args()

    target_language = target_choices[args.target]
    native_language = native_choices[args.native]

    if not args.output:
        args.output = (
            f"cards/translations_{target_language.code_name}_"
            f"{native_language.code_name}.csv"
        )

    units = target_language.units()
    print(f"Found {len(units)} units in {target_language.writing_system}.")

    name_to_definitions = {}
    for u in units:
        if isinstance(u, DictionaryUnit):
            name_to_definitions.setdefault(u.name(), []).append(u.definition())

    results = {}
    output_path = Path(args.output)
    if output_path.exists():
        print(f"Loading existing translations from {output_path}...")
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = row.get("unit_id")
                    trans = row.get("translation", "")
                    if uid:
                        results[uid] = trans
            existing_count = sum(1 for t in results.values() if t.strip())
            print(
                f"Loaded {len(results)} entries, {existing_count} already translated."
            )
        except Exception as e:
            print(f"Warning: Failed to read existing translations: {e}")

    units_to_translate = [u for u in units if not results.get(u.id(), "").strip()]
    print(f"Need to translate {len(units_to_translate)} units.")

    llm_client = llm.get_llm_client()
    semaphore = asyncio.Semaphore(16)

    try:
        async with asyncio.TaskGroup() as tg:
            for unit in units_to_translate:
                await semaphore.acquire()

                async def run_task(u=unit):
                    try:
                        await translate_unit(
                            u,
                            target_language,
                            llm_client,
                            native_language,
                            results,
                            name_to_definitions,
                        )
                    finally:
                        semaphore.release()

                tg.create_task(run_task())
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nTranslation run was interrupted/cancelled. Saving progress...")
    finally:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["unit_id", "translation"])
            for unit in units:
                writer.writerow([unit.id(), results.get(unit.id(), "")])

        success_count = sum(1 for u in units if results.get(u.id(), "").strip())
        print(
            f"Progress saved to {output_path}. Total translated: "
            f"{success_count}/{len(units)}"
        )


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
